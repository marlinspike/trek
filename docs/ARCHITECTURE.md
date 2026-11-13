# Architecture

The game has three layers. The simulation (`sim/`) owns every fact about the battle and knows nothing about pygame. The session (`session/`) plays one battle for a captain: it runs the clock, takes orders typed, spoken or clicked, runs the officers, the hails and the language models, and says what happened as plain news. The screen (`ui/`) presents a session and nothing more. Everything outside the simulation uses one of two paths into it: it reads a side's picture of the battle (an `Observation`), or it submits commands. That covers the screen, the console, the AI captains, the ship computer and the officers. The player, the AI and the officers therefore play by exactly the same rules, and a battle runs the same with or without a window.

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
         session/battle.py    BattleSession: clock, console, officers, hails, models ─► News
             ▲ Session protocol (session/interface.py), the only door the screen uses
         ui/battle_scene.py   map, HUD panels, console line, manual, sound (parts in ui/battle/)
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

**The Borg** [E] are a faction with `collective` rules (`content/schema.py` `CollectiveRules`), and their behaviour lives in its own modules rather than in the shared systems:

- `sim/collective.py` covers the hive's memory (`Mind`), adaptation per weapon family and phaser frequency, what each side has learned (`Insight`, `Survey`), the vinculum relay, dormancy, chain reactions and drones aboard. `damage.py` asks `collective.incoming` for the multiplier on every hit and calls `collective.learn` afterwards.
- `sim/away.py` runs away teams, by shuttle or transporter, through their phases (`AwayOp`) and tasks.
- `sim/systems/sensors.py` covers plasma trails from a damaged drive at warp, the sweep, and the trail-following seeker. Fire from a `cloak_fire` class's cloak shows only the flash.
- `sim/systems/disposition.py` answers a hail to a hive with a refusal or silence, and never with terms.

`Observation` exposes all of this to the UI and the crew: `is_hive`, `adaptation`, `weak_point`, `dormant`, `away_ops`, `plasma`, `venting` and `plasma_fresh`. `HiveEvent` carries the moments. `crew/borg_talk.py` turns them into what the officers say, even with chatter off. On the map, `ui/hive_marks.py` draws adaptation rings, dormant veils and core-critical rings, and `ui/stealth.py` draws our ship under her cloak, plasma trails, exhaust fixes and seekers.

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
| `tours.toml` | The shipped tours of duty. |
| `hails.toml` | Enemy captains' offline lines, by race and mood. |
| `wheel.toml` | The command wheel's slices for an enemy, an ally and our own ship, each a console line. |
| `alerts.toml` | The lines `alert red`, `yellow` and `green` run. |

`content/loader.py` reads them into the typed dataclasses in `content/schema.py` (`ContentDB`), checks cross-references, and supports `base = "<class id>"` so a variant class lists only what differs. `battle.py` turns a `BattleSetup` (fleets of `ShipSpec`s, a seed, rules) into a `Battle`: it places the ships, rolls each captain's personality, and attaches the controllers. `presets.py` and `quick_battle` make setups.

## Controllers

A controller has a `side`, a `period` (ticks between decisions) and a `phase` (an offset, so controllers don't all think on the same tick). Its `think(obs)` returns commands, which the world executes at once.

- **AICaptain** (`ai/captain.py`) thinks every 2 ticks. Each decision covers strategy (target choice, retreat, last stand), then shields and cloak, weapons, and manoeuvre. Begin's decoded scoring is the baseline. Personalities (`ai/personality.py`) and doctrines change the weights. Each decision is written to a short trace (`ai/trace.py`) for debugging.
- **ShipComputer** (`ai/computer.py`) runs every tick for every ship. It handles autoload, point defense against ordnance in flight, and Assisted or Automatic fire, all at computer authority.
- **Crew** (`crew/officers.py`) runs an `OfficerBrain`, an AICaptain limited to one station, for each station the player has delegated. It keeps only the commands that belong to that station. An officer at the helm flies with `crew/helm.py`: `plan_helm` predicts the ship's path under a spread of helm orders with its real turn and acceleration limits and scores each against incoming torpedoes, the range the weapons officer wants and the shield facing the enemy. `Crew.activity` reports what each officer is doing (helm plan, objective step and progress); `ui/officer_view.py` draws it as the activity panel and the map overlays, and `Bridge._callouts` turns new steps into spoken lines.

## Officers and language models

`crew/conversation.py` (`Bridge`) handles talking to the officers. It decides who is addressed, answers offline from the battle state (with help from `help/coach.py`), keeps rapport (`crew/characters.py`), and builds the system prompt when a language model is configured. The patterns that recognise what the captain means (an order, a handover, praise, a question) are in `crew/intents.py`; the officers' running commentary on the battle is `crew/chatter.py`, mixed into `Bridge`; each station's report and the situation summary given to the model are in `crew/station_reports.py`. `llm/reply.py` reads a model's JSON answer, however mangled, for the officers, the hails and the translator alike. Requests go through `llm/service.py`, a small thread pool that `BattleSession.update` polls every frame, so the battle never waits for the network.

The providers (`llm/providers/`) share one `complete(system, messages) -> str` method. `llm/routing.py` can put an optional second model, for character voices, behind the same method: `RoutedProvider` reads who asked (the request's tag, which `LLMService` sets in `llm.usage.caller`) and sends enemy captains' and officers' flavour lines to it by situation, faction and officer, falling back to the main model on failure. The console, named orders and judgements never route there. The session passes a `faction_of` callback so the router never touches the world. Anthropic uses the official SDK. OpenAI and OpenRouter share an OpenAI-compatible client, and Ollama talks to the local server's `/api/chat`. The commands in a reply go through the same console parser as typed ones.

`console/translator.py` (`Translator`) turns plain English typed at the console into commands. `BattleSession._run_one` (`session/console.py`) parses every line first, and only a line the parser rejects (or every line, in `always` mode, or the answer to a clarifying question) goes to the model, on its own `LLMService` worker. The reply's commands are validated with the parser (`BattleSession._would_run`, `session/orders.py`) before any runs; a rejected one is sent back once with the parser's error.

## Game and screen: the session

The screen never holds the game. `BattleSession` (`session/battle.py`) plays one battle and is complete without a window: `tests/test_architecture.py` plays one headless, typing orders and stepping the clock. It is split by concern into mixins, each type-checked against the state declared in `session/state.py`: `console.py` (typed lines, printouts, the chart, the translator), `orders.py` (named orders and their checks), `comms.py` (talking to officers, hails), `command.py` (alert conditions, recording, command style) and `voices.py` (who speaks, read-backs, an officer's proposals). `debrief.py` reduces the end of a battle to plain records, `prefs.py` holds how much of the bridge the captain wants, `models.py` builds the language-model service from settings, and `hit_report.py` turns a hit into words.

The session owns the clock: `update(dt, rate)` adds battle time and steps the world in fixed ticks, at most 12 per call, and returns how many it stepped. It says what happened by publishing **news** (`session/news.py`): small frozen records such as `Line` (a log line, with a tone), `Voice` (an officer speaking), `Cue` (a sound), `Printout`, `Prompt`, `Show` (open an overlay), `Request` (something only the screen can do, like changing the zoom) and `Ticked` (the tick's events). Tones are words like `"warn"` or `"good"`; the screen maps them to colours (`ui/battle/common.TONE_COLOR`), so the session never names a colour. News published before anyone subscribes is kept and delivered to the first subscriber.

**The contract.** The battle screen is typed against `Session` (`session/interface.py`), a `Protocol` that lists every attribute and method a presenter may use, rather than against `BattleSession`. mypy rejects any call the protocol doesn't list, and `BattleSession` is checked to honour it. What the screen shows comes from the `Observation` (which carries the outcome, pending scans, repairs, boarders, names, and the side's read of each enemy captain), and what it changes goes by order: `submit(cmd)`, `say(text)` and the named helpers.

**Orders that travel.** `session/wire.py` turns every `Command` into a dict of JSON values and back, driven by the dataclass fields and their type hints, so a new command needs no code there; anything malformed is refused with `WireError`, never guessed at. Because the simulation is deterministic, the same orders at the same ticks give the same battle, and a test replays a battle from orders sent through JSON and compares the final state. That is the basis for:

- a **networked session**: each machine holds a mirror of the world and exchanges orders in lockstep, presenting it through the same `Session` protocol;
- a **replay**: the world's command log, fed back through the same clock;
- a **new presenter** (a web front end, a GPU renderer, a test harness) that implements nothing but the screen.

**Game modes.** `modes.py` registers the ways to start a battle (`Mode(key, title, blurb, hotkey, make)`). The main menu builds its buttons and hotkeys from `MODES`, so a new mode is one `register(...)` call (see EXTENDING).

**The rules, enforced.** `tests/test_architecture.py` fails the build when the layering is crossed:

1. nothing outside `begin.ui` imports pygame or `begin.ui`, so the game runs without a screen;
2. `begin.ui` never imports the world, its systems, the AI, the language models or the session's machinery at run time (type-only imports are allowed); only the composition root (`ui/app.py`, `ui/battle_scene.py`) builds a session;
3. no UI code reads `.world`;
4. the session speaks in tones, never colours;
5. every command survives the wire, and a battle replays exactly from orders sent as JSON.

So the AI, the rules, the officers, a game mode or a network link can change without touching the screen, and a new screen can be written without touching the game.

## The front end

`ui/app.py` opens the window through a presenter (`ui/present.py`) and runs the loop at 60 FPS. The scenes draw each frame on `presenter.screen` in logical pixels, and the presenter shows it:

- `GLPresenter` (`ui/glpresent.py`) opens a high-density OpenGL window with moderngl. The screen surface is a `gfx.Canvas` at the display's real density (2 on a Retina Mac), so everything is drawn sharp while the layout stays in points. Each frame is uploaded as a texture and drawn by one shader that adds a bloom to the weapon light the map offers (`gfx.offer_light`: the glow layer under beams and blasts, shrunk through mipmaps, blurred and added back) and a slight vignette at the edge of the map (`gfx.set_stage`). Text and panels are never bloomed. The GPU work lives in `Compositor`, which needs no window, so `tests/test_gpu_present.py` checks it on an offscreen context.
- `SoftwarePresenter` is pygame's own window at density 1, as before. Headless runs, screenshots and the tests use it, and `open_presenter` falls back to it whenever the GPU path fails or OpenGL is drawn on the CPU.

`gfx` (`ui/gfx.py`) is what makes density invisible to the rest of the UI: a `Canvas` stores `SCALE` times the pixels but answers in logical ones, `gfx.draw` and `gfx.transform` scale coordinates and widths, and text is rendered at the real size. On Windows the presenter asks SDL for per-monitor DPI scaling, so Windows behaves like macOS: the window in points, the frame in pixels. The renderer is chosen by the `renderer` setting (or `--renderer`) and can only change at a restart, so the Display section of Settings offers one (`DisplayControl`, `relaunch_command`).

`App` swaps between `MenuScene` (`ui/menu_scene.py`: game modes, presets, Custom setup, and Settings, which is `ui/settings_hub.py`: every section of `config/settings.json` plus officers' names and styles, written to `officers.toml` a line at a time by `crew/officer_file.py`; it reaches the language models only through `session/models.py`), `TourScene` (tours of duty, between battles) and `BattleScene`.

`BattleScene` (`ui/battle_scene.py`) presents a session. Given a `Battle` it builds a `BattleSession`; given anything that honours `Session` it presents that. It subscribes to the news and turns it into log lines, subtitles, sound, printouts and overlays, and it mixes in its other parts from `ui/battle/`: `input.py` (keys and mouse, with the single-key controls as tables), `bridge.py` (the console line, completion and the order preview), `voice.py` (push-to-talk), `comms.py` (the hail prompt and buttons) and `render.py` (drawing). `ui/battle/state.py` declares the state they share; scene attributes such as `paused` and `obs` read and write the session's through `Forward` descriptors, so there is one source of truth.

Each frame it tells the session whether the captain is typing or a screen is open, calls `session.update(dt, speed)`, and keeps the previous tick's snapshot so motion is drawn smoothly between ticks. Each frame it draws:

- the tactical map (`ui/tactical.py`, with `camera.py`, `hulls.py`, `effects.py`, `beams.py` (phaser and disruptor shots), `torpedo_art.py` (rounds in flight by race) and `starfield.py`), which also keeps torpedo trails, inbound-torpedo markers and the target-lock animation. Zoomed out, a ship smaller than `hulls.ICON_MAX_PX` is drawn as one smoothed silhouette (`hulls.hull_icon`: a single outline round the union of her shapes, supersampled and cached by class, heading and scale) so overlapping shapes don't turn into a knot of lines. Zoomed in, a ship class listed in `tactical.SHOWPIECE` is drawn from its baked sprite instead of its outline;
- the HUD panels (`ui/hud.py`): Own Ship, Target, Weapons, and a tabbed Contacts/Fleet/Crew column. Shown numbers go through `ui/tween.py`, which eases them and flashes changes; `hud_detail` (or the mouse over a panel) decides whether every number is shown;
- the console and its log;
- any open overlay: Begin's text reports (`console/reports.py`) or the manual (`ui/manual.py`, which renders `ui/markdown.py`).

### Weapon effects, hits and sound

The simulation decides every blow within one tick; the front end spreads what happened over the next fraction of a second so it reads the way it would on screen. The pieces fit together like this.

`sim/events.py` carries what the drawing needs: `PhaserFired` names the bank that fired and its `power` (the bank's charge as a share of full, set in `sim/systems/phasers.py`), `ShieldHit` names the struck facing, its strength left and whether it collapsed, `HullHit` the damage that got through, and `SubsystemDamaged` the system hit.

`ui/beams.py` draws a shot. A `Beam` follows a fixed timeline (`Beam.timeline()`): the firing bank glows as it charges (0.12 s, skipped for point defence), a bright tip races out to the target (0.07 s), the beam holds for a time that grows with its power, then fades. It is drawn in three layers: a soft wide glow, a coloured body and a white-hot core, so a full-power volley looks heavier than a weak or point-defence shot. A `Stop` cuts the beam where the blow really landed: at the target's shield circle if the shield held, or at the hull if the hit got through. Races whose `colors.phaser_style` is `pulse` (Klingons and Orions) fire disruptor bolts instead of a steady beam, real bolts that fly the distance one after another.

`ui/torpedo_art.py` draws torpedoes in flight. Each faction's look (`colors.torpedo_style` in `factions.toml`: photon, disruptor, plasma or pulse) is its own function; `round_size` scales a round by its warhead and keeps it a few pixels across at any zoom.

`ui/effects.py` (`Effects.ingest`) turns a tick's events into effects. It reads the shots first, because the simulation emits a shot's hits before the shot itself, and records in `Effects.landing` how long each shooter's beam takes to reach each target. Everything that a blow causes then waits for that delay: the shield flash on the struck arc, the sparks of a collapse, hull fire and venting, a system blast, the map's jolt when our own ship is hit hard, and the sounds. Torpedo blasts are sized by yield, and a launch shows a muzzle flash at the tube.

Light is added rather than painted. `TacticalView` keeps one black `_glow` surface the size of the map, the effects draw their glow into it (`blast.add_light` stamps cached soft halos), and it is blitted onto the map with `BLEND_RGB_ADD`, so overlapping light brightens instead of greying. Crisp lines (beam cores, rays, rings) go on the alpha overlay as before, drawn with `gfx.draw.aaline`/`aacircle` at sub-pixel positions so beams are straight strokes and torpedo cores round; `blast.halo` supersamples its discs so small halos are round too.

Weapon light also falls on ships. Each frame `Effects.lights(cam)` lists the light sources on screen (a beam's muzzle and impact, blast rings, glows, flashes) as `Light(x, y, reach, color, k)`. `TacticalView._light_on` sums them at a ship (fading with the square of the distance from her edge, capped at `HULL_LIGHT_MAX`) and `_light_art` adds a tinted copy of her art or hull icon with `BLEND_RGB_ADD`, cached by art and colour step. `theme.shadow` puts a soft blurred rim under panels and cards. Both follow `gfx.LIGHTING`, which the *Light and glow* switch (settings `bloom`) sets.

`TacticalView` also marks rounds heading for us (`_inbound`: within 9,000 units and pointed at us within 14°) with their fuse ring, or with a chevron at the edge of the map when they are off screen, and plays the incoming warning once per round. The jolt (`hud jolt on|off`) offsets the camera for a moment after a heavy hit and settles quickly.

`ui/audio.py` synthesises every sound at start-up from plain sample arithmetic (no recordings, no numpy): phaser charge and ray, torpedo tube thunk, incoming whoosh, shield, collapse and hull hits, the three-whoop red alert, lock chirp, console confirm and deny tones, hail whistles, and the ship's hum. Each sound also has a low-passed copy that is played instead when the source is far away (level below `FAR_LEVEL`). `Audio.events` turns events into sounds, panned by position and delayed by `Effects.landing` (held in `Audio._later` and released by `Audio.tick`). The hum loops on a reserved channel, follows the warp setting, and ducks under the loud sounds in `LOUD`; its level is `settings.hum` (`sound hum off|on|0-100`). Nothing plays when sound is off.

`MenuScene` draws the starfield and the flybys from `ui/showpiece.py`, which plans each pass as a straight line across the screen at one heading, fires phasers and torpedoes along it and draws them with additive glow. The ship sprites it uses are PNGs in `assets/ships/`, baked by `tools/render_ship.py` (which needs numpy; the game does not).

Every other class has baked art too, in `assets/ships/fleet/`, made by `tools/render_fleet.py` from the class's hull in `hulls.toml`: each shape becomes part of a height field (domes, saucers, bevelled slabs, nacelle capsules, raised details), lit and plated in its faction's colours, one sprite per 30° of heading on a canvas centred on the hull origin. `ui/fleet_art.py` loads them (`fleet_image`), and the tactical map (`TacticalView._sprite`, own ships and identified contacts) and the tour screens (`tour_art.ship_art`) draw a class with its sprite when there is one and fall back to the outline when there isn't. Change a hull and run `PYTHONPATH=src python tools/render_fleet.py <class-id>` to rebake it.

Panels subclass `Panel` and draw themselves into a rectangle, using small immediate-mode widgets from `ui/widgets.py`. Colours and fonts come from `ui/theme.py`.

Words never run off the screen or out of their panel. Anything whose length isn't fixed (a fleet's ships, a description, a reason, a tool tip) goes through `theme.wrap` (lines that fit a width, with a no-break space keeping "3 × Dreadnought" together), `theme.para` (draws them, and with `bottom=` stops with an ellipsis when the room runs out) or `theme.fit` (one line, cut with an ellipsis). Buttons make their words a little smaller before they cut them, `UI.choice` rows given `room` tighten up, and map labels stay whole inside the map (a ship off the map is not labelled). The battle's right-hand column needs about 900 pixels of height; on a shorter window `column_panels` moves Weapons, then Target, into the tabs at the bottom (`TabbedPanel.fold`) instead of letting the column run off the screen. `tests/test_text_fits.py` holds this in place: it draws every screen at 1024×640, 1440×860 and 1920×1080 inside `theme.watching()`, which records each line of text and each panel (`theme.frame`, called by `panel`, `shadow`, buttons and tool tips), and fails on any line past an edge or out of its panel.

`console/parser.py` turns Begin's command language into commands. It handles unique prefixes, filler words, ship and subsystem names, ally orders and multi-command lines. Status commands return text instead. Its vocabulary (verbs and their spellings, weapon and system words, the help summary) is `console/vocab.py`, which the officers and the manual use too; `console/tokens.py` reads a line a word at a time; and `console/plain.py` rewrites a captain's plain words into the console's own and splits a line of several orders.

The manual (`help/docs.py`) is a folder of Markdown pages with front matter. Pages in `config/help/` replace or add to the bundled ones. `{{blocks}}` insert live content such as the coach or weapon tables.

## The bridge

How the captain gives orders is layered over the console rather than beside it: the wheel, proposals, alert conditions, recorded orders and voice all end as console lines, so the parser is the one place an order is understood, and the log always shows the line that ran.

- **Readbacks** (`console/readback.py`): `readback(cmd, name_of)` builds the sentence an officer says back from the command's own fields, so it says exactly what will happen; commands without a phrase fall back to `Command.describe()`. `session/voices.py` picks who speaks (the officer at that order's station) and publishes a `Voice`, and the screen shows it as a subtitle and in the log's Bridge column.
- **Proposals** (`session/voices.py`): an officer at a station the captain runs can offer an order, one at a time and at most once a minute per officer; `accept_proposal` and `belay_proposal` answer it. How long it waits, whether it may interrupt typing and whether an urgent one is carried out unanswered depend on the officer's trust.
- **Trust and command styles** (`crew/career.py`): `Career` is a view on settings' `career` (points per officer, ribbons per style). Levels are Green 0, Steady 10, Trusted 30 and Veteran 70. A `Style` is a promise checked against what the captain does during the battle (`session/command.py`).
- **Alert conditions and recording** (`session/command.py`): `alert` runs the lines of `content/data/alerts.toml` (or `config/alerts.toml`); `record` keeps the lines that ran, tidies them (`tidy`: displays and repeats dropped, pauses of two cycles or more kept as `wait N`) and writes them to `config/orders.toml`. Plain English that the model turned into commands is remembered in `config/phrasebook.json`.
- **How much of it** (`session/prefs.py`): `BridgePrefs` holds `full`, `quiet` or `classic` and each part's switch; everything above asks it before speaking, proposing or slowing time.
- **Tactical focus** (`BattleScene._focus_update`): while the captain types, the screen eases the rate it passes to `session.update` down to a quarter (or to a pause), until Enter or eight idle seconds; it also tells the session the captain is typing (`captain_typing`), so proposals wait or come as a chip.
- **Pointing and completion** (`console/pointing.py`, `ui/battle/bridge.py`): with the mouse on a ship, pointing words ("her", "that one") after a word that takes a ship are replaced by her name before parsing; Tab completes from the vocabulary, the ships, the officers and the orders. The preview line under the console is the readback of what Enter would run, parsed but not executed.
- **On the screen**: `ui/wheel.py` (`CommandWheel`, slices from `wheel.toml` via `load_wheels`, the captain's file winning kind by kind), `ui/order_marks.py` (the captain's standing orders drawn on the map, and the ghost of the typed line), and `ui/orders_panel.py` (the Orders tab's cards).
- **Voice** (`voice/`, `ui/microphone.py`, `ui/battle/voice.py`): `Recorder` captures 16 kHz mono through SDL while the push-to-talk key is held and returns a WAV; an `Engine` from `voice/engines.make_engine` (`MacSpeech`, `WhisperLocal`, `WhisperServer`, `CloudWhisper`) turns it into text on a worker thread, and the text is typed into the console as if by hand. `MacSpeech` builds `mac_transcribe.swift` into `config/voice/` the first time; a failure is a `VoiceError` shown as it is.

## Tours of duty

A tour links battles. `tour/model.py` reads tours from `content/data/tours.toml` and `config/tours/*.toml` into frozen `TourDef`s (stops, choices, waves). `tour/state.py` holds how a tour stands: a `ShipRecord` per ship of the squadron (hull, system damage, crew, magazines, morale, lost or in reserve), the flags set by choices and wins, what the enemy has learned, and the log. `TourState` is saved as JSON after every change.

`tour/run.py`'s `TourRun` joins the two and knows nothing about pygame, so `begin --tour-test` and the tests fly whole tours headless:

1. `launch` applies the transit (field repairs and resupply, or a refit), builds the stop's `BattleSetup` from the squadron, and turns its waves and the Ready Room's reinforcement calls into `Arrival`s.
2. `prepare` writes each record onto its freshly built ship.
3. During the battle, `reinforcement_arrival` adds a Starfleet `Arrival` with an ETA.
4. `finish` writes every ship back, adds prizes and reinforcements, records the result and what the enemy learned, and drafts the log page (`tour/log.py`).

A hive's memory carries between stops [E]. `finish` keeps a share of each `Mind`'s levels, plus our `Insight`'s experience, in `TourState.lessons` (`hive:<faction>|<weapon key>`), and `prepare` puts them back into the next battle. A flagship taken by drones ends the tour with the outcome `assimilated`. A choice with `flagship = "<class>"` rebuilds the flagship as that class (the cloak refit), and while she carries a cloak, every reinforcement call has Starfleet ask why.

Arrivals are part of the simulation (`sim/arrivals.py`): the world places the ships when their time comes and emits `ShipArrived`; `World.on_arrival` lets the battle give them a ship computer and a captain. Waves hold the battle open (`World._check_outcome`), and each wave's lull starts only once the earlier waves are here and beaten.

The screens are `ui/tour_scene.py` (the tour list, the squadron, the Ready Room, the log and the rating) and `ui/tour_art.py` (the procedural patrol chart, the lit ships and the officers' cards). `ui/app.py` starts a stop's battle from the Ready Room and takes the squadron back when the battle scene exits. The officers' voices go through the same `LLMService` as the bridge, in the background, and an entry you have edited is never rewritten.

## Settings

`paths.py` decides where the player's files live: `<project>/config/` in a source checkout, the `Begin config` folder beside a packaged build, or the folder named by `BEGIN_HOME`. `settings.py` reads and writes `settings.json` there. Its sections belong to the parts that use them: `llm` (the officers' model, and `llm.character` for the character voice model, read by `llm/routing.py`), `bridge` (`session/prefs.py`), `voice` (`voice/engines.py`), `career` (`crew/career.py`), and `renderer` and `bloom` (`ui/present.py`, `ui/gfx.py`). API keys are read only from the environment.

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
| Border Incident, 1600×900 | 3 | 0.11 ms | 5.4 ms, 7.2 ms |
| Starbase Defense, 1600×900 | 7 | 0.18 ms | 5.9 ms, 7.6 ms |
| Fleet Action, 1600×900 | 15 | 0.32 ms | 7.0 ms, 10.2 ms |
| Fleet Action, 2560×1440 | 15 | 0.18 ms | 11.2 ms, 13.0 ms |

The weapon effects (charging banks, three-layer beams, additive glow, the torpedo art) cost a few tenths of a millisecond a frame on top of the figures before them (measured 11 November 2026). Drawing at a density of 2 for a Retina screen, with *Light and glow* on, costs about another millisecond a frame in Fleet Action on the same CPU (roughly 15 to 16.5 ms at 2×, measured 12 November 2026); the overlay and glow layers track what was drawn on them and clear only that, which is what keeps 2× affordable. With the GPU presenter the upload and the bloom shader run on the graphics card.

Drawing is nearly all of the frame. The same labels are drawn every frame, so `theme.render` caches finished lines of text and `hulls` caches the hull outlines; without those caches Fleet Action took 12.0 ms to draw at 1600×900 and 18.1 ms at 2560×1440, past the 16.7 ms a frame that 60 FPS allows. A surface returned by `theme.render` is shared, so draw it but never draw on it.

The simulation costs about 0.3 ms a tick for a duel, 1.5 ms with 14 ships and about 8 ms with Begin's limit of 60 (`tools/bench.py` times fleets of each size with AI on both sides; the same machine measured 0.5, 3 and 17 ms before the dodge planner was tuned). The biggest share is enemy captains dodging torpedoes (`AICaptain._dodge`, which plans with the officers' `crew/helm.plan_helm` and tests some ninety candidate helm orders against every round in flight). The planner keeps that affordable without changing a single decision: `_relevant` drops torpedoes that cannot reach the ship under any order, `_danger` skips a torpedo whose flight stays clear of the box round a candidate path, `_path` finishes a settled course as a straight line, and `_miss` works in squared distances. The cost comes in bursts while torpedoes are in the air. Per-tick work that looks at every pair of ships gathers its lists once per tick or per choice rather than once per ship or per contact (`World._escapes`, `AICaptain._scoring_sets`).

## Checking a change

Before a pull request: `ruff check .` (all CI runs), `mypy` (no issues today; keep it that way) and `pytest`. For a change meant to keep behaviour, `begin --tournament 12` and `begin --balance 1` print the same results before and after, since every battle is deterministic; `tools/bench.py` shows whether it changed the speed.
