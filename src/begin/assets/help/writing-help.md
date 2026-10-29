---
title: Writing help pages
category: Game
order: 90
aliases: help format, markdown, edit help
summary: The Markdown format the manual uses, for editing or adding pages.
---
Each page is a `.md` file. It starts with a short header between `---` lines:

```
---
title: Torpedoes
category: Weapons
order: 2
aliases: tor, torp, torpedo, torpedoes
summary: One line shown under the title and in search results.
see: fire, lock, loading
---
```

- **category** groups pages in the sidebar. The built-in groups are Getting started, Coach, Helm, Weapons, Defense, Sensors and status, Ship systems, Allies and Game.
- **aliases** are the words `help <word>` matches. Add a command's name here, and `help <command>` and its short forms will find the page.
- **see** adds "See also" links at the bottom of the page.

## Formatting

| You write | You get |
|---|---|
| `# Heading`, `## Section`, `### Sub-section` | headings |
| `**bold**`, `*italic*`, `` `code` `` | inline styles |
| `- item` / `1. item` | lists |
| `[[torpedoes]]` or `[[torpedoes|the torpedo page]]` | a link to another page |
| `> **Tip** text` | a callout (Tip, Coach, Note, Warning, Example) |
| a table with `|` columns | a table |

A code block fenced with ```` ```console ```` holds example commands. Each line becomes clickable and is put in the console when clicked.

## Live blocks

These placeholders are replaced with up-to-date tables and advice built from the game data:

| Placeholder | Shows |
|---|---|
| `{{coach}}` | advice for the current battle |
| `{{my_weapons}}` | the weapons of the ship you command |
| `{{torpedo_table}}` | every torpedo type compared |
| `{{probe_table}}` | every probe type compared |
| `{{phaser_falloff}}` | phaser damage by range and spread |
| `{{class_table}}` | every ship class |
