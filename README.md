# Begin (remake)

A real-time 2D tactical starship simulation in Python and pygame-ce, rebuilt from *Begin: A Tactical Starship Simulation* (Clockwork Software, v1.65 manual with the Begin 2.0 appendix) and the [fireflyk64/begin](https://github.com/fireflyk64/begin) reverse-engineered reconstruction. It is a personal, non-commercial fan project: see [LICENSING.md](LICENSING.md).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
begin                      # or: python -m begin
```

You need Python 3.10 or newer. macOS's system `python3` is 3.9, which is too old, so install a newer Python first (for example from python.org or with `brew install python`) and create the venv with it. On 3.10, `tomli` is installed automatically. Any Python version with a pygame-ce wheel works.

Useful shortcuts:

| Command | What it does |
|---|---|
| `begin --preset border-incident` | Jumps straight into a preset battle (ids are in `src/begin/content/data/presets.toml`). |
| `begin --quick 42` | Starts seeded quick battle number 42. |
| `begin --preset fleet-action --cycles 30 --screenshot shot.png` | Simulates 30 cycles headlessly and saves a screenshot. |
| `begin --tournament 20` | Runs 20 headless AI-versus-AI battles and prints a balance summary. |
| `pytest` | Runs the test suite. |

## Playing

Press **F1** in battle for the full controls list. The essentials:

**Time**
- **Space** pauses and resumes. You can still give orders while paused.
- **[** and **]** change the speed between 0.25× and 4×. One cycle is one second at 1×.

**Targeting**
- **Left-click** a contact, or press **Tab**, to target it.
- Type `range 8000` in the console (or use the mouse wheel) to set the display radius; bare `range` reports it.
- **R** cycles precision aim through propulsion, weapons, shields, power and sensors.

**Helm**
- **Right-click** the map to steer toward that point.
- **Shift + right-click** a ship to pursue it.
- **W** and **S** change warp; **A** and **D** turn.

**Weapons**
- **F** fires phasers, **T** fires torpedoes, **P** launches a probe, and **X** scans the target.
- In the weapons panel, the **Mode** button switches a weapon group between Manual, Assisted and Automatic. The **PD** button sets the point-defense doctrine. Right-click a phaser bank to reserve it for point defense.

**Console**
- Press **Enter** to open a Begin-style console. It accepts long forms (`fire phasers 1 2 spread 10`), terse forms (`fp 1 2 s 10`, `al tor al mk7 400`) and readable variants (`autoload all torpedo tubes with mk8 prox 400`).
- Type `help` for the full list.

## Project layout

```
src/begin/
  content/   TOML data (ship classes, ordnance, factions, doctrines, hulls, presets) and its typed loader
  core/      angles, vectors, deterministic RNG
  sim/       the authoritative simulation: ships, systems, commands, events, observations, world, scoring
  ai/        ship computer (point defense, assisted/automatic fire) and Begin-derived AI captains
  console/   the command parser
  ui/        pygame presentation: tactical map, HUD panels, menus, effects
  battle.py  builds a World with AI attached from a battle description
docs/        REFERENCE (mechanics digest), PLAN, ARCHITECTURE, EXTENDING, DEVIATIONS
tests/       headless tests
tools/       content importer from the reference data
```

Start with [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together, and [docs/EXTENDING.md](docs/EXTENDING.md) to add ships, weapons, AI policies or HUD panels.
