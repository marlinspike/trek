---
title: The command console
category: Getting started
order: 2
aliases: console, syntax, abbreviations, commands, typing
summary: How commands are typed, shortened and combined.
see: fire, controls, keys, plain-english
---
Press **Enter** to open the console, type an order and press **Enter** again. Commands follow Begin's own wording, so a Begin captain can type what they always typed.

```console
helm 90 warp 4
fire all phasers spread 10
lock all tubes on gorkon
tell agena attack gorkon
```

## Shortening words

Any word can be cut to a unique prefix, as in Begin. These all fire every torpedo tube:

```console
fire all torpedoes
fir tor al
torp all
ft
```

If a prefix matches more than one command, the console says which ones it could mean (`lo` could be `lock`, `load` or `lower`).

## Lists of mounts

Phaser banks, torpedo tubes, probe launchers and shields are numbered from 1. All of these forms work:

| You type | Means |
|---|---|
| `all`, `al` (or nothing) | every mount |
| `1 2 3`, `1,2,3`, `1 2 and 3` | those mounts |
| `1-3` | a range |

```console
fir tor 1,2,3
lock banks 1 2 and 3 on gorkon
lower shields 4-6
```

## Ships and filler words

- Name a ship by any unique start of its name: `pursue gor`. An unidentified contact is `#` followed by its number, as shown on the map: `target #7`.
- Words like *the*, *to*, *at*, *on*, *with* and *of* are ignored, so `tell the agena to attack the gorkon` works.

## Several commands at once

Separate commands with `;` to send them together. This is also how [[keys|key macros]] work.

```console
lock all banks on gorkon; fire all phasers spread 10
```

## Results

- Orders are acknowledged in the log under the map, and rejected orders say why.
- Status commands such as `banks`, `tubes` or `chart` print a table. The latest table stays on the map and keeps updating until you press **Esc**. See [[status]].
