"""Per-phase simulation behaviour operating on `World` state.

Each module owns one area of the rules (helm, power, shields, phasers,
torpedoes, probes, damage, repair, sensors, special 2.0 systems). The world
step calls them in a fixed order; see `World.step`.
"""
