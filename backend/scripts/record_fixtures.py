"""LIVE: run demo questions through the real pipeline and save passing outputs as mock fixtures.

Every question is one generation call against the budget. Usage:
    uv run python scripts/record_fixtures.py q1:en q2:ar          # visual mode
    uv run python scripts/record_fixtures.py --text q1:ar          # 'Before' text mode
    uv run python scripts/record_fixtures.py                       # all q1-q6 x ar,en (12 calls)
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys

from app.cache import AnswerCache
from app.config import ROOT, get_settings
from app.metrics import MetricsLog
from app.providers import get_provider
from app.stream import AskContext, TextRun, VisualRun

ANSWERS = ROOT / "fixtures" / "answers"
INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))


async def run_one(qid: str, lang: str, text_mode: bool) -> dict:
    settings = dataclasses.replace(
        get_settings(), mock_llm=False, llm_provider="gemini", log_raw_output=True, request_timeout_s=150
    )
    from app.upload import DocStore

    store = DocStore(settings)
    pdf = ROOT / "fixtures" / "pdfs" / "cot.pdf"
    doc = store.add(pdf.read_bytes(), "cot.pdf", "application/pdf")
    provider = get_provider(settings)
    handle = await provider.prepare_document(doc)
    question = INDEX["questions"]["cot"][qid][lang]
    tmp_cache = settings.data_dir / "record_cache.sqlite"
    tmp_cache.unlink(missing_ok=True)

    async def no_sleep(_: float) -> None:
        raise RuntimeError("recording does not retry")

    ctx = AskContext(
        sleep=no_sleep,
        settings=settings,
        provider=provider,
        doc=doc,
        handle=handle,
        question=question,
        lang=lang,
        cache=AnswerCache(tmp_cache),
        metrics=MetricsLog(),
    )
    run = TextRun(ctx) if text_mode else VisualRun(ctx)
    events = [e async for e in run.events()]
    names = [e[0] for e in events]
    metrics = next((d for n, d in events if n == "METRICS"), {})
    report = {
        "qid": qid,
        "lang": lang,
        "mode": "text" if text_mode else "visual",
        "events": names,
        "dropped": [d for n, d in events if n == "COMPONENT_DROPPED"],
        "statuses": [d["verification"]["status"] for n, d in events if n == "COMPONENT"],
        "types": [d["type"] for n, d in events if n == "COMPONENT"],
        "metrics": metrics,
        "error": next((d for n, d in events if n == "RUN_ERROR"), None),
    }
    if text_mode:
        text = "".join(d["delta"] for n, d in events if n == "TEXT_MESSAGE_CONTENT")
        out = ANSWERS / "cot" / "text" / f"{qid}.{lang}.txt"
        if text and not report["error"]:
            out.write_text(text, encoding="utf-8")
            report["saved"] = str(out.relative_to(ROOT))
        return report

    raw_file = settings.data_dir / "logs" / f"{run.st.run_id}.json"
    if not raw_file.exists():
        report["passed"] = False
        return report
    raw = raw_file.read_text(encoding="utf-8")
    passed = not report["error"] and not report["dropped"] and all(s == "verified" for s in report["statuses"])
    try:
        pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except ValueError:
        pretty = raw
    dest = ANSWERS / "cot" if passed else ANSWERS / "_rejected"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{qid}.{lang}.json"
    out.write_text(pretty + "\n", encoding="utf-8")
    report["saved"] = str(out.relative_to(ROOT))
    report["passed"] = passed
    return report


def update_meta(report: dict) -> None:
    meta_file = ANSWERS / "cot" / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    key = f"{'text/' if report['mode'] == 'text' else ''}{report['qid']}.{report['lang']}"
    m = report.get("metrics") or {}
    meta[key] = {
        "source": "recorded" if report.get("passed", True) else "recorded-rejected",
        "model": m.get("model"),
        "tokens": m.get("tokens"),
        "cost_usd": (m.get("cost_usd") or {}).get("total"),
        "latency_ms": m.get("latency_ms"),
        "types": report.get("types"),
        "dropped": report.get("dropped"),
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="*", help="qid:lang, e.g. q1:en")
    ap.add_argument("--text", action="store_true", help="record the plain-text 'Before' answer")
    args = ap.parse_args()
    items = args.items or [f"q{i}:{lang}" for i in range(1, 7) for lang in ("ar", "en")]
    for item in items:
        qid, lang = item.split(":")
        report = await run_one(qid, lang, args.text)
        update_meta(report)
        print(json.dumps({k: v for k, v in report.items() if k != "events"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
