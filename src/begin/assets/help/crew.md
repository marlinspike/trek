---
title: Bridge officers
category: Crew
order: 0
aliases: crew, bridge, officers, delegate, dg, assume, takeback, station, stations, spock, worf, scotty, scott, seven, seven of nine, chatter
summary: Hand a station to its officer, take it back, and hear what your crew thinks.
see: talking, llm, controls
---
Four officers stand by on your bridge. Each one can run a **station** for you, so you can concentrate on the decisions that matter.

| Station | Officer | Runs |
|---|---|---|
| Helm | Commander Spock | course and speed: closing, opening the range, weaving |
| Tactical | Lieutenant Worf | targets, phasers, torpedoes, probes, point defense |
| Engineering | Lieutenant Commander Scott | shields, reinforcing, repair priorities, cloak |
| Science | Seven of Nine | scanning the target and every other contact |

```console
delegate tactical
delegate helm science
delegate all
assume helm
assume all
crew
```

- `delegate <station>` hands a station to its officer. `assume <station>` takes it back. `all` covers every station.
- The **Bridge crew** panel shows who runs each station. Click **Captain** / **Officer** to switch, or click an officer's name to speak to them.
- `crew` lists your officers, who is running what, and how each of them feels about you.

## You stay in command

- Anything you order yourself overrides the officer for a few seconds, then they carry on from where you left them.
- Officers never pick a target when you have chosen one. They only choose when you have none.
- Officers never retreat, surrender, self-destruct, beam across or give orders to allies. Those decisions are yours.
- If you beam to another ship, your officers come with you. Their stations go back to you until you hand them over again.

Each officer has a personality. Worf is aggressive and closes for the kill; Spock holds a careful range; Scott spends repair effort where it matters most; Seven scans everything, efficiently.

## Chatter

Your officers comment on the battle: Worf when torpedoes go out, Scott when the hull or the engines are in trouble, Seven when new contacts appear. `crew chatter off` quiets them, and `crew chatter on` brings them back.

To ask them questions or give them orders in plain words, see [[talking|Talking to your officers]].
