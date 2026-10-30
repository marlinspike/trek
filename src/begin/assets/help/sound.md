---
title: Sound
category: Game
order: 3
aliases: sound, volume, audio, mute, sound effects
summary: Soft synthesised sound for what you can see happen, with a volume setting and a mute key.
see: controls, time
---
The battle has quiet, synthesised sound: beams (a clean tone for phasers, buzzing bolts for disruptors), torpedoes leaving their tubes, warheads going off, shields turning a blow, ships breaking up, a cloak engaging or dropping, and two soft notes when your ship goes to red alert. The game makes every sound itself when it starts; there are no sound files.

You hear only what you can see. Each sound comes from where it happened on the map: from the left or right of the view, fainter when it is just off screen, and silent when it is far away.

| Command | What it does |
|---|---|
| `M` | sound on or off |
| `sound off`, `sound on` | the same, from the console |
| `sound 40` | set the volume, 0 to 100 |
| `sound` | say what the sound is set to |

The volume and whether it's muted are saved in `config/settings.json` (`volume`, 0 to 1, and `muted`). Without an audio device the battle is simply silent.
