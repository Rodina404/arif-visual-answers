"""Any-PDF features: document list/delete, demo flag, OCR for scanned pages, suggestions, query translation."""

import io
import json
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import PDFS, make_settings, upload
from .helpers import ANSWERS, ask, components

URL = "https://api.groq.com/openai/v1/chat/completions"
INDEX = json.loads((ANSWERS / "index.json").read_text(encoding="utf-8"))["questions"]["cot"]


def image_only_pdf(text_lines: list[str]) -> bytes:
    """A one-page PDF whose only content is a picture of text (like a scanned slide)."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    for i, line in enumerate(text_lines):
        draw.text((80, 120 + i * 120), line, fill="black", font=font)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(1600, 900), invariant=1)
    c.drawImage(ImageReader(img), 0, 0, width=1600, height=900)
    c.showPage()
    c.save()
    return buf.getvalue()


def wait_ready(client, doc_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        d = client.get(f"/api/documents/{doc_id}").json()
        if d["status"] == "ready":
            return d
        time.sleep(0.3)
    raise AssertionError("document never became ready")


ME = {"X-Client-Id": "client-aaaa-1111"}
OTHER = {"X-Client-Id": "client-bbbb-2222"}


def up(client, path, headers):
    return client.post(
        "/api/documents", files={"file": (path.name, path.read_bytes(), "application/pdf")}, headers=headers
    )


def test_list_and_delete_documents(client):
    a = up(client, PDFS / "cot.pdf", ME).json()
    b = up(client, PDFS / "tiny.pdf", ME).json()
    up(client, PDFS / "tiny.pdf", OTHER)
    listed = client.get("/api/documents", headers=ME).json()
    assert [d["doc_id"] for d in listed] == [a["doc_id"], b["doc_id"]]
    assert [d["is_demo"] for d in listed] == [True, False]
    assert all(d["status"] == "ready" and d["language"] == "en" for d in listed)
    # Another browser can't see or delete my documents; no id at all lists nothing.
    assert len(client.get("/api/documents", headers=OTHER).json()) == 1
    assert client.get("/api/documents").json() == []
    assert client.delete(f"/api/documents/{a['doc_id']}", headers=OTHER).status_code == 404
    assert client.delete(f"/api/documents/{a['doc_id']}", headers=ME).json() == {"deleted": a["doc_id"]}
    assert [d["doc_id"] for d in client.get("/api/documents", headers=ME).json()] == [b["doc_id"]]
    assert client.get(f"/api/documents/{a['doc_id']}/pages/1").status_code == 404
    assert client.delete(f"/api/documents/{a['doc_id']}", headers=ME).status_code == 404


def test_scanned_pdf_is_ocrd_in_the_background(client):
    data = image_only_pdf(["Smart Job Matching", "Collaborative filtering", "Hybrid models win"])
    r = client.post("/api/documents", files={"file": ("slides.pdf", data, "application/pdf")})
    body = r.json()
    assert body["status"] == "reading"
    d = wait_ready(client, body["doc_id"])
    assert d["ocr_pages"] == [1]
    assert any(w["code"] == "OCR_USED" for w in d["warnings"])
    text = client.get(f"/api/documents/{body['doc_id']}/pages/1").json()["text"].lower()
    assert "collaborative" in text and "hybrid" in text


def test_mock_suggestions_are_generic_and_localised(client):
    doc = upload(client, PDFS / "tiny.pdf").json()["doc_id"]
    en = client.get(f"/api/documents/{doc}/suggestions?lang=en").json()
    ar = client.get(f"/api/documents/{doc}/suggestions?lang=ar").json()
    assert en["generated"] is False and len(en["questions"]) == 4
    assert ar["questions"][0] != en["questions"][0]


@pytest.fixture
def live_groq(tmp_path):
    s = make_settings(tmp_path, mock_llm=False, llm_provider="groq", groq_api_key="gsk_test")
    with TestClient(create_app(s)) as c:
        yield c


def _chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 50}})


@respx.mock
def test_suggestions_are_generated_once_and_cached(live_groq):
    route = respx.post(URL).mock(
        return_value=_chat(json.dumps({"questions": ["Q one?", "Q two?", "Q three?", "Q four?"]}))
    )
    doc = upload(live_groq, PDFS / "tiny.pdf").json()["doc_id"]
    first = live_groq.get(f"/api/documents/{doc}/suggestions?lang=en").json()
    second = live_groq.get(f"/api/documents/{doc}/suggestions?lang=en").json()
    assert first["questions"] == second["questions"] == ["Q one?", "Q two?", "Q three?", "Q four?"]
    assert route.call_count == 1
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "openai/gpt-oss-20b" and body["response_format"]["json_schema"]["strict"] is True
    assert "A tiny one-page PDF" in body["messages"][1]["content"]


@respx.mock
def test_suggestions_fall_back_when_the_call_fails(live_groq):
    respx.post(URL).mock(return_value=httpx.Response(429, json={"error": {"message": "slow down"}}))
    doc = upload(live_groq, PDFS / "tiny.pdf").json()["doc_id"]
    assert len(live_groq.get(f"/api/documents/{doc}/suggestions?lang=ar").json()["questions"]) == 4


@respx.mock
def test_arabic_question_is_translated_for_retrieval_only(live_groq):
    q2 = json.loads((ANSWERS / "cot" / "q2.ar.json").read_text(encoding="utf-8"))
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["model"] == "openai/gpt-oss-20b":
            return _chat(INDEX["q2"]["en"])  # the translation
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(q2, ensure_ascii=False)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5000, "completion_tokens": 900},
            },
        )

    respx.post(URL).mock(side_effect=handler)
    doc = upload(live_groq, PDFS / "cot.pdf").json()["doc_id"]
    ev = ask(live_groq, doc, INDEX["q2"]["ar"], lang="ar")
    assert [c["model"] for c in calls] == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    main = calls[1]["messages"][1]["content"]
    assert "[[page 21]]" in main and "62B 9.6 29.9" in main  # retrieval found Table 2 via the translation
    assert INDEX["q2"]["ar"] in main  # ...while the answer model still gets the original Arabic question
    m = next(d for n, d in ev if n == "METRICS")
    assert m["retrieval"]["search_query"] == INDEX["q2"]["en"]
    assert components(ev)[0]["verification"]["status"] == "verified"

    # Same question again (different document upload): the translation comes from the cache.
    calls.clear()
    doc2 = upload(live_groq, PDFS / "cot.pdf").json()["doc_id"]
    live_groq.post("/api/ask", json={"doc_id": doc2, "question": INDEX["q2"]["ar"] + " ", "lang": "ar"})
    assert all(c["model"] != "openai/gpt-oss-20b" for c in calls)


@respx.mock
def test_english_question_on_english_document_is_not_translated(live_groq):
    route = respx.post(URL).mock(
        return_value=_chat(json.dumps({"answer_text": "x", "language": "en", "needs_visual": False, "components": []}))
    )
    doc = upload(live_groq, PDFS / "tiny.pdf").json()["doc_id"]
    ask(live_groq, doc, "What is this?", lang="en")
    assert [json.loads(c.request.content)["model"] for c in route.calls] == ["openai/gpt-oss-120b"]
