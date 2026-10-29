"""List Gemini models, confirm MODEL/FALLBACK_MODEL exist, and count tokens for cot.pdf.

Makes no generation calls: models.list, files.upload and count_tokens only.
"""

import hashlib
import os
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PDF = ROOT / "fixtures" / "pdfs" / "cot.pdf"


def main() -> int:
    data = PDF.read_bytes()
    with pdfplumber.open(PDF) as pdf:
        pages = len(pdf.pages)
    print(f"cot.pdf sha256={hashlib.sha256(data).hexdigest()} pages={pages} bytes={len(data)}")

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("no key: skipping model check")
        return 0

    from google import genai

    model = os.getenv("MODEL", "gemini-3.8-flash")
    fallback = os.getenv("FALLBACK_MODEL", "gemini-3.1-flash-lite")
    client = genai.Client(api_key=key)

    names = sorted(m.name.removeprefix("models/") for m in client.models.list())
    print("generateContent-capable gemini models:")
    for n in names:
        if n.startswith("gemini"):
            print("  ", n)
    status = 0
    for wanted in (model, fallback):
        ok = wanted in names
        print(f"{wanted}: {'FOUND' if ok else 'MISSING'}")
        status |= 0 if ok else 2

    if model in names:
        uploaded = client.files.upload(file=PDF, config={"mime_type": "application/pdf"})
        resp = client.models.count_tokens(model=model, contents=[uploaded])
        total = resp.total_tokens or 0
        print(f"count_tokens({model}) total={total} per_page={total / pages:.1f}")
        details = getattr(resp, "prompt_tokens_details", None) or getattr(resp, "cache_tokens_details", None)
        if details:
            for d in details:
                print(f"  modality={d.modality} tokens={d.token_count}")
    return status


if __name__ == "__main__":
    sys.exit(main())
