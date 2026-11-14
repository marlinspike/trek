---
title: Split fire: two ships at once
category: Weapons
order: 5
aliases: split, divide, unsplit, engage, split fire, divided fire, divide fire, two targets, both ships, rest on
summary: Some tubes or banks on one ship and the rest on another, by number or by the tactical officer's judgement.
see: lock, torpedoes, phasers, crew
---
When two enemies are on you at once, you don't have to leave one of them free to shoot. Split your fire: some tubes on one ship and the rest on the other, phasers on whichever ship they bear on, or let your tactical officer divide them and keep them divided as the ships move.

## Saying how to split

```console
split tubes 1-4 on talon, rest on wraith
split tubes 1 2 on talon, rest on wraith, phasers on talon
split banks 1-3 on talon, rest on wraith
split tubes 1-4 on talon, 5-8 on wraith now
split off
```

- Name the tubes or banks by number (`1 2`, `1-4`, `one through four`), then the ship. `rest` (or `the rest`) gives that ship every mount you haven't named yet.
- Numbers with no weapon named are tubes, and so is `rest` after them: `split 1 2 on talon, rest on wraith` divides only the tubes.
- `now` fires each group at its own ship straight away. Without it, the tubes and banks are locked and wait for your fire order.
- `split off` puts every weapon back on your target.

Your officer reads the division back ("Splitting fire. Tubes 1-4 on the Talon, 5-8 on the Wraith; phasers on the Talon."). A tube the ship doesn't have, or one you named twice, is refused before anything changes.

## Letting your officer divide them

```console
split talon wraith
split torpedoes talon wraith
divide the torpedoes between them
```

Name only the ships, and the tactical officer chooses. Name one weapon too (`split torpedoes ...`) and only that weapon is divided. "Them" means your target and the nearest other enemy. The officer weighs the same things every time:

- **Who comes first:** a ship already crippled (a third of her hull gone or worse) so she is finished off, otherwise the nearer.
- **Both in reach of everything:** the banks go to the ship each one bears on, and the tubes are divided between them. A ship half again as heavy as the other gets three quarters of the tubes; otherwise they are shared equally.
- **One in phaser range, the other only in torpedo range:** phasers on the near one, every tube on the far one.
- **Only one in reach:** everything on her, until the other comes in.

A tube or bank is given to the ship its arc covers; the rest make up the numbers.

## Engage both

```console
engage talon and wraith
worf, engage the talon and the wraith
engage off
```

`engage` with two ships is a standing order. The tactical officer divides the fire as above and keeps re-dividing it as the ships move (waiting a moment so the weapons don't flick back and forth), fires phasers at each ship as they bear, and sends a full salvo at each ship inside the torpedo window. The helm stays with you or the helm officer. When one ship is destroyed or escapes, her tubes and banks swing to your target; the order ends when neither is left. `engage` with one ship targets her, closes in and opens fire, as before.

## In plain words

No language model is needed for these:

- "torpedoes 1 through 4 on the Talon and the rest on the Wraith"
- "target tubes 1, 2 on the Talon, the rest on the Wraith"
- "phasers on the Talon and torpedoes on the Wraith"
- "fight both the Talon and the Wraith", "take on the Talon and the Wraith"
- "Worf, engage the Talon and the Wraith"

With a model on, looser words work too ("half the torpedoes on each of them").

## Firing a split

Once the weapons are divided, **F** and **T** (and `fire phasers`, `fire torpedoes` with no ship named) send each bank and tube at the ship it is locked on. Assisted fire does the same: each group fires at its own ship when it has a good shot. Clicking a ship or pressing **Tab** puts everything back on that one ship.

## Seeing it

While the fire is split, each cell in the Weapons panel carries a small letter for its ship, and the panel's title keys the letters ("H Hydra  W Wraith"); in a tab, the key sits under the buttons. The letter is amber for your target and lavender for the other ship. A cell's green edge means it bears on its own ship. On the map the other ship wears small, still lavender brackets, quieter than your target's.

## When your officers suggest it

With two enemies in reach and every weapon on one of them, the tactical officer may propose dividing the fire ("The Talon and the Wraith are both in reach, Captain. Divide our fire between them?"); Y runs `engage`. Turning it down quiets that suggestion for a while, whichever pair of ships it named. In counsel (**O**), Worf's plan may lead with "Divide our fire" when two ships are in reach.
