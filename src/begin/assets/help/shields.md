---
title: Shields
category: Defense
order: 0
aliases: shields, shield, raise, up, lower, drop, down, reinforce, reenforce, rf
summary: Raise, lower and reinforce your six shields, and keep a strong one facing the enemy.
see: firecontrol, tactics, transport, status
---
Your ship has six shields, each guarding a 60° slice around the hull. A hit is taken by the shield facing the attacker; the others are not touched.

| Shield | Faces |
|---|---|
| 1 | bow (straight ahead) |
| 2 | forward starboard (right) |
| 3 | forward port (left) |
| 4 | aft starboard |
| 5 | aft port |
| 6 | stern |

```console
raise all
lower 4 5 6
raise shields 1 2 3
shields
reinforce 1
reinforce off
```

- `raise` and `lower` take a list of shields or `all`. `drop` and `down` also lower; `up` also raises.
- `shields` alone (or `status shields`) prints each shield's state, strength and recharge rate.
- **G** raises or lowers every shield at once.

## Energy

A shield that is up costs energy every cycle, and it recharges when it has been weakened. Power goes to warp and life support before shields, and if what is left cannot pay for every raised shield, **none** of them hold that cycle. When power is tight, lower the shields that face away from the enemy, or slow down.

## Reinforcing

`reinforce <n>` makes one shield lose strength at half the rate when it is hit, at four times the energy cost. Only one shield can be reinforced at a time. Reinforce the one facing the enemy, then turn to keep it there. `reinforce off` ends it.

## When shields must come down

Transporters cannot beam through a raised shield, so both your shield and the other ship's shield that face each other must be down. See [[transport]].

Surrendering lowers every shield.
