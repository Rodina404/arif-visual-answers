"""Provider-neutral interface so Gemini can be swapped for a self-hosted model."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..upload import StoredDoc


@dataclass
class Usage:
    input: int = 0
    cached_input: int = 0
    output: int = 0
    thinking: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.thinking


@dataclass
class ProviderDelta:
    text_delta: str | None = None
    usage: Usage | None = None
    finish_reason: str | None = None
    meta: dict[str, Any] | None = None  # e.g. retrieval details, shown in the metrics drawer


@dataclass
class ProviderDocHandle:
    provider: str
    doc_id: str
    sha256: str
    data: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after  # seconds, from a 429's retry-after header


def parse_duration(value: str | None) -> float | None:
    """'7.66s', '2m59.56s', '120', '850ms' -> seconds."""
    if not value:
        return None
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    import re

    total = 0.0
    matched = False
    for num, unit in re.findall(r"([\d.]+)(ms|h|m|s)", value):
        matched = True
        total += float(num) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if matched else None


class LLMProvider(Protocol):
    name: str
    model: str  # primary model id, shown in metrics
    fallback_model: str  # used after retries on 429/503

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle: ...

    def stream_structured(
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
    ) -> AsyncIterator[ProviderDelta]: ...

    def stream_text(
        self,
        *,
        system: str,
        doc: ProviderDocHandle,
        question: str,
        lang: str,
        max_output_tokens: int,
        model: str | None = None,
    ) -> AsyncIterator[ProviderDelta]: ...

    async def count_tokens(self, doc: ProviderDocHandle) -> int: ...


def page_marked_text(doc: StoredDoc) -> str:
    """Visible text with page markers, for providers that can't read PDFs."""
    return "\n\n".join(f"[[page {p.number}]]\n{p.visible_text}" for p in doc.pages)
