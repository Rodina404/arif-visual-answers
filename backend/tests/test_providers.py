import dataclasses
import json
from datetime import date

import httpx
import pytest
import respx

from app.cache import AnswerCache, cache_key
from app.config import Settings
from app.metrics import MetricsLog, cost_usd, price_for
from app.providers import get_provider
from app.providers.base import ProviderError, Usage, page_marked_text
from app.providers.gemini import _to_provider_error
from app.providers.openai_compat import OpenAICompatProvider
from app.upload import PageText, StoredDoc


def _doc() -> StoredDoc:
    pages = [PageText(1, "First page text.", "First page text."), PageText(2, "Second page.", "Second page.")]
    return StoredDoc("11111111-1111-1111-1111-111111111111", "sha", "d.pdf", "d.pdf", 0, pages)


def _sse(*chunks: dict) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


@pytest.fixture
def compat_settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        llm_provider="openai_compat",
        openai_compat_base_url="http://llm.local/v1",
        openai_compat_model="qwen-test",
        openai_compat_api_key="k",
    )


def test_page_markers():
    assert page_marked_text(_doc()) == "[[page 1]]\nFirst page text.\n\n[[page 2]]\nSecond page."


@respx.mock
async def test_openai_compat_structured_stream(compat_settings):
    route = respx.post("http://llm.local/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text=_sse(
                {"choices": [{"delta": {"content": '{"answer_text": "Hi'}}]},
                {"choices": [{"delta": {"content": '"}'}, "finish_reason": "stop"}]},
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 8,
                        "prompt_tokens_details": {"cached_tokens": 100},
                    },
                },
            ),
            headers={"content-type": "text/event-stream"},
        )
    )
    p = OpenAICompatProvider(compat_settings)
    handle = await p.prepare_document(_doc())
    deltas = [
        d
        async for d in p.stream_structured(
            system="SYS", doc=handle, question="Q?", schema={"type": "object"}, lang="en", max_output_tokens=50
        )
    ]
    assert "".join(d.text_delta or "" for d in deltas) == '{"answer_text": "Hi"}'
    assert deltas[-1].usage == Usage(input=120, cached_input=100, output=8)
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "qwen-test" and body["stream"] is True
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert "[[page 2]]" in body["messages"][1]["content"]  # extracted text, not the PDF
    assert route.calls[0].request.headers["authorization"] == "Bearer k"


@respx.mock
async def test_openai_compat_text_mode_has_no_response_format(compat_settings):
    route = respx.post("http://llm.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=_sse({"choices": [{"delta": {"content": "prose"}}]}))
    )
    p = OpenAICompatProvider(compat_settings)
    handle = await p.prepare_document(_doc())
    out = [d async for d in p.stream_text(system="S", doc=handle, question="Q", lang="ar", max_output_tokens=10)]
    assert out[0].text_delta == "prose"
    assert "response_format" not in json.loads(route.calls[0].request.content)


@respx.mock
async def test_openai_compat_busy_is_retryable(compat_settings):
    respx.post("http://llm.local/v1/chat/completions").mock(return_value=httpx.Response(503, text="busy"))
    p = OpenAICompatProvider(compat_settings)
    handle = await p.prepare_document(_doc())
    with pytest.raises(ProviderError) as exc:
        async for _ in p.stream_text(system="S", doc=handle, question="Q", lang="en", max_output_tokens=10):
            pass
    assert exc.value.retryable and exc.value.status == 503


def test_gemini_error_mapping():
    from google.genai import errors

    busy = errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    assert _to_provider_error(busy).retryable
    bad = errors.ClientError(400, {"error": {"code": 400, "message": "x", "status": "INVALID_ARGUMENT"}})
    assert _to_provider_error(bad).code == "SCHEMA_REJECTED" and not _to_provider_error(bad).retryable
    auth = errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}})
    assert _to_provider_error(auth).code == "UPSTREAM_AUTH"


def test_provider_selection(tmp_path):
    base = Settings(data_dir=tmp_path, gemini_api_key="x")
    assert get_provider(dataclasses.replace(base, llm_provider="gemini")).name == "gemini"
    assert get_provider(dataclasses.replace(base, llm_provider="openai_compat")).name == "openai_compat"
    assert get_provider(dataclasses.replace(base, llm_provider="mock")).name == "mock"
    assert get_provider(dataclasses.replace(base, llm_provider="gemini", mock_llm=True)).name == "mock"
    with pytest.raises(ValueError):
        get_provider(dataclasses.replace(base, llm_provider="nope"))


def test_cost_both_price_periods():
    u = Usage(input=10_000, cached_input=4_000, output=1_000, thinking=500)
    before = cost_usd("gemini-3.8-flash", u, date(2026, 10, 29))
    # 6,000 uncached x 0.75 + 4,000 cached x 0.075 + 1,500 output+thinking x 3.75, per 1M
    assert before["input"] == pytest.approx(0.0045)
    assert before["cached_input"] == pytest.approx(0.0003)
    assert before["output"] == pytest.approx(0.005625)
    assert before["total"] == pytest.approx(0.010425)
    after = cost_usd("gemini-3.8-flash", u, date(2027, 1, 1))
    assert after["total"] == pytest.approx(2 * before["total"])
    assert price_for("gemini-3.8-flash", date(2026, 12, 31))["input"] == 0.75
    assert cost_usd("self-hosted", u)["total"] == 0.0


def test_cache_key_and_roundtrip(tmp_path):
    k1 = cache_key(sha256="s", question="  What IS it? ", lang="en", model="m", prompt_version="v1", mode="visual")
    k2 = cache_key(sha256="s", question="what is it?", lang="en", model="m", prompt_version="v1", mode="visual")
    assert k1 == k2
    assert k1 != cache_key(sha256="s", question="what is it?", lang="ar", model="m", prompt_version="v1", mode="visual")
    assert k1 != cache_key(sha256="s", question="what is it?", lang="en", model="m", prompt_version="v2", mode="visual")
    c = AnswerCache(tmp_path / "c.sqlite")
    c.put(k1, [("COMPONENT", {"a": "ع"})])
    assert c.get(k1) == [("COMPONENT", {"a": "ع"})] and c.get("missing") is None


def test_metrics_summary_percentiles():
    log = MetricsLog()
    for ms in (100, 200, 300, 400, 1000):
        log.add(
            {
                "mode": "visual",
                "latency_ms": {"total": ms, "ttft_text": ms // 2},
                "cost_usd": {"total": 0.01},
                "cache": {"app_cache_hit": False},
            }
        )
    s = log.summary()["by_mode"]["visual"]
    assert s["latency_total_ms"]["p50"] == 300 and s["count"] == 5 and s["cost_usd_mean"] == 0.01
