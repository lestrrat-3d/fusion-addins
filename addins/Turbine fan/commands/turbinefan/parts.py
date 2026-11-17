"""One builder per body. Every tool and fastener is built at the origin with its axis on +Z, then moved onto its site,
so the sketches stay on the XY and XZ planes and every revolve turns about the component's Z axis.

The hub and the blades are built in their final local frame. The placement is the top component's occurrence
transform, so no body is moved by it.
"""

from __future__ import annotations

import math
import typing

import adsk.fusion

from ...lib.gen import blade, bodies, bridge, fasteners, sections
from ...lib.gen.constants import (
    BLADE_COUNT,
    BLADE_SOCKET_FLOOR_ROUND,
    CHAMFER_SIZE,
    LEFT_HAND,
    NUT_SLOT_ROUND,
    PRESS_WALL,
    SET_SCREW_Z,
    STUD_CHAMFER,
)
from ...lib.gen.curves import Loop
from ...lib.gen.fasteners import NUT_CAVITY_HEIGHT, STOCK, Site
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

_ORIGIN = (0.0, 0.0)
_IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_LONG_LOOP = 20.0  # edgefinish.Long: a face loop at least this long is chamfered
_FACE_AREA = 100.0  # the hub's faces are far larger; the head pockets' floors and nut slots' faces are not


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


def _cylinder(ctx: BuildContext, what: str, radius: float, z0: float, length: float) -> adsk.fusion.BRepBody:
    sk = fusion.new_sketch(ctx.comp, what)
    fusion.draw_circle(sk, _ORIGIN, radius)
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
    tool = _cylinder(ctx, what, fasteners.HEAD_POCKET_RADIUS, -STOCK, STOCK + fasteners.HEAD_POCKET_DEPTH)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _hole(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HoleTool] The clearance hole, from STOCK before the head to STOCK past the tip."""
    tool = _cylinder(ctx, what, fasteners.HOLE_RADIUS, -STOCK, STOCK + site.tip() + STOCK)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _round(ctx: BuildContext, edges: list[adsk.fusion.BRepEdge], radius: float, what: str) -> None:
    """Round `edges`. # Deviation: when Fusion rejects a round on a cutting tool, the tool keeps its sharp edges and
    the build logs a `fallback` line (docs/turbinefan/deviations.md). The gallery has no fallback."""
    try:
        fusion.fillet(ctx, edges, radius, what)
    except fusion.BuildError as e:
        ctx.log.write("fallback", [("step", what), ("message", str(e))])


def _slot(ctx: BuildContext, what: str, reach: float, axes: tuple) -> adsk.fusion.BRepBody:
    """[slotTool] A hex nut slot: the hexagon of the nut's cavity with its two sides toward +x run on as straight walls
    out to x = reach, extruded NUT_CAVITY_HEIGHT along +Z, its three hexagon corners rounded by NUT_SLOT_ROUND, then
    moved onto the slot's frame `axes` (origin, x = the radial line, y = its tangent, z = the extrusion)."""
    tool = _prism(ctx, what, sections.nut_slot_loop(reach), 0.0, NUT_CAVITY_HEIGHT)
    edges = fusion.z_edges_at(tool, sections.nut_slot_round_corners())
    if len(edges) != 3:
        raise fusion.BuildError(f"{what}: found {len(edges)} corner edges, expected 3")
    _round(ctx, edges, NUT_SLOT_ROUND, f"{what} round_corners")
    return fusion.move(ctx, tool, axes, f"{what} move")


def _cavity_slot(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[slotTool] The nut slot of a blade bolt (Dir -Z: its far face CAVITY_FAR behind the head) or of an adapter bolt
    (Dir +Z: Cavity in front of the head), running out along the site's corner through the hub's rim."""
    u = site.corner
    z = site.head[2] + (site.cavity if site.dir[2] > 0 else -site.cavity_far())
    axes = ((site.head[0], site.head[1], z), u, (-u[1], u[0], 0.0), (0.0, 0.0, 1.0))
    # The reach runs from the bolt's line out past the rim: the blade bolt's distance from the axis (size.blade_bolt_at)
    # or the adapter bolt's (the clutch's face circle).
    return _slot(ctx, what, ctx.dm.size.hub_radius + STOCK - math.hypot(site.head[0], site.head[1]), axes)


def _set_screw_slot(ctx: BuildContext, what: str) -> adsk.fusion.BRepBody:
    """[setScrewSlotTool] The set screw's nut slot, open to the back face: the slot outline in the plane
    y = -(f_b + PRESS_WALL), extruded along -Y, with every edge of both slot faces rounded by NUT_SLOT_ROUND."""
    dm = ctx.dm
    tool = _prism(ctx, what, sections.nut_slot_loop(SET_SCREW_Z + STOCK), 0.0, NUT_CAVITY_HEIGHT)
    edges: list[adsk.fusion.BRepEdge] = []
    for z in (0.0, NUT_CAVITY_HEIGHT):
        edges += [e for is_outer, loop in fusion.face_loops(tool, z, 1.0, what) if is_outer for e in loop]
    _round(ctx, edges, NUT_SLOT_ROUND, f"{what} round_faces")
    axes = ((0.0, -(dm.bore_flat + PRESS_WALL), SET_SCREW_Z), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))
    return fusion.move(ctx, tool, axes, f"{what} move")


def _counterbore(ctx: BuildContext, what: str) -> adsk.fusion.BRepBody:
    """[counterboreTool] The set screw's counterbore: a meridian revolved about the screw's line, from the floor at
    rho_f a quarter round up to the head pocket's radius, out through the round face."""
    dm = ctx.dm
    tool = _turned(ctx, what, fasteners.meridian_loop(sections.counterbore_meridian(dm)))
    axes = ((0.0, -dm.counterbore_floor, SET_SCREW_Z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
    return fusion.move(ctx, tool, axes, f"{what} move")


def _socket_tools(ctx: BuildContext) -> list[adsk.fusion.BRepBody]:
    """[socketTools, BladeSocketTool] The three blade sockets' cutters: a cylinder along +Y from y = size.blade_socket_start
    in the hub's mid plane, its start cap's outer loop rounded, and its two copies about the shaft axis."""
    sz = ctx.dm.size
    tool = _cylinder(ctx, "socket tool", sz.blade_socket_radius, 0.0, sz.hub_radius + 1 - sz.blade_socket_start)
    edges = [e for is_outer, loop in fusion.face_loops(tool, 0.0, 1.0, "socket tool") if is_outer for e in loop]
    if len(edges) != 1:
        raise fusion.BuildError(f"socket tool: found {len(edges)} start-cap edges, expected 1")
    _round(ctx, edges, BLADE_SOCKET_FLOOR_ROUND, "socket tool round_start")
    tool = fusion.move(ctx, tool, ((0.0, sz.blade_socket_start, sz.hub_mid), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                       "socket tool move")
    return fusion.pattern(ctx, tool, BLADE_COUNT, "socket tool pattern")


def _bridge(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str) -> adsk.fusion.BRepBody:
    """Directive: sacrificial bridge layers of the hub, only when the `Sacrificial bridging` box is checked
    (docs/turbinefan/directives.md, docs/sacrificial-bridging.md). Each layer is a disc BRIDGE_THICKNESS thick that
    fills a bolt hole directly above the ceiling of a pocket or nut slot, so the first printed layer over it is whole.
    The disc reaches BRIDGE_OVERLAP into the hole wall so the join overlaps the body, and it is joined into the same
    body.

    # Deviation: the gallery has no bridge layers (docs/turbinefan/deviations.md)."""
    for i, layer in enumerate(bridge.hub_layers(ctx.p, ctx.dm)):
        tool = _cylinder(ctx, f"{what} bridge {i + 1} tool", bridge.layer_radius(), layer.start,
                         bridge.BRIDGE_THICKNESS)
        tool = fusion.move(ctx, tool, layer.site.axes(), f"{what} bridge {i + 1} move")
        body = fusion.join(ctx, body, [tool], f"{what} bridge {i + 1}_join")
    return body


def build_hub(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[hub] Extrude the outline (circle, D bore and three blade bolt holes), chamfer both faces' long loops, then cut
    the three sockets, each blade's head pocket and nut slot, the set screw's counterbore, hole and nut slot, and each
    adapter bolt's hole and nut slot, in this order."""
    dm = ctx.dm
    sk = fusion.new_sketch(ctx.comp, "hub outline")
    fusion.draw_circle(sk, _ORIGIN, dm.size.hub_radius)
    fusion.draw_loop(sk, sections.bore_loop(dm))
    for site in dm.blade_sites:
        fusion.draw_circle(sk, (site.head[0], site.head[1]), fasteners.HOLE_RADIUS)
    profile = fusion.profile_with_loops(sk, BLADE_COUNT + 2, "hub outline_sketch")
    body = fusion.extrude(ctx, profile, 0.0, dm.size.hub_length, "hub extrude")

    edges: list[adsk.fusion.BRepEdge] = []
    for z in (0.0, dm.size.hub_length):
        edges += fusion.long_loop_edges(body, z, _FACE_AREA, _LONG_LOOP, f"hub z={z:g}")
    fusion.chamfer(ctx, edges, CHAMFER_SIZE, "hub chamfer faces", tangent_chain=False)

    tools = _socket_tools(ctx)
    for k, site in enumerate(dm.blade_sites, start=1):
        tools.append(_head_pocket(ctx, site, f"hub blade {k} head pocket tool"))
        tools.append(_cavity_slot(ctx, site, f"hub blade {k} nut slot tool"))
    tools.append(_counterbore(ctx, "hub counterbore tool"))
    tools.append(_hole(ctx, dm.set_screw_site, "hub set screw hole tool"))
    tools.append(_set_screw_slot(ctx, "hub set screw nut slot tool"))
    for k, site in enumerate(dm.adapter_sites, start=1):
        tools.append(_hole(ctx, site, f"hub adapter bolt {k} hole tool"))
        tools.append(_cavity_slot(ctx, site, f"hub adapter bolt {k} nut slot tool"))
    body = _cut_all(ctx, body, tools, "hub")
    # Print orientation: front face (z = hub_length) down, so -Z is up and each pocket's or slot's ceiling is its roof.
    return _require_solid(ctx, _bridge(ctx, body, "hub"))


def _turn_axes(angle: float) -> tuple:
    """The rotation about the Z axis through the origin, as a frame."""
    c, s = math.cos(angle), math.sin(angle)
    return ((0.0, 0.0, 0.0), (c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0))


def build_blades(ctx: BuildContext) -> list[adsk.fusion.BRepBody]:
    """[blades, bladeBody] Blade 1 in the blade's own frame: a loft through the ten sections drawn at the 25 degree
    pitch, turned to the pitch, joined to the drilled and chamfered root stud; then turned into the hub's frame and
    copied about the shaft axis."""
    p = ctx.p
    sz = ctx.dm.size
    mirror = p.hand == LEFT_HAND
    profiles = []
    for st in blade.stations_for(sz):
        name = f"blade section r{st.r:g}"
        sk = fusion.new_sketch_at_z(ctx.comp, name, st.r)
        fusion.draw_section(sk, blade.fit_points(st, mirror, sz), st.r)
        profiles.append(fusion.profile_with_loops(sk, 1, f"{name}_sketch", only=True))
    # Deviation: Fusion lofts through the section profiles itself; the gallery's twisted-loft workaround (always loft at
    # the 25 degree sections, then turn the loft) is kept (docs/turbinefan/deviations.md).
    loft = fusion.loft(ctx, profiles, "blade loft")
    turn = blade.pitch_turn(p.blade_pitch, mirror)
    if abs(turn) > 1e-12:
        loft = fusion.move(ctx, loft, _turn_axes(turn), "blade pitch turn")

    stud = _cylinder(ctx, "blade stud", sz.blade_stud_radius, sz.blade_stud_start, sz.blade_stud_end - sz.blade_stud_start)
    start = [e for is_outer, loop in fusion.face_loops(stud, sz.blade_stud_start, 1.0, "blade stud") if is_outer
             for e in loop]
    if len(start) != 1:
        raise fusion.BuildError(f"blade stud chamfer: found {len(start)} start-cap edges, expected 1")
    fusion.chamfer(ctx, start, STUD_CHAMFER, "blade stud chamfer", tangent_chain=False)
    reach = sz.blade_stud_radius + 2  # the bolt hole's cutter starts and ends this far from the stud's axis
    hole = _cylinder(ctx, "blade stud hole tool", fasteners.HOLE_RADIUS, 0.0, 2 * reach)
    hole = fusion.move(ctx, hole, ((0.0, -reach, sz.blade_bolt_at), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                       "blade stud hole move")
    stud = fusion.cut(ctx, stud, [hole], "blade stud cut")
    body = fusion.join(ctx, loft, [stud], "blade join")
    _require_solid(ctx, body)

    # Blade-local Z (the radial line) becomes +Y, local Y becomes +Z and local X becomes -X, from (0, 0, size.hub_mid).
    body = fusion.move(ctx, body, ((0.0, 0.0, sz.hub_mid), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
                       "blade place")
    return fusion.pattern(ctx, body, BLADE_COUNT, "blade pattern")


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


def build_fastener(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the bolt or the nut called `name` in the current container's component."""
    site = bodies.site_of(name, ctx.dm)
    return build_bolt(ctx, site) if bodies.is_bolt(name) else build_nut(ctx, site)
