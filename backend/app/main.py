"""FastAPI entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .upload import DocStore, UploadError

log = logging.getLogger("arif")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = DocStore(settings)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.cleanup()

        async def hourly() -> None:
            while True:
                await asyncio.sleep(3600)
                store.cleanup()

        task = asyncio.create_task(hourly())
        yield
        task.cancel()

    app = FastAPI(title="Arif Visual Answers", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store

    @app.exception_handler(UploadError)
    async def upload_error(_: Request, exc: UploadError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/documents")
    async def upload_document(request: Request, file: UploadFile) -> dict:
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        doc = await asyncio.to_thread(store.add, data, file.filename or "document.pdf", file.content_type)
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
            return JSONResponse({"code": "NOT_FOUND", "message": "Unknown document."}, status_code=404)
        page = doc.page(n)
        if page is None:
            return JSONResponse({"code": "NOT_FOUND", "message": "Unknown page."}, status_code=404)
        return JSONResponse({"page": n, "text": page.visible_text, "has_text": bool(page.visible_text.strip())})

    return app


app = create_app()
