# Technical plan

## What we are building

A real-time, pausable, 2D remake of *Begin 2.0* in Python 3.11+ and Pygame-ce. Every session is one engagement. The tactical depth comes from Begin's rules (energy budget, directional shields, phasers that hit everything in the cone, led torpedoes with proximity fuses, slow homing probes, crew-driven repair, personality-driven captains); the remake adds a modern tactical console, subsystem targeting, a ship computer (autoload, point defense, fire control), smarter but still Begin-flavored AI, and optional officer delegation and LLM characters.

## Major decisions

| Decision | Choice | Why |
|---|---|---|
| Time | Fixed 10 ticks per cycle, 1 cycle = 1 s at 1×; render decoupled with an accumulator | Begin's cycle maps naturally onto a second of real time, and 10 ticks mirrors 1.65's 10 sub-cycles |
| Authority | A single `World` owns all mutable state; everything else submits typed `Command`s and reads `Event`s and `Observation`s | Keeps player, AI, computer and officers on identical rules and makes replays trivial |
| Commands | Dataclasses validated against the current state, executed at tick boundaries, logged with tick + issuer | Same path for every controller; recorded logs replay deterministically |
| Events | Plain dataclasses appended to a per-tick list; consumers (renderer, log, AI memory, debrief) read them | Simple, inspectable, no event sourcing |
| Randomness | One seeded `random.Random` for the simulation, separate seeded streams per AI brain | Deterministic headless battles and replays |
| Ship systems | Small first-party `System` classes (reactors, drives, shields, phaser banks, tubes, launchers, sensors, computer, cloak, tractor, transporters…) with a common contract (health, location, tick, power demand, observation) | Adding a weapon or system means one class plus data |
| Content | TOML files for ship classes (including hull polygons, subsystem locations, mount arcs), ordnance, factions, doctrines, officers, presets | Data-driven and hand editable |
| Damage | "Remake" model: Begin 1.65 shield absorption, a structural hull pool, and location-aware subsystem damage with targetable subsystems; "Classic 1.65" kept as a rules profile | Lets players disable ships without destroying them while keeping Begin's shield economy |
| AI | Layered: reflexes every tick, tactical every cycle (Begin's decoded scoring as baseline utilities), morale/strategy every few cycles; personality vector + faction doctrine + computer sophistication; every decision writes a trace | Begin's feel, more texture, explainable behavior |
| Automation | Ship computer functions (autoload, point defense, fire control) issue ordinary commands with `COMPUTER` authority; captain commands hold their channel against lower authorities | No privileged code paths, no AI fighting the player |
| Rendering | Pure Pygame-ce 2D: procedural hull polygons, antialiased lines, additive glows on small cached surfaces | Meets the restrained-console visual brief at 60 FPS |
| LLM | Optional provider interface, background thread, tool calls mapped to the same commands; offline rule-based intent parser by default | Game is complete without any network |

## Milestones (we keep the game runnable after each)

- **A — foundation:** project, data import, world, helm physics, power, fixed-step loop, tactical map with camera, selection, basic phasers/torpedoes, HUD shell.
- **B — Begin combat:** directional shields, full phasers/torpedoes/probes, energy, damage, repair, sensors, class differences, subsystem targeting, autoload, pause and speeds, console parser.
- **C — opponents and computer:** AI captains (reflexes, targeting, fire control, maneuver, morale), doctrines, personalities, point defense, automatic fire, multi-ship battles, quick/preset/custom setup, headless AI tournaments.
- **D — presentation:** scan and damage-assessment views, effects polish, transitions, sound (procedurally synthesized), performance validation, screenshots.
- **E — crew:** stations with manual/assisted/delegated modes, officer policies with personalities, captain override, LLM adapters, character profiles.
- **F — Begin 2.0 extras:** cloak, tractor, docking, transporters and boarding, fleet groups and ally orders, more presets, balance passes.
