# Begin reference extract

This is the engineering digest of the two authoritative references, written so that nobody has to reopen them during routine development. Every rule carries a provenance tag:

- **[M]** documented in the *Begin 1.65 Advanced Strategy Manual* (incl. Appendix D, the 2.0 preview), read from the copy in `reference/Begin_Manual.pdf`. The manual is copyrighted by Clockwork Software and must not be redistributed, so `.gitignore` keeps it out of version control. Appendix C numbers were cross-checked against the binary-extracted data and agree except where listed at the end.
- **[R]** reconstructed from the begin2.exe disassembly by the `fireflyk64/begin` project (BSD-2, commit `0fdade8`, file `AI_AND_COMBAT.md` and `crates/begin-core`). These are decoded formulas and constants, not guesses, but a few are marked `[VERIFY]` upstream.
- **[E]** our deliberate extension or change. Each one is listed again in `DEVIATIONS.md` with the reason.

Ship, torpedo, probe and faction numbers live in `src/begin/content/data/*.toml`; the importer `tools/import_reference_data.py` documents how they were derived from the Rust project's JSON (which was itself extracted from begin2.exe, with v1.65 weapon mount counts).

## 1. Units, time and geometry

- [M] Space is an infinite flat plane. Ships are points and never collide.
- [M] Speed is in linear warp. One distance unit is 1/100 of what warp 1 covers in a cycle, so speed = warp × 100 units/cycle. Ships can reverse at up to warp −1.
- [M][R] Time is measured in cycles ("seconds"). 1.65 resolves motion in 10 sub-cycles, 2.0 in 20 (19 with ordnance in flight, a binary quirk).
- [R] Bearings are compass degrees: 0° = +Y ("north"), 90° = +X. Relative bearing ("mark") = bearing to target − own course.
- [E] We run a fixed 10-tick-per-cycle simulation in real time (1 cycle = 1 s at 1×) instead of Begin's turn-based "type a command, one cycle passes" loop. Proximity fuses use swept closest-approach tests per tick instead of point sampling, which removes the "fast torpedo strides past a tight prox" artifact.

## 2. Helm

- [M][R] Desired warp is clamped to [−1, max attainable]. If |diff| < 0.01 it snaps. If both desired and current warp ≤ 1, the change is instant.
- [R] Acceleration per cycle = `w1accel / current_warp` (plain `w1accel` below warp 1); deceleration per cycle = `decel` (flat).
- [M][R] Turn rate per cycle = `w1turn / current_warp`, always the shorter way; ships turn instantly at warp ≤ 1.
- [R] Max attainable warp = min(design max, warp budget / `warp_power_use`); if that is ≤ 1 the ship falls back to warp 1 on impulse (2.0: only if the impulse engine works, else 0).
- [M] Helm modes: course, pursue (re-aim at target each cycle), elude (aim directly away).

## 3. Power (energy units, eu)

- [R] WARP budget = Σ drives × health × `warp_power`. Warp costs `desired_warp × warp_power_use` per cycle and only when desired warp > 1 (impulse crawl is free and cold).
- [R] Half the unused warp budget spills into the general pool. [M] The 1.65 manual instead says 4 warp eu = 1 reactor eu. We follow the decoded binary (0.5) because both decoded versions agree; the manual likely describes an older build.
- [R] General pool = Σ reactors × health × `reactor_output` + Σ charge of undamaged batteries.
- [M][R] Drain order: life support (design crew / 10 per cycle; three consecutive failures kill the crew), shields (`shield_energy` each, ×4 when reinforced; if the pool cannot pay for all of them, all shields drop for that cycle), cloak upkeep, tractor upkeep, then weapon charging (phasers, then tubes).
- [M][R] Leftover refills undamaged batteries to capacity; any excess is lost.
- [E] Continuous form: all per-cycle rates are applied per tick × 0.1, with batteries as the buffer. Steady-state results equal Begin's.

## 4. Drive temperature

- [M][R] Per drive per cycle: `temp += (warp_ratio − health × warp_efficiency) × 4`, floor 12, where `warp_ratio = desired / max attainable`. Above 40 the drive is destroyed. A destroyed drive cools by `warp_efficiency × 4` per cycle.
- [M] Cruise speed (≈ the warp at which temperature is stable) = max warp × efficiency. The manual's "cruise" column matches this (HC 9.0 × 0.67 ≈ 6.0).

## 5. Shields

- [M] Six shields, 60° each. Numbering: 1 front (0°), 2 at 60°, 3 at 300°, 4 at 120°, 5 at 240°, 6 rear (180°). Lowered shields cost nothing and do not regenerate.
- [R] Hit face from relative bearing of the impact: ±30° front, 30–90 = shield 2, 90–150 = 4, 150–210 = 6, 210–270 = 5, 270–330 = 3.
- [R] Absorb capacity = `shield_strength × effective% / 100` (1.65; 2.0 multiplies by 0.25). Absorbed = min(damage, capacity). Strength loss = `1 + absorbed × (1 − shield_absorption)` percent (2.0: absorption × 0.25), halved when reinforced.
- [R] Regeneration per cycle while up: `strength += max(strength/100 × shield_recharge, 0.1)` capped at 100 − generator damage%.
- [M] Reinforcing a shield (2.0) costs four times its upkeep.
- [R] The Orion Shield Auger (warhead type 1) does ×4 damage to shields and never penetrates.

## 6. Phasers

- [M] Spread 10–45°. Wider spread hits more objects but weakens each hit. Banks can be locked on a target (auto-aim) or turned to a fixed mark. Disabled banks keep their charge.
- [R] Damage to every object in the cone (friend or foe, range < `banks_range`): `charge × (45 / spread) × sqrt(1 − d/range) × 0.5`. Charge goes to zero after firing. A bank must be fully charged and undamaged to fire.
- [R] Charging per cycle per bank: `banks_charge / banks_rate` eu (three cycles for most ships).
- [M] Phasers fired at a torpedo or probe destroy it (standard torpedoes and probes detonate on any energy; plasma bleeds strength).
- [E] Banks have mounting positions and firing arcs. Begin banks could point anywhere.

## 7. Torpedoes

- [M][R] Tubes charge over the torpedo's `charge_time` cycles (paying `load_energy` spread over those cycles), then load at the set proximity. The proximity floor is 100.
- [M][R] Locked tubes lead the target: `mark = rel_bearing + asin(sin(angle_off) × target_warp / torp_velocity)` plus an optional dispersion fan.
- [R] Launch velocity = design velocity ± `speed_variance` (additive warp). Non-homing torpedoes are ballistic. Same-cycle torpedoes with identical course/design/target merge into a salvo that applies its blast once per torpedo.
- [M][R] Arm delay (1 cycle) then a time fuse; expiry fizzles without a blast. Armed torpedoes detonate within prox of **any** ship, including the firer's side.
- [R] Blast: `total = warhead × 5`, radius `total × 10`; damage at distance d = `total × sqrt(1 − d/radius)`, hit face = bearing from target to the blast. Docked ships are sheltered.
- [M] Plasma (Romulan) torpedoes home, lose strength over time (yield scales with remaining fuse), and need several phaser hits to kill.
- [M] Tip: proximity of ¾–⅘ of maximum is a good default; very small prox misses maneuvering targets.

## 8. Probes

- [M][R] Slow homing weapons, loaded with prox and time fuse (bounds 50..max prox, 5..max time); no energy cost. Each gets a control code. They can be re-locked, turned, or detonated remotely, including by anyone who knows the code.
- [R] Prox triggers only on other-nation ships (or a deliberately targeted ally). Expiry detonates (unlike torpedoes). Any hit detonates the probe at full warhead.
- [M] Data probes (2.0) travel at warp 20 and carry sensors (20 000 range); the Klingon version also has a small warhead.

## 9. Damage beyond the shields

- [M] Energy that passes the facing shield damages crew and subsystems; some systems are tougher; some damage disables instantly (tubes) while some only degrades efficiency (drives, reactors).
- [R] 1.65: any post-shield hit ≥ 50 destroys the ship; crew loss is percentage based. 2.0: armour gate, hull integrity ≈ design mass, absolute crew loss, 8000 cap.
- [R] System damage: `n = damage/10` rolls; each roll hits each class with an independent chance (shields 75%, tubes 50%, banks 45%, drives 40%, reactors 60% with 25% outright destruction, launchers 20%, batteries 15%, transporters 10%, scanner 10%, cloak 10%, impulse 5%, tractor 5%), adding 5 + rand(0..25) % damage to a random item of that class. Damaged tubes lose their loaded torpedo.
- [R] Crew below 6 means all hands lost (derelict).
- [E] We replace random class rolls with *location-aware* rolls: the same class weights, multiplied by each subsystem's exposure to the hit direction (from data-driven hull geometry), plus a deliberate bias toward a targeted subsystem that depends on weapon precision and sensor quality. We add a structural hull pool so ships can be disabled without being destroyed. See `DEVIATIONS.md`.

## 10. Repair

- [M] Damage control repairs automatically; warp drives take longer than phasers; repair slows as crew are lost.
- [R] Efficiency `e = survivors / crew` (docked: host's `docked_repair_ratio`), skipped below 0.1. Progress per item per cycle = rate × e (2.0: rand(0, 2 × rate × e)); whole points reduce damage%. Destroyed items repair only while docked (2.0), behind a 2%/cycle gate.
- [M] 2.0 adds `Repair <system>` priority (×4 that class, ×0.5 others) and doubles docked repair.

## 11. Sensors and cloaking (2.0)

- [M][R] Objects beyond sensor range vanish; the last known position is kept and used by AI and display. Range = scanner range × target reflectivity (ship `scanner_reflect`, probes 0.5). Data probes extend a side's coverage. [E] The remake replaces reflectivity for ships with faction sensor ranges and a haze band; see DEVIATIONS.md.
- [M][R] Cloaked Romulans have reflectivity × 0.005 and reappear for a cycle when hit or firing. Cloak upkeep is `cloak_energy` per cycle. Phasers and blasts still hit cloaked ships.

## 12. Tractor, docking, transport, boarding (2.0)

- [R] Tractor: range 1000, upkeep `tractor_energy`; pull ratio = `tractor_strength / target mass`, scaled down by distance/1000; under 0.1 it fails. Towing speed = ratio.
- [R] Docking: same side, within 1000, host `mass_capacity` must hold the docked masses. Docked ships repair at the host ratio, can repair destroyed items, are immune to phasers and blasts (the host passes hits ≥ 10 on to them), and keep life support.
- [R] Transporters: range 3000, target shields facing must be down; capacity Σ `beam_cap` of working transporters. Beaming crew onto an enemy is boarding.
- [R] Boarding combat per cycle: rounds = rand(0,1) × boarders, rolls against nation boarding level; crew < 6 with ≥ 6 boarders = capture (ship changes side and gets a fresh AI captain).

## 13. Self-destruct

- [M][R] Countdown (default 5 cycles); abort allowed while more than 5 remain. Yield = warp budget / 9 (Daniel's multiplayer patch uses 14) plus the design's suicide bomb (`destruct`) when deliberate. Uses the splash rules above.

## 14. AI (begin2, decoded)

Personality per captain: `clamp01(nation value ± uniform(deviation))` for aggression, bravery, loyalty, fanaticism.

| Nation | Aggression | Bravery | Loyalty | Fanaticism | Boarding | Deviation |
|---|---|---|---|---|---|---|
| Federation | .65 | .95 | 1.20 | .05 | .5 | .30 |
| Klingon | .95 | .50 | .60 | .10 | .5 | .20 |
| Romulan | .75 | .95 | 1.00 | .95 | .5 | .10 |
| Orion | .45 | .45 | .45 | .45 | .75 | .40 |

Per-cycle priority order [R]: reflexes (overheat slowdown, flee imminent detonations, snap phasers at the nearest approaching enemy using exactly enough banks to break the facing shield, phaser point defense against probes, reinforce the weakest shield) → target selection → remote-detonate own probes → fire phasers / torpedoes / probes / board → cloak when idle → mission or stance helm or morale + default maneuver → lock/load housekeeping.

- Target score = target strength (`1 + charged banks × range/1000 + loaded tubes × 6`) × distance band (×3.0 under 2000 falling to ×1.1 at 18–20 k, ×0.5 beyond) × 2 if in own phaser range × 1.25 if current target × 0.5 if own probes already chase it × 0.5 if already outnumbered relative to `(1 − bravery) × 5` × 0.1 if contact is stale.
- Phasers: lock, then fire half the charged banks when `rand + 0.1 < aggression`, otherwise all banks only when all are charged; spread 45.
- Torpedoes: fire inside [min, max] envelope (`closing = v_torp + v_target × cos`; min = arm × closing × 100; max = (arm + fuse) × closing × 100); aim 20° off-axis at a target already under heavy torpedo pressure; volley size by target "incoming torpedo pressure"; never fire through an ally (sidestep ±90°).
- Torpedo prox = `min(target max warp × 50, design max)` (100 for slow targets).
- Maneuver: phaser-dominant ships close to phaser range (pursue at target warp + aggression × 4), torpedo-dominant ships hold standoff `min + (1 − aggression) × (max − min)`; weave amplitude `rand(0, (1.1 − aggression) × (31 − dist/833))` within 25 000; slow down to complete sharp turns; temperature panic hysteresis 0.85/0.4.
- Morale: retreat when damage ratio > bravery × 0.75, recover below bravery × 0.5; fanatics (> 0.9) or desperate crews self-destruct and ram.
- [M] Nation flavor: Federation fight to the end; Klingons aggressive and phaser-happy; Romulans avoid close combat, rely on plasma, cloak, carry suicide bombs, retreat after losing the main weapon; Orions vary widely.

## 15. Scoring

- [M] Score = own condition relative to the enemy's, multiplied by the starting odds (offensive + defensive strength totals). Negative scores are possible. Destroying a ship and killing its crew score the same. Seven verdict tiers per nation (thresholds 15, 5, 2, 0, −2, −5) [R].

## 16. Commands (1.65 + 2.0)

Helm: `helm [course] <c> [warp] <w>`, `pursue <ship> [warp] <w>`, `elude <ship> [warp] <w>`. Phasers: `fire phasers [all|list] [spread] <s>`, `lock banks [all|list] on <ship>`, `turn banks <list> to <mark>`, `enable/disable banks`. Tubes: `fire torpedoes [all|list]`, `lock tubes on <ship> [dispersion] <d>`, `turn tubes`, `load tubes [all|list] [prox] <p>`, `unload tubes`. Probes: `fire probes [all|list] at <ship> | course <c>`, `load launchers [list] prox <p> time <t>`, `turn probe <code> course <c>`, `lock probe <code> on <ship>`, `detonate <code>|all`, `status probes`. Shields: `raise/lower [all|list]`, `reenforce <n>` (2.0). Information: `status`, `damage`, `scan <ship>`, `chart`, `range <r>`, `computer ship|torpedo|probe`. 2.0: `repair <system>|all`, `tractor <ship>|off`, `board <ship>`, `dock <base> on|off`, `cloak on|off`, `destruct <n>` / `abort`, `transport`. Ally orders (`tell <ally|group#> …`): target, attack, hold fire, open fire, disengage, escort, course, run, withdraw, cancel, torpedo, phaser, probe, report, and 2.0 board, tow, tractor, release, approach, dock, undock, join, leave, stop, defend, recover, eject.

## Known source discrepancies

| Topic | Manual 1.65 | Binary (begin2, decoded) | Our choice |
|---|---|---|---|
| Unused warp → pool | 4:1 | 0.5 | 0.5 (decoded code is executable truth) |
| Sub-cycles | 10 | 20 (19 with ordnance) | 10 ticks/cycle + swept fuses |
| pxii probe speed | warp 3 | 2.5 | 2.5 (2.0 data) |
| dnk probe speed | warp 4 | 3.5 | 3.5 (2.0 data) |
| Weapon mounts | e.g. Klingon BC 5 banks/5 tubes | 2.0 halved most loadouts | 1.65 counts (the reference port's choice, the classic feel) |
| Damage application | — | 1.65 vs 2.0 differ a lot | Remake model (§9 [E]); classic 1.65 available as a rules profile |
| Phaser falloff | "decreases linearly with distance" | `sqrt(1 − d/range)` | decoded formula |
| Blast falloff | "reduced by the square of the distance" | `sqrt(1 − d/radius)` | decoded formula |
| Torpedo speed variance | "warp 30 ±7%" | ±0.07 warp (additive) | ±7% of velocity: the manual states intent, and the spread gives salvos a visible stagger |
| Klingon Battle Cruiser, Orion Saboteur/Armadillo, Tug, Tanker, bases | absent from 1.65 tables | present in 2.0 data | included, marked as 2.0 classes |
| Tube/bank counts | 1.65 tables (e.g. Klingon Frigate 5 banks, 2 tubes) | 2.0 halved some | 1.65 counts, matching the manual |
