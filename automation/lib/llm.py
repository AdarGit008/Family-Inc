"""
Family inc. — the ONLY Anthropic wrapper (SPEC.md §8.7).

Model ids live in `config.MODELS`, never at call sites. Every call logs usage
to `logs/llm_costs.csv`. LLM calls are decoration, not structure: `complete()`
returns None on any failure (no key, SDK missing, API error, empty answer) and
the caller takes its deterministic fallback — degrade quiet, per SPEC §3.6.

Tests NEVER hit the API (ENGINEERING.md §7): set FAMILY_INC_LLM_FAKE to a
canned response and `complete()` returns it verbatim.
"""
from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from typing import Optional

from automation.lib import config

log = logging.getLogger("llm")


def available() -> bool:
    """True when a call would do something: a fake is injected or a key is set."""
    return bool(os.environ.get(config.LLM_FAKE_ENV) or os.environ.get("ANTHROPIC_API_KEY"))


def complete(prompt: str, *, task: str = "classify", system: Optional[str] = None,
             max_tokens: int = 400, source: str = "") -> Optional[str]:
    """One completion. None means 'use your deterministic fallback'."""
    fake = os.environ.get(config.LLM_FAKE_ENV)
    if fake:
        _log_cost(source or task, task, "fake", 0, 0)
        return fake

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — deterministic fallback")
        return None

    model = config.MODELS.get(task)
    if not model:
        log.warning("unknown LLM task %r (config.MODELS) — deterministic fallback", task)
        return None

    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(**kwargs)
        text = (resp.content[0].text or "").strip() if resp.content else ""
        usage = getattr(resp, "usage", None)
        _log_cost(source or task, task, model,
                  getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        return text or None
    except Exception as e:  # degrade quiet: log with context, fall back
        log.warning("LLM call failed (%s: %s) — deterministic fallback", type(e).__name__, e)
        return None


_COST_HEADER = ["at", "source", "task", "model", "input_tokens", "output_tokens"]


def _log_cost(source: str, task: str, model: str, tokens_in: int, tokens_out: int) -> None:
    """Per-call usage line. Monthly ₪ totals are derived from this at briefing
    time (first weekly briefing of each month, SPEC §8.7)."""
    try:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        new = not config.LLM_COSTS_LOG.exists()
        with config.LLM_COSTS_LOG.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(_COST_HEADER)
            w.writerow([datetime.now().isoformat(timespec="seconds"),
                        source, task, model, tokens_in, tokens_out])
    except OSError as e:
        log.warning("could not write llm cost log: %s", e)
