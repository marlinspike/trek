"""What goes to the language model stays small and steady, however long the battle or the conversation."""

from __future__ import annotations

import os
import time
from collections import deque

import pytest

from begin.battle import build_battle
from begin.llm.context import (MESSAGE_CAP, PROMPT_BUDGET, STABLE_END, context_window, fit, flatten,
                               prompt_tokens, split)
from begin.llm.providers.base import LLMConfig, config_from_settings, make_provider
from begin.llm.service import LLMService
from begin.presets import load_presets


def _talk(n: int, words: int = 60) -> list[dict[str, str]]:
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"order {i} " + "word " * words})
        out.append({"role": "assistant", "content": f"answer {i} " + "word " * words})
    out.append({"role": "user", "content": "the newest order"})
    return out


def test_fit_drops_the_oldest_turns_and_keeps_the_newest() -> None:
    system = "rules " * 400
    msgs = _talk(40)
    kept = fit(system, msgs, budget=1500)
    assert prompt_tokens(system, kept) <= 1500
    assert kept[-1]["content"] == "the newest order"
    assert kept[0]["role"] == "user"                          # never starts with a reply to a line it lost
    assert kept == msgs[-len(kept):]                          # what's kept is the most recent, in order
    assert fit(system, msgs[-3:], budget=10_000) == msgs[-3:]   # a short talk is sent whole
    huge = fit("s", [{"role": "user", "content": "x" * 50_000}], budget=10)
    assert len(huge) == 1 and len(huge[0]["content"]) == MESSAGE_CAP + 1   # one message is cut, never dropped


def test_the_service_fits_every_request() -> None:
    seen: list[list[dict[str, str]]] = []

    class Rec:
        name = "rec"

        def complete(self, system: str, messages: list[dict[str, str]]) -> str:
            seen.append(messages)
            return "ok"

    svc = LLMService(Rec(), workers=1)
    svc.submit("spock", "rules", _talk(200))
    end = time.time() + 5
    while not seen and time.time() < end:
        time.sleep(0.01)
    svc.close()
    assert seen and prompt_tokens("rules", seen[0]) <= PROMPT_BUDGET and seen[0][-1]["content"] == "the newest order"


def test_stable_mark_splits_and_flattens() -> None:
    assert split("rules" + STABLE_END + "now") == ("rules", "now")
    assert split("no mark") == ("", "no mark")
    assert STABLE_END not in flatten("a" + STABLE_END + "b")


def test_ollama_gets_a_window_that_fits_and_never_the_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    from begin.llm.providers import ollama

    bodies: list[dict] = []   # type: ignore[type-arg]
    monkeypatch.setattr(ollama, "post_json", lambda url, body, headers, timeout: bodies.append(body)
                        or {"message": {"content": "Aye."}})
    make_provider(LLMConfig("ollama", "lfm3"), env={}).complete("rules" + STABLE_END + "now", [])
    make_provider(LLMConfig("ollama", "lfm3"), env={}).complete("short", [{"role": "user", "content": "hi"}])
    assert bodies[0]["options"]["num_ctx"] == bodies[1]["options"]["num_ctx"] == context_window(2000) == 8192
    assert STABLE_END not in bodies[0]["messages"][0]["content"]
    assert context_window(2000) >= PROMPT_BUDGET + 2000            # the biggest prompt fit allows, and the reply
    cfg = config_from_settings({"provider": "ollama", "model": "lfm3", "context": 16384}, env={})
    assert cfg is not None and cfg.context == 16384
    make_provider(cfg, env={}).complete("s", [])
    assert bodies[-1]["options"]["num_ctx"] == 16384
    for raw in ("auto", None, 100, "lots"):
        c = config_from_settings({"provider": "ollama", "model": "m", "context": raw}, env={})
        assert c is not None and c.context is None


def test_openai_never_sees_the_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    from begin.llm.providers import openai_compat

    bodies: list[dict] = []   # type: ignore[type-arg]
    monkeypatch.setattr(openai_compat, "post_json", lambda url, body, headers, timeout: bodies.append(body)
                        or {"choices": [{"message": {"content": "Aye."}}]})
    make_provider(LLMConfig("openai", "m"), env={"OPENAI_API_KEY": "k"}).complete("a" + STABLE_END + "b", [])
    assert bodies[0]["messages"][0]["content"] == "a\nb"


def test_anthropic_caches_the_unchanging_part() -> None:
    from begin.llm.providers.anthropic import system_blocks

    blocks = system_blocks("rules" + STABLE_END + "the situation")
    assert blocks[0] == {"type": "text", "text": "rules", "cache_control": {"type": "ephemeral"}}
    assert blocks[1] == {"type": "text", "text": "the situation"}
    assert system_blocks("plain") == [{"type": "text", "text": "plain"}]


@pytest.fixture()
def bridge(content):  # type: ignore[no-untyped-def]
    from begin.crew.conversation import Bridge
    from begin.help.coach import HelpContext

    b = build_battle(content, next(p for p in load_presets() if p.id == "fleet-action").setup())
    assert b.crew is not None
    w = b.world
    me = w.ships[b.player_ship_id]
    return Bridge(b.crew, {}, None), w, lambda: HelpContext(content, w.observe(me.side), me)


def test_every_officer_shares_one_unchanging_rulebook(bridge) -> None:  # type: ignore[no-untyped-def]
    br, w, ctx = bridge
    first = {o.id: split(br.system_prompt(o, ctx()))[0] for o in br.officers()}
    w.run(30)
    br.recent["worf"] = deque(["Torpedoes away."])
    later = {o.id: split(br.system_prompt(o, ctx()))[0] for o in br.officers()}
    assert len(set(first.values()) | set(later.values())) == 1      # same text for everyone, all battle long
    rules = next(iter(first.values()))
    assert "console syntax" in rules and "What the ship knows" not in rules
    worf = split(br.system_prompt(br.find("worf"), ctx()))[1]
    assert "Worf" in worf and "What the ship knows" in worf and "Torpedoes away." in worf


def test_officers_recall_only_their_last_few_lines(bridge) -> None:  # type: ignore[no-untyped-def]
    br, _, _ = bridge
    br.recent["worf"] = deque([f"line {i} " + "x" * 300 for i in range(12)], maxlen=12)
    text = br.character(br.find("worf"))
    assert "line 11" in text and "line 6" not in text and "x" * 200 not in text


def test_a_long_silence_starts_a_fresh_conversation(bridge) -> None:  # type: ignore[no-untyped-def]
    from begin.crew import conversation

    br, w, ctx = bridge
    asked: list[list[dict[str, str]]] = []

    class Rec:
        name = "rec"

        def complete(self, system: str, messages: list[dict[str, str]]) -> str:
            asked.append(list(messages))
            return '{"say": "Aye.", "commands": []}'

    br.llm = LLMService(Rec(), workers=1)
    worf = br.find("worf")

    def say(words: str) -> None:
        br._ask_model(worf, words, words, ctx())
        end = time.time() + 5
        while br.llm.busy("worf") and time.time() < end:
            br.poll(ctx(), lambda line, o: None)
            time.sleep(0.005)

    for i in range(10):
        say(f"question {i}")
    assert len(asked[-1]) <= conversation.HISTORY and asked[-1][-1]["content"] == "question 9"
    w.run(conversation.CONVERSATION_GAP + 5)
    say("a new matter")
    assert asked[-1] == [{"role": "user", "content": "a new matter"}]
    br.llm.close()


class _Recorder:
    name = "rec"

    def __init__(self) -> None:
        self.prompts: list[tuple[str, int]] = []

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        from begin.llm.usage import caller

        who = caller.get()
        self.prompts.append((who, prompt_tokens(system, messages)))
        if who == "console":
            return '{"commands": ["status"], "say": "", "clarify": ""}'
        return '{"say": "Aye, Captain.", "commands": []}'


def test_a_long_battle_never_grows_the_prompt(content, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    import begin.llm.providers as providers
    from begin.session.battle import BattleSession

    rec = _Recorder()
    monkeypatch.setattr(providers, "make_provider", lambda cfg, env=os.environ: rec)
    b = build_battle(content, next(p for p in load_presets() if p.id == "fleet-action").setup())
    s = BattleSession(b, hidden={}, llm={"provider": "ollama", "model": "x"})
    s.paused = False
    lines = ["worf, what do you make of their shields?", "spock, what do you recommend?",
             "geordi, how are the engines?", "seven, what do you see?", "go after the closest one"]
    for i in range(48):
        s.run_console(lines[i % len(lines)])
        for _ in range(10):
            s.update(0.5, rate=1.0)
            time.sleep(0.002)
    time.sleep(0.2)
    s.update(0.0)
    officers = [n for who, n in rec.prompts if who in ("worf", "spock", "geordi", "seven")]
    assert len(officers) >= 30
    assert max(n for _, n in rec.prompts) <= PROMPT_BUDGET
    early, late = officers[:8], officers[-8:]
    assert sum(late) / len(late) < sum(early) / len(early) * 1.3       # bounded: no log piling up
