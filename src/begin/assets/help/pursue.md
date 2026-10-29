---
title: Pursue and elude
category: Helm
order: 1
aliases: pursue, chase, follow, elude, evade, flee, intercept
summary: Let the helm chase a ship, or keep away from it, automatically.
see: helm, tactics, tell
---
`pursue` hands steering to the helm computer, which keeps turning to intercept a ship. `elude` does the opposite: it keeps turning away from one.

```console
pursue gorkon warp 6
pursue gorkon
chase #3 8
elude gorkon warp 7
```

- The warp is optional. Without it, the ship keeps its current speed.
- The pursuit lasts until you give another helm order, such as `helm 90` or `stop`.
- You can name the ship, use its number from the [[chart]] with a `#` in front (`#3`), or type a unique part of its name.
- **Shift** + right-click a ship on the map also starts a pursuit.

## When to use which

Pursue a ship you want to keep inside your weapon range, especially one that is trying to run. Elude a ship that outguns you at close range, or a stream of incoming probes. The [[coach]] says when the range is wrong for your weapons.
