---
title: Fire
category: Weapons
order: 0
aliases: fire, fp, ft, fpr, shoot, weapons, attack
summary: Everything you can fire: phasers, torpedoes and probes.
see: phasers, torpedoes, probes, lock, weapons-guide
---
Your ship can carry three kinds of weapon, and `fire` works for each of them. Not every ship has all three; the [[library]] and the weapons panel show what yours has.

| Weapon | Range | Speed | Best for | Fire it |
|---|---|---|---|---|
| [[phasers|Phasers]] | short (about 2,000) | instant | close fights, stopping incoming torpedoes | `fire phasers`, **F** |
| [[torpedoes|Torpedoes]] | long (10,000–25,000) | fast, but they take time to arrive | hitting from outside phaser range | `fire torpedoes`, **T** |
| [[probes|Probes]] | medium | slow, but most of them home in | slow ships and stationary targets, big warheads | `fire probes at <ship>`, **P** |

## Phasers

```console
fire phasers
fire all phasers 45
fire phasers 1 2 3 spread 10
phaser all 20
fp 1 2 s 10 at gorkon
```

- The number after the list is the **spread** in degrees, from 10 to 45. A narrow spread puts the whole charge on one ship. A wide one is weaker but can hit several objects, including torpedoes.
- Phasers fire where they point. Lock them on a ship with `lock banks on <ship>`, or select a target and they lock automatically. See [[lock]].

## Torpedoes

```console
fire all torpedoes
fire torpedo 1 2 3
fir tor al
torp 1
ft 1-3 at gorkon
```

- Tubes locked on a ship aim ahead of it, leading the target. A torpedo only explodes when it passes within its **proximity** setting of a ship, so a target that changes course can still dodge.
- Tubes reload by themselves after firing. Change the proximity or torpedo type with [[loading|load]] and `autoload`.

## Probes

```console
fire probes at gorkon
probe all at gorkon
fire probes 1 2 course 180
fpr 1 at gorkon
```

- A probe's target or course is set at launch. Afterwards you can steer it, re-target it or blow it up by its control code. See [[probes]].
- Probe launchers must be loaded first. See [[loading]].

## Aiming at a part of the ship

Add a subsystem to aim at part of the target: `propulsion`, `weapons`, `shields`, `power`, `sensors` (or `cloak`). Aimed shots trade some accuracy for a better chance of disabling that system.

```console
fire phasers at gorkon weapons
fire all torpedoes at gorkon propulsion
```

> **Coach** Not sure which weapon to use? Open the [[coach]]. It checks your target's range against each of your weapons and tells you which shot is on.
