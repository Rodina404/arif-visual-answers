"""FastAPI entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import security
from .cache import AnswerCache
from .config import Settings, get_settings
from .metrics import MetricsLog
from .providers import SELECTABLE, available, get_provider
from .providers.base import LLMProvider, ProviderDocHandle, ProviderError
from .stream import AskContext, TextRun, VisualRun, sse
from .upload import DocStore, StoredDoc, UploadError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("arif")


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_id: str = Field(max_length=64)
    question: str = Field(min_length=1, max_length=500)
    lang: Literal["ar", "en"] = "ar"
    text_only: bool = False
    provider: Literal["gemini", "groq"] | None = None  # the UI's provider switch; default is PROVIDER


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = DocStore(settings)
    default_name = settings.llm_provider
    providers: dict[str, LLMProvider] = {}

    def provider_for(name: str | None) -> LLMProvider:
        name = name or default_name
        if name not in providers:
            providers[name] = get_provider(settings, name)
        return providers[name]

    provider = provider_for(None)
    cache = AnswerCache(settings.data_dir / "cache.sqlite")
    metrics = MetricsLog()
    # (provider name, doc_id) -> handle; each provider prepares a document its own way.
    handles: dict[tuple[str, str], ProviderDocHandle] = {}
    preparing: dict[tuple[str, str], asyncio.Task[ProviderDocHandle]] = {}
    limiter = Limiter(key_func=get_remote_address)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.cleanup()

        async def hourly() -> None:
            while True:
                await asyncio.sleep(3600)
                store.cleanup()

        task = asyncio.create_task(hourly())
        log.info(
            "provider=%s model=%s schema_mode=%s retrieval=%s",
            default_name,
            provider.model,
            settings.schema_mode,
            settings.retrieval,
        )
        yield
        task.cancel()
        cache.close()

    app = FastAPI(title="Arif Visual Answers", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.store = store
    app.state.cache = cache
    app.state.provider = provider
    security.install(app, settings)
    app.state.limiter = limiter

    async def _prepare(doc: StoredDoc, name: str) -> ProviderDocHandle:
        p = provider_for(name)
        handle = await p.prepare_document(doc)
        handles[(name, doc.doc_id)] = handle
        store.save(doc)
        try:
            doc.token_count = await p.count_tokens(handle)
            log.info("doc %s: %s pages, %s tokens (count_tokens)", doc.doc_id, doc.page_count, doc.token_count)
        except Exception as exc:  # token counting is informational only
            log.warning("count_tokens failed: %s", exc)
        return handle

    async def handle_for(doc: StoredDoc, name: str) -> ProviderDocHandle:
        key = (name, doc.doc_id)
        if key in handles:
            return handles[key]
        task = preparing.get(key)
        if task is None or (task.done() and task.exception() is not None):
            task = preparing[key] = asyncio.create_task(_prepare(doc, name))
        return await task

    @app.exception_handler(UploadError)
    async def upload_error(_: Request, exc: UploadError) -> JSONResponse:
        return _error(exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({str(e["loc"][-1]) for e in exc.errors()})
        return _error("INVALID_REQUEST", f"Invalid request: {', '.join(fields)}", 422)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    async def public_config() -> dict[str, Any]:
        ok = available(settings)
        models = {
            "gemini": settings.model,
            "groq": settings.groq_model,
        }
        return {
            "provider": default_name if default_name in SELECTABLE else "gemini",
            "providers": [{"name": n, "model": models[n], "available": ok[n]} for n in SELECTABLE],
            "model": provider.model,
            "digits": settings.digits,
            "mock": settings.mock_llm,
            "max_upload_mb": settings.max_upload_mb,
            "max_pages": settings.max_pages,
        }

    @app.post("/api/documents")
    @limiter.limit(lambda: settings.rate_limit_upload)
    async def upload_document(request: Request, file: UploadFile) -> dict[str, Any]:
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        doc = await asyncio.to_thread(store.add, data, file.filename or "document.pdf", file.content_type)
        preparing[(default_name, doc.doc_id)] = asyncio.create_task(_prepare(doc, default_name))
        return {
            "doc_id": doc.doc_id,
            "pages": doc.page_count,
            "sha256": doc.sha256,
            "filename": doc.filename,
            "warnings": doc.warnings(),
        }

    @app.get("/api/documents/{doc_id}/pages/{n}")
    async def page_text(doc_id: str, n: int) -> JSONResponse:
        doc = store.get(doc_id)
        if doc is None:
            return _error("NOT_FOUND", "Unknown document.", 404)
        page = doc.page(n)
        if page is None:
            return _error("NOT_FOUND", "Unknown page.", 404)
        return JSONResponse({"page": n, "text": page.visible_text, "has_text": bool(page.visible_text.strip())})

    async def _start(request: Request, body: AskRequest) -> AskContext | JSONResponse:
        doc = store.get(body.doc_id)
        if doc is None:
            return _error("NOT_FOUND", "Unknown document. Please upload it again.", 404)
        if doc.questions_asked >= settings.max_questions_per_doc:
            return _error("QUESTION_LIMIT", "This document has reached its question limit.", 429)
        name = body.provider or default_name
        if not available(settings).get(name, name == default_name):
            return _error("PROVIDER_UNAVAILABLE", f"{name} is not configured (missing API key).", 400)
        doc.questions_asked += 1
        p = provider_for(name)
        try:
            handle = await handle_for(doc, name)
        except ProviderError as exc:
            return _error(exc.code, "The model provider could not read the document.", 502)
        mock = p.name == "mock"
        forced = request.headers.get("x-mock-fixture") if mock else None
        # Tests can bypass the answer cache to see streaming; never honoured outside mock mode.
        no_cache = mock and request.headers.get("x-no-cache") == "1"
        return AskContext(
            settings=settings,
            provider=p,
            doc=doc,
            handle=handle,
            question=body.question.strip(),
            lang=body.lang,
            cache=cache,
            metrics=metrics,
            text_only=body.text_only,
            mock_fixture=forced,
            no_cache=no_cache,
        )

    def _stream(events: AsyncIterator[tuple[str, dict[str, Any]]]) -> StreamingResponse:
        async def gen() -> AsyncIterator[str]:
            async for name, data in events:
                yield sse(name, data)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/ask", response_model=None)
    @limiter.limit(lambda: settings.rate_limit_ask)
    async def ask(request: Request, body: AskRequest) -> StreamingResponse | JSONResponse:
        ctx = await _start(request, body)
        if isinstance(ctx, JSONResponse):
            return ctx
        return _stream(VisualRun(ctx).events())

    @app.post("/api/ask_text", response_model=None)
    @limiter.limit(lambda: settings.rate_limit_ask)
    async def ask_text(request: Request, body: AskRequest) -> StreamingResponse | JSONResponse:
        ctx = await _start(request, body)
        if isinstance(ctx, JSONResponse):
            return ctx
        return _stream(TextRun(ctx).events())

    @app.get("/api/metrics/summary")
    async def metrics_summary() -> dict[str, Any]:
        return metrics.summary()

    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA from the same origin (strict CSP). Unknown paths fall back to index.html."""
    index = dist / "index.html"
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    async def spa(path: str) -> FileResponse | JSONResponse:
        if path.startswith("api/"):
            return _error("NOT_FOUND", "Not found.", 404)
        if not index.exists():
            return _error("NO_FRONTEND", "Frontend not built. Run `make build`.", 404)
        target = (dist / path).resolve()
        if path and target.is_file() and target.is_relative_to(root):
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if path.startswith("assets/") else {}
            return FileResponse(target, headers=headers)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
