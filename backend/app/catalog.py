"""The component catalog: the only shapes the model may produce.

Defined once here. `scripts/export_schema.py` writes the JSON Schema that the frontend's Zod schemas
are tested against. Gemini doesn't enforce string lengths, so Pydantic does.
"""

from __future__ import annotations

import copy
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

Lang = Literal["ar", "en"]

COMPONENT_TYPES = ("text", "chart", "comparison", "steps", "table", "diagram", "formula", "quiz", "flashcards")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def S(max_length: int, min_length: int = 0) -> Any:
    return Field(max_length=max_length, min_length=min_length)


class Citation(Strict):
    page: int = Field(ge=1)
    quote: str = S(300, 10)


class BaseComponent(Strict):
    id: str = Field(pattern=r"^c[1-9]$")
    lang: Lang
    title: str = S(80)
    reason: str = S(140)


class TextComponent(BaseComponent):
    type: Literal["text"]
    body: str = S(1200)


class ChartPoint(Strict):
    label: str = S(30)
    value: float
    citation: Citation


class ChartSeries(Strict):
    name: str = S(40)
    points: list[ChartPoint] = Field(min_length=3, max_length=12)


class ChartComponent(BaseComponent):
    type: Literal["chart"]
    chart_type: Literal["bar", "line"]
    x_label: str = S(40)
    y_label: str = S(40)
    unit: str = S(12)
    series: list[ChartSeries] = Field(min_length=1, max_length=2)


class Attribute(Strict):
    key: str = S(30)
    value: str = S(80)
    citation: Citation | None = None


class ComparisonItem(Strict):
    name: str = S(40)
    summary: str = S(160)
    attributes: list[Attribute] = Field(min_length=2, max_length=6)


class ComparisonComponent(BaseComponent):
    type: Literal["comparison"]
    items: list[ComparisonItem] = Field(min_length=2, max_length=4)


class Step(Strict):
    title: str = S(60)
    detail: str = S(220)
    page: int | None = Field(default=None, ge=1)


class StepsComponent(BaseComponent):
    type: Literal["steps"]
    ordered: Literal[True]
    steps: list[Step] = Field(min_length=2, max_length=8)


Cell = Annotated[str, Field(max_length=60)]
Column = Annotated[str, Field(max_length=30)]


class TableRow(Strict):
    cells: list[Cell]
    citation: Citation


class TableComponent(BaseComponent):
    type: Literal["table"]
    columns: list[Column] = Field(min_length=2, max_length=6)
    rows: list[TableRow] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def _cells_match_columns(self) -> TableComponent:
        for i, row in enumerate(self.rows):
            if len(row.cells) != len(self.columns):
                raise ValueError(f"row {i} has {len(row.cells)} cells, expected {len(self.columns)}")
        return self


class DiagramNode(Strict):
    id: str = S(20, 1)
    label: str = S(40)


class DiagramEdge(Strict):
    from_: str = Field(alias="from", max_length=20)
    to: str = S(20)
    label: str | None = Field(default=None, max_length=24)


class DiagramComponent(BaseComponent):
    type: Literal["diagram"]
    layout: Literal["flow", "cycle"]
    nodes: list[DiagramNode] = Field(min_length=2, max_length=10)
    edges: list[DiagramEdge] = Field(min_length=1, max_length=14)
    page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _edges_reference_nodes(self) -> DiagramComponent:
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node id")
        for e in self.edges:
            if e.from_ not in ids or e.to not in ids:
                raise ValueError(f"edge {e.from_}->{e.to} references an unknown node")
        return self


class FormulaComponent(BaseComponent):
    type: Literal["formula"]
    latex: str = S(300, 1)
    explanation: str = S(220)
    citation: Citation | None = None


class QuizQuestion(Strict):
    prompt: str = S(160)
    options: list[Annotated[str, Field(max_length=80)]] = Field(min_length=3, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = S(220)
    citation: Citation

    @model_validator(mode="after")
    def _index_in_range(self) -> QuizQuestion:
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index out of range")
        return self


class QuizComponent(BaseComponent):
    type: Literal["quiz"]
    questions: list[QuizQuestion] = Field(min_length=1, max_length=4)


class Flashcard(Strict):
    front: str = S(60)
    back: str = S(200)
    page: int | None = Field(default=None, ge=1)


class FlashcardsComponent(BaseComponent):
    type: Literal["flashcards"]
    cards: list[Flashcard] = Field(min_length=3, max_length=8)


Component = Annotated[
    TextComponent
    | ChartComponent
    | ComparisonComponent
    | StepsComponent
    | TableComponent
    | DiagramComponent
    | FormulaComponent
    | QuizComponent
    | FlashcardsComponent,
    Field(discriminator="type"),
]
ComponentAdapter: TypeAdapter[Any] = TypeAdapter(Component)

COMPONENT_MODELS: dict[str, type[BaseComponent]] = {
    "text": TextComponent,
    "chart": ChartComponent,
    "comparison": ComparisonComponent,
    "steps": StepsComponent,
    "table": TableComponent,
    "diagram": DiagramComponent,
    "formula": FormulaComponent,
    "quiz": QuizComponent,
    "flashcards": FlashcardsComponent,
}


class VisualAnswer(Strict):
    """What the model fills. Property order matters: answer_text streams first."""

    answer_text: str = S(700, 1)
    language: Lang
    needs_visual: bool
    components: list[Component] = Field(default_factory=list, max_length=3)


class PlannedComponent(Strict):
    type: Literal[COMPONENT_TYPES]  # type: ignore[valid-type]
    intent: str = S(140)


class AnswerPlan(Strict):
    """Plan-then-fill mode, call 1."""

    answer_text: str = S(700, 1)
    language: Lang
    needs_visual: bool
    plan: list[PlannedComponent] = Field(default_factory=list, max_length=3)


def parse_component(raw: Any) -> BaseComponent:
    return ComponentAdapter.validate_python(raw)


def dump_component(c: BaseComponent) -> dict[str, Any]:
    return c.model_dump(by_alias=True, exclude_none=True)


# ---------------------------------------------------------------------------------------------
# Gemini-compatible JSON Schema

_STRIP_KEYS = {"title", "default", "examples", "discriminator", "pattern"}


def _resolve(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            merged = {**copy.deepcopy(defs[name]), **{k: v for k, v in node.items() if k != "$ref"}}
            return _resolve(merged, defs)
        out: dict[str, Any] = {}
        for k, v in node.items():
            if k in _STRIP_KEYS or k == "$defs":
                continue
            if k == "const":
                # Gemini enums are string-only; a boolean const becomes a plain boolean (the server
                # normalises it, e.g. steps.ordered is always set to true before validation).
                if isinstance(v, bool):
                    out["type"] = "boolean"
                else:
                    out["enum"] = [v]
                    out.setdefault("type", "string")
                continue
            if k == "enum" and all(isinstance(x, bool) for x in v):
                out["type"] = "boolean"
                continue
            if k in ("minLength", "maxLength"):
                # Not enforced by Gemini and a source of 400s on large schemas: express the limit as a
                # description hint instead. Pydantic enforces the real limit.
                if k == "maxLength":
                    out["description"] = (out.get("description", "") + f" (max {v} characters)").strip()
                continue
            if k == "properties":
                props = {pk: _resolve(pv, defs) for pk, pv in v.items()}
                # Put the discriminator first so the stream can announce a component's type early.
                if "type" in props and "enum" in props["type"]:
                    props = {"type": props.pop("type"), **props}
                out[k] = props
                continue
            out[k] = _resolve(v, defs)
        if "oneOf" in out:
            out["anyOf"] = out.pop("oneOf")
        # Optional fields: anyOf[X, null] -> X (the field is already not required).
        if "anyOf" in out:
            branches = [b for b in out["anyOf"] if b.get("type") != "null"]
            if len(branches) == 1 and len(out["anyOf"]) == 2:
                rest = {k: v for k, v in out.items() if k != "anyOf"}
                return {**branches[0], **rest}
            out["anyOf"] = branches
        return out
    if isinstance(node, list):
        return [_resolve(v, defs) for v in node]
    return node


def to_gemini_schema(model: type[BaseModel] | TypeAdapter[Any]) -> dict[str, Any]:
    raw = model.json_schema(by_alias=True) if isinstance(model, TypeAdapter) else model.model_json_schema(by_alias=True)
    out = _resolve(raw, raw.get("$defs", {}))
    # Every property the model fills is required; optional-with-default only matters to Pydantic.
    if "components" in out.get("properties", {}) or "plan" in out.get("properties", {}):
        out["required"] = list(out["properties"])
    return out


def visual_answer_schema() -> dict[str, Any]:
    return to_gemini_schema(VisualAnswer)


def plan_schema() -> dict[str, Any]:
    return to_gemini_schema(AnswerPlan)


def component_schema(kind: str) -> dict[str, Any]:
    return to_gemini_schema(COMPONENT_MODELS[kind])


_FIELD_OWNERS: dict[str, list[str]] = {}
for _kind, _model in COMPONENT_MODELS.items():
    for _name, _f in _model.model_fields.items():
        _FIELD_OWNERS.setdefault(_f.alias or _name, []).append(_kind)
_BASE_FIELDS = {"type", "id", "lang", "title", "reason"}


def _strip_additional(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_additional(v) for k, v in node.items() if k != "additionalProperties"}
    if isinstance(node, list):
        return [_strip_additional(v) for v in node]
    return node


def flat_component_schema() -> dict[str, Any]:
    """One object with a `type` enum and every type's fields optional: no anyOf.

    Gemini rejected the 9-branch anyOf schema with 400 INVALID_ARGUMENT (too complex). The server
    projects each component back onto its real model (`project_component`) and validates it strictly.
    """
    props: dict[str, Any] = {
        "type": {
            "type": "string",
            "enum": list(COMPONENT_TYPES),
            "description": "Component type; decides which fields apply.",
        }
    }
    for kind in COMPONENT_TYPES:
        schema = component_schema(kind)
        for name, sub in schema["properties"].items():
            if name in props:
                continue
            sub = dict(sub)
            if name not in _BASE_FIELDS:
                owners = ", ".join(_FIELD_OWNERS[name])
                sub["description"] = (f"Only for type {owners}. " + sub.get("description", "")).strip()
            props[name] = sub
    return _strip_additional(
        {"type": "object", "properties": props, "required": ["type", "id", "lang", "title", "reason"]}
    )


def flat_answer_schema() -> dict[str, Any]:
    base = visual_answer_schema()
    base["properties"]["components"] = {"type": "array", "maxItems": 3, "items": flat_component_schema()}
    return _strip_additional(base)


def project_component(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields that belong to the declared type (flat-mode output carries the rest)."""
    model = COMPONENT_MODELS.get(raw.get("type", ""))
    if model is None:
        return raw
    names = {f.alias or n for n, f in model.model_fields.items()}
    return {k: v for k, v in raw.items() if k in names}


# ---------------------------------------------------------------------------------------------
# Groq / OpenAI-style strict schema


def _strictify(node: Any) -> Any:
    """Strict structured outputs: every property required, optional ones nullable, no extra keys.

    Length/count keywords become description hints (Groq does not document them for strict mode);
    Pydantic still enforces the real limits after the model answers.
    """
    if isinstance(node, list):
        return [_strictify(v) for v in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    hints: list[str] = []
    for k, v in node.items():
        if k in ("minItems", "maxItems"):
            hints.append(f"{'min' if k == 'minItems' else 'max'} {v} items")
            continue
        out[k] = _strictify(v)
    if hints:
        out["description"] = (out.get("description", "") + " (" + ", ".join(hints) + ")").strip()
    if out.get("type") == "object" and "properties" in out:
        required = set(node.get("required", []))
        props = {}
        for name, sub in out["properties"].items():
            if name not in required:
                sub = _nullable(sub)
            props[name] = sub
        out["properties"] = props
        out["required"] = list(props)
        out["additionalProperties"] = False
    return out


def _nullable(sub: dict[str, Any]) -> dict[str, Any]:
    t = sub.get("type")
    if isinstance(t, str) and t not in ("object", "array") and "enum" not in sub:
        return {**sub, "type": [t, "null"]}
    return {"anyOf": [sub, {"type": "null"}]}


def _drop_descriptions(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _drop_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_drop_descriptions(v) for v in node]
    return node


def strict_schema(kind: str = "union", descriptions: bool = False) -> dict[str, Any]:
    """Schema for providers with strict structured outputs (Groq). kind: union (anyOf per type) | flat.

    Descriptions are dropped by default: they cost ~700 input tokens and the system prompt already
    lists every limit, which matters under Groq's 8K tokens-per-minute budget.
    """
    base = visual_answer_schema()
    if kind == "flat":
        base["properties"]["components"] = {"type": "array", "maxItems": 3, "items": flat_component_schema()}
    out = _strictify(base)
    return out if descriptions else _drop_descriptions(out)


def strip_nulls(value: Any) -> Any:
    """Strict-mode output carries explicit nulls for absent optional fields; drop them before validation."""
    if isinstance(value, dict):
        return {k: strip_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [strip_nulls(v) for v in value]
    return value
