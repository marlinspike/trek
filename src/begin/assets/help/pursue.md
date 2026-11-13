---
title: Pursue and elude
category: Helm
order: 1
aliases: pursue, chase, follow, elude, evade, flee, intercept, hold range, standoff
summary: Let the helm chase a ship, keep away from it, or hold it at a range you choose.
see: helm, tactics, tell
---
`pursue` hands steering to the helm computer, which keeps turning to intercept a ship. `elude` does the opposite: it keeps turning away from one.

```console
pursue gorkon warp 6
pursue gorkon
chase #3 8
elude gorkon warp 7
elude gorkon at 9000
pursue gorkon warp 6 at 4000
```

- The warp is optional. Without it, the ship keeps its current speed.
- The pursuit lasts until you give another helm order, such as `helm 90` or `stop`.
- You can name the ship, use its number from the [[chart]] with a `#` in front (`#3`), or type a unique part of its name.
- **Shift** + right-click a ship on the map also starts a pursuit.
- Add `at` and a range to hold her there instead: the helm closes when she is beyond it, opens the range when she is inside it, and circles her in between. `elude gorkon at 9000` keeps a heavy cruiser at torpedo range, outside her phasers, without running off the map. A bare number above 100 means a range too (`elude gorkon 9000`). The map line reads "holding at 9,000".

## When to use which

Pursue a ship you want to keep inside your weapon range, especially one that is trying to run. Elude a ship that outguns you at close range, or a stream of incoming probes. Plain `elude` keeps running for as long as the order stands, and a ship far enough from every enemy has left the battle: when you mean to fight her at your range, not leave, give the range (`elude gorkon at 9000`). The officers' [[counsel]] does.

A runner on a set heading is better met than chased: a `helm` course that leads her, at your best warp, closes the distance a stern chase never will. Spock works one out in the counsel when there is a runner to stop (see [[missions]]). The [[coach]] says when the range is wrong for your weapons.
