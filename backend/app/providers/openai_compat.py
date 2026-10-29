"""OpenAI-compatible /chat/completions providers: self-hosted (vLLM, Ollama, llama.cpp) and Groq.

The PDF never leaves the server: the model receives extracted visible text with [[page N]] markers,
either the whole document or (RETRIEVAL) only the chunks most relevant to the question.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .. import retrieval
from ..config import Settings
from ..prompts import DOC_END, DOC_START, question_block
from ..upload import StoredDoc
from .base import ProviderDelta, ProviderDocHandle, ProviderError, Usage, page_marked_text, parse_duration


def _usage(u: dict[str, Any] | None) -> Usage | None:
    if not u:
        return None
    prompt_details = u.get("prompt_tokens_details") or {}
    completion_details = u.get("completion_tokens_details") or {}
    reasoning = completion_details.get("reasoning_tokens") or 0
    completion = u.get("completion_tokens", 0)
    return Usage(
        input=u.get("prompt_tokens", 0),
        cached_input=prompt_details.get("cached_tokens") or 0,
        output=max(completion - reasoning, 0),
        thinking=reasoning,
    )


class OpenAICompatProvider:
    name = "openai_compat"
    # Whether structured answers can stream. Groq: "Streaming ... not supported with Structured Outputs".
    stream_structured_output = True

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._docs: dict[str, StoredDoc] = {}
        self.base_url = settings.openai_compat_base_url
        self.api_key = settings.openai_compat_api_key
        self.model = settings.openai_compat_model
        self.fallback_model = settings.openai_compat_model

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle:
        self._docs[doc.doc_id] = doc
        return ProviderDocHandle(self.name, doc.doc_id, doc.sha256, {"pages": doc.page_count})

    # -- context ------------------------------------------------------------------------------
    def _context(self, handle: ProviderDocHandle, question: str, fixed_tokens: int) -> tuple[str, dict[str, Any]]:
        doc = self._docs[handle.doc_id]
        if not self.settings.retrieval_on(self.name):
            text = page_marked_text(doc)
            return text, {"retrieval": "off", "pages": list(range(1, doc.page_count + 1))}
        budget = max(self.settings.retrieval_max_prompt_tokens - fixed_tokens, 800)
        r = retrieval.retrieve(doc, question, budget)
        return r.text, {
            "retrieval": "bm25",
            "pages": r.pages,
            "chunks": r.chunks,
            "context_tokens_est": r.est_tokens,
            "prompt_budget": self.settings.retrieval_max_prompt_tokens,
        }

    def _messages(self, system: str, context: str, prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{DOC_START}\n{context}\n{DOC_END}\n\n{prompt}"},
        ]

    def _fixed_tokens(self, system: str, prompt: str, schema: dict[str, Any] | None) -> int:
        schema_chars = len(json.dumps(schema, separators=(",", ":"))) if schema else 0
        return (
            retrieval.estimate_tokens(system)
            + retrieval.estimate_tokens(prompt)
            + int(schema_chars / 3.2)  # JSON tokenizes denser than prose
            + 60  # delimiters, chat template
        )

    # -- HTTP ---------------------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extra_body(self, model: str) -> dict[str, Any]:
        return {}

    def _error(self, status: int, detail: str, headers: httpx.Headers) -> ProviderError:
        if status == 429:
            wait = parse_duration(headers.get("retry-after")) or parse_duration(headers.get("x-ratelimit-reset-tokens"))
            return ProviderError("RATE_LIMITED", detail, 429, retryable=True, retry_after=wait)
        if status in (500, 502, 503, 504):
            return ProviderError("UPSTREAM_BUSY", detail, status, retryable=True)
        if status in (401, 403):
            return ProviderError("UPSTREAM_AUTH", detail, status)
        if status == 400 and ("json_validate_failed" in detail or "generated json does not match" in detail.lower()):
            # Groq validates the model's output against the strict schema and 400s on a bad generation;
            # that is a sampling failure, so it is worth one more try (then the fallback model).
            return ProviderError("OUTPUT_INVALID", detail, 400, retryable=True, retry_after=0)
        if status == 400:
            return ProviderError("SCHEMA_REJECTED" if "schema" in detail.lower() else "UPSTREAM_ERROR", detail, 400)
        return ProviderError("UPSTREAM_ERROR", detail, status)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=self.settings.request_timeout_s + 15)

    async def _stream(self, body: dict[str, Any], meta: dict[str, Any]) -> AsyncIterator[ProviderDelta]:
        body = {**body, "stream": True, "stream_options": {"include_usage": True}}
        url = self.base_url.rstrip("/") + "/chat/completions"
        usage: Usage | None = None
        finish: str | None = None
        try:
            async with self._client() as client:
                async with client.stream("POST", url, json=body, headers=self._headers()) as resp:
                    if resp.status_code >= 400:
                        detail = (await resp.aread()).decode("utf-8", "replace")[:300]
                        raise self._error(resp.status_code, detail, resp.headers)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        chunk = json.loads(payload)
                        # Groq puts usage under x_groq.usage on the last chunk; OpenAI under usage.
                        usage = _usage(chunk.get("usage") or (chunk.get("x_groq") or {}).get("usage")) or usage
                        for choice in chunk.get("choices") or []:
                            if choice.get("finish_reason"):
                                finish = choice["finish_reason"]
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                yield ProviderDelta(text_delta=delta)
        except httpx.HTTPError as exc:
            raise ProviderError("UPSTREAM_ERROR", str(exc)[:300], None, retryable=True) from exc
        yield ProviderDelta(usage=usage, finish_reason=finish, meta=meta)

    async def _complete(self, body: dict[str, Any], meta: dict[str, Any]) -> AsyncIterator[ProviderDelta]:
        """Non-streamed call; the whole JSON arrives at once and goes through the same event pipeline."""
        url = self.base_url.rstrip("/") + "/chat/completions"
        started = time.perf_counter()
        try:
            async with self._client() as client:
                resp = await client.post(url, json=body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProviderError("UPSTREAM_ERROR", str(exc)[:300], None, retryable=True) from exc
        if resp.status_code >= 400:
            raise self._error(resp.status_code, resp.text[:300], resp.headers)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        meta = {
            **meta,
            "streamed": False,
            "upstream_ms": int((time.perf_counter() - started) * 1000),
            "remaining_tokens_per_minute": resp.headers.get("x-ratelimit-remaining-tokens"),
        }
        if content:
            yield ProviderDelta(text_delta=content)
        yield ProviderDelta(usage=_usage(data.get("usage")), finish_reason=choice.get("finish_reason"), meta=meta)

    # -- provider interface -------------------------------------------------------------------
    def structured_schema(self, schema: dict[str, Any] | None) -> dict[str, Any] | None:
        return schema

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
        schema = self.structured_schema(schema)
        prompt = question_block(question, lang, text_only=text_only, intent=intent)
        context, meta = self._context(doc, question, self._fixed_tokens(system, prompt, schema))
        use_model = model or self.model
        body: dict[str, Any] = {
            "model": use_model,
            "messages": self._messages(system, context, prompt),
            "max_tokens": max_output_tokens,
            "response_format": (
                {"type": "json_schema", "json_schema": {"name": "visual_answer", "schema": schema, "strict": True}}
                if schema
                else {"type": "json_object"}
            ),
            **self._extra_body(use_model),
        }
        gen = self._stream(body, meta) if self.stream_structured_output else self._complete(body, meta)
        async for d in gen:
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
        prompt = question_block(question, lang)
        context, meta = self._context(doc, question, self._fixed_tokens(system, prompt, None))
        use_model = model or self.model
        body = {
            "model": use_model,
            "messages": self._messages(system, context, prompt),
            "max_tokens": max_output_tokens,
            **self._extra_body(use_model),
        }
        async for d in self._stream(body, meta):
            yield d

    async def count_tokens(self, doc: ProviderDocHandle) -> int:
        # No tokenizer endpoint is standard across servers; estimate from the extracted text.
        d = self._docs.get(doc.doc_id)
        return retrieval.estimate_tokens(page_marked_text(d)) if d else 0
