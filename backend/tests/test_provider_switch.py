"""The UI's Gemini/Groq switch: /api/config, per-request provider, labels, availability."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import make_settings
from .helpers import Q1_EN, ask, components, cot_doc


def test_config_lists_providers_in_mock_mode(client):
    cfg = client.get("/api/config").json()
    assert cfg["mock"] is True
    assert [(p["name"], p["model"], p["available"]) for p in cfg["providers"]] == [
        ("gemini", "gemini-3.8-flash", True),
        ("groq", "openai/gpt-oss-120b", True),
    ]


def test_mock_answers_as_the_requested_provider(client):
    doc = cot_doc(client)
    gem = next(d for n, d in ask(client, doc, Q1_EN, provider="gemini") if n == "METRICS")
    groq_events = ask(client, doc, Q1_EN, provider="groq")
    groq = next(d for n, d in groq_events if n == "METRICS")
    assert (gem["provider"], gem["model"]) == ("gemini (mock)", "gemini-3.8-flash")
    assert (groq["provider"], groq["model"], groq["schema_mode"]) == ("groq (mock)", "openai/gpt-oss-120b", "strict")
    assert groq["retrieval"]["retrieval"] == "bm25" and gem["retrieval"]["retrieval"] == "off"
    assert groq["tokens"]["input"] < 6000 < gem["tokens"]["input"]
    # Replays fixtures/answers/live/groq/q1.en.json when a live Groq answer was recorded.
    assert components(groq_events) and components(groq_events)[0]["type"] == "comparison"
    assert next(d for n, d in groq_events if n == "RUN_STARTED")["provider"] == "groq (mock)"


def test_answers_are_cached_per_provider(client):
    doc = cot_doc(client)
    ask(client, doc, "Who are the authors of this paper?", provider="gemini")
    second = ask(client, doc, "Who are the authors of this paper?", provider="groq")
    assert next(d for n, d in second if n == "RUN_STARTED")["cached"] is False


def test_unconfigured_provider_is_rejected(tmp_path):
    s = make_settings(tmp_path, mock_llm=False, llm_provider="groq", groq_api_key="k", gemini_api_key="")
    with TestClient(create_app(s)) as c:
        doc = cot_doc(c)
        r = c.post("/api/ask", json={"doc_id": doc, "question": "hi", "lang": "en", "provider": "gemini"})
        assert r.status_code == 400 and r.json()["code"] == "PROVIDER_UNAVAILABLE"
        cfg = c.get("/api/config").json()
    assert cfg["provider"] == "groq"
    assert {p["name"]: p["available"] for p in cfg["providers"]} == {"gemini": False, "groq": True}


def test_provider_env_alias(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("PROVIDER", "groq")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert Settings().llm_provider == "groq"
    monkeypatch.delenv("PROVIDER")
    assert Settings().llm_provider == "gemini"


async def test_gemini_with_retrieval_sends_text_not_file(tmp_path, monkeypatch):
    from app.providers.gemini import GeminiProvider
    from scripts.check_fixtures import load_doc

    s = make_settings(tmp_path, mock_llm=False, gemini_api_key="x", retrieval="on")
    p = GeminiProvider(s)
    seen = {}

    async def fake_stream(*, model, contents, config):
        seen["parts"] = contents[0].parts

        async def gen():
            yield SimpleNamespace(usage_metadata=None, candidates=[])

        return gen()

    async def no_upload(**_):
        raise AssertionError("retrieval mode must not upload the PDF")

    monkeypatch.setattr(p.client.aio.models, "generate_content_stream", fake_stream)
    monkeypatch.setattr(p.client.aio.files, "upload", no_upload)
    handle = await p.prepare_document(load_doc("cot"))
    out = [
        d
        async for d in p.stream_structured(
            system="S", doc=handle, question=Q1_EN, schema=None, lang="en", max_output_tokens=10
        )
    ]
    texts = [part.text for part in seen["parts"] if part.text]
    assert any("[[page 1]]" in t for t in texts)
    assert not any(getattr(part, "file_data", None) for part in seen["parts"])
    assert out[-1].meta["retrieval"] == "bm25"
