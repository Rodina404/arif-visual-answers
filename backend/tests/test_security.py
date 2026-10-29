import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import CSP

from .conftest import PDFS, make_settings, upload
from .helpers import Q1_EN, ask, cot_doc, names

ROOT = Path(__file__).resolve().parents[2]


def test_security_headers_on_api_and_root(client):
    for path in ("/healthz", "/"):
        r = client.get(path)
        assert r.headers["content-security-policy"] == CSP
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in CSP and "object-src 'none'" in CSP


def test_ask_rate_limit(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, rate_limit_ask="2/minute"))) as c:
        doc = cot_doc(c)
        body = {"doc_id": doc, "question": "Who are the authors of this paper?", "lang": "en"}
        assert c.post("/api/ask", json=body).status_code == 200
        assert c.post("/api/ask", json=body).status_code == 200
        r = c.post("/api/ask", json=body)
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"


def test_upload_rate_limit(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, rate_limit_upload="1/minute"))) as c:
        assert upload(c, PDFS / "tiny.pdf").status_code == 200
        assert upload(c, PDFS / "tiny.pdf").status_code == 429


def test_question_length_cap(client):
    doc = cot_doc(client)
    r = client.post("/api/ask", json={"doc_id": doc, "question": "x" * 501, "lang": "en"})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_REQUEST"
    r = client.post("/api/ask", json={"doc_id": doc, "question": "hi", "lang": "fr"})
    assert r.status_code == 422


def test_questions_per_doc_cap(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, max_questions_per_doc=1))) as c:
        doc = cot_doc(c)
        ask(c, doc, "Who are the authors of this paper?")
        r = c.post("/api/ask", json={"doc_id": doc, "question": "again", "lang": "en"})
    assert r.status_code == 429 and r.json()["code"] == "QUESTION_LIMIT"


def test_request_body_cap(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, max_upload_mb=1))) as c:
        r = c.post("/api/documents", content=b"x" * (3 * 1024 * 1024), headers={"content-type": "application/pdf"})
    assert r.status_code == 413


def test_unsafe_mock_fixture_name_ignored(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as c:
        ev = ask(c, cot_doc(c), Q1_EN, fixture="../../etc/passwd")
    assert names(ev)[-1] == "RUN_FINISHED"  # unsafe fixture names are ignored, the normal fixture is used


def test_spa_route_cannot_escape_dist(client):
    r = client.get("/..%2F..%2Fbackend%2Fapp%2Fconfig.py")
    assert "GEMINI_API_KEY" not in r.text


def test_api_key_not_in_frontend_sources_or_build():
    import os

    key = os.getenv("GEMINI_API_KEY", "")
    for folder in (ROOT / "frontend" / "src", ROOT / "frontend" / "dist"):
        if not folder.exists():
            continue
        for f in folder.rglob("*"):
            if f.is_file() and f.suffix in {".js", ".ts", ".tsx", ".html", ".json", ".css", ".map"}:
                text = f.read_text(encoding="utf-8", errors="ignore")
                assert not re.search(r"AIza[0-9A-Za-z_\-]{20,}", text), f
                assert not key or key not in text, f


def test_no_secrets_in_prompts():
    from app import prompts

    for value in vars(prompts).values():
        if isinstance(value, str):
            assert "AIza" not in value
