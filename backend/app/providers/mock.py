"""Replays fixtures as streamed deltas (MOCK_LLM=1). Deterministic; no network."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from ..config import Settings
from ..grounding import normalize
from ..upload import StoredDoc
from .base import ProviderDelta, ProviderDocHandle, ProviderError, Usage

CHUNK = 40
TOKENS_PER_PAGE = 560  # measured with count_tokens on cot.pdf (24,081 tokens / 43 pages)
_SAFE_NAME = re.compile(r"^[a-z0-9_]+/[a-z0-9_]+$")


class MockProvider:
    name = "mock"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.fixtures_dir / "answers"
        index = self.root / "index.json"
        self.index: dict[str, Any] = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        self._busy_calls = 0

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle:
        slug = self.index.get("docs", {}).get(doc.sha256, "generic")
        return ProviderDocHandle(self.name, doc.doc_id, doc.sha256, {"slug": slug, "pages": doc.page_count})

    def question_id(self, slug: str, question: str) -> str | None:
        questions: dict[str, Any] = self.index.get("questions", {}).get(slug, {})
        q = normalize(question)
        best, best_score = None, 0.0
        for qid, entry in questions.items():
            for text in (entry.get("en", ""), entry.get("ar", "")):
                score = fuzz.ratio(q, normalize(text))
                if score > best_score:
                    best, best_score = qid, score
        if best_score >= 75:
            return best
        hits = {
            qid: sum(1 for kw in entry.get("keywords", []) if normalize(kw) in q) for qid, entry in questions.items()
        }
        top = max(hits.items(), key=lambda kv: kv[1], default=(None, 0))
        return top[0] if top[1] > 0 else None

    def _fixture_path(self, doc: ProviderDocHandle, question: str, lang: str, ext: str, forced: str | None) -> Path:
        if forced:
            return self.root / f"{forced}.json"
        slug = doc.data.get("slug", "generic")
        sub = "text/" if ext == "txt" else ""
        qid = self.question_id(slug, question)
        for candidate in (
            self.root / slug / f"{sub}{qid}.{lang}.{ext}" if qid else None,
            self.root / slug / f"{sub}default.{lang}.{ext}",
            self.root / "generic" / f"{sub}default.{lang}.{ext}",
        ):
            if candidate is not None and candidate.exists():
                return candidate
        raise ProviderError("NO_FIXTURE", f"no mock fixture for {slug}/{qid}/{lang}")

    async def _replay(self, text: str, doc: ProviderDocHandle) -> AsyncIterator[ProviderDelta]:
        await asyncio.sleep(self.settings.mock_ttft_ms / 1000)
        for i in range(0, len(text), CHUNK):
            yield ProviderDelta(text_delta=text[i : i + CHUNK])
            await asyncio.sleep(self.settings.mock_delay_ms / 1000)
        usage = Usage(input=doc.data.get("pages", 1) * TOKENS_PER_PAGE + 1800, output=max(1, len(text) // 3))
        yield ProviderDelta(usage=usage, finish_reason="STOP")

    async def _forced_error(self, forced: str, model: str | None) -> None:
        kind = forced.split("/", 1)[1]
        if kind == "busy" or (kind == "busy_then_ok" and model != self.settings.fallback_model):
            raise ProviderError("UPSTREAM_BUSY", "mock 503", 503, retryable=True)
        if kind == "run_error":
            await asyncio.sleep(self.settings.mock_ttft_ms / 1000)
            raise ProviderError("UPSTREAM_ERROR", "mock failure")

    async def stream_structured(
        self,
        *,
        system: str,
        doc: ProviderDocHandle,
        question: str,
        schema: dict[str, Any] | None,
        lang: str,
        max_output_tokens: int,
        model: str | None = None,
        text_only: bool = False,
        intent: str | None = None,
        mock_fixture: str | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        forced = mock_fixture if mock_fixture and _SAFE_NAME.match(mock_fixture) else None
        if forced == "error/stall":
            # Stream the start of a real answer, then hang: exercises the request timeout.
            text = self._fixture_path(doc, question, lang, "json", None).read_text(encoding="utf-8")
            await asyncio.sleep(self.settings.mock_ttft_ms / 1000)
            yield ProviderDelta(text_delta=text[:150])
            await asyncio.sleep(3600)
            return
        if forced and forced.startswith("error/"):
            await self._forced_error(forced, model)
            forced = None
        text = self._fixture_path(doc, question, lang, "json", forced).read_text(encoding="utf-8")
        try:
            # Fixtures are pretty-printed for humans; a real model streams compact JSON.
            text = json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))
        except ValueError:
            pass  # deliberately malformed fixtures (e.g. truncated) replay as-is
        if text_only:
            # Honour the user's text-only preference the way the real model is told to.
            data = json.loads(text)
            data["needs_visual"], data["components"] = False, []
            text = json.dumps(data, ensure_ascii=False)
        async for d in self._replay(text, doc):
            yield d

    async def stream_text(
        self,
        *,
        system: str,
        doc: ProviderDocHandle,
        question: str,
        lang: str,
        max_output_tokens: int,
        model: str | None = None,
        mock_fixture: str | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        text = self._fixture_path(doc, question, lang, "txt", None).read_text(encoding="utf-8")
        async for d in self._replay(text, doc):
            yield d

    async def count_tokens(self, doc: ProviderDocHandle) -> int:
        return doc.data.get("pages", 1) * TOKENS_PER_PAGE
