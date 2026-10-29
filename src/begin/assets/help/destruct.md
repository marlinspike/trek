---
title: Self-destruct and surrender
category: Ship systems
order: 5
aliases: destruct, self, selfdestruct, sd, self destruct, abort, surrender, give up
summary: Blow up your own ship on a countdown, or surrender it.
see: transport, tactics
---
## Self-destruct

`self destruct <cycles>` starts a countdown. When it reaches zero, your ship explodes, and the blast damages every ship nearby, friend or foe. The more power your ship had, the bigger the blast.

```console
self destruct 10
abort
```

- `abort` (or `self destruct abort`) stops the countdown, but only while more than five cycles remain. After that, nothing can stop it.
- The last five cycles are announced to everyone, so enemies may try to get clear.
- Beam to an ally first if you want to keep fighting. See [[transport]].

## Surrender

`surrender` lowers every shield and gives up the ship. A surrendered ship takes no further part in the battle, and it counts against you in the assessment.

```console
surrender
```
