"""Proposed actions and the local tasks store.

The agent's tools only ever write *proposals*. A task exists only after the user who asked clicks
Approve (POST /api/actions/{id}/approve); a draft message is only ever saved, never sent.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Proposal:
    proposal_id: str
    client: str
    doc_id: str
    filename: str
    action: dict[str, Any]  # a catalog ProposedAction (kind, title, owner, ..., citation, flags)
    status: str  # proposed | approved | rejected
    created: float


class ActionStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY, client TEXT, doc_id TEXT, filename TEXT, action TEXT, status TEXT, created REAL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, client TEXT, kind TEXT, record TEXT, created REAL
            );
            """
        )
        self._db.commit()

    @staticmethod
    def new_id() -> str:
        return "p" + uuid.uuid4().hex[:12]

    def propose(self, proposal: Proposal) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal.proposal_id,
                    proposal.client,
                    proposal.doc_id,
                    proposal.filename,
                    json.dumps(proposal.action, ensure_ascii=False),
                    proposal.status,
                    proposal.created,
                ),
            )
            self._db.commit()

    def get(self, proposal_id: str, client: str) -> Proposal | None:
        """A proposal is visible only to the browser whose question produced it."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, client, doc_id, filename, action, status, created FROM proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
        if not row or not client or row[1] != client:
            return None
        return Proposal(row[0], row[1], row[2], row[3], json.loads(row[4]), row[5], row[6])

    def _set_status(self, proposal_id: str, status: str) -> None:
        self._db.execute("UPDATE proposals SET status = ? WHERE id = ?", (status, proposal_id))

    def approve(self, p: Proposal, edits: dict[str, Any]) -> dict[str, Any]:
        """The only way a task (or a saved draft) comes into existence."""
        action = {**p.action, **{k: v for k, v in edits.items() if v is not None}}
        kind = "task" if action["kind"] == "create_task" else "draft"
        record: dict[str, Any] = {
            "id": ("t" if kind == "task" else "d") + uuid.uuid4().hex[:12],
            "proposal_id": p.proposal_id,
            "doc_id": p.doc_id,
            "filename": p.filename,
            "title": action["title"],
            "citation": action.get("citation"),
            "flags": action.get("flags", []),
            "edited": any(edits.get(k) not in (None, p.action.get(k)) for k in edits),
            "approved_at": time.time(),
        }
        if kind == "task":
            record.update(owner=action.get("owner") or "", due_date=action.get("due_date"))
        else:
            record.update(to=action.get("to") or "", body=action.get("body") or "", sent=False)
        with self._lock:
            self._set_status(p.proposal_id, "approved")
            self._db.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (record["id"], p.client, kind, json.dumps(record, ensure_ascii=False), record["approved_at"]),
            )
            self._db.commit()
        return {"kind": kind, **record}

    def reject(self, p: Proposal) -> None:
        with self._lock:
            self._set_status(p.proposal_id, "rejected")
            self._db.commit()

    def items(self, client: str) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, record FROM tasks WHERE client = ? ORDER BY created", (client,)
            ).fetchall()
        out: dict[str, list[dict[str, Any]]] = {"tasks": [], "drafts": []}
        for kind, record in rows:
            out["tasks" if kind == "task" else "drafts"].append(json.loads(record))
        return out

    def delete(self, item_id: str, client: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM tasks WHERE id = ? AND client = ?", (item_id, client))
            self._db.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._db.close()
