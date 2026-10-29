"""Page retrieval: send only the parts of the PDF relevant to the question, within a token budget.

Groq's free tier allows ~8K tokens per minute and cot.pdf is ~24K tokens, so the whole paper can't
be sent. Pages are split into ~600-character chunks, ranked with BM25 against the question, and the
best chunks are packed (grouped by page, in page order, with [[page N]] markers) until the budget is
used. Citations still name whole pages, and grounding still checks quotes against the full page text.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field

from .grounding import normalize
from .upload import StoredDoc

CHUNK_CHARS = 600
CHARS_PER_TOKEN = 3.6  # conservative for English PDF text; checked against Groq usage.prompt_tokens

_STOP = set(
    "a an and are as at be by for from has have how in is it its of on or that the this to was were what which "
    "who with does did do it's than then there their them they these those into over also can".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*|[؀-ۿ]+")


# English query expansion: question words -> the words papers use for the same idea.
EN_SYNONYMS = {
    "size": "scale parameters",
    "sizes": "scale parameters",
    "grows": "scale larger",
    "bigger": "scale larger",
    "results": "accuracy performance table",
    "improve": "improves outperforms gains",
    "improvement": "outperforms gains",
    "benchmarks": "datasets tasks",
    "benchmark": "datasets tasks",
    "evaluate": "benchmarks experiments",
    "evaluated": "benchmarks experiments",
    "wrote": "authors",
}


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(normalize(text))
    out: list[str] = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        out.append(t)
        if "-" in t:  # "chain-of-thought" also matches "chain of thought"
            out.extend(p for p in t.split("-") if p not in _STOP and len(p) > 1)
    return out


def expand_query(question: str) -> list[str]:
    toks = tokenize(question)
    extra: list[str] = []
    for t in toks:
        if t in EN_SYNONYMS:
            extra.extend(tokenize(EN_SYNONYMS[t]))
    return toks + extra


# Questions asking for amounts should reach tables, whose chunks are mostly numbers and so score low
# on words alone.
QUANT_WORDS = {
    "much",
    "many",
    "results",
    "accuracy",
    "improve",
    "percent",
    "numbers",
    "score",
    "scores",
    "قد",
    "كام",
    "النتايج",
    "النتائج",
    "نسبه",
    "دقه",
}


def is_quantitative(question: str) -> bool:
    return bool(set(tokenize(question)) & QUANT_WORDS)


def numeric_density(tokens: list[str]) -> float:
    return sum(t.replace(".", "").isdigit() for t in tokens) / max(len(tokens), 1)


@dataclass
class Chunk:
    page: int
    index: int
    text: str
    tokens: list[str] = field(default_factory=list)


def chunk_pages(doc: StoredDoc) -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in doc.pages:
        buf: list[str] = []
        size = 0
        idx = 0
        for line in p.visible_text.splitlines():
            buf.append(line)
            size += len(line) + 1
            if size >= CHUNK_CHARS:
                chunks.append(Chunk(p.number, idx, "\n".join(buf)))
                buf, size, idx = [], 0, idx + 1
        if buf and "".join(buf).strip():
            chunks.append(Chunk(p.number, idx, "\n".join(buf)))
    for c in chunks:
        c.tokens = tokenize(c.text)
    return chunks


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(d) for d in docs]
        self.lens = [len(d) for d in docs]
        self.avg = sum(self.lens) / max(len(docs), 1)
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: list[str], i: int) -> float:
        tf, dl = self.docs[i], self.lens[i]
        s = 0.0
        for t in set(query):
            f = tf.get(t, 0)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avg))
        return s


_DIGITISH = re.compile(r"[\d.,%+\-()]")


def estimate_tokens(text: str) -> int:
    """Conservative token estimate. Numeric tables tokenize far denser than prose (a live Groq prompt
    with Appendix Table 2 came in above a prose-only estimate), so digits and their punctuation count
    at ~2 characters per token."""
    digitish = len(_DIGITISH.findall(text))
    return math.ceil((len(text) - digitish) / CHARS_PER_TOKEN + digitish / 2.0)


@dataclass
class Retrieved:
    text: str  # page-marked context to send
    pages: list[int]
    chunks: int
    est_tokens: int
    scores: list[tuple[int, int, float]]  # (page, chunk index, score) of what was sent, best first


_INDEX: dict[str, tuple[list[Chunk], BM25]] = {}

# The search query for this request: the question translated into the document's language when they
# differ (set by the stream layer); providers keep passing the original question.
RETRIEVAL_QUERY: ContextVar[str | None] = ContextVar("RETRIEVAL_QUERY", default=None)


def forget(sha256: str) -> None:
    """Drop a document's index (its text changed, e.g. after OCR)."""
    _INDEX.pop(sha256, None)


def _index(doc: StoredDoc) -> tuple[list[Chunk], BM25]:
    if doc.sha256 not in _INDEX:
        chunks = chunk_pages(doc)
        _INDEX[doc.sha256] = (chunks, BM25([c.tokens for c in chunks]))
        while len(_INDEX) > 32:
            _INDEX.pop(next(iter(_INDEX)))
    return _INDEX[doc.sha256]


def retrieve(doc: StoredDoc, question: str, budget_tokens: int) -> Retrieved:
    """Best chunks for the question within budget_tokens. The first chunk of page 1 (title, authors,
    abstract) is always included: it is small and anchors almost every question about a paper."""
    chunks, bm25 = _index(doc)
    search = RETRIEVAL_QUERY.get() or question
    query = expand_query(search)
    quant = is_quantitative(search)

    final_page = max((c.page for c in chunks), default=1)

    def score(i: int) -> float:
        base = bm25.score(query, i)
        # Papers define things early; appendices repeat the same terms in tables. A mild prior
        # (x1.5 on page 1 down to x1.0 on the last page) keeps definitions ahead of repetitions.
        base *= 1 + 0.5 * (1 - (chunks[i].page - 1) / max(final_page - 1, 1))
        return base * (1 + 2 * numeric_density(chunks[i].tokens)) if quant else base

    ranked = sorted(range(len(chunks)), key=lambda i: (-score(i), i))
    # A table caption is useless without its body: they are packed as one unit (both or neither, or the
    # body alone, which holds the numbers), so a caption never arrives without its rows.
    units: list[list[int]] = []
    seen: set[int] = set()
    for i in ranked:
        if i in seen:
            continue
        unit = [i]
        nxt = i + 1
        if re.match(r"\s*Table \d+:", chunks[i].text) and nxt < len(chunks) and chunks[nxt].page == chunks[i].page:
            if nxt not in seen:
                unit.append(nxt)
        seen.update(unit)
        units.append(unit)
    cost = {i: estimate_tokens(c.text) + 6 for i, c in enumerate(chunks)}  # + page marker
    chosen: list[int] = []
    used = 0
    pinned = [i for i, c in enumerate(chunks) if c.page == 1 and c.index == 0]
    for i in pinned:
        if cost[i] <= budget_tokens:
            chosen.append(i)
            used += cost[i]
    for unit in units:
        unit = [i for i in unit if i not in chosen]
        if not unit:
            continue
        for candidate in (unit, unit[1:]):
            need = sum(cost[i] for i in candidate)
            if candidate and used + need <= budget_tokens:
                chosen.extend(candidate)
                used += need
                break
    order = sorted(chosen, key=lambda i: (chunks[i].page, chunks[i].index))
    parts: list[str] = []
    last_page = None
    for i in order:
        c = chunks[i]
        if c.page != last_page:
            parts.append(f"[[page {c.page}]]")
            last_page = c.page
        parts.append(c.text)
    return Retrieved(
        text="\n".join(parts),
        pages=sorted({chunks[i].page for i in chosen}),
        chunks=len(chosen),
        est_tokens=used,
        scores=[(chunks[i].page, chunks[i].index, round(score(i), 2)) for i in chosen],
    )
