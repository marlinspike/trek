"""The polish sweep: patrols, officers shaped from the player's file, quiet moments, and the map's labels."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from begin.battle import PATROL_SITUATIONS, build_battle, patrol_battle
from begin.content import default_content
from begin.crew.characters import load_officers, read_characters


@pytest.fixture(scope="module")
def content():  # type: ignore[no-untyped-def]
    return default_content()


def test_every_patrol_situation_builds_and_is_seeded(content) -> None:  # type: ignore[no-untyped-def]
    for sid, title, _ in PATROL_SITUATIONS:
        a = patrol_battle(content, 11, situation=sid)
        b = patrol_battle(content, 11, situation=sid)
        assert title in a.title and a.description and "{enemy}" not in a.description
        assert [[s.class_id for s in f.ships] for f in a.fleets] == [[s.class_id for s in f.ships] for f in b.fleets]
        battle = build_battle(content, a)
        me = battle.world.ships[battle.player_ship_id]
        assert me.cls.id == "federation.dn" and me.name == "Enterprise"
        assert any(s.side == 1 for s in battle.world.ships.values())
    assert patrol_battle(content, 5, situation="waves").arrivals          # the second wave is on its way
    assert len(patrol_battle(content, 5, situation="escort").fleets[0].ships) > 1
    assert len([f for f in patrol_battle(content, 5, situation="ambush").fleets if f.side == 1]) == 2


def test_random_patrols_vary(content) -> None:  # type: ignore[no-untyped-def]
    titles = {patrol_battle(content, seed).title.split(": ")[1] for seed in range(1, 40)}
    assert len(titles) >= 4


def test_player_file_reshapes_an_officer(tmp_path: Path) -> None:
    f = tmp_path / "officers.toml"
    f.write_text('''
[worf]
name = "Kor"
rank = "Commander"
interests = ["cooking for the crew", "Klingon opera"]
quirks = "judges a battle like a meal"
background = "Once the finest chef in the fleet"
aliases = ["chef"]
[worf.lines]
idle = ["The galley has gagh tonight."]
victory = "Tonight, the crew eats well."
[seven]
traits = "precise, calm"
''')
    raw = read_characters(f)
    assert raw["worf"]["interests"] == ("cooking for the crew", "Klingon opera")
    officers = load_officers(traits_file=f)
    w = officers["worf"]
    assert (w.name, w.rank) == ("Kor", "Commander")
    assert {"kor", "chef", "worf"} <= set(w.aliases)
    assert w.lines["idle"] == ("The galley has gagh tonight.",) and w.lines["victory"] == ("Tonight, the crew eats well.",)
    assert "target" in w.lines                                   # lines the file leaves alone stay as shipped
    brief = w.brief()
    assert "cooking for the crew" in brief and "judges a battle like a meal" in brief and "finest chef in the fleet." in brief
    assert officers["seven"].traits == ("precise", "calm")
    assert officers["spock"].name == "Spock"                      # an officer the file leaves out stays as shipped


def test_bad_player_file_is_ignored(tmp_path: Path) -> None:
    f = tmp_path / "officers.toml"
    f.write_text("[worf\nname = ")
    assert load_officers(traits_file=f)["worf"].name == "Worf"


def test_quiet_moment_brings_an_idle_line(content) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.conversation import Bridge
    from begin.help.coach import HelpContext

    battle = build_battle(content, patrol_battle(content, 3, situation="flagship"))
    w = battle.world
    for s in list(w.ships.values()):
        if s.side == 1:
            w.ships.pop(s.id)          # nobody in sight: a quiet patrol
    bridge = Bridge(battle.crew, {}, None, seed=1)
    me = w.ships[battle.player_ship_id]
    said = []
    for _ in range(int(400 * w.rules.ticks_per_cycle)):
        w.step()
        obs = w.observe(me.side)
        said += bridge.react([], HelpContext(content, obs=obs, ship=me))
    idle = {line for o in battle.crew.officers.values() for line in o.lines.get("idle", ())}
    assert any(u.text in idle for u in said)


def test_close_ships_share_one_label() -> None:
    from begin.ui.tactical import LABEL_GROUP_PX, TacticalView

    pygame.init()
    from begin.ui.camera import Camera

    view = TacticalView(Camera(pygame.Rect(0, 0, 800, 600), zoom=0.05))
    view._label_more, view._label_quiet, view._label_reach = {}, set(), {}
    near = LABEL_GROUP_PX / 2 / view.cam.zoom
    ships = [(1, (0.0, 0.0, 0.0)), (2, (near, 0.0, 0.0)), (3, (2 * near, 0.0, 0.0)), (4, (5000.0, 5000.0, 0.0))]
    view._group_labels(ships, {None})
    assert view._label_quiet == {2, 3} and view._label_more == {1: 2}
    view._label_more, view._label_quiet, view._label_reach = {}, set(), {}
    view._group_labels(ships, {2})                               # a kept ship (the target) is never folded in
    assert 2 not in view._label_quiet
