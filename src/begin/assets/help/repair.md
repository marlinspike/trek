---
title: Repair
category: Ship systems
order: 0
aliases: repair, damage control, fix, engineering, hull repair, manage repairs, under repair
summary: Tell your damage-control crews which system to fix first.
see: status, dock, targeting
---
Your crew repairs damaged systems on its own, a little each cycle. `repair <system>` tells them to put that system first: it is repaired four times faster, and everything else at half speed. `repair all` spreads the work evenly again.

```console
repair shields
repair drives
repair phasers
repair all
```

| System words | |
|---|---|
| `reactors`, `batteries` | power |
| `drives` (or `warp`, `engines`), `impulse` | movement |
| `phasers` (or `banks`), `tubes` (or `torpedoes`), `launchers` (or `probes`) | weapons |
| `shields`, `sensors`, `computer`, `transporters`, `tractor`, `cloak` | everything else |
| `hull` | the hull itself (see below) |

## What limits repair

- Repairs go faster with a full crew. A ship that has lost most of its crew repairs slowly, and below a tenth of its crew it cannot repair at all.
- A **destroyed** system cannot be fixed in space. Dock at a starbase, where repairs run twice as fast and destroyed systems can be rebuilt. See [[dock]].

## The hull

The crews patch the hull as well as the systems. They work slowly in battle, at a quarter of the usual rate, while the ship has been hit in the last 15 cycles or an enemy ship is within 12,000. Out of the fight, a full crew patches about 0.4% of the hull every cycle. In space they can only bring it back to 75%; a starbase restores the rest, and quickly (see [[dock]]). `repair hull` makes the hull the priority.

## Letting an officer direct repairs

Spock keeps an eye on the damage. When a system is badly hurt, or the hull drops past another quarter, he tells you what needs fixing and offers to direct the crews. Say yes in your own words, or use the console:

```console
spock, manage repairs
repair auto spock
repair manual
```

While he directs them he picks the priority as the fight changes: engines if the ship can't move, the shield facing the enemy, the weapons, power, then a badly holed hull. He says where he sends them. Any `repair <system>` you give yourself takes the crews back, as does "spock, I'll handle repairs" or `repair manual`.

## Seeing what is being repaired

In the Own ship panel, the dots on the ship diagram are its systems, placed where they sit in the hull. The big ones are reactors and warp drives, and the small ones are batteries, phaser banks, torpedo tubes, probe launchers, sensors and the rest. Each is coloured by health: teal is intact, amber damaged, red badly damaged and grey destroyed. Systems under repair have a pulsing ring, thick for the current priority. Hover over a dot to see what it is. The **Repairs** line counts the jobs under way and shows the priority, and who sets it; **Hull** says "under repair" while it is being patched. The damage screen (`I`, or click the diagram) shows the same, with a legend.

Check progress with `damage`. See [[status]].
