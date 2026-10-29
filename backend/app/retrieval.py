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

# The demo paper is English while questions are often Egyptian Arabic. A small glossary bridges the
# common question words; technical terms (GSM8K, chain-of-thought, PaLM) are usually written in
# English inside Arabic questions and match directly.
AR_GLOSSARY = {
    "موديل": "model",
    "موديلات": "models language",
    "الموديل": "model",
    "الموديلات": "models language",
    "حجم": "size scale parameters",
    "الحجم": "size scale",
    "مين": "authors",
    "كتبوا": "authors wrote",
    "الورقه": "paper",
    "الورقة": "paper",
    "الفرق": "difference standard",
    "مثال": "exemplar example",
    "الإجابه": "answer",
    "الإجابة": "answer",
    "للإجابه": "answer",
    "للإجابة": "answer",
    "النتايج": "results accuracy table",
    "بيحسن": "improve",
    "بيحسّن": "improve",
    "جربوا": "evaluate benchmarks",
    "جرّبوا": "evaluate benchmarks",
    "الأساسيه": "key",
    "الأساسية": "key",
    "الأفكار": "ideas",
    "خطوات": "steps reasoning",
    "يعني": "what",
    "بيوصل": "leads arrive answer",
    "بيوصّل": "leads arrive answer",
}


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
    "authors": "google research",
    "wrote": "authors",
    "different": "standard",
    "difference": "standard",
    "exemplar": "exemplars few-shot",
    "review": "key",
    "ideas": "properties",
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
    for word in question.split():
        word = re.sub(r"[؟?.!,،:]", "", word)
        for key in (word, normalize(word)):
            if key in AR_GLOSSARY:
                extra.extend(tokenize(AR_GLOSSARY[key]))
                break
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
    query = expand_query(question)
    quant = is_quantitative(question)

    final_page = max((c.page for c in chunks), default=1)

    def score(i: int) -> float:
        base = bm25.score(query, i)
        # Papers define things early; appendices repeat the same terms in tables. A mild prior
        # (x1.5 on page 1 down to x1.0 on the last page) keeps definitions ahead of repetitions.
        base *= 1 + 0.5 * (1 - (chunks[i].page - 1) / max(final_page - 1, 1))
        return base * (1 + 2 * numeric_density(chunks[i].tokens)) if quant else base

    ranked = sorted(range(len(chunks)), key=lambda i: (-score(i), i))
    # A table caption is useless without its body: rank the chunk after a caption right behind it.
    order: list[int] = []
    for i in ranked:
        if i in order:
            continue
        order.append(i)
        if re.match(r"\s*Table \d+:", chunks[i].text) and i + 1 < len(chunks) and chunks[i + 1].page == chunks[i].page:
            if i + 1 not in order:
                order.append(i + 1)
    ranked = order
    chosen: list[int] = []
    used = 0
    pinned = [i for i, c in enumerate(chunks) if c.page == 1 and c.index == 0]
    for i in pinned + [i for i in ranked if i not in pinned]:
        cost = estimate_tokens(chunks[i].text) + 6  # + page marker
        if used + cost > budget_tokens:
            continue
        chosen.append(i)
        used += cost
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
