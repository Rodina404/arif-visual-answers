"""FastAPI entry point."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import retrieval, security
from .cache import AnswerCache
from .config import Settings, get_settings
from .metrics import MetricsLog
from .ocr import ocr_pages
from .providers import SELECTABLE, available, get_provider
from .providers.base import LLMProvider, ProviderDocHandle, ProviderError
from .small_llm import SmallLLM
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


_CLIENT_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def client_id(request: Request) -> str:
    """The browser's random id (X-Client-Id). Documents are listed and deleted only by their owner."""
    value = request.headers.get("x-client-id", "")
    return value if _CLIENT_ID.match(value) else ""


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
    small = SmallLLM(settings, cache)
    ocr_tasks: dict[str, asyncio.Task[None]] = {}
    try:
        index = json.loads((settings.fixtures_dir / "answers" / "index.json").read_text(encoding="utf-8"))
        demo_shas = {sha for sha, slug in index.get("docs", {}).items() if slug == "cot"}
    except (OSError, ValueError):
        demo_shas = set()
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
        doc = await asyncio.to_thread(
            store.add, data, file.filename or "document.pdf", file.content_type, client_id(request)
        )
        if doc.needs_ocr:
            # Scanned pages: recognise their text in the background; questions wait for it.
            doc.status = "reading"
            store.save(doc)
            ocr_tasks[doc.doc_id] = asyncio.create_task(_ocr(doc, data))
        else:
            preparing[(default_name, doc.doc_id)] = asyncio.create_task(_prepare(doc, default_name))
        return doc_payload(doc)

    def doc_payload(doc: StoredDoc) -> dict[str, Any]:
        return {
            "doc_id": doc.doc_id,
            "pages": doc.page_count,
            "sha256": doc.sha256,
            "filename": doc.filename,
            "status": doc.status,
            "language": doc.language,
            "is_demo": doc.sha256 in demo_shas,
            "ocr_pages": [p.number for p in doc.pages if p.ocr],
            "created_at": doc.created_at,
            "warnings": doc.warnings(),
        }

    async def _ocr(doc: StoredDoc, data: bytes) -> None:
        try:
            texts = await asyncio.to_thread(ocr_pages, data, doc.needs_ocr)
            store.apply_ocr(doc, texts)
            retrieval.forget(doc.sha256)
            log.info("doc %s: OCR on %d pages", doc.doc_id, len(texts))
        except Exception as exc:  # the document stays usable, just without text on those pages
            log.warning("OCR failed for %s: %s", doc.doc_id, exc)
            doc.status = "ready"
            store.save(doc)

    async def ready(doc: StoredDoc) -> None:
        task = ocr_tasks.get(doc.doc_id)
        if task is not None:
            await task

    @app.get("/api/documents")
    async def list_documents(request: Request) -> list[dict[str, Any]]:
        owner = client_id(request)
        return [doc_payload(d) for d in store.list(owner)] if owner else []

    @app.get("/api/documents/{doc_id}", response_model=None)
    async def get_document(doc_id: str) -> dict[str, Any] | JSONResponse:
        doc = store.get(doc_id)
        return doc_payload(doc) if doc else _error("NOT_FOUND", "Unknown document.", 404)

    @app.delete("/api/documents/{doc_id}", response_model=None)
    async def delete_document(request: Request, doc_id: str) -> dict[str, Any] | JSONResponse:
        doc = store.get(doc_id)
        if doc is None or doc.owner != client_id(request):
            return _error("NOT_FOUND", "Unknown document.", 404)
        task = ocr_tasks.pop(doc_id, None)
        if task is not None:
            task.cancel()
        for key in [k for k in handles if k[1] == doc_id]:
            handles.pop(key, None)
        return {"deleted": doc_id} if store.delete(doc_id) else _error("NOT_FOUND", "Unknown document.", 404)

    @app.get("/api/documents/{doc_id}/suggestions", response_model=None)
    async def suggestions(doc_id: str, lang: Literal["ar", "en"] = "en") -> dict[str, Any] | JSONResponse:
        doc = store.get(doc_id)
        if doc is None:
            return _error("NOT_FOUND", "Unknown document.", 404)
        await ready(doc)
        return {"questions": await small.suggestions(doc, lang), "generated": small.enabled}

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
        await ready(doc)
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
            small=small,
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
