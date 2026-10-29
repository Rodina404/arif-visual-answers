"""Draws docs/images/architecture.svg (the README's architecture and data-flow diagram).

Run: python docs/images/make_architecture.py
"""

from pathlib import Path

NL = chr(10)
W, H = 1440, 1240
FONT = "Segoe UI, system-ui, -apple-system, Helvetica, Arial, sans-serif"
out: list[str] = []

STYLES = {
    "plain": ("#ffffff", "#cbd5e1", "#0f172a"),
    "check": ("#fff7ed", "#c2410c", "#9a3412"),
    "agent": ("#f5f3ff", "#a78bfa", "#5b21b6"),
    "store": ("#ecfdf5", "#34d399", "#065f46"),
    "ext": ("#f8fafc", "#94a3b8", "#334155"),
}
COLORS = {"data": "#334155", "sse": "#6d28d9", "cond": "#64748b", "prop": "#c2410c", "store": "#059669"}


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, t, size=12, color="#475569", weight=400, anchor="start", family=None):
    fam = f' font-family="{family}"' if family else ""
    out.append(
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" '
        f'text-anchor="{anchor}"{fam}>{esc(t)}</text>'
    )


def box(x, y, w, h, title, lines, style="plain", dashed=False, mono=()):
    fill, stroke, title_color = STYLES[style]
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dash}/>')
    text(x + 14, y + 24, title, 14, title_color, 700)
    for i, line in enumerate(lines):
        text(x + 14, y + 45 + i * 16, line, 11.5, "#475569", 400, family="Consolas, Menlo, monospace" if i in mono else None)


def arrow(points, color="data", label=None, lx=None, ly=None, dashed=False, anchor="middle", lcolor=None):
    c = COLORS[color]
    d = "M" + " L".join(f"{x} {y}" for x, y in points)
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    out.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2"{dash} marker-end="url(#m-{color})"/>')
    if label:
        text(lx, ly, label, 11, lcolor or c, 600, anchor)


def lane(y, h, label):
    out.append(f'<rect x="248" y="{y}" width="1180" height="{h}" rx="16" fill="#f8fafc" stroke="#e2e8f0"/>')
    text(266, y + 24, label, 13, "#334155", 700)


# --- frame -----------------------------------------------------------------------------------
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">')
out.append("<defs>")
for name, c in COLORS.items():
    out.append(
        f'<marker id="m-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'
    )
out.append("</defs>")
out.append(f'<rect width="{W}" height="{H}" rx="18" fill="#ffffff"/>')
text(24, 36, "Arif Visual Answers: architecture and data flow", 20, "#0f172a", 700)
text(24, 56, "Three request paths (upload, ask, approve). Ask splits into the visual-answer path and the agent path.", 12.5, "#64748b")

# --- browser ---------------------------------------------------------------------------------
out.append('<rect x="20" y="76" width="212" height="996" rx="14" fill="#6d28d9"/>')
text(126, 106, "Browser", 17, "#ffffff", 700, "middle")
browser = [
    ("React 19 · Vite · TypeScript", 0),
    ("Tailwind 4 · RTL (ar) / LTR (en)", 0),
    ("", 0),
    ("PDF upload  → ①", 1),
    ("", 0),
    ("Question  → ②", 1),
    ("SSE reader (fetch stream)", 0),
    ("Zod re-validates every props", 0),
    ("Renderers: Recharts, KaTeX,", 0),
    ("comparison, steps, quiz …", 0),
    ("Execution audit drawer", 0),
    ("", 0),
    ("Action card: Approve /", 0),
    ("Edit / Reject  → ③", 1),
    ("Tasks tab", 0),
    ("", 0),
    ("X-Client-Id (random, per", 0),
    ("browser) on every request", 0),
]
for i, (line, bold) in enumerate(browser):
    text(36, 140 + i * 19, line, 12, "#ffffff" if bold else "#ede9fe", 700 if bold else 400)

# --- ① upload ---------------------------------------------------------------------------------
lane(76, 190, "① UPLOAD   POST /api/documents")
box(266, 112, 200, 140, "Validate", ["MIME type + %PDF magic", "≤ 20 MB · ≤ 60 pages", "encrypted → rejected", "rate limit (slowapi)"])
box(494, 112, 250, 140, "Parse · pdfplumber", ["visible text only", "hidden = white · tiny · off-page", "→ HIDDEN_TEXT_DETECTED", "Arabic visual → logical order", "(Chromium / Word PDFs)"], "check")
box(772, 112, 200, 140, "OCR · RapidOCR", ["only pages without text", "local ONNX, background task", "status: reading → ready", "skipped if all pages have text"], dashed=True)
box(1000, 112, 200, 140, "DocStore", ["memoised by SHA-256", "per-hash parse lock", "owner = X-Client-Id", "kept 48 h · data/uploads"], "store")
box(1228, 112, 186, 140, "Provider prep", ["Gemini: Files API upload", "+ count_tokens", "Groq: text stays local", "suggested questions", "(gpt-oss-20b, cached)"])
arrow([(232, 182), (264, 182)])
arrow([(466, 182), (492, 182)])
arrow([(744, 182), (770, 182)], "cond", dashed=True)
arrow([(972, 182), (998, 182)])
arrow([(1200, 182), (1226, 182)])

# --- ② ask -------------------------------------------------------------------------------------
lane(282, 610, "② ASK   POST /api/ask   →   text/event-stream (AG-UI event names)")
box(266, 520, 196, 152, "Router", ["text_only → visual", "agent.wants_agent(q):", "decisions · owners ·", "action items · tasks ·", "draft / email", "+ Groq key → agent"])
arrow([(232, 596), (264, 596)])

text(500, 328, "VISUAL ANSWER PATH  (default)", 11.5, "#6d28d9", 700)
box(500, 336, 180, 154, "Answer cache", ["SQLite cache.sqlite", "key: sha · question · lang", "· model · prompt v · mode", "hit → replay events", "< 300 ms · $0"], "store")
box(714, 336, 218, 154, "Retrieval · BM25", ["~600-char chunks", "caption + table kept together", "budget ≈ 5K prompt tokens", "on for Groq (RETRIEVAL=auto)", "ar↔en query: gpt-oss-20b", "Gemini: whole PDF instead"])
box(956, 336, 222, 154, "LLM provider", ["Gemini 3.8 Flash · stream", "Groq gpt-oss-120b · strict JSON", "self-hosted · OpenAI API", "429/503 → wait retry-after", "→ retry → fallback model", "(only before any output)"])
box(1202, 336, 212, 154, "Stream → checks", ["jiter partial JSON → text deltas", "each component:", "1 Pydantic + fit_limits", "2 quote ≥ 90 · ±1 page,", "  numbers in quote AND page", "3 ≤ 3 visuals · quiz last ·", "  chart → table if < 3 points"], "check")
arrow([(462, 548), (480, 548), (480, 410), (498, 410)], "data")
text(486, 470, "visual", 10.5, "#334155", 600)
arrow([(680, 410), (712, 410)])
text(696, 402, "miss", 10, "#334155", 600, "middle")
arrow([(932, 410), (954, 410)])
arrow([(1178, 410), (1200, 410)])
# SSE back to the browser (visual)
arrow([(1308, 490), (1308, 508), (234, 508)], "sse")
text(640, 503, "SSE: TEXT_MESSAGE_* · COMPONENT_PLANNED · COMPONENT · COMPONENT_DROPPED · WARNING · METRICS · RUN_FINISHED", 11, "#6d28d9", 600)
arrow([(595, 490), (595, 506)], "store", dashed=True)
text(588, 501, "hit", 10, "#059669", 700, "end")

text(500, 566, "AGENT PATH  (Groq tool calling · never cached)", 11.5, "#6d28d9", 700)
box(500, 578, 180, 196, "Sentences", ["visible text → s1, s2, …", "each with page + quote", "small doc → sent whole", "large doc → via search", "", "untrusted-data markers", "around the document"], "agent")
box(704, 578, 212, 196, "Tool loop", ["Groq gpt-oss-120b", "tool_choice = auto", "≤ 4 steps · timeout each", "429 → wait → fallback", "asked action missing →", "  nudge once", "emits TOOL_CALL_START /", "  TOOL_CALL_RESULT"], "agent")
box(956, 578, 222, 196, "Tools", ["search_document(query)", "  BM25 over sentences", "extract_items(kind)", "  strict JSON · sentence ids", "create_task(…)   → proposal", "draft_message(…) → proposal", "  (nothing is ever sent)"], "agent", mono=(0, 2, 4, 5))
box(1202, 578, 212, 196, "Cards + checks", ["server builds decision_cards,", "task_cards, action_card", "same Pydantic + grounding:", "owner & date in sentence", "flags: FROM_HIDDEN_TEXT ·", "UNVERIFIED_SOURCE ·", "NOT_REQUESTED", "missing tasks → [server]"], "check")
arrow([(462, 640), (480, 640), (480, 676), (498, 676)], "data")
text(486, 664, "agent", 10.5, "#334155", 600)
arrow([(680, 676), (702, 676)])
arrow([(916, 640), (954, 640)], "data")
text(935, 632, "call", 10, "#334155", 600, "middle")
arrow([(954, 712), (918, 712)], "data")
text(935, 728, "result", 10, "#334155", 600, "middle")
arrow([(810, 774), (810, 792), (1250, 792), (1250, 776)], "data")
text(930, 787, "final reply (or step limit)", 10.5, "#334155", 600, "middle")
# SSE back to the browser (agent)
arrow([(1390, 774), (1390, 860), (234, 860)], "sse")
text(300, 855, "SSE: RUN_STARTED{agent} · TOOL_CALL_START / RESULT · TEXT_MESSAGE_* · COMPONENT (cards) · METRICS{tools}", 11, "#6d28d9", 600)
# Router fallback
text(272, 700, "no Groq key →", 10.5, "#64748b", 600)
text(272, 714, "visual + AGENT_UNAVAILABLE", 10.5, "#64748b", 600)

# --- ③ approve ----------------------------------------------------------------------------------
lane(908, 148, "③ APPROVE   the only path that creates a task or saves a draft")
box(560, 944, 290, 100, "POST /api/actions/{id}/approve | reject", ["owner must equal X-Client-Id, else 404", "already decided → 409", "edits: title · owner · due · to · body"])
box(956, 944, 222, 100, "ActionStore", ["agent.sqlite", "proposed → approved | rejected"], "store")
box(1202, 944, 212, 100, "Tasks store", ["tasks + drafts (sent = false)", "GET /api/tasks · DELETE", "→ Tasks tab"], "store")
arrow([(232, 994), (558, 994)], "data")
text(395, 986, "user clicks Approve / Edit / Reject", 11, "#334155", 600, "middle")
arrow([(1067, 774), (1067, 942)], "prop", dashed=True)
text(1073, 900, "proposals only", 10.5, "#c2410c", 700)
arrow([(850, 994), (954, 994)], "data")
text(902, 986, "status", 10, "#334155", 600, "middle")
arrow([(1178, 994), (1200, 994)], "store")
arrow([(1308, 1044), (1308, 1066), (234, 1066)], "store")
text(760, 1061, "approved tasks and drafts → Tasks tab (owner, due date, source sentence)", 11, "#059669", 600, "middle")

# --- external services, storage, stack ------------------------------------------------------------
y = 1094
w = 268
cards = [
    ("Groq API (external)", ["gpt-oss-120b: answers, agent", "qwen3.8-27b: rate-limit fallback", "gpt-oss-20b: translation,", "  suggestions"], "ext"),
    ("Google Gemini API (external)", ["Files API (PDF upload)", "gemini-3.8-flash", "3.1-flash-lite fallback", "only when Gemini is selected"], "ext"),
    ("Local storage", ["data/uploads: PDF + text", "cache.sqlite: answers,", "  translations, suggestions", "agent.sqlite: proposals, tasks"], "store"),
    ("Security", ["API keys server-side · strict CSP", "model output never rendered", "  as HTML, links or images", "hidden text never used as evidence"], "check"),
    ("Stack", ["FastAPI · Pydantic · uvicorn", "pdfplumber · rapidfuzz · jiter", "React 19 · Tailwind 4 · Zod", "pytest · Playwright · axe"], "plain"),
]
for i, (title, lines, style) in enumerate(cards):
    box(20 + i * (w + 15), y, w, 128, title, lines, style)

out.append("</svg>")
Path(__file__).with_name("architecture.svg").write_text(NL.join(out) + NL, encoding="utf-8")
print("wrote architecture.svg")
