"""Short-lived procedural effects driven by simulation events.

Effects live in world coordinates and real (wall-clock) seconds, so they
read the same at every time scale and keep animating while paused.

Weapons are coloured by the race that fired them (`colors` in
factions.toml) [E]: each race's beams have their own colour and style
(a steady beam or a string of bolts), and its torpedoes and their blasts
their own colour. A ship we can't identify fires in neutral white. A
torpedo set off by a phaser before it reached anything "fizzles": a small
grey flash with a few sparks of debris, nothing like the bright ring and
flash of one that went off where it was meant to.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from collections.abc import Callable

from ..content.schema import Faction
from ..sim.events import (DeflectorPulsed, Detonation, Event, HullHit, OrdnanceDestroyed, PhaserFired, ShieldHit,
                          ShipStatusChanged, SubsystemDamaged, TorpedoLaunched)
from . import theme
from .beams import Beam, Stop
from .blast import add_light
from .camera import Camera
from . import gfx

Body = tuple[float, float, float]     # where a ship is seen: x, y and her hull length, world units


@dataclass(frozen=True)
class Light:
    """Weapon light falling on whatever is near it this frame, in screen pixels: lights the hulls round it."""
    x: float
    y: float
    reach: float           # pixels: nothing beyond this is lit
    color: theme.Color
    k: float               # 0..1 at its centre


@dataclass
class Ring:
    x: float
    y: float
    radius: float
    color: theme.Color
    life: float = 0.9
    age: float = 0.0
    core: bool = True


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    color: theme.Color
    life: float
    age: float = 0.0


@dataclass
class Pop:
    """A round shot down: a small grey star of debris, the same size on screen at any zoom."""
    x: float
    y: float
    life: float = 0.7
    age: float = 0.0
    spin: float = 0.0


@dataclass
class Debris:
    """A piece of a ship that broke up: a short bright shard, tumbling and dimming as it drifts."""
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    length: float          # pixels
    color: theme.Color
    life: float
    age: float = 0.0


@dataclass
class Glow:
    """The soft light of a ship's reactor letting go, under the blast ring."""
    x: float
    y: float
    radius: float          # world units
    color: theme.Color
    life: float = 0.6
    age: float = 0.0


@dataclass
class Ripple:
    """A cloak engaging or failing: the space around the ship shivers in a wavering ring."""
    x: float
    y: float
    vanishing: bool
    life: float = 1.1
    age: float = 0.0
    phase: float = 0.0


@dataclass
class Streak:
    """A ship dropping out of warp [E]: a long streak of light that shrinks into her, and a flash where she arrives."""
    x0: float
    y0: float
    x1: float
    y1: float
    color: theme.Color
    life: float = 1.0
    age: float = 0.0


@dataclass
class Flash:
    """A point of light that is the same size on screen at any zoom: a torpedo leaving its tube, a system
    going up inside a hull."""
    x: float
    y: float
    radius: float          # pixels
    color: theme.Color
    life: float = 0.25
    age: float = 0.0
    delay: float = 0.0


@dataclass
class Vent:
    """Gas and fire venting from a breached hull: a soft puff drifting out from the wound, cooling as it spreads."""
    x: float
    y: float
    vx: float
    vy: float
    life: float
    age: float = 0.0
    delay: float = 0.0
    size: float = 3.0      # pixels at the start


@dataclass
class Effects:
    beams: list[Beam] = field(default_factory=list)
    rings: list[Ring] = field(default_factory=list)
    sparks: list[Spark] = field(default_factory=list)
    pops: list[Pop] = field(default_factory=list)
    debris: list[Debris] = field(default_factory=list)
    glows: list[Glow] = field(default_factory=list)
    embers: list[Spark] = field(default_factory=list)
    ripples: list[Ripple] = field(default_factory=list)
    streaks: list[Streak] = field(default_factory=list)
    flashes: list[Flash] = field(default_factory=list)
    vents: list[Vent] = field(default_factory=list)
    rng: random.Random = field(default_factory=lambda: random.Random(7))
    clock: float = 0.0
    landing: dict[tuple[int, int], float] = field(default_factory=dict)   # (shooter, ship hit) -> seconds until the shot lands

    def ingest(self, events: list[Event], player_side: int, visible: set[int], friendly: set[int],
               faction_of: Callable[[int | None], Faction | None] = lambda sid: None,
               body_of: Callable[[int | None], Body | None] = lambda sid: None) -> None:
        self.landing = {}
        # how each blow this batch landed: did it stop on the shield, or get through to the hull?
        got_through: dict[tuple[int, int], bool] = {}
        for ev in events:
            if isinstance(ev, ShieldHit) and ev.attacker is not None:
                key = (ev.attacker, ev.ship_id)
                got_through[key] = got_through.get(key, False) or ev.penetrated > 0.5 or ev.collapsed
            elif isinstance(ev, HullHit) and ev.attacker is not None and ev.amount > 0:
                got_through[(ev.attacker, ev.ship_id)] = True
        for ev in events:      # shots first: the blows they land are reported before the shot itself
            if isinstance(ev, PhaserFired) and ev.ship_id in visible:
                self._shot(ev, faction_of(ev.ship_id), body_of, got_through)
        for ev in events:
            if isinstance(ev, PhaserFired):
                continue
            elif isinstance(ev, Detonation) and ev.cause == "intercepted":
                # an armed round set off by a beam still blasts, but dully: a faint grey ring, no flash
                self.rings.append(Ring(ev.x, ev.y, ev.radius, theme.dim(FIZZLE, 0.6), life=0.5, core=False))
            elif isinstance(ev, Detonation):
                self._burst(ev, faction_of)
            elif isinstance(ev, DeflectorPulsed):
                a = math.radians(ev.facing)
                self.beams.append(Beam(ev.x, ev.y, ev.x + math.sin(a) * ev.range, ev.y + math.cos(a) * ev.range,
                                       ev.arc, theme.CREW, life=1.4, width=1.0, cone=(ev.facing, ev.arc, ev.range),
                                       style="sweep"))
            elif isinstance(ev, OrdnanceDestroyed):
                self._fizzle(ev.x, ev.y, 90.0)
            elif isinstance(ev, TorpedoLaunched) and ev.ship_id in visible:
                me = body_of(ev.ship_id)
                f = faction_of(ev.ship_id)
                if me is not None:          # the tube's flash: the round's own light as it leaves
                    col = f.torpedo_color if f is not None else theme.TORPEDO
                    self.flashes.append(Flash(me[0], me[1], 14.0, theme.mix(col, (255, 255, 255), 0.4), life=0.3))
            elif isinstance(ev, HullHit) and ev.ship_id in visible and ev.amount > 0:
                me = body_of(ev.ship_id)
                if me is not None:
                    self._vent(ev, me, body_of(ev.attacker))
            elif isinstance(ev, SubsystemDamaged) and ev.ship_id in visible and ev.damage > 0:
                me = body_of(ev.ship_id)
                if me is not None:
                    self._secondary(me, ev.destroyed)
            elif isinstance(ev, ShipStatusChanged) and ev.status == "destroyed":
                pass  # the breakup Detonation carries the visuals

    def _shot(self, ev: PhaserFired, f: Faction | None, body_of: Callable[[int | None], Body | None],
              got_through: dict[tuple[int, int], bool]) -> None:
        """A bank firing: its beam (or bolts), cut short on the shield or hull of whatever it hit."""
        col = f.phaser_color if f is not None else UNKNOWN_WEAPON
        me = body_of(ev.ship_id)
        stop: Stop | None = None
        for hit in ev.hits:
            them = body_of(hit)
            if them is not None:
                stop = Stop(them[0], them[1], them[2], on_shield=not got_through.get((ev.ship_id, hit), False))
                break
        beam = Beam(ev.origin[0], ev.origin[1], ev.end[0], ev.end[1], ev.spread, col,
                    width=1.5 if ev.defensive else 2.2, cone=(ev.facing, ev.spread, ev.range),
                    style=f.phaser_style if f is not None else "beam", power=getattr(ev, "power", 1.0),
                    defensive=ev.defensive, strip=(me[2] * 0.3) if me is not None else 0.0, stop=stop,
                    seed=self.rng.randrange(1 << 16))
        self.beams.append(beam)
        for hit in ev.hits:
            key = (ev.ship_id, hit)
            self.landing[key] = max(self.landing.get(key, 0.0), beam.arrives)

    def _burst(self, ev: Detonation, faction_of: Callable[[int | None], Faction | None]) -> None:
        """A warhead or a ship going off: flash, shockwave and sparks, all sized by what actually went off."""
        if ev.source in ("torpedo", "probe"):
            f = faction_of(ev.owner)
            col = theme.mix(f.torpedo_color if f is not None else UNKNOWN_WEAPON, (255, 255, 255), 0.25)
        else:
            col = theme.BLAST if ev.source != "ship" else (255, 230, 190)
        big = ev.source in ("ship", "destruct")      # a ship's flash is its own soft glow, not a hard disc
        heft = max(0.6, min(1.8, (max(ev.yield_, 1.0) / 15.0) ** 0.5))     # an MK8 is a bigger bang than an MK7
        self.rings.append(Ring(ev.x, ev.y, max(ev.radius, 150.0), col, life=1.1 if big else 0.8, core=not big))
        if big:
            self._breakup(ev.x, ev.y, max(ev.radius, 300.0))
        else:
            self.glows.append(Glow(ev.x, ev.y, max(ev.radius, 150.0) * 0.55 * heft, theme.mix(col, (255, 255, 255), 0.4),
                                   life=0.45))
            self.flashes.append(Flash(ev.x, ev.y, 10 + 10 * heft, (255, 250, 235), life=0.18))
        n = 26 if big else int(10 + 6 * heft)
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.3, 1.0) * max(ev.radius, 200.0) * 1.2
            self.sparks.append(Spark(ev.x, ev.y, math.sin(a) * sp, math.cos(a) * sp, col,
                                     self.rng.uniform(0.4, 1.2)))

    def _vent(self, ev: HullHit, me: Body, them: Body | None) -> None:
        """A breach: gas and fire vent from the side the blow came from, more the harder it hit."""
        x, y, length = me
        if them is not None:
            a = math.atan2(them[0] - x, them[1] - y)
        else:
            a = self.rng.uniform(0, math.tau)
        delay = self.landing.get((ev.attacker, ev.ship_id), 0.0) if ev.attacker is not None else 0.0
        wx, wy = x + math.sin(a) * length * 0.2, y + math.cos(a) * length * 0.2
        for _ in range(int(3 + min(7, ev.amount / 6))):
            b = a + self.rng.uniform(-0.6, 0.6)
            sp = length * self.rng.uniform(0.25, 0.7)
            self.vents.append(Vent(wx, wy, math.sin(b) * sp, math.cos(b) * sp, self.rng.uniform(0.9, 1.8),
                                   delay=delay + self.rng.uniform(0.0, 0.25), size=self.rng.uniform(2.0, 4.0)))

    def _secondary(self, me: Body, destroyed: bool) -> None:
        """A system hit inside her: a small blast somewhere on the hull, a moment after the blow."""
        x, y, length = me
        a = self.rng.uniform(0, math.tau)
        r = length * self.rng.uniform(0.05, 0.3)
        self.flashes.append(Flash(x + math.sin(a) * r, y + math.cos(a) * r, 16.0 if destroyed else 10.0,
                                  (255, 200, 120), life=0.4 if destroyed else 0.3, delay=self.rng.uniform(0.2, 0.45)))

    def _splash(self, b: Beam) -> None:
        """A beam landing: sparks thrown off the shield where it stopped, or off the hull it reached."""
        st = b.stop
        assert st is not None
        dx, dy = b.x0 - st.x, b.y0 - st.y
        d = math.hypot(dx, dy) or 1.0
        r = st.length * (0.62 if st.on_shield else 0.19)
        x, y = st.x + dx / d * r, st.y + dy / d * r
        out = math.atan2(dx, dy)
        col = theme.mix(b.color, (255, 255, 255), 0.5) if st.on_shield else (255, 214, 140)
        for _ in range(int(4 + 6 * min(1.0, b.weight))):
            a = out + self.rng.uniform(-1.2, 1.2)
            sp = st.length * self.rng.uniform(0.3, 1.0)
            self.sparks.append(Spark(x, y, math.sin(a) * sp, math.cos(a) * sp, col, self.rng.uniform(0.2, 0.5)))

    def _breakup(self, x: float, y: float, radius: float) -> None:
        """A ship coming apart: a flash, a ring of shards flung outward, and embers that linger."""
        self.glows.append(Glow(x, y, radius * 0.6, (255, 236, 200), life=0.7))
        hull = (205, 208, 218)
        for _ in range(self.rng.randint(9, 14)):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.25, 0.7) * radius
            self.debris.append(Debris(x, y, math.sin(a) * sp, math.cos(a) * sp, self.rng.uniform(0, math.tau),
                                      self.rng.uniform(-6, 6), self.rng.uniform(3, 8), hull, self.rng.uniform(2.2, 3.6)))
        for _ in range(18):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.05, 0.4) * radius
            self.embers.append(Spark(x + math.sin(a) * radius * 0.1, y + math.cos(a) * radius * 0.1,
                                     math.sin(a) * sp, math.cos(a) * sp, EMBER, self.rng.uniform(1.4, 3.0)))

    def warp_in(self, x0: float, y0: float, x1: float, y1: float, color: theme.Color) -> None:
        """A ship arriving from warp: the streak from (x0, y0), then a flash and a soft glow at (x1, y1)."""
        self.streaks.append(Streak(x0, y0, x1, y1, color))
        self.glows.append(Glow(x1, y1, 1400.0, theme.mix(color, (255, 255, 255), 0.5), life=0.9))

    def ripple(self, x: float, y: float, vanishing: bool) -> None:
        self.ripples.append(Ripple(x, y, vanishing, phase=self.rng.uniform(0, math.tau)))

    def smoulder(self, x: float, y: float, hull: float, dt: float, zoom: float) -> None:
        """A badly hurt ship sheds the odd spark: more of them the worse the damage."""
        rate = 1.0 + 7.0 * max(0.0, 0.5 - hull) / 0.5      # sparks per second
        if self.rng.random() >= rate * dt or len(self.sparks) > 400:
            return
        a = self.rng.uniform(0, math.tau)
        sp = self.rng.uniform(15.0, 45.0) / max(zoom, 1e-4)      # a few pixels a second at any zoom
        off = self.rng.uniform(2.0, 9.0) / max(zoom, 1e-4)
        self.sparks.append(Spark(x + math.sin(a) * off, y + math.cos(a) * off, math.sin(a) * sp, math.cos(a) * sp,
                                 self.rng.choice((EMBER, (255, 214, 140), (255, 240, 220))), self.rng.uniform(0.25, 0.6)))

    def _fizzle(self, x: float, y: float, radius: float) -> None:
        """A round shot down: a small dull flash and a puff of grey debris, no fireball."""
        self.rings.append(Ring(x, y, radius, FIZZLE, life=0.4, core=False))
        self.pops.append(Pop(x, y, spin=self.rng.uniform(0, math.pi / 4)))
        for _ in range(6):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(60.0, 220.0)
            self.sparks.append(Spark(x, y, math.sin(a) * sp, math.cos(a) * sp, FIZZLE, self.rng.uniform(0.3, 0.7)))

    def update(self, dt: float) -> None:
        self.clock += dt
        for b in self.beams:
            b.age += dt
            if b.landing() and b.stop is not None and not b.defensive:
                self._splash(b)
        for fl in self.flashes:
            if fl.delay > 0:
                fl.delay -= dt
            else:
                fl.age += dt
        self.flashes = [fl for fl in self.flashes if fl.age < fl.life]
        for v in self.vents:
            if v.delay > 0:
                v.delay -= dt
                continue
            v.age += dt
            v.x += v.vx * dt
            v.y += v.vy * dt
            drag = math.exp(-1.6 * dt)
            v.vx *= drag
            v.vy *= drag
        self.vents = [v for v in self.vents if v.age < v.life]
        for r in self.rings:
            r.age += dt
        for pp in self.pops:
            pp.age += dt
        self.pops = [pp for pp in self.pops if pp.age < pp.life]
        for s in self.sparks:
            s.age += dt
            if s.age < 0:          # waiting for the blow that throws it to land
                continue
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vx *= 0.96
            s.vy *= 0.96
        for d in self.debris:
            d.age += dt
            d.x += d.vx * dt
            d.y += d.vy * dt
            d.angle += d.spin * dt
        for g in self.glows:
            g.age += dt
        for rp in self.ripples:
            rp.age += dt
        for st in self.streaks:
            st.age += dt
        self.streaks = [st for st in self.streaks if st.age < st.life]
        self.ripples = [rp for rp in self.ripples if rp.age < rp.life]
        for e in self.embers:
            e.age += dt
            e.x += e.vx * dt
            e.y += e.vy * dt
            drag = math.exp(-1.2 * dt)
            e.vx *= drag
            e.vy *= drag
        self.debris = [d for d in self.debris if d.age < d.life]
        self.glows = [g for g in self.glows if g.age < g.life]
        self.embers = [e for e in self.embers if e.age < e.life]
        self.beams = [b for b in self.beams if b.age < b.life]
        self.rings = [r for r in self.rings if r.age < r.life]
        self.sparks = [s for s in self.sparks if s.age < s.life]

    def lights(self, cam: Camera) -> list[Light]:
        """The light of shots landing, banks firing, warheads and ships going up, and launches, right now."""
        out: list[Light] = []
        for b in self.beams:
            if b.style == "sweep":
                continue
            charge, arrive, tail, gone = b.timeline()
            if b.age < charge:
                continue
            p0, p1 = b.endpoints(cam)
            w = b.weight
            fade = 1.0 if b.age < tail else max(0.0, 1.0 - (b.age - tail) / max(gone - tail, 1e-6))
            col = theme.mix(b.color, (255, 255, 255), 0.3)
            out.append(Light(p0[0], p0[1], 40 + 30 * w, col, 0.45 * w * fade))          # the bank that fired
            if b.age >= arrive:
                out.append(Light(p1[0], p1[1], 60 + 50 * w, col, min(1.0, 0.9 * w) * fade))   # where it lands
        for r in self.rings:
            t = r.age / r.life
            out.append(Light(*cam.to_screen(r.x, r.y), 30 + r.radius * cam.zoom * 2.5, r.color, (1.0 - t) ** 2))
        for g in self.glows:
            t = g.age / g.life
            out.append(Light(*cam.to_screen(g.x, g.y), 20 + g.radius * cam.zoom * 3.0, g.color, 0.8 * (1.0 - t) ** 1.5))
        for fl in self.flashes:
            if fl.delay <= 0:
                out.append(Light(*cam.to_screen(fl.x, fl.y), fl.radius * 5.0, fl.color, 0.7 * (1.0 - fl.age / fl.life)))
        return [lt for lt in out if lt.k > 0.02]

    def draw(self, surf: pygame.Surface, cam: Camera, overlay: pygame.Surface,
             glow: pygame.Surface | None = None) -> None:
        """`glow` is a black layer the caller adds onto the map afterwards; without one, light goes on `surf`."""
        for g in self.glows:
            t = g.age / g.life
            sx, sy = cam.to_screen(g.x, g.y)
            rad = int(min(300.0, max(6.0, g.radius * cam.zoom * (0.7 + 0.5 * t))))
            light = gfx.Surface((rad * 2, rad * 2))
            fade = (1 - t) ** 2
            for step in range(GLOW_STEPS):   # nested discs, outermost first: a gaussian of light
                share = 1 - step / GLOW_STEPS
                k = fade * math.exp(-5.0 * share * share)
                gfx.draw.circle(light, tuple(min(255, int(c * k)) for c in g.color), (rad, rad), max(1, int(rad * share)))
            surf.blit(light, (int(sx) - rad, int(sy) - rad), special_flags=pygame.BLEND_RGB_ADD)
        for rp in self.ripples:
            t = rp.age / rp.life
            sx, sy = cam.to_screen(rp.x, rp.y)
            # vanishing: the ring closes in on the ship; appearing: it spreads out from her
            base = 14 + (34 * (1 - t) if rp.vanishing else 34 * t)
            for k in range(2):
                pts = []
                for j in range(40):
                    a = j / 40 * math.tau
                    wob = 1 + 0.08 * math.sin(a * 6 + rp.phase + rp.age * 9 + k) * (1 - t)
                    rr = (base + k * 6) * wob
                    pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
                alpha = int(120 * math.sin(math.pi * t) / (1 + k))
                if alpha > 3:
                    gfx.draw.lines(overlay, (*CLOAK, alpha), True, pts, 1)
        for st in self.streaks:
            self._streak(surf, cam, overlay, st)
        for shard in self.debris:
            t = shard.age / shard.life
            sx, sy = cam.to_screen(shard.x, shard.y)
            hx, hy = math.cos(shard.angle) * shard.length / 2, math.sin(shard.angle) * shard.length / 2
            hot = theme.mix((255, 220, 170), shard.color, min(1.0, t * 3))
            gfx.draw.line(surf, theme.mix(hot, theme.BG, t ** 1.3), (sx - hx, sy - hy), (sx + hx, sy + hy), 2 if t < 0.4 else 1)
        for e in self.embers:
            t = e.age / e.life
            sx, sy = cam.to_screen(e.x, e.y)
            col = theme.mix(theme.mix((255, 210, 120), EMBER, min(1.0, t * 2)), theme.BG, t ** 1.5)
            gfx.draw.circle(surf, col, (int(sx), int(sy)), 1)
        for v in self.vents:
            if v.delay > 0:
                continue
            t = v.age / v.life
            sx, sy = cam.to_screen(v.x, v.y)
            col = theme.mix((255, 190, 120), (150, 160, 175), min(1.0, t * 2.5))     # fire, cooling to grey gas
            gfx.draw.circle(overlay, (*col, int(110 * (1 - t) ** 1.5)), (int(sx), int(sy)), max(1, int(v.size * (1 + 2.5 * t))))
        if self.beams:
            if glow is None:
                glow = gfx.Surface(surf.get_size())
                glow.fill((0, 0, 0))
                for b in self.beams:
                    b.draw(surf, glow, cam, self.clock)
                surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            else:
                for b in self.beams:
                    b.draw(surf, glow, cam, self.clock)
        for fl in self.flashes:
            if fl.delay > 0:
                continue
            t = fl.age / fl.life
            sx, sy = cam.to_screen(fl.x, fl.y)
            add_light(surf, sx, sy, fl.radius * (0.6 + 0.6 * t), fl.color, (1 - t) ** 1.5)
        for r in self.rings:
            t = r.age / r.life
            sx, sy = cam.to_screen(r.x, r.y)
            rad = max(3, int(r.radius * cam.zoom * (0.35 + 0.65 * math.sqrt(t))))
            col = theme.mix(r.color, theme.BG, t)
            gfx.draw.circle(surf, col, (int(sx), int(sy)), rad, max(1, int(3 * (1 - t))))
            if r.core and t < 0.35:          # the fireball: a soft white-hot light, not a hard disc
                u = t / 0.35
                add_light(surf, sx, sy, max(4.0, rad * 0.8 * (1 - 0.5 * u)), theme.mix((255, 255, 240), r.color, u),
                          (1 - u) ** 1.2)
        for pp in self.pops:
            t = pp.age / pp.life
            sx, sy = cam.to_screen(pp.x, pp.y)
            col = theme.mix(FIZZLE, theme.BG, t)
            r0, r1 = 3 + 4 * t, 7 + 5 * t
            for k in range(4):
                a = pp.spin + k * math.pi / 2
                gfx.draw.line(surf, col, (sx + math.cos(a) * r0, sy + math.sin(a) * r0),
                                 (sx + math.cos(a) * r1, sy + math.sin(a) * r1), 2)
        for s in self.sparks:
            if s.age < 0:
                continue
            t = s.age / s.life
            sx, sy = cam.to_screen(s.x, s.y)
            gfx.draw.circle(surf, theme.mix(s.color, theme.BG, t), (int(sx), int(sy)), 1 if t > 0.5 else 2)


    @staticmethod
    def _streak(surf: pygame.Surface, cam: Camera, overlay: pygame.Surface, st: Streak) -> None:
        t = st.age / st.life
        p1 = cam.to_screen(st.x1, st.y1)
        p0 = cam.to_screen(st.x0, st.y0)
        # the tail races in to the ship over the first part of the effect; the flash fades after
        k = 1.0 - (1.0 - min(1.0, t / STREAK_IN)) ** 3
        tail = (p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k)
        fade = 1.0 if t < STREAK_IN else max(0.0, 1.0 - (t - STREAK_IN) / (1.0 - STREAK_IN))
        if math.hypot(p1[0] - tail[0], p1[1] - tail[1]) > 2:
            for w, a in STREAK_GLOW:
                gfx.draw.line(overlay, (*st.color, int(a * fade)), tail, p1, w)
            gfx.draw.line(surf, theme.mix(st.color, (255, 255, 255), 0.7), tail, p1, 2)
        flash = max(0.0, 1.0 - abs(t - STREAK_IN) / 0.25)
        if flash > 0:
            gfx.draw.circle(overlay, (255, 255, 255, int(200 * flash)), (int(p1[0]), int(p1[1])), int(4 + 12 * flash))
            gfx.draw.circle(overlay, (*st.color, int(90 * flash)), (int(p1[0]), int(p1[1])), int(10 + 30 * flash), 2)


UNKNOWN_WEAPON = (215, 215, 215)   # a ship we can't identify
FIZZLE = (150, 150, 150)           # a round shot down before it could go off properly
EMBER = (255, 132, 60)
CLOAK = (170, 225, 215)            # the shimmer of a cloak engaging or dropping
GLOW_STEPS = 28             # burning fragments of a ship
STREAK_GLOW = ((15, 40), (7, 90))   # the halo round a warp streak
STREAK_IN = 0.45                    # share of the warp-in spent on the streak shrinking into the ship   # (pixels wide, alpha at full strength): the halo around a beam


__all__ = ["FIZZLE", "UNKNOWN_WEAPON", "Beam", "Effects", "Flash", "Streak", "Vent"]
