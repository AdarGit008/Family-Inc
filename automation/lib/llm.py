"""
Family inc. — the ONE LLM wrapper (SPEC.md §8.6–8.7).

Provider (D-032, wired M4/D-044): DeepSeek is the single configured provider,
reached over its OpenAI-compatible /chat/completions endpoint with stdlib
urllib (no third-party SDK). The Anthropic path is kept as a fallback provider.
The active provider is chosen by which key is present — DeepSeek first, then
Anthropic, then neither.

Model ids live in `config.MODELS` (+ `config.ANTHROPIC_MODELS`), never at call
sites. Every call logs usage to `logs/llm_costs.csv`. LLM calls are decoration,
not structure: `complete()` returns None on any failure (no key, network/API
error, empty or garbled answer) and the caller takes its deterministic fallback
— degrade quiet, per SPEC §3.6.

Tests NEVER hit the network (ENGINEERING.md §7): set FAMILY_INC_LLM_FAKE to a
canned response and `complete()` returns it verbatim, before any provider is
consulted. The single network seam is `_http_post()`, which tests monkeypatch;
conftest also blanks both provider keys so the appliance's /etc/family-inc/env
can't pull a real call into a test (D-038/D-041/D-044).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from automation.lib import config

log = logging.getLogger("llm")


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
def _provider() -> Optional[str]:
    """The active provider name, or None for the deterministic fallback.
    DeepSeek is the configured provider (D-032); Anthropic is the fallback when
    only that key is set. load_env() first so the appliance's
    /etc/family-inc/env keys are seen even before sheet.is_live() runs."""
    config.load_env()
    if os.environ.get(config.DEEPSEEK_API_KEY_ENV):
        return "deepseek"
    if os.environ.get(config.ANTHROPIC_API_KEY_ENV):
        return "anthropic"
    return None


def available() -> bool:
    """True when a call would do something: a fake is injected, or a provider
    key is configured."""
    if os.environ.get(config.LLM_FAKE_ENV):
        return True
    return _provider() is not None


def complete(prompt: str, *, task: str = "classify", system: Optional[str] = None,
             max_tokens: int = 400, source: str = "", json_mode: bool = False) -> Optional[str]:
    """One completion. None means 'use your deterministic fallback'.
    json_mode=True asks the provider for a strict JSON object (DeepSeek
    response_format); callers that parse JSON should set it AND still tolerate
    stray prose on parse, since the Anthropic fallback has no such switch."""
    fake = os.environ.get(config.LLM_FAKE_ENV)
    if fake:
        _log_cost(source or task, task, "fake", 0, 0)
        return fake
    provider = _provider()
    if provider == "deepseek":
        return _complete_deepseek(prompt, task, system, max_tokens, source, json_mode)
    if provider == "anthropic":
        return _complete_anthropic(prompt, task, system, max_tokens, source)
    return None


# ---------------------------------------------------------------------------
# DeepSeek — OpenAI-compatible /chat/completions over stdlib urllib
# ---------------------------------------------------------------------------
def _http_post(url: str, body: bytes, headers: dict, timeout: int) -> dict:
    """POST JSON, return the parsed response dict. This is the ONLY network
    seam — tests monkeypatch THIS, never the real endpoint (ENGINEERING §7)."""
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _complete_deepseek(prompt, task, system, max_tokens, source, json_mode=False) -> Optional[str]:
    model = config.MODELS.get(task)
    if not model:
        log.warning("unknown LLM task %r (config.MODELS) — deterministic fallback", task)
        return None
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "stream": False}
    if json_mode:  # strict JSON object — kills the trailing-prose parse failures (D-046)
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {os.environ[config.DEEPSEEK_API_KEY_ENV]}"}
    try:
        data = _http_post(f"{config.DEEPSEEK_BASE_URL}/chat/completions",
                          body, headers, config.LLM_TIMEOUT_S)
    except (urllib.error.URLError, OSError, ValueError) as e:  # degrade quiet
        log.warning("DeepSeek call failed (%s: %s) — deterministic fallback",
                    type(e).__name__, e)
        return None
    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        log.warning("DeepSeek response unparseable (%s) — deterministic fallback", e)
        return None
    usage = data.get("usage") or {}
    _log_cost(source or task, task, model,
              usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return text or None


# ---------------------------------------------------------------------------
# Anthropic — fallback provider (SDK, lazy import)
# ---------------------------------------------------------------------------
def _complete_anthropic(prompt, task, system, max_tokens, source) -> Optional[str]:
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — deterministic fallback")
        return None
    model = config.ANTHROPIC_MODELS.get(task)
    if not model:
        log.warning("unknown LLM task %r (config.ANTHROPIC_MODELS) — fallback", task)
        return None
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    try:
        client = anthropic.Anthropic(api_key=os.environ[config.ANTHROPIC_API_KEY_ENV])
        resp = client.messages.create(**kwargs)
        text = (resp.content[0].text or "").strip() if resp.content else ""
        usage = getattr(resp, "usage", None)
        _log_cost(source or task, task, model,
                  getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        return text or None
    except Exception as e:  # degrade quiet: log with context, fall back
        log.warning("Anthropic call failed (%s: %s) — deterministic fallback",
                    type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# Cost log (monthly ₪ totals derived from this at briefing time, SPEC §8.7)
# ---------------------------------------------------------------------------
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
