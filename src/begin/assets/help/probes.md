---
title: Probes
category: Weapons
order: 3
aliases: probe, probes, launchers, launcher, detonate, det, codes, control code
summary: Slow, steerable warheads that home in. Controlled by code after launch.
see: fire, loading, weapons-guide
---
Probes are slow but smart. Most home in on a target, they can be steered or re-targeted after launch, and their warheads are large. A ship slower than the probe cannot outrun it. Data probes carry little or no warhead but extend your sensors.

{{probe_table}}

## Loading

Probe launchers do not need power to load or fire. When you load a launcher, its probe gets a **control code** such as `h01`, which you use to control it after launch.

```console
load launchers 1 prox 500 time 20
load all launchers 450 15
load probes 200 10
unload all launchers
launchers
```

- The first number is the **proximity** fuse and the second the **time** fuse in cycles.
- A launcher you unload stays empty until you load it again.

## Launching

```console
fire probes at gorkon
probe all at gorkon
fire probes 1 2 course 180
```

## Controlling probes in flight

`status probes` lists your active probes with their codes, courses, ranges and targets.

```console
status probes
turn probe h01 course 90
turn all probes to course 270
lock probe h01 on gorkon
lock all probes on gorkon
detonate h01
detonate all
```

> **Tip** If you know an enemy probe's control code, you can steer or detonate it too.
