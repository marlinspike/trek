---
title: Targeting
category: Weapons
order: 7
aliases: target, t, tgt, designate, subsystem, subsystems, aim, warp core, life support, precision fire
summary: Select a target, and aim at a part of it.
see: lock, scan, fire
---
Your target is the ship your weapons and the fire computer concentrate on. Click a ship, press **Tab**, or use `target`. On the map its brackets swing in and close on it, then pulse gently while the lock holds.

```console
target gorkon
target #7
target gorkon warp core
aim life support
aim hull
target off
```

## Aiming at her systems

Add a system to aim at part of the target, or say `aim <system>` once she is targeted. You can aim at:

- **shields** (shield generators): a destroyed generator leaves a permanent hole in her shields, which your transporters can beam through.
- **warp core** (`power`, reactors and batteries): without power her shields fail, and then her life support.
- **life support** (`crew`, the crew decks): every aimed hit that lands kills a slice of her crew.
- **weapons**, **phasers**, **torpedoes**: her phaser banks and torpedo tubes.
- **engines** (`propulsion`, warp drives and impulse).
- **sensors** (sensors and computer), and **cloak**.

Press **R** to cycle through them, or click them in the Target panel. Aimed fire only works on hits that get through her shields, so knock the facing shield down first. Each hit that gets through goes for what you aimed at, keeps after a system it has already hurt, and does only about a third of the usual damage to her hull. A shot that misses its mark is a single stray hit somewhere else. Accuracy is best close in, with a narrow phaser spread (`spread 10`) and a fresh `scan`. Fire at the hull (`aim hull`) when you simply want her destroyed.

> **Tip** To take a ship: aim at her **shields** until a generator is destroyed, then at her **life support** until her crew is gone, and [[transport|board]] her. Spare her **engines** if you mean to keep her: a destroyed warp drive can only be rebuilt at a base.
