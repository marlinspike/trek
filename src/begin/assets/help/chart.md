---
title: Chart
category: Sensors and status
order: 1
aliases: chart, contacts, list ships, positions
summary: A table of every ship you can see, with range, bearing, course and speed.
see: scan, range, status
---
`chart` prints a table of every ship and base you have on sensors: its name, warp, course, bearing, range, the mark (its bearing relative to your bow) and its class.

```console
chart
chart on
chart by distance
chart from gorkon
chart all
chart off
```

| Form | Effect |
|---|---|
| `chart` | Print the table once |
| `chart on` / `chart off` | Keep the table up and updating, or close it |
| `chart by name`, `by distance`, `by nation` | Sort order |
| `chart from <ship>` | Measure ranges and bearings from another ship instead of yours |
| `chart <ship> off` / `chart <ship> on` | Hide a ship from the table, or show it again |
| `chart all` | Show every ship, including hidden ones |

Ships you have not identified yet show as `#` followed by their contact number, such as `#7`. You can type that number in any command that takes a ship (`scan #7`, `target #7`), and a detailed [[scan]] identifies the ship.
