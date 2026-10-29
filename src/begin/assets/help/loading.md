---
title: Loading and autoload
category: Weapons
order: 5
aliases: load, unload, autoload, al, reload, ld, ul
summary: Torpedo and probe loading, proximity and time fuses, and ordnance type.
see: torpedoes, probes
---
Torpedo tubes and probe launchers **autoload**: after firing, each reloads with the same settings. `load` sets the fuses and starts loading, `unload` empties mounts so new settings take effect, and `autoload` picks the ordnance type or switches automatic reloading off.

## Torpedo tubes

```console
load tubes prox 500
load tubes 1 2 3 350
load all tubes prox 425
unload all tubes
```

## Probe launchers

```console
load launchers 1 prox 500 time 20
load all launchers 450 15
unload launchers 2
```

## Autoload

```console
autoload tor all mk8 400
al tor al mk7 1200
autoload probes 1 px2 300 20
al tor off
al tor now
```

The words after `autoload` are, in any order: the weapon (`tor` or `probe`), the mounts, the ordnance type, the proximity, a probe time fuse (`time 20`), `on`/`off`, and `now` to reload at once with the new settings.

> **Note** Proximity limits depend on the ordnance type. If you ask for more than a type allows, the order is refused and the limit is shown. See the tables in [[weapons-guide]].
