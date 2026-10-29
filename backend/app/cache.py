"""SQLite answer cache: a repeated question replays its final validated events immediately."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .grounding import normalize


def cache_key(*, sha256: str, question: str, lang: str, model: str, prompt_version: str, mode: str) -> str:
    raw = "\x1f".join([sha256, normalize(question), lang, model, prompt_version, mode])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AnswerCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, events TEXT, created REAL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT, created REAL)")
        self._db.commit()

    def get(self, key: str) -> list[tuple[str, dict[str, Any]]] | None:
        with self._lock:
            row = self._db.execute("SELECT events FROM answers WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return [(e, d) for e, d in json.loads(row[0])]

    def put(self, key: str, events: list[tuple[str, dict[str, Any]]]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO answers VALUES (?, ?, ?)",
                (key, json.dumps(events, ensure_ascii=False), time.time()),
            )
            self._db.commit()

    def get_kv(self, key: str) -> Any | None:
        """Small cached values (translations, suggested questions)."""
        with self._lock:
            row = self._db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_kv(self, key: str, value: Any) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO kv VALUES (?, ?, ?)", (key, json.dumps(value, ensure_ascii=False), time.time())
            )
            self._db.commit()

    def close(self) -> None:
        self._db.close()
