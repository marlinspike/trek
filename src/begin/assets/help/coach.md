---
title: Coach
category: Coach
order: 0
aliases: coach, advise, advice, hint, hints, what now, what should i do
summary: Reads the battle you are in and suggests what to do next, with the command for each step.
see: weapons-guide, tactics, torpedoes, shields
---
The coach looks at the same information your sensors give you: your target's range, course and speed, your weapons and what they are loaded with, incoming fire, your shields, heat and power. It never peeks at anything your side could not know. Advice is listed most urgent first, and this page refreshes while it is open, so you can leave it up and watch the advice change as the fight moves.

Click a **›** line to put that command in the console. Nothing is sent until you press Enter.

{{coach}}

## Your weapons

{{my_weapons}}

## How the coach thinks

- **Incoming fire comes first.** A torpedo or probe heading your way is the most urgent thing on the board, so point defense and shield facing are checked before anything else.
- **Every weapon has an envelope.** A torpedo is only useful between its *arming* range and its *maximum* range against the target's current motion, and both change as the target turns. The coach tells you whether your target is inside it, and how far to close or open the range.
- **The right warhead for the job.** Fast torpedoes suit fast or manoeuvring targets. Heavy warheads suit slow ships and bases. Shield-bore warheads ignore part of the shield, and plasma fades the further it travels. See [[weapons-guide]].
- **Proximity is a trade.** A wide proximity setting is more likely to explode near the target but does less damage. Tight settings hit hard but need good aim. Against a ship that is turning, open the proximity up.
- **Heat and power.** Running hot at high warp, or with too little power left for shields, gets flagged with the warp that fixes it.

Type `coach` in the console at any time to open this page.
