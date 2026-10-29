"""FastAPI entry point."""

from fastapi import FastAPI

app = FastAPI(title="Arif Visual Answers")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
