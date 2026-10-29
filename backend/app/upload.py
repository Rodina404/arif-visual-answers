"""PDF upload validation, per-page text layers, hidden-text detection and storage."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from .config import Settings

MIN_VISIBLE_PT = 4.0
WHITE_LUMINANCE = 0.9
X_TOLERANCE = 1.5  # pdfplumber's default (3) glues words together in LaTeX papers
# Real papers contain tiny but dark glyphs (figure tick labels), so tiny text needs a higher bar than
# white or off-page text, which has no innocent reason to exist.
WHITE_OR_OFFPAGE_THRESHOLD = 10
TINY_THRESHOLD = 60
RETENTION_S = 48 * 3600
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


class UploadError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class PageText:
    number: int
    visible_text: str
    all_text: str
    hidden_chars: int = 0
    suspicious: bool = False
    ocr: bool = False  # text recognised from the page image (no text layer)


@dataclass
class StoredDoc:
    doc_id: str
    sha256: str
    filename: str
    path: str
    created_at: float
    pages: list[PageText]
    hidden_pages: list[int] = field(default_factory=list)
    questions_asked: int = 0
    provider_handles: dict[str, Any] = field(default_factory=dict)
    token_count: int | None = None
    status: str = "ready"  # "reading" while OCR runs in the background
    owner: str = ""  # the browser that uploaded it (X-Client-Id); lists show only the owner's documents
    language: str = "en"  # dominant script of the text: "en" (Latin), "ar" or "other"

    @property
    def needs_ocr(self) -> list[int]:
        return [p.number for p in self.pages if not p.visible_text.strip() and not p.ocr]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def page(self, n: int) -> PageText | None:
        return self.pages[n - 1] if 1 <= n <= len(self.pages) else None

    def warnings(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if self.hidden_pages:
            out.append(
                {
                    "code": "HIDDEN_TEXT_DETECTED",
                    "message": "Hidden text (tiny, white or off-page) found; it is ignored when verifying claims.",
                    "pages": self.hidden_pages,
                }
            )
        ocr = [p.number for p in self.pages if p.ocr and p.visible_text.strip()]
        if ocr:
            out.append(
                {
                    "code": "OCR_USED",
                    "message": "Text on these pages was recognised from images (OCR); quotes are checked against it.",
                    "pages": ocr,
                }
            )
        empty = [p.number for p in self.pages if not p.visible_text.strip() and (p.ocr or self.status != "reading")]
        if empty:
            out.append(
                {
                    "code": "NO_TEXT_PAGES",
                    "message": "Some pages have no extractable text (scanned?). Claims citing them can't be verified.",
                    "pages": empty,
                }
            )
        return out


_ARABIC = re.compile("[؀-ۿ]")
_LATIN = re.compile("[A-Za-z]")


def detect_language(text: str) -> str:
    """Dominant script: "ar" for Arabic, "en" for Latin (any Latin-script language), else "other"."""
    ar, la = len(_ARABIC.findall(text)), len(_LATIN.findall(text))
    if ar + la < 20:
        return "other" if text.strip() else "en"
    return "ar" if ar > la else "en"


def _luminance(color: Any) -> float | None:
    if color is None or isinstance(color, str):
        return None
    try:
        vals = [float(v) for v in (color if isinstance(color, (list, tuple)) else [color])]
    except (TypeError, ValueError):
        return None
    if len(vals) == 1:
        return vals[0]
    if len(vals) == 3:
        r, g, b = vals
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    if len(vals) == 4:
        c, m, y, k = vals
        r, g, b = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    return None


def hidden_reason(ch: dict[str, Any], crop: tuple[float, float, float, float]) -> str | None:
    """Return "white", "offpage" or "tiny" for a hidden character, or None when it is visible."""
    lum = _luminance(ch.get("non_stroking_color"))
    if lum is not None and lum >= WHITE_LUMINANCE:
        return "white"
    x0, top, x1, bottom = crop
    if not (ch["x0"] >= x0 - 1 and ch["x1"] <= x1 + 1 and ch["top"] >= top - 1 and ch["bottom"] <= bottom + 1):
        return "offpage"
    if float(ch.get("size", 0)) < MIN_VISIBLE_PT:
        return "tiny"
    return None


def is_visible_char(ch: dict[str, Any], crop: tuple[float, float, float, float]) -> bool:
    return hidden_reason(ch, crop) is None


def extract_pages(pdf: Any) -> list[PageText]:
    pages: list[PageText] = []
    for i, page in enumerate(pdf.pages, start=1):
        # pdfplumber coordinates are relative to the mediabox; express the cropbox the same way.
        cb = page.cropbox
        mb = page.mediabox
        crop = (cb[0] - mb[0], mb[3] - cb[3], cb[2] - mb[0], mb[3] - cb[1])
        all_text = page.extract_text(x_tolerance=X_TOLERANCE) or ""
        reasons = [hidden_reason(c, crop) for c in page.chars if c["text"].strip()]
        tiny = reasons.count("tiny")
        sneaky = reasons.count("white") + reasons.count("offpage")
        visible_page = page.filter(
            lambda obj, crop=crop: obj.get("object_type") != "char" or is_visible_char(obj, crop)
        )
        visible_text = visible_page.extract_text(x_tolerance=X_TOLERANCE) or ""
        pages.append(
            PageText(
                number=i,
                visible_text=visible_text,
                all_text=all_text,
                hidden_chars=tiny + sneaky,
                suspicious=sneaky >= WHITE_OR_OFFPAGE_THRESHOLD or tiny >= TINY_THRESHOLD,
            )
        )
    return pages


def parse_pdf(data: bytes, settings: Settings) -> list[PageText]:
    if not data.startswith(b"%PDF-"):
        raise UploadError("NOT_PDF", "The file is not a PDF.", 415)
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # pdfminer raises many types, including password errors
        # pdfplumber wraps pdfminer errors, e.g. PdfminerException(PDFPasswordIncorrect()).
        detail = f"{type(exc).__name__} {exc!r}".lower()
        if "password" in detail or "encrypt" in detail:
            raise UploadError("ENCRYPTED", "Encrypted PDFs are not supported.", 400) from exc
        raise UploadError("UNREADABLE", "The PDF could not be opened.", 400) from exc
    with pdf:
        if getattr(pdf.doc, "encryption", None):
            raise UploadError("ENCRYPTED", "Encrypted PDFs are not supported.", 400)
        try:
            count = len(pdf.pages)
        except Exception as exc:
            raise UploadError("UNREADABLE", "The PDF could not be opened.", 400) from exc
        if count == 0:
            raise UploadError("UNREADABLE", "The PDF has no pages.", 400)
        if count > settings.max_pages:
            raise UploadError("TOO_MANY_PAGES", f"The PDF has {count} pages; the limit is {settings.max_pages}.", 413)
        try:
            return extract_pages(pdf)
        except Exception as exc:
            raise UploadError("UNREADABLE", "The PDF text could not be extracted.", 400) from exc


def validate_upload(data: bytes, content_type: str | None, settings: Settings) -> None:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadError("TOO_LARGE", f"The file is larger than {settings.max_upload_mb} MB.", 413)
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in PDF_CONTENT_TYPES:
        raise UploadError("NOT_PDF", "Only PDF files are accepted.", 415)
    if not data.startswith(b"%PDF-"):
        raise UploadError("NOT_PDF", "The file is not a PDF.", 415)


_PARSED: dict[str, list[PageText]] = {}
_PARSE_LOCKS: dict[str, threading.Lock] = {}


class DocStore:
    """Keeps parsed documents in memory with a JSON sidecar so a restart doesn't lose them."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.uploads = settings.data_dir / "uploads"
        self.meta = settings.data_dir / "docs"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.meta.mkdir(parents=True, exist_ok=True)
        self._docs: dict[str, StoredDoc] = {}

    def add(self, data: bytes, filename: str, content_type: str | None, owner: str = "") -> StoredDoc:
        validate_upload(data, content_type, self.settings)
        sha = hashlib.sha256(data).hexdigest()
        # Parsing a 43-page paper takes seconds; the same bytes always give the same text layers.
        # The per-hash lock makes concurrent uploads of one file parse it once (parallel parses
        # thrash the GIL: 4 at once took 44 s instead of ~5 s).
        with _PARSE_LOCKS.setdefault(sha, threading.Lock()):
            if sha not in _PARSED:
                _PARSED[sha] = parse_pdf(data, self.settings)
                while len(_PARSED) > 32:
                    _PARSED.pop(next(iter(_PARSED)))
            pages = copy.deepcopy(_PARSED[sha])
        if len(pages) > self.settings.max_pages:
            raise UploadError(
                "TOO_MANY_PAGES", f"The PDF has {len(pages)} pages; the limit is {self.settings.max_pages}.", 413
            )
        doc_id = str(uuid.uuid4())
        path = self.uploads / f"{doc_id}.pdf"
        path.write_bytes(data)
        hidden = [p.number for p in pages if p.suspicious]
        doc = StoredDoc(
            owner=owner,
            language=detect_language(" ".join(p.visible_text for p in pages)),
            doc_id=doc_id,
            sha256=sha,
            filename=Path(filename or "document.pdf").name[:120],
            path=str(path),
            created_at=time.time(),
            pages=pages,
            hidden_pages=hidden,
        )
        self._docs[doc_id] = doc
        self.save(doc)
        return doc

    def list(self, owner: str) -> list[StoredDoc]:
        for f in self.meta.glob("*.json"):
            self.get(f.stem)
        return sorted((d for d in self._docs.values() if d.owner == owner), key=lambda d: d.created_at)

    def delete(self, doc_id: str) -> bool:
        doc = self.get(doc_id)
        if doc is None:
            return False
        self._docs.pop(doc_id, None)
        (self.meta / f"{doc_id}.json").unlink(missing_ok=True)
        (self.uploads / f"{doc_id}.pdf").unlink(missing_ok=True)
        return True

    def apply_ocr(self, doc: StoredDoc, texts: dict[int, str]) -> None:
        """Store recognised text as the page text layer (and in the parse cache for re-uploads)."""
        for n, text in texts.items():
            page = doc.page(n)
            if page is not None:
                page.visible_text = page.all_text = text
                page.ocr = True
        doc.language = detect_language(" ".join(p.visible_text for p in doc.pages))
        doc.status = "ready"
        _PARSED[doc.sha256] = copy.deepcopy(doc.pages)
        self.save(doc)

    def save(self, doc: StoredDoc) -> None:
        (self.meta / f"{doc.doc_id}.json").write_text(json.dumps(asdict(doc)), encoding="utf-8")

    def get(self, doc_id: str) -> StoredDoc | None:
        try:
            uuid.UUID(doc_id)
        except ValueError:
            return None
        if doc_id in self._docs:
            return self._docs[doc_id]
        f = self.meta / f"{doc_id}.json"
        if not f.exists():
            return None
        raw = json.loads(f.read_text(encoding="utf-8"))
        raw["pages"] = [PageText(**p) for p in raw["pages"]]
        doc = StoredDoc(**raw)
        self._docs[doc_id] = doc
        return doc

    def cleanup(self, now: float | None = None) -> int:
        now = now or time.time()
        removed = 0
        for d in (self.uploads, self.meta):
            for f in d.iterdir():
                if f.is_file() and now - f.stat().st_mtime > RETENTION_S:
                    f.unlink(missing_ok=True)
                    removed += 1
        for doc_id, doc in list(self._docs.items()):
            if now - doc.created_at > RETENTION_S:
                del self._docs[doc_id]
        return removed
