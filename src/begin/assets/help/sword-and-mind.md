---
title: The sword and the mind
category: Captain's manual
order: 7
aliases: strategy, tactics guide, how to win, winning, playbook, playbooks, doctrine, principles
summary: How to win: the principles that decide every fight, a playbook for each enemy, and the many ways a battle can be won.
see: tactics, hidden-depths, the-powers, coach
---
Every battle is decided by a handful of things: who chooses the range, which shields take the hits, whether fire lands together or piecemeal, and who knows more about the other. Get those right and the dice matter far less.

## The principles

### Choose the range

The side that chooses the range usually wins. Look at your weapons and at hers, then decide where you want to fight:

- **Torpedo-heavy ships** want to stand off inside their torpedo envelope and outside her phasers.
- **Phaser-heavy ships** want to close fast and stay close, where every hit is strongest.

Use `pursue <ship> warp <w>` to hold a chase and `elude <ship>` to keep away. The [[coach]] tells you which side of each envelope you are on. Remember that her motion moves the envelope: a ship charging at you shrinks your minimum range, and a ship running away stretches it.

### Fight with your shields

You have six shields, and she can hit only the one that faces her. When the forward shield weakens, turn so a fresh one takes the next volley. Then work her shields the same way:

- Keep hitting the face she shows you until it collapses.
- If she turns, go after the new face.
- `reinforce` the shield you will keep toward her.
- When power is tight, lower the shields facing away from every enemy, so the ones that matter hold.

### Mass your fire

Shields absorb a volley and then recharge. Fire that arrives a little at a time is soaked up. Fire that arrives all at once breaks through:

- Fire the whole salvo, not a tube at a time.
- Let banks charge, then fire them together.
- Tell your allies to attack the same ship (`tell 1 attack gorkon`).

Against the Borg this matters doubly, because every hit teaches them. Potshots teach them for free.

### Strip, then strike

A ship with no weapons can't hurt you, and a ship with no engines can't run. Once a shield is down, aim through it at what matters most right now:

| Aim at | When |
|---|---|
| **weapons** | she outguns you |
| **engines** | she is about to run |
| **shields** | you want a permanent hole, one her crew can't simply recharge |
| **life support** | you mean to take her |

A system knocked out by aimed fire stays out three times longer than one knocked out by a lucky hit.

### Spend power on purpose

Warp, shields, cloak and weapons all draw on one budget. Racing in at top warp leaves less for your shields when you arrive. Fight at the speed you need, keep the drives below their limit, and remember that a burned-out drive is gone for the rest of the battle, and for the rest of a tour until a starbase rebuilds it.

### Know before you commit

A scan tells you her shields, her damaged systems, her crew, and how many banks are charged and tubes loaded. A ship that has just emptied her tubes is a ship you can close on. Scans go stale, but your own hits keep you current: the log reports what each volley took off her shield. Use data probes to see past your own sensors.

### Use your bridge

You can't watch everything, and you don't have to:

- Hand the helm to Spock while you fight the guns.
- Hand Seven a job: disable their shields, take out her torpedoes, find that cloaked ship.
- When the battle is too big, give an officer the conn and step in only where it matters.

Your orders always come first. See [[your-crew|Your crew]].

### Know when to stop

Not every fight should be fought to the end. A beaten crew can be talked into surrender, and a Klingon into withdrawing with honour. A ship that gets 60,000 units clear of every enemy for ten cycles escapes, and on a tour an escaped ship is a ship you still have. See [[hailing]].

## The playbooks

### Against Klingons

They will come to you. Most Klingon captains charge: a run to point-blank range, a massive volley, a break to recharge, and then they come again.

- Meet the charge with a full torpedo salvo fired early, while they are still beyond your minimum range.
- Turn a fresh shield into the alpha strike.
- Punish the break with phasers as they turn away and show you a new shield.
- Their point defense is trigger-happy, so **bait** it: one torpedo first, the salvo a cycle later.
- Watching their friends die makes them angry, not afraid. Expect the survivors to come for you.
- Don't demand a surrender. Offer a way to **withdraw** with honour.
- Keep your distance from a beaten Klingon, who may ram or blow up the ship.

### Against Romulans

They decide when you see them.

- **Make the plasma fly far.** Plasma homes in but fades as it travels, so open the range and keep it open. Every unit it flies is damage it loses.
- **Don't chase blindly.** The feint is a turn and a run, often under cloak, that ends with a full spread at the ship that followed. Pursue at an angle, keep a fresh shield toward where she will turn, and keep your tubes loaded for the moment she shows.
- **When she vanishes:** your science officer gives the last fix and heading. Say `hunt <ship>`, or burst a tachyon detector a little ahead of where she was going. At close range, turn your bow toward her and use the deflector pulse.
- **When she is hurt:** a damaged warp drive vents plasma at warp, cloak or no cloak. `sweep` finds the trail and a plasma-seeker follows it. See [[cloak]].
- Their point defense is disciplined, so it won't take the bait. Use Seven's ring salvo instead ([[disable]]).

### Against Orions

They are fast, brittle and not here to die.

- They raid: in, one volley, and out. Don't race after them and burn your drives. Hold a central position and let them come.
- Against fast ships, use the fastest torpedo you have, a wider proximity and a fan.
- **Aim at the engines** of a runner and the chase is over.
- They frighten easily. Once a few of them are battered, **hail** the rest: a surrender demand with fair terms often ends the fight without another shot.
- Their point defense is the most trigger-happy of all.

### Against the Borg

Learn first, then strike hard. See [[borg|Fighting the Borg]] for the whole method. In short:

1. Keep the range open while Seven surveys the ship (`duty harmonics`).
2. Tune your shields before the drones come (`tune shields`).
3. Hold your fire until you can mass it, and `remodulate` when they adapt.
4. When Seven finds the vinculum relay, destroy it (`target cube relay`), or send Worf across to do it ([[away-team]]).
5. While she sleeps, hit her warp core and stand well clear, or board her and plant charges.

### Against bases and outposts

A base can't move, so it can't dodge.

- Use the heaviest warhead and the slow, hard-hitting probes.
- Fight from outside its phaser reach: a Klingon outpost carries eight banks.
- Strip its screen of escorts first, so it can't be relieved.

### Leading a squadron

Allies follow standing orders until you change them:

- `tell <ally> attack <ship>` concentrates fire.
- `escort` and `defend` keep a guard on a damaged ship, or on you.
- `run` and `withdraw` save a ship before she is lost.
- Group allies (`tell excalibur join 1`) and order the group by its number.
- A crippled ally can be towed to a starbase with `tow`. Docked, she can't be hit and repairs twice as fast.

See [[tell]].

## More than one way to win

The best battles are often won in ways the enemy didn't expect:

- **Take her instead of destroying her.** Open a hole in her shields, aim at her life support, then board her (`capture <ship>`). On a tour she joins your squadron for good.
- **Talk her out of the fight.** A shaken captain will often yield. A frightened Orion pack may simply leave. Offering their own prisoners back makes a captain far readier to withdraw.
- **Bluff, carefully.** A claim of strength works only if her scans of you don't give you away.
- **Taunt to draw her in.** An enraged captain closes on you, which is exactly what a phaser-heavy ship wants.
- **Change ships.** If the Enterprise is crippled but the fight isn't over, `beam` to an ally within 3,000 units and fight on from there.
- **Use the starbase.** In a defense with waves, dock damaged ships between waves. A docked ship can't be hit.
- **Hold her still.** A tractor beam pins a ship for your torpedoes and your boarders.
- **Write the battle plan before the battle.** A named order runs a whole manoeuvre with one word, and `record` saves a move that worked.

For the moves that aren't written on any button, read [[hidden-depths|Hidden depths]].
