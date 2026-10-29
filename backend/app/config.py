"""Settings loaded from the environment (and the repo-root .env)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # PROVIDER=gemini|groq (LLM_PROVIDER is the older name and still works; openai_compat|mock too).
    llm_provider: str = field(default_factory=lambda: os.getenv("PROVIDER") or os.getenv("LLM_PROVIDER") or "gemini")
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""), repr=False)
    model: str = field(default_factory=lambda: os.getenv("MODEL", "gemini-3.8-flash"))
    fallback_model: str = field(default_factory=lambda: os.getenv("FALLBACK_MODEL", "gemini-3.1-flash-lite"))
    thinking_level: str = field(default_factory=lambda: os.getenv("THINKING_LEVEL", "low"))
    media_resolution: str = field(default_factory=lambda: os.getenv("MEDIA_RESOLUTION", "medium"))
    schema_mode: str = field(default_factory=lambda: os.getenv("SCHEMA_MODE", "json"))
    max_output_tokens: int = field(default_factory=lambda: _int("MAX_OUTPUT_TOKENS", 4096))
    request_timeout_s: int = field(default_factory=lambda: _int("REQUEST_TIMEOUT_S", 45))
    enable_explicit_cache: bool = field(default_factory=lambda: _bool("ENABLE_EXPLICIT_CACHE"))
    prompt_version: str = field(default_factory=lambda: os.getenv("PROMPT_VERSION", "v2"))

    openai_compat_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8001/v1")
    )
    openai_compat_model: str = field(default_factory=lambda: os.getenv("OPENAI_COMPAT_MODEL", ""))
    openai_compat_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_COMPAT_API_KEY", ""), repr=False)

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""), repr=False)
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    groq_fallback_model: str = field(default_factory=lambda: os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b"))
    groq_base_url: str = field(default_factory=lambda: os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"))
    groq_max_output_tokens: int = field(default_factory=lambda: _int("GROQ_MAX_OUTPUT_TOKENS", 2400))
    groq_schema: str = field(default_factory=lambda: os.getenv("GROQ_SCHEMA", "union"))  # union | flat

    # Retrieval: send only the most relevant chunks. auto = on for groq/openai_compat, off for gemini
    # (which reads the whole PDF through the Files API).
    retrieval: str = field(default_factory=lambda: os.getenv("RETRIEVAL", "auto"))
    retrieval_max_prompt_tokens: int = field(default_factory=lambda: _int("RETRIEVAL_MAX_PROMPT_TOKENS", 5800))
    rate_limit_max_wait_s: int = field(default_factory=lambda: _int("RATE_LIMIT_MAX_WAIT_S", 30))

    mock_llm: bool = field(default_factory=lambda: _bool("MOCK_LLM"))
    mock_delay_ms: int = field(default_factory=lambda: _int("MOCK_DELAY_MS", 30))
    mock_ttft_ms: int = field(default_factory=lambda: _int("MOCK_TTFT_MS", 400))
    log_raw_output: bool = field(default_factory=lambda: _bool("LOG_RAW_OUTPUT"))

    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 20))
    max_pages: int = field(default_factory=lambda: _int("MAX_PAGES", 60))
    max_questions_per_doc: int = field(default_factory=lambda: _int("MAX_QUESTIONS_PER_DOC", 50))
    rate_limit_ask: str = field(default_factory=lambda: os.getenv("RATE_LIMIT_ASK", "10/minute"))
    rate_limit_upload: str = field(default_factory=lambda: os.getenv("RATE_LIMIT_UPLOAD", "5/minute"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    )
    digits: str = field(default_factory=lambda: os.getenv("DIGITS", "latn"))

    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))))
    fixtures_dir: Path = field(default_factory=lambda: ROOT / "fixtures")
    frontend_dist: Path = field(default_factory=lambda: ROOT / "frontend" / "dist")

    @property
    def provider_name(self) -> str:
        return "mock" if self.mock_llm else self.llm_provider

    def retrieval_on(self, provider: str) -> bool:
        if self.retrieval in ("on", "1", "true"):
            return True
        if self.retrieval in ("off", "0", "false"):
            return False
        return provider in ("groq", "openai_compat")


def get_settings() -> Settings:
    return Settings()
