---
title: Sound
category: Game
order: 3
aliases: sound, volume, audio, mute, sound effects, phaser sound, torpedo sound, wav, hum, engine hum, klaxon
summary: Soft synthesised sound for what you can see happen, with a volume setting and a mute key.
see: controls, time
---
The battle has synthesised sound, and each sound tells you something you might not be looking at:

| You hear | It means |
|---|---|
| a beam (phasers) or buzzing bolts (disruptors) | a bank fired; a full-charge shot sounds heavier than a weak one, a point-defense flick lighter still |
| a mechanical knock under the launch | a torpedo left its tube |
| a rising, rushing whoosh | an enemy torpedo is closing on one of your ships: turn now |
| a bright ring that thins as the facing weakens | a shield turned a blow |
| a falling crackle | a shield facing gave way |
| a metallic crunch over a low boom | a blow got through to a hull; deeper for a big one |
| warheads going off, ships breaking up, a cloak's airy sweep | what it sounds like |
| a two-tone whoop, three times | your ship has gone to red alert |
| a clean rising pair of notes | you locked a new target |
| a soft chirp, or a low double tone | an order was taken, or "unable to comply" |
| a short whistle up, or down | a hail channel opened, or closed |
| a low engine hum | the ship herself, under everything, rising with her warp and dipping under a big blast |

A blow from a phaser is heard when the beam gets there, not when the bank fires. The game makes every sound itself when it starts.

You hear only what you can see. Each sound comes from where it happened on the map: from the left or right of the view, quieter and duller when it is off at the edge, and silent when it is far away.

| Command | What it does |
|---|---|
| `M` | sound on or off |
| `sound off`, `sound on` | the same, from the console |
| `sound 40` | set the volume, 0 to 100 |
| `sound` | say what the sound is set to |
| `sound phaser a` | use version a of the phaser (a, b, c or d), and play it |
| `sound torpedo b` | use version b of the torpedo launch |
| `sound hum off`, `sound hum on`, `sound hum 20` | the ship's engine hum: off, back on, or how loud (a share of the volume) |

The phaser comes in four versions. **a**, **b** and **c** are rays: noise fed round a tuned feedback loop so the beam sings at one steady pitch and sizzles while it fires (a is a single piercing tone, b is higher and shimmers, c is the ray over d's buzz). **d**, the standard one, is a harsh square-wave buzz.

The torpedo launch does too. **a**, **b** and **c** are energy pulses: a bright burst that drops fast from high to low and rings away (a is the plain pulse, b winds up first and has d's thump under it, c is short and sharp). **d**, the standard one, is a deep "thoom" with a falling whoosh.

### Your own sounds

Put a WAV (or OGG) file in `config/sounds/` and it replaces the game's own: `phaser.wav`, `torpedo.wav` (or `launch.wav`), and also `pulse`, `blast`, `fizzle`, `shield`, `breakup`, `cloak`, `alert`, `thunk`, `incoming`, `collapse`, `hull`, `lock`, `confirm`, `deny`, `hail_open`, `hail_close` or `hum` (the hum loops). They are read when a battle starts, and they stay on your machine (git ignores everything in `config/`). Delete the file to go back to the made sound.

The volume, whether it's muted and the versions you picked are saved in `config/settings.json` (`volume`, 0 to 1, `muted`, `sounds`, such as `{"phaser": "b", "torpedo": "a"}`, and `hum`, 0 to 1). Without an audio device the battle is simply silent.
