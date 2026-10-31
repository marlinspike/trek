"""The language model's debug logs: every prompt and reply, and per-game and all-time token counts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from begin.llm import usage as usage_mod
from begin.llm.providers import anthropic as anthropic_mod
from begin.llm.providers import base
from begin.llm.providers.base import Completion, LLMConfig, LLMError, Message, Usage, config_from_settings
from begin.llm.providers.ollama import OllamaProvider
from begin.llm.providers.openai_compat import OpenAICompatProvider
from begin.llm.service import LLMService
from begin.llm.usage import MeteredProvider, summary


class _Fake:
    name = "fake"

    def __init__(self, usage: Usage | None = Usage(120, 30), fail: bool = False) -> None:
        self.usage = usage
        self.fail = fail

    def complete(self, system: str, messages: list[Message]) -> str:
        return self.complete_full(system, messages).text

    def complete_full(self, system: str, messages: list[Message]) -> Completion:
        if self.fail:
            raise LLMError("Could not reach the provider.")
        return Completion("Aye, Captain.", self.usage)


def _cfg(**kw: Any) -> LLMConfig:
    return LLMConfig("ollama", "lfm3", **kw)


def test_both_logs_are_off_unless_switched_on() -> None:
    cfg = config_from_settings({"provider": "ollama", "model": "lfm3"}, env={})
    assert cfg is not None and not cfg.log_prompts and not cfg.log_tokens
    assert isinstance(base.make_provider(cfg, env={}), OllamaProvider)   # not wrapped: nothing is written
    on = config_from_settings({"provider": "ollama", "model": "lfm3", "log_prompts": "on", "log_tokens": True}, env={})
    assert on is not None and on.log_prompts and on.log_tokens
    assert isinstance(base.make_provider(on, env={}), MeteredProvider)
    by_env = config_from_settings({"provider": "ollama", "model": "lfm3"}, env={"BEGIN_LLM_LOG_TOKENS": "1"})
    assert by_env is not None and by_env.log_tokens and not by_env.log_prompts


def test_the_logs_live_in_the_project_config_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEGIN_HOME", str(tmp_path))
    assert usage_mod.log_dir() == tmp_path / "logs"


def test_every_prompt_and_reply_is_logged_with_its_tokens(tmp_path: Path) -> None:
    p = MeteredProvider(_Fake(), _cfg(log_prompts=True), tmp_path)
    usage_mod.caller.set("spock")
    assert p.complete("You are Spock.", [{"role": "user", "content": "Status?"}]) == "Aye, Captain."
    text = (tmp_path / "llm-prompts.log").read_text()
    assert "spock" in text and "ollama/lfm3" in text and "in 120 out 30" in text
    assert "--- system\nYou are Spock." in text and "--- user\nStatus?" in text and "--- reply\nAye, Captain." in text
    assert not (tmp_path / "llm-tokens.json").exists()   # only the log that was asked for


def test_tokens_are_counted_per_game_and_in_total(tmp_path: Path) -> None:
    usage_mod._ledgers.clear()
    first = MeteredProvider(_Fake(), _cfg(log_tokens=True), tmp_path)
    usage_mod.caller.set("worf")
    first.complete("s", [{"role": "user", "content": "q"}])
    usage_mod.caller.set("console")
    first.complete("s", [{"role": "user", "content": "q"}])
    second = MeteredProvider(_Fake(Usage(10, 5)), _cfg(log_tokens=True), tmp_path)
    second.complete("s", [{"role": "user", "content": "q"}])
    data = json.loads((tmp_path / "llm-tokens.json").read_text())
    assert data["total"]["calls"] == 3 and data["total"]["tokens_in"] == 250 and data["total"]["tokens_out"] == 65
    g1, g2 = data["games"]
    assert (g1["calls"], g1["tokens_in"], g1["tokens_out"]) == (2, 240, 60)
    assert g1["by_caller"]["worf"]["tokens_in"] == 120 and g1["by_caller"]["console"]["calls"] == 1
    assert (g2["calls"], g2["tokens_in"]) == (1, 10)
    # the totals carry on across runs of the game
    usage_mod._ledgers.clear()
    MeteredProvider(_Fake(), _cfg(log_tokens=True), tmp_path).complete("s", [])
    data = json.loads((tmp_path / "llm-tokens.json").read_text())
    assert data["total"]["calls"] == 4 and len(data["games"]) == 3
    assert "All time: 4 calls, 370 tokens in, 95 out" in summary(tmp_path / "llm-tokens.json")


def test_missing_counts_are_estimated_and_marked(tmp_path: Path) -> None:
    usage_mod._ledgers.clear()
    p = MeteredProvider(_Fake(usage=None), _cfg(log_prompts=True, log_tokens=True), tmp_path)
    p.complete("x" * 400, [{"role": "user", "content": "y" * 40}])
    assert "in 110 out 4 (estimated)" in (tmp_path / "llm-prompts.log").read_text()
    data = json.loads((tmp_path / "llm-tokens.json").read_text())
    assert data["total"]["estimated_calls"] == 1 and data["total"]["tokens_in"] == 110


def test_failures_are_logged_and_still_raised(tmp_path: Path) -> None:
    usage_mod._ledgers.clear()
    p = MeteredProvider(_Fake(fail=True), _cfg(log_prompts=True, log_tokens=True), tmp_path)
    with pytest.raises(LLMError):
        p.complete("s", [{"role": "user", "content": "q"}])
    assert "--- error\nCould not reach the provider." in (tmp_path / "llm-prompts.log").read_text()
    data = json.loads((tmp_path / "llm-tokens.json").read_text())
    assert data["total"]["errors"] == 1 and data["total"]["tokens_in"] == 0


def test_the_service_names_who_asked(tmp_path: Path) -> None:
    p = MeteredProvider(_Fake(), _cfg(log_prompts=True), tmp_path)
    svc = LLMService(p)
    svc.submit("geordi", "s", [{"role": "user", "content": "q"}])
    for _ in range(200):
        if svc.poll():
            break
        time.sleep(0.01)
    svc.close()
    assert "  geordi  " in (tmp_path / "llm-prompts.log").read_text()


def test_each_provider_reads_its_own_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    replies: dict[str, dict[str, Any]] = {
        "ollama": {"message": {"content": "Aye."}, "prompt_eval_count": 812, "eval_count": 64},
        "openai": {"choices": [{"message": {"content": "Aye."}}], "usage": {"prompt_tokens": 500, "completion_tokens": 9}},
    }
    monkeypatch.setattr("begin.llm.providers.ollama.post_json", lambda *a, **k: replies["ollama"])
    monkeypatch.setattr("begin.llm.providers.openai_compat.post_json", lambda *a, **k: replies["openai"])
    assert OllamaProvider(_cfg()).complete_full("s", []).usage == Usage(812, 64)
    oa = OpenAICompatProvider(LLMConfig("openai", "m"), "openai", "https://x", "key")
    assert oa.complete_full("s", []).usage == Usage(500, 9)
    replies["ollama"] = {"message": {"content": "Aye."}, "eval_count": 3}   # a cached prompt: no input count
    assert OllamaProvider(_cfg()).complete_full("s", []).usage is None

    class _AnthropicUsage:
        input_tokens, output_tokens = 20, 7
        cache_creation_input_tokens, cache_read_input_tokens = 100, 1000

    assert anthropic_mod.usage_of(_AnthropicUsage()) == Usage(1120, 7)
    assert anthropic_mod.usage_of(None) is None


def test_cli_switches_the_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from begin.tools.llm import configure

    monkeypatch.setenv("BEGIN_HOME", str(tmp_path))
    s = configure(["provider=ollama", "model=lfm3", "log_prompts=on", "log_tokens=off"])
    assert s.llm["log_prompts"] is True and s.llm["log_tokens"] is False
