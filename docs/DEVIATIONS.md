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

**Phasers against ordnance.** Begin's phasers detonate every torpedo in the cone. We give each torpedo a chance instead: 10% plus 5% per point of damage, up to 85%. Balance runs showed that certain interception made torpedoes nearly useless once ships had automatic point defense. Shots aimed at ordnance by point defense get only 40% of that chance (`Rules.pd_kill_scale`). Point defense also depends on its crew: each faction has a `pd_discipline` (Klingons 0.3 and Orions 0.2 pour four banks onto the first round they see; Romulans and Starfleet, 0.85, send one bank per round), and crew losses and sensor damage slow reactions, spoil aim and erode discipline. A trigger-happy defense can be baited with one torpedo and the rest a cycle later (`bait`, which Seven also uses). At full strength, a Klingon Dreadnought's point defense stopped about 85% of a Federation Dreadnought's torpedoes, and the duel took over 100 volleys.

**Probe launchers** need a one-cycle preparation instead of being instantly ready.

## Sensors

Begin detects a ship at its rated sensor range multiplied by the ship's reflectivity, so small ships can close unseen, and a cloaked ship shows as a faint return at very short range. The remake does it differently:

- **Inside rated range,** every uncloaked ship is seen exactly and identified, whatever its size.
- **From 100% to 150% of rated range,** a contact is hazy. Its reported position wanders by up to 8% of the rated range at the outer edge, shown on the map as a dashed ring. A ship first seen this far out isn't identified.
- **Beyond 150%,** nothing is seen. The last fix is kept, and Starfleet computers extrapolate it. The science officer reports where a lost contact was last seen and where it was heading.
- **Sensor ranges differ by faction** (`sensors.range` in `factions.toml`): Federation 1.0, Romulan 0.85, Orion 0.8 and Klingon 0.7. The Federation and Klingon figures follow the player's direction that Starfleet sensors are the best and Klingon sensors notably worse; the Romulan and Orion figures are our guesses.
- **Cloaked ships are not detected at all** until they fire, which reveals them briefly, or until a tachyon burst or deflector pulse lights them up (below).

`Rules.sensor_haze_limit` and `Rules.sensor_haze_error` set the band and the error.

## Crew projects: the tachyon detector

Begin has no way to find a cloaked ship except waiting for it to fire. In the remake, Spock and Seven of Nine can design a tachyon detector torpedo when you ask them about cloaked ships (or with `design tachyon`). It takes 20 cycles with a full crew, goes into one tube for a single shot, and the tube then goes back to ordinary torpedoes. Fired with `tachyon <bearing> <range>` or `tachyon <ship>`, it bursts at that point and shows every cloaked ship within 6,000 units for 30 cycles. It does no damage. The design is ours, inspired by the tachyon detection grids of the films and series.

They can also set the main deflector dish up to emit tachyons (`design deflector`, about 12 cycles, once per battle). After that, `pulse` sweeps a 60° cone ahead of the bow out to 15,000 units and shows cloaked ships there for 20 cycles. Each pulse costs 40 battery energy and the dish recharges for 30 cycles (`Rules.deflector_pulse_*`). The pulse is quick and reusable but short-range and forward-only; the torpedo reaches further in every direction but uses a tube and is built for each shot.

## Officer objectives

Begin has no standing orders. In the remake, "Seven, disable the Klingons' shields" (or `disable <systems> <ships>`) gives the science officer an objective covering shields, phasers, torpedoes, weapons, engines, sensors or the cloak, on one ship or several. She plans it herself:

- she scans each target to judge progress;
- she aims phasers at the chosen systems;
- she fires full torpedo salvos from just outside arming range, fused to burst on a ring around the target's predicted position (`FireAtPoint`);
- when two targets are close together, she bursts the salvo between them;
- she hunts cloaked targets with the deflector or tachyon detector.

She baits trigger-happy point defenses (one torpedo, then the rest while their banks recharge), and "take out the Wraith" (`destroy`) keeps her at it until the ship is gone. She never steers, and the captain's orders still override hers. Weapons count as disabled when all of them are off line, and shields when two thirds of the generators are. In 8-seed test runs with Spock at the helm, a Seven objective won the Border Incident 7 of 8 in about half the time (Spock alone won 6 of 8), and was about even in quick battles. Targets were often destroyed before she could confirm them disabled, because blast and phaser damage also reaches the hull.

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
| Klingon Dreadnought | shield absorption 0.6 (was 0.8) | With 0.8, each hit drained a shield by only a fifth of what it absorbed, and full Federation volleys couldn't wear it down. |
| Federation Dreadnought | 10,000 torpedoes (was 55) | The player's request: with eight tubes, 55 ran out in about 20 seconds of full volleys. |
| Federation Dreadnought | 250 probes (was 9) | The player's request. |

Torpedo designs have their own table, `ORDNANCE_OVERRIDES`:

| Torpedo | Change | Why |
|---|---|---|
| Federation Mark 7 | warhead 16 (was 10); max proximity 800 (was 500); arms after 0.4 s, 1,200 units (was 1.0 s, 3,000); blast radius 920 (was 500) | The player's requests. The arming change alone moved 32-seed AI-vs-AI balance runs toward the Federation (Fleet Action 17 → 25 of 32, Outpost Assault 20 → 29, Starbase Defense 21 → 27, Pirate Hunt 25 → 30). |
| Federation Mark 8 | warhead 24 (was 15); max proximity 800 (was 500); arms after 0.95 s, 1,425 units (was 1.0 s, 1,500; briefly 0.6 s); blast radius 1,380 (was 750) | As above. The Mark 8 arming time went back up when the bigger warhead's blast outgrew 900 units, so each round still arms beyond its own blast and a ship can't catch itself. |

The blast radius is a per-design `blast_scale` (1.15) on Begin's formula (yield × 5 × 10). The warheads were scaled by the same factor as the proximity limit (800 / 500 = 1.6): blast radius grows in step with the warhead, so a burst at the widest fuse sits at the same fraction of the blast radius as before (800 of 920 now, 500 of 575 then) and delivers the same share of a 1.6 × bigger warhead. With the bigger warheads the Federation side wins most AI-vs-AI runs (32 seeds: Border Incident 14 → 32, Three-Way 15 → 30, Fleet Action 25 → 31).

## Hull repairs [E]

Begin repairs systems but never the hull. Here damage-control crews also patch it, at `hull_repair_rate` (0.4% of the hull per cycle with a full crew), a quarter of that while in battle (hit in the last 15 cycles, or an enemy ship within 12,000), and only up to 75% in space. Docked at a base the hull is repaired at 3% per cycle × the base's repair ratio, all the way. The hull can be the repair priority (`repair hull`), with the same × 4 / × 0.5 weighting as systems. `repair auto <officer>` hands the priority to an officer, who uses the same choice the engineering station makes. All of these are in `sim/rules.py`.

## Evasive manoeuvres [E]

A Federation-only helm order (`evasive`, from the faction's `orders` list in `factions.toml`). The helm keeps the captain's course or pursuit, and when a torpedo would hit it picks a dodge with the same predictor the officers fly with (`crew/helm.py`), then returns to the captain's order two cycles after the danger has passed. Any navigation order from the captain ends it.

## Scenarios and setup

- **Presets** (`content/data/presets.toml`) are our own scenarios. Balance runs set their fleets: each preset is fought by AI captains on both sides many times, and fleets are adjusted until the result is in a sensible range.
- **Quick and Custom battles** generate fleets from a seed or from the player's choices.
- **Escape.** A ship more than 60,000 units from every enemy for 10 cycles leaves the battle.

## Bridge officers and language models

Spock, Worf, Scott and Seven of Nine can run stations (helm, tactical, engineering, science) when you delegate them. They answer questions offline from the battle state, or in their own words through an optional language model (Anthropic, OpenAI, OpenRouter or a local Ollama).

They use the AI captain's judgement for one station each, but they never pick a target other than yours, retreat, surrender or self-destruct. Commands in an answer to an order are carried out only for the officer's own stations. Commands in an answer to a question are only suggested. None of this exists in Begin.

**Giving an officer the bridge.** "Seven, take the bridge" (or `conn seven`) puts one officer in command of every station. A single AI captain's judgement with that officer's personality runs the ship, under the same limits: your orders hold their channels against theirs, they keep your target, and they never retreat, surrender or self-destruct. Spock and Seven also build and fire the tachyon detector when an enemy cloaks. "I have the bridge" hands command back and restores the stations that were delegated before. In 8-seed test runs of three presets, Spock, Scott and Seven in command won about as often as the plain AI captain or better, and Seven and Spock did much better against Romulans. Worf, true to form, closes recklessly and won only about a third of the time.

**Weapons coloured by race.** Begin drew every phaser and torpedo alike. Here each race's beams and torpedoes have their own colour (`colors` in `factions.toml`), Klingon and Orion beams are drawn as bolts so the races differ in shape as well as colour, and an unidentified ship fires in white. A torpedo shot down by a phaser shows a small grey star of debris instead of the bright coloured blast ring of one that went off on its target. `Detonation` events carry the owner and the cause (`proximity`, `fuse` or `intercepted`) for this.

**Officers at the helm dodge, and fly for each other.** An officer flying the ship predicts where each incoming torpedo will pass under a spread of possible helm orders and takes the one that makes them miss. When Seven is working an objective, the helm sets up her torpedo shots (just inside torpedo range, outside the enemy's phasers, strongest shield toward it), except against a faster ship already close, which it fights head on. In 96 test battles per preset with Spock in command and Seven told to take down the enemy's shields, the share of enemy torpedoes that hit fell from 28% to 16% (Dreadnought Duel), 40% to 25% (Border Incident), 28% to 21% (Pirate Hunt) and 19% to 12% (quick battles); damage taken fell by 16-50%. Seven finished the Dreadnought Duel job more often (67 vs 56 of 96) and faster (47 vs 57 seconds). The cost is that more damaged enemies get away: in quick battles 144 of 192 enemies were destroyed against 162 before. An activity panel, map overlays and spoken callouts show what each officer is doing. Begin's officers didn't exist.

**Orders in plain English.** With a language model set up, the console accepts plain English. The exact parser still reads every line first, so Begin's syntax runs instantly; a line it rejects goes to the model with the command list and what the ship knows. The model replies with console commands, an answer, or a clarifying question. Each command is checked by the parser before it runs and echoed with a ≈, so the player learns the syntax. Quit, self-destruct, surrender and changing ships are only ever suggested. `translate always` sends every line to the model, and `translate off` turns it off. Begin's console only took its own syntax.

## The manual and coach

The in-game manual is our own writing, organised by station, with clickable examples. The coach reads the live battle and suggests next steps. Begin's manual is copyrighted and isn't reproduced; see [LICENSING.md](../LICENSING.md).

## Settings

Everything the player sets lives in the project's `config/` folder (see [config/README.md](../config/README.md)) instead of beside the program.
