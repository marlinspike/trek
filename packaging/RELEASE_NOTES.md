## What's new in 1.2

**Begin : Trek.** The title screen now carries the remake's own name; Begin is the original game it remakes.

**Settings in the game.** A Settings page on the main menu (S) changes everything you used to edit in the config folder: display, sound with a sample of each phaser and torpedo, the speed battles start at, the bridge style and its parts, speaking orders, the officers' language model and the character voice model (each with a Test button), and your officers' names, ranks, traits and how they speak. Each change is saved at once; in `officers.toml` only the line you change is written.

**Command from the bridge.** Every order you give is read back by the officer at that station ("Course 090, warp 6."), and officers speak in subtitles low on the map, with the log split into Bridge and Computer columns. Right-click a ship (or press E) for a command wheel; while you type, the battle eases to a quarter speed, the map shows a ghost of what Enter would do, and Tab finishes names. Officers now and then propose an order (Y makes it so, N belays it). `alert red`, `yellow` and `green` give a set of orders at once, `record` saves what you just did as a named order, the new Orders tab holds them all as cards, and `style` promises a way of commanding for a ribbon. Each officer's trust in you grows across battles, from Green to Veteran, and changes what they will do. None of it replaces anything: keys, clicks and the console work as before, and `hud bridge classic` turns it all off.

**Speak your orders.** Hold Right Alt (Option on a Mac), say the order, let go. The Mac's own recogniser, whisper.cpp on your computer, a whisper.cpp server or a cloud service hears it; the `voice` page picks one and tests it. The first time, your computer asks whether Begin may use the microphone.

**Patrols.** A new mode on the main menu (P): a fresh single battle each time, one of five situations (an ambush, a wolf pack, a second wave, an escort or an enemy flagship behind her screen) against a random enemy.

**Sharp on Retina and 4K.** The game now draws at your screen's real pixel density through the graphics card, so text, hulls and beams are crisp. Weapon fire lights the hulls near it, beams and blasts have a soft glow, and panels cast a soft shadow. The Display section of Settings (D) shows what is drawing and lets you choose; where the graphics card can't be used, the game draws as before.

**Officers of your own, and voices for the aliens.** The `officers.toml` file in your config folder can now give an officer a new name, rank, background, interests, quirks and lines of their own. An optional second language model can speak for the characters alone, for richer Klingon, Romulan and other alien speech (Settings → Character voices on the main menu, V).

**Tougher fleets.** The enemy fleets in the preset battles are larger again, so the Dreadnought has a real fight: an AI captain flying her wins about two battles in three. Map labels are easier to read, ships in close formation share one label, and a faint nebula drifts behind the stars.

**Klingons that look Klingon.** The battle cruiser, frigate and dreadnought are redrawn on the classic plan: a command pod on a long boom, a slim engine hull, and thin wings swept back to long nacelles. The escort is now a bird-of-prey, with a wedge head, broad wings and a disruptor cannon at each wingtip. Zoomed out, every ship is drawn as one clean, smoothed silhouette instead of a tangle of outlines, and a ship's speed line starts at her bow so it no longer runs through her.

**Big battles run faster.** Enemy captains decide exactly as before, but working out how to dodge torpedoes now takes half the time, so a 60-ship battle runs about twice as fast.

**Small fixes.** Ship names near the edge of the map stay on screen, the target and contact lists no longer spill out of their panels, and the helm officer doesn't repeat the incoming-torpedo warning every few seconds.

## What's new in 1.1

**Weapons you can read at a glance.** A phaser bank glows as it charges, then its beam races to the target and stops where the blow really landed: on the shield if it held, on the hull if it got through. A full-power volley is heavier than a weak or point-defense shot. Klingon and Orion disruptors fly as real bolts. Torpedoes are drawn each nation's own way (a turning photon star, a harsh Klingon flare, a wobbling Romulan plasma ball) and stay easy to find at any zoom, and a round heading for you is ringed with its fuse radius, or marked at the edge of the map when it's off screen.

**Hits you can feel.** The struck shield arc lights up, a facing that gives way bursts into sparks, breached hulls vent, system hits flash, and a heavy blow on your own ship jolts the map (`hud jolt off` turns that off).

**A fuller soundscape**, all synthesised by the game, and only when sound is on: phaser charge and ray, the torpedo tube, an incoming warning, shield, collapse and hull hits, a three-whoop red alert, lock and console tones, hail whistles, distant fire heard muffled, and a low ship's hum that follows your warp and ducks under the big moments (`sound hum off`, or `sound hum 0-100`).

**Tougher enemies.** The Enterprise is a Dreadnought from the start, and enemy captains now dodge torpedoes, fire snap shots, flee blasts and fight in their nation's style (Klingons charge, Romulans feint, Orions raid), with fleets sized to match. The HUD no longer overlaps PAUSED and RED ALERT, and drawing is faster.

## Download and play

Pick the file for your computer below. You don't need Python or anything else installed.

| Computer | File | How to start it |
|---|---|---|
| Windows 10 or 11 | `Begin-windows.exe` | Double-click it. |
| Mac with Apple Silicon (M1 or later) | `Begin-mac-apple-silicon.zip` | Double-click the zip, drag `Begin.app` into Applications, then open it. |
| Mac with an Intel chip | `Begin-mac-intel.zip` | The same as above. |
| Linux (64-bit) | `Begin-linux-x86_64.tar.gz` | Extract it, then run `./begin`. |

Not sure which Mac you have? Apple menu > About This Mac: "Chip: Apple M…" means Apple Silicon, "Processor: Intel" means Intel.

### The first time you open it

These builds aren't signed with a paid certificate, so your computer will be cautious the first time.

**Windows** may show "Windows protected your PC". Click **More info**, then **Run anyway**.

**macOS** may say Begin "can't be opened" or "Apple could not verify" it. Click **Done**, open **System Settings > Privacy & Security**, scroll down to the message about Begin and click **Open Anyway**, then confirm. On older macOS you can instead right-click `Begin.app` and choose **Open**. You only need to do this once.

### Your settings

The game makes a `Begin config` folder beside itself, holding plain text files you can edit (the **Open config folder** button on the main menu takes you there). Keep that folder with the game if you move it. On a Mac, open the game from Applications (or any folder of yours) rather than straight from Downloads, so it can save settings.

The officers' talking-AI is optional; the game plays fully without it. See the README in the `Begin config` folder to set it up.
