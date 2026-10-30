---
title: Named tactical orders
category: Game
order: 2
aliases: orders, execute, execute order, named orders, belay, plan, plans, beta-1, wait
summary: Write a sequence of orders before the battle, give it a name, and run it with one command.
see: console, plain-english, crew, keys
---
A named order is a short battle plan you write before the fight: a name and a list of steps. In battle, one command runs the whole list.

| Command | What it does |
|---|---|
| `execute order beta-1` | run the order called beta-1 (`execute beta-1` and `exec beta-1` work too) |
| `beta-1` | the same, by name alone |
| `orders` | list your named orders and their steps |
| `belay` | stop the order that is running; steps already run stay done |

Starting another order belays the one running.

## Writing them

Orders live in `config/orders.toml`. Copy `config/orders.example.toml` to start; until you do, the examples are loaded so you can try them.

```toml
[beta-1]
note = "Turn away, fan the torpedoes, let Spock fight while Seven goes for their shields"
steps = [
    "helm 180 speed 5",
    "fire all torpedoes spread 10",
    "wait 2",
    "spock, you have the conn",
    "seven, disable their shields",
]
```

Each step runs as if you typed it at the console, so anything the console takes works: helm and weapons orders, shields, orders to allies (`tell agena attack the target`) and orders to your officers (`worf, fire all phasers`, `spock, manage repairs`). An officer only does what their station allows, as when you speak to them yourself.

Steps run in the order written, and later ones can undo earlier ones: a helm order ends evasive manoeuvres, so put `evasive` after the course you want (the helm goes back to that course once the torpedoes are past).

`wait N` holds the order for N cycles of battle time before the next step. While the game is paused, the wait doesn't run down.

**"their", "the target" and "the enemy"** mean whichever ship you have targeted when the step runs, so one order works against any enemy. Target something first, or include a `target` step.

A name is letters, digits, `-` and `_`. An order can't run another order.

## Plain English

Steps don't have to be in console syntax. With a language model set up (see `help llm`), a step the console doesn't recognise, such as "come about and run", is put into console commands when the battle starts, checked against the console, and remembered in `config/orders.cache.json` so later battles don't need the model for it. Each step the model translates is shown as it runs, so you can see what it made of your words.

Without a model, write steps in console syntax. Either way, a step that won't work is reported in the log when the battle starts, not halfway through the fight, and is skipped if you run the order anyway.

## Example: a 10° torpedo fan

`fire all torpedoes spread 10` fans a full salvo 10° wide, so an enemy that turns away still meets a torpedo. At ordinary torpedo ranges a spread of only a degree or two adds little, because the 800-unit proximity fuses already cover that much. See `help torpedoes`.
