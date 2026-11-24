"""The click indexer's bodies: hub, rotor, housing, button and spring.

Same scheme as `parts.py`: each body is built in its own local frame (its axis on local +Z, see
`lib/gen/clicker_params.py`) at the component origin, then moved once onto its frame in the model. The hub, the rotor and
the spring turn with the shaft by theta; the housing and the button do not.

`build_clicker_part(ctx, name)` builds one body in `ctx.comp`; `CLICKER_PART_NAMES` lists the names it takes. The
dispatch in `parts.build_part` calls it for these names.

# Deviation: no decad `Coil` in Fusion; the face teeth and the spring are built another way
(docs/sevensegment/deviations.md, "Click indexer"). Nothing here has been run in Fusion.
"""

from __future__ import annotations

import math
import typing

import adsk.fusion

from ...lib.gen import bodies, poses
from ...lib.gen import clicker_params as cp
from ...lib.gen import clicker_teeth as ct
from ...lib.gen.curves import Loop
from . import fusion, fusion_clicker as fc

if typing.TYPE_CHECKING:
    from .build import BuildContext

CLICKER_PART_NAMES: tuple[str, ...] = (bodies.HUB, bodies.ROTOR, bodies.HOUSING, bodies.BUTTON, bodies.SPRING)

SPRING_SECTIONS_PER_TURN = 8
_TEETH_COUNT = cp.CLICKER_STEPS


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _prism(ctx: BuildContext, what: str, loop: Loop, z0: float, length: float) -> adsk.fusion.BRepBody:
    """The closed loop on the XY plane, extruded from z0 for length along +Z."""
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")


def _cut_loops(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, loops: list[Loop], z0: float,
               length: float) -> adsk.fusion.BRepBody:
    """Cut `body` with the closed `loops` (separate outlines, one profile each) in one sketch extruded from z0 for
    length along +Z, as one feature [cutKeySlots]."""
    sk = fusion.new_sketch(ctx.comp, f"{what} tool")
    for loop in loops:
        fusion.draw_loop(sk, loop)
    profiles = fusion.profiles_with_loops(sk, 1, len(loops), f"{what} tool_sketch")
    return fusion.cut_extrude(ctx, profiles, body, z0, length, what)


def _turned(ctx: BuildContext, what: str, section: Loop) -> adsk.fusion.BRepBody:
    """A (radius, z) section revolved a full turn about the Z axis."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    fusion.draw_loop_xz(sk, section)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.revolve(ctx, profile, f"{what}_revolve")


def _radial_box(ctx: BuildContext, what: str, r0: float, r1: float, w: float, z0: float, z1: float,
                angle: float) -> adsk.fusion.BRepBody:
    """[localBox] A box on the radius r0 to r1, w wide, over local z z0 to z1, turned by angle degrees."""
    return _prism(ctx, what, cp.radial_box_loop(r0, r1, w, angle), z0, z1 - z0)


def _face_teeth(ctx: BuildContext, body: adsk.fusion.BRepBody, ft: ct.FaceTeeth, shift: float,
                what: str) -> adsk.fusion.BRepBody:
    """[faceTeethBodies, joinTeeth] Join the ring of ten teeth `ft`, tooth 0 turned by `shift`, into `body`.

    # Deviation: tooth 0 is the intersection of two twisted prisms, one holding the rising ramp and one the falling
    ramp, instead of a partial revolve cut by two `Coil` tools; the ten teeth are a circular pattern of it. Both start
    at the valley plane z = 0 (the gallery's blank starts 0.01 above it), so the tooth's walls and the plate's top meet
    the way the gallery's do: the plate's top lies `ft.plate` above the valley and buries the bottoms
    (docs/sevensegment/deviations.md)."""
    top = ft.top
    path = fc.axis_path(ctx, top, f"{what} path")
    (rise_loop, rise_twist), (fall_loop, fall_twist) = ct.sweeps(ft, shift)
    prisms = []
    for label, loop, twist, rising in (("rising", rise_loop, rise_twist, True), ("falling", fall_loop, fall_twist, False)):
        sk = fusion.new_sketch(ctx.comp, f"{what} {label} sector")
        fusion.draw_loop(sk, loop)
        profile = fusion.profile_with_loops(sk, 1, f"{what} {label} sector_sketch", only=True)
        prisms.append(fc.twisted_prism(ctx, profile, path, top, twist, ct.cap_angle(ft, shift, rising),
                                       f"{what} {label} prism"))
    tooth = fc.intersect(ctx, prisms[0], prisms[1], f"{what} tooth")
    teeth = fc.pattern(ctx, tooth, _TEETH_COUNT, f"{what} teeth")
    return fusion.join(ctx, body, teeth, f"{what} join teeth")


def _outer_chamfer(ctx: BuildContext, body: adsk.fusion.BRepBody, z: float, what: str) -> None:
    """Chamfer the outer loop of the large planar face at local z by CHAMFER."""
    found = [es for is_outer, es in fusion.face_loops(body, z, 100.0, f"{what} z={z:g}") if is_outer]
    if len(found) != 1:
        raise fusion.BuildError(f"{what}: found {len(found)} outer loops at z={z:g}, expected 1")
    fusion.chamfer(ctx, found[0], cp.CHAMFER, f"{what} chamfer z={z:g}", tangent_chain=False)


def build_hub(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[hub] Revolve the cup and base, join the three keys, cut the stub's D bore through the base; move it onto its
    frame, turned by theta."""
    what = ctx.part
    body = _turned(ctx, f"{what} meridian", cp.hub_meridian())
    z0, z1 = cp.hub_key_span()
    keys = [_radial_box(ctx, f"{what} key {i + 1}", cp.HUB_KEY_INNER, cp.HUB_WALL_INNER + 0.5, cp.HUB_KEY_WIDTH, z0, z1,
                        cp.key_angle(i)) for i in range(cp.HUB_KEY_COUNT)]
    body = fusion.join(ctx, body, keys, f"{what} join keys")
    body = _cut_loops(ctx, body, f"{what} cut D bore", [cp.d_bore_loop(cp.BORE_STUB_RADIUS, cp.BORE_STUB_FLAT)], -1.0,
                      cp.HUB_BASE_LENGTH + 2.0)
    body = fusion.move(ctx, body, cp.hub_axes(ctx.dm.theta), f"{what} move")
    return _require_solid(ctx, body)


def build_rotor(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[rotor] Revolve the skirt and plate, chamfer the plate's underside rim, cut the three key slots, join the inner
    and the outer face teeth; move it onto its frame, turned by theta."""
    what = ctx.part
    inner, outer = ct.rotor_inner_teeth(), ct.rotor_outer_teeth()
    body = _turned(ctx, f"{what} meridian", cp.rotor_meridian(inner.plate))  # one root land under both rings
    _outer_chamfer(ctx, body, cp.rotor_skirt_top(), what)
    z0, z1 = cp.rotor_slot_span()
    slots = [cp.radial_box_loop(cp.ROTOR_SLOT_FLOOR, cp.ROTOR_SKIRT_OUTER + 0.5, cp.ROTOR_SLOT_WIDTH, cp.key_angle(i))
             for i in range(cp.HUB_KEY_COUNT)]
    body = _cut_loops(ctx, body, f"{what} cut slots", slots, z0, z1 - z0)
    body = _face_teeth(ctx, body, inner, ct.ROTOR_INNER_SHIFT, f"{what} inner")
    body = _face_teeth(ctx, body, outer, ct.ROTOR_OUTER_SHIFT, f"{what} outer")
    body = fusion.move(ctx, body, cp.rotor_axes(ctx.dm.theta), f"{what} move")
    return _require_solid(ctx, body)


def build_housing(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[housing] Revolve the flange, tube, bezel and crown ring, cut the three lug slots, join the crown's teeth,
    cut the two H bolts' clearance holes and head pockets; move it onto its frame (it does not turn)."""
    from . import parts  # the fastener tools of the walls (m2fastener HoleTool, PocketTool)

    what = ctx.part
    crown = ct.crown_teeth()
    body = _turned(ctx, f"{what} meridian", cp.housing_meridian(crown.plate))
    z0, z1 = cp.housing_slot_span()
    slots = [cp.radial_box_loop(cp.HOUSING_CROWN_R0 - 0.5, cp.HOUSING_SLOT_OUTER, cp.HOUSING_SLOT_WIDTH, cp.key_angle(i))
             for i in range(cp.HUB_KEY_COUNT)]
    body = _cut_loops(ctx, body, f"{what} cut slots", slots, z0, z1 - z0)
    body = _face_teeth(ctx, body, crown, ct.CROWN_SHIFT, f"{what} crown")
    axes = cp.housing_axes()
    for index in (8, 9):  # the H sites
        label = bodies.SITE_LABELS[index]
        site = poses.site_in(ctx.dm.sites[index], axes)
        for tool in (parts._hole(ctx, site, f"{what} {label} hole tool"),
                     parts._head_pocket(ctx, site, f"{what} {label} head pocket tool")):
            body = fusion.cut(ctx, body, [tool], f"{what} cut {label}")
    body = fusion.move(ctx, body, axes, f"{what} move")
    return _require_solid(ctx, body)


def build_button(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[button] Revolve the head with its recess, join the three keys (two boxes each) to the plain head, then join
    the face teeth, in the gallery's order; move it onto its frame (it does not turn)."""
    what = ctx.part
    teeth = ct.button_teeth()
    body = _turned(ctx, f"{what} meridian", cp.button_meridian(teeth.plate))
    for i in range(cp.HUB_KEY_COUNT):
        boxes = [_radial_box(ctx, f"{what} key {i + 1} part {j + 1}", r0, r1, cp.BUTTON_KEY_WIDTH, z0, z1,
                             cp.key_angle(i)) for j, (r0, r1, z0, z1) in enumerate(cp.button_key_boxes())]
        body = fusion.join(ctx, body, boxes, f"{what} join key {i + 1}")
    body = _face_teeth(ctx, body, teeth, ct.BUTTON_SHIFT, what)
    body = fusion.move(ctx, body, cp.button_axes(), f"{what} move")
    return _require_solid(ctx, body)


def build_spring(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[spring, compressionspring.Build] The KSSC 1087 at SPRING_REST_LENGTH: a round wire on a constant-pitch helix,
    6.5 turns, centreline radius 3.2, about the local Z axis; moved onto its frame, turned by theta.

    # Deviation: the gallery sweeps the wire with `decad.Coil`. Fusion's `CoilFeatures` cannot be created from an add-in
    and a swept helix needs a wire body that would stay in the component as an extra body, so the wire is a loft
    through its meridian circles, one every 45 degrees (docs/sevensegment/deviations.md)."""
    what = ctx.part
    radius = cp.SPRING_WIRE_DIAMETER / 2
    planes: dict[float, object] = {}
    profiles = []
    for i, (angle, z, r) in enumerate(cp.spring_sections(cp.SPRING_REST_LENGTH, SPRING_SECTIONS_PER_TURN)):
        # Angle and angle + 180 share one plane through the axis.
        turn = angle % 180.0
        if turn not in planes:
            planes[turn] = fc.plane_through_axis(ctx, turn, f"{what} plane {turn:g}")
        centre = (r * math.cos(math.radians(angle)), r * math.sin(math.radians(angle)), z)
        profiles.append(fc.circle_profile(ctx, planes[turn], centre, radius, f"{what} section {i + 1}"))
    body = fc.loft(ctx, profiles, f"{what} coil")
    body = fusion.move(ctx, body, cp.spring_axes(ctx.dm.theta), f"{what} move")
    return _require_solid(ctx, body)


_BUILDERS: dict[str, typing.Callable[[BuildContext], adsk.fusion.BRepBody]] = {
    bodies.HUB: build_hub,
    bodies.ROTOR: build_rotor,
    bodies.HOUSING: build_housing,
    bodies.BUTTON: build_button,
    bodies.SPRING: build_spring,
}


def build_clicker_part(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the click-indexer body called `name` in the current container's component."""
    builder = _BUILDERS.get(name)
    if builder is None:
        raise fusion.BuildError(f"{name}: not a click-indexer body")
    return builder(ctx)
