---
title: Lock and turn
category: Weapons
order: 4
aliases: lock, turn, mark, dispersion, unlock
summary: Point banks and tubes at a ship, or at a fixed angle.
see: phasers, torpedoes, targeting
---
Weapons fire in the direction they point. A **locked** mount follows its target. Tubes also lead it: they aim where the target will be when the torpedo arrives. Each mount can be locked on a different ship. If the target is destroyed, the mount returns to manual control.

## Lock

```console
lock banks on gorkon
lock all banks on gorkon
lock banks 1 2 and 3 on gorkon
lock tubes on gorkon 0
lock tubes 4 5 on gorkon 24
lock all tubes on gorkon with a dispersion of 45
lock on gorkon
lock off
```

- The number after the ship in a tube lock is the **dispersion**: the angle a salvo fans out around the lead point.
- `lock on <ship>` locks phasers and tubes together. Selecting a target with a click or **Tab** does the same.

## Turn

`turn` points mounts at a **mark**, an angle relative to your bow: 0 is dead ahead, 90 to starboard, 180 astern, 270 to port. A turned mount keeps that angle as the ship manoeuvres.

```console
turn banks to 180
turn all banks to 0
turn banks 1 2 to 90
turn tubes to 0
```

Probes are steered by course instead. See [[probes]].
