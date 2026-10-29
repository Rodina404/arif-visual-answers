"""OCR for pages without a text layer (scanned PDFs, slide decks exported as images).

RapidOCR runs locally on onnxruntime (no network, no document leaves the server). Its text becomes the
page's visible text, so retrieval and grounding work on scanned pages; the page is flagged `ocr=True`
and the UI says the text was recognised. Arabic is not in RapidOCR's default models: Arabic scans stay
without text (and their claims show "Not verified").
"""

from __future__ import annotations

import io
import logging
import threading
from typing import Any

import pdfplumber

log = logging.getLogger("arif.ocr")

RENDER_WIDTH = 1280
_engine: Any = None
_lock = threading.Lock()


def _get_engine() -> Any:
    global _engine
    with _lock:
        if _engine is None:
            logging.getLogger("RapidOCR").setLevel(logging.WARNING)
            from rapidocr import RapidOCR

            _engine = RapidOCR()
        return _engine


def lines_from_result(result: Any) -> list[str]:
    """Group recognised boxes into reading-order lines (top to bottom, then left to right)."""
    boxes = getattr(result, "boxes", None)
    txts = list(getattr(result, "txts", None) or [])
    if boxes is None or not txts:
        return txts
    items = []
    for box, text in zip(boxes, txts, strict=False):
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), text))
    items.sort()
    lines: list[list[tuple[float, str]]] = []
    bottoms: list[float] = []
    for top, bottom, x, text in items:
        mid = (top + bottom) / 2
        if lines and mid < bottoms[-1]:
            lines[-1].append((x, text))
            bottoms[-1] = max(bottoms[-1], bottom)
        else:
            lines.append([(x, text)])
            bottoms.append(bottom)
    return [" ".join(t for _, t in sorted(line)) for line in lines]


def ocr_pages(data: bytes, numbers: list[int]) -> dict[int, str]:
    """OCR the given 1-based page numbers; returns {page: text}. Failures leave a page empty."""
    import numpy as np

    out: dict[int, str] = {}
    engine = _get_engine()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for n in numbers:
            try:
                image = pdf.pages[n - 1].to_image(width=RENDER_WIDTH).original.convert("RGB")
                out[n] = "\n".join(lines_from_result(engine(np.array(image)))).strip()
            except Exception as exc:  # one bad page must not lose the rest
                log.warning("OCR failed on page %s: %s", n, exc)
                out[n] = ""
    return out
