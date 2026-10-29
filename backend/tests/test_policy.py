import copy
import json

import pytest

from app.catalog import ComparisonComponent
from app.policy import ComponentProcessor, Outcome, Selector, comparison_keys_match, strip_urls

from .helpers import ANSWERS

Q1 = json.loads((ANSWERS / "cot" / "q1.en.json").read_text(encoding="utf-8"))
Q2 = json.loads((ANSWERS / "cot" / "q2.en.json").read_text(encoding="utf-8"))
Q3 = json.loads((ANSWERS / "cot" / "q3.en.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc():
    from scripts.check_fixtures import load_doc

    return load_doc("cot")


def test_needs_visual_false_drops(doc):
    o = ComponentProcessor(doc, needs_visual=False).process(Q1["components"][0], 0)
    assert o.drop_reason == "needs_visual_false"


def test_unknown_type_dropped(doc):
    assert ComponentProcessor(doc).process({"type": "video", "id": "c1"}, 0).drop_reason == "unknown_type"


def test_invalid_component_dropped(doc):
    c = copy.deepcopy(Q1["components"][1])
    c["steps"] = c["steps"][:1]  # minItems 2
    assert ComponentProcessor(doc).process(c, 0).drop_reason == "invalid"


def test_empty_reason_dropped(doc):
    c = copy.deepcopy(Q1["components"][1])
    c["reason"] = "  "
    assert ComponentProcessor(doc).process(c, 0).drop_reason == "empty_reason"


def test_duplicate_id_dropped(doc):
    p = ComponentProcessor(doc)
    assert not p.process(Q1["components"][1], 0).dropped
    assert p.process(Q1["components"][1], 1).drop_reason == "duplicate_id"


def test_comparison_with_different_keys_dropped(doc):
    c = copy.deepcopy(Q1["components"][0])
    c["items"][1]["attributes"][0]["key"] = "Something else"
    assert ComponentProcessor(doc).process(c, 0).drop_reason == "mismatched_attribute_keys"
    assert comparison_keys_match(ComparisonComponent.model_validate(Q1["components"][0]))


def test_comparison_bad_citation_removed_partial(doc):
    c = copy.deepcopy(Q1["components"][0])
    c["items"][0]["attributes"][2]["value"] = "31 (wrong)"  # 31 is not in "A: The answer is 27."
    o = ComponentProcessor(doc).process(c, 0)
    assert o.status == "partial" and "citation" not in o.props["items"][0]["attributes"][2]


def test_good_chart_verified(doc):
    o = ComponentProcessor(doc).process(Q2["components"][0], 0)
    assert (o.type, o.status, o.dropped_points) == ("chart", "verified", 0)


def test_chart_with_bad_value_is_partial(doc):
    c = copy.deepcopy(Q2["components"][0])
    c["series"][0]["points"].append({"label": "1T", "value": 31.4, "citation": c["series"][0]["points"][2]["citation"]})
    o = ComponentProcessor(doc).process(c, 0)
    assert (o.type, o.status, o.dropped_points) == ("chart", "partial", 1)


def test_chart_below_three_points_becomes_table(doc):
    c = copy.deepcopy(Q2["components"][0])
    c["series"] = [c["series"][1]]
    c["series"][0]["points"][0]["value"] = 14.1
    o = ComponentProcessor(doc).process(c, 0)
    assert o.type == "table" and o.downgraded_from == "chart" and o.status == "partial"
    assert len(o.props["rows"]) == 2 and o.props["columns"] == ["PaLM model size", "GSM8K accuracy (%)"]


def test_chart_below_two_points_dropped_with_text(doc):
    c = copy.deepcopy(Q2["components"][0])
    c["series"] = [c["series"][1]]
    for p in c["series"][0]["points"][:2]:
        p["value"] = 77.7
    o = ComponentProcessor(doc).process(c, 0)
    assert o.drop_reason == "insufficient_verified_points"
    assert o.fallback_text == "540B: 56.9% (p. 21)"


def test_table_below_two_rows_dropped(doc):
    t = copy.deepcopy(Q3["components"][1])
    for row in t["rows"][1:]:
        row["citation"]["quote"] = "this sentence is not anywhere in the paper at all"
    o = ComponentProcessor(doc).process(t, 0)
    assert o.drop_reason == "insufficient_verified_rows"
    assert "GPT-3" in o.fallback_text


def test_table_row_with_unprinted_number_dropped(doc):
    t = copy.deepcopy(Q3["components"][1])
    t["rows"][2]["cells"][1] = "8B, 62B, 999B"
    o = ComponentProcessor(doc).process(t, 0)
    assert o.status == "partial" and len(o.props["rows"]) == 4


def test_quiz_with_bad_citation_loses_question(doc):
    q = copy.deepcopy(Q1["components"][2])
    q["questions"][0]["citation"]["quote"] = "a quote that the paper never printed anywhere"
    o = ComponentProcessor(doc).process(q, 0)
    assert o.status == "partial" and len(o.props["questions"]) == 1


def test_page_fix_neighbour(doc):
    c = copy.deepcopy(Q2["components"][0])
    for s in c["series"]:
        for p in s["points"]:
            p["citation"]["page"] = 20  # off by one: Table 2 is on page 21
    o = ComponentProcessor(doc).process(c, 0)
    assert o.status == "verified"
    assert {p["citation"]["page"] for s in o.props["series"] for p in s["points"]} == {21}


def test_out_of_range_pages_removed(doc):
    c = copy.deepcopy(Q1["components"][1])
    c["steps"][0]["page"] = 99
    o = ComponentProcessor(doc).process(c, 0)
    assert "page" not in o.props["steps"][0]


def test_urls_are_stripped():
    assert strip_urls({"a": ["see https://evil.example/x now", "javascript:alert(1)"]}) == {
        "a": ["see [link removed] now", "[link removed]"]
    }


def _o(kind: str, i: int) -> Outcome:
    return Outcome(component_id=f"c{i}", type=kind)


def test_selector_caps_at_three_with_quiz_last():
    s = Selector()
    emitted = []
    for i, k in enumerate(["quiz", "comparison", "steps", "table", "text"]):
        emitted += s.offer(_o(k, i))
    emitted += s.finish()
    assert [o.type for o in emitted if not o.dropped] == ["comparison", "steps", "quiz"]
    assert {o.type for o in emitted if o.dropped} == {"table", "text"}


def test_selector_priority_for_held_components():
    s = Selector()
    out = s.offer(_o("text", 1)) + s.offer(_o("formula", 2)) + s.offer(_o("text", 3)) + s.offer(_o("comparison", 4))
    out += s.finish()
    assert [o.type for o in out if not o.dropped] == ["text", "formula", "comparison"]


def test_selector_one_quiz_only():
    s = Selector()
    s.offer(_o("quiz", 1))
    assert s.offer(_o("quiz", 2))[0].drop_reason == "only_one_quiz"
