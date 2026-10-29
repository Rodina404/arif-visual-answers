"""LIVE (1 request per variant): isolate what Gemini rejects. Prints the full error."""

import json
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app.catalog import flat_answer_schema  # noqa: E402

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
variant = sys.argv[1]
model = os.getenv("MODEL", "gemini-3.8-flash")
cfg: dict = {"max_output_tokens": 300, "thinking_config": types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)}
if variant in ("schema", "all"):
    cfg |= {"response_mime_type": "application/json", "response_json_schema": flat_answer_schema()}
if variant == "all":
    cfg["media_resolution"] = types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
try:
    r = client.models.generate_content(
        model=model,
        contents="Answer in JSON: what is 2+2? answer_text only, language en, needs_visual false, components [].",
        config=types.GenerateContentConfig(**cfg),
    )
    print("OK", r.text[:300])
    print("usage", r.usage_metadata)
except Exception as e:
    print("ERR", type(e).__name__, getattr(e, "code", None))
    print(json.dumps(getattr(e, "details", None), indent=1, default=str)[:3000])
