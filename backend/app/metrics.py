"""Token accounting, cost from prices.json, latency timers and the session summary."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .providers.base import Usage

PRICES_FILE = Path(__file__).with_name("prices.json")


@lru_cache
def price_table() -> dict[str, Any]:
    return json.loads(PRICES_FILE.read_text(encoding="utf-8"))


def price_for(model: str, on: date | None = None) -> dict[str, float] | None:
    on = on or date.today()
    for period in price_table()["models"].get(model, []):
        start = date.fromisoformat(period["valid_from"])
        end = date.fromisoformat(period["valid_until"]) if period["valid_until"] else date.max
        if start <= on <= end:
            return period
    return None


def cost_usd(model: str, usage: Usage, on: date | None = None) -> dict[str, Any]:
    # Thinking tokens are billed as output for both Gemini and Groq.
    p = price_for(model, on)
    table_date = price_table()["price_table_date"]
    if p is None:  # self-hosted or unknown model: no per-token price
        return {"input": 0.0, "cached_input": 0.0, "output": 0.0, "total": 0.0, "price_table_date": table_date}
    uncached = max(usage.input - usage.cached_input, 0)
    inp = uncached * p["input"] / 1e6
    cached = usage.cached_input * p["cached_input"] / 1e6
    # Thinking tokens are billed at the output rate.
    out = (usage.output + usage.thinking) * p["output"] / 1e6
    return {
        "input": round(inp, 6),
        "cached_input": round(cached, 6),
        "output": round(out, 6),
        "total": round(inp + cached + out, 6),
        "price_table_date": table_date,
    }


@dataclass
class RunTimer:
    started: float = field(default_factory=time.perf_counter)
    ttft_text: float | None = None
    first_component: float | None = None

    def ms(self, t: float | None = None) -> int:
        return int(((t or time.perf_counter()) - self.started) * 1000)

    def mark_text(self) -> None:
        if self.ttft_text is None:
            self.ttft_text = time.perf_counter()

    def mark_component(self) -> None:
        if self.first_component is None:
            self.first_component = time.perf_counter()


def build_metrics(
    *,
    model: str,
    provider: str,
    thinking_level: str,
    usage: Usage,
    timer: RunTimer,
    counts: dict[str, int],
    app_cache_hit: bool,
    schema_mode: str,
    fallback_used: bool,
    mode: str,
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "model": model,
        "provider": provider,
        "thinking_level": thinking_level,
        "tokens": {
            "input": usage.input,
            "cached_input": usage.cached_input,
            "output": usage.output,
            "thinking": usage.thinking,
            "total": usage.total,
        },
        "cost_usd": cost_usd(model, usage) if not app_cache_hit else cost_usd(model, Usage()),
        "latency_ms": {
            "ttft_text": timer.ms(timer.ttft_text) if timer.ttft_text else None,
            "first_component": timer.ms(timer.first_component) if timer.first_component else None,
            "total": timer.ms(),
        },
        "components": {k: counts.get(k, 0) for k in ("emitted", "dropped", "verified", "partial", "unverified")},
        "cache": {"app_cache_hit": app_cache_hit, "gemini_cached_tokens": usage.cached_input},
        "schema_mode": schema_mode,
        "fallback_used": fallback_used,
        "retrieval": retrieval or {"retrieval": "off"},
    }


class MetricsLog:
    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []

    def add(self, m: dict[str, Any]) -> None:
        self.runs.append(m)
        del self.runs[:-1000]

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"runs": len(self.runs), "by_mode": {}}
        for mode in sorted({r["mode"] for r in self.runs}):
            rs = [r for r in self.runs if r["mode"] == mode]
            out["by_mode"][mode] = _stats(rs)
        out["all"] = _stats(self.runs)
        return out


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1]


def _stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = [float(r["latency_ms"]["total"]) for r in runs]
    ttft = [float(r["latency_ms"]["ttft_text"]) for r in runs if r["latency_ms"]["ttft_text"] is not None]
    cost = [r["cost_usd"]["total"] for r in runs]
    return {
        "count": len(runs),
        "latency_total_ms": {"p50": _pct(total, 50), "p95": _pct(total, 95)},
        "ttft_text_ms": {"p50": _pct(ttft, 50), "p95": _pct(ttft, 95)},
        "cost_usd_mean": round(statistics.fmean(cost), 6) if cost else None,
        "cache_hits": sum(1 for r in runs if r["cache"]["app_cache_hit"]),
    }
