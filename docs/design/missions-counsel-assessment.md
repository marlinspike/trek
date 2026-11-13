# Missions, counsel and Starfleet's assessment

Design for the round Reuben chose on 2026-11-13: battles with real goals, live counsel from the bridge officers,
and an end-of-battle assessment that tells the story of the fight. Nothing here changes a combat number, and every
existing battle plays exactly as before unless it asks for a mission.

## Reuben's rulings

- Counsel is not about who the captain listened to. It helps solve the situation **now**.
- The officers must know every capability in the game and the live battle situation, or the counsel is worthless.
- Each officer has a perspective, and each perspective is a plausible way forward. Going all in on one may win;
  taking a bit of each may do well too.
- Counsel changes as the battle changes.
- A failed mission goal does not end a tour (the question was left open; this is the recommended default). It
  shows in the assessment, the log and the stop's flags.

## 1. Missions

A battle may carry one `Mission`. The battle still ends the old way (one side holds the field); the mission is a
second question the battle answers, and Starfleet judges both.

| Kind | Setup | Success | Failure |
|---|---|---|---|
| **rescue** | a stricken ship of ours (`ward`) that can't move, `people` aboard, optional `deadline` | everyone off: our ship within transporter range with the shield facing her lowered takes people off each cycle | the ward is destroyed or the deadline passes with people aboard (partial credit for those saved) |
| **escort** | a ship of ours (`ward`) sailing to a point (`to`) at her own speed | she reaches the point and goes to warp | she is destroyed, captured or surrenders |
| **intercept** | one enemy (`runner`) makes for the edge on a set heading | she is destroyed, disabled (can't move), surrenders or is taken | she escapes |

Rules that make these play well:

- **Rescue is the mind against the sword.** Beaming needs the facing shield down (the rule `transport` already
  uses), so the captain must turn a lowered face to the ward and an armoured face to the enemy, or let a wingman
  screen. Rate: `beam_cap × working transporters ÷ 4` people a cycle (a Dreadnought: 20). Rescued people ride in
  the rescuing ship (`Ship.evacuees`) and die with her. When the enemy is beaten, anyone still aboard is taken off
  after the battle.
- **Hunters.** A mission names how many enemy ships go for the ward (`hunters`, default 1 for rescue and escort).
  They are given the ward as their ordered target, the same lever as `tell <ally> attack`. The rest fight as
  usual. When the ward is gone, they fight as usual too.
- **The runner** sails on the mission heading (the existing standing order `course`, weaving under threat) and
  escapes by the existing escape rule (60,000 clear for 10 cycles). She still fires when she can.
- **Wards don't hold the field.** A ward is not a combatant: she doesn't keep a battle open, can't escape by
  distance, and isn't counted as a tour stop's friend.
- Missions are data: `[tour.stop.mission]` in tour files, `mission = {...}` in presets, and three new patrol
  situations (`rescue`, `convoy`, `runner`).

Code: `sim/mission.py` (definition, runtime state, `update_mission` called each step before the outcome check),
`World.mission`, `Ship.ward` and `Ship.evacuees`, wired in `battle.build_battle`. The HUD shows one mission card
over the map (goal, progress, time left) and marks the ward and runner on the map.

## 2. Counsel

Press **O** (or type `counsel`) in battle: a panel over the left of the map shows each officer's way forward,
rebuilt from the live situation about once a second while it is open. Time keeps running unless the captain pauses.

Each officer gives one **plan**: a title, the reason in a sentence or two built from live numbers, and two to four
**steps**, each a real console line. **All in** runs every step; clicking a single step runs just that one, so the
captain can mix. Keys 1 to 4 run an officer's whole plan while the panel is open. A plan only offers steps the
console would accept now (checked with the console's own dry run), so nothing offered can be refused.

### What the officers know: the situation

`crew/situation.py` builds one `Situation` from our side's `Observation` (never the world), the same knowledge the
AI and the coach use:

- **Us:** hull, crew, morale; each shield facing and the one toward the main threat; the freshest facing; power
  balance and battery; loaded tubes, torpedoes left, the torpedo types we carry; charged banks and phaser range;
  probes; top warp, drive heat, a drive venting plasma; cloak fitted and on; evasive drill; transporters; the
  stations handed over and the officer with the conn; objectives under way; projects (tachyon, deflector,
  seeker, harmonic...); the deflector ready.
- **Allies:** each one's hull and standing order; who is hurt.
- **Enemies:** every visible contact with class, range, bearing, closing speed, threat (Begin's strength score),
  faction doctrine (charger, feinter, raider, hive), our scan (shields, charged banks, loaded tubes, damage), how
  her captain reads (fear, anger, resolve, pliancy) when we can read her, surrendered or withdrawing.
- **Envelopes:** our torpedo envelope against each enemy and hers against us, phaser ranges, who out-ranges whom.
- **Hidden things:** contacts lost at close range (probably cloaked), plasma trails, incoming ordnance.
- **The Borg:** adaptation to our weapons, survey progress, the relay found or not, dormant, the opening
  (stolen or cracked harmonics), shield tuning, the away team.
- **The mission:** kind, ward, runner, people aboard, time left, the runner's time to escape at her speed.
- **The campaign:** reinforcement calls left and their time to arrive, prisoners aboard (a bargaining chip).

### Their perspectives

Every officer reasons from the same situation but values different things. Each plan is assembled from
**moves** (a library of capabilities, below) that their perspective favours, scored by how well each fits the
situation now. The top-scoring coherent set becomes the plan.

| Officer | Perspective | Favours |
|---|---|---|
| **Worf** (Sulu when he stands in) | *The sword.* Decisive force, concentrated, now. | mass fire on the most dangerous ship; a full salvo early at a charger; baiting trigger-happy point defense; closing to phaser range when we out-phaser her; taking a prize when one is hurt; striking through a Borg opening; running down a runner; killing the hunters before they reach the ward |
| **Spock** (Chekov at the helm when Spock covers science) | *Geometry and the mind.* Choose the range, use the shields, read the captain. | the range where our envelope beats hers (stand off or close); turning the freshest shield and reinforcing it; evasive manoeuvres against aimed torpedoes; separating groups; opening range against plasma; hailing a captain who is close to giving way (withdrawal for Klingons, surrender for Orions, prisoners as the price); interposing the Enterprise between the hunters and the ward |
| **La Forge** | *Keep the ship and her people alive to win.* | power: lowering shields facing away when power is short; reinforcing; repair priorities; the boost for a long run; stopping a plasma leak; fighting at phaser range to save torpedoes; Starfleet's reinforcements when they can arrive in time; pulling a hurt ally back; the cloak; lowering the facing shield and beaming the people off |
| **Seven of Nine** (Spock when she is away) | *Knowledge and precision.* Know first, then remove exactly what matters. | scanning the threat; disabling the system that decides the fight (weapons if she outguns us, engines if she runs, shields for a permanent hole, life support to take her); finding cloaked ships (hunt, tachyon, deflector pulse, sweep, seeker); the ring salvo against disciplined point defense; every Borg duty |

Each plan is a complete way to play the next stretch of the fight. They overlap where the situation demands it
(every officer will say "torpedoes inbound" in their own way), but each has a distinct centre.

### The moves (capabilities the counsel can use)

Weapons: `target`, aimed fire (`target <ship> <system>`), `fire all torpedoes [spread]`, `fire all phasers`,
`bait`, `autoload` (torpedo type, proximity), probes and probe fields, point-defense doctrine, phaser roles.
Helm: `pursue`, `elude`, `helm`, `evasive`, `stop`. Shields and power: `reenforce`, `lower`/`raise`, `boost`,
`repair <system>`, `repair auto`. Officers: `delegate`, `conn`, `seven, disable ...`, `capture`, `hunt`,
`design ...`. Detection: `scan`, `tachyon`, `pulse`, `sweep`, `seeker`. Mind: `hail <ship> <words>`, prisoners.
Squadron: `tell <ally> attack|defend|escort|run|withdraw`. Borg: `duty harmonics|shields|phasers`, `tune shields`,
`remodulate`, `away ...`, `design harmonic|inoculate|encrypt|sever`. Campaign: `request reinforcements`.
Cloak: `cloak on|off`. Missions: lowering the facing shield toward the ward, interposing, running down.

### In the Ready Room

The same engine reads the stop before the battle from the tour's records (the squadron as Geordi expects it to
arrive, the enemy's classes, the mission and what the enemy has learned) and each officer says, in two sentences,
how they would play it. No orders are queued: the live counsel takes over on the bridge.

## 3. Starfleet's assessment

The end of every battle opens on Starfleet's assessment; the old table is one click behind it (**Details**).

- **Headline:** the mission's result in words when there is a mission ("The survey team is safe."), else the
  field ("The Klingons are beaten.").
- **Lives:** people rescued; our crew lost; enemy crew spared (surrendered, prisoners, withdrew on terms) and lost.
- **Conduct:** surrenders accepted, prisoners taken, any fire on a ship that had struck, truces kept.
- **Objective:** the mission's result, with partial credit for a rescue.
- **Cost:** our hull, torpedoes left, systems down, ships lost.
- **Commendation:** at most one, for something specific: the Karagite Order of Heroism for a full rescue under
  fire, the Palm Leaf of Axanar Peace Mission for winning while sparing those who yielded, the Grankite Order of
  Tactics for a decisive win that left the Enterprise sound.
- **The bridge:** a line from each officer whose work showed, in their voice, built from what happened.
- **What follows:** who escaped and what they will report, what the enemy will remember of our conduct, and on a
  tour, what the mission's result changes.

The same facts feed the tour log: the mission result goes into each stop's facts, Spock's entry and the captain's
draft.

## 4. Border Patrol, rewritten

Three of the six stops gain a mission; the others keep their shape.

| Stop | Mission |
|---|---|
| Orion raiders (Tau Ceti) | **escort**: the freighter SS *Tamar Kessel* must reach the shipping lane; two raiders go for her |
| Frigates at Kessik | **intercept**: one frigate runs for the border with her report; the stop's win flag needs her stopped |
| Romulan ambush (Galorndon Core) | **rescue**: the distress call is real. The survey ship USS *Aldren* is crippled with 120 aboard, and the Romulans are using her as bait |

## Testing

- `tests/test_missions.py`: each kind succeeds and fails as written; wards don't hold the field; hunters chase the
  ward; the runner escapes when left alone and is stopped when engaged; rescue needs the facing shield down.
- `tests/test_counsel.py`: plans for every officer in a spread of situations (Klingon charge, Romulan cloak,
  Orion raid, Borg cube, rescue, intercept, low power, empty magazine); every offered line passes the console's
  dry run; plans change when the situation changes.
- `tests/test_assessment.py`: headline, lives and conduct from staged outcomes; commendations only when earned.
- AI-flown battles of every preset and patrol situation still finish; the full suite passes.
