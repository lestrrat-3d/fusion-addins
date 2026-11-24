"""One builder per body. Every part is built in its own local frame (its axis on local +Z) at the component origin, and
every tool and fastener at the origin with its axis on +Z, so the sketches stay on the XY and XZ planes and every
revolve turns about the component's Z axis. Each finished part is then moved once onto its frame in the model
(`lib/gen/poses.py`; the camshaft group is turned by theta in the same move). The placement is the top component's
occurrence transform, so no body is moved by it.
"""

from __future__ import annotations

import typing

import adsk.fusion

from ...lib.gen import bodies, fasteners, grooves, poses, sections
from ...lib.gen import constants as k
from ...lib.gen.curves import Loop, Point
from ...lib.gen.fasteners import Site
from ...lib.gen.truth import SEGMENTS
from . import fusion, parts_clicker, parts_flags

if typing.TYPE_CHECKING:
    from .build import BuildContext

_ORIGIN: Point = (0.0, 0.0)
Circle = tuple[Point, float]


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _prism(ctx: BuildContext, what: str, loops: list[Loop], circles: list[Circle], z0: float, length: float,
           count: int) -> adsk.fusion.BRepBody:
    """The sketch of `loops` and `circles` on the XY plane, extruded from z0 for length along +Z. `count` is the
    number of loops of the profile to extrude (its outline and its holes)."""
    sk = fusion.new_sketch(ctx.comp, what)
    for loop in loops:
        fusion.draw_loop(sk, loop)
    for center, radius in circles:
        fusion.draw_circle(sk, center, radius)
    profile = fusion.profile_with_loops(sk, count, f"{what}_sketch", only=count == 1)
    return fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")


def _cut_prism(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, loops: list[Loop], circles: list[Circle],
               z0: float, length: float, count: int = 1, loops_per: int = 1,
               only: bool = True) -> adsk.fusion.BRepBody:
    """[cutExtrude] Cut `body` with one sketch of `loops` and `circles` extruded from z0 for length along +Z, as one feature.
    The sketch holds `count` profiles of `loops_per` loops each (`only`: and no other profile). Tools of the same extent
    share the sketch, so they are cut together."""
    sk = fusion.new_sketch(ctx.comp, f"{what} tool")
    for loop in loops:
        fusion.draw_loop(sk, loop)
    for center, radius in circles:
        fusion.draw_circle(sk, center, radius)
    profiles = fusion.profiles_with_loops(sk, loops_per, count, f"{what} tool_sketch", only)
    return fusion.cut_extrude(ctx, profiles, body, z0, length, what)


def _tool_prism(ctx: BuildContext, what: str, loop: Loop, z0: float, length: float) -> adsk.fusion.BRepBody:
    return _prism(ctx, what, [loop], [], z0, length, 1)


def _cylinder(ctx: BuildContext, what: str, radius: float, z0: float, length: float,
              center: Point = _ORIGIN) -> adsk.fusion.BRepBody:
    return _prism(ctx, what, [], [(center, radius)], z0, length, 1)


def _turned(ctx: BuildContext, what: str, section: Loop) -> adsk.fusion.BRepBody:
    """A (radius, z) section revolved about the Z axis."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    fusion.draw_loop_xz(sk, section)
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    return fusion.revolve(ctx, profile, f"{what}_revolve")


def _head_pocket(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener PocketTool] The head's pocket: radius HEAD_POCKET_RADIUS, from STOCK before the face to the head's
    underside."""
    tool = _cylinder(ctx, what, fasteners.HEAD_POCKET_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + fasteners.HEAD_POCKET_DEPTH)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _hole(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HoleTool] The clearance hole, from STOCK before the head to STOCK past the tip."""
    tool = _cylinder(ctx, what, fasteners.HOLE_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + site.tip() + fasteners.STOCK)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _hex_pocket(ctx: BuildContext, site: Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HexPocketTool] The hexagonal pocket from the site's cavity, NUT_CAVITY_HEIGHT + STOCK deep along the
    site's direction, so it opens through the face the cavity is near. Its corners lie on the circle of radius
    NUT_CAVITY_RADIUS with the first along the site's corner, and stay sharp."""
    tool = _tool_prism(ctx, what, fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS), 0.0,
                       fasteners.NUT_CAVITY_HEIGHT + fasteners.STOCK)
    return fusion.move(ctx, tool, site.axes(site.cavity), f"{what} move")


def _cut(ctx: BuildContext, body: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody,
         what: str) -> adsk.fusion.BRepBody:
    return fusion.cut(ctx, body, [tool], what)


def build_shaft(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[shaft] Revolve the meridian about the shaft axis (local Z = world +Y), cut the cam flat, the cam back flat and
    the stub flat, then move the shaft onto its frame, turned by theta."""
    body = _turned(ctx, "shaft", sections.shaft_meridian())
    for name, x0, x1, z0, z1 in sections.shaft_flats():
        sk = fusion.new_sketch(ctx.comp, f"shaft {name} tool")
        fusion.draw_rectangle(sk, (x0, -k.SHAFT_FLAT_HALF), (x1, k.SHAFT_FLAT_HALF))
        profile = fusion.profile_with_loops(sk, 1, f"shaft {name} tool_sketch", only=True)
        body = fusion.cut_extrude(ctx, profile, body, z0, z1 - z0, f"shaft cut {name}")
    body = fusion.move(ctx, body, poses.shaft_axes(ctx.dm.theta), "shaft move")
    return _require_solid(ctx, body)


def _cut_groove(ctx: BuildContext, body: adsk.fusion.BRepBody, segment: int) -> adsk.fusion.BRepBody:
    """[cutGroove] Cut the groove: the outer wall with the inner wall as its hole, from z -1.9 to +1.0 (the gallery
    sketches it on z = +1.0 and cuts 2.9 against the normal).

    # Deviation: the sketch carries no constraints (docs/sevensegment/deviations.md)."""
    outer, inner = grooves.groove_loops(segment, ctx.dm)
    return _cut_prism(ctx, body, f"{ctx.part} cut groove", [outer, inner], [], -k.GROOVE_DEPTH, k.GROOVE_DEPTH + 1.0,
                      loops_per=2, only=False)


def _inscribe(ctx: BuildContext, body: adsk.fusion.BRepBody, segment: int) -> adsk.fusion.BRepBody:
    """[inscribe] Engrave the segment's letter INSCRIPTION_DEPTH deep into the back face (local z = -CAM_THICKNESS).

    # Deviation: the gallery engraves with decad.Emboss; Fusion has no emboss in the add-in API, so the letter's loops
    are extruded as a cutter from 1 mm behind the back face to the engraving depth and cut
    (docs/sevensegment/deviations.md)."""
    loops = grooves.letter_curves(segment)
    z0 = -k.CAM_THICKNESS - 1.0
    return _cut_prism(ctx, body, f"{ctx.part} engrave", loops, [], z0, 1.0 + k.INSCRIPTION_DEPTH,
                      loops_per=len(loops), only=len(loops) == 1)


def build_cam(ctx: BuildContext, segment: int) -> adsk.fusion.BRepBody:
    """[cam] Revolve the meridian (disc z -5.7 to 0, hub to 10.75), cut the double-D bore, the groove, the look-alike
    holes (the circles of one sketch, one cut) and engrave the letter, all in the cam's frame; then move it onto its
    frame, turned by theta."""
    body = _turned(ctx, f"{ctx.part} meridian", sections.cam_meridian())
    height = k.CAM_THICKNESS + 1.0 + k.CAM_HUB_TOP + 1.0
    marks = [(centre, k.CAM_MARK_RADIUS) for centre in sections.cam_mark_centres(segment)]
    z0 = -k.CAM_THICKNESS - 1.0
    body = _cut_prism(ctx, body, f"{ctx.part} cut D bore", [sections.cam_bore_loop()], [], z0, height)
    body = _cut_groove(ctx, body, segment)
    body = _cut_prism(ctx, body, f"{ctx.part} cut marks", [], marks, z0, height, count=len(marks))
    body = _inscribe(ctx, body, segment)
    body = fusion.move(ctx, body, poses.cam_axes(segment, ctx.dm.theta), f"{ctx.part} move")
    return _require_solid(ctx, body)


def _wall_chamfer(ctx: BuildContext, body: adsk.fusion.BRepBody, z: float, what: str) -> None:
    """Chamfer the outer loop of the wall's face at local z by WALL_CHAMFER."""
    found = [es for is_outer, es in fusion.face_loops(body, z, 100.0, f"{what} z={z:g}") if is_outer]
    if len(found) != 1:
        raise fusion.BuildError(f"{what}: found {len(found)} outer loops at z={z:g}, expected 1")
    fusion.chamfer(ctx, found[0], k.WALL_CHAMFER, f"{what} chamfer z={z:g}", tangent_chain=False)


def _round_rib_roots(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str) -> None:
    """Round each rib's root, the four edges of its footprint on the inner face (local z = 0), one call per rib: the
    footprints are the inner loops of that face. The ribs stand 1.5 inside the plate's edges, so none meets the
    chamfer."""
    loops = [es for is_outer, es in fusion.face_loops(body, 0.0, 100.0, f"{what} inner face") if not is_outer]
    if len(loops) != 4 or any(len(es) != 4 for es in loops):
        raise fusion.BuildError(f"{what}: found {len(loops)} rib roots, expected 4 of 4 edges")
    for i, es in enumerate(loops, start=1):
        fusion.fillet(ctx, es, k.RIB_ROUND, f"{what} round rib root {i}")


def build_wall(ctx: BuildContext, front: bool) -> adsk.fusion.BRepBody:
    """[wall] In the wall's frame (inner face at z = 0, thickness along +Z): extrude the plate, union four ribs against
    the normal, chamfer the outer loop of each face, round the rib roots, cut the fastener tools, the bearing seat and
    lip, and the look-alike holes; then move the wall onto its frame.

    The fastener tools are cut before the seat tool, as in the gallery (after the seat, the front wall's G head
    pockets meet a held mesh coarser than their chord tolerance and decad refuses them)."""
    what = ctx.part
    axes = poses.wall_axes(front)
    u0, u1, v0, v1 = sections.wall_plate()
    body = _tool_prism(ctx, f"{what} plate", sections.rect_loop(u0, u1, v0, v1), 0.0, k.WALL_THICKNESS)
    for i, ((ru0, ru1, rv0, rv1), depth) in enumerate(sections.wall_ribs(front), start=1):
        rib = _tool_prism(ctx, f"{what} rib {i}", sections.rect_loop(ru0, ru1, rv0, rv1), -depth, depth)
        body = fusion.join(ctx, body, [rib], f"{what} union rib {i}")
    _wall_chamfer(ctx, body, k.WALL_THICKNESS, what)
    _wall_chamfer(ctx, body, 0.0, what)
    _round_rib_roots(ctx, body, what)
    for index, kind in sections.wall_site_indices(front):
        label = bodies.SITE_LABELS[index]
        site = poses.site_in(ctx.dm.sites[index], axes)
        tools = [_hole(ctx, site, f"{what} {label} hole tool")]
        if kind == "G":
            tools.append(_head_pocket(ctx, site, f"{what} {label} head pocket tool"))
        else:
            tools.append(_hex_pocket(ctx, site, f"{what} {label} nut pocket tool"))
        for tool in tools:
            body = _cut(ctx, body, tool, f"{what} cut {label}")
    sk = fusion.new_sketch_xz(ctx.comp, f"{what} seat tool")
    fusion.draw_loop_xz(sk, sections.wall_seat_loop())
    profile = fusion.profile_with_loops(sk, 1, f"{what} seat tool_sketch", only=True)
    body = fusion.cut_revolve(ctx, profile, body, f"{what} cut seat")
    marks = [(centre, k.CAM_MARK_RADIUS) for centre in sections.wall_mark_centres(front)]
    body = _cut_prism(ctx, body, f"{what} cut marks", [], marks, -1.0, k.WALL_THICKNESS + 2.0, count=len(marks))
    body = fusion.move(ctx, body, axes, f"{what} move")
    return _require_solid(ctx, body)


def build_bearing(ctx: BuildContext, front: bool) -> adsk.fusion.BRepBody:
    """[ballbearing Build] The 608ZZ envelope: a ring from the bore to the outer diameter, local z 0 to the width, moved
    onto its wall's inner face, extruding into the seat. Bearings do not turn with theta."""
    body = _prism(ctx, f"{ctx.part} ring", [],
                  [(_ORIGIN, k.BEARING_OUTER / 2), (_ORIGIN, k.BEARING_BORE / 2)], 0.0, k.BEARING_WIDTH, 2)
    body = fusion.move(ctx, body, poses.bearing_axes(front), f"{ctx.part} move")
    return _require_solid(ctx, body)


def build_bolt(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw placed on the site. The bolts of one length are the same body: the first
    is built and the others are copies (see parts_flags._shared)."""
    return parts_flags._shared(ctx, f"bolt {site.length:g}", site.bolt_axes(), lambda: _build_bolt(ctx, site))


def _build_bolt(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2bolt Build] M2 socket head cap screw: revolved section, underhead fillet, hex socket; placed on the site."""
    comp = ctx.comp
    sk = fusion.new_sketch_xz(comp, "bolt section")
    fusion.draw_loop_xz(sk, fasteners.bolt_section(site.length))
    body = fusion.revolve(ctx, fusion.profile_with_loops(sk, 1, "bolt section_sketch", only=True), "bolt revolve")
    edges = fusion.circular_edges_at(body, fasteners.SHANK_DIAMETER / 2, 0.0)
    if len(edges) != 1:
        raise fusion.BuildError(f"bolt underhead_fillet: found {len(edges)} underhead edges, expected 1")
    fusion.fillet(ctx, edges, fasteners.UNDERHEAD_RADIUS, "bolt underhead_fillet")

    body = _cut_prism(ctx, body, "bolt socket_cut", [fasteners.hexagon_loop(fasteners.SOCKET_ACROSS_FLATS)], [],
                      fasteners.HEAD_HEIGHT - fasteners.SOCKET_DEPTH,
                      fasteners.SOCKET_DEPTH + fasteners.SOCKET_CUTTER_RISE)
    body = fusion.move(ctx, body, site.bolt_axes(), "bolt move")
    return _require_solid(ctx, body)


def build_nut(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut placed on the site. Every nut is the same body: the first is built and the others are
    copies (see parts_flags._shared)."""
    return parts_flags._shared(ctx, "nut", site.nut_axes(), lambda: _build_nut(ctx, site))


def _build_nut(ctx: BuildContext, site: Site) -> adsk.fusion.BRepBody:
    """[m2nut Build] M2 hex nut: hexagon with a bore, then a revolved chamfer cut on each face; placed on the site.

    # Deviation: each chamfer is one cut revolve of its section. The gallery's `hexnut` builds the chamfer body and
    # cuts it with `decad.Cut` (docs/sevensegment/deviations.md)."""
    comp = ctx.comp
    nut = _prism(ctx, "nut hexagon", [fasteners.hexagon_loop(fasteners.NUT_ACROSS_FLATS)],
                 [(_ORIGIN, fasteners.NUT_BORE_DIAMETER / 2)], 0.0, fasteners.NUT_THICKNESS, 2)
    for side, upper in (("lower", False), ("upper", True)):
        sk = fusion.new_sketch_xz(comp, f"nut {side} chamfer")
        fusion.draw_loop_xz(sk, fasteners.nut_chamfer_section(upper))
        profile = fusion.profile_with_loops(sk, 1, f"nut {side}_chamfer_sketch", only=True)
        nut = fusion.cut_revolve(ctx, profile, nut, f"nut {side}_chamfer_cut")
    nut = fusion.move(ctx, nut, site.nut_axes(), "nut move")
    return _require_solid(ctx, nut)


def shared_info(ctx: BuildContext, name: str) -> tuple[str, tuple] | None:
    """The key under which the body `name` shares its build with others (`parts_flags._shared`) and the frame it is
    moved onto, or None for a body that nothing copies."""
    if bodies.is_bolt(name):
        site = ctx.dm.sites[bodies.site_index(name)]
        return f"bolt {site.length:g}", site.bolt_axes()
    if bodies.is_nut(name):
        return "nut", ctx.dm.sites[bodies.site_index(name)].nut_axes()
    return parts_flags.shared_info(ctx, name)


def first_of_each_kind(ctx: BuildContext) -> list[str]:
    """The first body of every kind that is built once and copied, in build order: the bodies that can be built in a
    design of their own (isolate.py) and registered as the prototypes."""
    seen: set[str] = set()
    out: list[str] = []
    for name in bodies.ALL_BODY_NAMES:
        info = shared_info(ctx, name)
        if info is not None and info[0] not in seen:
            seen.add(info[0])
            out.append(name)
    return out


def build_part(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the body called `name` in the current container's component."""
    if name == bodies.FRONT_WALL:
        return build_wall(ctx, True)
    if name == bodies.REAR_WALL:
        return build_wall(ctx, False)
    if name == bodies.SHAFT:
        return build_shaft(ctx)
    if name == bodies.FRONT_BEARING:
        return build_bearing(ctx, True)
    if name == bodies.REAR_BEARING:
        return build_bearing(ctx, False)
    for s in SEGMENTS:
        if name == bodies.cam_name(s):
            return build_cam(ctx, s)
    if bodies.is_bolt(name):
        return build_bolt(ctx, ctx.dm.sites[bodies.site_index(name)])
    if bodies.is_nut(name):
        return build_nut(ctx, ctx.dm.sites[bodies.site_index(name)])
    if bodies.BODY_STAGE.get(name) == 2:
        return parts_flags.build_flag_part(ctx, name)
    if bodies.BODY_STAGE.get(name) == 3:
        return parts_clicker.build_clicker_part(ctx, name)
    raise fusion.BuildError(f"{name}: unknown body")
