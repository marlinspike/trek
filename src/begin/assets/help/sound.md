---
title: Sound
category: Game
order: 3
aliases: sound, volume, audio, mute, sound effects, phaser sound, torpedo sound, wav
summary: Soft synthesised sound for what you can see happen, with a volume setting and a mute key.
see: controls, time
---
The battle has synthesised sound: beams (a bright, buzzing held beam for phasers, buzzing bolts for disruptors), torpedoes leaving their tubes with a thump and a falling whoosh, warheads going off, shields turning a blow, ships breaking up, a cloak engaging or dropping, and two soft notes when your ship goes to red alert. The game makes every sound itself when it starts.

You hear only what you can see. Each sound comes from where it happened on the map: from the left or right of the view, fainter when it is just off screen, and silent when it is far away.

| Command | What it does |
|---|---|
| `M` | sound on or off |
| `sound off`, `sound on` | the same, from the console |
| `sound 40` | set the volume, 0 to 100 |
| `sound` | say what the sound is set to |
| `sound phaser b` | use version b of the phaser (a, b or c), and play it |
| `sound torpedo c` | use version c of the torpedo launch |

The phaser comes in three versions: **a** is a bright saw tone with a metallic ring and a shimmer, **b** a harsher square-wave buzz, and **c** two tones a fifth apart, throbbing and gritty. The torpedo launch does too: **a** is a deep "thoom", **b** a brighter, quicker "pshew", and **c** a heavy launch with a tone dropping away under it.

### Your own sounds

Put a WAV (or OGG) file in `config/sounds/` and it replaces the game's own: `phaser.wav`, `torpedo.wav` (or `launch.wav`), and also `pulse`, `blast`, `fizzle`, `shield`, `breakup`, `cloak` or `alert`. They are read when a battle starts, and they stay on your machine (git ignores everything in `config/`). Delete the file to go back to the made sound.

The volume, whether it's muted and the versions you picked are saved in `config/settings.json` (`volume`, 0 to 1, `muted`, and `sounds`, such as `{"phaser": "b", "torpedo": "a"}`). Without an audio device the battle is simply silent.
