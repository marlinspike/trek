---
title: Status displays
category: Sensors and status
order: 0
aliases: status, st, report, damage, dmg, probes status, text displays, printout
summary: Text readouts of your ship, weapons, shields and fleet, printed in the console.
see: scan, chart, fleet, shields
---
Status commands print a table in the console, in the style of Begin's text displays. The table stays on screen and updates live until you press **Esc** or type another command. Scroll the log with the mouse wheel.

| Command | Shows |
|---|---|
| `report` | Name, class, survivors, condition, course and warp (desired and current) and target |
| `damage` or `status` | Every system with its damage, from reactors to transporters |
| `banks` | Each phaser bank: charge, mark, lock, role and arc |
| `tubes` | Each torpedo tube: what it holds, proximity, charge and lock |
| `launchers` | Each probe launcher: probe type, proximity, timer and lock |
| `status probes` | Your probes in flight, with their control codes |
| `shields` | Each shield's state, strength and recharge rate |
| `fleet` | Your allies, their state and their standing orders |
| `group` | Which allies are in which numbered group |

`status` takes the name of any of these as a second word, so `status banks` is the same as `banks`. The short form `st` works too.

```console
report
damage
status tubes
banks
shields
fleet
```

## The panels

The right-hand panels show the same information at a glance: the weapons panel lists every bank, tube and launcher; the engineering panel shows power, heat and damage. Press **I** for the damage view, which lays the damage out over a picture of your ship.

Scanning an enemy prints its damage table the same way. See [[scan]].
