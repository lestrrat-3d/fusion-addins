"""One builder per gallery part. Each builds at part-local coordinates (origin on the part's own axis) and returns the
finished, unposed body; build.py moves it once by its Pose.

Plate tools and the arbors' tools sit at model coordinates where the gallery builds them there: the plates' pose is the
identity, so their local frame is the model frame.
"""

from __future__ import annotations

import math
import typing

import adsk.fusion

from ...lib.gen import bearing, edgefinish, fasteners, gears, sections, spring
from ...lib.gen.constants import (
    ANCHOR_BORE_AT,
    ANCHOR_BORE_H,
    ANCHOR_COUNTER_FLOOR,
    ANCHOR_COUNTER_RADIUS,
    ANCHOR_COUNTER_TOP,
    ANCHOR_HIGH,
    ANCHOR_LOW,
    BACK_LOW,
    BACK_TOP,
    CAP_HIGH,
    CAP_LOW,
    CARRIER_BOSS_LENGTH,
    CARRIER_BOSS_LOW,
    CARRIER_BOSS_RADIUS,
    CARRIER_CORE_RADIUS,
    COLLAR_LENGTH,
    COLLAR_RADIUS,
    CRUTCH_HIGH,
    CRUTCH_LOW,
    CRUTCH_PIN_HIGH,
    CRUTCH_PIN_LOW,
    FRONT_LOW,
    FRONT_TOP,
    GREAT_BORE,
    GREAT_COUNTER_FLOOR,
    GREAT_COUNTER_LOW,
    GREAT_COUNTER_RADIUS,
    GREAT_LENGTH,
    GREAT_REAR,
    KEYED_COUNTER_LENGTH,
    KEYED_COUNTER_LOW,
    KNOB_HIGH,
    KNOB_LOW,
    KNOB_RADIUS,
    LAYER_LENGTH,
    LAYER_LOW,
    PENDULUM_HIGH,
    PENDULUM_LOW,
    PILLAR_HIGH,
    PILLAR_LOW,
    PILLAR_RADIUS,
    PINION_COUNTER_FLOOR,
    PINION_COUNTER_LOW,
    PINION_LENGTH,
    PINION_REAR,
    PLATE_THICK,
    POCKET_LOW,
    POCKET_RADIUS,
    PRESS_TOOL_LOW,
    RATCHET_DISC,
    RATCHET_FLOOR,
    RATCHET_TEETH,
    RATCHET_TOOL,
    ROOT_RADIUS,
    SEAT_DEPTH,
    SEAT_RADIUS,
    SPACER_HIGH,
    SPACER_LOW,
    SPRING_ANCHOR_HIGH,
    SPRING_ANCHOR_LOW,
    SPRING_ANCHOR_PIN_R,
    SPRING_HEIGHT,
    SPRING_SOCKET_HIGH,
    SPRING_SOCKET_LOW,
    SPRING_SOCKET_R,
    WHEEL_COUNTER_FLOOR,
    WHEEL_COUNTER_RADIUS,
    WHEEL_COUNTER_TOP,
    WHEEL_HIGH,
    WHEEL_LOW,
    BORE_TOOL_REACH,
    LIP_RADIUS,
    MOUNT_RADIUS,
)
from ...lib.gen.curves import Arc, Line, Loop
from ...lib.gen.pose import Pose
from ...lib.gen.involute import GearDims, is_embedded, root_contacts, tooth_section
from ...lib.gen.report import fmt_num
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

Pt = tuple[float, float]
_ORIGIN: Pt = (0.0, 0.0)
# A tool reaches this far past a face it opens (the gearbox's TOOL_MARGIN; the gallery's pressToolLow is 1.0 too).
TOOL_MARGIN = 1.0


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def disc(
    ctx: BuildContext, what: str, r: float, z0: float, z1: float, at: Pt = _ORIGIN
) -> adsk.fusion.BRepBody:
    """A round disc of radius r about `at`, extruded over z0 to z1 [discAt]."""
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_circle(sk, at, r)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.extrude(ctx, profile, z0, z1 - z0, f"{what}_extrude")


def _shift(loop: Loop, dx: float, dy: float) -> Loop:
    """The loop moved by (dx, dy). Lines and arcs only; a point shared by two curves stays shared."""
    out: list = []
    for c in loop:
        if isinstance(c, Line):
            out.append(Line((c.start[0] + dx, c.start[1] + dy), (c.end[0] + dx, c.end[1] + dy)))
        elif isinstance(c, Arc):
            out.append(Arc((c.center[0] + dx, c.center[1] + dy), (c.start[0] + dx, c.start[1] + dy),
                           (c.end[0] + dx, c.end[1] + dy)))
        else:
            raise fusion.BuildError("shift takes lines and arcs only")
    return out


def d_tool(
    ctx: BuildContext, what: str, z0: float, z1: float, at: Pt = _ORIGIN, d: sections.DFamily = sections.END_D
) -> adsk.fusion.BRepBody:
    """The D section of family d (arc radius, chord x; default the end press fit r2.55, x 2.05) about `at`, extruded
    over z0 to z1, flat on +X [dTool]."""
    loop = sections.d_section(d)
    if at != _ORIGIN:
        loop = _shift(loop, at[0], at[1])
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.extrude(ctx, profile, z0, z1 - z0, f"{what}_extrude")


def _bore_with_d(
    ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, z0: float, z1: float, at: Pt = _ORIGIN,
    d: sections.DFamily = sections.END_D,
):
    """Cut the D bore of family d over z0 to z1 out of body."""
    return fusion.cut(ctx, body, [d_tool(ctx, f"{what} bore", z0, z1, at, d)], f"{what} bore_cut")


def _keyed_counterbore(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, at: Pt = _ORIGIN):
    """Cut the keyed D counterbore of a crutch or knob [keyedCounterbore]."""
    tool = d_tool(
        ctx, what, KEYED_COUNTER_LOW, KEYED_COUNTER_LOW + KEYED_COUNTER_LENGTH, at, sections.KEYED_COUNTER_D
    )
    return fusion.cut(ctx, body, [tool], f"{what}_cut")


def finish_face_edges(ctx: BuildContext, body: adsk.fusion.BRepBody) -> None:
    """Surface edge finishing [edgefinish.go finishFaceEdges]: one equal-distance chamfer feature per plane of
    edgefinish.finish_planes, on the loops its rule keeps, by edgefinish.CHAMFER."""
    centres = sections.lip_centres(ctx.g)
    for fp in edgefinish.finish_planes(ctx.part):
        step = f"{ctx.part} edge_chamfer z={fmt_num(fp.z)}"
        loops = fusion.flat_face_loops(body, fp.z, edgefinish.LARGE_FACE_AREA, step)
        rim_centres = centres if fp.rule == edgefinish.PLATE else [_ORIGIN]
        kept = [
            edges
            for outer, edges, circle, start, length in loops
            if edgefinish.keep_loop(fp.rule, outer, len(edges), circle, start, rim_centres, fp.radii, length)
        ]
        if not kept:
            raise fusion.BuildError(f"{step}: no loop to chamfer")
        # Deviation: one chamfer feature per plane, not one call for both (decad cannot chamfer a body twice), and the
        # kept-loop count must equal the gallery's (Fusion may split edges differently); see
        # docs/escapement/deviations.md.
        if len(kept) != fp.loops:
            raise fusion.BuildError(f"{step}: found {len(kept)} loops to chamfer, expected {fp.loops}")
        # Exactly the kept edges, like the gallery's Exactly(count) selection: no tangent chain.
        fusion.chamfer(ctx, [e for edges in kept for e in edges], edgefinish.CHAMFER, step, tangent_chain=False)
        if not body.isSolid:
            raise fusion.BuildError(f"{step}: chamfered result is not a solid")


def build_spur(
    ctx: BuildContext, what: str, gd: GearDims, z0: float, thickness: float, bore: float
) -> adsk.fusion.BRepBody:
    """Tooth section + root disc extrude, circular pattern, join, root fillet, round bore cut [spurgear assemble].

    There is no fillet ladder: Fusion rejecting the root fillet raises BuildError and stops the build (owner decision,
    docs/escapement/directives.md)."""
    comp, n, samples = ctx.comp, gd.teeth, gears.SAMPLES

    def w(step: str) -> str:
        return f"{what} {step}"

    sk = fusion.new_sketch(comp, f"{what} tooth")
    fusion.draw_loop(sk, tooth_section(gd, samples))
    tooth = fusion.extrude(ctx, fusion.profile_with_loops(sk, 1, w("tooth_sketch"), only=True), z0, thickness,
                           w("tooth_extrude"))
    root = disc(ctx, w("root_disc"), gd.root, z0, z0 + thickness)
    teeth = fusion.pattern(ctx, tooth, n, w("pattern"))
    gear = fusion.join(ctx, root, teeth, w("join"))

    if gd.fillet > 0:
        if is_embedded(gd):
            edges = fusion.concave_axial_edges(gear)
        else:
            edges = fusion.axial_edges_at(gear, root_contacts(gd, samples))
        if len(edges) != 2 * n:
            raise fusion.BuildError(f"{w('root_fillet')}: found {len(edges)} root edges, expected {2 * n}")
        fusion.fillet(ctx, edges, gd.fillet, w("root_fillet"))

    if bore > 0:
        tool = disc(ctx, w("bore"), bore / 2, z0 - TOOL_MARGIN, z0 + thickness + TOOL_MARGIN)
        gear = fusion.cut(ctx, gear, [tool], w("bore_cut"))
    return gear


def _cut_tools(ctx: BuildContext, body: adsk.fusion.BRepBody, tools: list, what: str) -> adsk.fusion.BRepBody:
    # Deviation: every tool is removed by one combine cut that takes all of them as tool bodies. The gallery unions
    # the tools first; a join of tools that do not touch would not give one body (docs/escapement/deviations.md).
    return fusion.cut(ctx, body, tools, what)


def _seat_tools(ctx: BuildContext, z0: float) -> list[adsk.fusion.BRepBody]:
    return [
        disc(ctx, f"{ctx.part} seat {i + 1}", SEAT_RADIUS, z0, z0 + SEAT_DEPTH, at)
        for i, at in enumerate(sections.lip_centres(ctx.g))
    ]


def _site_tools(
    ctx: BuildContext, name: str, radius: float, span: tuple[float, float]
) -> list[adsk.fusion.BRepBody]:
    return [
        disc(ctx, f"{ctx.part} {name} {i + 1}", radius, span[0], span[1], at)
        for i, at in enumerate(fasteners.PILLARS)
    ]


def _plate_outline(ctx: BuildContext, what: str, top: float, z0: float, mounts: tuple[Pt, ...]):
    """Outline, both windows, the three lip bores and the mount holes as one sketch, extruded PLATE_THICK from z0."""
    g = ctx.g
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_loop(sk, sections.plate_outline(top))
    fusion.draw_loop(sk, sections.window_loop(g, 1.0))
    fusion.draw_loop(sk, sections.window_loop(g, -1.0))
    for c in sections.lip_centres(g):
        fusion.draw_circle(sk, c, LIP_RADIUS)
    for c in mounts:
        fusion.draw_circle(sk, c, MOUNT_RADIUS)
    profile = fusion.profile_with_loops(sk, 2 + 3 + len(mounts) + 1, f"{what}_sketch")
    return fusion.extrude(ctx, profile, z0, PLATE_THICK, f"{what}_extrude")


def build_back_plate(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildBackPlate] Outline with windows and holes, four pillars, then seats, bolt holes and nut cavities."""
    plate = _plate_outline(ctx, "back_plate outline", BACK_TOP, BACK_LOW, sections.MOUNT_HOLES)
    posts = [
        disc(ctx, f"back_plate pillar {i + 1}", PILLAR_RADIUS, PILLAR_LOW, PILLAR_HIGH, at)
        for i, at in enumerate(fasteners.PILLARS)
    ]
    plate = fusion.join(ctx, plate, posts, "back_plate pillars_join")
    tools = _seat_tools(ctx, BACK_LOW + 1)
    tools += _site_tools(ctx, "hole", fasteners.HOLE_RADIUS, fasteners.hole_span())
    tools += _site_tools(ctx, "cavity", fasteners.NUT_CAVITY_RADIUS, fasteners.cavity_span())
    plate = _cut_tools(ctx, plate, tools, "back_plate tools_cut")
    finish_face_edges(ctx, plate)
    return _require_solid(ctx, plate)


def build_front_plate(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildFrontPlate] Outline with windows and holes, then seats, bolt holes, head pockets, the suspension D socket
    and the spring anchor socket."""
    g = ctx.g
    plate = _plate_outline(ctx, "front_plate outline", FRONT_TOP, FRONT_LOW, ())
    tools = _seat_tools(ctx, FRONT_LOW - 1)
    tools += _site_tools(ctx, "hole", fasteners.HOLE_RADIUS, fasteners.hole_span())
    tools += _site_tools(ctx, "pocket", fasteners.HEAD_POCKET_RADIUS, fasteners.pocket_tool_span())
    tools.append(d_tool(ctx, "front_plate suspension_socket", 31.0, 35.0, g.axis_s))
    tools.append(
        disc(ctx, "front_plate anchor_socket", SPRING_SOCKET_R, SPRING_SOCKET_LOW, SPRING_SOCKET_HIGH, g.spring_anchor)
    )
    plate = _cut_tools(ctx, plate, tools, "front_plate tools_cut")
    finish_face_edges(ctx, plate)
    return _require_solid(ctx, plate)


def _arbor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[arbor] Revolve the stair meridian about the Z axis, then cut the flat boxes over their z spans."""
    part = ctx.part
    sk = fusion.new_sketch_xz(ctx.comp, f"{part} meridian")
    fusion.draw_loop_xz(sk, sections.arbor_meridian(part))
    profile = fusion.profile_with_loops(sk, 1, f"{part} meridian_sketch", only=True)
    body = fusion.revolve(ctx, profile, f"{part} revolve")
    boxes = []
    for i, (flat_x, lo, hi) in enumerate(sections.ARBOR_FLATS[part]):
        a, b = sections.flat_box(flat_x)
        sk = fusion.new_sketch(ctx.comp, f"{part} flat box {i + 1}")
        fusion.draw_rectangle(sk, a, b)
        profile = fusion.profile_with_loops(sk, 1, f"{part} flat_box_sketch", only=True)
        boxes.append(fusion.extrude(ctx, profile, lo, hi - lo, f"{part} flat_box_extrude"))
    body = _cut_tools(ctx, body, boxes, f"{part} flats_cut")
    return _require_solid(ctx, body)


def build_escape_arbor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return _arbor(ctx)


def build_pallet_arbor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return _arbor(ctx)


def build_great_wheel_arbor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return _arbor(ctx)


def build_suspension_pin(ctx: BuildContext) -> adsk.fusion.BRepBody:
    return _arbor(ctx)


def build_escape_wheel(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildEscapeWheel] Root disc with six windows, tooth 0 patterned 30 times, the front counterbore, window and
    counterbore rim chamfers, then the pinion (turned to its phase), and the D bore joined with the rear counterbore."""
    g, comp = ctx.g, ctx.comp
    sk = fusion.new_sketch(comp, "escape_wheel disc")
    fusion.draw_circle(sk, _ORIGIN, ROOT_RADIUS)
    for loop in sections.escape_windows():
        fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 7, "escape_wheel disc_sketch")
    wheel = fusion.extrude(ctx, profile, WHEEL_LOW, WHEEL_HIGH - WHEEL_LOW, "escape_wheel disc_extrude")

    sk = fusion.new_sketch(comp, "escape_wheel tooth")
    fusion.draw_loop(sk, sections.escape_tooth(g))
    profile = fusion.profile_with_loops(sk, 1, "escape_wheel tooth_sketch", only=True)
    tooth = fusion.extrude(ctx, profile, WHEEL_LOW, WHEEL_HIGH - WHEEL_LOW, "escape_wheel tooth_extrude")
    teeth = fusion.pattern(ctx, tooth, 30, "escape_wheel tooth_pattern")
    wheel = fusion.join(ctx, wheel, teeth, "escape_wheel teeth_join")
    front = disc(ctx, "escape_wheel front_counterbore", WHEEL_COUNTER_RADIUS, WHEEL_COUNTER_FLOOR, WHEEL_COUNTER_TOP)
    wheel = fusion.cut(ctx, wheel, [front], "escape_wheel front_counterbore_cut")
    finish_face_edges(ctx, wheel)

    pinion = build_spur(ctx, "escape_wheel pinion", gears.pinion_dims(ctx.p), PINION_REAR, PINION_LENGTH, 0.0)
    # The pinion is built with tooth 0 on +X, then turned to the gallery's phase.
    fusion.move(ctx, pinion, Pose(angle=g.pinion_phase), "escape_wheel pinion_turn")
    part = fusion.join(ctx, wheel, [pinion], "escape_wheel part_join")
    bore = d_tool(
        ctx, "escape_wheel bore", -BORE_TOOL_REACH, WHEEL_HIGH + BORE_TOOL_REACH + 1, d=sections.BODY_D
    )
    rear = disc(ctx, "escape_wheel rear_counterbore", WHEEL_COUNTER_RADIUS, PINION_COUNTER_LOW, PINION_COUNTER_FLOOR)
    tool = fusion.join(ctx, bore, [rear], "escape_wheel bore_tool_join")
    part = fusion.cut(ctx, part, [tool], "escape_wheel bore_cut")
    return _require_solid(ctx, part)


def build_anchor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildAnchor] The 14-piece outline, the front counterbore, the D bore, then the outline and counterbore rim
    chamfers."""
    sk = fusion.new_sketch(ctx.comp, "anchor outline")
    fusion.draw_loop(sk, sections.anchor_outline(ctx.g))
    profile = fusion.profile_with_loops(sk, 1, "anchor outline_sketch", only=True)
    body = fusion.extrude(ctx, profile, ANCHOR_LOW, ANCHOR_HIGH - ANCHOR_LOW, "anchor outline_extrude")
    counter = disc(ctx, "anchor counterbore", ANCHOR_COUNTER_RADIUS, ANCHOR_COUNTER_FLOOR, ANCHOR_COUNTER_TOP)
    body = fusion.cut(ctx, body, [counter], "anchor counterbore_cut")
    body = _bore_with_d(ctx, body, "anchor", ANCHOR_BORE_AT, ANCHOR_BORE_AT + ANCHOR_BORE_H, d=sections.BODY_D)
    finish_face_edges(ctx, body)
    return _require_solid(ctx, body)


def build_crutch(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildCrutch] Hub, arm and round end, the pin on its end, the keyed D counterbore and the D socket."""
    sk = fusion.new_sketch(ctx.comp, "crutch outline")
    fusion.draw_loop(sk, sections.crutch_outline(ctx.g))
    profile = fusion.profile_with_loops(sk, 1, "crutch outline_sketch", only=True)
    body = fusion.extrude(ctx, profile, CRUTCH_LOW, CRUTCH_HIGH - CRUTCH_LOW, "crutch outline_extrude")
    centre, radius = sections.CRUTCH_PIN
    pin = disc(ctx, "crutch pin", radius, CRUTCH_PIN_LOW, CRUTCH_PIN_HIGH, centre)
    body = fusion.join(ctx, body, [pin], "crutch pin_join")
    body = _keyed_counterbore(ctx, body, "crutch counterbore")
    body = _bore_with_d(ctx, body, "crutch", CRUTCH_LOW - PRESS_TOOL_LOW, CRUTCH_HIGH + PRESS_TOOL_LOW)
    return _require_solid(ctx, body)


def build_pendulum(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildPendulum] Eye, rod and bob with a lip bore and the crutch slot, the bearing pocket, then rim chamfers."""
    sk = fusion.new_sketch(ctx.comp, "pendulum outline")
    fusion.draw_loop(sk, sections.pendulum_outline(ctx.g))
    fusion.draw_circle(sk, _ORIGIN, LIP_RADIUS)
    fusion.draw_loop(sk, sections.crutch_slot())
    profile = fusion.profile_with_loops(sk, 3, "pendulum outline_sketch")
    body = fusion.extrude(ctx, profile, PENDULUM_LOW, PENDULUM_HIGH - PENDULUM_LOW, "pendulum outline_extrude")
    pocket = disc(ctx, "pendulum pocket", POCKET_RADIUS, POCKET_LOW, POCKET_LOW + 6.0)
    body = fusion.cut(ctx, body, [pocket], "pendulum pocket_cut")
    finish_face_edges(ctx, body)
    return _require_solid(ctx, body)


def build_suspension_cap(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildCap] A disc on the pin's front peg with a D socket."""
    body = disc(ctx, "suspension_cap disc", COLLAR_RADIUS, CAP_LOW, CAP_HIGH)
    body = _bore_with_d(ctx, body, "suspension_cap", CAP_LOW - PRESS_TOOL_LOW, CAP_HIGH + PRESS_TOOL_LOW)
    return _require_solid(ctx, body)


def build_great_wheel(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildGreatWheel] The 48-tooth gear with its round bore, the rear counterbore with its rim chamfer, then the
    internal ratchet cut."""
    wheel = build_spur(ctx, "great_wheel", gears.great_dims(ctx.p), GREAT_REAR, GREAT_LENGTH, GREAT_BORE)
    counter = disc(ctx, "great_wheel counterbore", GREAT_COUNTER_RADIUS, GREAT_COUNTER_LOW, GREAT_COUNTER_FLOOR)
    wheel = fusion.cut(ctx, wheel, [counter], "great_wheel counterbore_cut")
    finish_face_edges(ctx, wheel)
    disc_tool = disc(ctx, "great_wheel ratchet disc", RATCHET_DISC, RATCHET_FLOOR, RATCHET_FLOOR + RATCHET_TOOL)
    sk = fusion.new_sketch(ctx.comp, "great_wheel ratchet tooth")
    fusion.draw_loop(sk, sections.ratchet_triangle())
    profile = fusion.profile_with_loops(sk, 1, "great_wheel ratchet_tooth_sketch", only=True)
    tooth = fusion.extrude(ctx, profile, RATCHET_FLOOR, RATCHET_TOOL, "great_wheel ratchet_tooth_extrude")
    teeth = fusion.pattern(ctx, tooth, RATCHET_TEETH, "great_wheel ratchet_pattern")
    tool = fusion.join(ctx, disc_tool, teeth, "great_wheel ratchet_join")
    wheel = fusion.cut(ctx, wheel, [tool], "great_wheel ratchet_cut")
    return _require_solid(ctx, wheel)


def build_pawl_carrier(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildPawlCarrier] Core, two pawls, a short boss in front, and the D bore."""
    core = disc(ctx, "pawl_carrier core", CARRIER_CORE_RADIUS, LAYER_LOW, LAYER_LOW + LAYER_LENGTH)
    rest = []
    for j, gang in enumerate((math.pi / 2 - ctx.g.carrier_offset, 3 * math.pi / 2 - ctx.g.carrier_offset)):
        sk = fusion.new_sketch(ctx.comp, f"pawl_carrier pawl {j + 1}")
        fusion.draw_loop(sk, sections.pawl_loop(gang))
        profile = fusion.profile_with_loops(sk, 1, f"pawl_carrier pawl_{j + 1}_sketch", only=True)
        rest.append(fusion.extrude(ctx, profile, LAYER_LOW, LAYER_LENGTH, f"pawl_carrier pawl_{j + 1}_extrude"))
    rest.append(
        disc(ctx, "pawl_carrier boss", CARRIER_BOSS_RADIUS, CARRIER_BOSS_LOW, CARRIER_BOSS_LOW + CARRIER_BOSS_LENGTH)
    )
    body = fusion.join(ctx, core, rest, "pawl_carrier parts_join")
    body = _bore_with_d(ctx, body, "pawl_carrier", LAYER_LOW - 1.0, LAYER_LOW - 1.0 + 7.75, d=sections.DRIVE_D)
    return _require_solid(ctx, body)


def build_mainspring(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildMainspring, spiralspring Build] The spring profile (outer loop, D bore, eye hole) extruded over its
    height, the five concave edges filleted, then the outer-loop chamfers."""
    sp = spring.spring_params()
    dm = ctx.g.spring
    outer, bore, eye = spring.profile(sp, dm)
    sk = fusion.new_sketch(ctx.comp, "mainspring profile")
    fusion.draw_loop(sk, outer)
    fusion.draw_loop(sk, bore)
    fusion.draw_circle(sk, eye.center, eye.radius)
    profile = fusion.profile_with_loops(sk, 3, "mainspring profile_sketch")
    body = fusion.extrude(ctx, profile, 0.0, SPRING_HEIGHT, "mainspring extrude")
    edges = fusion.axial_edges_at(body, spring.fillet_corners(sp, dm))
    if len(edges) != 5:
        raise fusion.BuildError(f"mainspring fillet: found {len(edges)} concave edges, expected 5")
    fusion.fillet(ctx, edges, dm.fillet_radius, "mainspring fillet")
    finish_face_edges(ctx, body)
    return _require_solid(ctx, body)


def build_spring_spacer(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildSpringSpacer] A pressed tube from the spring hub's front face to the front bearing."""
    body = disc(ctx, "spring_spacer disc", COLLAR_RADIUS, SPACER_LOW, SPACER_HIGH)
    body = _bore_with_d(ctx, body, "spring_spacer", SPACER_LOW - 1.0, SPACER_HIGH + 1.0, d=sections.BODY_D)
    return _require_solid(ctx, body)


def build_spring_anchor_pin(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildSpringAnchorPin] The round rod that carries the spring's eye, about its own axis."""
    body = disc(ctx, "spring_anchor_pin disc", SPRING_ANCHOR_PIN_R, SPRING_ANCHOR_LOW, SPRING_ANCHOR_HIGH)
    return _require_solid(ctx, body)


def build_winding_knob(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildKnob] A disc with a keyed D counterbore and a D socket."""
    body = disc(ctx, "winding_knob disc", KNOB_RADIUS, KNOB_LOW, KNOB_HIGH)
    body = _keyed_counterbore(ctx, body, "winding_knob counterbore")
    body = _bore_with_d(ctx, body, "winding_knob", KNOB_LOW - PRESS_TOOL_LOW, KNOB_HIGH + PRESS_TOOL_LOW)
    return _require_solid(ctx, body)


def build_arbor_collar(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildCollarRing] A ring of the collar radius with the body-family D bore, local z 0 to 3."""
    body = disc(ctx, "arbor_collar ring", COLLAR_RADIUS, 0.0, COLLAR_LENGTH)
    body = _bore_with_d(ctx, body, "arbor_collar", -PRESS_TOOL_LOW, COLLAR_LENGTH + PRESS_TOOL_LOW, d=sections.BODY_D)
    return _require_solid(ctx, body)


def build_end_collar(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildKeyedRing] A keyed D ring (arc r 3.7, chord x 3.3) with the end-family D bore, local z 0 to 3."""
    body = d_tool(ctx, "end_collar ring", 0.0, COLLAR_LENGTH, d=sections.KEYED_RING_D)
    body = _bore_with_d(ctx, body, "end_collar", -PRESS_TOOL_LOW, COLLAR_LENGTH + PRESS_TOOL_LOW)
    return _require_solid(ctx, body)


def build_bearing(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[ballbearing Build] The 605ZZ envelope: a ring from the bore to the outer diameter, local z 0 to the width."""
    b = bearing.bearing_605zz()
    sk = fusion.new_sketch(ctx.comp, f"{ctx.part} ring")
    fusion.draw_circle(sk, _ORIGIN, b.outer_diameter / 2)
    fusion.draw_circle(sk, _ORIGIN, b.bore_diameter / 2)
    profile = fusion.profile_with_loops(sk, 2, f"{ctx.part} bearing_sketch")
    body = fusion.extrude(ctx, profile, 0.0, b.width, f"{ctx.part} bearing_extrude")
    return _require_solid(ctx, body)


def build_bolt(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw: revolved section, underhead fillet, hex socket."""
    comp = ctx.comp
    sk = fusion.new_sketch_xz(comp, "bolt section")
    fusion.draw_loop_xz(sk, fasteners.bolt_section(fasteners.BOLT_LENGTH))
    body = fusion.revolve(ctx, fusion.profile_with_loops(sk, 1, "bolt section_sketch", only=True), "bolt revolve")
    edges = fusion.circular_edges_at(body, fasteners.SHANK_DIAMETER / 2, 0.0)
    if len(edges) != 1:
        raise fusion.BuildError(f"bolt underhead_fillet: found {len(edges)} underhead edges, expected 1")
    fusion.fillet(ctx, edges, fasteners.UNDERHEAD_RADIUS, "bolt underhead_fillet")

    sk = fusion.new_sketch(comp, "bolt socket")
    fusion.draw_loop(sk, fasteners.hexagon_loop(fasteners.SOCKET_ACROSS_FLATS))
    profile = fusion.profile_with_loops(sk, 1, "bolt socket_sketch", only=True)
    tool = fusion.extrude(
        ctx,
        profile,
        fasteners.HEAD_HEIGHT - fasteners.SOCKET_DEPTH,
        fasteners.SOCKET_DEPTH + fasteners.SOCKET_CUTTER_RISE,
        "bolt socket_extrude",
    )
    body = fusion.cut(ctx, body, [tool], "bolt socket_cut")
    return _require_solid(ctx, body)


def build_nut(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut: hexagon with a bore, then a revolved chamfer cut on each face."""
    comp = ctx.comp
    sk = fusion.new_sketch(comp, "nut hexagon")
    fusion.draw_loop(sk, fasteners.hexagon_loop(fasteners.NUT_ACROSS_FLATS))
    fusion.draw_circle(sk, _ORIGIN, fasteners.NUT_BORE_DIAMETER / 2)
    profile = fusion.profile_with_loops(sk, 2, "nut hexagon_sketch")
    nut = fusion.extrude(ctx, profile, 0.0, fasteners.NUT_THICKNESS, "nut hexagon_extrude")
    for side, upper in (("lower", False), ("upper", True)):
        sk = fusion.new_sketch_xz(comp, f"nut {side} chamfer")
        fusion.draw_loop_xz(sk, fasteners.nut_chamfer_section(upper))
        profile = fusion.profile_with_loops(sk, 1, f"nut {side}_chamfer_sketch", only=True)
        tool = fusion.revolve(ctx, profile, f"nut {side}_chamfer_revolve")
        nut = fusion.cut(ctx, nut, [tool], f"nut {side}_chamfer_cut")
    return _require_solid(ctx, nut)
