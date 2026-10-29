"""Self-hosted models (vLLM, Ollama, llama.cpp) through an OpenAI-compatible /chat/completions API.

The PDF never leaves the server: the model receives the extracted visible text with page markers.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import Settings
from ..prompts import DOC_END, DOC_START, question_block
from ..upload import StoredDoc
from .base import ProviderDelta, ProviderDocHandle, ProviderError, Usage, page_marked_text


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._texts: dict[str, str] = {}

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle:
        self._texts[doc.doc_id] = page_marked_text(doc)
        return ProviderDocHandle(self.name, doc.doc_id, doc.sha256, {"chars": len(self._texts[doc.doc_id])})

    def _messages(self, system: str, doc: ProviderDocHandle, prompt: str) -> list[dict[str, str]]:
        text = self._texts.get(doc.doc_id, "")
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{DOC_START}\n{text}\n{DOC_END}\n\n{prompt}"},
        ]

    async def _stream(self, body: dict[str, Any]) -> AsyncIterator[ProviderDelta]:
        headers = {"Content-Type": "application/json"}
        if self.settings.openai_compat_api_key:
            headers["Authorization"] = f"Bearer {self.settings.openai_compat_api_key}"
        body = {
            **body,
            "model": self.settings.openai_compat_model,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        url = self.settings.openai_compat_base_url.rstrip("/") + "/chat/completions"
        usage: Usage | None = None
        finish: str | None = None
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self.settings.request_timeout_s) as client:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        detail = (await resp.aread()).decode("utf-8", "replace")[:300]
                        raise ProviderError(
                            "UPSTREAM_BUSY" if resp.status_code in (429, 503) else "UPSTREAM_ERROR",
                            detail,
                            resp.status_code,
                            retryable=resp.status_code in (429, 503),
                        )
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        chunk = json.loads(payload)
                        if chunk.get("usage"):
                            u = chunk["usage"]
                            details = u.get("prompt_tokens_details") or {}
                            usage = Usage(
                                input=u.get("prompt_tokens", 0),
                                cached_input=details.get("cached_tokens", 0),
                                output=u.get("completion_tokens", 0),
                            )
                        for choice in chunk.get("choices") or []:
                            if choice.get("finish_reason"):
                                finish = choice["finish_reason"]
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                yield ProviderDelta(text_delta=delta)
        except httpx.HTTPError as exc:
            raise ProviderError("UPSTREAM_ERROR", str(exc)[:300], None, retryable=True) from exc
        yield ProviderDelta(usage=usage, finish_reason=finish)

    async def stream_structured(
        self,
        *,
        system: str,
        doc: ProviderDocHandle,
        question: str,
        schema: dict[str, Any],
        lang: str,
        max_output_tokens: int,
        model: str | None = None,
        text_only: bool = False,
        intent: str | None = None,
    ) -> AsyncIterator[ProviderDelta]:
        body = {
            "messages": self._messages(system, doc, question_block(question, lang, text_only=text_only, intent=intent)),
            "max_tokens": max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "visual_answer", "schema": schema, "strict": True},
            },
        }
        async for d in self._stream(body):
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
        body = {
            "messages": self._messages(system, doc, question_block(question, lang)),
            "max_tokens": max_output_tokens,
        }
        async for d in self._stream(body):
            yield d

    async def count_tokens(self, doc: ProviderDocHandle) -> int:
        # No tokenizer endpoint is standard across servers; ~4 characters per token is a fair estimate.
        return len(self._texts.get(doc.doc_id, "")) // 4
