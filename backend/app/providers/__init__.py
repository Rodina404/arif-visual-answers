"""Provider selection: PROVIDER=gemini|groq|openai_compat|mock; MOCK_LLM=1 forces mock.

A request may name a provider (the UI's Gemini/Groq switch). With MOCK_LLM=1 the mock answers "as"
that provider so the switch, labels and recorded live fixtures can be demoed offline.
"""

from ..config import Settings
from .base import LLMProvider

SELECTABLE = ("gemini", "groq")


def available(settings: Settings) -> dict[str, bool]:
    """Which providers can serve a request right now."""
    if settings.mock_llm:
        return {name: True for name in SELECTABLE}
    return {"gemini": bool(settings.gemini_api_key), "groq": bool(settings.groq_api_key)}


def get_provider(settings: Settings, name: str | None = None) -> LLMProvider:
    name = name or settings.llm_provider
    if settings.mock_llm or name == "mock":
        from .mock import MockProvider

        return MockProvider(settings, as_provider=name if name in SELECTABLE else "gemini")
    if name == "openai_compat":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(settings)
    if name == "groq":
        from .groq import GroqProvider

        return GroqProvider(settings)
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings)
    raise ValueError(f"unknown PROVIDER {name!r}")
