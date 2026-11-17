"""Own copy of the One-way clutch add-in's part builders, used by the clutch mount (docs/turbinefan/deviations.md).

One builder per body. Every tool and fastener is built at the origin with its axis on +Z, then moved onto its site,
so the sketches stay on the XY and XZ planes and every revolve turns about the component's Z axis.

The hub, the ring, the plates and the adapter are built in their final local frame. The placement is the top
component's occurrence transform, so no body is moved by it.
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import fasteners
from ...lib.gen.clutch import bodies, bridge, expected, sections
from ...lib.gen.clutch.constants import (
    ADAPTER_FROM,
    ADAPTER_THICKNESS,
    ADAPTER_TO,
    BACK_PLATE_THICKNESS,
    BOLT_ANGLES,
    CHAMFER_LOOP_MIN,
    COVER_FROM,
    COVER_THICKNESS,
    COVER_TO,
    EAR_ANGLES,
    FACE_CIRCLE,
    HUB_FROM,
    HUB_HEIGHT,
    PLATE_CHAMFER,
    RING_CHAMFER,
    RING_FROM,
    RING_HEIGHT,
    RING_TO,
)
from ...lib.gen.curves import Loop, Point
from ...lib.gen.fasteners import Site
from . import fusion

if typing.TYPE_CHECKING:
    from .clutch_build import ClutchContext

_ORIGIN = (0.0, 0.0)
Circle = tuple[Point, float]


def _require_solid(ctx: ClutchContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _prism(ctx: ClutchContext, what: str, loops: list[Loop], circles: list[Circle], z0: float, length: float,
           count: int) -> adsk.fusion.BRepBody:
    """The sketch of `loops` and `circles` on the XY plane, extruded from z0 for length along +Z. `count` is the
    number of loops of the profile to extrude (its outline and its holes)."""
    sk = fusion.new_sketch(ctx.comp, what)
    for loop in loops:
        fusion.draw_loop(sk, loop)
    for center, radius in circles:
        fusion.draw_circle(sk, center, radius)
    profile = fusion.profile_with_loops(sk, count, f"{what}_sketch")
    return fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")


def _tool_prism(ctx: ClutchContext, what: str, loop: Loop, z0: float, length: float) -> adsk.fusion.BRepBody:
    return _prism(ctx, what, [loop], [], z0, length, 1)


def _cylinder(ctx: ClutchContext, what: str, radius: float, z0: float, length: float) -> adsk.fusion.BRepBody:
    return _prism(ctx, what, [], [(_ORIGIN, radius)], z0, length, 1)


def _turned(ctx: ClutchContext, what: str, section: Loop) -> adsk.fusion.BRepBody:
    """A (radius, z) section revolved about the Z axis."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    fusion.draw_loop_xz(sk, section)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.revolve(ctx, profile, f"{what}_revolve")


def _cut_all(
    ctx: ClutchContext, body: adsk.fusion.BRepBody, tools: list[adsk.fusion.BRepBody], what: str
) -> adsk.fusion.BRepBody:
    """Cut the tools one after another, in the gallery's order."""
    for i, tool in enumerate(tools):
        body = fusion.cut(ctx, body, [tool], f"{what} cut {i + 1}")
    return body


def _head_pocket(ctx: ClutchContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener PocketTool] The head's pocket: radius HEAD_POCKET_RADIUS, from STOCK before the face to the head's
    underside."""
    tool = _cylinder(ctx, what, fasteners.HEAD_POCKET_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + fasteners.HEAD_POCKET_DEPTH)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _hex_pocket(ctx: ClutchContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HexPocketTool] The hexagonal pocket from the site's cavity, NUT_CAVITY_HEIGHT + STOCK deep along the
    site's direction, so it opens through the face the cavity is near. Its corners lie on the circle of radius
    NUT_CAVITY_RADIUS with the first along the site's corner, and stay sharp."""
    tool = _tool_prism(ctx, what, fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS), 0.0,
                       fasteners.NUT_CAVITY_HEIGHT + fasteners.STOCK)
    return fusion.move(ctx, tool, site.axes(site.cavity), f"{what} move")


def _hole_circles(radius: float, angles: tuple[float, ...]) -> list[Circle]:
    return [(c, fasteners.HOLE_RADIUS) for c in sections.bolt_hole_centers(radius, angles)]


def _chamfer_loops(ctx: ClutchContext, body: adsk.fusion.BRepBody, zs: tuple[float, ...], size: float, what: str,
                   outer_only: bool) -> None:
    """One chamfer call over the long loops of the large faces at each z (mm): the outer loop only when outer_only,
    else every loop of CHAMFER_LOOP_MIN or more. A short loop (a bolt hole) stays sharp.

    # Deviation: when Fusion rejects a chamfer that includes an inner loop (the D loop of an 8 mm bore), the build logs
    a `fallback` line and chamfers the outer loops only (docs/onewayclutch/deviations.md)."""
    outer: list[adsk.fusion.BRepEdge] = []
    inner: list[adsk.fusion.BRepEdge] = []
    for z in zs:
        found = fusion.face_loops(body, z, 100.0, f"{what} z={z:g}")
        if outer_only:
            found = [(is_outer, es) for is_outer, es in found if is_outer]
            if len(found) != 1:
                raise fusion.BuildError(f"{what}: found {len(found)} outer loops at z={z:g}, expected 1")
        else:
            found = [(is_outer, es) for is_outer, es in found if fusion.loop_length(es) >= CHAMFER_LOOP_MIN]
            if not found:
                raise fusion.BuildError(f"{what}: found no long loop at z={z:g}")
        for is_outer, es in found:
            (outer if is_outer else inner).extend(es)
    try:
        fusion.chamfer(ctx, outer + inner, size, f"{what} chamfer faces", tangent_chain=False)
    except fusion.BuildError as e:
        if not inner:
            raise
        ctx.log.write("fallback", [("step", f"{what} chamfer faces"), ("message", str(e))])
        fusion.chamfer(ctx, outer, size, f"{what} chamfer outer faces", tangent_chain=False)


def build_hub(ctx: ClutchContext) -> adsk.fusion.BRepBody:
    """[hub] Extrude the outline, the D bore and the three bolt holes HUB_HEIGHT along +Z, then chamfer the arms' long
    runs on both faces by dm.hub_chamfer, and the whole D loop when it is CHAMFER_LOOP_MIN or more (the 8 mm presets).
    Every hub's faces are over 400 mm^2, so every hub takes the chamfer. No Boolean."""
    dm = ctx.dm
    outline = sections.layout(sections.hub_outline(dm), dm.sign)
    body = _prism(ctx, "hub", [outline, sections.bore_loop(dm)], _hole_circles(dm.bolt_circle, BOLT_ANGLES), HUB_FROM,
                  HUB_HEIGHT, 5)
    if expected.hub_is_chamfered(dm):
        # Each pawl's arm outer arc and its inner run (the inner arc, slot round, core arc, web round and web face,
        # which Fusion takes as one tangent chain); the head run (flank, tip round, lock face) stays sharp.
        edges: list[adsk.fusion.BRepEdge] = []
        for z in (HUB_FROM, HUB_FROM + HUB_HEIGHT):
            for radius in (dm.arm_outer, dm.arm_inner):
                edges += fusion.circular_edges_at(body, radius, z)
        if len(edges) != 12:
            raise fusion.BuildError(f"hub chamfer: found {len(edges)} arm arcs, expected 12")
        if dm.bore_loop >= CHAMFER_LOOP_MIN:
            # The 8 mm presets' D loop is 20 mm or more, so the gallery chamfers it whole.
            for z in (HUB_FROM, HUB_FROM + HUB_HEIGHT):
                loops = [es for is_outer, es in fusion.face_loops(body, z, 100.0, f"hub z={z:g}")
                         if not is_outer and fusion.loop_length(es) >= CHAMFER_LOOP_MIN]
                if len(loops) != 1:
                    raise fusion.BuildError(f"hub chamfer: found {len(loops)} long D loops at z={z:g}, expected 1")
                edges += loops[0]
        try:
            fusion.chamfer(ctx, edges, dm.hub_chamfer, "hub chamfer faces", tangent_chain=True)
        except fusion.BuildError as e:
            # Deviation: the gallery has no fallback; the hub stays an exact prism (docs/onewayclutch/deviations.md).
            ctx.log.write("fallback", [("step", "hub chamfer faces"), ("message", str(e))])
    return _require_solid(ctx, body)


def build_ring(ctx: ClutchContext) -> adsk.fusion.BRepBody:
    """[ring] Extrude the outline (the outside with three ears; as holes the tooth loop and the three ear bores),
    chamfer the outer loop of both end faces, cut the two counterbore tools, then the three mount nut pockets."""
    dm = ctx.dm
    body = _prism(ctx, "ring", [sections.ring_outline(dm), sections.layout(sections.tooth_loop(dm), dm.sign)],
                  [(c, fasteners.HOLE_RADIUS) for c in sections.ear_centers(dm)], RING_FROM, RING_HEIGHT, 5)
    _chamfer_loops(ctx, body, (RING_FROM, RING_TO), RING_CHAMFER, "ring", outer_only=True)
    back = _turned(ctx, "ring back counterbore tool", sections.ring_back_tool(dm))
    front = _turned(ctx, "ring front counterbore tool", sections.ring_front_tool(dm))
    tools = [back, front]
    for i, site in enumerate(dm.mount_sites):
        tools.append(_hex_pocket(ctx, site, f"ring mount nut pocket {i + 1} tool"))
    return _require_solid(ctx, _cut_all(ctx, body, tools, "ring"))


def _bridge(ctx: ClutchContext, body: adsk.fusion.BRepBody, name: str, what: str) -> adsk.fusion.BRepBody:
    """Directive: sacrificial bridge layers, only when the `Sacrificial bridging` box is checked
    (docs/turbinefan/directives.md, docs/sacrificial-bridging.md). Each layer is a disc BRIDGE_THICKNESS thick that
    fills a bolt hole directly above the ceiling of a pocket that opens on the print bed, so the first printed layer
    over the pocket is whole. The disc reaches BRIDGE_OVERLAP into the hole wall so the join overlaps the body, and it
    is joined into the same body.

    # Deviation: the gallery has no bridge layers (docs/turbinefan/deviations.md)."""
    for i, layer in enumerate(bridge.layers_for(name, ctx.p, ctx.dm)):
        tool = _cylinder(ctx, f"{what} bridge {i + 1} tool", bridge.layer_radius(), layer.start,
                         bridge.BRIDGE_THICKNESS)
        tool = fusion.move(ctx, tool, layer.site.axes(), f"{what} bridge {i + 1} move")
        body = fusion.join(ctx, body, [tool], f"{what} bridge {i + 1}_join")
    return body


def _plate(ctx: ClutchContext, what: str, z0: float, thickness: float, outer_z: float,
           inner: Loop) -> adsk.fusion.BRepBody:
    """[plate] The circle dm.plate_radius, the D bore and the three bolt holes extruded `thickness` along +Z from z0, then
    one chamfer of the outer face's long loops (the outer circle, and the D loop when it is 20 mm or more), then the
    revolved inner-face tool. The fastener tools are cut by the caller, after the chamfer."""
    dm = ctx.dm
    circles = [(_ORIGIN, dm.plate_radius)] + _hole_circles(dm.bolt_circle, BOLT_ANGLES)
    body = _prism(ctx, what, [sections.bore_loop(dm)], circles, z0, thickness, 5)
    _chamfer_loops(ctx, body, (outer_z,), PLATE_CHAMFER, what, outer_only=False)
    inner_tool = _turned(ctx, f"{what} inner face tool", inner)
    return fusion.cut(ctx, body, [inner_tool], f"{what} inner face")


def build_back_plate(ctx: ClutchContext) -> adsk.fusion.BRepBody:
    """[backPlate] Outer face z = 0; a hex nut pocket at each bolt site, open to the outer face."""
    sites = ctx.dm.sites
    body = _plate(ctx, "back plate", 0.0, BACK_PLATE_THICKNESS, 0.0, sections.back_plate_tool(ctx.dm))
    pockets = [_hex_pocket(ctx, s, f"back plate nut pocket {i + 1} tool") for i, s in enumerate(sites)]
    body = _cut_all(ctx, body, pockets, "back plate pockets")
    # Print orientation: outer face (z = 0) down, so each nut pocket's ceiling is its roof.
    return _require_solid(ctx, _bridge(ctx, body, bodies.BACK_PLATE, "back plate"))


def build_cover(ctx: ClutchContext) -> adsk.fusion.BRepBody:
    """[cover] Outer face z = COVER_TO; a head pocket at each bolt site."""
    sites = ctx.dm.sites
    body = _plate(ctx, "cover", COVER_FROM, COVER_THICKNESS, COVER_TO, sections.cover_tool(ctx.dm))
    pockets = [_head_pocket(ctx, s, f"cover head pocket {i + 1} tool") for i, s in enumerate(sites)]
    body = _cut_all(ctx, body, pockets, "cover pockets")
    # Print orientation: outer face (z = 18.5) down, so each head pocket's ceiling is its roof.
    return _require_solid(ctx, _bridge(ctx, body, bodies.COVER, "cover"))


def build_adapter(ctx: ClutchContext) -> adsk.fusion.BRepBody:
    """[adapter] The circle dm.adapter_radius with ten holes (the bore, three ear holes, three face holes on the ear lines
    and three access holes over the clutch's bolt heads) extruded ADAPTER_THICKNESS along +Z, one chamfer of both
    faces' long loops, then a head pocket at each mount site and at each face site."""
    dm = ctx.dm
    circles = [(_ORIGIN, dm.adapter_radius), (_ORIGIN, dm.adapter_inner)]
    circles += _hole_circles(dm.ear_circle, EAR_ANGLES) + _hole_circles(FACE_CIRCLE, EAR_ANGLES)
    circles += _hole_circles(dm.bolt_circle, BOLT_ANGLES)
    body = _prism(ctx, "adapter", [], circles, ADAPTER_FROM, ADAPTER_THICKNESS, 11)
    _chamfer_loops(ctx, body, (ADAPTER_FROM, ADAPTER_TO), PLATE_CHAMFER, "adapter", outer_only=False)
    tools = [_head_pocket(ctx, s, f"adapter mount head pocket {i + 1} tool") for i, s in enumerate(dm.mount_sites)]
    tools += [_head_pocket(ctx, s, f"adapter face head pocket {i + 1} tool") for i, s in enumerate(dm.face_sites)]
    body = _cut_all(ctx, body, tools, "adapter")
    # Print orientation: front face (z = 26) down, so each ear head pocket's ceiling is its roof. The face head pockets
    # open on the rear face, which is on top, so they get no layer.
    return _require_solid(ctx, _bridge(ctx, body, bodies.ADAPTER, "adapter"))


def build_bolt(ctx: ClutchContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw: revolved section, underhead fillet, hex socket; placed on the site."""
    comp = ctx.comp
    sk = fusion.new_sketch_xz(comp, "bolt section")
    fusion.draw_loop_xz(sk, fasteners.bolt_section(site.length))
    body = fusion.revolve(ctx, fusion.profile_with_loops(sk, 1, "bolt section_sketch", only=True), "bolt revolve")
    edges = fusion.circular_edges_at(body, fasteners.SHANK_DIAMETER / 2, 0.0)
    if len(edges) != 1:
        raise fusion.BuildError(f"bolt underhead_fillet: found {len(edges)} underhead edges, expected 1")
    fusion.fillet(ctx, edges, fasteners.UNDERHEAD_RADIUS, "bolt underhead_fillet")

    tool = _tool_prism(ctx, "bolt socket", fasteners.hexagon_loop(fasteners.SOCKET_ACROSS_FLATS),
                       fasteners.HEAD_HEIGHT - fasteners.SOCKET_DEPTH,
                       fasteners.SOCKET_DEPTH + fasteners.SOCKET_CUTTER_RISE)
    body = fusion.cut(ctx, body, [tool], "bolt socket_cut")
    body = fusion.move(ctx, body, site.bolt_axes(), "bolt move")
    return _require_solid(ctx, body)


def build_nut(ctx: ClutchContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut: hexagon with a bore, then a revolved chamfer cut on each face; placed on the site."""
    comp = ctx.comp
    nut = _prism(ctx, "nut hexagon", [fasteners.hexagon_loop(fasteners.NUT_ACROSS_FLATS)],
                 [(_ORIGIN, fasteners.NUT_BORE_DIAMETER / 2)], 0.0, fasteners.NUT_THICKNESS, 2)
    for side, upper in (("lower", False), ("upper", True)):
        sk = fusion.new_sketch_xz(comp, f"nut {side} chamfer")
        fusion.draw_loop_xz(sk, fasteners.nut_chamfer_section(upper))
        profile = fusion.profile_with_loops(sk, 1, f"nut {side}_chamfer_sketch", only=True)
        tool = fusion.revolve(ctx, profile, f"nut {side}_chamfer_revolve")
        nut = fusion.cut(ctx, nut, [tool], f"nut {side}_chamfer_cut")
    nut = fusion.move(ctx, nut, site.nut_axes(), "nut move")
    return _require_solid(ctx, nut)


def build_part(ctx: ClutchContext, name: str) -> adsk.fusion.BRepBody:
    """Build the body called `name` in the current container's component."""
    if name == bodies.HUB:
        return build_hub(ctx)
    if name == bodies.RING:
        return build_ring(ctx)
    if name == bodies.BACK_PLATE:
        return build_back_plate(ctx)
    if name == bodies.COVER:
        return build_cover(ctx)
    if name == bodies.ADAPTER:
        return build_adapter(ctx)
    site = bodies.site_of(name, ctx.dm)
    return build_bolt(ctx, site) if bodies.is_bolt(name) else build_nut(ctx, site)
