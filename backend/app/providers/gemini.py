"""Gemini through google-genai (generateContent streaming, Files API, thinking level)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import errors, types

from ..config import Settings
from ..prompts import DOC_END, DOC_START, question_block
from ..upload import StoredDoc
from .base import ProviderDelta, ProviderDocHandle, ProviderError, Usage

log = logging.getLogger("arif.gemini")

FILE_MAX_AGE_S = 47 * 3600
_RESOLUTION = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}
_THINKING = {
    "minimal": types.ThinkingLevel.MINIMAL,
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}


def _usage(meta: Any) -> Usage | None:
    if meta is None:
        return None
    return Usage(
        input=meta.prompt_token_count or 0,
        cached_input=meta.cached_content_token_count or 0,
        output=meta.candidates_token_count or 0,
        thinking=meta.thoughts_token_count or 0,
    )


def _to_provider_error(exc: Exception) -> ProviderError:
    status = getattr(exc, "code", None)
    msg = str(exc)[:300]
    if isinstance(exc, errors.APIError):
        if status in (429, 503, 500, 504):
            return ProviderError("UPSTREAM_BUSY", msg, status, retryable=True)
        if status == 400 and "INVALID_ARGUMENT" in msg:
            return ProviderError("SCHEMA_REJECTED", msg, status)
        if status in (401, 403):
            return ProviderError("UPSTREAM_AUTH", msg, status)
        return ProviderError("UPSTREAM_ERROR", msg, status)
    return ProviderError("UPSTREAM_ERROR", msg, None, retryable=False)


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)
        # sha256 -> {file_uri, mime_type, uploaded_at, cache_name}
        self._files: dict[str, dict[str, Any]] = {}

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle:
        entry = self._files.get(doc.sha256) or doc.provider_handles.get(self.name)
        if not entry or time.time() - entry["uploaded_at"] > FILE_MAX_AGE_S:
            try:
                f = await self.client.aio.files.upload(
                    file=doc.path, config=types.UploadFileConfig(mime_type="application/pdf")
                )
            except Exception as exc:
                raise _to_provider_error(exc) from exc
            entry = {"file_uri": f.uri, "mime_type": "application/pdf", "uploaded_at": time.time()}
            log.info("uploaded %s to Files API", doc.doc_id)
        self._files[doc.sha256] = entry
        doc.provider_handles[self.name] = entry
        return ProviderDocHandle(self.name, doc.doc_id, doc.sha256, dict(entry))

    def _doc_parts(self, doc: ProviderDocHandle) -> list[types.Part]:
        return [
            types.Part(text=DOC_START),
            types.Part.from_uri(file_uri=doc.data["file_uri"], mime_type=doc.data["mime_type"]),
            types.Part(text=DOC_END),
        ]

    async def _explicit_cache(self, doc: ProviderDocHandle, system: str, model: str) -> str | None:
        if not self.settings.enable_explicit_cache:
            return None
        key = f"cache:{model}:{hash(system)}"
        entry = self._files.get(doc.sha256, {})
        if key in entry:
            return entry[key]
        try:
            cache = await self.client.aio.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    contents=[types.Content(role="user", parts=self._doc_parts(doc))],
                    system_instruction=system,
                    ttl="3600s",
                ),
            )
        except Exception as exc:  # explicit caching is optional; fall back to implicit caching
            log.warning("explicit cache create failed: %s", exc)
            return None
        entry[key] = cache.name
        return cache.name

    async def _stream(
        self, *, system: str, doc: ProviderDocHandle, prompt: str, model: str, config: dict[str, Any]
    ) -> AsyncIterator[ProviderDelta]:
        cache_name = await self._explicit_cache(doc, system, model)
        parts = [types.Part(text=prompt)] if cache_name else [*self._doc_parts(doc), types.Part(text=prompt)]
        kwargs: dict[str, Any] = {
            "thinking_config": types.ThinkingConfig(thinking_level=_THINKING[self.settings.thinking_level]),
            "media_resolution": _RESOLUTION.get(self.settings.media_resolution),
            **({"cached_content": cache_name} if cache_name else {"system_instruction": system}),
            **config,
        }
        cfg = types.GenerateContentConfig(**kwargs)
        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=model, contents=[types.Content(role="user", parts=parts)], config=cfg
            )
            usage: Usage | None = None
            finish: str | None = None
            async for chunk in stream:
                usage = _usage(chunk.usage_metadata) or usage
                if chunk.candidates and chunk.candidates[0].finish_reason:
                    finish = str(chunk.candidates[0].finish_reason)
                text = "".join(
                    p.text
                    for c in (chunk.candidates or [])[:1]
                    for p in ((c.content.parts if c.content else None) or [])
                    if p.text and not p.thought
                )
                if text:
                    yield ProviderDelta(text_delta=text)
            yield ProviderDelta(usage=usage, finish_reason=finish)
        except ProviderError:
            raise
        except Exception as exc:
            raise _to_provider_error(exc) from exc

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
    ) -> AsyncIterator[ProviderDelta]:
        async for d in self._stream(
            system=system,
            doc=doc,
            prompt=question_block(question, lang, text_only=text_only, intent=intent),
            model=model or self.settings.model,
            config={
                "response_mime_type": "application/json",
                # SCHEMA_MODE=json sends no schema (it is in the system prompt instead).
                **({"response_json_schema": schema} if schema else {}),
                "max_output_tokens": max_output_tokens,
            },
        ):
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
    ) -> AsyncIterator[ProviderDelta]:
        async for d in self._stream(
            system=system,
            doc=doc,
            prompt=question_block(question, lang),
            model=model or self.settings.model,
            config={"max_output_tokens": max_output_tokens},
        ):
            yield d

    async def count_tokens(self, doc: ProviderDocHandle) -> int:
        resp = await self.client.aio.models.count_tokens(
            model=self.settings.model, contents=[types.Content(role="user", parts=self._doc_parts(doc))]
        )
        return resp.total_tokens or 0
