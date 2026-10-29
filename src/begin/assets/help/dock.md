---
title: Docking
category: Ship systems
order: 2
aliases: dock, undock, starbase, base, docking, recover, eject
summary: Dock at a friendly base to repair faster, rebuild destroyed systems and shelter from fire.
see: repair, tractor, tell
---
Ships can dock at a friendly base that has docking bays. Fly within 1,000 units and give the order.

```console
dock starbase 12
undock
dock off
```

## While you are docked

- Repairs run twice as fast, and even destroyed systems can be rebuilt.
- Your crew does not draw on your own life support.
- Weapons and explosions cannot reach you: the base shelters you.
- You move with the base, and you cannot escape the battle on your own.

The base's bays hold a limited mass of ships. If they are full, you have to wait for someone to leave.

## Allies and bases

- `tell <ally> dock <base>` sends an ally to dock, and `tell <ally> undock` brings it out.
- A base you command can bring a ship aboard with `tell <base> recover <ship>`, and push one out with `tell <base> eject <ship>`.

If a base is destroyed, every ship docked in it is cast loose.
