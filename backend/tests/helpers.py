import json
from pathlib import Path

from .conftest import PDFS, upload

ANSWERS = Path(__file__).resolve().parents[2] / "fixtures" / "answers"
Q1_EN = "What is chain-of-thought prompting and how is it different from standard prompting?"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    return events


def ask(client, doc_id, question, lang="en", fixture=None, endpoint="/api/ask", **extra):
    headers = {"X-Mock-Fixture": fixture} if fixture else {}
    r = client.post(endpoint, json={"doc_id": doc_id, "question": question, "lang": lang, **extra}, headers=headers)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def cot_doc(client) -> str:
    return upload(client, PDFS / "cot.pdf").json()["doc_id"]


def names(events):
    return [e[0] for e in events]


def components(events):
    return [d for n, d in events if n == "COMPONENT"]


def dropped(events):
    return [d for n, d in events if n == "COMPONENT_DROPPED"]


def text_of(events):
    return "".join(d["delta"] for n, d in events if n == "TEXT_MESSAGE_CONTENT")
