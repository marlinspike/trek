---
title: Alert conditions
category: Game
order: 3
aliases: alert, condition, red alert condition, condition red, yellow alert, green
summary: alert red, yellow or green: a set of orders at once, and the condition shown on the map.
see: orders, bridge, shields
---
`alert red` runs every line of the red condition at once, as if you had typed them, and shows **CONDITION RED** at the top of the map. The tactical officer reads it back.

| Command | Out of the box |
|---|---|
| `alert red` | raise shields all · pd balanced · autoload torpedoes on |
| `alert yellow` | raise shields all · pd conservative |
| `alert green` | lower shields all · pd off |
| `alert` | the condition now, and what each one does |

Make them your own: copy `content/data/alerts.toml` to `config/alerts.toml` and change the steps. Any console line works, including an order to an officer ("geordi, manage repairs").

The red border the panels take on in a fight is the ship's own red alert, and comes and goes by itself.
