"""Check quotes and numbers against the PDF's VISIBLE page text."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from .upload import StoredDoc

QUOTE_THRESHOLD = 90
NUMBER_TOLERANCE = 0.05

_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")} | {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_TASHKEEL = re.compile(r"[\u064B-\u065F\u0670]")
_DASHES = re.compile(r"[\u2010-\u2015\u2212\ufffd]")
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " "})
# Digits glued to a word ("GSM8K", "GPT-3", "code-davinci-002") are identifiers, not numbers.
_NUMBER = re.compile(r"(?<![\w.\-])-?\d+(?:\.\d+)?")

Status = Literal["verified", "failed", "unverified"]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_DIGITS)
    t = t.replace("٫", ".").replace("٬", "").replace("٪", "%")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    t = _TASHKEEL.sub("", t).replace("ـ", "")
    t = re.sub("[أإآ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = t.translate(_QUOTES)
    t = re.sub(r"(\w)-[ \t]*\n[ \t]*(\w)", r"\1\2", t)
    t = _DASHES.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return "".join(c.lower() if c.isascii() else c for c in t)


def numbers_in(text: str) -> list[float]:
    return [float(m) for m in _NUMBER.findall(normalize(text).replace("%", " "))]


def _decimals(v: float) -> int:
    s = repr(v)
    return 0 if v == int(v) else len(s.split(".")[1])


def number_matches(value: float, candidates: list[float]) -> bool:
    for q in candidates:
        if abs(q - value) <= NUMBER_TOLERANCE + 1e-9:
            return True
        # One decimal place of rounding either way, e.g. 56.94 -> 56.9 or 56.9 -> 57.
        if round(q, max(_decimals(value), 0)) == value or round(value, _decimals(q)) == q:
            if abs(q - value) < 1:
                return True
    return False


def quote_score(quote: str, page_text: str) -> float:
    q, p = normalize(quote), normalize(page_text)
    if not q or not p:
        return 0.0
    score = fuzz.partial_ratio(q, p)
    if score < QUOTE_THRESHOLD:
        # PDF extraction sometimes drops or adds spaces; compare without them as a second chance.
        score = max(score, fuzz.partial_ratio(q.replace(" ", ""), p.replace(" ", "")))
    return score


@dataclass
class QuoteResult:
    status: Status
    page: int
    score: float = 0.0


def check_quote(doc: StoredDoc, page: int, quote: str) -> QuoteResult:
    target = doc.page(page)
    if target is not None and not target.visible_text.strip():
        return QuoteResult("unverified", page)
    best = QuoteResult("failed", page)
    for candidate in (page, page - 1, page + 1):
        p = doc.page(candidate)
        if p is None or not p.visible_text.strip():
            continue
        score = quote_score(quote, p.visible_text)
        if score >= QUOTE_THRESHOLD:
            return QuoteResult("verified", candidate, score)
        if score > best.score:
            best = QuoteResult("failed", page, score)
    if target is None and best.score == 0:
        return QuoteResult("failed", page)
    return best


def check_numbers(values: list[float], quote: str, page_text: str | None) -> bool:
    """Every value must appear in the quote, and the quote's matching number must appear on the page.

    The second condition stops a quote that fuzzy-matches the page (score >= 90) but has one digit
    changed from smuggling a number the document never printed.
    """
    in_quote = numbers_in(quote)
    on_page = numbers_in(page_text) if page_text is not None else None
    for v in values:
        matches = [q for q in in_quote if number_matches(v, [q])]
        if not matches:
            return False
        if on_page is not None and not any(number_matches(q, on_page) for q in matches):
            return False
    return True


def cell_numbers(cells: list[str]) -> list[float]:
    out: list[float] = []
    for c in cells:
        out.extend(numbers_in(c))
    return out
