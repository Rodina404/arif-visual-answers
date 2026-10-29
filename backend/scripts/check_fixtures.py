"""Run fixtures through validation + grounding + policy against the real PDF and report each outcome."""

import json
import sys
from pathlib import Path

import pdfplumber

from app.config import ROOT
from app.policy import ComponentProcessor
from app.upload import StoredDoc, extract_pages

ANSWERS = ROOT / "fixtures" / "answers"
INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))
SLUG_TO_SHA = {v: k for k, v in INDEX["docs"].items()}


def load_doc(slug: str) -> StoredDoc:
    pdf_path = ROOT / "fixtures" / "pdfs" / f"{slug}.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        pages = extract_pages(pdf)
    return StoredDoc(SLUG_TO_SHA.get(slug, slug), SLUG_TO_SHA.get(slug, ""), pdf_path.name, str(pdf_path), 0, pages)


def check(path: Path, doc: StoredDoc) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    proc = ComponentProcessor(doc, needs_visual=bool(data.get("needs_visual")))
    out = []
    for i, raw in enumerate(data.get("components", [])):
        o = proc.process(raw, i)
        out.append({"type": o.type, "status": o.status, "dropped_points": o.dropped_points, "drop": o.drop_reason})
    return out


def main() -> int:
    bad = 0
    docs = {s: load_doc(s) for s in ("cot", "injection")}
    for slug, doc in docs.items():
        for f in sorted((ANSWERS / slug).glob("*.json")):
            if f.name == "meta.json":
                continue
            res = check(f, doc)
            ok = all(r["status"] == "verified" and not r["drop"] for r in res)
            bad += 0 if ok or slug != "cot" else 1
            print(("OK  " if ok else "FAIL"), f"{slug}/{f.name}", json.dumps(res, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
