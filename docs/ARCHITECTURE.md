# Architecture

The game has two halves. The simulation (`sim/`) owns every fact about the battle and knows nothing about pygame. Everything else uses one of two paths: it reads a side's picture of the battle, or it submits commands. That covers the screen, the console, the AI captains, the ship computer and the officers. The player, the AI and the officers therefore play by exactly the same rules, and a battle runs the same with or without a window.

```
             content/*.toml ──► ContentDB ──► battle.build_battle(setup) ──► Battle
                                                                              │
   ┌──────────────────────────────── World (sim/world.py) ◄───────────────────┘
   │  ships, torpedoes, probes, intel, outcome, event list, command log
   │
   │  step():  sensors ─► controllers think(Observation) ─► execute(Command)…
   │           ─► power ─► helm ─► movement and towing ─► ordnance flight and detonation
   │           ─► repair, self-destruct, boarding ─► scans ─► escapes ─► outcome
   │
   ├── Controllers (read an Observation, return Commands)
   │     AICaptain (ai/captain.py)     one per non-player ship
   │     ShipComputer (ai/computer.py) autoload, point defense, assisted/automatic fire
   │     Crew (crew/officers.py)       the player's delegated stations
   │
   └── Front ends (read Observations and Events, submit Commands)
         ui/battle_scene.py   map, HUD panels, console, manual, officers' chat (parts in ui/battle/)
         console/parser.py    Begin's command language ─► Commands
         tools/balance.py     headless runs with AI on every ship
```

## The simulation

**World** (`sim/world.py`) holds all mutable state: ships, ordnance in flight, each side's sensor intel, the outcome, the events since the last read, and a log of every command with its tick and whether it was accepted. `World.step()` advances one tick (a tenth of a cycle) in a fixed order. Everything random draws from seeded streams (`core/rng.py`), so the same setup and the same commands always produce the same battle. The tests and the balance runs depend on that.

**Rules** (`sim/rules.py`) keeps every tunable number in one frozen dataclass. Each field is tagged [R] (decoded from Begin) or [E] (ours). Balance experiments pass a modified copy instead of editing constants in the code.

**Ships** (`sim/ship.py`, built by `sim/factory.py`) are dataclasses made of subsystems: reactors, batteries, drives, shields, phaser banks, torpedo tubes, probe launchers, sensors, transporters, and the optional cloak, tractor and impulse engine. Each subsystem has health and a position on the hull. The systems that act on them are plain functions in `sim/systems/`:

- `power.py`: the energy budget, life support, shield upkeep and weapon charging;
- `helm.py`: turning, acceleration and movement;
- `phasers.py`: arcs and cone fire;
- `ordnance.py`: torpedo and probe flight, fuses and blasts;
- `damage.py`: shields, the hull, crew and subsystem hits;
- `sensors.py`: detection, cloaking and scans;
- `repair.py`: repairs, at a rate set by the class and the surviving crew.

**Commands** (`sim/commands.py`) are dataclasses with `validate` and `apply`. `World.execute` checks that the ship can respond, checks channel holds, validates, logs, then applies. A rejected command raises `Rejected` with a reason, which becomes a `CommandRejected` event, and the captain sees "Unable to comply". Each command carries an `Authority`: computer < officer < AI captain < captain. When the captain gives an order, its channels (helm, phasers, tubes and so on) are held against lower authorities for 8 cycles. That keeps the computer and the officers from undoing what you just did.

**Events** (`sim/events.py`) are small dataclasses: messages, phaser shots, launches, detonations, shield and hull hits, subsystem damage and repair, status changes, contacts and scans. The renderer turns them into effects. The console log prints the messages, and the officers comment on them.

**Observation** (`sim/observation.py`) is one side's read-only picture for the current tick: its own ships in full, and contacts and ordnance only as far as its sensors know them. Controllers get nothing else, so an AI can't see a cloaked ship any more than you can.

## Content

The TOML files in `content/data/` describe everything that isn't a rule:

| File | Contents |
|---|---|
| `classes.toml` | Ship classes. Generated from Begin's data by `tools/import_reference_data.py`; the deliberate changes are in the importer's `OVERRIDES`. |
| `hulls.toml` | Silhouettes, internal system positions and weapon mounts with arcs, per class. |
| `ordnance.toml` | Torpedo and probe designs (generated). |
| `factions.toml` | Factions: names, allowed ordnance, Begin's nation dogma, computer sophistication and captain competence. |
| `doctrines.toml` | Faction tactics: weapon preferences, focus fire, point defense, cloaking. |
| `officers.toml` | Bridge officers: stations, personalities, LLM personas and offline lines. |
| `presets.toml` | The curated battles. |

`content/loader.py` reads them into the typed dataclasses in `content/schema.py` (`ContentDB`), checks cross-references, and supports `base = "<class id>"` so a variant class lists only what differs. `battle.py` turns a `BattleSetup` (fleets of `ShipSpec`s, a seed, rules) into a `Battle`: it places the ships, rolls each captain's personality, and attaches the controllers. `presets.py` and `quick_battle` make setups.

## Controllers

A controller has a `side`, a `period` (ticks between decisions) and a `phase` (an offset, so controllers don't all think on the same tick). Its `think(obs)` returns commands, which the world executes at once.

- **AICaptain** (`ai/captain.py`) thinks every 2 ticks. Each decision covers strategy (target choice, retreat, last stand), then shields and cloak, weapons, and manoeuvre. Begin's decoded scoring is the baseline. Personalities (`ai/personality.py`) and doctrines change the weights. Each decision is written to a short trace (`ai/trace.py`) for debugging.
- **ShipComputer** (`ai/computer.py`) runs every tick for every ship. It handles autoload, point defense against ordnance in flight, and Assisted or Automatic fire, all at computer authority.
- **Crew** (`crew/officers.py`) runs an `OfficerBrain`, an AICaptain limited to one station, for each station the player has delegated. It keeps only the commands that belong to that station. An officer at the helm flies with `crew/helm.py`: `plan_helm` predicts the ship's path under a spread of helm orders with its real turn and acceleration limits and scores each against incoming torpedoes, the range the weapons officer wants and the shield facing the enemy. `Crew.activity` reports what each officer is doing (helm plan, objective step and progress); `ui/officer_view.py` draws it as the activity panel and the map overlays, and `Bridge._callouts` turns new steps into spoken lines.

## Officers and language models

`crew/conversation.py` (`Bridge`) handles talking to the officers. It decides who is addressed, answers offline from the battle state (with help from `help/coach.py`), keeps rapport (`crew/characters.py`), and builds the system prompt when a language model is configured. The patterns that recognise what the captain means (an order, a handover, praise, a question) are in `crew/intents.py`; the officers' running commentary on the battle is `crew/chatter.py`, mixed into `Bridge`; each station's report and the situation summary given to the model are in `crew/station_reports.py`. `llm/reply.py` reads a model's JSON answer, however mangled, for the officers, the hails and the translator alike. Requests go through `llm/service.py`, a small thread pool that `BattleScene.update` polls every frame, so the battle never waits for the network.

The providers (`llm/providers/`) share one `complete(system, messages) -> str` method. Anthropic uses the official SDK. OpenAI and OpenRouter share an OpenAI-compatible client, and Ollama talks to the local server's `/api/chat`. The commands in a reply go through the same console parser as typed ones.

`console/translator.py` (`Translator`) turns plain English typed at the console into commands. `BattleScene._run_one` parses every line first, and only a line the parser rejects (or every line, in `always` mode, or the answer to a clarifying question) goes to the model, on its own `LLMService` worker. The reply's commands are validated with the parser (`BattleScene._would_run`) before any runs; a rejected one is sent back once with the parser's error.

## The front end

`ui/app.py` opens the window and runs the loop at 60 FPS. It swaps between `MenuScene` (presets, Quick and Custom setup), `TourScene` (tours of duty, between battles) and `BattleScene`.

`BattleScene` (`ui/battle_scene.py`) holds the scene's state and frame loop, and mixes in its other parts from `ui/battle/`: `input.py` (keys and mouse, with the single-key controls as tables), `console.py` (typed orders, printouts, the chart and the manual), `orders.py` (named orders and the translator), `comms.py` (officers and hails) and `render.py` (drawing). `ui/battle/state.py` declares the state they share, so each part is type-checked against it.

It adds frame time × speed to an accumulator and steps the world in fixed ticks, at most 12 per frame. It keeps the previous tick's snapshot so motion is drawn smoothly between ticks. Each frame it draws:

- the tactical map (`ui/tactical.py`, with `camera.py`, `hulls.py`, `effects.py` and `starfield.py`), which also keeps torpedo trails and the target-lock animation. Zoomed in, a ship class listed in `tactical.SHOWPIECE` is drawn from its baked sprite instead of its outline;
- the HUD panels (`ui/hud.py`): Own Ship, Target, Weapons, and a tabbed Contacts/Fleet/Crew column. Shown numbers go through `ui/tween.py`, which eases them and flashes changes; `BattleScene.hud_detail` (or the mouse over a panel) decides whether every number is shown;
- the console and its log;
- any open overlay: Begin's text reports (`console/reports.py`) or the manual (`ui/manual.py`, which renders `ui/markdown.py`).

`MenuScene` draws the starfield and the flybys from `ui/showpiece.py`, which plans each pass as a straight line across the screen at one heading, fires phasers and torpedoes along it and draws them with additive glow. The ship sprites it uses are PNGs in `assets/ships/`, baked by `tools/render_ship.py` (which needs numpy; the game does not).

Every other class has baked art too, in `assets/ships/fleet/`, made by `tools/render_fleet.py` from the class's hull in `hulls.toml`: each shape becomes part of a height field (domes, saucers, bevelled slabs, nacelle capsules, raised details), lit and plated in its faction's colours, one sprite per 30° of heading on a canvas centred on the hull origin. `ui/fleet_art.py` loads them (`fleet_image`), and the tactical map (`TacticalView._sprite`, own ships and identified contacts) and the tour screens (`tour_art.ship_art`) draw a class with its sprite when there is one and fall back to the outline when there isn't. Change a hull and run `PYTHONPATH=src python tools/render_fleet.py <class-id>` to rebake it.

Panels subclass `Panel` and draw themselves into a rectangle, using small immediate-mode widgets from `ui/widgets.py`. Colours and fonts come from `ui/theme.py`.

`console/parser.py` turns Begin's command language into commands. It handles unique prefixes, filler words, ship and subsystem names, ally orders and multi-command lines. Status commands return text instead. Its vocabulary (verbs and their spellings, weapon and system words, the help summary) is `console/vocab.py`, which the officers and the manual use too; `console/tokens.py` reads a line a word at a time; and `console/plain.py` rewrites a captain's plain words into the console's own and splits a line of several orders.

The manual (`help/docs.py`) is a folder of Markdown pages with front matter. Pages in `config/help/` replace or add to the bundled ones. `{{blocks}}` insert live content such as the coach or weapon tables.

## Tours of duty

A tour links battles. `tour/model.py` reads tours from `content/data/tours.toml` and `config/tours/*.toml` into frozen `TourDef`s (stops, choices, waves). `tour/state.py` holds how a tour stands: a `ShipRecord` per ship of the squadron (hull, system damage, crew, magazines, morale, lost or in reserve), the flags set by choices and wins, what the enemy has learned, and the log. `TourState` is saved as JSON after every change.

`tour/run.py`'s `TourRun` joins the two and knows nothing about pygame, so `begin --tour-test` and the tests fly whole tours headless:

1. `launch` applies the transit (field repairs and resupply, or a refit), builds the stop's `BattleSetup` from the squadron, and turns its waves and the Ready Room's reinforcement calls into `Arrival`s.
2. `prepare` writes each record onto its freshly built ship.
3. During the battle, `reinforcement_arrival` adds a Starfleet `Arrival` with an ETA.
4. `finish` writes every ship back, adds prizes and reinforcements, records the result and what the enemy learned, and drafts the log page (`tour/log.py`).

Arrivals are part of the simulation (`sim/arrivals.py`): the world places the ships when their time comes and emits `ShipArrived`; `World.on_arrival` lets the battle give them a ship computer and a captain. Waves hold the battle open (`World._check_outcome`), and each wave's lull starts only once the earlier waves are here and beaten.

The screens are `ui/tour_scene.py` (the tour list, the squadron, the Ready Room, the log and the rating) and `ui/tour_art.py` (the procedural patrol chart, the lit ships and the officers' cards). `ui/app.py` starts a stop's battle from the Ready Room and takes the squadron back when the battle scene exits. The officers' voices go through the same `LLMService` as the bridge, in the background, and an entry you have edited is never rewritten.

## Settings

`paths.py` decides where the player's files live: `<project>/config/` in a source checkout, or the folder named by `BEGIN_HOME`. `settings.py` reads and writes `settings.json` there. The `llm` section configures the officers' language model; API keys are read only from the environment.

## Tools and tests

- `begin --balance N` (`tools/balance.py`) fights every preset N times with AI captains on all ships, including the player's, and prints win rates.
- `begin --tournament N` (`tools/tournament.py`) runs random AI battles.
- `begin --tour-test N` (`tools/tours.py`) flies every tour N times with the officers in command of the flagship and AI captains on every other ship, and prints how many were won.
- `begin --preset ... --cycles N --screenshot file.png` renders a frame headlessly; the README screenshots are made this way.
- `pytest` runs headless tests of the geometry, the rules, commands, the AI, the parser, the manual, the officers and the UI wiring. Tests use a temporary config folder.

## Performance

Measured in the cloud container (software rendering, no GPU, a 2.1 GHz Xeon) with `python tools/bench.py`, which drives the real battle screen headlessly and times the update and the drawing separately:

| Battle | Ships | Update | Draw (mean, 95th percentile) |
|---|---|---|---|
| Border Incident, 1600×900 | 2 | 0.11 ms | 5.8 ms, 8.4 ms |
| Starbase Defense, 1600×900 | 6 | 0.15 ms | 6.0 ms, 8.1 ms |
| Fleet Action, 1600×900 | 14 | 0.23 ms | 7.1 ms, 10.4 ms |
| Fleet Action, 2560×1440 | 14 | 0.18 ms | 11.8 ms, 15.3 ms |

Drawing is nearly all of the frame. The same labels are drawn every frame, so `theme.render` caches finished lines of text and `hulls` caches the hull outlines; without those caches Fleet Action took 12.0 ms to draw at 1600×900 and 18.1 ms at 2560×1440, past the 16.7 ms a frame that 60 FPS allows. A surface returned by `theme.render` is shared, so draw it but never draw on it.

The simulation costs about 0.3 ms a tick for a duel, 0.9 ms with 14 ships and 4 ms with Begin's limit of 60 (`tools/bench.py` times fleets of each size with AI on both sides). At 4× speed that is 40 ticks a second, well within budget even at the limit. Per-tick work that looks at every pair of ships gathers its lists once per tick or per choice rather than once per ship or per contact (`World._escapes`, `AICaptain._scoring_sets`).

## Checking a change

Before a pull request: `ruff check .` (all CI runs), `mypy` (no issues today; keep it that way) and `pytest`. For a change meant to keep behaviour, `begin --tournament 12` and `begin --balance 1` print the same results before and after, since every battle is deterministic; `tools/bench.py` shows whether it changed the speed.
