---
title: Phasers
category: Weapons
order: 1
aliases: phaser, phasers, banks, bank, spread, enable, disable, role
summary: Short-range beams that hit instantly but weaken with distance.
see: fire, lock, firecontrol, shields
---
Phasers are beam weapons mounted in **banks**. A hit lands the instant you fire, but it weakens with distance and is useless beyond the bank's range, which is about 2,000 for most ships. After firing, a bank recharges by itself from the ship's power.

## How hard they hit

A bank's hit grows with its charge, shrinks as the **spread** widens, and falls off with range: at three-quarters of maximum range a hit is only half as strong as at point blank. The shield facing the shot absorbs part of every hit.

{{phaser_falloff}}

> **Tip** Use spread 10 against a ship. Use a wide spread to sweep incoming torpedoes, or several small targets, out of the sky.

## Firing

```console
fire all phasers spread 10
fire phasers 1 2 3 spread 10
phaser all 45
```

## Pointing the banks

Each bank covers an arc around its mount. Locked banks follow their target; others hold a fixed **mark**, an angle from your bow (0 is dead ahead, 180 is astern).

```console
lock banks on gorkon
lock all banks on gorkon
lock banks 1 2 and 3 on gorkon
turn banks to 180
turn banks 1 2 to 90
```

## Charging, spread and roles

```console
disable banks 3 4
enable all banks
spread 20
role banks 5 6 defense
```

- **disable** stops a bank recharging, which saves power on a damaged ship. It keeps whatever charge it already has. **enable** resumes charging.
- **spread** sets the default spread used by **F** and by fire control.
- **role** reserves banks for point defense (`defense`), keeps them for attack (`offense`), or lets them do both (`flex`). See [[firecontrol]].

## Status

`banks` (or `status banks`) shows each bank's charge, whether it is locked or manual, its mark, its spread and its target.

```console
banks
```
