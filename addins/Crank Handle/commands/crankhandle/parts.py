"""One builder per body. Every tool and fastener is built at the origin with its axis on +Z, then moved onto its site,
so the sketches stay on the XY and XZ planes and every revolve turns about the component's Z axis.

The arm, the pin and the handle are built in their final local frame. The placement is the top component's occurrence
transform, so no body is moved by it.
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies, bridge, fasteners, sections
from ...lib.gen.constants import (
    ARM_RADIUS,
    ARM_THICKNESS,
    BORE_FLOOR,
    CHAMFER_SIZE,
    CROSS_Z,
    HUB_LENGTH,
    NUT_POCKET_ROUND,
    PIN_HOLE_R,
    POCKET_FLATS,
    POCKET_FROM,
    POCKET_LENGTH,
    STUB_FLATS,
    STUB_FROM,
    STUB_LENGTH,
)
from ...lib.gen.curves import Loop
from ...lib.gen.fasteners import Site
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_ORIGIN = (0.0, 0.0)
_IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _prism(ctx: BuildContext, what: str, loop: Loop, z0: float, length: float) -> adsk.fusion.BRepBody:
    """A closed loop on the XY plane extruded from z0 for length along +Z."""
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")


def _cylinder(
    ctx: BuildContext, what: str, radius: float, z0: float, length: float, center: tuple[float, float] = _ORIGIN
) -> adsk.fusion.BRepBody:
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_circle(sk, center, radius)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")


def _turned(ctx: BuildContext, what: str, section: Loop) -> adsk.fusion.BRepBody:
    """A (radius, z) section revolved about the Z axis."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    fusion.draw_loop_xz(sk, section)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.revolve(ctx, profile, f"{what}_revolve")


def _cut_all(
    ctx: BuildContext, body: adsk.fusion.BRepBody, tools: list[adsk.fusion.BRepBody], what: str
) -> adsk.fusion.BRepBody:
    """Cut the tools one after another, in the gallery's order."""
    for i, tool in enumerate(tools):
        body = fusion.cut(ctx, body, [tool], f"{what} cut {i + 1}")
    return body


def _head_pocket(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener PocketTool] The head's pocket: radius HEAD_POCKET_RADIUS, from STOCK before the face to the head's
    underside."""
    tool = _cylinder(ctx, what, fasteners.HEAD_POCKET_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + fasteners.HEAD_POCKET_DEPTH)
    tool = fusion.move(ctx, tool, site.axes(), f"{what} move")
    return tool


def _hole(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HoleTool] The clearance hole, from STOCK before the head to STOCK past the tip."""
    tool = _cylinder(ctx, what, fasteners.HOLE_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + site.tip() + fasteners.STOCK)
    tool = fusion.move(ctx, tool, site.axes(), f"{what} move")
    return tool


def _nut_pocket(ctx: BuildContext, site: Site, what: str, depth: float) -> adsk.fusion.BRepBody:
    """[m2fastener HexPocketTool, nutPocketCutter] The hexagonal pocket from the site's cavity floor, `depth` deep
    along the bolt, so it opens through the face past the nut. Its corners lie on the circle of radius
    NUT_CAVITY_RADIUS with the first along the site's corner. Its floor's outline is rounded by NUT_POCKET_ROUND.

    # Deviation: when Fusion rejects the floor round, the pocket keeps its sharp floor and the build logs a
    `fallback` line (docs/crankhandle/deviations.md)."""
    loop = fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS)
    tool = _prism(ctx, what, loop, 0.0, depth)
    floor = [e for is_outer, edges in fusion.face_loops(tool, 0.0, 1.0, what) if is_outer for e in edges]
    if len(floor) != 6:
        raise fusion.BuildError(f"{what}: found {len(floor)} floor edges, expected 6")
    try:
        fusion.fillet(ctx, floor, NUT_POCKET_ROUND, f"{what} round_floor")
    except fusion.BuildError as e:
        ctx.log.write("fallback", [("step", f"{what} round_floor"), ("message", str(e))])
    tool = fusion.move(ctx, tool, site.axes(site.cavity), f"{what} move")
    return tool


def _rounded(ctx: BuildContext, site: Site, what: str, meridian: list[tuple[float, float]]) -> adsk.fusion.BRepBody:
    """[m2fastener RoundedHoleTool, RoundedCavityTool] A tool revolved about the site's axis."""
    tool = _turned(ctx, what, fasteners.meridian_loop(meridian))
    tool = fusion.move(ctx, tool, site.axes(), f"{what} move")
    return tool


def _relief(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[reliefTool] The cutter that turns the hub's full-height block into the boss and its ramp: the side profile on the
    YZ plane, extruded across the arm, from x = -(ARM_RADIUS + 1) to ARM_RADIUS + 1."""
    sk = fusion.new_sketch_yz(ctx.comp, "arm relief tool")
    fusion.draw_loop_yz(sk, sections.relief_tool(ctx.p, ctx.dm))
    profile = fusion.profile_with_loops(sk, 1, "arm relief tool_sketch", only=True)
    return fusion.extrude_symmetric(ctx, profile, 2 * ARM_RADIUS + 2, "arm relief tool_extrude")


def build_arm(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[arm] Extrude the outline to HUB_LENGTH, chamfer both faces' outer loops, cut the relief that leaves the boss and
    its ramp, chamfer the new outer face, then cut the slit, the blind bore, the hexagonal pocket, the pin bolt's head
    pocket, and each clamp bolt's nut pocket, head pocket and hole, in this order. The bore's rim in the back face is
    chamfered last."""
    p, dm = ctx.p, ctx.dm
    sk = fusion.new_sketch(ctx.comp, "arm outline")
    fusion.draw_loop(sk, sections.arm_outline(p, dm))
    fusion.draw_circle(sk, (0.0, p.throw), PIN_HOLE_R)
    profile = fusion.profile_with_loops(sk, 2, "arm outline_sketch")
    body = fusion.extrude(ctx, profile, 0.0, HUB_LENGTH, "arm extrude")

    edges = []
    for z in (0.0, HUB_LENGTH):
        loops = fusion.face_loops(body, z, 100.0, f"arm z={z:g}")
        outer = [edges_ for is_outer, edges_ in loops if is_outer]
        if len(outer) != 1:
            raise fusion.BuildError(f"arm chamfer: found {len(outer)} outer loops at z={z:g}, expected 1")
        edges += outer[0]
    fusion.chamfer(ctx, edges, CHAMFER_SIZE, "arm chamfer faces", tangent_chain=False)

    body = fusion.cut(ctx, body, [_relief(ctx)], "arm relief cut")
    # The relief's new outer face and the ramp's top edge are chamfered by two calls: the outline is a tangent chain and
    # the ramp's top edge is not.
    outline, top = fusion.outer_face_edges(body, ARM_THICKNESS, HUB_LENGTH, ARM_RADIUS, dm.ramp_foot, p.throw,
                                           PIN_HOLE_R, "arm outer face")
    fusion.chamfer(ctx, outline, CHAMFER_SIZE, "arm outer face chamfer", tangent_chain=False)
    fusion.chamfer(ctx, top, CHAMFER_SIZE, "arm ramp top chamfer", tangent_chain=False)

    slit = _prism(ctx, "arm slit tool", sections.slit_tool(dm), -1.0, HUB_LENGTH + 2)
    bore = _prism(ctx, "arm bore tool", sections.bore_tool(dm, p.double_flat), -1.0, 1 + HUB_LENGTH - BORE_FLOOR)
    pocket = _prism(ctx, "arm pocket tool", fasteners.hexagon_loop(POCKET_FLATS, (0.0, p.throw)), POCKET_FROM,
                    POCKET_LENGTH)
    head = _head_pocket(ctx, dm.site, "arm pin head pocket tool")
    tools = [slit, bore, pocket, head]
    for i, site in enumerate(dm.clamp_sites, start=1):
        # Each clamp's nut pocket runs from its floor out through the -X side face, 2 ARM_RADIUS from the head's face.
        tools += [
            _nut_pocket(ctx, site, f"arm clamp {i} nut pocket tool", 2 * ARM_RADIUS - site.cavity + fasteners.STOCK),
            _head_pocket(ctx, site, f"arm clamp {i} head pocket tool"),
            _hole(ctx, site, f"arm clamp {i} hole tool"),
        ]
    body = _cut_all(ctx, body, tools, "arm")
    if p.sacrificial_bridging:
        body = _bridge_layers(ctx, body)
    _chamfer_bore_rim(ctx, body)
    return _require_solid(ctx, body)


def _bridge_layers(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    """Sacrificial bridge layers, only when the `Sacrificial bridging` box is checked.

    # Deviation from decad-gallery: the pin bolt's head pocket in the arm is wider than the pin hole above it, so with the
    arm printed on its back face the first layer over the pocket would hang in the air. A BRIDGE_THICKNESS disc fills
    the hole directly above the pocket's roof, so that layer is whole. The owner drills it out after printing. The
    disc reaches BRIDGE_OVERLAP into the hole wall so the join overlaps the arm's volume
    (directive in docs/crankhandle/directives.md; rule in docs/sacrificial-bridging.md)."""
    for i, b in enumerate(bridge.arm_bridges(ctx.p), start=1):
        layer = _cylinder(ctx, f"arm bridge {i}", b.disc_radius(), b.z0, b.thickness, b.center)
        body = fusion.join(ctx, body, [layer], f"arm bridge {i} join")
    return body


def _chamfer_bore_rim(ctx: BuildContext, body: adsk.fusion.BRepBody) -> None:
    """[chamferBoreRim] Chamfer the bore's rim in the back face by CHAMFER_SIZE: the two arcs and the flat the slit
    leaves, or with a double flat the two arcs and three lines, because the slit splits the -Y flat. Each arc ends at a
    slit wall. It runs after every cut, so no later cut meets the rim.

    # Deviation: when Fusion rejects the chamfer, the rim stays sharp and the build logs a `fallback` line
    (docs/crankhandle/deviations.md)."""
    edges = fusion.bore_rim_edges(body, ctx.dm.bore_radius, "arm bore rim", 3 if ctx.p.double_flat else 1)
    try:
        fusion.chamfer(ctx, edges, CHAMFER_SIZE, "arm bore rim chamfer", tangent_chain=False)
    except fusion.BuildError as e:
        ctx.log.write("fallback", [("step", "arm bore rim chamfer"), ("message", str(e))])


def build_pin(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[pin] Join the hexagonal stub to the turned shank and head, then cut the double flats, the pin bolt's rounded
    hole and nut cavity, and each cross bolt's hole, head pocket and hexagonal nut pocket open to the -Y flat."""
    p, dm = ctx.p, ctx.dm
    stub = _prism(ctx, "pin stub", fasteners.hexagon_loop(STUB_FLATS, (0.0, p.throw)), STUB_FROM, STUB_LENGTH)
    turned = _turned(ctx, "pin turned", sections.pin_meridian())
    turned = fusion.move(ctx, turned, ((0.0, p.throw, 0.0),) + _IDENTITY[1:], "pin turned move")
    body = fusion.join(ctx, stub, [turned], "pin join")

    tools: list[adsk.fusion.BRepBody] = []
    for i, z in enumerate(CROSS_Z):
        for side in (1.0, -1.0):
            a, b, z0, length = sections.flat_box(p.throw, z, side)
            sk = fusion.new_sketch(ctx.comp, f"pin flat {i + 1}{'+' if side > 0 else '-'}")
            fusion.draw_rectangle(sk, a, b)
            profile = fusion.profile_with_loops(sk, 1, f"pin flat {i + 1}_sketch", only=True)
            tools.append(fusion.extrude(ctx, profile, z0, length, f"pin flat {i + 1} extrude"))
    tools.append(_rounded(ctx, dm.site, "pin bolt hole tool", fasteners.rounded_hole_meridian(dm.site)))
    tools.append(_rounded(ctx, dm.site, "pin bolt cavity tool", fasteners.rounded_cavity_meridian(dm.site)))
    for i, site in enumerate(dm.cross_sites):
        tools.append(_hole(ctx, site, f"pin cross {i + 1} hole tool"))
        tools.append(_head_pocket(ctx, site, f"pin cross {i + 1} head pocket tool"))
        tools.append(_nut_pocket(ctx, site, f"pin cross {i + 1} nut pocket tool",
                                 fasteners.NUT_CAVITY_HEIGHT + fasteners.STOCK))
    body = _cut_all(ctx, body, tools, "pin")
    return _require_solid(ctx, body)


def build_handle(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[handle] Revolve the handle's meridian about the pin axis."""
    body = _turned(ctx, "handle", sections.handle_meridian())
    body = fusion.move(ctx, body, ((0.0, ctx.p.throw, 0.0),) + _IDENTITY[1:], "handle move")
    return _require_solid(ctx, body)


def build_bolt(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw: revolved section, underhead fillet, hex socket; placed on the site."""
    comp = ctx.comp
    sk = fusion.new_sketch_xz(comp, "bolt section")
    fusion.draw_loop_xz(sk, fasteners.bolt_section(site.length))
    body = fusion.revolve(ctx, fusion.profile_with_loops(sk, 1, "bolt section_sketch", only=True), "bolt revolve")
    edges = fusion.circular_edges_at(body, fasteners.SHANK_DIAMETER / 2, 0.0)
    if len(edges) != 1:
        raise fusion.BuildError(f"bolt underhead_fillet: found {len(edges)} underhead edges, expected 1")
    fusion.fillet(ctx, edges, fasteners.UNDERHEAD_RADIUS, "bolt underhead_fillet")

    tool = _prism(ctx, "bolt socket", fasteners.hexagon_loop(fasteners.SOCKET_ACROSS_FLATS),
                  fasteners.HEAD_HEIGHT - fasteners.SOCKET_DEPTH, fasteners.SOCKET_DEPTH + fasteners.SOCKET_CUTTER_RISE)
    body = fusion.cut(ctx, body, [tool], "bolt socket_cut")
    body = fusion.move(ctx, body, site.bolt_axes(), "bolt move")
    return _require_solid(ctx, body)


def build_nut(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut: hexagon with a bore, then a revolved chamfer cut on each face; placed on the site."""
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
    nut = fusion.move(ctx, nut, site.nut_axes(), "nut move")
    return _require_solid(ctx, nut)


def build_part(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the body called `name` in the current container's component."""
    if name == bodies.ARM:
        return build_arm(ctx)
    if name == bodies.PIN:
        return build_pin(ctx)
    if name == bodies.HANDLE:
        return build_handle(ctx)
    site = bodies.site_of(name, ctx.dm)
    return build_bolt(ctx, site) if bodies.is_bolt(name) else build_nut(ctx, site)
