"""Plain-English console input through a (stub) language model."""

from __future__ import annotations

import time

import pygame
import pytest

from begin.battle import build_battle
from begin.console.translator import Translator, normalize_mode, parse_answer
from begin.llm.providers.base import LLMError
from begin.llm.service import LLMService
from begin.presets import load_presets


class _Script:
    """A provider that answers from a list, one reply per request, and records what it was sent."""

    name = "script"

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.seen: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        self.seen.append((system, [dict(m) for m in messages]))
        reply = self.replies.pop(0) if self.replies else '{"commands": [], "say": "", "clarify": ""}'
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, load_presets()[0].setup())
    for ship in b.world.ships.values():
        if ship.side != b.world.ships[b.player_ship_id].side:
            ship.name = "Derango"
    settings: dict[str, object] = {}
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm=settings)
    assert sc.translator is None    # no model configured
    yield sc
    sc.close()


def _hook(sc, *replies: str | Exception, mode: str = "fallback") -> _Script:  # type: ignore[no-untyped-def]
    fake = _Script(*replies)
    sc.translator = Translator(LLMService(fake, workers=1), mode)
    return fake


def _settle(sc, timeout: float = 5.0) -> None:  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while sc.translator.busy() and time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)
    assert not sc.translator.busy()


def _log(sc) -> list[str]:  # type: ignore[no-untyped-def]
    return [ln.text for ln in sc.log]


def test_answers_are_read_cleaned_and_split() -> None:
    say, cmds, ask = parse_answer('Sure. {"commands": ["raise all; helm 90 warp 4", "target [derango]"], "say": "Done."}')
    assert cmds == ["raise all", "helm 90 warp 4", "target derango"] and say == "Done." and ask == ""
    assert parse_answer("Just words.") == ("Just words.", [], "")
    assert parse_answer('{"commands": [], "clarify": "Which ship?"}')[2] == "Which ship?"
    assert [normalize_mode(m) for m in (None, "on", "OFF", "always", "nonsense")] == [
        "fallback", "fallback", "off", "always", "fallback"]


def test_exact_commands_run_at_once_and_prose_goes_to_the_model(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    fake = _hook(sc, '{"commands": ["raise all", "helm 90 warp 2"], "say": "", "clarify": ""}')
    sc.run_console("lower all")
    assert fake.seen == [] and not any(sh.up for sh in sc.player.shields)
    sc.run_console("get the shields up and turn us to starboard, slowly")
    assert any("interpreting" in t for t in _log(sc))
    _settle(sc)
    assert all(sh.up for sh in sc.player.shields) and sc.player.desired_course == pytest.approx(90)
    assert "≈ raise all" in _log(sc) and "≈ helm 90 warp 2" in _log(sc)
    system, messages = fake.seen[0]
    assert "fire [all] phasers" in system and "Derango" in system and "spock" in system
    assert messages[-1]["content"].startswith("get the shields up") and "parser said" in messages[-1]["content"]


def test_unclear_orders_get_a_question_and_the_answer_is_understood(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    fake = _hook(sc, '{"commands": [], "say": "", "clarify": "Which ship, Captain?"}',
                 '{"commands": ["target derango"], "say": "", "clarify": ""}')
    sc.run_console("go after him")
    _settle(sc)
    assert "Computer: Which ship, Captain?" in _log(sc) and sc.translator.awaiting
    course = sc.player.desired_course
    sc.run_console("2")     # would be "helm 2" to the console; here it answers the question
    _settle(sc)
    assert sc.player.desired_course == course and sc.player.target is not None
    _, messages = fake.seen[1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"] and messages[-1]["content"].startswith("2")
    assert not sc.translator.awaiting


def test_a_rejected_command_gets_one_correction(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    fake = _hook(sc, '{"commands": ["frobnicate the warp core"]}', '{"commands": ["raise all"]}')
    sc.run_console("make us safer")
    _settle(sc)
    assert len(fake.seen) == 2 and "rejected by the console" in fake.seen[1][1][-1]["content"]
    assert all(sh.up for sh in sc.player.shields) and not any("frobnicate" in t for t in _log(sc) if t.startswith("≈"))
    fake2 = _hook(sc, '{"commands": ["frobnicate"]}', '{"commands": ["frobnicate again"]}')
    sc.run_console("do the thing")
    _settle(sc)
    assert len(fake2.seen) == 2 and any(t.startswith("Not understood") for t in _log(sc))


def test_the_model_never_ends_the_battle_on_its_own_reading(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    _hook(sc, '{"commands": ["quit"], "say": "Ending the engagement."}')
    sc.run_console("we're done here")
    _settle(sc)
    assert sc.overlay != "debrief" and not sc.world.outcome.over
    assert any("not run: type it yourself" in t for t in _log(sc))


def test_questions_get_answers_and_officers_are_asked(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    _hook(sc, '{"commands": ["ask spock status"], "say": "Use \'raise all\' to raise the shields."}')
    sc.run_console("how do I get my shields up, and what does spock think")
    _settle(sc)
    assert "Computer: Use 'raise all' to raise the shields." in _log(sc)
    assert any(t.startswith("Spock:") for t in _log(sc))


def test_failures_and_modes(scene) -> None:  # type: ignore[no-untyped-def]
    sc = scene
    sc.run_console("translate")
    assert any("No language model" in t for t in _log(sc))
    _hook(sc, LLMError("down"))
    sc.run_console("make it so, number one")
    _settle(sc)
    assert any(t.startswith("Not understood (down)") for t in _log(sc))
    fake = _hook(sc, '{"commands": ["lower all"]}', mode="off")
    sc.run_console("bring us about")
    assert fake.seen == [] and "Unknown command 'bring'. Type 'help' for the list." in _log(sc)
    sc.run_console("translate always")
    assert sc.translator.mode == "always" and sc.llm_settings["console"] == "always"
    sc.run_console("raise all")             # even an exact command goes to the model now
    _settle(sc)
    assert len(fake.seen) == 1 and "≈ lower all" in _log(sc)
    sc.run_console("translate off")          # always reachable, even in "always" mode
    assert sc.translator.mode == "off" and len(fake.seen) == 1


def test_cli_saves_the_console_mode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    from begin.llm.cli import configure
    from begin.ui.settings import Settings

    monkeypatch.setenv("BEGIN_HOME", str(tmp_path))
    configure(["provider=ollama", "model=lfm3", "console=always"])
    assert Settings.load().llm["console"] == "always"
