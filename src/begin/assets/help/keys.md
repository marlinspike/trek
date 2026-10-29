---
title: Key macros
category: Game
order: 1
aliases: key, keys, macro, macros, bind, text, text mode
summary: Bind a function key or Ctrl+letter to one or more console commands.
see: controls, console
---
`key <key> <commands>` binds a key to console commands. Pressing the key runs them as if you had typed them. Separate several commands with `;`.

```console
key F2 fire all torpedoes
key F3 fire all phasers 10; fire all torpedoes
key ^r raise all; reinforce 1
key F4
key
```

- Keys you can bind: **F2** to **F8**, **F10** to **F12**, and **Ctrl+letter**, written `^a` to `^z`. **F1** opens the manual and **F9** the debug view, so those two are taken.
- `key <key>` with no commands clears that key. `key` alone lists your bindings.
- Bindings are saved, so they are there next time you play.

## Keeping a key file

You can also write your bindings in a text file called `begin2.key` in the project's `config/` folder, one per line, in the same form as the command: `F2 fire all torpedoes`. They are loaded when the game starts.

## Text mode

The original game could switch to a text-only display. This remake always shows the tactical map, so `text` just says so. The status commands print the original text displays in the console instead. See [[status]].

For the fixed keyboard shortcuts, see [[controls]].
