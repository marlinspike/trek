---
title: Keyboard and mouse
category: Getting started
order: 1
aliases: controls, keyboard, mouse, shortcuts, hotkeys, hud, detail, display
summary: Every key and mouse action in battle.
see: console, keys
---
## Time

| Key | Action |
|---|---|
| **Space** | Pause or resume. Orders still work while paused. |
| **[** and **]** | Slower or faster: 0.25×, 0.5×, 1×, 2×, 4×. One cycle is one second at 1×. |

## Helm

| Key or mouse | Action |
|---|---|
| **W** / **S** | Warp up or down by one |
| **A** / **D** | Turn 15° to port or starboard (hold **Shift** for 5°) |
| Right-click the map | Steer toward that point |
| **Shift** + right-click a ship | Pursue it |

## Weapons and targeting

| Key or mouse | Action |
|---|---|
| Left-click a ship, or **Tab** | Select a target (**Shift+Tab** goes backwards) |
| **R** | Aim at a subsystem: propulsion, weapons, shields, power, sensors |
| **F** | Fire phasers |
| **T** | Fire torpedoes |
| **P** | Launch a probe at the target |
| **X** | Scan the target |
| **V** | Cycle the point-defense doctrine |
| **G** | Raise or lower all shields |

## View

| Key or mouse | Action |
|---|---|
| Mouse wheel, **+** / **−** | Zoom (or type `range 8000`) |
| Drag, arrow keys | Pan the map |
| **C** | Centre on your ship and follow it |
| **Q** | Show phaser arcs |
| **I** | Damage view |
| **M** | Sound on or off. See [[sound]]. |
| Mouse wheel over the log | Scroll the console log |

## Console and help

| Key | Action |
|---|---|
| **Enter** or **/** | Open the command console. See [[console]]. |
| **↑** / **↓** in the console | Previous and next commands |
| **H** | Open this manual |
| **F1** | Open this page |
| **F2–F8, F10–F12**, **Ctrl+letter** | Run a key macro. See [[keys]]. |
| **Esc** | Close the open window or text display, or open the battle menu |

## How much the panels show

The panels show what matters at a glance: warp, course, crew, hull, morale, and shield arcs coloured by strength. Hover over the Own ship panel and it shows every number: shield strengths, maximum warp, power in and out, the magazine. Numbers ease to their new value instead of jumping, and flash briefly when they change: brighter for a rise, warmer for a fall.

| Command | What it does |
|---|---|
| `hud detail` | always show every number |
| `hud simple` | back to the essentials (hover a panel for the rest) |
| `hud` | say which it is |

