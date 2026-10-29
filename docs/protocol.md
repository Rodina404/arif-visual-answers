# Arif Visual Answers — streaming protocol

`POST /api/ask` and `POST /api/ask_text` return `text/event-stream`. Each message is

```
event: <TYPE>
data: <json>

```

The client reads it with `fetch` + `ReadableStream` (not `EventSource`, which only does GET). Request body:
`{doc_id, question (1–500 chars), lang: "ar"|"en", text_only?: bool}`.

## Events

Event names follow AG-UI 1.0 so a real AG-UI adapter is a rename, not a redesign.

| Event | Data | AG-UI mapping |
|---|---|---|
| `RUN_STARTED` | `{run_id, doc_id, lang, model, cached: bool}` | `RUN_STARTED` |
| `TEXT_MESSAGE_START` | `{message_id}` | same |
| `TEXT_MESSAGE_CONTENT` | `{message_id, delta}` | same |
| `TEXT_MESSAGE_END` | `{message_id}` | same |
| `COMPONENT_PLANNED` | `{component_id, type}` — show a skeleton | `TOOL_CALL_START` (tool name = component type) |
| `COMPONENT` | `{component_id, type, props, verification: {status: "verified"\|"partial"\|"unverified", dropped_points: n}, downgraded_from?}` | `TOOL_CALL_ARGS` + `TOOL_CALL_END`; A2UI: one catalog component in a surface update |
| `COMPONENT_DROPPED` | `{component_id, type, reason, fallback_text?}` | custom |
| `WARNING` | `{code, message, pages?}` — `HIDDEN_TEXT_DETECTED`, `FALLBACK_MODEL_USED`, `TRUNCATED_OUTPUT` | custom |
| `METRICS` | tokens, cost, latency, component counts, cache (see README §9) | `STATE_SNAPSHOT` |
| `RUN_ERROR` | `{code, message}` — terminal | `RUN_ERROR` |
| `RUN_FINISHED` | `{run_id}` — terminal | `RUN_FINISHED` |

### Ordering guarantees

- `RUN_STARTED` is first. Exactly one of `RUN_FINISHED` or `RUN_ERROR` is last.
- All `TEXT_MESSAGE_CONTENT` deltas arrive before `TEXT_MESSAGE_END`. Concatenating them gives the final `answer_text`.
- `COMPONENT_PLANNED` for a component arrives before its `COMPONENT` or `COMPONENT_DROPPED`. Every planned component ends in exactly one of the two.
- At most 3 `COMPONENT` events. A `quiz` is always the last `COMPONENT`.
- `component_id` is positional (`c1`, `c2`, …), so a skeleton and its component always share an id. `props.id` is whatever id the model produced.
- `METRICS` comes just before the terminal event. On a timeout it comes before `RUN_ERROR`, after any text that arrived.
- An app-cache hit replays the stored events immediately with `RUN_STARTED.cached = true` and `METRICS.cache.app_cache_hit = true`.

### Drop reasons

`needs_visual_false`, `unknown_type`, `invalid` (failed schema validation), `empty_reason`, `duplicate_id`, `mismatched_attribute_keys`, `insufficient_verified_points` (chart), `insufficient_verified_rows` (table), `no_verified_questions` (quiz), `only_one_quiz`, `too_many_components`, `incomplete` (the output was cut off mid-component).

A chart with fewer than 3 verified points but at least 2 arrives as `COMPONENT` with `type: "table"` and `downgraded_from: "chart"`.

## Component props

The props are the Pydantic models in `backend/app/catalog.py`. Their JSON Schema is exported to `frontend/src/catalog/schema.json`, which the Zod schemas in `frontend/src/catalog/schemas.ts` are tested against. `frontend/src/catalog/gemini.schema.json` is the exact schema sent to the model (`SCHEMA_MODE=flat`).

## Future adapters

**AG-UI.** A `/api/agui` endpoint would wrap the same generator. Text events pass through unchanged. `COMPONENT_PLANNED` becomes `TOOL_CALL_START {toolCallId: component_id, toolCallName: type}`. `COMPONENT` becomes `TOOL_CALL_ARGS {delta: JSON.stringify(props)}` followed by `TOOL_CALL_END`. `COMPONENT_DROPPED` becomes `TOOL_CALL_END` plus a `CUSTOM` event. `METRICS` becomes `STATE_SNAPSHOT`. A CopilotKit frontend would then register each catalog component as a render-only tool with the same React components.

**A2UI.** The catalog is already flat and keyed by component id, which is A2UI's model. Each `COMPONENT` maps to one `surfaceUpdate` entry `{id: component_id, component: {<type>: props}}` in a custom catalog that declares the nine types. Verification status and citations would travel as extra props, because A2UI has no native notion of grounding. RTL would have to come from our renderer, since A2UI v0.9 does not specify text direction.
