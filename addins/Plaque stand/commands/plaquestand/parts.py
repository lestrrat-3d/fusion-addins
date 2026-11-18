"""One builder per body. Every tool and fastener is built at the origin with its axis on +Z, then moved onto its site,
so the sketches stay on the XY and XZ planes and every revolve turns about the component's Z axis.

The bracket's profile is a loop in (y, z). It is drawn on the XY plane as (x, y) = (y, z), extruded along +Z by the
bracket's width and then turned onto the X axis by a move: sketch x becomes world Y, sketch y becomes world Z and the
extrusion becomes world X. The rail's section and the plaque's rectangle are drawn and moved the same way.
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies, expected, fasteners, sections
from ...lib.gen.constants import (
    BASE_THICKNESS,
    BRACKET_WIDTH,
    CHAMFER_SIZE,
    JOINT_FIT,
    NUT_POCKET_ROUND,
    RAIL_HEIGHT,
)
from ...lib.gen.curves import Loop, Point
from ...lib.gen.fasteners import Site
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_ORIGIN = (0.0, 0.0)
# Sketch (x, y) = world (Y, Z) and the +Z extrusion = world +X: a right-handed frame (x = Y, y = Z, z = X).
_AXES_X = ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


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
    `fallback` line (docs/plaquestand/deviations.md)."""
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



def _onto_x(origin: tuple[float, float, float]) -> tuple:
    """The frame that turns a section drawn on the XY plane and extruded along +Z onto the X axis, with the sketch
    origin at `origin`."""
    return (origin, _AXES_X[1], _AXES_X[2], _AXES_X[3])


def build_bracket(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """[buildBracket] Extrude the profile BRACKET_WIDTH, chamfer both side faces' outlines by CHAMFER_SIZE, then cut the
    bolt's nut pocket (its floor outline rounded) and hole."""
    dm = ctx.dm
    first = name == bodies.BRACKET_1
    x0 = 0.0 if first else dm.span - BRACKET_WIDTH
    site = dm.sites[0 if first else 1]
    sk = fusion.new_sketch(ctx.comp, f"{name} profile")
    fusion.draw_loop(sk, sections.outline_loop(dm))
    profile = fusion.profile_with_loops(sk, 1, f"{name} profile_sketch", only=True)
    body = fusion.extrude(ctx, profile, 0.0, BRACKET_WIDTH, f"{name} extrude")

    edges = []
    for z in (0.0, BRACKET_WIDTH):
        loops = fusion.face_loops(body, z, 100.0, f"{name} z={z:g}")
        outer = [es for is_outer, es in loops if is_outer]
        if len(outer) != 1:
            raise fusion.BuildError(f"{name} chamfer: found {len(outer)} outer loops at z={z:g}, expected 1")
        edges += outer[0]
    fusion.chamfer(ctx, edges, CHAMFER_SIZE, f"{name} chamfer faces", tangent_chain=False)
    body = fusion.move(ctx, body, _onto_x((x0, 0.0, 0.0)), f"{name} move")

    pocket = _nut_pocket(ctx, site, f"{name} nut pocket tool", fasteners.NUT_CAVITY_HEIGHT + fasteners.STOCK)
    hole = _hole(ctx, site, f"{name} bolt hole tool")
    return _require_solid(ctx, _cut_all(ctx, body, [pocket, hole], name))


def build_rail(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[buildRail] The rounded rectangle section extruded the span along X, then each bolt's head pocket and hole."""
    dm = ctx.dm
    sk = fusion.new_sketch(ctx.comp, "rail section")
    fusion.draw_loop(sk, sections.rail_loop())
    profile = fusion.profile_with_loops(sk, 1, "rail section_sketch", only=True)
    body = fusion.extrude(ctx, profile, 0.0, dm.span, "rail extrude")
    # The section's centre is on the channel's centre line, 0.4 above the channel floor's height: z = T_b - h_r/2 + j.
    body = fusion.move(ctx, body, _onto_x((0.0, dm.rail_center, BASE_THICKNESS - RAIL_HEIGHT / 2 + JOINT_FIT)),
                       "rail move")
    tools = []
    for k, site in enumerate(dm.sites, start=1):
        tools.append(_head_pocket(ctx, site, f"rail head pocket {k} tool"))
        tools.append(_hole(ctx, site, f"rail bolt hole {k} tool"))
    return _require_solid(ctx, _cut_all(ctx, body, tools, "rail"))


def build_plaque(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[plaqueSketch] The reference plaque: a W by t rectangle extruded H, then turned to lean back and set on the seat:
    x along the span, y along the slot's normal and z along the slot."""
    p = ctx.p
    sk = fusion.new_sketch(ctx.comp, "plaque")
    fusion.draw_rectangle(sk, _ORIGIN, (p.plaque_width, p.plaque_thickness))
    profile = fusion.profile_with_loops(sk, 1, "plaque_sketch", only=True)
    body = fusion.extrude(ctx, profile, 0.0, p.plaque_height, "plaque extrude")
    body = fusion.move(ctx, body, expected.plaque_axes(p, ctx.dm), "plaque move")
    return _require_solid(ctx, body)


def build_part(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the body called `name` in the current container's component."""
    if name in bodies.BRACKETS:
        return build_bracket(ctx, name)
    if name == bodies.RAIL:
        return build_rail(ctx)
    if name == bodies.PLAQUE:
        return build_plaque(ctx)
    site = bodies.site_of(name, ctx.dm)
    return build_bolt(ctx, site) if bodies.is_bolt(name) else build_nut(ctx, site)
