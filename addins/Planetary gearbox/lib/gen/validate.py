"""Input checks. Own copy of decad-gallery models/planetarygearbox problems.go (Problems, inputProblems, fitProblems,
bearingFitProblems; Params.Validate) at 45b5875.

Messages are the gallery's, without its "planetarygearbox: " prefix.
"""

from __future__ import annotations

import json
import math

from .bearing import catalog_names, lookup
from .dims import Dims, derive
from .sections import pin_socket_radius
from .ears import ear_problems
from . import gears as gearset
from .involute import closing_radius, is_embedded, validate_spur
from .kits import kit_for, kit_teeth
from .fasteners import (
    COVER_FLOOR,
    HEAD_HEIGHT,
    MIN_BOLT_HOLE_DIAMETER,
    NUT_ROOF,
    POCKET_MARGIN,
    SHANK_DIAMETER,
    head_pocket_diameter,
    nut_cavity_height,
    nut_pocket_diameter,
)
from .params import (
    BOLT_RIM_MARGIN,
    FIT_CLEARANCE,
    LIP_THICKNESS,
    COLLAR_MARGIN,
    GEAR_ROOT_MEASUREMENT_MARGIN,
    LOOSE_GEAR_CLEARANCE,
    MIN_EDGE_CHAMFER,
    MIN_SOCKET_FACE_WALL,
    MIN_SOCKET_WALL,
    PIN_SHOULDER_CLEARANCE,
    PIN_SHOULDER_REACH,
    PRESS_FIT_CLEARANCE,
    PLANET_BEARING_LIFT,
    RING_MARGIN,
    SEAT_CLEARANCE,
    Params,
    frame_is_valid,
    gear_root_depth,
)
from .report import fmt_num as n


_TOOTH_CHAIN = "tooth: spurgear: tooth section: "


class ValidationError(ValueError):
    pass


def _suggestion(p: Params) -> str:
    """Names a kit tooth set for p's bearings when p is at module 1 and uses other teeth, or returns ""."""
    if p.module != 1:
        return ""
    kit = kit_for(p.planet_bearing, p.shaft_bearing)
    if kit is None:
        return ""
    sun, planet, ring = kit_teeth(kit)
    if (sun, planet, ring) == (p.sun_teeth, p.planet_teeth, p.ring_teeth):
        return ""
    return f"; try {sun}/{planet}/{ring}"


def _placement_problems(p: Params) -> list[str]:
    if p.placement is not None and not frame_is_valid(p.placement):
        return ["invalid placement frame"]
    return []


def _input_problems(p: Params) -> list[str]:
    """Checks the inputs one at a time, in the order of the construction contract [inputProblems]."""
    probs: list[str] = []
    names_known = True
    for role, name in (("planet", p.planet_bearing), ("shaft", p.shaft_bearing)):
        if lookup(name) is None:
            probs.append(
                f"{role} bearing {json.dumps(name, ensure_ascii=False)} is not in the bearing catalog; "
                f"choose one of {', '.join(catalog_names())}"
            )
            names_known = False

    all_finite = True
    for name, v in (
        ("Module", p.module),
        ("PressureAngle", p.pressure_angle),
        ("GearThickness", p.gear_thickness),
        ("CarrierThickness", p.carrier_thickness),
        ("StageGap", p.stage_gap),
        ("CoverThickness", p.cover_thickness),
        ("BoltHoleDiameter", p.bolt_hole_diameter),
        ("InputShaftLength", p.input_shaft_length),
        ("FlatDepth", p.flat_depth),
        ("SeatChamfer", p.seat_chamfer),
        ("EdgeChamfer", p.edge_chamfer),
        ("BearingClearance", p.bearing_clearance),
        ("CarrierWall", p.carrier_wall),
        ("RingWall", p.ring_wall),
        ("Backlash", p.backlash),
        ("OutputShaftLength", p.output_shaft_length),
        ("EarBoreDiameter", p.ear_bore_diameter),
    ):
        if not math.isfinite(v):
            probs.append(f"{name} must be finite, got {n(v)}")
            all_finite = False
    if not all_finite:
        return probs

    flat_ok = p.flat_depth >= 0
    if names_known:
        pb, sb = lookup(p.planet_bearing), lookup(p.shaft_bearing)
        flat_ok = flat_ok and p.flat_depth <= min(pb.bore_diameter, sb.bore_diameter) / 4
    for name, v, ok in (
        ("module", p.module, p.module > 0),
        ("gear thickness", p.gear_thickness, p.gear_thickness > 0),
        ("carrier thickness", p.carrier_thickness, p.carrier_thickness >= 2),
        ("stage gap", p.stage_gap, p.stage_gap >= PLANET_BEARING_LIFT + PIN_SHOULDER_CLEARANCE + PIN_SHOULDER_REACH),
        ("cover thickness", p.cover_thickness, p.cover_thickness > 0),
        ("bolt hole diameter", p.bolt_hole_diameter, p.bolt_hole_diameter > 0),
        ("input shaft length", p.input_shaft_length, p.input_shaft_length > 0),
        ("flat depth", p.flat_depth, flat_ok),
        ("seat chamfer", p.seat_chamfer, 0 <= p.seat_chamfer <= 1),
        ("edge chamfer", p.edge_chamfer, MIN_EDGE_CHAMFER <= p.edge_chamfer <= 1),
        ("bearing clearance", p.bearing_clearance, p.bearing_clearance >= SEAT_CLEARANCE),
        ("carrier wall", p.carrier_wall, p.carrier_wall > 0),
        ("ring wall", p.ring_wall, p.ring_wall > 0),
        ("backlash", p.backlash, 0 <= p.backlash <= p.module / 2),
        ("output shaft length", p.output_shaft_length, p.output_shaft_length > 0),
        ("ear count", float(p.ear_count), p.ear_count >= 0),
        (
            "ear bore diameter",
            p.ear_bore_diameter,
            p.ear_bore_diameter >= 0 and (p.ear_count == 0 or p.ear_bore_diameter > 0),
        ),
    ):
        if not ok:
            probs.append(f"{name} {n(v)} is out of range")
    if p.pressure_angle <= 0 or p.pressure_angle >= math.pi / 2:
        probs.append(f"pressure angle {n(p.pressure_angle)} must be in (0, pi/2)")
    if p.samples < 3:
        probs.append(f"samples {p.samples} must be at least 3")
    count_ok = p.planet_count >= 2
    if not count_ok:
        probs.append(f"planet count {p.planet_count} must be at least 2")
    if p.stages < 1:
        probs.append(f"stages {p.stages} must be at least 1")
    teeth_ok = True
    for name, z in (("sun", p.sun_teeth), ("planet", p.planet_teeth), ("ring", p.ring_teeth)):
        if z < 3:
            probs.append(f"{name} teeth {z} must be at least 3")
            teeth_ok = False
    if not teeth_ok:
        return probs + _placement_problems(p)
    want = p.sun_teeth + 2 * p.planet_teeth
    if p.ring_teeth != want:
        probs.append(f"ring teeth {p.ring_teeth} must equal sun teeth + 2 * planet teeth = {want}")
    total = p.sun_teeth + p.ring_teeth
    if count_ok and total % p.planet_count != 0:
        probs.append(
            f"sun teeth + ring teeth = {total} must divide by planet count {p.planet_count} "
            "so the planets mesh at equal angles"
        )
    return probs + _placement_problems(p)


def _fit_problems(p: Params, d: Dims) -> list[str]:
    """Checks that the parts fit around each other; every failing check [fitProblems]."""
    probs: list[str] = []
    m = p.module
    chord = 2 * d.orbit * math.sin(math.pi / p.planet_count)
    if chord < 2 * d.planet_tip + LOOSE_GEAR_CLEARANCE:
        probs.append(
            f"neighbouring planet centers are {n(chord)} apart; tips need "
            f"{n(2 * d.planet_tip + LOOSE_GEAR_CLEARANCE)} for at least {n(LOOSE_GEAR_CLEARANCE)} clearance"
        )
    sun_root = m * p.sun_teeth / 2 - gear_root_depth(m)
    if d.shaft_bore / 2 > sun_root - m:
        min_sun = math.ceil((d.shaft_bore + 2 * gear_root_depth(m) + 2 * m) / m - 1e-9)
        probs.append(
            f"the {n(d.shaft_bore)} mm shaft bore leaves less than one module of wall under the sun root; "
            f"SunTeeth must be at least {min_sun} for the {n(d.shaft_bore)} mm shaft at module {n(m)}"
            f"{_suggestion(p)}"
        )
    wp = d.planet_bearing.width
    if p.gear_thickness - wp < LIP_THICKNESS:
        probs.append(
            f"gear thickness {n(p.gear_thickness)} leaves less than {n(LIP_THICKNESS)} "
            f"for the lip behind a {n(wp)} wide bearing; "
            f"a {p.planet_bearing} planet bearing needs GearThickness >= {n(wp + LIP_THICKNESS)}"
        )
    if d.planet_pocket / 2 > d.planet_root - m:
        min_planet = math.ceil(
            (d.planet_pocket + 2 * gear_root_depth(m) + 2 * GEAR_ROOT_MEASUREMENT_MARGIN + 2 * m) / m - 1e-9
        )
        probs.append(
            f"bearing pocket diameter {n(d.planet_pocket)} leaves less than one module of wall under the planet "
            f"root; PlanetTeeth must be at least {min_planet} for the {p.planet_bearing} planet bearing at module "
            f"{n(m)}{_suggestion(p)}"
        )
    if d.shaft / 2 + d.boss / 2 >= d.orbit:
        probs.append(
            f"shaft diameter {n(d.shaft)} and planet pin boss {n(d.boss)} do not fit within orbit radius {n(d.orbit)}"
        )
    if (
        d.bolt_circle - p.bolt_hole_diameter / 2 < d.ring_root + BOLT_RIM_MARGIN
        or d.bolt_circle + p.bolt_hole_diameter / 2 > d.ring_outer - BOLT_RIM_MARGIN
    ):
        probs.append(
            f"bolt holes of diameter {n(p.bolt_hole_diameter)} do not fit the ring wall {n(p.ring_wall)} "
            f"with {n(BOLT_RIM_MARGIN)} of material either side"
        )
    if p.bolt_hole_diameter < MIN_BOLT_HOLE_DIAMETER:
        probs.append(
            f"bolt hole diameter {n(p.bolt_hole_diameter)} is under the {n(MIN_BOLT_HOLE_DIAMETER)} "
            f"clearance hole for the M2 bolt shank {n(SHANK_DIAMETER)}"
        )
    if p.cover_thickness < HEAD_HEIGHT + COVER_FLOOR:
        probs.append(
            f"cover thickness {n(p.cover_thickness)} leaves less than {n(COVER_FLOOR)} "
            f"under a {n(HEAD_HEIGHT)} tall bolt head"
        )
    reach = max(nut_pocket_diameter(), head_pocket_diameter()) / 2
    if d.bolt_circle - reach < d.ring_root + POCKET_MARGIN or d.bolt_circle + reach > d.ring_outer - POCKET_MARGIN:
        probs.append(
            f"bolt head and nut pockets of radius {n(reach)} do not fit the ring wall {n(p.ring_wall)} "
            f"with {n(POCKET_MARGIN)} of material either side"
        )
    if d.ring_length < 2 * (NUT_ROOF + nut_cavity_height()) + 2 * POCKET_MARGIN:
        probs.append(f"ring length {n(d.ring_length)} is too short for a nut cavity at each end")
    if d.cover_hub / 2 >= d.rim_inner - d.arm:
        min_wall = 2 * (d.cover_hub / 2 + d.arm + head_pocket_diameter() / 2 + BOLT_RIM_MARGIN - d.ring_root)
        probs.append(
            f"the cover's bearing hub of diameter {n(d.cover_hub)} leaves no room for spokes "
            f"inside the rim at radius {n(d.rim_inner)}; "
            f"the {p.shaft_bearing} shaft bearing needs RingWall above {min_wall:.2f} or more RingTeeth"
        )
    if d.orbit + d.boss / 2 >= d.ring_tip - LOOSE_GEAR_CLEARANCE:
        probs.append(
            f"carrier radius {n(d.orbit + d.boss / 2)} does not leave more than {n(LOOSE_GEAR_CLEARANCE)} "
            f"clearance from ring tip radius {n(d.ring_tip)}"
        )
    if p.flat_depth >= COLLAR_MARGIN:
        probs.append(
            f"flat depth {n(p.flat_depth)} must stay under the {n(COLLAR_MARGIN)} collar margin, "
            "so a thick part's flat stays outside its rod"
        )
    socket = pin_socket_radius(d)
    wall = d.boss / 2 - socket
    if wall < MIN_SOCKET_WALL:
        probs.append(
            f"carrier wall {n(p.carrier_wall)} leaves {n(wall)} of plate around a pin socket, "
            f"less than {n(MIN_SOCKET_WALL)}"
        )
    face = wall - p.edge_chamfer
    if face < MIN_SOCKET_FACE_WALL:
        probs.append(
            f"carrier wall {n(p.carrier_wall)} and edge chamfer {n(p.edge_chamfer)} leave {n(face)} of plate "
            f"around a pin socket at the plate's face, less than {n(MIN_SOCKET_FACE_WALL)}"
        )
    return probs


def _collar_race_problem(collar: float, race: float, name: str) -> str:
    """A problem when the shaft collar is not narrower than the shaft bearing's inner race."""
    if collar < race:
        return ""
    return f"the {n(collar)} mm shaft collar is not narrower than the {n(race)} mm inner race of the {name} shaft bearing"


def _pin_race_problem(pin_collar: float, race: float, name: str) -> str:
    """A problem when the pin's thick part is not narrower than the planet bearing's inner race."""
    if pin_collar < race:
        return ""
    return (
        f"the {n(pin_collar)} mm pin thick part is not narrower than the {n(race)} mm inner race "
        f"of the {name} planet bearing"
    )


def _collar_lip_problem(collar: float, lip: float) -> str:
    """A problem when the shaft collar does not pass the cover's lip bore with FIT_CLEARANCE on each side."""
    if collar + 2 * FIT_CLEARANCE <= lip:
        return ""
    return (
        f"the {n(collar)} mm shaft collar does not pass the {n(lip)} mm cover lip bore "
        f"with {n(FIT_CLEARANCE)} on each side"
    )


def _centre_hole_problem(orbit: float, collar: float, pin_collar: float) -> str:
    """A problem when the carrier's centre hole and a pin socket leave less than MIN_SOCKET_WALL of plate."""
    plate = orbit - (collar / 2 + PRESS_FIT_CLEARANCE) - (pin_collar / 2 + PRESS_FIT_CLEARANCE)
    if plate >= MIN_SOCKET_WALL:
        return ""
    return (
        f"the carrier's centre hole and pin sockets leave {n(plate)} of plate between them, "
        f"less than {n(MIN_SOCKET_WALL)}"
    )


def _bearing_fit_problems(p: Params, d: Dims) -> list[str]:
    """The checks that a bearing's size forces on the shafts, pins and carrier."""
    found = (
        _collar_race_problem(d.collar, d.shaft_bearing.inner_race_diameter, p.shaft_bearing),
        _pin_race_problem(d.pin_collar, d.planet_bearing.inner_race_diameter, p.planet_bearing),
        _collar_lip_problem(d.collar, d.cover_lip),
        _centre_hole_problem(d.orbit, d.collar, d.pin_collar),
    )
    return [s for s in found if s]


def _spur_problem(p: Params, d: Dims) -> str | None:
    """Message of the first spur-gear limit, which the gallery raises at build time (ring, sun, planet order)."""
    m = p.module
    sun_bore = d.shaft_bore if p.flat_depth == 0 else 0.0
    gears = (
        ("ring tooth spaces: ", p.ring_teeth, d.ring_length + 2 * RING_MARGIN, 0.0, -p.backlash),
        ("sun gear: ", p.sun_teeth, p.gear_thickness, sun_bore, p.backlash),
        ("planet gear: ", p.planet_teeth, p.gear_thickness, d.planet_lip, p.backlash),
    )
    for prefix, teeth, thickness, bore, backlash in gears:
        msg = validate_spur(m, teeth, p.pressure_angle, thickness, p.samples, bore, backlash)
        if msg is not None:
            return prefix + msg
        if prefix.startswith("ring"):
            gd = gearset.ring_tool(p)
        elif prefix.startswith("sun"):
            gd = gearset.sun_gear(p)
        else:
            gd = gearset.planet_gear(p)
        if is_embedded(gd):
            try:
                closing_radius(gd)
            except ValueError as e:
                # [spurgear assemble "tooth: %w" + Variant.tooth "spurgear: tooth section: %w"]
                return prefix + _TOOTH_CHAIN + str(e)
    return None


def problems(p: Params) -> list[str]:
    """Every way p is invalid, in check order; empty for a buildable p [Problems].

    When an input check fails, only the input problems are returned, because the fit checks read derived dimensions
    that need valid inputs.
    """
    probs = _input_problems(p)
    if probs:
        return probs
    d = derive(p)
    probs = _fit_problems(p, d) + _bearing_fit_problems(p, d) + ear_problems(p, d)
    if not probs:
        # Deviation: the spur-gear limits, which the gallery raises at build time, are checked here so the dialog shows
        # them before building (docs/planetarygearbox/deviations.md "Input errors"). Only the first failing gear is
        # reported, as the gallery build would stop there.
        msg = _spur_problem(p, d)
        if msg is not None:
            probs.append(msg)
    return probs


def validate(p: Params) -> None:
    """Raise ValidationError with the first message of problems(p) [Params.Validate]."""
    probs = problems(p)
    if probs:
        raise ValidationError(probs[0])
