"""Groq: OpenAI-compatible API with strict structured outputs.

- Strict `json_schema` (every property required, optional ones nullable) is supported by
  openai/gpt-oss-120b, openai/gpt-oss-20b and qwen/qwen3.8-27b, but not together with streaming,
  so structured answers are one non-streamed call. The plain-text "Before" answer does stream.
- The free tier is ~8K tokens per minute while cot.pdf is ~24K tokens, so retrieval is on by
  default (RETRIEVAL=auto) and the prompt is kept under RETRIEVAL_MAX_PROMPT_TOKENS.
- 429s carry `retry-after` (seconds); the stream layer waits that long, then tries the fallback model,
  which has its own per-model token bucket.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..catalog import strict_schema
from ..config import Settings
from .openai_compat import OpenAICompatProvider

_EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high"}


class GroqProvider(OpenAICompatProvider):
    name = "groq"
    stream_structured_output = False

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport)
        self.base_url = settings.groq_base_url
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.fallback_model = settings.groq_fallback_model
        self.max_output_tokens = settings.groq_max_output_tokens

    def structured_schema(self, schema: dict[str, Any] | None) -> dict[str, Any] | None:
        # Groq gets its own strict schema (enforced while decoding), except when the caller asks for plain
        # JSON mode (schema=None): the retry after Groq rejected its own output (`json_validate_failed`).
        return strict_schema(self.settings.groq_schema) if schema is not None else None

    def _extra_body(self, model: str) -> dict[str, Any]:
        if model.startswith("openai/gpt-oss"):
            # Reasoning tokens count against the per-minute budget; keep them small.
            return {"reasoning_effort": _EFFORT.get(self.settings.thinking_level, "low")}
        return {}
