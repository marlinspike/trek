---
title: Welcome aboard
category: Getting started
order: 0
aliases: index, contents, home, help
summary: How to use this manual, and where to start.
---
This manual covers every command, how each weapon works, and how to win. Open it at any time with **H**, or by typing `help` or `man` in the console. To go straight to one command, type `help <command>`. Short forms work here too, so `help tor` opens the torpedo page.

> **Coach** The [[coach]] page reads the battle you are in and tells you what to do next: whether your target is inside your torpedo envelope, which torpedo and proximity setting suit it, and which shield to turn toward the enemy.

## Start here

- [[first-battle|Your first battle]]: a five-minute walkthrough.
- [[controls|Keyboard and mouse]]: every key.
- [[console|The command console]]: how commands are typed, shortened and combined.
- [[fire|Fire]]: everything you can shoot, and how.
- [[weapons-guide|Choosing weapons]]: torpedo and probe types compared, with live numbers.

## Using this manual

- Type anywhere in this window to search. Press **Enter** to open the best match.
- Click a link to follow it, and press **Backspace** or **‹ Back** to return.
- Lines marked **›** are example commands. Click one to put it in the console, ready to edit and send.

```console
help fire
man tor
coach
```

## Editing the manual

Every page is a Markdown file. You can change the wording, add tips, or write new pages without touching the code. The path of the page you are reading is shown in the bottom-right corner of this window.

- The bundled pages live in `src/begin/assets/help/`.
- To keep your own versions separate, put `.md` files in the project's `config/help/` folder (or in the folder named by `BEGIN_HELP_DIR`). A file there replaces the bundled page with the same name, and new files become new pages.
- Pages reload automatically when the files change.

The page format is described in [[writing-help|Writing help pages]].
