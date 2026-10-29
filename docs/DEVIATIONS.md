# Deviations from Begin

The remake follows Begin's rules wherever the manual ([M]) or the decoded binary ([R]) says what they are; [docs/REFERENCE.md](REFERENCE.md) is the digest of both. This page lists every place we deliberately do something else, marked [E] in the code and data, and why. When two sources disagree, the table at the end of REFERENCE.md records which one we followed.

## Time and motion

**Real time instead of turns.** Begin is turn-based: you type a command and one cycle passes. The remake runs continuously at 10 ticks per cycle, where one cycle is one second at 1× speed. You can pause at any time and still give orders, and the speed runs from 0.25× to 4×. Per-cycle rates (power, repair, shield regeneration, heat) are applied per tick in proportion, so their totals over a cycle match Begin's.

**Swept proximity fuses.** Begin samples torpedo positions at its sub-cycles, so a fast torpedo with a tight proximity setting could step past its target without detonating. We test the closest approach along each tick's path instead.

**Smooth helm at low warp.** Begin turns instantly at warp 1 or below. We turn at the warp-1 rate so ships don't snap round on screen.

## Ships and weapons

**Hull shapes, mounts and arcs.** Begin treats ships as points whose banks can fire in any direction. Each class now has a silhouette, internal system positions and weapon mounts with firing arcs (`content/data/hulls.toml`). Phasers fire from their mount, and a target has to be inside the mount's arc. This makes facing matter for weapons as well as shields. Torpedo tubes also have mounts, but as in Begin they fire in any direction; setting `Rules.tube_arcs` limits each tube to its arc (forward and aft launchers, as in the shows).

**Point-blank fire.** A target closer to the ship's centre than a bank's own mount is pressed against the hull, so every bank can reach it whatever its arc. Without this rule, a ship that parked inside a starbase's ring of mounts could neither hit the base nor be hit by it, and the Starbase Defense preset ended in stalemates.

**Damage model.** Begin 1.65 kills a ship outright on any hit of 50 or more that gets through the shields, and 2.0 handles damage quite differently. The remake keeps 1.65's shield absorption but adds a structural hull pool (40 plus 1 per unit of mass) and spreads subsystem damage by location. Each damage roll uses Begin's per-class weights, multiplied by how exposed each subsystem is to the direction of the hit. The 1.65 model is still available as a rules profile (`DamageModel.CLASSIC_165`).

**Subsystem targeting.** `target <ship> <subsystem>` aims phasers at propulsion, weapons, shields, power or sensors. Accuracy depends on the computer, the sensors, range, beam width and how recently the target was scanned. Begin had no aimed fire.

**Phasers against ordnance.** Begin's phasers detonate every torpedo in the cone. We give each torpedo a chance instead: 10% plus 5% per point of damage, up to 85%. Balance runs showed that certain interception made torpedoes nearly useless once ships had automatic point defense.

**Probe launchers** need a one-cycle preparation instead of being instantly ready.

## Sensors

Begin detects a ship at its rated sensor range multiplied by the ship's reflectivity, so small ships can close unseen, and a cloaked ship shows as a faint return at very short range. The remake does it differently:

- **Inside rated range,** every uncloaked ship is seen exactly and identified, whatever its size.
- **From 100% to 150% of rated range,** a contact is hazy. Its reported position wanders by up to 8% of the rated range at the outer edge, shown on the map as a dashed ring. A ship first seen this far out isn't identified.
- **Beyond 150%,** nothing is seen. The last fix is kept, and Starfleet computers extrapolate it. The science officer reports where a lost contact was last seen and where it was heading.
- **Sensor ranges differ by faction** (`sensors.range` in `factions.toml`): Federation 1.0, Romulan 0.85, Orion 0.8 and Klingon 0.7. The Federation and Klingon figures follow the player's direction that Starfleet sensors are the best and Klingon sensors notably worse; the Romulan and Orion figures are our guesses.
- **Cloaked ships are not detected at all** until they fire, which reveals them briefly, or until a tachyon burst lights them up (below).

`Rules.sensor_haze_limit` and `Rules.sensor_haze_error` set the band and the error.

## Crew projects: the tachyon detector

Begin has no way to find a cloaked ship except waiting for it to fire. In the remake, Spock and Seven of Nine can design a tachyon detector torpedo when you ask them about cloaked ships (or with `design tachyon`). It takes 20 cycles with a full crew, goes into one tube for a single shot, and the tube then goes back to ordinary torpedoes. Fired with `tachyon <bearing> <range>` or `tachyon <ship>`, it bursts at that point and shows every cloaked ship within 6,000 units for 30 cycles. It does no damage. The design is ours, inspired by the tachyon detection grids of the films and series.

## The ship computer

Begin has no automation. The remake adds a ship computer that can:

- reload tubes automatically (`autoload`);
- run point defense against incoming ordnance, with a choice of doctrine (`pd`);
- fire each weapon group in Manual, Assisted or Automatic mode (`mode`).

It issues ordinary commands at a lower authority than the captain, so it can never override you. Your own orders hold their channel for 8 cycles against the computer and the officers.

## AI captains

The captains follow Begin's decoded scoring for targets, fire discipline, weapon choice, weaving, retreat and overheating ([R]). On top of that:

- **Personalities and doctrines.** Each captain rolls a personality from its faction, and faction doctrines (`content/data/doctrines.toml`) bias the choices. For example, Klingons favour phasers and Romulans cloak while closing.
- **Disabling.** Competent captains whose doctrine prefers it aim at weapons or engines.
- **Fighting inside phaser range.** A torpedo-armed captain fights with phasers once a faster enemy is within 1.5× phaser range. Begin's captains keep turning away toward torpedo standoff, which can't work against a faster ship and only shows it their weaker shields and blind tube arcs.
- **Opening the range obliquely.** When a captain opens to torpedo range, it turns 70° off dead astern instead of running straight away, which only invites a stern chase.
- **Out of torpedoes.** A captain whose magazine is empty stops counting its tubes and closes for phasers.
- **Bases.** Attackers stand off a starbase or outpost at 0.6× phaser range instead of sitting on top of it.

## Ship data

Numbers come from begin2.exe through the importer (`tools/import_reference_data.py`), with 1.65 weapon counts. The changes are listed in the importer's `OVERRIDES` table, so re-importing keeps them:

| Class | Change | Why |
|---|---|---|
| Federation Dreadnought | top speed warp 9.5 (was 9.0), warp power 305 (was 285) | The player asked for the Federation flagship to have the edge. Raising the warp power keeps 9.5 reachable on the power budget. |
| Federation Dreadnought | 10,000 torpedoes (was 55) | The player's request: with eight tubes, 55 ran out in about 20 seconds of full volleys. |

## Scenarios and setup

- **Presets** (`content/data/presets.toml`) are our own scenarios. Balance runs set their fleets: each preset is fought by AI captains on both sides many times, and fleets are adjusted until the result is in a sensible range.
- **Quick and Custom battles** generate fleets from a seed or from the player's choices.
- **Escape.** A ship more than 60,000 units from every enemy for 10 cycles leaves the battle.

## Bridge officers and language models

Spock, Worf, Scott and Seven of Nine can run stations (helm, tactical, engineering, science) when you delegate them. They answer questions offline from the battle state, or in their own words through an optional language model (Anthropic, OpenAI, OpenRouter or a local Ollama).

They use the AI captain's judgement for one station each, but they never pick a target other than yours, retreat, surrender or self-destruct. Commands in an answer to an order are carried out only for the officer's own stations. Commands in an answer to a question are only suggested. None of this exists in Begin.

**Giving an officer the bridge.** "Seven, take the bridge" (or `conn seven`) puts one officer in command of every station. A single AI captain's judgement with that officer's personality runs the ship, under the same limits: your orders hold their channels against theirs, they keep your target, and they never retreat, surrender or self-destruct. Spock and Seven also build and fire the tachyon detector when an enemy cloaks. "I have the bridge" hands command back and restores the stations that were delegated before. In 8-seed test runs of three presets, Spock, Scott and Seven in command won about as often as the plain AI captain or better, and Seven and Spock did much better against Romulans. Worf, true to form, closes recklessly and won only about a third of the time.

## The manual and coach

The in-game manual is our own writing, organised by station, with clickable examples. The coach reads the live battle and suggests next steps. Begin's manual is copyrighted and isn't reproduced; see [LICENSING.md](../LICENSING.md).

## Settings

Everything the player sets lives in the project's `config/` folder (see [config/README.md](../config/README.md)) instead of beside the program.
