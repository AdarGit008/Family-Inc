"""Tests for automation/lib/llm.py — provider selection, the DeepSeek HTTP path
(through the monkeypatched _http_post seam, NEVER the network, ENGINEERING §7),
the fake hook, cost logging, and degrade-to-None on every failure mode."""

import json

from automation.lib import config, llm


# ---------------------------------------------------------------------------
# Provider selection + the fake hook
# ---------------------------------------------------------------------------
def test_fake_wins_before_any_provider(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "CANNED")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-should-be-ignored")
    assert llm.available() is True
    assert llm.complete("hi", task="classify") == "CANNED"


def test_no_keys_no_fake_returns_none(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "")
    monkeypatch.setenv(config.ANTHROPIC_API_KEY_ENV, "")
    assert llm.available() is False
    assert llm.complete("hi") is None


def test_provider_prefers_deepseek(monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")
    monkeypatch.setenv(config.ANTHROPIC_API_KEY_ENV, "sk-anthropic")
    assert llm._provider() == "deepseek"


def test_provider_anthropic_when_only_anthropic(monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "")
    monkeypatch.setenv(config.ANTHROPIC_API_KEY_ENV, "sk-anthropic")
    assert llm._provider() == "anthropic"


# ---------------------------------------------------------------------------
# DeepSeek path — happy + every degrade-to-None branch
# ---------------------------------------------------------------------------
def test_deepseek_happy_path_parses_and_logs_cost(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")
    captured = {}

    def fake_post(url, body, headers, timeout):
        captured["url"] = url
        captured["payload"] = json.loads(body.decode("utf-8"))
        captured["auth"] = headers["Authorization"]
        return {"choices": [{"message": {"content": "  שלום  "}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4}}

    monkeypatch.setattr(llm, "_http_post", fake_post)
    out = llm.complete("classify this", task="classify", system="be terse", source="t")
    assert out == "שלום"  # whitespace stripped
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["model"] == config.MODELS["classify"]
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "be terse"}
    assert captured["auth"] == "Bearer sk-deepseek"
    assert config.LLM_COSTS_LOG.exists()
    assert "deepseek-chat" in config.LLM_COSTS_LOG.read_text(encoding="utf-8")


def test_deepseek_network_error_degrades_to_none(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")

    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(llm, "_http_post", boom)
    assert llm.complete("x") is None


def test_deepseek_garbled_response_degrades_to_none(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")
    monkeypatch.setattr(llm, "_http_post", lambda *a, **k: {"unexpected": "shape"})
    assert llm.complete("x") is None


def test_deepseek_empty_content_is_none(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")
    monkeypatch.setattr(llm, "_http_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "   "}}]})
    assert llm.complete("x") is None


def test_unknown_task_returns_none(tmp_runtime, monkeypatch):
    monkeypatch.setenv(config.LLM_FAKE_ENV, "")
    monkeypatch.setenv(config.DEEPSEEK_API_KEY_ENV, "sk-deepseek")
    # _http_post must never be reached for an unknown task → make it explode.
    monkeypatch.setattr(llm, "_http_post",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert llm.complete("x", task="does-not-exist") is None
