---
title: Display range
category: Sensors and status
order: 2
aliases: range, display, rng, zoom, scale, display range
summary: Zoom the tactical map by setting how far it reaches.
see: chart, scan, controls
---
`range <distance>` sets how far the tactical map reaches from its centre, from 200 to 500,000 units. `range` on its own tells you the current setting.

```console
range 8000
range 40000
display 2000
range
```

- `display`, `zoom` and `scale` mean the same thing, and `scan <distance>` does too.
- The mouse wheel and the **+** and **−** keys zoom in steps. **C** centres the map on your ship.
- A useful rhythm: zoom out to 40,000 or more to find the enemy, then in to 5,000 to 10,000 for a gunfight.

The display range is only a view. It does not change what your sensors can see.
