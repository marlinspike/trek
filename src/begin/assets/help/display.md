---
title: Display and sharpness
category: Game
order: 7
aliases: display, graphics, renderer, gpu, opengl, retina, 4k, sharp, blurry, glow, bloom, vignette, lighting, shadows, software rendering
summary: How the game is drawn: sharp on Retina and 4K screens through the graphics card, with weapon light that falls on nearby hulls and a soft glow round it.
see: weapon-colors, sound
---
Open **Settings** from the main menu and choose **Display** (or press **D** on the main menu) to see how the game is being drawn and to change it.

**Renderer** has three choices:

- **Automatic** (the default) uses the graphics card when it can. On a high-density screen, such as a Mac's Retina display, a 4K monitor or Windows set to 150% or 200%, the game is then drawn at the screen's real pixel density, so text, hulls and beams are crisp rather than stretched. If OpenGL 3.3 isn't available, or OpenGL would be drawn on the processor (as in a virtual machine), it uses pygame's own drawing instead.
- **Graphics card** always uses OpenGL, even where that is slow.
- **Software** is pygame's own drawing at one pixel per point, as the game always drew. It works everywhere and is softer on high-density screens.

A window can't change renderer while it is open, so after you pick a different one the page offers **Restart now**. Or the change simply applies the next time you start the game.

**Light and glow** makes weapon fire feel physical. A phaser hit, a launch or a torpedo blast briefly lights the hulls next to it in its own colour, and panels and cards cast a soft shadow so they sit above the map. With the graphics card drawing, phaser beams, disruptor bolts and blasts also get a soft halo, and the very edge of the map is slightly darker, like a viewscreen. Text is never touched. It takes effect at once; turn it off for the flattest, quickest picture.

The **Now** box says what is drawing at the moment: the graphics card and the screen's density, or software drawing and why the graphics card isn't being used.

The choices are saved as `renderer` and `bloom` in `settings.json` in your config folder. `begin --renderer software` (or `gpu`, or `auto`) overrides them for one run.
