import json

import pytest
from fastapi.testclient import TestClient

import app.stream as stream_mod
from app.main import create_app
from app.stream import parse_partial

from .conftest import PDFS, make_settings, upload
from .helpers import ANSWERS, Q1_EN, ask, components, cot_doc, dropped, names, text_of

INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(stream_mod, "BACKOFF_BASE_S", 0.001)


def test_q1_event_order(client):
    ev = ask(client, cot_doc(client), Q1_EN)
    n = names(ev)
    assert n[0] == "RUN_STARTED" and n[-1] == "RUN_FINISHED" and n[-2] == "METRICS"
    assert n.index("TEXT_MESSAGE_START") < n.index("TEXT_MESSAGE_END") < n.index("COMPONENT")
    planned = [(i, d["component_id"]) for i, (x, d) in enumerate(ev) if x == "COMPONENT_PLANNED"]
    assert [cid for _, cid in planned] == ["c1", "c2", "c3"]
    for i, cid in planned:  # each skeleton is announced before its component arrives
        assert i < next(j for j, (x, d) in enumerate(ev) if x == "COMPONENT" and d["component_id"] == cid)
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]
    expected = json.loads((ANSWERS / "cot" / "q1.en.json").read_text(encoding="utf-8"))["answer_text"]
    assert text_of(ev) == expected
    assert all(c["verification"]["status"] == "verified" for c in components(ev))


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize(
    "qid,types",
    [
        ("q1", ["comparison", "steps", "quiz"]),
        ("q2", ["chart", "text"]),
        ("q3", ["table", "table"]),
        ("q4", []),
        ("q5", ["flashcards"]),
        ("q6", ["diagram"]),
    ],
)
def test_every_demo_fixture_streams_verified(client, qid, types, lang):
    ev = ask(client, cot_doc(client), INDEX["questions"]["cot"][qid][lang], lang=lang)
    assert [c["type"] for c in components(ev)] == types
    assert not dropped(ev)
    assert all(c["verification"]["status"] == "verified" for c in components(ev))
    assert all(c["props"]["lang"] == lang for c in components(ev))


def test_chunked_parse_emits_components_in_order():
    text = (ANSWERS / "cot" / "q1.en.json").read_text(encoding="utf-8")
    seen = []
    for i in range(1, len(text), 7):
        n = len((parse_partial(text[:i]) or {}).get("components") or [])
        if not seen or n != seen[-1]:
            seen.append(n)
    assert seen == sorted(seen) and seen[-1] == 3


def test_question_matching_by_keyword(client):
    ev = ask(client, cot_doc(client), "who wrote it?")
    assert components(ev) == [] and "Jason Wei" in text_of(ev)


def test_truncated_fixture_keeps_text_and_completed_components(client):
    ev = ask(client, cot_doc(client), "anything", fixture="malformed/truncated")
    assert [c["type"] for c in components(ev)] == ["comparison"]
    assert [d["reason"] for d in dropped(ev)] == ["incomplete"]
    assert "RUN_ERROR" not in names(ev) and names(ev)[-1] == "RUN_FINISHED"
    assert any(x == "WARNING" and d["code"] == "TRUNCATED_OUTPUT" for x, d in ev)
    assert text_of(ev).startswith("Chain-of-thought prompting")


def test_unknown_type_ignored(client):
    ev = ask(client, cot_doc(client), "x", fixture="malformed/unknown_type")
    assert [c["type"] for c in components(ev)] == ["comparison"]
    assert dropped(ev)[0]["reason"] == "unknown_type"


def test_bad_number_partial(client):
    ev = ask(client, cot_doc(client), "x", fixture="malformed/bad_number")
    c = components(ev)[0]
    assert c["type"] == "chart" and c["verification"] == {"status": "partial", "dropped_points": 2}


def test_two_point_chart_becomes_table(client):
    c = components(ask(client, cot_doc(client), "x", fixture="malformed/two_point_chart"))[0]
    assert c["type"] == "table" and c["downgraded_from"] == "chart"


def test_too_many_truncated_quiz_last(client):
    ev = ask(client, cot_doc(client), "x", fixture="malformed/too_many")
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]
    assert sorted(d["reason"] for d in dropped(ev)) == ["too_many_components", "too_many_components"]


def test_needs_visual_false_drops_components(client):
    ev = ask(client, cot_doc(client), "x", fixture="malformed/needs_visual_false_with_components")
    assert components(ev) == [] and len(dropped(ev)) == 2


def test_html_payload_passes_through_as_data(client):
    ev = ask(client, cot_doc(client), "x", fixture="malformed/html_payload")
    body = components(ev)[0]["props"]["body"]
    assert "<img src=x onerror=alert(1)>" in body  # React renders it as literal text
    assert "javascript:" not in body


def test_injection_pdf(client):
    doc = upload(client, PDFS / "injection.pdf").json()["doc_id"]
    ev = ask(client, doc, "What accuracy does the baseline model reach on each task?")
    warn = [d for x, d in ev if x == "WARNING" and d["code"] == "HIDDEN_TEXT_DETECTED"]
    assert warn and warn[0]["pages"] == [1]
    chart = components(ev)[0]
    values = [p["value"] for s in chart["props"]["series"] for p in s["points"]]
    assert values == [41.2, 55.0, 63.7]
    assert chart["verification"] == {"status": "partial", "dropped_points": 1}
    assert "evil.example" not in json.dumps([c["props"] for c in components(ev)])


def test_text_only_preference(client):
    assert components(ask(client, cot_doc(client), Q1_EN, text_only=True)) == []


def test_run_error(client):
    ev = ask(client, cot_doc(client), "x", fixture="error/run_error")
    assert names(ev)[-1] == "RUN_ERROR" and "METRICS" in names(ev)


def test_busy_then_fallback_model(tmp_path):
    s = make_settings(tmp_path)
    with TestClient(create_app(s)) as c:
        ev = ask(c, cot_doc(c), Q1_EN, fixture="error/busy_then_ok")
    assert [d for x, d in ev if x == "WARNING"][0]["code"] == "FALLBACK_MODEL_USED"
    m = next(d for x, d in ev if x == "METRICS")
    assert m["fallback_used"] and m["model"] == s.fallback_model
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]


def test_busy_everywhere_gives_run_error(client):
    ev = ask(client, cot_doc(client), "x", fixture="error/busy")
    assert names(ev)[-1] == "RUN_ERROR"
    assert next(d for x, d in ev if x == "RUN_ERROR")["code"] == "UPSTREAM_BUSY"


def test_timeout_keeps_partial_text(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, request_timeout_s=1))) as c:
        ev = ask(c, cot_doc(c), Q1_EN, fixture="error/stall")
    assert names(ev)[-1] == "RUN_ERROR"
    assert next(d for x, d in ev if x == "RUN_ERROR")["code"] == "TIMEOUT"
    assert "TEXT_MESSAGE_END" in names(ev)
    assert text_of(ev).startswith("Chain-of-thought")


def test_ask_text_streams_prose(client):
    ev = ask(client, cot_doc(client), INDEX["questions"]["cot"]["q1"]["ar"], lang="ar", endpoint="/api/ask_text")
    assert names(ev)[:2] == ["RUN_STARTED", "TEXT_MESSAGE_START"] and names(ev)[-1] == "RUN_FINISHED"
    assert len(text_of(ev)) > 1500


def test_plan_mode_event_shape(tmp_path):
    # The mock replays a full VisualAnswer for the plan call; a q4 answer has no plan, so this only
    # exercises plan mode's text path and termination.
    with TestClient(create_app(make_settings(tmp_path, schema_mode="plan"))) as c:
        ev = ask(c, cot_doc(c), "Who are the authors of this paper?")
    assert names(ev)[0] == "RUN_STARTED" and names(ev)[-1] == "RUN_FINISHED"
    assert components(ev) == [] and "Jason Wei" in text_of(ev)


def test_flat_mode_same_result(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, schema_mode="flat"))) as c:
        ev = ask(c, cot_doc(c), Q1_EN)
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]


def test_json_mode_sends_no_api_schema(tmp_path, monkeypatch):
    from app import prompts
    from app.providers.mock import MockProvider

    seen = {}
    original = MockProvider.stream_structured

    def spy(self, **kw):
        seen.update(schema=kw["schema"], system=kw["system"])
        return original(self, **kw)

    monkeypatch.setattr(MockProvider, "stream_structured", spy)
    with TestClient(create_app(make_settings(tmp_path, schema_mode="json"))) as c:
        ev = ask(c, cot_doc(c), Q1_EN)
    assert seen["schema"] is None
    assert seen["system"] == prompts.json_mode_system() and '"components"' in seen["system"]
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]
