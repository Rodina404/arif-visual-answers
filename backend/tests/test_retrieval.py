import json

import pytest

from app.retrieval import BM25, chunk_pages, estimate_tokens, expand_query, is_quantitative, retrieve, tokenize
from app.upload import PageText, StoredDoc

from .helpers import ANSWERS

INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))["questions"]["cot"]


@pytest.fixture(scope="module")
def cot():
    from scripts.check_fixtures import load_doc

    return load_doc("cot")


def _doc(*texts: str) -> StoredDoc:
    return StoredDoc("d", f"sha-{hash(texts)}", "x", "x", 0, [PageText(i + 1, t, t) for i, t in enumerate(texts)])


def test_tokenize_splits_hyphenated_terms_and_drops_stopwords():
    toks = tokenize("What is Chain-of-Thought prompting on GSM8K?")
    assert "chain-of-thought" in toks and "chain" in toks and "thought" in toks and "gsm8k" in toks
    assert "what" not in toks and "is" not in toks


def test_query_expansion_bridges_arabic_and_synonyms():
    ar = expand_query(INDEX["q2"]["ar"])
    assert {"gsm8k", "size", "scale"} <= set(ar)
    en = expand_query("results as model size grows")
    assert {"scale", "accuracy"} <= set(en)
    assert is_quantitative(INDEX["q2"]["en"]) and not is_quantitative(INDEX["q4"]["en"])


def test_bm25_prefers_matching_chunk():
    bm = BM25([tokenize("apples and oranges"), tokenize("chain of thought prompting improves reasoning")])
    q = tokenize("chain of thought")
    assert bm.score(q, 1) > bm.score(q, 0) == 0


def test_budget_is_respected_and_page_one_is_pinned(cot):
    for budget in (1000, 2500, 4000):
        r = retrieve(cot, "completely unrelated question about bananas", budget)
        assert r.est_tokens <= budget and 1 in r.pages
        assert estimate_tokens(r.text) <= budget + 10 * len(r.pages)


def test_context_is_page_marked_in_page_order(cot):
    r = retrieve(cot, INDEX["q3"]["en"], 3000)
    markers = [int(x) for x in __import__("re").findall(r"\[\[page (\d+)\]\]", r.text)]
    assert markers == sorted(markers) == r.pages


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_q2_reaches_table_2_with_the_palm_rows(cot, lang):
    r = retrieve(cot, INDEX["q2"][lang], 2600)
    assert 21 in r.pages
    assert "62B 9.6 29.9" in r.text and "540B 17.9 56.9" in r.text  # caption pulled its table body along


@pytest.mark.parametrize("qid,page", [("q1", 2), ("q3", 4), ("q4", 1), ("q6", 1)])
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_key_page_is_retrieved(cot, qid, page, lang):
    assert page in retrieve(cot, INDEX[qid][lang], 2600).pages


def test_chunking_covers_all_text():
    doc = _doc("line one\n" * 200, "short page")
    chunks = chunk_pages(doc)
    assert {c.page for c in chunks} == {1, 2}
    assert sum(len(c.text) for c in chunks if c.page == 1) >= len("line one\n" * 200) - 200


def test_numeric_text_is_estimated_denser_than_prose():
    prose = "the model improves reasoning on many tasks " * 10
    table = "540B 17.9 56.9 69.4 79.0 72.1 73.9 25.2 35.8 " * 10
    assert estimate_tokens(table) / len(table) > estimate_tokens(prose) / len(prose) * 1.4
