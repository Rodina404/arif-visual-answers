"""Groq provider: request shape, strict schema, retrieval budget, 429 handling — all mocked (respx)."""

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import app.stream as stream_mod
from app.catalog import strict_schema
from app.main import create_app
from app.providers.base import ProviderError, parse_duration
from app.providers.groq import GroqProvider

from .conftest import make_settings
from .helpers import ANSWERS, Q1_EN, ask, components, cot_doc, names, text_of

URL = "https://api.groq.com/openai/v1/chat/completions"
Q1 = json.loads((ANSWERS / "cot" / "q1.en.json").read_text(encoding="utf-8"))


def with_strict_nulls(answer: dict) -> dict:
    """What a strict-mode model returns: optional fields present as explicit nulls."""
    out = json.loads(json.dumps(answer))
    for c in out["components"]:
        if c["type"] == "steps":
            for s in c["steps"]:
                s.setdefault("page", None)
        if c["type"] == "comparison":
            for item in c["items"]:
                for a in item["attributes"]:
                    a.setdefault("citation", None)
    return out


def groq_ok(answer: dict, prompt_tokens: int = 5100) -> httpx.Response:
    body = {
        "choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 1300,
            "completion_tokens_details": {"reasoning_tokens": 200},
        },
    }
    return httpx.Response(200, json=body, headers={"x-ratelimit-remaining-tokens": "1600"})


def rate_limited(seconds: str) -> httpx.Response:
    return httpx.Response(
        429,
        json={"error": {"message": "Rate limit reached for model on tokens per minute (TPM)"}},
        headers={"retry-after": seconds, "x-ratelimit-reset-tokens": f"{seconds}s"},
    )


@pytest.fixture
def groq_app(tmp_path):
    s = make_settings(tmp_path, mock_llm=False, llm_provider="groq", groq_api_key="gsk_test")
    with TestClient(create_app(s)) as c:
        yield c


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(stream_mod, "BACKOFF_BASE_S", 0.001)


@pytest.mark.parametrize(
    "value,seconds", [("7.66s", 7.66), ("2m59.56s", 179.56), ("12", 12.0), ("850ms", 0.85), (None, None), ("x", None)]
)
def test_parse_duration(value, seconds):
    assert parse_duration(value) == (pytest.approx(seconds) if seconds is not None else None)


def test_strict_schema_rules():
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object" and "properties" in n:
                assert set(n["required"]) == set(n["properties"]) and n["additionalProperties"] is False
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    for kind in ("union", "flat"):
        s = strict_schema(kind)
        walk(s)
        text = json.dumps(s)
        assert "maxLength" not in text and "minItems" not in text and "description" not in text
    steps = next(b for b in strict_schema()["properties"]["components"]["items"]["anyOf"] if "steps" in b["properties"])
    assert steps["properties"]["steps"]["items"]["properties"]["page"]["type"] == ["integer", "null"]


@respx.mock
def test_groq_answer_end_to_end(groq_app):
    route = respx.post(URL).mock(return_value=groq_ok(with_strict_nulls(Q1)))
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    body = json.loads(route.calls[0].request.content)
    assert route.calls[0].request.headers["authorization"] == "Bearer gsk_test"
    assert body["model"] == "openai/gpt-oss-120b" and "stream" not in body
    assert body["reasoning_effort"] == "low" and body["max_tokens"] == 2400
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    user = body["messages"][1]["content"]
    assert "[[page 1]]" in user and "[[page 2]]" in user
    assert len(user) < 24_000 * 3  # nowhere near the whole paper
    # Nulls from strict mode are stripped, so the components validate and ground exactly as before.
    assert [c["type"] for c in components(ev)] == ["comparison", "steps", "quiz"]
    assert all(c["verification"]["status"] == "verified" for c in components(ev))
    assert text_of(ev) == Q1["answer_text"]
    m = next(d for n, d in ev if n == "METRICS")
    assert (m["provider"], m["model"], m["schema_mode"]) == ("groq", "openai/gpt-oss-120b", "strict")
    assert m["tokens"] == {"input": 5100, "cached_input": 0, "output": 1100, "thinking": 200, "total": 6400}
    assert m["retrieval"]["retrieval"] == "bm25" and 1 in m["retrieval"]["pages"]
    assert m["retrieval"]["streamed"] is False


@respx.mock
async def test_prompt_stays_under_budget(tmp_path):
    from scripts.check_fixtures import load_doc

    s = make_settings(tmp_path, mock_llm=False, llm_provider="groq", groq_api_key="k")
    route = respx.post(URL).mock(return_value=groq_ok(Q1))
    p = GroqProvider(s)
    handle = await p.prepare_document(load_doc("cot"))
    async for _ in p.stream_structured(
        system="S" * 3800, doc=handle, question=Q1_EN, schema=None, lang="en", max_output_tokens=100
    ):
        pass
    body = json.loads(route.calls[0].request.content)
    schema_chars = len(json.dumps(body["response_format"], separators=(",", ":")))
    chars = sum(len(m["content"]) for m in body["messages"]) + schema_chars
    assert chars / 3.6 < s.retrieval_max_prompt_tokens  # conservative chars->tokens estimate


@respx.mock
def test_429_waits_retry_after_then_succeeds(groq_app):
    route = respx.post(URL).mock(side_effect=[rate_limited("0.2"), groq_ok(Q1)])
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    assert route.call_count == 2
    models = [json.loads(c.request.content)["model"] for c in route.calls]
    assert models == ["openai/gpt-oss-120b", "openai/gpt-oss-120b"]
    assert any(n == "WARNING" and d["code"] == "RATE_LIMIT_WAIT" for n, d in ev)
    assert names(ev)[-1] == "RUN_FINISHED"


@respx.mock
def test_429_with_long_wait_goes_to_fallback_model(groq_app):
    route = respx.post(URL).mock(side_effect=[rate_limited("45"), groq_ok(Q1)])
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    models = [json.loads(c.request.content)["model"] for c in route.calls]
    assert models == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
    assert "reasoning_effort" not in json.loads(route.calls[1].request.content)
    assert any(n == "WARNING" and d["code"] == "FALLBACK_MODEL_USED" for n, d in ev)
    m = next(d for n, d in ev if n == "METRICS")
    assert m["fallback_used"] and m["model"] == "qwen/qwen3.8-27b"


@respx.mock
def test_429_everywhere_is_a_rate_limit_error(groq_app):
    respx.post(URL).mock(return_value=rate_limited("50"))
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    err = next(d for n, d in ev if n == "RUN_ERROR")
    assert err["code"] == "RATE_LIMITED" and names(ev)[-1] == "RUN_ERROR"


@respx.mock
def test_schema_rejection_is_not_retried(groq_app):
    route = respx.post(URL).mock(return_value=httpx.Response(400, json={"error": {"message": "invalid json_schema"}}))
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    assert route.call_count == 1
    assert next(d for n, d in ev if n == "RUN_ERROR")["code"] == "SCHEMA_REJECTED"


@respx.mock
def test_groq_text_mode_streams_with_x_groq_usage(groq_app):
    sse = (
        'data: {"choices":[{"delta":{"content":"Chain of thought "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"is prose."},"finish_reason":"stop"}],'
        '"x_groq":{"usage":{"prompt_tokens":4000,"completion_tokens":20}}}\n\n'
        "data: [DONE]\n\n"
    )
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
    )
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN, endpoint="/api/ask_text")
    assert json.loads(route.calls[0].request.content)["stream"] is True
    assert text_of(ev) == "Chain of thought is prose."
    m = next(d for n, d in ev if n == "METRICS")
    assert m["tokens"]["input"] == 4000 and m["provider"] == "groq"


def test_provider_error_carries_retry_after():
    p = GroqProvider(make_settings_dummy())
    err = p._error(429, "slow down", httpx.Headers({"retry-after": "7"}))
    assert isinstance(err, ProviderError) and err.retryable and err.retry_after == 7.0 and err.code == "RATE_LIMITED"
    err2 = p._error(429, "slow down", httpx.Headers({"x-ratelimit-reset-tokens": "2m3s"}))
    assert err2.retry_after == 123.0


def make_settings_dummy():
    import tempfile
    from pathlib import Path

    return make_settings(Path(tempfile.mkdtemp()), mock_llm=False, groq_api_key="k")


@respx.mock
def test_invalid_generation_is_retried(groq_app):
    bad = httpx.Response(
        400,
        json={
            "error": {
                "message": "Generated JSON does not match the expected schema. Please adjust your prompt.",
                "type": "invalid_request_error",
                "code": "json_validate_failed",
            }
        },
    )
    route = respx.post(URL).mock(side_effect=[bad, groq_ok(Q1)])
    ev = ask(groq_app, cot_doc(groq_app), Q1_EN)
    assert route.call_count == 2 and names(ev)[-1] == "RUN_FINISHED"
