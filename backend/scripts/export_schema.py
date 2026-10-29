"""Write the catalog's JSON Schemas for the frontend (Zod equivalence test) and for reference.

frontend/src/catalog/schema.json  — Pydantic's own schema per component (the contract)
frontend/src/catalog/gemini.schema.json — what is actually sent to Gemini (SCHEMA_MODE=flat)
"""

import json
import sys

from app.catalog import COMPONENT_MODELS, Citation, VisualAnswer, flat_answer_schema
from app.config import ROOT

OUT = ROOT / "frontend" / "src" / "catalog"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = {
        "answer": VisualAnswer.model_json_schema(by_alias=True),
        "citation": Citation.model_json_schema(by_alias=True),
        "components": {k: m.model_json_schema(by_alias=True) for k, m in COMPONENT_MODELS.items()},
    }
    (OUT / "schema.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "gemini.schema.json").write_text(json.dumps(flat_answer_schema(), indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT / "schema.json", "and gemini.schema.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
