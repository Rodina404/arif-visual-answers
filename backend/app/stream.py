"""Turn a provider's streamed JSON into AG-UI-named events, one validated component at a time."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import jiter

from . import prompts
from .cache import AnswerCache, cache_key
from .catalog import component_schema, flat_answer_schema, plan_schema, visual_answer_schema
from .config import Settings
from .metrics import MetricsLog, RunTimer, build_metrics
from .policy import ComponentProcessor, Outcome, Selector
from .providers.base import LLMProvider, ProviderDelta, ProviderDocHandle, ProviderError, Usage
from .upload import StoredDoc

log = logging.getLogger("arif.stream")

Event = tuple[str, dict[str, Any]]
BACKOFF_BASE_S = 0.5


def parse_partial(buf: str) -> dict[str, Any] | None:
    start = buf.find("{")
    if start < 0:
        return None
    try:
        value = jiter.from_json(buf[start:].encode("utf-8"), partial_mode="trailing-strings")
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def parse_complete(buf: str) -> dict[str, Any] | None:
    start = buf.find("{")
    end = buf.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        value = json.loads(buf[start : end + 1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


class Deadline(Exception):
    pass


async def _with_deadline(it: AsyncIterator[ProviderDelta], deadline: float) -> AsyncIterator[ProviderDelta]:
    loop = asyncio.get_running_loop()
    ait = it.__aiter__()
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise Deadline
            try:
                async with asyncio.timeout(remaining):
                    d = await ait.__anext__()
            except StopAsyncIteration:
                return
            except TimeoutError as exc:
                raise Deadline from exc
            yield d
    finally:
        aclose = getattr(ait, "aclose", None)
        if aclose:
            with contextlib.suppress(Exception):
                await aclose()


@dataclass
class AskContext:
    settings: Settings
    provider: LLMProvider
    doc: StoredDoc
    handle: ProviderDocHandle
    question: str
    lang: str
    cache: AnswerCache
    metrics: MetricsLog
    text_only: bool = False
    mock_fixture: str | None = None
    no_cache: bool = False
    sleep: Callable[[float], Any] = asyncio.sleep


@dataclass
class _RunState:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    message_id: str = field(default_factory=lambda: "m" + uuid.uuid4().hex[:8])
    timer: RunTimer = field(default_factory=RunTimer)
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    fallback_used: bool = False
    text_started: bool = False
    text_ended: bool = False
    sent_text: str = ""
    planned: set[int] = field(default_factory=set)
    finalized: set[int] = field(default_factory=set)
    counts: dict[str, int] = field(default_factory=dict)
    cacheable: list[Event] = field(default_factory=list)
    errored: bool = False

    def add_usage(self, u: Usage | None) -> None:
        if u:
            self.usage = Usage(
                self.usage.input + u.input,
                self.usage.cached_input + u.cached_input,
                self.usage.output + u.output,
                self.usage.thinking + u.thinking,
            )

    def bump(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1


def _extra(ctx: AskContext) -> dict[str, Any]:
    return {"mock_fixture": ctx.mock_fixture} if ctx.provider.name == "mock" else {}


async def _resilient(
    ctx: AskContext, st: _RunState, make: Callable[[str], AsyncIterator[ProviderDelta]], events: list[Event]
) -> AsyncIterator[ProviderDelta]:
    """Retry 429/503 with backoff + jitter (2 retries), then once on FALLBACK_MODEL. Only before output."""
    models = [ctx.settings.model] * 3 + [ctx.settings.fallback_model]
    for attempt, model in enumerate(models):
        started = False
        try:
            st.model = model
            async for d in make(model):
                started = True
                yield d
            return
        except ProviderError as exc:
            log.warning("attempt %d on %s failed: %s %s", attempt + 1, model, exc.status, exc.message[:200])
            if started or not exc.retryable or attempt == len(models) - 1:
                raise
            if attempt < 2:
                await ctx.sleep(BACKOFF_BASE_S * (2**attempt) + random.uniform(0, 0.25))
            else:
                st.fallback_used = True
                events.append(
                    ("WARNING", {"code": "FALLBACK_MODEL_USED", "message": f"Primary model busy; used {models[-1]}."})
                )


class VisualRun:
    def __init__(self, ctx: AskContext):
        self.ctx = ctx
        self.st = _RunState()
        self.processor = ComponentProcessor(ctx.doc)
        self.selector = Selector()

    # -- helpers that build events -----------------------------------------------------------
    def _text_events(self, state: dict[str, Any]) -> list[Event]:
        st, out = self.st, []
        text = state.get("answer_text")
        if isinstance(text, str) and text.startswith(st.sent_text) and len(text) > len(st.sent_text):
            if not st.text_started:
                st.text_started = True
                out.append(("TEXT_MESSAGE_START", {"message_id": st.message_id}))
            out.append(("TEXT_MESSAGE_CONTENT", {"message_id": st.message_id, "delta": text[len(st.sent_text) :]}))
            st.sent_text = text
            st.timer.mark_text()
        if (
            st.text_started
            and not st.text_ended
            and any(k in state for k in ("language", "needs_visual", "components", "plan"))
        ):
            out.extend(self._end_text())
        return out

    def _end_text(self) -> list[Event]:
        if self.st.text_ended:
            return []
        self.st.text_ended = True
        if not self.st.text_started:
            return []
        return [("TEXT_MESSAGE_END", {"message_id": self.st.message_id})]

    def _plan(self, index: int, kind: Any) -> list[Event]:
        if index in self.st.planned or not isinstance(kind, str):
            return []
        self.st.planned.add(index)
        return [("COMPONENT_PLANNED", {"component_id": f"c{index + 1}", "type": kind[:20]})]

    def _emit(self, outcomes: list[Outcome]) -> list[Event]:
        out: list[Event] = []
        for o in outcomes:
            if o.dropped:
                self.st.bump("dropped")
                log.info("component %s (%s) dropped: %s", o.component_id, o.type, o.drop_reason)
                out.append(("COMPONENT_DROPPED", o.dropped_event()))
            else:
                self.st.bump("emitted")
                self.st.bump(o.status)
                self.st.timer.mark_component()
                out.append(("COMPONENT", o.component_event()))
        return out

    def _finalize(self, index: int, raw: Any) -> list[Event]:
        if index in self.st.finalized:
            return []
        self.st.finalized.add(index)
        o = self.processor.process(raw, index)
        o.component_id = f"c{index + 1}"
        if o.dropped:
            return self._emit([o])
        return self._emit(self.selector.offer(o))

    def _drop_incomplete(self, index: int, raw: Any) -> list[Event]:
        if index in self.st.finalized:
            return []
        self.st.finalized.add(index)
        kind = raw.get("type") if isinstance(raw, dict) else None
        o = Outcome(component_id=f"c{index + 1}", type=str(kind or "unknown"), drop_reason="incomplete")
        return self._emit([o])

    def _component_events(self, state: dict[str, Any], complete: bool) -> list[Event]:
        out: list[Event] = []
        if isinstance(state.get("needs_visual"), bool):
            self.processor.needs_visual = state["needs_visual"]
        comps = state.get("components")
        if not isinstance(comps, list):
            return out
        for i, c in enumerate(comps):
            if isinstance(c, dict) and "type" in c:
                out += self._plan(i, c["type"])
            if complete or i < len(comps) - 1:
                out += self._finalize(i, c)
        return out

    # -- main loop ---------------------------------------------------------------------------
    async def events(self) -> AsyncIterator[Event]:
        ctx, st = self.ctx, self.st
        key = cache_key(
            sha256=ctx.doc.sha256,
            question=ctx.question,
            lang=ctx.lang,
            model=ctx.settings.model,
            prompt_version=ctx.settings.prompt_version,
            mode=f"visual:{ctx.settings.schema_mode}:{int(ctx.text_only)}",
        )
        hit = None if ctx.mock_fixture or ctx.no_cache else ctx.cache.get(key)
        st.model = ctx.settings.model
        yield self._started(cached=hit is not None)
        if hit is not None:
            for e in hit:
                if e[0] == "TEXT_MESSAGE_CONTENT":
                    st.timer.mark_text()
                if e[0] == "COMPONENT":
                    st.timer.mark_component()
                    st.bump("emitted")
                    st.bump(e[1]["verification"]["status"])
                if e[0] == "COMPONENT_DROPPED":
                    st.bump("dropped")
                yield e
            yield self._metrics(app_cache_hit=True)
            yield ("RUN_FINISHED", {"run_id": st.run_id})
            return

        for w in ctx.doc.warnings():
            if w["code"] == "HIDDEN_TEXT_DETECTED":
                yield self._keep(("WARNING", w))

        try:
            gen = self._plan_mode() if ctx.settings.schema_mode == "plan" else self._single_mode()
            async for e in gen:
                yield self._keep(e)
        except Deadline:
            st.errored = True
            for e in self._end_text():
                yield e
            yield self._metrics(app_cache_hit=False)
            yield ("RUN_ERROR", {"code": "TIMEOUT", "message": "The model took too long; showing what arrived."})
            return
        except ProviderError as exc:
            st.errored = True
            log.warning("provider error %s: %s", exc.code, exc.message)
            for e in self._end_text():
                yield e
            yield self._metrics(app_cache_hit=False)
            yield ("RUN_ERROR", {"code": exc.code, "message": _friendly(exc)})
            return

        yield self._metrics(app_cache_hit=False)
        yield ("RUN_FINISHED", {"run_id": st.run_id})
        if not st.errored and not st.fallback_used and not ctx.mock_fixture:
            ctx.cache.put(key, st.cacheable)

    def _keep(self, e: Event) -> Event:
        self.st.cacheable.append(e)
        if e[0] == "RUN_ERROR":
            self.st.errored = True
        return e

    def _started(self, cached: bool) -> Event:
        return (
            "RUN_STARTED",
            {
                "run_id": self.st.run_id,
                "doc_id": self.ctx.doc.doc_id,
                "lang": self.ctx.lang,
                "model": self.ctx.settings.model,
                "cached": cached,
            },
        )

    def _metrics(self, app_cache_hit: bool) -> Event:
        m = build_metrics(
            model=self.st.model,
            provider=self.ctx.provider.name,
            thinking_level=self.ctx.settings.thinking_level,
            usage=Usage() if app_cache_hit else self.st.usage,
            timer=self.st.timer,
            counts=self.st.counts,
            app_cache_hit=app_cache_hit,
            schema_mode=self.ctx.settings.schema_mode,
            fallback_used=self.st.fallback_used,
            mode="visual",
        )
        self.ctx.metrics.add(m)
        return ("METRICS", m)

    def _deadline(self) -> float:
        return asyncio.get_running_loop().time() + self.ctx.settings.request_timeout_s

    async def _single_mode(self) -> AsyncIterator[Event]:
        ctx, st = self.ctx, self.st
        pending: list[Event] = []
        buf = ""

        def make(model: str) -> AsyncIterator[ProviderDelta]:
            mode = ctx.settings.schema_mode
            return ctx.provider.stream_structured(
                system=prompts.json_mode_system() if mode == "json" else prompts.VISUAL_SYSTEM,
                doc=ctx.handle,
                question=ctx.question,
                schema={"flat": flat_answer_schema(), "json": None}.get(mode, visual_answer_schema()),
                lang=ctx.lang,
                max_output_tokens=ctx.settings.max_output_tokens,
                model=model,
                text_only=ctx.text_only,
                **_extra(ctx),
            )

        try:
            async for d in _with_deadline(_resilient(ctx, st, make, pending), self._deadline()):
                for e in pending:
                    yield e
                pending.clear()
                st.add_usage(d.usage)
                if not d.text_delta:
                    continue
                if not buf:
                    log.info("run %s: first chunk after %d ms", st.run_id, st.timer.ms())
                buf += d.text_delta
                state = parse_partial(buf)
                if state is None:
                    continue
                for e in self._text_events(state) + self._component_events(state, complete=False):
                    yield e
        finally:
            _log_raw(ctx.settings, st.run_id, buf)
        for e in pending:
            yield e
        for e in self._finish(buf):
            yield e

    def _finish(self, buf: str) -> list[Event]:
        out: list[Event] = []
        full = parse_complete(buf)
        if full is not None:
            out += self._text_events(full) + self._end_text() + self._component_events(full, complete=True)
        else:
            partial = parse_partial(buf) or {}
            out += self._text_events(partial) + self._end_text() + self._component_events(partial, complete=False)
            comps = partial.get("components")
            if isinstance(comps, list) and comps:
                out += self._drop_incomplete(len(comps) - 1, comps[-1])
            if partial:
                out.append(("WARNING", {"code": "TRUNCATED_OUTPUT", "message": "The model's output was cut off."}))
        if not self.st.text_started:
            raise ProviderError("EMPTY_ANSWER", "The model returned no answer.")
        out += self._emit(self.selector.finish())
        return out

    async def _plan_mode(self) -> AsyncIterator[Event]:
        ctx, st = self.ctx, self.st
        pending: list[Event] = []
        deadline = self._deadline()
        buf = ""

        def make_plan(model: str) -> AsyncIterator[ProviderDelta]:
            return ctx.provider.stream_structured(
                system=prompts.VISUAL_SYSTEM + "\n\n" + prompts.PLAN_SYSTEM_SUFFIX,
                doc=ctx.handle,
                question=ctx.question,
                schema=plan_schema(),
                lang=ctx.lang,
                max_output_tokens=ctx.settings.max_output_tokens,
                model=model,
                text_only=ctx.text_only,
                **_extra(ctx),
            )

        async for d in _with_deadline(_resilient(ctx, st, make_plan, pending), deadline):
            for e in pending:
                yield e
            pending.clear()
            st.add_usage(d.usage)
            if d.text_delta:
                buf += d.text_delta
                state = parse_partial(buf)
                if state:
                    for e in self._text_events(state):
                        yield e
        plan_state = parse_complete(buf) or parse_partial(buf) or {}
        for e in self._text_events(plan_state) + self._end_text():
            yield e
        if not st.text_started:
            raise ProviderError("EMPTY_ANSWER", "The model returned no answer.")
        self.processor.needs_visual = bool(plan_state.get("needs_visual"))
        plan = (
            [p for p in plan_state.get("plan") or [] if isinstance(p, dict)][:3] if self.processor.needs_visual else []
        )
        for i, p in enumerate(plan):
            for e in self._plan(i, p.get("type")):
                yield e
        for i, p in enumerate(plan):
            kind = p.get("type")
            if kind not in (
                "text",
                "chart",
                "comparison",
                "steps",
                "table",
                "diagram",
                "formula",
                "quiz",
                "flashcards",
            ):
                for e in self._drop_incomplete(i, p):
                    yield e
                continue
            cbuf = ""

            def make_fill(
                model: str, kind: str = kind, intent: str = str(p.get("intent", ""))
            ) -> AsyncIterator[ProviderDelta]:
                return ctx.provider.stream_structured(
                    system=prompts.fill_system(kind),
                    doc=ctx.handle,
                    question=ctx.question,
                    schema=component_schema(kind),
                    lang=ctx.lang,
                    max_output_tokens=ctx.settings.max_output_tokens,
                    model=model,
                    intent=intent,
                    **_extra(ctx),
                )

            async for d in _with_deadline(_resilient(ctx, st, make_fill, pending), deadline):
                st.add_usage(d.usage)
                if d.text_delta:
                    cbuf += d.text_delta
            for e in pending:
                yield e
            pending.clear()
            raw = parse_complete(cbuf)
            if raw is None:
                for e in self._drop_incomplete(i, {"type": kind}):
                    yield e
                continue
            raw.setdefault("id", f"c{i + 1}")
            for e in self._finalize(i, raw):
                yield e
        for e in self._emit(self.selector.finish()):
            yield e


class TextRun:
    """The 'Before' panel: the same model answering in plain prose."""

    def __init__(self, ctx: AskContext):
        self.ctx = ctx
        self.st = _RunState()

    async def events(self) -> AsyncIterator[Event]:
        ctx, st = self.ctx, self.st
        key = cache_key(
            sha256=ctx.doc.sha256,
            question=ctx.question,
            lang=ctx.lang,
            model=ctx.settings.model,
            prompt_version=ctx.settings.prompt_version,
            mode="text",
        )
        hit = None if ctx.no_cache else ctx.cache.get(key)
        st.model = ctx.settings.model
        yield (
            "RUN_STARTED",
            {"run_id": st.run_id, "doc_id": ctx.doc.doc_id, "lang": ctx.lang, "model": st.model, "cached": bool(hit)},
        )
        if hit:
            for e in hit:
                st.timer.mark_text()
                yield e
            yield self._metrics(True)
            yield ("RUN_FINISHED", {"run_id": st.run_id})
            return
        pending: list[Event] = []
        events: list[Event] = []

        def make(model: str) -> AsyncIterator[ProviderDelta]:
            return ctx.provider.stream_text(
                system=prompts.TEXT_SYSTEM,
                doc=ctx.handle,
                question=ctx.question,
                lang=ctx.lang,
                max_output_tokens=ctx.settings.max_output_tokens,
                model=model,
                **_extra(ctx),
            )

        deadline = asyncio.get_running_loop().time() + ctx.settings.request_timeout_s
        started = False
        try:
            async for d in _with_deadline(_resilient(ctx, st, make, pending), deadline):
                for e in pending:
                    yield e
                pending.clear()
                st.add_usage(d.usage)
                if d.text_delta:
                    if not started:
                        started = True
                        e0: Event = ("TEXT_MESSAGE_START", {"message_id": st.message_id})
                        events.append(e0)
                        yield e0
                    st.timer.mark_text()
                    e1: Event = ("TEXT_MESSAGE_CONTENT", {"message_id": st.message_id, "delta": d.text_delta})
                    events.append(e1)
                    yield e1
        except (Deadline, ProviderError) as exc:
            if started:
                yield ("TEXT_MESSAGE_END", {"message_id": st.message_id})
            yield self._metrics(False)
            code = "TIMEOUT" if isinstance(exc, Deadline) else exc.code
            msg = "The model took too long." if isinstance(exc, Deadline) else _friendly(exc)
            yield ("RUN_ERROR", {"code": code, "message": msg})
            return
        if started:
            end: Event = ("TEXT_MESSAGE_END", {"message_id": st.message_id})
            events.append(end)
            yield end
        yield self._metrics(False)
        yield ("RUN_FINISHED", {"run_id": st.run_id})
        if started and not st.fallback_used:
            ctx.cache.put(key, events)

    def _metrics(self, hit: bool) -> Event:
        m = build_metrics(
            model=self.st.model,
            provider=self.ctx.provider.name,
            thinking_level=self.ctx.settings.thinking_level,
            usage=Usage() if hit else self.st.usage,
            timer=self.st.timer,
            counts={},
            app_cache_hit=hit,
            schema_mode="text",
            fallback_used=self.st.fallback_used,
            mode="text",
        )
        self.ctx.metrics.add(m)
        return ("METRICS", m)


def _friendly(exc: ProviderError) -> str:
    if exc.code == "UPSTREAM_BUSY":
        return "The model is busy right now. Please try again in a moment."
    if exc.code == "UPSTREAM_AUTH":
        return "The model provider rejected the request (billing or permission)."
    return "Something went wrong while generating the answer. Please try again."


def _log_raw(settings: Settings, run_id: str, buf: str) -> None:
    if not settings.log_raw_output:
        return
    d = settings.data_dir / "logs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{run_id}.json").write_text(buf, encoding="utf-8")


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
