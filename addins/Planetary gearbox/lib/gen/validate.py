"""Input validation. Own copy of decad-gallery models/planetarygearbox Params.Validate / validateFit / validateEars.

Messages are the gallery's (791aeb2), without its "planetarygearbox: " prefix.
"""

from __future__ import annotations

import math

from .bearing import bearing_608zz
from .dims import derive
from .ears import validate_ears
from . import gears as gearset
from .involute import closing_radius, is_embedded, validate_spur
from .fasteners import (
    COVER_FLOOR,
    HEAD_HEIGHT,
    MIN_BOLT_HOLE_DIAMETER,
    NUT_ROOF,
    POCKET_MARGIN,
    SHANK_DIAMETER,
    head_pocket_diameter,
    nut_cavity_height,
    nut_pocket_flats,
)
from .params import (
    BOLT_RIM_MARGIN,
    FIT_CLEARANCE,
    LIP_THICKNESS,
    LOOSE_GEAR_CLEARANCE,
    MIN_EDGE_CHAMFER,
    PIN_COLLAR_CLEARANCE,
    PIN_COLLAR_THICKNESS,
    PLANET_BEARING_LIFT,
    RING_MARGIN,
    Params,
    frame_is_valid,
)
from .report import fmt_num as n


_TOOTH_CHAIN = "spurgear: tooth: spurgear: tooth section: "


class ValidationError(ValueError):
    pass


def validate(p: Params) -> None:
    """Raise ValidationError with the message of the first failing rule."""
    b = bearing_608zz()
    m = p.module

    # 1. Finiteness.
    for name, v in (
        ("Module", p.module),
        ("PressureAngle", p.pressure_angle),
        ("GearThickness", p.gear_thickness),
        ("CarrierThickness", p.carrier_thickness),
        ("StageGap", p.stage_gap),
        ("CoverThickness", p.cover_thickness),
        ("BoltHoleDiameter", p.bolt_hole_diameter),
        ("InputShaftLength", p.input_shaft_length),
        ("KeyDepth", p.key_depth),
        ("KeyWidth", p.key_width),
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
            raise ValidationError(f"{name} must be finite, got {n(v)}")

    # 2. Ranges.
    for name, v, ok in (
        ("module", p.module, p.module > 0),
        ("gear thickness", p.gear_thickness, p.gear_thickness > 0),
        ("carrier thickness", p.carrier_thickness, p.carrier_thickness > 0),
        ("stage gap", p.stage_gap, p.stage_gap >= PLANET_BEARING_LIFT + PIN_COLLAR_CLEARANCE + PIN_COLLAR_THICKNESS),
        ("cover thickness", p.cover_thickness, p.cover_thickness > 0),
        ("bolt hole diameter", p.bolt_hole_diameter, p.bolt_hole_diameter > 0),
        ("input shaft length", p.input_shaft_length, p.input_shaft_length > 0),
        ("key depth", p.key_depth, 0 <= p.key_depth <= b.bore_diameter / 4),
        ("seat chamfer", p.seat_chamfer, 0 <= p.seat_chamfer <= 1),
        ("edge chamfer", p.edge_chamfer, MIN_EDGE_CHAMFER <= p.edge_chamfer <= 1),
        ("key width", p.key_width, 0 < p.key_width <= b.bore_diameter / 2),
        ("bearing clearance", p.bearing_clearance, p.bearing_clearance >= FIT_CLEARANCE),
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
            raise ValidationError(f"{name} {n(v)} is out of range")

    # 3-4. Angle and counts.
    if p.pressure_angle <= 0 or p.pressure_angle >= math.pi / 2:
        raise ValidationError(f"pressure angle {n(p.pressure_angle)} must be in (0, pi/2)")
    if p.samples < 3:
        raise ValidationError(f"samples {p.samples} must be at least 3")
    if p.planet_count < 2:
        raise ValidationError(f"planet count {p.planet_count} must be at least 2")
    if p.stages < 1:
        raise ValidationError(f"stages {p.stages} must be at least 1")

    # 5-7. Teeth.
    for name, z in (("sun", p.sun_teeth), ("planet", p.planet_teeth), ("ring", p.ring_teeth)):
        if z < 3:
            raise ValidationError(f"{name} teeth {z} must be at least 3")
    want = p.sun_teeth + 2 * p.planet_teeth
    if p.ring_teeth != want:
        raise ValidationError(f"ring teeth {p.ring_teeth} must equal sun teeth + 2 * planet teeth = {want}")
    total = p.sun_teeth + p.ring_teeth
    if total % p.planet_count != 0:
        raise ValidationError(
            f"sun teeth + ring teeth = {total} must divide by planet count {p.planet_count} "
            "so the planets mesh at equal angles"
        )

    # 8. Placement.
    if p.placement is not None and not frame_is_valid(p.placement):
        raise ValidationError("invalid placement frame")

    if p.key_depth > 0 and p.key_width <= 2 * FIT_CLEARANCE:
        raise ValidationError(
            f"key width {n(p.key_width)} must exceed {n(2 * FIT_CLEARANCE)} for the shaft clearance"
        )

    # 9. Fit.
    d = derive(p)
    chord = 2 * d.orbit * math.sin(math.pi / p.planet_count)
    if chord < 2 * d.planet_tip + LOOSE_GEAR_CLEARANCE:
        raise ValidationError(
            f"neighbouring planet centers are {n(chord)} apart; tips need "
            f"{n(2 * d.planet_tip + LOOSE_GEAR_CLEARANCE)} for at least {n(LOOSE_GEAR_CLEARANCE)} clearance"
        )
    if d.shaft_bore / 2 > d.sun_root - m:
        raise ValidationError(
            f"the {n(d.shaft_bore)} mm shaft bore leaves less than one module of wall under the sun root"
        )
    if p.gear_thickness - b.width < LIP_THICKNESS:
        raise ValidationError(
            f"gear thickness {n(p.gear_thickness)} leaves less than {n(LIP_THICKNESS)} "
            f"for the lip behind a {n(b.width)} wide bearing"
        )
    if d.pocket / 2 > d.planet_root - m:
        raise ValidationError(
            f"bearing pocket diameter {n(d.pocket)} leaves less than one module of wall under the planet root"
        )
    if d.shaft / 2 + d.boss / 2 >= d.orbit:
        raise ValidationError(
            f"shaft diameter {n(d.shaft)} and planet pin boss {n(d.boss)} do not fit within orbit radius {n(d.orbit)}"
        )
    if (
        d.bolt_circle - p.bolt_hole_diameter / 2 < d.ring_root + BOLT_RIM_MARGIN
        or d.bolt_circle + p.bolt_hole_diameter / 2 > d.ring_outer - BOLT_RIM_MARGIN
    ):
        raise ValidationError(
            f"bolt holes of diameter {n(p.bolt_hole_diameter)} do not fit the ring wall {n(p.ring_wall)} "
            f"with {n(BOLT_RIM_MARGIN)} of material either side"
        )
    if p.bolt_hole_diameter < MIN_BOLT_HOLE_DIAMETER:
        raise ValidationError(
            f"bolt hole diameter {n(p.bolt_hole_diameter)} is under the {n(MIN_BOLT_HOLE_DIAMETER)} "
            f"clearance hole for the M2 bolt shank {n(SHANK_DIAMETER)}"
        )
    if p.cover_thickness < HEAD_HEIGHT + COVER_FLOOR:
        raise ValidationError(
            f"cover thickness {n(p.cover_thickness)} leaves less than {n(COVER_FLOOR)} "
            f"under a {n(HEAD_HEIGHT)} tall bolt head"
        )
    reach = max(nut_pocket_flats(), head_pocket_diameter()) / 2
    if d.bolt_circle - reach < d.ring_root + POCKET_MARGIN or d.bolt_circle + reach > d.ring_outer - POCKET_MARGIN:
        raise ValidationError(
            f"bolt head and nut pockets of radius {n(reach)} do not fit the ring wall {n(p.ring_wall)} "
            f"with {n(POCKET_MARGIN)} of material either side"
        )
    if d.ring_length < 2 * (NUT_ROOF + nut_cavity_height()) + 2 * POCKET_MARGIN:
        raise ValidationError(f"ring length {n(d.ring_length)} is too short for a nut cavity at each end")
    if d.cover_hub / 2 >= d.rim_inner - d.arm:
        raise ValidationError(
            f"the cover's bearing hub of diameter {n(d.cover_hub)} leaves no room for spokes "
            f"inside the rim at radius {n(d.rim_inner)}"
        )
    if d.orbit + d.boss / 2 >= d.ring_tip - LOOSE_GEAR_CLEARANCE:
        raise ValidationError(
            f"carrier radius {n(d.orbit + d.boss / 2)} does not leave more than {n(LOOSE_GEAR_CLEARANCE)} "
            f"clearance from ring tip radius {n(d.ring_tip)}"
        )

    # The ears clear each other and the bolt sites [params.go validateEars].
    ear_error = validate_ears(p, d)
    if ear_error is not None:
        raise ValidationError(ear_error)

    # 10. Spur-gear limits, which the gallery raises at build time (ring, sun, planet order).
    # Deviation: checked here so the dialog shows them before building (README "Deviations from decad-gallery").
    sun_bore = d.shaft_bore if p.key_depth == 0 else 0.0
    gears = (
        ("ring tooth spaces: ", p.ring_teeth, d.ring_length + 2 * RING_MARGIN, 0.0, -p.backlash),
        ("sun gear: ", p.sun_teeth, p.gear_thickness, sun_bore, p.backlash),
        ("planet gear: ", p.planet_teeth, p.gear_thickness, d.lip, p.backlash),
    )
    for prefix, teeth, thickness, bore, backlash in gears:
        msg = validate_spur(m, teeth, p.pressure_angle, thickness, p.samples, bore, backlash)
        if msg is not None:
            raise ValidationError(prefix + msg)
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
                # [spurgear assemble "spurgear: tooth: %w" + Variant.tooth "spurgear: tooth section: %w"]
                raise ValidationError(prefix + _TOOTH_CHAIN + str(e)) from e
