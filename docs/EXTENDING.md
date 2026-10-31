# Extending the game

Most changes are data: a new ship, scenario, officer line or manual page is a TOML or Markdown edit, with no code. Code changes follow the pattern in [ARCHITECTURE.md](ARCHITECTURE.md). Everything that acts on a battle is a `Command` validated by the `World`, and everything that decides is a controller that reads an `Observation`. Run `pytest` after any change, and `begin --balance 8` after anything that affects combat.

## A new ship class

`content/data/classes.toml` is generated from Begin's data, so don't put new classes there. Put them in `content/data/custom_classes.toml`, which the loader reads after it and the importer never touches. The quickest way is to start from an existing class with `base`, and list only what differs:

```toml
[[class]]
id = "federation.dnr"
base = "federation.dn"      # copies every field, the repair table, the names and the hull
name = "Dreadnought Refit"
abbrev = "RF"
max_warp = 9.8
warp_power = 320.0
ship_names = ["Enterprise", "Excalibur"]
```

A brand-new class needs every field of a class in `classes.toml` and a `[class.repair]` table. The loader stops with an error that names whatever is missing.

The silhouette and weapon mounts live in `content/data/hulls.toml` under `[hull."<class id>"]`. A class made with `base` reuses its base's hull unless you give it one. The comment at the top of `hulls.toml` explains the coordinate system:

- `shapes` draw the ship;
- `anchors` place the internal systems, which drives where hits land;
- `banks`, `tubes` and `launchers` each list mount positions with an arc `[centre, width]`.

You need at least one mount of each kind the class carries.

Two things to keep in mind about power and speed:

- A ship's top speed is limited by power as well as by `max_warp`: attainable warp = drives × `warp_power` ÷ `warp_power_use`. Raise `warp_power` with `max_warp`, as the Federation Dreadnought does.
- To change an imported class's numbers and keep the change when the data is re-imported, add it to `OVERRIDES` in `tools/import_reference_data.py`, run the importer, and record the change in [DEVIATIONS.md](DEVIATIONS.md).

## Ship sprites

The Enterprise's lit, plated sprite comes from `tools/render_ship.py`, which builds the ship from height fields (saucer, bridge dome, secondary hull, pylons, nacelles), lights it, and writes `src/begin/assets/ships/heavy-cruiser-000.png` to `-330.png`, one per 30° of heading. It needs numpy (`pip install numpy`); the game itself only loads the PNGs. `python tools/render_ship.py` bakes all twelve in about a minute and a half, and `python tools/render_ship.py 0 90` bakes just those headings while you iterate. The constants at the top set the pixel scale (`PX`), supersampling (`SS`), the light and rim directions and the palette; if you change `PX` or the model's bounds, change `SPRITE_PX` and `SPRITE_CENTRE_Y` in `ui/showpiece.py` to match. Every other class gets its sprites from `tools/render_fleet.py`, which builds them from the class's shapes in `hulls.toml` (see [ARCHITECTURE.md](ARCHITECTURE.md)). After you add or change a hull, run `PYTHONPATH=src python tools/render_fleet.py <class-id>` (about five seconds a class) and its twelve PNGs land in `src/begin/assets/ships/fleet/`. A class you make with `base` and no hull of its own wears its base's art; one with a new hull and no baked art is drawn as its outline.

## Torpedoes and probes

Designs live in `content/data/ordnance.toml` (`[[torpedo]]` and `[[probe]]`). A class's native loadout is its `torpedo` and `probe` field. Its tubes and launchers can also load the other designs listed in its faction's `torpedoes` and `probes` in `factions.toml`; plasma tubes and antimatter tubes don't share designs. `ordnance.toml` is generated, so put hand-made designs in `content/data/custom_ordnance.toml` instead; it is loaded after the generated file and survives a re-import. A design marked `special = true` is never autoloaded. It only reaches a tube through a crew project (see below). `reveal_radius` and `reveal_cycles` make a round burst into a cloud that shows cloaked ships, as the tachyon detector does.

## A preset battle

Add a `[[preset]]` to `content/data/presets.toml`. Each fleet has a `side`, a `center` in world units and a list of class ids. On the player's fleet, `player = true` makes its first ship yours. Check the balance with:

```
begin --balance 16
begin --preset <id>
```

The first fights every preset 16 times with AI on both sides; aim for the player's side to win roughly 35 to 65% of them. The second plays it.

## A tour of duty

Write a tour in `config/tours/<anything>.toml`, in the format of `content/data/tours.toml` (the full list of keys is in the docstring of `tour/model.py`). A tour with the id of a shipped one replaces it. A tour is a `[[tour]]` with its flagship, fleet budget, reinforcement calls and the classes Starfleet can send, then one `[[tour.stop]]` per battle:

```toml
[[tour.stop]]
id = "ambush"
title = "Romulan ambush"
system = "Galorndon Core"
chart = [0.66, 0.40]      # where it sits on the patrol chart
transit = 140             # cycles of travel before it: field repairs happen on the way
eta = 200                 # how long Starfleet's reinforcements take to get here
officer = "spock"         # who gives the briefing
briefing = "..."
enemies = ["romulan.bp", "romulan.bp"]

[[tour.stop.choice]]      # a decision in the Ready Room
label = "Refit at the starbase"
consequence = "..."
refit = true
transit = 360
flags = ["refit"]
```

A stop can add later waves (`[[tour.stop.wave]]` with `ships`, `after_clear` and/or `at`, and `if_flag` or `unless_flag`), add or drop enemies when a flag is set (`[tour.stop.add]`, `[tour.stop.drop]`), set a flag when it is won (`win_flag`), and put friendly ships on the field (`friends = ["federation.sb"]`). On a `finale = true` stop, losing those friends loses the tour. A misspelt class is reported on the tour list rather than crashing the game. Check a tour's difficulty with `begin --tour-test 8`; the officers win the shipped tours roughly a third to all of the time.

## Rules

Every tunable number is a field of `Rules` in `sim/rules.py`. To try a change without editing the defaults, build a modified copy, `DEFAULT_RULES.with_changes(beam_kill_max=0.7)`, and pass it in a `BattleSetup`. Mark a new field [E] if it isn't from Begin.

## AI behaviour

There are three levels, from least to most code:

- **Weapon colours.** Each faction's `colors` in `factions.toml` sets how its weapons look on the map: `phaser` and `torpedo` as `#RRGGBB`, and `phaser_style` as `beam` or `pulse`. The manual's "Who fired what" page draws its legend from the same values.
- **Personality and doctrine.** Faction personality ranges are in `factions.toml` and tactics are in `doctrines.toml`, such as weapon preferences, focus fire, point-defense posture, cloaking and surrender. Changing these needs no code.
- **Constants.** The `AI_*` constants at the top of `ai/captain.py` set distances, angles and thresholds. Tag a new one [E] with a short reason.
- **Decisions.** `AICaptain.think` runs `_strategy` (morale, retreat, last stand, target) once a cycle, and `_tactics` at the captain's reaction speed; `_tactics` follows any ally orders (`_standing_orders`), then calls `_shields`, `_cloak`, `_weapons` and `_maneuver`. Each returns commands built with `self._cmd(...)`, which stamps them with AI authority. Add to the relevant method, and check the result with `begin --balance` and the matchup tests.

`OfficerBrain` (`crew/officers.py`) subclasses `AICaptain`, so improvements to the captain carry over to the officers. The officers keep their own limits: they never change your target, retreat or surrender.

## A new command

1. Subclass `Command` in `sim/commands.py`. Implement `validate` (raise `Rejected("why")` when it can't be done now) and `apply`, and return the channels it controls from `channels()` so the captain's hold applies to it.
2. Teach the console the words: add the verb and its synonyms to `VERBS` in `console/parser.py`, and write a `_v_<verb>` method that reads the tokens and appends the command to the result.
3. Write a manual page for it (below) and add a parser test in `tests/test_manual_commands.py`.

If an officer should be able to use it, map it to a station in `station_of` in `crew/officers.py`.

## A HUD panel

Subclass `Panel` in `ui/hud.py`. Override `draw(surf, rect, hud)`, or for a tab, `body(surf, rect, y, hud)` and `tab_label(hud)`. `hud` is the `BattleScene`: read `hud.obs` (the side's Observation), `hud.player` (your ship) and so on, and act through its methods, which submit commands. Use the widgets in `ui/widgets.py` and the colours and fonts in `ui/theme.py`. Then add the panel to `BattleScene.panels`, or as a tab to `self.side_tabs`.

## Manual pages

Each page is a Markdown file in `src/begin/assets/help/` with front matter:

```
---
title: Torpedoes
category: Weapons
aliases: tor, torp, fire torpedoes
summary: One line for lists and search.
see: fire, lock, load
order: 20
---
```

Inside a page:

- `[[topic]]` links to another page;
- a fenced block tagged `console` makes clickable example commands;
- `{{coach}}` and the other blocks in `help/coach.py` insert live content.

To change a page without touching the bundled ones, put your version in `config/help/` with the same file name. Changes show up the next time the page opens.

## Officers

`content/data/officers.toml` gives each officer:

- a station, plus the stations they advise on;
- the aliases you can address them by;
- personality overrides;
- the persona sent to a language model;
- offline lines for each event, with `{target}`, `{ship}`, `{captain}` and `{n}` filled in. The `bridge`, `bridge_released`, `bridge_target` and `bridge_torpedoes` lines are used when the officer has command of the whole bridge (`conn <officer>`).

All the lines are original writing; keep it that way (see [LICENSING.md](../LICENSING.md)).

## Enemy captains and hails

A race's captains take their `temperament` from `factions.toml` (`temper`: 0 cowed by losses, 1 enraged by them; `obstinacy`: how hard they are to talk round at the start; `deviation`). What they watch, and how a hail is answered, lives in `sim/systems/disposition.py`: the shock each event deals, how fast fear and anger build and fade, and the odds of a demand being accepted. Their words come from `content/data/hails.toml`, one table per race over `[default]`; a player's `config/hails.toml` is read over it. `crew/hails.py` reads the captain's words (keywords, or the language model) and puts the answer into words, and `ui/comms_view.py` draws the comms card and the mood marks.

## Crew collaborations and projects

Spock and Seven's tachyon detector is the first of these, and the pattern is meant for more. It has two halves:

- **The project** (`sim/projects.py`): a `ProjectDef` in `PROJECTS` says how long the work takes with a full crew and what finishing it does, for example `load_special_round`, which puts one round of a `special` design into a tube, or `configure_deflector`, which leaves the dish set up for the rest of the battle. A lasting result like the deflector sets `is_ready` (so it isn't built twice) and `use` (the command an officer runs when asked again). The simulation knows nothing about officers, so the console command `design <project>` works with or without them.
- **The collaboration** (`crew/collaborations.py`): a `Collaboration` in `COLLABORATIONS` names the officers, the phrases that set it off when the captain talks to one of them, and the lines each says when work starts and when it is done (`{tube}` is filled in). The Bridge checks these before anything else, so they work offline and with a language model.

Add a help page for each new project, and a coach tip in `help/coach.py` if there is a situation that calls for it.

## Officer objectives

A standing objective ("disable their shields") has two halves, like collaborations:

- **The record** (`sim/objectives.py`): `SetObjective` and `EndObjective` store and end it on the ship, so it replays with the battle. Add the goal to `GOALS`.
- **The plan** (`crew/objectives.py`): a planner function in `PLANNERS` turns the objective into ordinary commands each time the crew thinks, and issues `EndObjective` with `done` or `impossible` and a reason. While an objective runs, the crew's routine station work leaves targeting and offensive fire to it.

The Bridge reports progress (`objective_progress`, `objective_done` and `objective_failed` lines in `officers.toml`) even when chatter is off.

## A language model provider

Write a class with a `name` and `complete(system, messages) -> str` in `llm/providers/`. Raise `LLMError` with a readable message on failure. Then add a branch for it in `make_provider` in `llm/providers/base.py`. Read API keys from environment variables only, never from settings. `post_json` in `base.py` handles plain HTTP, including bypassing the proxy for local hosts. The officers, threading and command handling need no changes.
