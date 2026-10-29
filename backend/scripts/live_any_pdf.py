"""LIVE end-to-end check over HTTP against a running `make serve` (real model, any PDF).

    uv run python scripts/live_any_pdf.py [--base http://localhost:8000] [--gap 50]

Uploads each PDF in fixtures/pdfs/real/, waits for OCR, fetches suggestions, asks free-form questions
(spaced by --gap seconds for Groq's per-minute token limit) and writes data/live-any-pdf.json + a
markdown table on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
PDFS = ROOT / "fixtures" / "pdfs" / "real"

PLAN = [
    (
        "resume-ner-peft.pdf",
        [
            ("en", "How does LoRA compare with full fine-tuning in this report?"),
            ("ar", "إيه الخطوات اللي عملوها علشان يدربوا الموديل؟"),
            ("en", "Quiz me on the key ideas of this report."),
        ],
    ),
    (
        "smart-job-matching.pdf",
        [
            ("en", "Compare content-based, collaborative and hybrid recommendation approaches."),
            ("ar", "إزاي LinkedIn و Indeed بيرشحوا الوظايف للناس؟"),
            ("en", "Which steps does a job recommendation pipeline go through?"),
        ],
    ),
    (
        "cot.pdf",
        [
            ("ar", "إيه حدود الـ chain-of-thought اللي الورقة بتعترف بيها؟"),
            ("en", "Which tasks did chain-of-thought help least, and why?"),
            ("en", "Make a table of the commonsense benchmarks and what each one tests."),
        ],
    ),
]


def sse_events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            out.append((name, data))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--gap", type=float, default=50)
    args = ap.parse_args()
    headers = {"X-Client-Id": f"live-check-{uuid.uuid4().hex[:12]}"}
    client = httpx.Client(base_url=args.base, headers=headers, timeout=240)
    cfg = client.get("/api/config").json()
    print("provider:", cfg["provider"], "| mock:", cfg["mock"], flush=True)
    if cfg["mock"]:
        print("server is in mock mode: run `make serve`")
        return 2
    results = []
    first = True
    for filename, questions in PLAN:
        t0 = time.time()
        r = client.post("/api/documents", files={"file": (filename, (PDFS / filename).read_bytes(), "application/pdf")})
        r.raise_for_status()
        doc = r.json()
        while doc["status"] != "ready":
            time.sleep(1)
            doc = client.get(f"/api/documents/{doc['doc_id']}").json()
        upload_s = round(time.time() - t0, 1)
        sugg = {
            lang: client.get(f"/api/documents/{doc['doc_id']}/suggestions?lang={lang}").json() for lang in ("en", "ar")
        }
        print(
            f"\n== {filename}: {doc['pages']} pages, lang={doc['language']}, OCR pages={len(doc['ocr_pages'])}, "
            f"ready in {upload_s}s, demo={doc['is_demo']}",
            flush=True,
        )
        for lang in ("en", "ar"):
            print(f"   suggestions[{lang}] generated={sugg[lang]['generated']}: {sugg[lang]['questions']}", flush=True)
        for lang, q in questions:
            if not first:
                time.sleep(args.gap)
            first = False
            t1 = time.time()
            resp = client.post("/api/ask", json={"doc_id": doc["doc_id"], "question": q, "lang": lang})
            wall = round(time.time() - t1, 1)
            if resp.status_code != 200:
                results.append(
                    {
                        "pdf": filename,
                        "lang": lang,
                        "question": q,
                        "http": resp.status_code,
                        "error": resp.text[:200],
                        "wall_s": wall,
                    }
                )
                print(f"   [{lang}] HTTP {resp.status_code}: {resp.text[:120]}", flush=True)
                continue
            ev = sse_events(resp.text)
            comps = [d for n, d in ev if n == "COMPONENT"]
            drops = [d for n, d in ev if n == "COMPONENT_DROPPED"]
            m = next((d for n, d in ev if n == "METRICS"), {}) or {}
            err = next((d for n, d in ev if n == "RUN_ERROR"), None)
            ret = m.get("retrieval", {})
            row = {
                "pdf": filename,
                "lang": lang,
                "question": q,
                "answer": "".join(d["delta"] for n, d in ev if n == "TEXT_MESSAGE_CONTENT")[:240],
                "visual": bool(comps),
                "types": [c["type"] for c in comps],
                "statuses": [c["verification"]["status"] for c in comps],
                "citations_dropped": sum(c["verification"]["dropped_points"] for c in comps),
                "dropped": [f"{d['type']}:{d['reason']}" for d in drops],
                "warnings": [d["code"] for n, d in ev if n == "WARNING"],
                "error": err,
                "model": m.get("model"),
                "fallback": m.get("fallback_used"),
                "latency_s": round((m.get("latency_ms") or {}).get("total", 0) / 1000, 1),
                "model_s": round((ret.get("upstream_ms") or 0) / 1000, 1),
                "wall_s": wall,
                "prompt_tokens": (m.get("tokens") or {}).get("input"),
                "pages_sent": ret.get("pages"),
                "search_query": ret.get("search_query"),
            }
            results.append(row)
            print(
                f"   [{lang}] {q}\n      -> visual={row['visual']} {row['types']} {row['statuses']} "
                f"dropped={row['dropped']} latency={row['latency_s']}s (model {row['model_s']}s) "
                f"tokens={row['prompt_tokens']} translated={bool(row['search_query'])} "
                f"error={err['code'] if err else None}",
                flush=True,
            )
    out = ROOT / "data" / "live-any-pdf.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
