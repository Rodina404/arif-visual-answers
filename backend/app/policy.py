"""Restraint policy: validation outcome, grounding per component type, downgrades, caps and order."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from . import grounding
from .catalog import (
    COMPONENT_TYPES,
    BaseComponent,
    ChartComponent,
    ComparisonComponent,
    DiagramComponent,
    FlashcardsComponent,
    FormulaComponent,
    QuizComponent,
    StepsComponent,
    TableComponent,
    dump_component,
    parse_component,
    project_component,
    strip_nulls,
)
from .upload import StoredDoc

MAX_COMPONENTS = 3
PRIORITY = ["comparison", "steps", "chart", "table", "diagram", "formula", "flashcards", "text"]
_URL = re.compile(r"(?i)\b(?:https?|ftp|file|javascript|vbscript|data):\S*|\bwww\.\S+")
LINK_REMOVED = "[link removed]"


@dataclass
class Outcome:
    component_id: str
    type: str
    props: dict[str, Any] | None = None
    status: str = "verified"
    dropped_points: int = 0
    drop_reason: str | None = None
    fallback_text: str | None = None
    downgraded_from: str | None = None
    truncated: int = 0  # strings/lists cut to the catalog's limits

    @property
    def dropped(self) -> bool:
        return self.drop_reason is not None

    def component_event(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "component_id": self.component_id,
            "type": self.type,
            "props": self.props,
            "verification": {"status": self.status, "dropped_points": self.dropped_points},
        }
        if self.downgraded_from:
            out["downgraded_from"] = self.downgraded_from
        if self.truncated:
            out["truncated_fields"] = self.truncated
        return out

    def dropped_event(self) -> dict[str, Any]:
        out: dict[str, Any] = {"component_id": self.component_id, "type": self.type, "reason": self.drop_reason}
        if self.fallback_text:
            out["fallback_text"] = self.fallback_text
        return out


def strip_urls(value: Any) -> Any:
    if isinstance(value, str):
        return _URL.sub(LINK_REMOVED, value)
    if isinstance(value, list):
        return [strip_urls(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_urls(v) for k, v in value.items()}
    return value


def fit_limits(raw: Any, err: ValidationError) -> tuple[Any, int] | None:
    """Repair length overruns from providers that can't enforce maxLength/maxItems (Gemini, Groq).

    Over-long strings are cut to the limit with an ellipsis and over-long lists are trimmed. Anything
    else is not repaired: the caller drops the component. Returns (repaired, fixes) or None.
    """
    import copy

    fixed = copy.deepcopy(raw)
    fixes = 0
    for e in err.errors():
        if e["type"] not in ("string_too_long", "too_long"):
            return None
        loc = list(e["loc"])[1:]  # first element is the union tag (component type)
        parent: Any = fixed
        for key in loc[:-1]:
            parent = parent[key]
        last = loc[-1]
        value = parent[last]
        limit = int((e.get("ctx") or {}).get("max_length", 0))
        if not limit:
            return None
        if isinstance(value, str):
            parent[last] = value[: limit - 1].rstrip() + "…"
        elif isinstance(value, list):
            parent[last] = value[:limit]
        else:
            return None
        fixes += 1
    return fixed, fixes


@dataclass
class _Tally:
    dropped: int = 0
    unverified: int = 0

    def status(self) -> str:
        if self.dropped:
            return "partial"
        if self.unverified:
            return "unverified"
        return "verified"


def _ground_citation(doc: StoredDoc, citation: Any, tally: _Tally, values: list[float] | None = None) -> bool:
    """Verify one citation in place (fixing the page if a neighbour matched). False means drop the item."""
    result = grounding.check_quote(doc, citation.page, citation.quote)
    if result.status == "unverified":
        tally.unverified += 1
        return True
    if result.status == "failed":
        return False
    citation.page = result.page
    if values:
        page = doc.page(result.page)
        if not grounding.check_numbers(values, citation.quote, page.visible_text if page else None):
            return False
    return True


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def _ground_chart(c: ChartComponent, doc: StoredDoc, out: Outcome) -> None:
    tally = _Tally()
    for s in c.series:
        kept = []
        for p in s.points:
            if _ground_citation(doc, p.citation, tally, [p.value]):
                kept.append(p)
            else:
                tally.dropped += 1
        s.points = kept
    out.dropped_points = tally.dropped
    out.status = tally.status()
    if all(len(s.points) >= 3 for s in c.series):
        out.props = dump_component(c)
        return
    remaining = [(s, p) for s in c.series for p in s.points]
    if len(remaining) >= 2:
        y = f"{c.y_label} ({c.unit})" if c.unit else c.y_label
        multi = len(c.series) > 1
        columns = [c.x_label or "Label", *(["Series"] if multi else []), y or "Value"]
        rows = [
            {
                "cells": [p.label, *([s.name] if multi else []), _fmt(p.value)],
                "citation": p.citation.model_dump(),
            }
            for s, p in remaining
        ]
        table = TableComponent.model_validate(
            {
                "id": c.id,
                "type": "table",
                "lang": c.lang,
                "title": c.title,
                "reason": c.reason,
                "columns": [col[:30] for col in columns],
                "rows": rows[:12],
            }
        )
        out.type = "table"
        out.downgraded_from = "chart"
        out.status = "partial"
        out.props = dump_component(table)
        return
    out.drop_reason = "insufficient_verified_points"
    if remaining:
        out.fallback_text = "; ".join(
            f"{p.label}: {_fmt(p.value)}{c.unit} (p. {p.citation.page})" for _, p in remaining
        )


def _ground_table(c: TableComponent, doc: StoredDoc, out: Outcome) -> None:
    tally = _Tally()
    kept = []
    for row in c.rows:
        if _ground_citation(doc, row.citation, tally, grounding.cell_numbers(row.cells)):
            kept.append(row)
        else:
            tally.dropped += 1
    c.rows = kept
    out.dropped_points = tally.dropped
    out.status = tally.status()
    if len(kept) >= 2:
        out.props = dump_component(c)
        return
    out.drop_reason = "insufficient_verified_rows"
    if kept:
        out.fallback_text = " · ".join(f"{col}: {cell}" for col, cell in zip(c.columns, kept[0].cells, strict=False))


def _ground_comparison(c: ComparisonComponent, doc: StoredDoc, out: Outcome) -> None:
    tally = _Tally()
    for item in c.items:
        for a in item.attributes:
            if a.citation is None:
                continue
            values = grounding.numbers_in(a.value) or None
            if not _ground_citation(doc, a.citation, tally, values):
                a.citation = None
                tally.dropped += 1
    out.dropped_points = tally.dropped
    out.status = tally.status()
    out.props = dump_component(c)


def _ground_quiz(c: QuizComponent, doc: StoredDoc, out: Outcome) -> None:
    tally = _Tally()
    kept = []
    for q in c.questions:
        if _ground_citation(doc, q.citation, tally):
            kept.append(q)
        else:
            tally.dropped += 1
    c.questions = kept
    out.dropped_points = tally.dropped
    out.status = tally.status()
    if kept:
        out.props = dump_component(c)
    else:
        out.drop_reason = "no_verified_questions"


def _ground_formula(c: FormulaComponent, doc: StoredDoc, out: Outcome) -> None:
    tally = _Tally()
    if c.citation is not None and not _ground_citation(doc, c.citation, tally):
        c.citation = None
        tally.dropped += 1
    out.dropped_points = tally.dropped
    out.status = tally.status()
    out.props = dump_component(c)


def _fix_pages(items: list[Any], doc: StoredDoc) -> None:
    for item in items:
        if getattr(item, "page", None) is not None and item.page > doc.page_count:
            item.page = None


def comparison_keys_match(c: ComparisonComponent) -> bool:
    first = [a.key for a in c.items[0].attributes]
    return all([a.key for a in item.attributes] == first for item in c.items[1:])


@dataclass
class ComponentProcessor:
    """Validates, grounds and polices one completed component at a time, as it streams in."""

    doc: StoredDoc
    needs_visual: bool = True
    seen_ids: set[str] = field(default_factory=set)

    def process(self, raw: Any, index: int) -> Outcome:
        raw_type = raw.get("type") if isinstance(raw, dict) else None
        cid = raw.get("id") if isinstance(raw, dict) and isinstance(raw.get("id"), str) else f"c{index + 1}"
        out = Outcome(component_id=str(cid)[:8], type=str(raw_type or "unknown")[:20])
        if not self.needs_visual:
            out.drop_reason = "needs_visual_false"
            return out
        if raw_type not in COMPONENT_TYPES:
            out.drop_reason = "unknown_type"
            return out
        raw = project_component(strip_nulls(raw))
        if raw_type == "steps":
            raw = {**raw, "ordered": True}  # steps are ordered by definition; the schema can't pin a bool
        raw = strip_urls(raw)
        try:
            comp: BaseComponent = parse_component(raw)
        except ValidationError as err:
            repaired = fit_limits(raw, err)
            try:
                if repaired is None:
                    raise err
                comp = parse_component(repaired[0])
                out.truncated = repaired[1]
            except ValidationError:
                out.drop_reason = "invalid"
                return out
        if not comp.reason.strip():
            out.drop_reason = "empty_reason"
            return out
        if comp.id in self.seen_ids:
            out.drop_reason = "duplicate_id"
            return out
        self.seen_ids.add(comp.id)

        if isinstance(comp, ComparisonComponent) and not comparison_keys_match(comp):
            out.drop_reason = "mismatched_attribute_keys"
            return out
        if isinstance(comp, ChartComponent):
            _ground_chart(comp, self.doc, out)
        elif isinstance(comp, TableComponent):
            _ground_table(comp, self.doc, out)
        elif isinstance(comp, ComparisonComponent):
            _ground_comparison(comp, self.doc, out)
        elif isinstance(comp, QuizComponent):
            _ground_quiz(comp, self.doc, out)
        elif isinstance(comp, FormulaComponent):
            _ground_formula(comp, self.doc, out)
        else:
            if isinstance(comp, StepsComponent):
                _fix_pages(comp.steps, self.doc)
            elif isinstance(comp, FlashcardsComponent):
                _fix_pages(comp.cards, self.doc)
            elif isinstance(comp, DiagramComponent) and comp.page and comp.page > self.doc.page_count:
                comp.page = None
            out.props = dump_component(comp)
        return out


@dataclass
class Selector:
    """Caps the answer at 3 components with at most one quiz, always last.

    The first two non-quiz components are emitted as soon as they're ready (so the user sees them while
    the rest streams). Later ones are held until the end, when the remaining slots go to the
    highest-priority held components; a quiz always keeps its slot.
    """

    emitted: int = 0
    quiz: Outcome | None = None
    held: list[Outcome] = field(default_factory=list)

    def offer(self, out: Outcome) -> list[Outcome]:
        if out.type == "quiz":
            if self.quiz is not None:
                out.drop_reason = "only_one_quiz"
                return [out]
            self.quiz = out
            return []
        if self.emitted < MAX_COMPONENTS - 1:
            self.emitted += 1
            return [out]
        self.held.append(out)
        return []

    def finish(self) -> list[Outcome]:
        slots = MAX_COMPONENTS - self.emitted - (1 if self.quiz else 0)
        ranked = sorted(self.held, key=lambda o: PRIORITY.index(o.type) if o.type in PRIORITY else len(PRIORITY))
        keep = {id(o) for o in ranked[: max(slots, 0)]}
        result: list[Outcome] = []
        for o in self.held:
            if id(o) not in keep:
                o.drop_reason = "too_many_components"
            result.append(o)
        if self.quiz:
            result.append(self.quiz)
        return result
