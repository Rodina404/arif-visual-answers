import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from scripts.make_injection_pdf import make_encrypted, make_many_pages

from .conftest import PDFS, make_settings, upload


def test_valid_pdf(client):
    r = upload(client, PDFS / "cot.pdf")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pages"] == 43
    assert body["sha256"].startswith("7d9f878c")
    assert not [w for w in body["warnings"] if w["code"] == "HIDDEN_TEXT_DETECTED"]
    p = client.get(f"/api/documents/{body['doc_id']}/pages/1").json()
    assert "Chain-of-Thought Prompting" in p["text"]
    assert "We explore how generating a chain of thought" in p["text"]


def test_png_renamed_to_pdf_is_rejected(client):
    r = upload(client, PDFS / "notpdf.pdf")
    assert r.status_code == 415
    assert r.json()["code"] == "NOT_PDF"


def test_wrong_content_type_is_rejected(client):
    r = upload(client, PDFS / "tiny.pdf", content_type="text/plain")
    assert r.status_code == 415


def test_oversize_is_rejected(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, max_upload_mb=1))) as c:
        data = b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024)
        r = c.post("/api/documents", files={"file": ("big.pdf", data, "application/pdf")})
    assert r.status_code == 413
    assert r.json()["code"] == "TOO_LARGE"


def test_too_many_pages_is_rejected(client, tmp_path):
    f = tmp_path / "many.pdf"
    make_many_pages(f, 61)
    r = upload(client, f)
    assert r.status_code == 413
    assert r.json()["code"] == "TOO_MANY_PAGES"


def test_encrypted_is_rejected(client, tmp_path):
    f = tmp_path / "enc.pdf"
    make_encrypted(f)
    r = upload(client, f)
    assert r.status_code == 400
    assert r.json()["code"] == "ENCRYPTED"


def test_garbage_after_magic_is_rejected(client):
    r = client.post("/api/documents", files={"file": ("x.pdf", b"%PDF-1.4 garbage", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["code"] == "UNREADABLE"


def test_injection_hidden_text_detected(client):
    r = upload(client, PDFS / "injection.pdf")
    body = r.json()
    warn = [w for w in body["warnings"] if w["code"] == "HIDDEN_TEXT_DETECTED"]
    assert warn and warn[0]["pages"] == [1]
    text = client.get(f"/api/documents/{body['doc_id']}/pages/1").json()["text"]
    assert "63.7%" in text
    assert "SYSTEM" not in text and "evil.example" not in text


def test_storage_uses_random_uuid_outside_static(client, settings):
    body = upload(client, PDFS / "tiny.pdf").json()
    stored = list((settings.data_dir / "uploads").iterdir())
    assert [f.name for f in stored] == [f"{body['doc_id']}.pdf"]


@pytest.mark.parametrize("bad", ["..%2F..%2Fetc%2Fpasswd", "not-a-uuid"])
def test_unknown_doc_ids(client, bad):
    assert client.get(f"/api/documents/{bad}/pages/1").status_code == 404


def test_page_out_of_range(client):
    body = upload(client, PDFS / "tiny.pdf").json()
    assert client.get(f"/api/documents/{body['doc_id']}/pages/2").status_code == 404


def test_cleanup_removes_old_files(client):
    body = upload(client, PDFS / "tiny.pdf").json()
    store = client.app.state.store
    assert store.cleanup(now=time.time() + 49 * 3600) >= 2
    assert store.get(body["doc_id"]) is None
