---
title: Library computer
category: Sensors and status
order: 4
aliases: computer, library, database, lookup, specs
summary: Look up the specifications of any ship class, torpedo or probe.
see: weapons-guide, scan
---
The library computer holds the specifications of every ship class, torpedo and probe in the game. Ask it about a subject and it prints the details in the console.

```console
computer ship klingon d7
computer ship federation
computer torpedo photon
computer probe
library torpedo
```

- `computer ship <nation> <class>` shows one class. Leave the class out to list every class of that nation.
- `computer torpedo <type>` and `computer probe <type>` show one weapon. Leave the type out to list them all.
- Any unique beginning of a name works, so `computer ship fed` lists the Federation classes.

The [[weapons-guide]] shows the same weapon numbers side by side in tables.
