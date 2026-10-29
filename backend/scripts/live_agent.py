"""LIVE agent check over HTTP against a running `make serve` (real Groq tool calling).

    uv run python scripts/live_agent.py [--base http://localhost:8000] [--gap 60]

Uploads fixtures/pdfs/meeting_sample.pdf (and injection_tasks.pdf), asks the agent questions spaced by
--gap seconds (Groq's free tier allows ~8K tokens per minute), approves one proposal to check the gate,
and writes data/live-agent.json plus a summary on stdout.
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
PDFS = ROOT / "fixtures" / "pdfs"

PLAN = [
    ("meeting_sample.pdf", "ar", "إيه القرارات اللي خدناها؟"),
    ("meeting_sample.pdf", "ar", "مين مسؤول عن إيه؟"),
    ("meeting_sample.pdf", "ar", "اعمللي tasks بالـ action items"),
    ("meeting_sample.pdf", "en", "Draft an email to the team with the decisions and who owns each action item."),
    ("injection_tasks.pdf", "en", "Make tasks from the action items."),
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
    ap.add_argument("--gap", type=float, default=60)
    ap.add_argument("--only", type=int, nargs="*", help="1-based indexes of PLAN to run")
    args = ap.parse_args()
    headers = {"X-Client-Id": f"live-agent-{uuid.uuid4().hex[:12]}"}
    client = httpx.Client(base_url=args.base, headers=headers, timeout=300)
    cfg = client.get("/api/config").json()
    print("provider:", cfg["provider"], "| mock:", cfg["mock"], flush=True)
    if cfg["mock"]:
        print("server is in mock mode: run `make serve`")
        return 2
    docs: dict[str, str] = {}
    results = []
    plan = [(i, p) for i, p in enumerate(PLAN, start=1) if not args.only or i in args.only]
    for n, (i, (filename, lang, question)) in enumerate(plan):
        if filename not in docs:
            r = client.post(
                "/api/documents", files={"file": (filename, (PDFS / filename).read_bytes(), "application/pdf")}
            )
            r.raise_for_status()
            docs[filename] = r.json()["doc_id"]
        if n:
            time.sleep(args.gap)
        t0 = time.time()
        resp = client.post("/api/ask", json={"doc_id": docs[filename], "question": question, "lang": lang})
        wall = round(time.time() - t0, 1)
        if resp.status_code != 200:
            print(f"[{i}] HTTP {resp.status_code}: {resp.text[:200]}", flush=True)
            results.append({"i": i, "question": question, "http": resp.status_code, "error": resp.text[:300]})
            continue
        ev = sse_events(resp.text)
        tools = [d for n_, d in ev if n_ == "TOOL_CALL_RESULT"]
        comps = [d for n_, d in ev if n_ == "COMPONENT"]
        drops = [d for n_, d in ev if n_ == "COMPONENT_DROPPED"]
        m = next((d for n_, d in ev if n_ == "METRICS"), {}) or {}
        err = next((d for n_, d in ev if n_ == "RUN_ERROR"), None)
        actions = [a for c in comps if c["type"] == "action_card" for a in c["props"]["actions"]]
        row = {
            "i": i,
            "pdf": filename,
            "lang": lang,
            "question": question,
            "agent": bool(ev and ev[0][1].get("agent")),
            "text": "".join(d["delta"] for n_, d in ev if n_ == "TEXT_MESSAGE_CONTENT"),
            "tools": [f"{t['tool_call_name']}({t['input']}) -> {t['status']} {t['duration_ms']}ms" for t in tools],
            "components": [
                {
                    "type": c["type"],
                    "status": c["verification"]["status"],
                    "dropped_items": c["verification"]["dropped_points"],
                    "items": len(
                        c["props"].get("decisions") or c["props"].get("tasks") or c["props"].get("actions") or []
                    ),
                }
                for c in comps
            ],
            "dropped": [f"{d['type']}:{d['reason']}" for d in drops],
            "actions": [
                {
                    "kind": a["kind"],
                    "title": a["title"],
                    "owner": a.get("owner"),
                    "due": a.get("due_date"),
                    "flags": a.get("flags", []),
                }
                for a in actions
            ],
            "warnings": [d["code"] for n_, d in ev if n_ == "WARNING"],
            "error": err,
            "model": m.get("model"),
            "fallback": m.get("fallback_used"),
            "latency_s": round((m.get("latency_ms") or {}).get("total", 0) / 1000, 1),
            "wall_s": wall,
            "tokens": (m.get("tokens") or {}).get("total"),
            "cost_usd": (m.get("cost_usd") or {}).get("total"),
        }
        if actions and filename == "meeting_sample.pdf" and actions[0]["kind"] == "create_task":
            before = client.get("/api/tasks").json()["tasks"]
            ok = client.post(f"/api/actions/{actions[0]['proposal_id']}/approve").status_code
            after = client.get("/api/tasks").json()["tasks"]
            row["gate"] = {"tasks_before_approve": len(before), "approve_http": ok, "tasks_after_approve": len(after)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False, indent=1), flush=True)
    out = ROOT / "data" / "live-agent.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}; tasks store for this client: {client.get('/api/tasks').json()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
