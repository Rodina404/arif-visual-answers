import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
PDFS = ROOT / "fixtures" / "pdfs"


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = Settings(data_dir=tmp_path / "data", mock_llm=True, gemini_api_key="", mock_ttft_ms=0, mock_delay_ms=0)
    return dataclasses.replace(base, **overrides)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def upload(client, path: Path, content_type: str = "application/pdf", name: str | None = None):
    return client.post("/api/documents", files={"file": (name or path.name, path.read_bytes(), content_type)})
