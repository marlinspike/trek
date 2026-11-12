"""Settings from the main menu (ui/settings_hub.py), and the line-by-line officers.toml editor behind it."""

from __future__ import annotations

import os
import sys

import pytest

from begin.crew import officer_file

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


MINE = '''# my own officers
[spock]
traits = ["precise and emphatic", "dry wit"]   # keep this comment
response_style = """
long and
  winding"""

[worf]
# interests = ["cooking"]
name = "Worf"
persona = "A very particular persona of mine."

[worf.lines]
idle = ["one",
        "two"]
'''


def test_one_key_changes_and_every_other_line_stays(tmp_path) -> None:
    p = tmp_path / "officers.toml"
    p.write_text(MINE)
    officer_file.set_field(p, "worf", "name", "Martok")
    after = p.read_text()
    assert after == MINE.replace('name = "Worf"', 'name = "Martok"')
    officer_file.set_field(p, "spock", "response_style", "short")       # a multi-line value is replaced whole
    data = tomllib.loads(p.read_text())
    assert data["spock"]["response_style"] == "short"
    assert "winding" not in p.read_text() and "# keep this comment" in p.read_text()
    assert data["worf"]["persona"] == "A very particular persona of mine." and data["worf"]["lines"]["idle"] == ["one", "two"]


def test_new_keys_go_under_their_officer_and_empty_takes_them_out(tmp_path) -> None:
    p = tmp_path / "officers.toml"
    p.write_text(MINE)
    officer_file.set_field(p, "worf", "rank", "General")
    officer_file.set_field(p, "seven", "traits", ["calm", "  ", "exact"])
    data = tomllib.loads(p.read_text())
    assert data["worf"]["rank"] == "General" and data["seven"]["traits"] == ["calm", "exact"]
    lines = p.read_text().splitlines()
    assert lines.index('rank = "General"') < lines.index("[worf.lines]")
    officer_file.set_field(p, "worf", "rank", "")
    officer_file.set_field(p, "seven", "traits", [])
    assert "rank" not in tomllib.loads(p.read_text())["worf"]
    assert p.read_text().startswith(MINE.rstrip("\n").split("[worf.lines]")[0][:40])
    assert officer_file.read_field(p, "worf", "name") == "Worf"
    assert officer_file.read_field(p, "seven", "traits") is None


def test_no_file_is_written_until_something_changes_and_a_broken_one_is_left_alone(tmp_path) -> None:
    p = tmp_path / "officers.toml"
    officer_file.set_field(p, "worf", "name", "")
    assert not p.exists()
    officer_file.set_field(p, "worf", "name", 'Kor "the Bold"')
    assert tomllib.loads(p.read_text())["worf"]["name"] == 'Kor "the Bold"'
    p.write_text("[worf\nname = ")
    with pytest.raises(ValueError):
        officer_file.set_field(p, "worf", "rank", "General")
    assert p.read_text() == "[worf\nname = "
    with pytest.raises(ValueError):
        officer_file.set_field(p, "worf", "persona", "anything")        # not one the page edits


@pytest.fixture
def menu(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from begin.content import default_content
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    monkeypatch.setenv("BEGIN_HOME", str(tmp_path))
    pygame.init()
    surf = pygame.display.set_mode((1400, 860))
    m = MenuScene(default_content(), Settings(), lambda setup: None, lambda: None)
    m.surf = surf
    return m


def _key(menu, key: int, text: str = "") -> None:  # type: ignore[no-untyped-def]
    import pygame

    menu.handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=text))


def _click(menu, tip: str, nth: int = 0) -> None:  # type: ignore[no-untyped-def]
    menu.draw(menu.surf)
    hits = [h for h in menu.ui.hotspots if h.tooltip.startswith(tip)]
    assert hits, tip
    hits[nth].action()


def test_settings_opens_from_the_main_menu_and_every_section_draws(menu) -> None:  # type: ignore[no-untyped-def]
    import pygame

    _key(menu, pygame.K_s, "s")
    assert menu.page == "settings"
    seen = []
    for _ in menu.hub.sections:
        menu.draw(menu.surf)
        seen.append(menu.hub.section)
        _key(menu, pygame.K_DOWN)
    assert seen == [s.key for s in menu.hub.sections] and "display" not in seen      # no display control: no page
    assert menu.hub.section == seen[0]
    small = pygame.Surface((1024, 640))
    for key in seen:                                    # a small window: everything still draws (and scrolls)
        menu.hub.go(key)
        menu.draw(small)
        assert all(menu.hub._view.contains(h.rect) for h in menu.ui.hotspots
                   if h.rect.x > menu.hub._view.x)
    _key(menu, pygame.K_ESCAPE)
    assert menu.page == "main"


def test_switches_choices_and_sliders_save_at_once(menu) -> None:  # type: ignore[no-untyped-def]
    import pygame

    from begin.settings import Settings

    menu.open_settings("battle")
    _click(menu, "Officers comment")
    _click(menu, "How fast battle time runs", 3)
    s = Settings.load()
    assert s.chatter is False and s.speed == 2.0
    menu.open_settings("bridge")
    _click(menu, "The console as Begin had it")
    assert Settings.load().bridge["mode"] == "classic" and Settings.load().bridge["wheel"] is False
    _click(menu, "Right-click a ship")
    b = Settings.load().bridge
    assert b["mode"] == "classic" and b["wheel"] is True
    menu.open_settings("sound")
    menu.draw(menu.surf)
    rail, set_x = menu.hub._sliders[0]                  # the volume: dragged to the left end, saved on release
    menu.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rail.center))
    menu.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(rail.x - 50, rail.centery), rel=(0, 0), buttons=(1, 0, 0)))
    menu.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(rail.x - 50, rail.centery)))
    assert Settings.load().volume == 0.0
    _click(menu, "Version B", 1)                        # the torpedo, version B
    assert Settings.load().sounds == {"torpedo": "b"}


def test_typing_a_model_saves_it_and_esc_puts_it_back(menu) -> None:  # type: ignore[no-untyped-def]
    import pygame

    from begin.settings import Settings

    menu.open_settings("model")
    _click(menu, "A model on this computer")             # Ollama
    assert Settings.load().llm["provider"] == "ollama"
    _click(menu, "The model's name")
    assert menu.hub.editing is not None
    for ch in "lfm3":
        menu.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    _key(menu, pygame.K_q, "q")                          # a letter while typing is the field's, not the menu's
    assert menu.page == "settings"
    _key(menu, pygame.K_RETURN)
    assert Settings.load().llm["model"] == "lfm3" and menu.hub.editing is None
    _click(menu, "Leave it empty")
    for ch in "localhost:11434":
        menu.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    _key(menu, pygame.K_RETURN)                          # not an address: said so, nothing saved
    assert "base_url" not in Settings.load().llm and menu.hub.fields["model.base_url"].error
    _click(menu, "Leave it empty")
    _key(menu, pygame.K_ESCAPE)                          # Esc leaves the field, not the page
    assert menu.page == "settings" and menu.hub.editing is None
    _click(menu, "Answer at once")
    assert Settings.load().llm["think"] is False
    _click(menu, "No model")
    assert Settings.load().llm["provider"] == "off" and Settings.load().llm["model"] == "lfm3"   # kept for later


def test_the_officers_page_writes_only_what_the_captain_changes(menu, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pygame

    p = tmp_path / "officers.toml"
    p.write_text(MINE)
    menu.open_settings("officers")
    _click(menu, "Worf's settings")
    _click(menu, "Their rank")
    assert menu.hub.editing.draft == "Lieutenant"         # the shipped words, to edit
    _key(menu, pygame.K_RETURN)                          # unchanged: nothing written
    assert p.read_text() == MINE
    _click(menu, "Their rank")
    menu.hub.editing.draft = ""
    for ch in "General":
        menu.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    _key(menu, pygame.K_RETURN)
    mine = 'persona = "A very particular persona of mine."\n'
    assert p.read_text() == MINE.replace(mine, mine + 'rank = "General"\n')
    menu.draw(menu.surf)
    _click(menu, "Take rank out")
    assert p.read_text() == MINE
    assert "persona" in p.read_text()


def test_character_voices_get_their_own_model_from_the_page(menu) -> None:  # type: ignore[no-untyped-def]
    import pygame

    from begin.settings import Settings

    _key(menu, pygame.K_v, "v")
    assert menu.page == "settings" and menu.hub.section == "voices"
    menu.draw(menu.surf)
    assert not any(h.tooltip.startswith("Off keeps") for h in menu.ui.hotspots)    # no model yet: no switch
    fields = [h for h in menu.ui.hotspots if h.tooltip.startswith("The model's name")]
    fields[0].action()
    for ch in "dolphin3":
        menu.handle(pygame.event.Event(pygame.TEXTINPUT, text=ch))
    _key(menu, pygame.K_RETURN)
    assert Settings.load().llm["character"] == {"model": "dolphin3"}
    _click(menu, "None picked")                           # Klingon captains only
    assert Settings.load().llm["character"]["factions"] == ["klingon"]
