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


@dataclass
class ProviderDocHandle:
    provider: str
    doc_id: str
    sha256: str
    data: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, code: str, message: str, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable


class LLMProvider(Protocol):
    name: str

    async def prepare_document(self, doc: StoredDoc) -> ProviderDocHandle: ...

    def stream_structured(
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
