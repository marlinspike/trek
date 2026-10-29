---
title: Fire control and point defense
category: Weapons
order: 6
aliases: mode, firemode, fm, pd, point defense, pointdefense, automatic, assisted, manual
summary: Let the ship's computer fire for you, and defend against incoming torpedoes.
see: phasers, torpedoes
---
The ship's computer can share the gunnery. It never overrides an order you give: a command from you always takes priority for several cycles.

## Fire modes

| Mode | The computer… |
|---|---|
| **manual** | fires only when you order it |
| **assisted** | fires at *your* target when the shot is good |
| **automatic** | picks the nearest enemy if you have no target, and fires when the shot is good |

```console
mode phasers automatic
mode tubes 1 2 assisted
mode tubes manual
```

The **Mode** button in the weapons panel cycles these too. Autoload never fires anything; it only reloads.

## Point defense

Point defense uses phaser banks to shoot down incoming torpedoes and probes. How far ahead the computer predicts, and how precisely it aims, depend on how advanced and how damaged your ship's computer is.

| Doctrine | Banks it uses |
|---|---|
| **off** | none |
| **conservative** | reserved banks only, against imminent hits |
| **balanced** | reserved banks, plus flexible banks against dangerous salvos |
| **aggressive** | any idle bank, against anything armed and in range |

```console
pd balanced
pd conservative reserve 5 6
role banks 1 2 offense
```

Press **V** to cycle doctrines, or right-click a bank in the weapons panel to reserve it.
