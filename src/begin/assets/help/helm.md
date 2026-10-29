---
title: Course and speed
category: Helm
order: 0
aliases: helm, h, course, c, warp, w, speed, stop, allstop, halt, steer, heading, move
summary: Set your course in degrees and your speed in warp.
see: pursue, tactics, controls
---
The helm takes a **course** and a **warp**. Courses are compass bearings in degrees: 0 is straight up the map, 90 is to the right, 180 is down and 270 is to the left. Negative courses count the other way, so `-90` is the same as `270`.

```console
helm 90 warp 4
helm 45
warp 6
90 4
stop
```

- `helm <course>` turns without changing speed, and `warp <w>` changes speed without turning.
- Two bare numbers are read as course and warp, so `90 4` is short for `helm 90 warp 4`.
- `stop` (or `allstop`) brings the ship to a halt.
- The ship turns at its own rate, so a big course change takes a few seconds. Heavy ships turn slowly.

## How fast can you go?

Every warp factor is 100 units of distance per cycle. Your top speed is limited by your class, by damage to your drives and by the power you have left over for shields and weapons. If you ask for more than you can reach, the helm tells you and uses the most it can.

Warp heats your drives. A drive that overheats burns out, so watch the temperature gauges on the engineering panel when you run at high warp. The [[coach]] warns you before that happens.

## Mouse and keys

- Right-click the map to steer toward a point.
- **W** and **S** change warp by one. **A** and **D** turn 15° (5° with **Shift**).

Starbases and other bases cannot move.
