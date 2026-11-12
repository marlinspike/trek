---
title: Display and sharpness
category: Game
order: 7
aliases: display, graphics, renderer, gpu, opengl, retina, 4k, sharp, blurry, glow, bloom, vignette, software rendering
summary: How the game is drawn: sharp on Retina and 4K screens through the graphics card, with a soft glow round weapon light.
see: weapon-colors, sound
---
Open **Display** from the main menu (or press **D** there) to see how the game is being drawn and to change it.

**Renderer** has three choices:

- **Automatic** (the default) uses the graphics card when it can. On a high-density screen, such as a Mac's Retina display, a 4K monitor or Windows set to 150% or 200%, the game is then drawn at the screen's real pixel density, so text, hulls and beams are crisp rather than stretched. If OpenGL 3.3 isn't available, or OpenGL would be drawn on the processor (as in a virtual machine), it uses pygame's own drawing instead.
- **Graphics card** always uses OpenGL, even where that is slow.
- **Software** is pygame's own drawing at one pixel per point, as the game always drew. It works everywhere and is softer on high-density screens.

A window can't change renderer while it is open, so after you pick a different one the page offers **Restart now**. Or the change simply applies the next time you start the game.

**Weapon glow** adds a soft halo round phaser beams, disruptor bolts and blasts, and makes the very edge of the map slightly darker, like a viewscreen. Text and panels are never touched. It takes effect at once, and only shows when the graphics card is drawing.

The **Now** box says what is drawing at the moment: the graphics card and the screen's density, or software drawing and why the graphics card isn't being used.

The choices are saved as `renderer` and `bloom` in `settings.json` in your config folder. `begin --renderer software` (or `gpu`, or `auto`) overrides them for one run.
