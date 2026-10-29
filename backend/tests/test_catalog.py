import json

import pytest
from pydantic import ValidationError

from app.catalog import (
    COMPONENT_TYPES,
    TableComponent,
    flat_answer_schema,
    parse_component,
    project_component,
    to_gemini_schema,
    visual_answer_schema,
)


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


@pytest.mark.parametrize("schema_fn", [visual_answer_schema, flat_answer_schema])
def test_gemini_schema_has_no_unsupported_constructs(schema_fn):
    schema = schema_fn()
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and '"const"' not in text and "oneOf" not in text
    for node in walk(schema):
        assert "default" not in node and "examples" not in node and "pattern" not in node
        assert "minLength" not in node and "maxLength" not in node
        if "enum" in node:
            assert all(isinstance(v, str) for v in node["enum"]), node
        if node.get("type") == "object" and "properties" in node and "title" in node.get("properties", {}):
            assert "title" in node["properties"]  # a field named title is fine; schema titles are not
    assert list(schema["properties"])[0] == "answer_text"
    assert schema["required"] == ["answer_text", "language", "needs_visual", "components"]


def test_full_schema_puts_type_first_in_each_component():
    branches = visual_answer_schema()["properties"]["components"]["items"]["anyOf"]
    assert sorted(b["properties"]["type"]["enum"][0] for b in branches) == sorted(COMPONENT_TYPES)
    assert all(list(b["properties"])[0] == "type" for b in branches)
    assert all(b["additionalProperties"] is False for b in branches)


def test_flat_schema_is_one_object():
    items = flat_answer_schema()["properties"]["components"]["items"]
    assert "anyOf" not in items and items["properties"]["type"]["enum"] == list(COMPONENT_TYPES)
    assert "Only for type chart" in items["properties"]["series"]["description"]


def test_to_gemini_schema_transformations():
    from typing import Literal

    from pydantic import BaseModel

    class Inner(BaseModel):
        x: int = 3

    class M(BaseModel):
        kind: Literal["a"]
        flag: Literal[True]
        inner: Inner | None = None

    s = to_gemini_schema(M)
    assert s["properties"]["kind"] == {"enum": ["a"], "type": "string"}
    assert s["properties"]["flag"] == {"type": "boolean"}
    assert s["properties"]["inner"]["properties"]["x"] == {"type": "integer"}
    assert "title" not in s


def test_pydantic_enforces_lengths_gemini_does_not():
    with pytest.raises(ValidationError):
        parse_component({"type": "text", "id": "c1", "lang": "en", "title": "x" * 81, "reason": "r", "body": "b"})
    with pytest.raises(ValidationError):
        parse_component(
            {"type": "text", "id": "c1", "lang": "en", "title": "t", "reason": "r", "body": "b", "extra": 1}
        )


def test_table_cells_must_match_columns():
    cit = {"page": 1, "quote": "a long enough quote"}
    with pytest.raises(ValidationError):
        TableComponent.model_validate(
            {
                "type": "table",
                "id": "c1",
                "lang": "en",
                "title": "t",
                "reason": "r",
                "columns": ["a", "b"],
                "rows": [{"cells": ["1"], "citation": cit}, {"cells": ["1", "2"], "citation": cit}],
            }
        )


def test_diagram_edges_must_reference_nodes():
    with pytest.raises(ValidationError):
        parse_component(
            {
                "type": "diagram",
                "id": "c1",
                "lang": "en",
                "title": "t",
                "reason": "r",
                "layout": "flow",
                "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "edges": [{"from": "a", "to": "zz"}],
            }
        )


def test_project_component_drops_other_types_fields():
    raw = {
        "type": "text",
        "id": "c1",
        "lang": "en",
        "title": "t",
        "reason": "r",
        "body": "b",
        "series": [],
        "cards": [],
    }
    assert parse_component(project_component(raw)).type == "text"
