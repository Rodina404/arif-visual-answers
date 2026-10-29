"""LIVE: run the demo questions on a provider, save the raw answers as live fixtures, report metrics.

    uv run python scripts/record_live.py --provider groq                 # q1-q6 x ar,en (12 calls)
    uv run python scripts/record_live.py --provider groq q2:ar q2:en
    uv run python scripts/record_live.py --provider gemini q1:ar --retrieval on

Fixtures go to fixtures/answers/live/<provider>/<qid>.<lang>.json (the model's JSON exactly as returned)
and are replayed by the mock when the UI's provider switch picks that provider. Every answer is saved,
including partial ones; report.json records how each one fared in validation and grounding.
Rate limits: a 429 waits its retry-after (up to 90 s here), then tries the fallback model.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
import time
from typing import Any

from app.cache import AnswerCache
from app.config import ROOT, get_settings
from app.metrics import MetricsLog
from app.providers import get_provider
from app.stream import AskContext, VisualRun
from app.upload import DocStore

ANSWERS = ROOT / "fixtures" / "answers"
INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))


def summarize(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    comps = [d for n, d in events if n == "COMPONENT"]
    drops = [d for n, d in events if n == "COMPONENT_DROPPED"]
    m = next((d for n, d in events if n == "METRICS"), {})
    return {
        "error": next((d for n, d in events if n == "RUN_ERROR"), None),
        "warnings": [d["code"] for n, d in events if n == "WARNING"],
        "types": [c["type"] for c in comps],
        "statuses": [c["verification"]["status"] for c in comps],
        "citations_dropped": sum(c["verification"]["dropped_points"] for c in comps),
        "downgraded": [c["downgraded_from"] for c in comps if c.get("downgraded_from")],
        "dropped": [f"{d['type']}:{d['reason']}" for d in drops],
        "metrics": m,
        "answer_chars": sum(len(d["delta"]) for n, d in events if n == "TEXT_MESSAGE_CONTENT"),
    }


async def run_one(provider_name: str, qid: str, lang: str, overrides: dict[str, Any]) -> dict[str, Any]:
    settings = dataclasses.replace(
        get_settings(),
        mock_llm=False,
        llm_provider=provider_name,
        log_raw_output=True,
        request_timeout_s=240,
        rate_limit_max_wait_s=90,
        **overrides,
    )
    store = DocStore(settings)
    doc = store.add((ROOT / "fixtures" / "pdfs" / "cot.pdf").read_bytes(), "cot.pdf", "application/pdf")
    provider = get_provider(settings, provider_name)
    handle = await provider.prepare_document(doc)
    cache_file = settings.data_dir / f"live_{provider_name}.sqlite"
    ctx = AskContext(
        settings=settings,
        provider=provider,
        doc=doc,
        handle=handle,
        question=INDEX["questions"]["cot"][qid][lang],
        lang=lang,
        cache=AnswerCache(cache_file),
        metrics=MetricsLog(),
        no_cache=True,
    )
    run = VisualRun(ctx)
    started = time.time()
    events = [e async for e in run.events()]
    report = {"qid": qid, "lang": lang, "provider": provider_name, "wall_s": round(time.time() - started, 1)}
    report.update(summarize(events))
    raw_file = settings.data_dir / "logs" / f"{run.st.run_id}.json"
    raw = raw_file.read_text(encoding="utf-8") if raw_file.exists() else ""
    out_dir = ANSWERS / "live" / provider_name
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw.strip():
        try:
            pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except ValueError:
            pretty = raw  # truncated/invalid output is kept verbatim: it is part of the evidence
        (out_dir / f"{qid}.{lang}.json").write_text(pretty + "\n", encoding="utf-8")
        report["saved"] = f"fixtures/answers/live/{provider_name}/{qid}.{lang}.json"
    return report


def table(reports: list[dict[str, Any]]) -> str:
    rows = [
        "| Q | lang | model | total s | prompt tok (est budget) | out+think tok | cost $ | pages sent | components | "
        "verified | citations dropped | dropped |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        m = r.get("metrics") or {}
        t = m.get("tokens", {})
        ret = m.get("retrieval", {})
        if r.get("error"):
            rows.append(
                f"| {r['qid']} | {r['lang']} | {m.get('model', '')} | {r['wall_s']} | — | — | — | — | "
                f"**error {r['error']['code']}** | — | — | — |"
            )
            continue
        rows.append(
            f"| {r['qid']} | {r['lang']} | {m.get('model')}{' (fallback)' if m.get('fallback_used') else ''} | "
            f"{(m.get('latency_ms') or {}).get('total', 0) / 1000:.1f} | {t.get('input')} "
            f"({ret.get('prompt_budget', '—')}) | {t.get('output', 0) + t.get('thinking', 0)} | "
            f"{(m.get('cost_usd') or {}).get('total', 0):.4f} | {','.join(map(str, ret.get('pages', [])))} | "
            f"{' '.join(r['types']) or 'text only'} | {r['statuses'].count('verified')}/{len(r['statuses'])} | "
            f"{r['citations_dropped']} | {', '.join(r['dropped']) or '—'} |"
        )
    return "\n".join(rows)


def aggregate(reports: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in reports if not r.get("error")]
    comps = sum(len(r["statuses"]) for r in ok)
    verified = sum(r["statuses"].count("verified") for r in ok)
    lat = sorted((r["metrics"]["latency_ms"]["total"] for r in ok), key=float)
    return {
        "runs": len(reports),
        "errors": len(reports) - len(ok),
        "components": comps,
        "verified": verified,
        "grounding_pass_rate": round(verified / comps, 3) if comps else None,
        "components_dropped": sum(len(r["dropped"]) for r in ok),
        "citations_dropped": sum(r["citations_dropped"] for r in ok),
        "latency_p50_s": round(lat[len(lat) // 2] / 1000, 1) if lat else None,
        "latency_max_s": round(lat[-1] / 1000, 1) if lat else None,
        "mean_prompt_tokens": round(sum(r["metrics"]["tokens"]["input"] for r in ok) / len(ok)) if ok else None,
        "mean_cost_usd": round(sum(r["metrics"]["cost_usd"]["total"] for r in ok) / len(ok), 5) if ok else None,
        "fallback_used": sum(1 for r in ok if r["metrics"].get("fallback_used")),
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="*", help="qid:lang (default: q1-q6 x ar,en)")
    ap.add_argument("--provider", default="groq", choices=["groq", "gemini"])
    ap.add_argument("--retrieval", choices=["auto", "on", "off"], default=None)
    args = ap.parse_args()
    items = args.items or [f"q{i}:{lang}" for i in range(1, 7) for lang in ("ar", "en")]
    overrides = {"retrieval": args.retrieval} if args.retrieval else {}
    out_dir = ANSWERS / "live" / args.provider
    report_file = out_dir / "report.json"
    previous = json.loads(report_file.read_text(encoding="utf-8"))["runs"] if report_file.exists() else []
    reports: list[dict[str, Any]] = []
    for item in items:
        qid, lang = item.split(":")
        r = await run_one(args.provider, qid, lang, overrides)
        reports.append(r)
        print(
            json.dumps(
                {k: r[k] for k in ("qid", "lang", "wall_s", "types", "statuses", "dropped", "error")},
                ensure_ascii=False,
            ),
            flush=True,
        )
    merged = {(r["qid"], r["lang"]): r for r in previous}
    merged.update({(r["qid"], r["lang"]): r for r in reports})
    runs = sorted(merged.values(), key=lambda r: (r["qid"], r["lang"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps({"provider": args.provider, "summary": aggregate(runs), "runs": runs}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(table(runs))
    print(json.dumps(aggregate(runs), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
