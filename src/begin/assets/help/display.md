---
title: Display and sharpness
category: Game
order: 7
aliases: display, interface size, ui scale, text size, bigger text, small text, zoom, big monitor, graphics, renderer, gpu, opengl, retina, 4k, sharp, blurry, glow, bloom, vignette, lighting, shadows, software rendering
summary: How the game is drawn: sharp on Retina and 4K screens through the graphics card, with weapon light that falls on nearby hulls and a soft glow round it.
see: weapon-colors, sound
---
Open **Settings** from the main menu and choose **Display** (or press **D** on the main menu) to see how the game is being drawn and to change it.

**Renderer** has three choices:

- **Automatic** (the default) uses the graphics card when it can. On a high-density screen, such as a Mac's Retina display, a 4K monitor or Windows set to 150% or 200%, the game is then drawn at the screen's real pixel density, so text, hulls and beams are crisp rather than stretched. If OpenGL 3.3 isn't available, or OpenGL would be drawn on the processor (as in a virtual machine), it uses pygame's own drawing instead.
- **Graphics card** always uses OpenGL, even where that is slow.
- **Software** is pygame's own drawing at one pixel per point, as the game always drew. It works everywhere and is softer on high-density screens.

A window can't change renderer while it is open, so after you pick a different one the page offers **Restart now**. Or the change simply applies the next time you start the game.

**Interface size** makes the whole screen larger: text, panels, buttons and the map's labels together. On **Auto** (the default) it follows the window. Up to 1,000 points tall nothing changes, since every screen is designed for that. Past it, the interface grows, so a window filling a 27-inch 2560x1440 monitor reads like a 1900x1070 one (135%), up to 150% at most. A Retina Mac or a Windows display already set to 150% or more is sized by the system, so Auto leaves it alone. Pick **100%**, **115%**, **130%** or **150%** to fix the size yourself. It takes effect at once. With the graphics card drawing, the larger interface is drawn at the screen's real pixels, so text stays sharp. Software drawing scales the finished picture up, which is a little softer.

**Light and glow** makes weapon fire feel physical. A phaser hit, a launch or a torpedo blast briefly lights the hulls next to it in its own colour, and panels and cards cast a soft shadow so they sit above the map. With the graphics card drawing, phaser beams, disruptor bolts and blasts also get a soft halo, and the very edge of the map is slightly darker, like a viewscreen. Text is never touched. It takes effect at once; turn it off for the flattest, quickest picture.

The **Now** box says what is drawing at the moment: the graphics card and the screen's density, or software drawing and why the graphics card isn't being used, and the interface size when it isn't 100%.

The choices are saved as `renderer`, `ui_scale` (0 for Auto) and `bloom` in `settings.json` in your config folder. `begin --renderer software` (or `gpu`, or `auto`) overrides them for one run.
