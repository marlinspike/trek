---
title: Scan
category: Sensors and status
order: 3
aliases: scan, sc, sensors, identify, detailed scan
summary: Take a detailed scan of a ship to learn its class and damage.
see: chart, status, targeting
---
`scan <ship>` points your sensors at one ship for a detailed scan. The scan identifies the ship and prints its damage table, so you can see which of its systems are hurt and pick your next target.

```console
scan gorkon
scan
scan #3
```

- `scan` alone scans your current target.
- The ship must be on your sensors and within detailed-scan reach, which is shorter than detection range. If it is too far, the reply tells you how close you need to be.
- Scanning one of your own ships shows its damage table straight away.
- **X** scans the current target.

`scan` followed by a distance, such as `scan 8000`, sets the [[range|display range]] instead, as in the original game.

Cloaked ships can't be scanned until they show themselves. See [[cloak]].
