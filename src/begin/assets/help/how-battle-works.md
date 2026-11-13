---
title: How a battle works
category: Captain's manual
order: 4
aliases: how it works, mechanics, systems, game systems, rules, power budget, energy, heat, damage model, sensors, fog of war, cycles, intel
summary: What happens underneath: time, power, heat, shields, damage, crew, sensors and the end of a battle.
see: time, shields, repair, morale, scan, status
---
Every battle runs on the same rules for every ship, yours and the enemy's. Nothing on the other side cheats, and nothing on yours is hidden from you. Learn these rules and you can read a fight before it turns.

## Time

A battle runs in **cycles**. At normal speed one cycle is one second, and everything is measured in cycles: reloads, torpedo flight, repairs, countdowns. Every battle begins **paused**. You can give orders, read displays and open this manual while paused, and the orders take effect when you resume. `time 0.25` to `time 4` slows or speeds the battle, and nothing about the outcome depends on the speed you play at.

The game is fully repeatable. The same starting position and the same orders always give the same result. A patrol's number, or a preset's seed, always gives the same battle.

## Movement

The helm takes a **course** (a compass bearing, 0 straight up the map) and a **warp**. One warp factor is 100 units of distance per cycle. Heavy ships turn slowly and light ships turn on a coin.

Your top speed is set by your class, by the health of your warp drives and by the power left over. A damaged drive slows you down before it fails.

**Heat.** Running above cruise warp heats the drives. Past their temperature limit they burn out for good, and only a starbase can rebuild them. Fight at the warp you need, not the warp you have, or ask Geordi for a team on the engines ([[boost]]).

**Leaving.** A ship that stays more than 60,000 units from every enemy for ten cycles has escaped the battle. An escaped ship is not lost.

## Power

Reactors make energy and batteries store it. Each cycle the energy goes out in a fixed order:

1. life support
2. shields
3. the cloak
4. the tractor beam
5. charging weapons: phasers first, then torpedo tubes

Warp draws on the same budget, so speed is paid for in shields and firepower. If what is left can't pay for every raised shield, **none of them hold** that cycle.

When power is tight, you have several options:

- Lower the shields that face away from the enemy.
- Slow down.
- Disable banks you don't need (`disable banks 3 4`). They keep their charge but stop drawing.

A ship whose power fails goes dark. Every side can see it, and her life support starts to fail, so her crew has moments left.

## Shields

Six shields each guard a 60° slice of the hull:

| Shield | Covers |
|---|---|
| 1 | the bow |
| 2 and 3 | the forward quarters |
| 4 and 5 | the aft quarters |
| 6 | the stern |

A hit is taken by the shield facing the attacker, and the others are untouched. A shield absorbs damage up to its strength, and each hit drains it by only a fraction of what it absorbed, so a strong shield can swallow whole volleys. A shield knocked down comes back within a few cycles. A shield **generator** destroyed by aimed fire leaves a permanent hole.

This is the heart of the fight: **turn a fresh shield toward the enemy, and make them hit a tired one.** `reinforce <n>` makes one shield lose strength at half the rate, at four times the energy cost.

## Damage

What gets past a shield strikes the **hull**, a pool of structure, and the **systems**, each placed at a real point on the hull. A hit from astern lands among the systems aft. Weapons are knocked out one mount at a time, drives slow the ship, and reactors cut the power. A ship can be crippled without being destroyed, and that is often the point.

Aimed fire (`target gorkon shields`, `aim life support`) sends what gets through toward the system you choose and does only about a third of the usual damage to the hull. A system knocked out by aimed fire takes her crew about three times as long to repair.

## Crew

Crew run the ship. Every hit that reaches the crew decks costs lives. Fewer crew means slower repairs, and below a tenth of the complement a ship can't repair at all. **Morale** is the crew's will (see [[morale]]): at 100 repairs run 25% faster and tubes load 15% faster, and at 0 the same amounts slower. An enemy crew in low spirits makes their captain readier to retreat or yield.

**Boarding.** When your shield facing a ship and at least one of hers are both down, your transporters can put a party aboard within 3,000 units. If her defenders fall below six while six or more of your boarders stand, she is yours. See [[transport]].

## Repairs

Crews repair on their own, a little each cycle. `repair <system>` puts one system first: four times faster, and everything else at half speed. A **destroyed** system is rebuilt from nothing and takes the longest, and warp drives are the slowest of all. In battle the hull is patched at a quarter of the usual rate, and in space only up to 75%. A starbase does the rest, and repairs everything twice as fast while you are docked. See [[repair]] and [[dock]].

## Sensors

Each side sees the battle through its own sensors, pooled from every ship and data probe it has. What you see is what you know:

- **Contacts** appear as your sensors find them. A ship you haven't scanned shows as `#7` until a detailed `scan` identifies her.
- At the edge of sensor range a contact's position is hazy.
- A contact you have lost keeps its last known position. Starfleet computers keep plotting where it should be from its last course and speed.
- A **scan** shows her shields, systems, crew and loaded weapons, as of that moment. Your own hits keep you informed between scans: the log tells you how much a volley took off her shield.
- A **cloaked** ship can't be seen at all, except when it fires, when it is hit, when a tachyon burst lights it up, or when its leaking warp plasma gives it away. See [[cloak]].

The enemy's AI captains see exactly this much of you, and no more.

## How a battle ends

A battle ends when only one side has ships still fighting. Ships stop fighting when they are destroyed, captured, surrendered or abandoned, or when they escape. When the last enemy is left helpless, the battle stays open for 60 cycles so you can board her.

Afterwards the **assessment** shows the score, each ship's record, and the officer who did the most for you. See [[after-battle]].
