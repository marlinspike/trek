---
title: Cease fire
category: Weapons
order: 3
aliases: cease, cease fire, hold, hold fire, stop firing, open, open fire, stand down, belay all, everyone stop
summary: Stop every weapon at once, and the officers with them; stand down takes every station back too.
see: fire, crew, orders
---
`cease fire` stops your ship's guns at once. It never waits on the language model, and it drops any line still being interpreted.

- Every officer's standing objective ends, such as Seven disabling their shields, and a bait volley about to follow its first torpedo is called off.
- Officers and the fire computer (assisted or automatic weapons) hold fire until you fire again yourself or say `open fire`.
- Point defense keeps shooting down incoming torpedoes.

```console
cease fire
hold fire
stop firing
open fire
```

You can say it to an officer too: `seven, cease fire`, `seven, stop firing` or `worf, hold fire`. A cease fire stops the guns only: if Spock is flying the ship, he keeps flying it.

## Stand down

To stop an officer outright, tell them to stop: `spock, stop`, `spock, stand down`, `seven, belay that`, `seven, forget the shields` or `seven, stop disabling their shields`. Everything a cease fire does happens, and the officer hands back what they were running: their station, the bridge if they had it, and evasive manoeuvres. A helm that was chasing the enemy steadies on its present course.

To stop the whole bridge at once, say `stand down`, `everyone stop`, `all stations, stand down`, `stop everything` or `belay all`. Every station and the bridge come back to you, and a running named order stops too.

```console
spock, stand down
seven, stop
stand down
everyone stop
belay all
```

Taking a station back with `assume <station>` (or `assume all`) also ends whatever that officer was working on, such as Seven disabling their shields, without holding your fire. `belay` on its own stops a running named order and ceases fire.

> **Note** A bare `stop` is all stop for the helm (warp 0), as in Begin. Say `stop firing` to stop the guns, or `stand down` to stop the officers. If an officer is still flying or working when you say it, the log tells you who.
