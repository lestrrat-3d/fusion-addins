"""The flag builders: the flag rotors (a yellow and a black body each), the sliders and the guide, cradle and top plates.

`build_flag_part(ctx, name)` builds the body called `name` in the current container's component. Like parts.py, every
profile is drawn on the XY plane of the component, extruded or revolved, and then moved once onto its plane in the model
(the frames come from `lib/gen/flags_*.py`). A rotor is built in its own local frame and moved onto its place, turned
by its angle, at the end. A body that the gallery makes in another way is described at its code site and in
docs/sevensegment/deviations.md ("Flags").
"""

from __future__ import annotations

import typing

import adsk.core
import adsk.fusion

from ...lib.gen import bodies, fasteners, frames
from ...lib.gen import flags_common as fc
from ...lib.gen import flags_pivot as fv
from ...lib.gen import flags_plates as fp
from ...lib.gen import flags_rotor as fr
from ...lib.gen import flags_slider as fs
from ...lib.gen.constants import STEM_THICKNESS, TRAVEL
from ...lib.gen.curves import Loop, Point
from ...lib.gen.truth import SEGMENTS, lit, station
from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

Circle = tuple[Point, float]
Axes = fc.Axes
_IDENTITY: Axes = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_TRAVEL = TRAVEL  # a lit slider is raised by this much (the gallery's Travel)

_SLIDERS = {bodies.slider_name(s): s for s in SEGMENTS}
_YELLOWS = {bodies.yellow_name(s): s for s in SEGMENTS}
_BLACKS = {bodies.black_name(s): s for s in SEGMENTS}
FLAG_PART_NAMES: tuple[str, ...] = tuple(n for n in bodies.ALL_BODY_NAMES if bodies.BODY_STAGE[n] == 2)


def _translate(x: float, y: float, z: float) -> Axes:
    return ((x, y, z), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _require_solid(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    if not body.isSolid:
        raise fusion.BuildError(f"{ctx.part}: result is not a solid")
    return body


def _prism(ctx: BuildContext, what: str, loops: list[Loop], circles: list[Circle], count: int, axes: Axes,
           z0: float, length: float) -> adsk.fusion.BRepBody:
    """The sketch of `loops` and `circles` (`count` loops in the profile to extrude) on the XY plane, extruded from z0
    for length along +Z, then moved onto `axes` (the plane the gallery sketches on)."""
    sk = fusion.new_sketch(ctx.comp, what)
    for loop in loops:
        fusion.draw_loop(sk, loop)
    for center, radius in circles:
        fusion.draw_circle(sk, center, radius)
    profile = fusion.profile_with_loops(sk, count, f"{what}_sketch", only=count == 1)
    body = fusion.extrude(ctx, profile, z0, length, f"{what}_extrude")
    return fusion.move(ctx, body, axes, f"{what} move")


def _poly(ctx: BuildContext, what: str, pts: list[Point], axes: Axes, z0: float, length: float):
    return _prism(ctx, what, [fc.poly_loop(pts)], [], 1, axes, z0, length)


def _flat(ctx: BuildContext, what: str, loop: Loop, z0: float, length: float) -> adsk.fusion.BRepBody:
    """A closed loop in the component's own XY plane, extruded from z0 for length."""
    return _prism(ctx, what, [loop], [], 1, _IDENTITY, z0, length)


def _cylinder(ctx: BuildContext, what: str, centre: Point, radius: float, z0: float, length: float):
    return _prism(ctx, what, [], [(centre, radius)], 1, _IDENTITY, z0, length)


def _cut_flat(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, loop: Loop, z0: float,
              length: float) -> adsk.fusion.BRepBody:
    """[cutPoly, cutPivotRoof] Cut `body` with a closed loop in the component's own XY plane, extruded from z0 for
    length, as one feature."""
    sk = fusion.new_sketch(ctx.comp, f"{what} tool")
    fusion.draw_loop(sk, loop)
    profile = fusion.profile_with_loops(sk, 1, f"{what} tool_sketch", only=True)
    return fusion.cut_extrude(ctx, profile, body, z0, length, what)


def _cut_turned(ctx: BuildContext, body: adsk.fusion.BRepBody, what: str, section: list[Point]) -> adsk.fusion.BRepBody:
    """[cutMeridian] Cut `body` with an (r, z) section revolved about the component's Z axis, as one feature."""
    sk = fusion.new_sketch_xz(ctx.comp, f"{what} tool")
    fusion.draw_loop_xz(sk, fc.poly_loop(section))
    profile = fusion.profile_with_loops(sk, 1, f"{what} tool_sketch", only=True)
    return fusion.cut_revolve(ctx, profile, body, what)


def _turned(ctx: BuildContext, what: str, section: list[Point], axes: Axes) -> adsk.fusion.BRepBody:
    """An (r, z) section revolved about the component's Z axis, then moved onto `axes`."""
    sk = fusion.new_sketch_xz(ctx.comp, what)
    fusion.draw_loop_xz(sk, fc.poly_loop(section))
    profile = fusion.profile_with_loops(sk, 1, f"{what}_sketch", only=True)
    body = fusion.revolve(ctx, profile, f"{what}_revolve")
    return fusion.move(ctx, body, axes, f"{what} move")


def _intersect(ctx: BuildContext, target: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody,
               what: str) -> adsk.fusion.BRepBody:
    """The common part of two bodies, as a new body (the gallery's decad.Intersect; both inputs are used up)."""
    try:
        inp = ctx.comp.features.combineFeatures.createInput(target, fusion._collection([tool]))
        inp.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
        inp.isKeepToolBodies = False
        feat = ctx.comp.features.combineFeatures.add(inp)
    except fusion.BuildError:
        raise
    except Exception as e:  # a Fusion API error names the step
        raise fusion.BuildError(f"{what}: {e}") from e
    if feat is None or feat.bodies.count != 1:
        raise fusion.BuildError(f"{what}: intersect produced {0 if feat is None else feat.bodies.count} bodies, "
                                "expected 1")
    return feat.bodies.item(0)


def _cut(ctx: BuildContext, body: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody,
         what: str) -> adsk.fusion.BRepBody:
    return fusion.cut(ctx, body, [tool], what)


def _join(ctx: BuildContext, body: adsk.fusion.BRepBody, tool: adsk.fusion.BRepBody,
          what: str) -> adsk.fusion.BRepBody:
    return fusion.join(ctx, body, [tool], what)


def _section_axes(yz: bool, at: float, length: float) -> tuple[Axes, float]:
    """The frame and start z of a profile drawn in (y, z) on x = at (yz) or in (x, z) on y = at; both extrude toward
    the positive axis for `length`."""
    return fc.yz_axes(at) if yz else fc.xz_axes(at, length)


# ---- the rotors ------------------------------------------------------------------------------------------------


def _rotor_solid(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[rotorSplit 1-2] The rotor in its local frame at turn 0: the pyramid tips (two prisms intersected) cut to the
    rounded square section."""
    half = fr.PRISM_LENGTH / 2
    pa = _poly(ctx, f"{ctx.part} prism A", fr.tip_prism_a(), fr.plane_a(), -half, fr.PRISM_LENGTH)
    pb = _poly(ctx, f"{ctx.part} prism B", fr.tip_prism_b(), fr.plane_b(), -half, fr.PRISM_LENGTH)
    tips = _intersect(ctx, pa, pb, f"{ctx.part} tips")
    section = _flat(ctx, f"{ctx.part} section", fr.section_loop(), fr.SECTION_FROM, fr.SECTION_LENGTH)
    return _intersect(ctx, tips, section, f"{ctx.part} rotor")


def _slab(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[rotorSplit 3] The slab T = P1 x P2 that is the yellow body's shape before it is cut to the rotor."""
    half = fr.PRISM_LENGTH / 2
    p1 = _poly(ctx, f"{ctx.part} P1", fr.slab_p1(), fr.plane_a(), -half, fr.PRISM_LENGTH)
    p2 = _poly(ctx, f"{ctx.part} P2", fr.slab_p2(), fr.plane_b(), -half, fr.PRISM_LENGTH)
    return _intersect(ctx, p1, p2, f"{ctx.part} slab")


_SHARE_TOL = 0.01  # mm: how far a copy's centre of mass may lie from where its pose puts it


def _shared(ctx: BuildContext, key: str, pose: Axes, build: typing.Callable[[], adsk.fusion.BRepBody]
            ) -> adsk.fusion.BRepBody:
    """The body of a part that the gallery builds once and copies (`decad.Copy`), posed at `pose` in the model frame.

    The first body with this `key` is built by `build` (which also moves it onto `pose`) and kept as the prototype. Each
    later one is a copy of the prototype, pasted into the current component and moved by the pose that takes the
    prototype's pose to its own: two features instead of the whole build. A copy that Fusion refuses is built instead,
    and a copy that lands off its place stops the build.

    The gallery copies in the same way (`decad.Copy`); the copy is pasted into the body's own component, because Fusion
    groups bodies only through components."""
    proto = ctx.shared.get(key)
    if proto is None:
        body = build()
        ctx.shared[key] = (body, pose)
        return body
    src, src_pose = proto
    return _require_solid(ctx, _copy_posed(ctx, src, frames.compose(pose, frames.inverse(src_pose)),
                                           f"{ctx.part}", build))


def _copy_posed(ctx: BuildContext, src: adsk.fusion.BRepBody, rel: Axes, what: str,
                build: typing.Callable[[], adsk.fusion.BRepBody]) -> adsk.fusion.BRepBody:
    """A copy of `src` pasted into the current component and moved by `rel` (a frame in the model frame). A copy that
    Fusion refuses is made by `build` instead (and logged); a copy whose centre of mass is off its place stops the
    build."""
    try:
        copy = fusion.copy_body(ctx, src, f"{what} copy")
    except fusion.BuildError as e:
        ctx.log.write("copy", [("part", what), ("error", str(e)), ("result", "FALLBACK")])
        return build()
    want = frames.apply(rel, fusion.centre_mm(src))
    copy = fusion.move(ctx, copy, rel, f"{what} move")
    got = fusion.centre_mm(copy)
    if max(abs(a - b) for a, b in zip(want, got)) > _SHARE_TOL:
        raise fusion.BuildError(f"{what}: the copy's centre is at {got}, expected {want}")
    return copy


def shared_info(ctx: BuildContext, name: str) -> tuple[str, Axes] | None:
    """The `_shared` key and pose of a flag body that is copied: a yellow body, a black body, a pivot block."""
    if name in _YELLOWS:
        return "yellow", _flag_pose(ctx, _YELLOWS[name])
    if name in _BLACKS:
        s = _BLACKS[name]
        return f"black {fr.notches(s)}", _flag_pose(ctx, s)
    if name in bodies.PIVOT_ENDS:
        s, sgn = bodies.PIVOT_ENDS[name]
        return "pivot block", fv.segment_axes(s, sgn)
    return None


def _pose(ctx: BuildContext, body: adsk.fusion.BRepBody, s: int) -> adsk.fusion.BRepBody:
    """Move the rotor from its local frame onto the model, turned by its angle at this digit."""
    return fusion.move(ctx, body, _flag_pose(ctx, s), f"{ctx.part} move")


def _flag_angle(ctx: BuildContext, s: int) -> float:
    """The turn of segment s's flag in degrees: its angle at the digit with `Params.tilt_flags`, else its print
    orientation (`fc.PRINT_TURN`: yellow face down, bed on the +Z side)."""
    return fc.flag_angle(s, ctx.dm.theta) if ctx.p.tilt_flags else fc.PRINT_TURN


def _flag_pose(ctx: BuildContext, s: int) -> Axes:
    return fc.rotor_axes(s, _flag_angle(ctx, s))


def build_yellow(ctx: BuildContext, s: int) -> adsk.fusion.BRepBody:
    """[flag] The yellow body (shared by every segment: built once, then copied and posed)."""
    return _shared(ctx, "yellow", _flag_pose(ctx, s), lambda: _build_yellow(ctx, s))


def _build_yellow(ctx: BuildContext, s: int) -> adsk.fusion.BRepBody:
    """[flag] The yellow body: the rotor's part inside the slab.

    # Deviation: the gallery builds the rotor and the slab once and copies both to get the yellow and the black body.
    The two bodies live in two components, and a Fusion combine needs its bodies in one component, so each of the two
    builds its own rotor and slab (docs/sevensegment/deviations.md, "Flags")."""
    rotor = _rotor_solid(ctx)
    slab = _slab(ctx)
    yellow = _intersect(ctx, slab, rotor, f"{ctx.part} yellow")
    return _require_solid(ctx, _pose(ctx, yellow, s))


def _pocket(ctx: BuildContext, n: tuple[float, float, float], i: int) -> adsk.fusion.BRepBody:
    """[pocketTool] A pin pocket's cutter: a stadium from z = u1 - 0.6, its floor rounded 0.5."""
    loop, z0, length = fr.pocket(n)
    what = f"{ctx.part} pocket {i} tool"
    tool = _flat(ctx, what, loop, z0, length)
    loops = [es for is_outer, es in fusion.face_loops(tool, z0 + length, 0.5, f"{what} floor") if is_outer]
    if len(loops) != 1:
        raise fusion.BuildError(f"{what}: found {len(loops)} floor loops, expected 1")
    fusion.fillet(ctx, loops[0], fr.POCKET_FLOOR_ROUND, f"{what} round the floor")
    return tool


def _notch_tool(ctx: BuildContext, u0: float, u1: float, i: int) -> adsk.fusion.BRepBody:
    """[notchTool] The two slanted profiles intersected, trimmed by the apex box."""
    half = fr.PRISM_LENGTH / 2
    prof = fr.notch_profile(u0, u1)
    sa = _poly(ctx, f"{ctx.part} notch {i} slant A", prof, fr.plane_a(), -half, fr.PRISM_LENGTH)
    sb = _poly(ctx, f"{ctx.part} notch {i} slant B", prof, fr.plane_b(), -half, fr.PRISM_LENGTH)
    tool = _intersect(ctx, sa, sb, f"{ctx.part} notch {i} slant A x B")
    (x0, x1, y0, y1), z0, length = fr.apex_box(u0, u1)
    box = _flat(ctx, f"{ctx.part} notch {i} apex box", fc.rect_loop(x0, x1, y0, y1), z0, length)
    tool = _intersect(ctx, tool, box, f"{ctx.part} notch {i} apex")
    if fr.mouth_applies(u0):
        tool = _join(ctx, tool, _mouth_tool(ctx, u0, i), f"{ctx.part} notch {i} mouth")
    return tool


def _mouth_tool(ctx: BuildContext, u0: float, i: int) -> adsk.fusion.BRepBody:
    """[mouthTool] The 0.7 mouth chamfer cutter of a notch's u0 end on hidden face 315: a triangle prism intersected with
    a wedge prism."""
    (p1, ax1, z1, len1), (p3, ax3, z3, len3) = fr.mouth_prism_sections(u0)
    what = f"{ctx.part} notch {i} mouth"
    prism = _poly(ctx, f"{what} prism", p1, ax1, z1, len1)
    taper = _poly(ctx, f"{what} taper", p3, ax3, z3, len3)
    return _intersect(ctx, prism, taper, f"{what} tool")


def build_black(ctx: BuildContext, s: int) -> adsk.fusion.BRepBody:
    """[flagBodies] The black body. It depends on the segment only through its notches, so the segments with the same
    notches (a, g, d; b, c, e, f) share one built body."""
    return _shared(ctx, f"black {fr.notches(s)}", _flag_pose(ctx, s), lambda: _build_black(ctx, s))


def _build_black(ctx: BuildContext, s: int) -> adsk.fusion.BRepBody:
    """[flagBodies] The black body: the rotor without the slab, the flat under the bottom, the notches with their pin
    pockets and, at each end, the pivot bore and its teardrop roof (see build_yellow for why the rotor and the slab are built here again)."""
    rotor = _rotor_solid(ctx)
    slab = _slab(ctx)
    body = _cut(ctx, rotor, slab, f"{ctx.part} black")
    x0, x1, y0, y1 = fr.flat_rect()
    body = _cut_flat(ctx, body, f"{ctx.part} cut flat", fc.rect_loop(x0, x1, y0, y1), fr.FLAT_FROM, fr.FLAT_LENGTH)
    for i, n in enumerate(fr.notches(s), start=1):
        body = _cut(ctx, body, _notch_tool(ctx, n[0], n[1], i), f"{ctx.part} cut notch {i}")
        body = _cut(ctx, body, _pocket(ctx, n, i), f"{ctx.part} cut pocket {i}")
    for sgn, side in ((1.0, "upper"), (-1.0, "lower")):
        body = _cut_turned(ctx, body, f"{ctx.part} cut {side} bore", fr.pivot_bore_meridian(sgn))
        # The roof's sketch frame only turns the pentagon in its plane (normal +Z), so it is drawn turned on the XY plane
        # and cut from its start z.
        pts, z0, length = fr.pivot_roof_cut(sgn)
        body = _cut_flat(ctx, body, f"{ctx.part} cut {side} roof", fc.poly_loop(pts), z0, length)
    return _require_solid(ctx, _pose(ctx, body, s))


# ---- the pivot blocks and their pockets ------------------------------------------------------------------------


def _rounded_prism(ctx: BuildContext, what: str, dims: tuple[float, float, float, float, float, float]):
    """[roundedPrism] A block or a pocket: the section prism intersected with the plan prism."""
    (sec, sec_axes, z1, len1), (plan, plan_axes, z2, len2) = fv.rounded_prism_sections(*dims)
    a = _prism(ctx, f"{what} section", [sec], [], 1, sec_axes, z1, len1)
    b = _prism(ctx, f"{what} plan", [plan], [], 1, plan_axes, z2, len2)
    return _intersect(ctx, a, b, what)


def build_pivot_block(ctx: BuildContext, s: int, sgn: float) -> adsk.fusion.BRepBody:
    """[pivotBlock, toSegment] The rounded block with its Ø1.4 pin joined, moved onto segment s's end sgn. The first one
    is built; the other 13 are copies of it, as in the gallery."""
    return _shared(ctx, "pivot block", fv.segment_axes(s, sgn), lambda: _build_pivot_block(ctx, s, sgn))


def _build_pivot_block(ctx: BuildContext, s: int, sgn: float) -> adsk.fusion.BRepBody:
    what = ctx.part
    body = _rounded_prism(ctx, f"{what} body", fv.block_dims())
    pin = _turned(ctx, f"{what} pin", fv.pin_meridian(), _IDENTITY)
    body = _join(ctx, body, pin, f"{what} union pin")
    return _require_solid(ctx, fusion.move(ctx, body, fv.segment_axes(s, sgn), f"{what} move"))


def _cut_pivot_pockets(ctx: BuildContext, body: adsk.fusion.BRepBody) -> adsk.fusion.BRepBody:
    """[cutPivotPockets] Cut every rotor end's pocket (the block's size plus PressFit) from a plate.

    The pocket tool is built once, at the origin. Each of the first 13 ends cuts a copy of it moved onto the end, and
    the last end cuts the tool itself, so no tool is left over. The gallery builds the tool again for every end.
    # Deviation: the copies (docs/sevensegment/deviations.md, "Pivot pockets")."""
    ends = list(fv.ALL_ENDS)
    first = f"{ctx.part} pivot pocket tool"
    proto = _rounded_prism(ctx, first, fv.pocket_dims())
    for i, (s, sgn) in enumerate(ends):
        what = f"{ctx.part} pivot pocket {bodies.segment_name(s)}{'+' if sgn > 0 else '-'}"
        axes = fv.segment_axes(s, sgn)
        if i == len(ends) - 1:
            tool = fusion.move(ctx, proto, axes, f"{what} move")
        else:
            tool = _copy_posed(ctx, proto, axes, what,
                               lambda: fusion.move(ctx, _rounded_prism(ctx, f"{what} tool", fv.pocket_dims()), axes,
                                                   f"{what} move"))
        body = _cut(ctx, body, tool, f"{what} cut")
    return body


# ---- the sliders -----------------------------------------------------------------------------------------------


_MATCH_TOL = 1e-3  # mm: how far an edge's end points may lie from the curve they are matched to


def _vertex_mm(v: adsk.fusion.BRepVertex) -> tuple[float, float, float]:
    g = v.geometry
    return (fusion.mm_from_cm(g.x), fusion.mm_from_cm(g.y), fusion.mm_from_cm(g.z))


def _on_stem_edge(edge: adsk.fusion.BRepEdge, se: fs.StemEdge) -> bool:
    """True when `edge` is `se` or a piece of it: a line whose end points lie on the segment, or an arc whose end points
    lie on the circle. A neighbour's chamfer trims an edge but leaves its end points on its curve."""
    if edge.geometry is None:
        return False
    pts = (_vertex_mm(edge.startVertex), _vertex_mm(edge.endVertex))
    if se.center is None:
        if edge.geometry.curveType != adsk.core.Curve3DTypes.Line3DCurveType:
            return False
        ax = [b - a for a, b in zip(se.a, se.b)]
        n2 = sum(c * c for c in ax)
        for p in pts:
            d = [q - a for q, a in zip(p, se.a)]
            k = sum(x * y for x, y in zip(d, ax)) / n2
            off = max(abs(d[i] - k * ax[i]) for i in range(3))
            if off > _MATCH_TOL or k * n2 ** 0.5 < -_MATCH_TOL or (k - 1) * n2 ** 0.5 > _MATCH_TOL:
                return False
        return True
    if edge.geometry.curveType != adsk.core.Curve3DTypes.Arc3DCurveType:
        return False
    r = sum((a - c) ** 2 for a, c in zip(se.a, se.center)) ** 0.5
    return all(abs(p[1] - se.center[1]) <= _MATCH_TOL
               and abs(sum((a - c) ** 2 for a, c in zip(p, se.center)) ** 0.5 - r) <= _MATCH_TOL for p in pts)


def _stem_run_edges(body: adsk.fusion.BRepBody, run: list[fs.StemEdge], what: str) -> list[adsk.fusion.BRepEdge]:
    """The body's edges of one run of the stem chamfer: exactly one per curve of the run."""
    found: list[adsk.fusion.BRepEdge] = []
    for se in run:
        match = [body.edges.item(i) for i in range(body.edges.count) if _on_stem_edge(body.edges.item(i), se)]
        if len(match) != 1:
            raise fusion.BuildError(f"{what}: found {len(match)} edges for a stem chamfer curve, want 1")
        found.append(match[0])
    return found


def _tongue(ctx: BuildContext, t: fs.Tongue) -> adsk.fusion.BRepBody:
    """[rootedTongue] The hull prism minus the end cutter, which has the rotor pin cut out of it first.

    # Deviation: the pin's 0.2 tip chamfer is part of the pin's revolved section; the gallery chamfers the tip edge of
    a cylinder (docs/sevensegment/deviations.md, "Flags")."""
    what = f"{ctx.part} tongue"
    axes, z0 = _section_axes(t.u_is_x, t.ua, t.hull_length)
    hull = _prism(ctx, f"{what} hull", [fs.tongue_outline(t.sl, t.sr, t.sc, t.zp)], [], 1, axes, z0, t.hull_length)
    axes, z0 = _section_axes(not t.u_is_x, t.cutter_at, t.cutter_length)
    cutter = _poly(ctx, f"{what} end cutter", fs.tongue_cutter(t.ue, t.zp), axes, z0, t.cutter_length)
    if t.u_is_x:  # the pin runs along +X from its face, at (sc, zp)
        pin_axes: Axes = ((t.pin_at, t.sc, t.zp), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    else:  # along +Y, at (sc, zp)
        pin_axes = ((t.sc, t.pin_at, t.zp), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    pin = _turned(ctx, f"{what} pin", fs.flag_pin_meridian(), pin_axes)
    cutter = _cut(ctx, cutter, pin, f"{what} cutter minus pin")
    return _cut(ctx, hull, cutter, f"{what} end cut")


def _chamfer_stem(ctx: BuildContext, body: adsk.fusion.BRepBody, s: int, what: str) -> None:
    """The stem's 0.5 chamfers: every long run of the outer loops of its two large faces (fs.stem_chamfer_runs).

    All runs are tried at once; when Fusion refuses that, each run alone, and when it refuses a run, each edge of it alone.
    An edge Fusion still refuses is skipped and logged. The edges are found again each time on the current body, because
    a chamfer replaces the edge it was made on and trims its neighbours."""
    runs = fs.stem_chamfer_runs(s)
    edges = [e for run in runs for e in _stem_run_edges(body, run, what)]
    try:
        fusion.chamfer(ctx, edges, fs.STEM_CHAMFER, f"{what} stem chamfers", tangent_chain=False)
        return
    except fusion.BuildError:
        pass
    for i, run in enumerate(runs):
        try:
            fusion.chamfer(ctx, _stem_run_edges(body, run, what), fs.STEM_CHAMFER, f"{what} stem chamfer run {i}",
                           tangent_chain=False)
            continue
        except fusion.BuildError:
            pass
        for j, se in enumerate(run):
            try:
                fusion.chamfer(ctx, _stem_run_edges(body, [se], what), fs.STEM_CHAMFER,
                               f"{what} stem chamfer run {i} edge {j}", tangent_chain=False)
            except fusion.BuildError as e:
                ctx.log.write("skipped_chamfer", [("part", what), ("run", i), ("edge", j), ("error", str(e)[:120])])


def build_slider(ctx: BuildContext, s: int) -> adsk.fusion.BRepBody:
    """[flagSlider] One slider at the unlit build pose, raised by TRAVEL when its segment is lit at this digit.

    # Deviation: the gallery's sketch rounds are drawn into the outline as arcs (lib/gen/flags_common.rounded_loop)
    instead of sketch fillets."""
    yi = station(s)
    what = ctx.part
    if fs.is_agd(s):
        axes = fc.plane_axes((-fs.STEM_HALF_AGD, yi, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        body = _prism(ctx, f"{what} profile", [fs.agd_loop()], [], 1, axes, 0.0, fs.AGD_THICK)
    else:
        axes, z0 = fc.xz_axes(yi - STEM_THICKNESS / 2, fs.BF_THICK)
        body = _prism(ctx, f"{what} profile", [fs.bf_loop(s)], [], 1, axes, z0, fs.BF_THICK)
        length = fs.BLADE_EXT_LENGTH + fs.BLADE_EXT_OVERLAP
        axes, z0 = fc.xz_axes(yi + STEM_THICKNESS / 2 - fs.BLADE_EXT_OVERLAP, length)
        ext = _poly(ctx, f"{what} blade extension", fs.blade_extension(s), axes, z0, length)
        body = _join(ctx, body, ext, f"{what} union blade extension")
    # Deviation: the stem chamfer is made on the profile prism, before the tongue and pin are joined, and leaves the runs
    # that reach the blade or the tongue sharp. Fusion refused the chamfer after the unions (ASM_BL_END_TOO_CMPLX at the
    # chain ends). A refused run or edge is skipped, because the chamfer is cosmetic (docs/sevensegment/deviations.md,
    # "Flags").
    _chamfer_stem(ctx, body, s, what)
    body = _join(ctx, body, _tongue(ctx, fs.tongue_for(s)), f"{what} union tongue")
    pin_axes: Axes = ((0.0, yi + STEM_THICKNESS / 2, fs.SLIDER_PIN_Z), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    pin = _turned(ctx, f"{what} groove pin", fs.groove_pin_meridian(), pin_axes)
    body = _join(ctx, body, pin, f"{what} union groove pin")
    if lit(ctx.dm.digit, s):
        body = fusion.move(ctx, body, _translate(0.0, 0.0, _TRAVEL), f"{what} lift")
    return _require_solid(ctx, body)


# ---- the plates ------------------------------------------------------------------------------------------------


def _chamfer_outer(ctx: BuildContext, body: adsk.fusion.BRepBody, z: float, what: str) -> None:
    """Chamfer the outer loop of the plate's face at z by 0.5 [edgefinish.Chamfer, Long(Outer)]."""
    found = [es for is_outer, es in fusion.face_loops(body, z, 100.0, f"{what} z={z:g}") if is_outer]
    if len(found) != 1:
        raise fusion.BuildError(f"{what}: found {len(found)} outer loops at z={z:g}, expected 1")
    fusion.chamfer(ctx, found[0], 0.5, f"{what} chamfer z={z:g}", tangent_chain=False)


def _hex_pocket(ctx: BuildContext, site: fasteners.Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener HexPocketTool] As in parts.py, for a site given in the model frame."""
    tool = _flat(ctx, what, fasteners.hexagon_by_radius(fasteners.NUT_CAVITY_RADIUS), 0.0,
                 fasteners.NUT_CAVITY_HEIGHT + fasteners.STOCK)
    return fusion.move(ctx, tool, site.axes(site.cavity), f"{what} move")


def _head_pocket(ctx: BuildContext, site: fasteners.Site, what: str) -> adsk.fusion.BRepBody:
    """[m2fastener PocketTool] As in parts.py, for a site given in the model frame."""
    tool = _cylinder(ctx, what, (0.0, 0.0), fasteners.HEAD_POCKET_RADIUS, -fasteners.STOCK,
                     fasteners.STOCK + fasteners.HEAD_POCKET_DEPTH)
    return fusion.move(ctx, tool, site.axes(), f"{what} move")


def _rooted(ctx: BuildContext, what: str, sections: tuple) -> adsk.fusion.BRepBody:
    """A rooted box or post: its two prisms (an x-z polygon extruded along y, a y-z polygon along x), intersected."""
    (px, y_at, y_len), (py, x_at, x_len) = sections
    axes, z0 = fc.xz_axes(y_at, y_len)
    sx = _poly(ctx, f"{what} x", px, axes, z0, y_len)
    axes, z0 = fc.yz_axes(x_at)
    sy = _poly(ctx, f"{what} y", py, axes, z0, x_len)
    return _intersect(ctx, sx, sy, what)


def _peg(ctx: BuildContext, what: str, section: list[Point], at: Point, z: float) -> adsk.fusion.BRepBody:
    return _turned(ctx, what, section, _translate(at[0], at[1], z))


def build_guide_plate(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[columnGuidePlate] The guide plate: z 81 to 87 with seven slots and four G holes, outer chamfers and the nut
    pockets, then two columns with a registration peg each."""
    what = ctx.part
    x0, x1, y0, y1 = fp.plate_rect()
    g_sites = ctx.dm.sites[4:8]
    loops = [fc.rect_loop(x0, x1, y0, y1)] + [fp.slot_loop(station(s)) for s in SEGMENTS]
    circles = [((st.head[0], st.head[1]), fasteners.HOLE_RADIUS) for st in g_sites]
    body = _prism(ctx, f"{what} plate", loops, circles, 1 + len(SEGMENTS) + len(g_sites), _IDENTITY, fp.GUIDE_FROM,
                  fp.GUIDE_THICK)
    for z in (fp.GUIDE_FROM, fp.GUIDE_FROM + fp.GUIDE_THICK):
        _chamfer_outer(ctx, body, z, what)
    for i, st in enumerate(g_sites, start=1):
        body = _cut(ctx, body, _hex_pocket(ctx, st, f"{what} nut pocket {i} tool"), f"{what} cut nut pocket {i}")
    for i, (p, h) in enumerate(zip(fp.COLUMN_PEGS, fp.COLUMN_HALF), start=1):
        col = _rooted(ctx, f"{what} column {i}", fp.rooted_post_sections(
            p[0] - h[0], p[0] + h[0], p[1] - h[1], p[1] + h[1], fp.COLUMN_FROM, fp.COLUMN_TOP, 0.1, 0.5))
        body = _join(ctx, body, col, f"{what} union column {i}")
        peg = _peg(ctx, f"{what} column peg {i}", fp.column_peg_meridian(), p, fp.COLUMN_TOP)
        body = _join(ctx, body, peg, f"{what} union column peg {i}")
    return _require_solid(ctx, body)


def _bores(ctx: BuildContext, body: adsk.fusion.BRepBody, axis_z: float) -> adsk.fusion.BRepBody:
    for s in SEGMENTS:
        tool = _turned(ctx, f"{ctx.part} bore {bodies.slider_name(s)[-1]} tool", fp.bore_meridian(),
                       fp.bore_axes(s, axis_z))
        body = _cut(ctx, body, tool, f"{ctx.part} cut bore {bodies.slider_name(s)[-1]}")
    return body


def build_cradle_plate(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[cradlePlate] z 120.0 to 124.0 with the four T holes, four registration holes, seven passages, seven rotor bores
    cut at the axis, two mouth cones for the top plate's pegs and the outer-loop chamfers."""
    what = ctx.part
    x0, x1, y0, y1 = fp.plate_rect()
    circles: list[Circle] = [((st.head[0], st.head[1]), fasteners.HOLE_RADIUS) for st in ctx.dm.sites[:4]]
    circles += [(p, fp.PEG_HOLE) for p in fp.COLUMN_PEGS + fp.TOP_PEGS]
    body = _prism(ctx, f"{what} plate", [fc.rect_loop(x0, x1, y0, y1)], circles, 1 + len(circles), _IDENTITY,
                  fp.CRADLE_FROM, fp.CRADLE_THICK)
    for s in SEGMENTS:
        name = bodies.slider_name(s)[-1]
        px0, px1, py0, py1 = fp.cradle_passage(s, station(s))
        tool = _flat(ctx, f"{what} passage {name} tool", fc.rect_loop(px0, px1, py0, py1, fp.PASSAGE_ROUND),
                     fp.PASSAGE_FROM, fp.PASSAGE_LENGTH)
        body = _cut(ctx, body, tool, f"{what} cut passage {name}")
    body = _bores(ctx, body, fc.ROTOR_AXIS_Z)
    body = _cut_pivot_pockets(ctx, body)
    for i, p in enumerate(fp.TOP_PEGS, start=1):
        cone = _turned(ctx, f"{what} mouth cone {i} tool", fp.cone_meridian(fp.CRADLE_FROM + fp.CRADLE_THICK),
                       _translate(p[0], p[1], 0.0))
        body = _cut(ctx, body, cone, f"{what} cut mouth cone {i}")
    for z in (fp.CRADLE_FROM, fp.CRADLE_FROM + fp.CRADLE_THICK):
        _chamfer_outer(ctx, body, z, what)
    return _require_solid(ctx, body)


def build_top_plate(ctx: BuildContext) -> adsk.fusion.BRepBody:
    """[flagTopPlate] 8.0 thick from z 124.25 to the display face, with seven tubes hanging from its underside, the rotor
    bores, the windows and T holes, the registration pegs, the blade holes, the outer chamfers and the head pockets.

    # Deviation: the gallery cuts the windows and the T holes from one sketch, one profile at a time; each tool here is
    its own sketch (docs/sevensegment/deviations.md, "Flags")."""
    what = ctx.part
    x0, x1, y0, y1 = fp.plate_rect()
    body = _flat(ctx, f"{what} plate", fc.rect_loop(x0, x1, y0, y1), fp.TOP_FROM, fp.TOP_THICK)
    for s in SEGMENTS:
        name = bodies.slider_name(s)[-1]
        t = fp.tube_footprint(s, station(s))
        tube = _rooted(ctx, f"{what} tube {name}", fp.rooted_box_sections(
            t[0], t[1], t[2], t[3], fp.TUBE_FROM, fp.TOP_FROM, 0.1, 0.5))
        body = _join(ctx, body, tube, f"{what} union tube {name}")
    body = _bores(ctx, body, fp.TOP_FROM)
    body = _cut_pivot_pockets(ctx, body)
    for s in SEGMENTS:
        name = bodies.slider_name(s)[-1]
        tool = _flat(ctx, f"{what} window {name} tool", fp.window_loop(s), fp.WINDOW_FROM, fp.WINDOW_LENGTH)
        body = _cut(ctx, body, tool, f"{what} cut window {name}")
    for i, st in enumerate(ctx.dm.sites[:4], start=1):
        tool = _cylinder(ctx, f"{what} T hole {i} tool", (st.head[0], st.head[1]), fasteners.HOLE_RADIUS,
                         fp.WINDOW_FROM, fp.WINDOW_LENGTH)
        body = _cut(ctx, body, tool, f"{what} cut T hole {i}")
    for i, p in enumerate(fp.TOP_PEGS, start=1):
        peg = _peg(ctx, f"{what} peg {i}", fp.top_peg_meridian(), p, fp.TOP_FROM)
        body = _join(ctx, body, peg, f"{what} union peg {i}")
    for s in SEGMENTS:
        name = bodies.slider_name(s)[-1]
        h = fp.blade_hole(s, station(s))
        tool = _flat(ctx, f"{what} blade hole {name} tool", fc.rect_loop(h[0], h[1], h[2], h[3], fp.BLADE_HOLE_ROUND),
                     fp.BLADE_HOLE_FROM, fp.BLADE_HOLE_TOP - fp.BLADE_HOLE_FROM)
        body = _cut(ctx, body, tool, f"{what} cut blade hole {name}")
    for z in (fp.TOP_FROM, fc.FLAG_FACE_Z):
        _chamfer_outer(ctx, body, z, what)
    for i, st in enumerate(ctx.dm.sites[:4], start=1):
        body = _cut(ctx, body, _head_pocket(ctx, st, f"{what} head pocket {i} tool"), f"{what} cut head pocket {i}")
    return _require_solid(ctx, body)


# ---- dispatch --------------------------------------------------------------------------------------------------


def build_flag_part(ctx: BuildContext, name: str) -> adsk.fusion.BRepBody:
    """Build the flag or plate body called `name` in the current container's component."""
    if name == bodies.GUIDE_PLATE:
        return build_guide_plate(ctx)
    if name == bodies.CRADLE_PLATE:
        return build_cradle_plate(ctx)
    if name == bodies.TOP_PLATE:
        return build_top_plate(ctx)
    if name in _SLIDERS:
        return build_slider(ctx, _SLIDERS[name])
    if name in _YELLOWS:
        return build_yellow(ctx, _YELLOWS[name])
    if name in _BLACKS:
        return build_black(ctx, _BLACKS[name])
    if name in bodies.PIVOT_ENDS:
        return build_pivot_block(ctx, *bodies.PIVOT_ENDS[name])
    raise fusion.BuildError(f"{name}: not a flag or plate body")
