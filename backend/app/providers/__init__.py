"""Provider selection: LLM_PROVIDER=gemini|openai_compat|mock; MOCK_LLM=1 forces mock."""

from ..config import Settings
from .base import LLMProvider


def get_provider(settings: Settings) -> LLMProvider:
    name = settings.provider_name
    if name == "mock":
        from .mock import MockProvider

        return MockProvider(settings)
    if name == "openai_compat":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(settings)
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(settings)
    raise ValueError(f"unknown LLM_PROVIDER {name!r}")
