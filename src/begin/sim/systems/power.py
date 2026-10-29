"""Power, life support, shield upkeep, drive heat and weapon charging [R §3–§5].

Begin settles energy once per cycle; we run the same budget continuously:
every per-cycle rate is applied per tick × dt and the batteries buffer the
difference. Drain order follows Begin: life support, shields, cloak,
tractor, then weapon charging (phasers, then torpedo tubes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..events import Message, Tone
from ..ship import LoadedTorpedo, Ship, ShipStatus

if TYPE_CHECKING:
    from ..world import World


def warp_budget(ship: Ship) -> float:
    """WARP POWER [R]: Σ drive health × warp_power (also the destruct-yield basis)."""
    return sum(d.health * ship.cls.warp_power for d in ship.drives)


def max_attainable_warp(ship: Ship, budget: float) -> float:
    cls = ship.cls
    if cls.max_warp <= 0.0:
        return 0.0
    fallback = 1.0 if (ship.impulse is not None and not ship.impulse.destroyed) else 0.0
    if budget <= 0.0 or cls.warp_power_use <= 0.0:
        return fallback
    w = min(cls.max_warp, budget / cls.warp_power_use)
    return fallback if w <= 1.0 else w


def update_power(world: World, ship: Ship, dt: float) -> None:
    rules = world.rules
    cls = ship.cls
    rep = ship.power

    budget = warp_budget(ship)
    maxw = max_attainable_warp(ship, budget)
    ship.max_attainable_warp = maxw
    desired = min(ship.desired_warp, maxw)
    warp_cost = desired * cls.warp_power_use if desired > 1.0 else 0.0
    warp_ratio = desired / maxw if (desired > 1.0 and maxw > 0.0) else 0.0
    _drive_heat(world, ship, warp_ratio, dt)

    spill = rules.warp_spill * max(0.0, budget - warp_cost)
    reactor = sum(r.health * cls.reactor_output for r in ship.reactors)
    generation = reactor + spill
    stored = ship.battery_charge()
    pool = generation * dt + stored

    rep.warp_budget = budget
    rep.warp_used = warp_cost
    rep.reactor = reactor
    rep.generation = generation

    # life support: design crew / 10 per cycle; three cycles of failure kill the crew
    life = 0.0
    docked = ship.docked_to is not None
    if ship.crew > 0 and not docked:
        need = cls.crew / 10.0 * dt
        if pool >= need:
            pool -= need
            life = need
            ship.life_failure_time = 0.0
            rep.life_failing = False
        else:
            pool = 0.0
            ship.life_failure_time += dt
            if not rep.life_failing:
                world.emit(Message(world.tick, f"{ship.name}: life support is failing!", Tone.ALERT,
                                   ship_id=ship.id, visible_to=frozenset({ship.side})))
            rep.life_failing = True
            if ship.life_failure_time >= rules.life_support_failure_cycles:
                world.lose_all_hands(ship, "life support failure")
    rep.life_support = life / dt

    # shields: if all raised shields can't be paid, none are up this tick [R]
    cost = 0.0
    for sh in ship.shields:
        if sh.up and not sh.destroyed:
            cost += cls.shield_energy * (rules.shield_reinforce_cost if sh.reinforced else 1.0)
    cost *= dt
    paid = pool >= cost
    if paid:
        pool -= cost
    else:
        pool = 0.0
    if rep.shields_starved != (not paid) and not paid and cost > 0:
        world.emit(Message(world.tick, f"{ship.name}: insufficient power for shields!", Tone.ALERT,
                           ship_id=ship.id, visible_to=frozenset({ship.side})))
    rep.shields_starved = not paid
    rep.shields = (cost if paid else 0.0) / dt
    for sh in ship.shields:
        if sh.destroyed:
            sh.effective = 0.0
            continue
        ceiling = sh.ceiling
        if sh.up and sh.strength < ceiling:
            gain = max(sh.strength / 100.0 * cls.shield_recharge, rules.shield_regen_min) * dt
            sh.strength = min(ceiling, sh.strength + gain)
        sh.strength = min(sh.strength, ceiling)
        sh.effective = sh.strength if (paid and sh.up) else 0.0
        if sh.flash > 0:
            sh.flash = max(0.0, sh.flash - dt)

    # cloak upkeep
    rep.cloak = 0.0
    if ship.cloaked:
        c = cls.cloak_energy * dt
        if pool >= c and ship.cloak is not None and not ship.cloak.destroyed:
            pool -= c
            rep.cloak = cls.cloak_energy
        else:
            ship.cloaked = False
            world.emit(Message(world.tick, f"{ship.name}: cloak failed — insufficient power.", Tone.CAUTION,
                               ship_id=ship.id, visible_to=frozenset({ship.side})))

    # tractor upkeep
    rep.tractor = 0.0
    if ship.tractor_target is not None:
        c = cls.tractor_energy * dt
        if pool >= c:
            pool -= c
            rep.tractor = cls.tractor_energy
        else:
            ship.tractor_target = None
            world.emit(Message(world.tick, f"{ship.name}: tractor beam released — insufficient power.",
                               Tone.CAUTION, ship_id=ship.id, visible_to=frozenset({ship.side})))

    # weapon charging
    spent = 0.0
    if ship.status == ShipStatus.ACTIVE and ship.crew > 0:
        pool, spent = _charge_weapons(world, ship, pool, dt)
    rep.weapons = spent / dt

    # leftover refills online batteries; any excess is lost [R]
    cap = cls.battery_capacity
    for b in ship.batteries:
        if not b.online:
            b.charge = 0.0
            continue
        fill = min(cap, max(0.0, pool))
        b.charge = fill
        pool -= fill
    rep.stored = ship.battery_charge()
    rep.capacity = ship.battery_capacity()


def _drive_heat(world: World, ship: Ship, warp_ratio: float, dt: float) -> None:
    rules = world.rules
    eff = ship.cls.warp_efficiency
    for d in ship.drives:
        before = d.temp
        if d.destroyed:
            d.temp = max(0.0, d.temp - eff * rules.temp_rate * dt)
        else:
            d.temp = max(rules.temp_floor, d.temp + (warp_ratio - d.health * eff) * rules.temp_rate * dt)
            if d.temp > rules.temp_limit:
                world.destroy_subsystem(ship, d, "overheated")
        d.temp_rate = (d.temp - before) / dt


def _charge_weapons(world: World, ship: Ship, pool: float, dt: float) -> tuple[float, float]:
    cls = ship.cls
    rules = world.rules
    spent = 0.0
    # phasers: banks_charge / banks_rate per cycle while intact and enabled [R]
    if ship.banks:
        per_cycle = cls.banks_charge / cls.banks_rate + 0.001
        for b in ship.banks:
            if not b.intact or not b.enabled or b.charge >= cls.banks_charge:
                continue
            step = min(per_cycle * dt, cls.banks_charge - b.charge, max(0.0, pool))
            if step <= 0:
                continue
            b.charge += step
            if cls.banks_charge - b.charge < 1e-6:
                b.charge = cls.banks_charge
            pool -= step
            spent += step

    # torpedo tubes: charge over the ordnance's charge time, then load [R].
    # [E] A tube claims its torpedo when it starts charging, so the last few in the magazine go to
    # tubes that can finish instead of being spread over every empty tube.
    charging = sorted((t for t in ship.tubes if t.loaded is None and t.charge > 0.0), key=lambda t: -t.charge)
    for t in charging[max(0, ship.torps_remaining):]:
        t.charge = 0.0  # no torpedo left for this tube: stand it down rather than leave it part-charged
    free = ship.torps_remaining - min(len(charging), max(0, ship.torps_remaining))
    if ship.torps_remaining > 0:
        ship.magazine_empty_told = False
    elif not ship.magazine_empty_told and ship.tubes:
        ship.magazine_empty_told = True
        if ship.side == world.player_side:
            world.emit(Message(world.tick, f"{ship.name}: torpedo magazine empty.", Tone.CAUTION,
                               ship_id=ship.id, visible_to=frozenset({ship.side})))
    for t in ship.tubes:
        if t.loaded is not None or not t.enabled:
            continue
        if rules.weapons_need_full_repair and not t.intact:
            continue
        if not (t.autoload or t.manual_load_pending):
            continue
        if ship.torps_remaining <= 0:
            continue
        if t.charge <= 0.0:
            if free <= 0:
                continue
            free -= 1
        spec = world.content.torpedoes.get(t.load_ordnance) or world.content.torpedoes.get(cls.torpedo)
        if spec is None:
            continue
        rate = spec.load_energy / max(spec.charge_time, 0.01)
        cost = rate * dt
        pay = min(cost, max(0.0, pool))
        if pay <= 0.0 and cost > 0.0:
            continue
        frac = pay / cost if cost > 0 else 1.0
        pool -= pay
        spent += pay
        t.charge = min(100.0, t.charge + 100.0 / max(spec.charge_time, 0.01) * dt * frac)
        if t.charge >= 100.0 - 1e-6:
            prox = t.load_prox if t.load_prox > 0 else spec.max_prox
            prox = max(rules.prox_floor, min(spec.max_prox, prox))
            t.loaded = LoadedTorpedo(spec.id, prox)
            t.charge = 100.0
            t.manual_load_pending = False
            ship.torps_remaining -= 1

    # probe launchers: no energy, a short preparation (1 cycle) [E]
    for lch in ship.launchers:
        if lch.loaded is not None or lch.destroyed or not lch.intact:
            continue
        if not (lch.autoload or lch.manual_load_pending) or ship.probes_remaining <= 0:
            continue
        lch.prep += dt
        if lch.prep >= 1.0:
            world.load_probe(ship, lch)
    return pool, spent
