---
title: Ally orders
category: Allies
order: 0
aliases: tell, order, orders, allies, ally, command allies, escort, defend, attack, withdraw, join, leave
summary: Give standing orders to the other ships in your fleet, one at a time or by group.
see: fleet, tactics, dock, tractor, transport
---
`tell <ally> <order>` gives one of your ships a standing order. Allies keep following their orders until you change them, and they report back in the console. `order` means the same as `tell`. Wherever an order names a ship, `me` means your own.

```console
tell excalibur attack gorkon
tell excalibur escort enterprise at 2000
tell excalibur defend me
tell 1 attack gorkon
tell excalibur hold fire
tell excalibur run
tell excalibur report
```

An ally carries several orders at once: one **movement** order, a **target**, **hold fire** or **open fire**, a **weapon** preference and a **group**. A new movement order replaces the old one, but leaves the target alone, and so on.

## From the screen

Click an ally on the map, or its row under **Contacts**, to open the **Fleet** tab beside the map. It shows that ally's mission and has a button for the common orders: escort me, defend me, attack my target, hold or open fire, run, withdraw, stop, cancel, dock at the nearest base, disengage, release a tow, and report. The **1**, **2** and **3** buttons put the ally in a group, or take it out again. Use **‹** and **›** to step through your allies.

On the map, each ally's mission is written under its name. A faint blue dashed line runs to the ship it is escorting, defending or towing, and a red one to its ordered target. The selected ally is marked with blue corners.

## Combat orders

| Order | Effect |
|---|---|
| `target <enemy>` | Shoot at this ship when it can, but keep its current movement order |
| `attack <enemy>` | Go after this ship and fight it, dropping the movement order |
| `torpedo <enemy>`, `phaser <enemy>`, `probe <enemy>` | Attack it, favouring that weapon |
| `hold fire` / `open fire` | Stop firing, or start again |
| `disengage` | Forget the ordered target |

## Movement orders

| Order | Effect |
|---|---|
| `escort <ship> [at <range>]` | Stay with a friendly ship (3,000 units unless you say) |
| `defend <ship>` | Stay close to a friendly ship and fight whatever threatens it |
| `approach <ship> [<range>]` | Close to a range of any ship and hold there (2,000 unless you say) |
| `course <c>` or `hold course` | Fly a set course |
| `run` | Get away from the enemy at full speed |
| `withdraw` | Pull back out of the fight and wait in reserve |
| `stop` | Come to a halt |
| `cancel` | Drop the movement order and go back to fighting on its own |

## Ship handling orders

| Order | Effect |
|---|---|
| `dock <base>` / `undock` | Dock at a friendly base, or leave it. See [[dock]]. |
| `tractor <ship>` / `release` | Grab a ship in a tractor beam, or let it go. See [[tractor]]. |
| `tow <ship> to <base>` | Drag a ship to a base |
| `board <enemy> <count>` | Close in and send a boarding party. See [[transport]]. |
| `recover <ship>` / `eject <ship>` | Bases only: bring a ship into the bays, or push it out |

## Groups

Put allies in numbered groups, then order the whole group by its number.

```console
tell excalibur join 1
tell lexington join 1
tell 1 escort enterprise
tell excalibur leave
group
```

## Checking on allies

`tell <ally> report` prints that ship's report, with its current mission. `fleet` lists every ally with its state and orders. See [[fleet]].

Allies are captained by the AI. Each captain has a personality, so some press an attack harder than others, and a badly damaged ship may break off even without an order.
