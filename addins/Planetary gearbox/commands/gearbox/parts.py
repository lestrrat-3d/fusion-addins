"""One builder per gallery part. Each builds at part-local coordinates and returns the finished body."""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import edgefinish, gears, layout
from ...lib.gen.curves import Circle
from ...lib.gen.ears import ear_bore_centers, ring_outline
from ...lib.gen.involute import (
    GearDims,
    is_embedded,
    root_contacts,
    tooth_section,
)
from ...lib.gen.fasteners import (
    FASTENER_LENGTH,
    FASTENER_STOCK,
    NUT_ACROSS_FLATS,
    NUT_BORE_DIAMETER,
    NUT_THICKNESS,
    SHANK_DIAMETER,
    SOCKET_ACROSS_FLATS,
    SOCKET_CUTTER_RISE,
    SOCKET_DEPTH,
    HEAD_HEIGHT,
    UNDERHEAD_RADIUS,
    bolt_section,
    head_pocket_diameter,
    hexagon_loop,
    nut_cavity_height,
    nut_chamfer_section,
    nut_pocket_flats,
)
from ...lib.gen.params import (
    PIN_COLLAR_CLEARANCE,
    PIN_COLLAR_THICKNESS,
    PLANET_BEARING_LIFT,
    RING_MARGIN,
    TOOL_MARGIN,
)
from ...lib.gen.phase import ring_tooth_angle
from ...lib.gen.report import fmt_num
from ...lib.gen.sections import (
    bolt_hole_centers,
    carrier_plate_outline,
    cover_window_loops,
    key_box,
    key_tool_section,
)
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _tool_instances(
    ctx: BuildContext, tool: adsk.fusion.BRepBody, poses: list[layout.Pose], what: str
) -> list[adsk.fusion.BRepBody]:
    """Copy tool into every pose but the last, then move the tool itself into the last [place.go instances].

    Returns the bodies in pose order, the tool last.
    """
    out: list[adsk.fusion.BRepBody] = []
    for pose in poses[:-1]:
        body = fusion.copy_body(ctx, tool, f"{what}_copy")
        fusion.move(ctx, body, pose, f"{what}_move")
        out.append(body)
    fusion.move(ctx, tool, poses[-1], f"{what}_move")
    out.append(tool)
    return out


def build_spur(
    ctx: BuildContext, what: str, gd: GearDims, thickness: float, bore: float, fillet_fallback: bool = False
) -> adsk.fusion.BRepBody:
    """Tooth section + root disc extrude, circular pattern, join, root fillet, bore cut [spurgear assemble]."""
    comp, n, samples = ctx.comp, gd.teeth, ctx.p.samples

    def w(step: str) -> str:
        return f"{what} {step}"

    sk = fusion.new_sketch(comp, f"{what} tooth")
    fusion.draw_loop(sk, tooth_section(gd, samples))
    tooth = fusion.extrude(ctx, fusion.profile_with_loops(sk, 1, w("tooth_sketch"), only=True), 0.0, thickness,
                           w("tooth_extrude"))

    sk = fusion.new_sketch(comp, f"{what} root disc")
    fusion.draw_circle(sk, (0.0, 0.0), gd.root)
    disc = fusion.extrude(ctx, fusion.profile_with_loops(sk, 1, w("root_disc_sketch"), only=True), 0.0, thickness,
                          w("root_disc"))

    teeth = fusion.pattern(ctx, tooth, n, w("pattern"))
    gear = fusion.join(ctx, disc, teeth, w("join"))

    if gd.fillet > 0:
        if is_embedded(gd):
            edges = fusion.concave_axial_edges(gear)
        else:
            edges = fusion.axial_edges_at(gear, root_contacts(gd, samples))
        if len(edges) != 2 * n:
            raise fusion.BuildError(f"{w('root_fillet')}: found {len(edges)} root edges, expected {2 * n}")
        if fillet_fallback:
            _fillet_with_fallback(ctx, what, gd, edges)
        else:
            fusion.fillet(ctx, edges, gd.fillet, w("root_fillet"))

    if bore > 0:
        sk = fusion.new_sketch(comp, f"{what} bore")
        fusion.draw_circle(sk, (0.0, 0.0), bore / 2)
        tool = fusion.extrude(ctx, fusion.profile_with_loops(sk, 1, w("bore_sketch"), only=True), -TOOL_MARGIN,
                              thickness + 2 * TOOL_MARGIN, w("bore_extrude"))
        gear = fusion.cut(ctx, gear, [tool], w("bore_cut"))
    return gear


def _fillet_with_fallback(ctx: BuildContext, what: str, gd: GearDims, edges: list) -> None:
    """Root fillet ladder (planet only): design radius, then the largest radius that fits the flank line, then none.

    Deviation from decad-gallery: Fusion may reject the planet's fillet, so a rejected fillet must not abort the
    build. At the default inputs the design radius fits and the ladder has one rung before the skip.
    The radius actually used is stored in ctx.fillet_radius for the volume check.
    """
    step = f"{what} root_fillet"
    # 1% under the exact fit, because a fillet that uses up the whole flank line is often rejected.
    reduced = 0.99 * (gd.base**2 - gd.root**2) / (2 * gd.root)
    ladder = [gd.fillet] + ([reduced] if 0 < reduced < gd.fillet else [])
    name = layout.master_name(ctx.p, ctx.d, ctx.part)
    for radius in ladder:
        try:
            fusion.fillet(ctx, edges, radius, step)
        except fusion.BuildError:
            continue
        ctx.fillet_radius[ctx.part] = radius
        if radius != gd.fillet:
            ctx.log.write("fallback", [("part", name), ("step", "root_fillet"), ("radius_mm", radius)])
        return
    ctx.fillet_radius[ctx.part] = 0.0
    ctx.log.write("fallback", [("part", name), ("step", "root_fillet"), ("radius_mm", 0.0)])


def extrude_key_tool(ctx: BuildContext, what: str, z: float, length: float) -> adsk.fusion.BRepBody:
    """The shaft's round section less the three keyways, extruded from z for length [extrudeKeyTool]."""
    sk = fusion.new_sketch(ctx.comp, f"{what} key tool")
    section = key_tool_section(ctx.p, ctx.d)
    if isinstance(section, Circle):
        fusion.draw_circle(sk, section.center, section.radius)
    else:
        fusion.draw_loop(sk, section)
    profile = fusion.profile_with_loops(sk, 1, f"{what} key_tool_sketch", only=True)
    return fusion.extrude(ctx, profile, z, length, f"{what} key_tool_extrude")


def build_sun(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildSun]"""
    p, d = ctx.p, ctx.d
    keyed = p.key_depth > 0
    gd = gears.sun_gear(p)
    # [buildSun] The unkeyed sun bore is the shaft bore, with the fit clearance.
    sun = build_spur(ctx, "sun", gd, p.gear_thickness, 0.0 if keyed else d.shaft_bore)
    if keyed:
        tool = extrude_key_tool(ctx, "sun", -TOOL_MARGIN, p.gear_thickness + 2 * TOOL_MARGIN)
        sun = fusion.cut(ctx, sun, [tool], "sun keyed_bore_cut")
    return _require_solid(ctx, sun)


def chamfer_seat(ctx: BuildContext, body: adsk.fusion.BRepBody, z: float) -> None:
    """Chamfer the bearing pocket's rim at height z [chamferSeat]."""
    sc = ctx.p.seat_chamfer
    if sc == 0:
        return
    edges = fusion.circular_edges_at(body, ctx.d.pocket / 2, z)
    if not edges:
        raise fusion.BuildError(f"{ctx.part} seat_chamfer: no pocket rim edge at z={z}")
    fusion.chamfer(ctx, edges, sc, f"{ctx.part} seat_chamfer")


def finish_face_edges(ctx: BuildContext, body: adsk.fusion.BRepBody) -> None:
    """Surface edge finishing [edgefinish.go finishFaceEdges]: one equal-distance chamfer feature per plane of
    edgefinish.finish_planes, on the loops its rule keeps, by edge_chamfer."""
    for fp in edgefinish.finish_planes(ctx.p, ctx.d, ctx.part):
        step = f"{ctx.part} edge_chamfer z={fmt_num(fp.z)}"
        loops = fusion.flat_face_loops(body, fp.z, edgefinish.LARGE_FACE_AREA, step)
        kept = [
            edges for outer, edges, radius in loops if edgefinish.keep_loop(fp.rule, outer, len(edges), radius, ctx.d)
        ]
        if not kept:
            raise fusion.BuildError(f"{step}: no loop to chamfer")
        # Deviation: README "Edge finishing loop count".
        if len(kept) != fp.loops:
            raise fusion.BuildError(f"{step}: found {len(kept)} loops to chamfer, expected {fp.loops}")
        # Exactly the kept edges, like the gallery's Exactly(count) selection: no tangent chain.
        fusion.chamfer(ctx, [e for edges in kept for e in edges], ctx.p.edge_chamfer, step, tangent_chain=False)
        if not body.isSolid:
            raise fusion.BuildError(f"{step}: chamfered result is not a solid")


def build_planet(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildPlanet]"""
    p, d = ctx.p, ctx.d
    t, wb = p.gear_thickness, d.bearing.width
    gd = gears.planet_gear(p)
    planet = build_spur(ctx, "planet", gd, t, d.lip, fillet_fallback=True)
    sk = fusion.new_sketch(ctx.comp, "planet pocket")
    fusion.draw_circle(sk, (0.0, 0.0), d.pocket / 2)
    profile = fusion.profile_with_loops(sk, 1, "planet pocket_sketch", only=True)
    tool = fusion.extrude(ctx, profile, t - wb, wb + 1.0, "planet pocket_extrude")
    planet = fusion.cut(ctx, planet, [tool], "planet pocket_cut")
    chamfer_seat(ctx, planet, t)
    return _require_solid(ctx, planet)


def build_bearing(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildBearing / ballbearing Build] The 608ZZ envelope: a ring from the bore to the outer diameter."""
    b = ctx.d.bearing
    sk = fusion.new_sketch(ctx.comp, f"{ctx.part} ring")
    fusion.draw_circle(sk, (0.0, 0.0), b.outer_diameter / 2)
    fusion.draw_circle(sk, (0.0, 0.0), b.bore_diameter / 2)
    profile = fusion.profile_with_loops(sk, 2, f"{ctx.part} bearing_sketch")
    body = fusion.extrude(ctx, profile, 0.0, b.width, f"{ctx.part} bearing_extrude")
    return _require_solid(ctx, body)


def build_ring(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildRing] The tooth-space tool is cut out of a bolted blank with mounting ears; then both end faces' rims
    (the ears' outline included) are chamfered."""
    p, d = ctx.p, ctx.d
    length = d.ring_length
    gd = gears.ring_tool(p)
    tool = build_spur(ctx, "ring", gd, length + 2 * RING_MARGIN, 0.0)
    turn = ring_tooth_angle(p)
    if turn != 0:
        fusion.move(ctx, tool, layout.Pose(angle=turn), "ring ring_tool_turn")
    sk = fusion.new_sketch(ctx.comp, "ring blank")
    # [addRingOutline] A circle, or with mounting ears one closed loop; each ear's bore is a hole of the section.
    outline = ring_outline(p, d)
    if isinstance(outline, Circle):
        fusion.draw_circle(sk, outline.center, outline.radius)
    else:
        fusion.draw_loop(sk, outline)
    for c in bolt_hole_centers(d):
        fusion.draw_circle(sk, c, p.bolt_hole_diameter / 2)
    for c in ear_bore_centers(p, d):
        fusion.draw_circle(sk, c, p.ear_bore_diameter / 2)
    profile = fusion.profile_with_loops(sk, 5 + p.ear_count, "ring ring_blank_sketch")
    blank = fusion.extrude(ctx, profile, RING_MARGIN, length, "ring ring_blank_extrude")

    # [cutNutPockets] Eight closed hexagonal nut cavities, one single-tool cut each, before the tooth cut.
    sk = fusion.new_sketch(ctx.comp, "ring nut cavity")
    fusion.draw_loop(sk, hexagon_loop(nut_pocket_flats()))
    profile = fusion.profile_with_loops(sk, 1, "ring nut_cavity_sketch", only=True)
    cavity = fusion.extrude(ctx, profile, 0.0, nut_cavity_height(), "ring nut_cavity_extrude")
    for cut_tool in _tool_instances(ctx, cavity, layout.nut_cavity_poses(p, d), "ring nut_cavity"):
        blank = fusion.cut(ctx, blank, [cut_tool], "ring nut_cavity_cut")
    ring = _require_solid(ctx, fusion.cut(ctx, blank, [tool], "ring ring_cut"))
    finish_face_edges(ctx, ring)
    return ring


def build_cover(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildCover] Frame with three windows and bolt holes, plus a bearing boss; then edge finishing on both faces."""
    p, d = ctx.p, ctx.d
    tv, wb = p.cover_thickness, d.bearing.width
    sk = fusion.new_sketch(ctx.comp, "cover frame")
    fusion.draw_circle(sk, (0.0, 0.0), d.ring_outer)
    fusion.draw_circle(sk, (0.0, 0.0), d.lip / 2)
    for c in bolt_hole_centers(d):
        fusion.draw_circle(sk, c, p.bolt_hole_diameter / 2)
    for loop in cover_window_loops(p, d):
        fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 9, "cover cover_frame_sketch")
    frame = fusion.extrude(ctx, profile, 0.0, tv, "cover cover_frame_extrude")

    sk = fusion.new_sketch(ctx.comp, "cover boss")
    fusion.draw_circle(sk, (0.0, 0.0), d.cover_boss / 2)
    fusion.draw_circle(sk, (0.0, 0.0), d.pocket / 2)
    profile = fusion.profile_with_loops(sk, 2, "cover cover_boss_sketch")
    boss = fusion.extrude(ctx, profile, tv - 1.0, wb + 1.0, "cover cover_boss_extrude")
    cover = fusion.join(ctx, frame, [boss], "cover cover_join")

    # [cutHeadPockets] Four round pockets for the bolt heads, one single-tool cut each, before the seat chamfer.
    sk = fusion.new_sketch(ctx.comp, "cover head pocket")
    fusion.draw_circle(sk, (0.0, 0.0), head_pocket_diameter() / 2)
    profile = fusion.profile_with_loops(sk, 1, "cover head_pocket_sketch", only=True)
    pocket = fusion.extrude(ctx, profile, tv - HEAD_HEIGHT, HEAD_HEIGHT + FASTENER_STOCK, "cover head_pocket_extrude")
    for cut_tool in _tool_instances(ctx, pocket, layout.head_pocket_poses(d), "cover head_pocket"):
        cover = fusion.cut(ctx, cover, [cut_tool], "cover head_pocket_cut")
    chamfer_seat(ctx, cover, tv + wb)
    finish_face_edges(ctx, cover)
    return _require_solid(ctx, cover)


def build_carrier(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildCarrier] Plate on the pin bosses, pins (with collars) down, keyed shaft hole; then the plate outline is
    chamfered on both faces."""
    p, d = ctx.p, ctx.d
    t, tc, g, n = p.gear_thickness, p.carrier_thickness, p.stage_gap, p.planet_count
    sk = fusion.new_sketch(ctx.comp, "carrier plate")
    fusion.draw_loop(sk, carrier_plate_outline(p, d))
    profile = fusion.profile_with_loops(sk, 1, "carrier plate_sketch", only=True)
    plate = fusion.extrude(ctx, profile, 0.0, tc, "carrier plate_extrude")

    sk = fusion.new_sketch(ctx.comp, "carrier pin")
    fusion.draw_circle(sk, (d.orbit, 0.0), d.pin / 2)
    profile = fusion.profile_with_loops(sk, 1, "carrier pin_sketch", only=True)
    pin = fusion.extrude(ctx, profile, -(t + g), t + g + tc / 2, "carrier pin_extrude")
    # [buildCarrier] The collar starts a pin-collar clearance above the lifted planet bearing.
    collar_start = -g + PLANET_BEARING_LIFT + PIN_COLLAR_CLEARANCE
    if g >= PLANET_BEARING_LIFT + PIN_COLLAR_CLEARANCE + PIN_COLLAR_THICKNESS:
        sk = fusion.new_sketch(ctx.comp, "carrier pin collar")
        fusion.draw_circle(sk, (d.orbit, 0.0), d.collar / 2)
        profile = fusion.profile_with_loops(sk, 1, "carrier pin_collar_sketch", only=True)
        collar = fusion.extrude(ctx, profile, collar_start, -collar_start + tc / 2, "carrier pin_collar_extrude")
        pin = fusion.join(ctx, pin, [collar], "carrier pin_join")
    pins = fusion.pattern(ctx, pin, n, "carrier pin_pattern") if n > 1 else [pin]
    carrier = fusion.join(ctx, plate, pins, "carrier carrier_join")
    hole = extrude_key_tool(ctx, "carrier", -1.0, tc + 2.0)
    carrier = _require_solid(ctx, fusion.cut(ctx, carrier, [hole], "carrier shaft_hole_cut"))
    finish_face_edges(ctx, carrier)
    return carrier


def build_shaft(ctx: BuildContext, spec: layout.ShaftSpec) -> adsk.fusion.BRepBody:
    """[buildShaft, keyCut] Round rod, optional collar, three keyway grooves cut over each groove span."""
    p, d = ctx.p, ctx.d
    what = ctx.part
    sk = fusion.new_sketch(ctx.comp, f"{what} rod")
    fusion.draw_circle(sk, (0.0, 0.0), d.shaft / 2)
    profile = fusion.profile_with_loops(sk, 1, f"{what} rod_sketch", only=True)
    rod = fusion.extrude(ctx, profile, spec.bottom, spec.top - spec.bottom, f"{what} rod_extrude")
    if spec.collar is not None:
        lo, hi = spec.collar
        sk = fusion.new_sketch(ctx.comp, f"{what} collar")
        fusion.draw_circle(sk, (0.0, 0.0), d.collar / 2)
        profile = fusion.profile_with_loops(sk, 1, f"{what} collar_sketch", only=True)
        collar = fusion.extrude(ctx, profile, lo, hi - lo, f"{what} collar_extrude")
        rod = fusion.join(ctx, rod, [collar], f"{what} collar_join")
    if p.key_depth > 0:
        boxes: list[adsk.fusion.BRepBody] = []
        a, b = key_box(p, d)
        for lo, hi in spec.grooves:
            sk = fusion.new_sketch(ctx.comp, f"{what} key box")
            fusion.draw_rectangle(sk, a, b)
            profile = fusion.profile_with_loops(sk, 1, f"{what} key_box_sketch", only=True)
            box = fusion.extrude(ctx, profile, lo, hi - lo, f"{what} key_box_extrude")
            boxes += fusion.pattern(ctx, box, 3, f"{what} key_box_pattern")
        rod = fusion.cut(ctx, rod, boxes, f"{what} keyway_cut")
    return _require_solid(ctx, rod)


def build_input_shaft(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return build_shaft(ctx, layout.input_shaft_spec(ctx.p, ctx.d))


def build_link_shaft(ctx: BuildContext) -> adsk.fusion.BRepBody:
    spec = layout.link_shaft_spec(ctx.p, ctx.d)
    if spec is None:
        raise fusion.BuildError("link_shaft does not exist with one stage")
    return build_shaft(ctx, spec)


def build_output_shaft(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return build_shaft(ctx, layout.output_shaft_spec(ctx.p, ctx.d))


def build_bolt(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw: revolved section, underhead fillet, hex socket."""
    comp = ctx.comp
    sk = fusion.new_sketch_xz(comp, "bolt section")
    fusion.draw_loop_xz(sk, bolt_section(FASTENER_LENGTH))
    body = fusion.revolve(ctx, fusion.profile_with_loops(sk, 1, "bolt section_sketch", only=True), "bolt revolve")
    edges = fusion.circular_edges_at(body, SHANK_DIAMETER / 2, 0.0)
    if len(edges) != 1:
        raise fusion.BuildError(f"bolt underhead_fillet: found {len(edges)} underhead edges, expected 1")
    fusion.fillet(ctx, edges, UNDERHEAD_RADIUS, "bolt underhead_fillet")

    sk = fusion.new_sketch(comp, "bolt socket")
    fusion.draw_loop(sk, hexagon_loop(SOCKET_ACROSS_FLATS))
    profile = fusion.profile_with_loops(sk, 1, "bolt socket_sketch", only=True)
    tool = fusion.extrude(ctx, profile, HEAD_HEIGHT - SOCKET_DEPTH, SOCKET_DEPTH + SOCKET_CUTTER_RISE,
                          "bolt socket_extrude")
    body = fusion.cut(ctx, body, [tool], "bolt socket_cut")
    return _require_solid(ctx, body)


def build_nut(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut: hexagon with a bore, then a revolved chamfer cut on each face."""
    comp = ctx.comp
    sk = fusion.new_sketch(comp, "nut hexagon")
    fusion.draw_loop(sk, hexagon_loop(NUT_ACROSS_FLATS))
    fusion.draw_circle(sk, (0.0, 0.0), NUT_BORE_DIAMETER / 2)
    profile = fusion.profile_with_loops(sk, 2, "nut hexagon_sketch")
    nut = fusion.extrude(ctx, profile, 0.0, NUT_THICKNESS, "nut hexagon_extrude")
    for side, upper in (("lower", False), ("upper", True)):
        sk = fusion.new_sketch_xz(comp, f"nut {side} chamfer")
        fusion.draw_loop_xz(sk, nut_chamfer_section(upper))
        profile = fusion.profile_with_loops(sk, 1, f"nut {side}_chamfer_sketch", only=True)
        tool = fusion.revolve(ctx, profile, f"nut {side}_chamfer_revolve")
        nut = fusion.cut(ctx, nut, [tool], f"nut {side}_chamfer_cut")
    return _require_solid(ctx, nut)
