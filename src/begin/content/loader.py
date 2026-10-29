"""Load and validate TOML content into a `ContentDB`."""

from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schema import (
    CaptainModel,
    ContentDB,
    Doctrine,
    Dogma,
    Faction,
    HullDef,
    MountDef,
    ProbeDef,
    RepairRates,
    Shape,
    ShipClass,
    TorpedoDef,
)

DATA_DIR = Path(__file__).parent / "data"


class ContentError(ValueError):
    pass


def _pt(v: Any) -> tuple[float, float]:
    return float(v[0]), float(v[1])


def _shape(d: dict[str, Any]) -> Shape:
    kind = d["kind"]
    role = d.get("role", "hull")
    if kind == "poly":
        return Shape("poly", role, points=tuple(_pt(p) for p in d["pts"]))
    if kind == "ellipse":
        return Shape("ellipse", role, center=_pt(d["c"]), radii=_pt(d["r"]))
    raise ContentError(f"unknown shape kind {kind!r}")


def _mounts(items: list[dict[str, Any]]) -> tuple[MountDef, ...]:
    return tuple(MountDef(_pt(m["pos"]), float(m["arc"][0]), float(m["arc"][1])) for m in items)


def _hull(cid: str, d: dict[str, Any]) -> HullDef:
    a = d["anchors"]
    return HullDef(
        class_id=cid,
        length=float(d["length"]),
        shapes=tuple(_shape(s) for s in d["shapes"]),
        bridge=_pt(a["bridge"]),
        core=_pt(a["core"]),
        nose=_pt(a["nose"]),
        aft=_pt(a["aft"]),
        nacelles=tuple(_pt(p) for p in a.get("nacelles", [])),
        banks=_mounts(d.get("banks", [])),
        tubes=_mounts(d.get("tubes", [])),
        launchers=_mounts(d.get("launchers", [])),
    )


CUSTOM_CLASSES = "custom_classes.toml"
CUSTOM_ORDNANCE = "custom_ordnance.toml"


def _read(name: str, data_dir: Path) -> dict[str, Any]:
    with open(data_dir / name, "rb") as f:
        return tomllib.load(f)


def load_content(data_dir: Path = DATA_DIR) -> ContentDB:
    db = ContentDB()
    ordnance = _read("ordnance.toml", data_dir)
    torpedoes = list(ordnance.get("torpedo", []))
    if (data_dir / CUSTOM_ORDNANCE).is_file():  # hand-written designs; the importer never touches this file
        torpedoes += _read(CUSTOM_ORDNANCE, data_dir).get("torpedo", [])
    for t in torpedoes:
        db.torpedoes[t["id"]] = TorpedoDef(
            id=t["id"], name=t["name"], velocity=float(t["velocity"]), damage=float(t["damage"]),
            arm_time=float(t["arm_time"]), max_time_fuse=float(t["max_time_fuse"]),
            max_prox=float(t["max_prox"]), homing=bool(t["homing"]),
            speed_variance=float(t["speed_variance"]), warhead_type=int(t["warhead_type"]),
            charge_time=float(t["charge_time"]), load_energy=float(t["load_energy"]),
            reveal_radius=float(t.get("reveal_radius", 0.0)), reveal_cycles=float(t.get("reveal_cycles", 0.0)),
            special=bool(t.get("special", False)),
        )
    for p in ordnance.get("probe", []):
        db.probes[p["id"]] = ProbeDef(
            id=p["id"], name=p["name"], velocity=float(p["velocity"]), damage=float(p["damage"]),
            arm_time=float(p["arm_time"]), max_time_fuse=float(p["max_time_fuse"]),
            max_prox=float(p["max_prox"]), homing=bool(p["homing"]), scan_range=float(p["scan_range"]),
        )

    doctrines_raw = _read("doctrines.toml", data_dir)["doctrine"]
    doctrines = {
        k: Doctrine(
            id=k,
            weapon_bias={kk: float(vv) for kk, vv in v["weapon_bias"].items()},
            focus_fire=float(v["focus_fire"]),
            probe_use=float(v["probe_use"]),
            retreat_threshold_scale=float(v["retreat_threshold_scale"]),
            surrender_willingness=float(v["surrender_willingness"]),
            point_defense=str(v["point_defense"]),
            cloak_ambush=float(v["cloak_ambush"]),
            self_destruct=float(v["self_destruct"]),
            prefers_disabling=bool(v["prefers_disabling"]),
        )
        for k, v in doctrines_raw.items()
    }

    for f in _read("factions.toml", data_dir)["faction"]:
        dg = f["dogma"]
        cm = f["captains"]
        if f["doctrine"] not in doctrines:
            raise ContentError(f"faction {f['id']} references unknown doctrine {f['doctrine']}")
        db.factions[f["id"]] = Faction(
            id=f["id"], name=f["name"], long_name=f["long_name"], command=f["command"],
            doctrine=doctrines[f["doctrine"]],
            torpedoes=tuple(f["torpedoes"]), probes=tuple(f["probes"]),
            officer_names=tuple(f["officer_names"]), captain_names=tuple(f["captain_names"]),
            dogma=Dogma(**{k: float(v) for k, v in dg.items()}),
            computer_sophistication=float(f["computer"]["sophistication"]),
            sensor_scale=float(f.get("sensors", {}).get("range", 1.0)),
            pd_discipline=float(f["computer"].get("pd_discipline", 0.7)),
            captains=CaptainModel(**{k: float(v) for k, v in cm.items()}),
        )

    hulls_raw = _read("hulls.toml", data_dir)["hull"]
    raw_classes: dict[str, dict[str, Any]] = {}
    entries = list(_read("classes.toml", data_dir)["class"])
    if (data_dir / CUSTOM_CLASSES).is_file():  # hand-written classes; the importer never touches this file
        entries += _read(CUSTOM_CLASSES, data_dir).get("class", [])
    for c in entries:
        # `base = "<class id>"` copies an earlier class; the entry then lists only what differs
        if "base" in c:
            if c["base"] not in raw_classes:
                raise ContentError(f"class {c['id']}: base {c['base']!r} must be an earlier class")
            base = raw_classes[c["base"]]
            c = {**base, "repair": dict(base["repair"]), **{k: v for k, v in c.items() if k != "base"},
                 "hull_of": base.get("hull_of", base["id"])}
        raw_classes[c["id"]] = c
        cid = c["id"]
        hull_id = cid if cid in hulls_raw else c.get("hull_of", cid)
        if hull_id not in hulls_raw:
            raise ContentError(f"class {cid} has no hull definition")
        if c["faction"] not in db.factions:
            raise ContentError(f"class {cid} references unknown faction {c['faction']}")
        hull = _hull(hull_id, hulls_raw[hull_id])
        fields = {k: v for k, v in c.items() if k not in ("repair", "ship_names", "hull_of")}
        cls = ShipClass(
            **fields,
            ship_names=tuple(c["ship_names"]),
            repair=RepairRates(**{k: float(v) for k, v in c["repair"].items()}),
            hull=hull,
            sensor_scale=db.factions[c["faction"]].sensor_scale,
        )
        _validate_class(cls, db)
        db.classes[cid] = cls
    return db


def _validate_class(cls: ShipClass, db: ContentDB) -> None:
    if cls.tubes and cls.torpedo not in db.torpedoes:
        raise ContentError(f"{cls.id}: unknown torpedo {cls.torpedo!r}")
    if cls.launchers and cls.probe not in db.probes:
        raise ContentError(f"{cls.id}: unknown probe {cls.probe!r}")
    for kind, count, mounts in (
        ("banks", cls.banks, cls.hull.banks),
        ("tubes", cls.tubes, cls.hull.tubes),
        ("launchers", cls.launchers, cls.hull.launchers),
    ):
        if count and not mounts:
            raise ContentError(f"{cls.id}: {count} {kind} but no mount positions")


@lru_cache(maxsize=1)
def default_content() -> ContentDB:
    """The built-in content set (cached; treat as read-only)."""
    return load_content()
