"""Print the VISIBLE text of pages of a PDF (what grounding checks quotes against).

uv run python scripts/page_text.py ../fixtures/pdfs/cot.pdf 1 2 3
"""

import sys

import pdfplumber

from app.upload import extract_pages

with pdfplumber.open(sys.argv[1]) as pdf:
    pages = extract_pages(pdf)
for n in sys.argv[2:] or [str(p.number) for p in pages]:
    print(f"===== page {n} =====")
    print(pages[int(n) - 1].visible_text)
