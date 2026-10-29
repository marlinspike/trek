---
title: Repair
category: Ship systems
order: 0
aliases: repair, damage control, fix, engineering
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

## What limits repair

- Repairs go faster with a full crew. A ship that has lost most of its crew repairs slowly, and below a tenth of its crew it cannot repair at all.
- A **destroyed** system cannot be fixed in space. Dock at a starbase, where repairs run twice as fast and destroyed systems can be rebuilt. See [[dock]].

Check progress with `damage`. See [[status]].
