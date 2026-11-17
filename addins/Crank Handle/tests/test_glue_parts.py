"""Runs each body builder against a recording fake of the Fusion helpers: the order of cuts, the tools' sketches and
the moves onto each site. It checks the builders' own logic; the Fusion calls themselves are checked in Fusion."""

import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Crank Handle.commands.crankhandle"


class FakeBody:
    def __init__(self, what):
        self.what = what
        self.isSolid = True


class FakeFusion:
    """Stands in for the `fusion` module: every call is recorded as (function, what)."""

    class BuildError(RuntimeError):
        pass

    def __init__(self, fail_fillet=False, floor_edges=6, fail_rim_chamfer=False):
        self.calls = []
        self.moves = []
        self.cuts = []
        self.joins = []
        self.sketches = []
        self.fail_fillet = fail_fillet
        self.floor_edges = floor_edges
        self.chamfers = []
        self.fail_rim_chamfer = fail_rim_chamfer
        self.rim_calls = []
        self.outer_calls = []
        self.filleted = []

    def new_sketch(self, comp, name):
        self.sketches.append(name)
        return name

    new_sketch_xz = new_sketch
    new_sketch_yz = new_sketch

    def draw_loop(self, sk, loop):
        self.calls.append(("draw_loop", sk, len(loop)))

    draw_loop_xz = draw_loop
    draw_loop_yz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.calls.append(("draw_circle", sk, center, radius))

    def draw_rectangle(self, sk, a, b):
        self.calls.append(("draw_rectangle", sk, a, b))

    def profile_with_loops(self, sk, loops, what, only=False):
        return sk

    def extrude(self, ctx, profile, z, length, what):
        self.calls.append(("extrude", what, z, length))
        return FakeBody(what)

    def extrude_symmetric(self, ctx, profile, length, what):
        self.calls.append(("extrude_symmetric", what, length))
        return FakeBody(what)

    def outer_face_edges(self, body, outer_z, top_z, top_y, ramp_foot, pin_y, pin_hole_r, what):
        self.outer_calls.append((outer_z, top_z, top_y, ramp_foot, pin_y, pin_hole_r))
        return [object()] * 3, [object()]

    def revolve(self, ctx, profile, what):
        self.calls.append(("revolve", what))
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append((body.what, [t.what for t in tools], what))
        return body

    def join(self, ctx, body, tools, what):
        self.joins.append((body.what, [t.what for t in tools]))
        return body

    def fillet(self, ctx, edges, radius, what):
        self.filleted.append((what, len(edges), radius))
        if self.fail_fillet and "round_floor" in what:
            raise self.BuildError(f"{what}: rejected")

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))
        if self.fail_rim_chamfer and "rim" in what:
            raise self.BuildError(f"{what}: rejected")

    def bore_rim_edges(self, body, radius, what, want_lines=1):
        self.rim_calls.append((getattr(body, "what", None), radius, what, want_lines))
        return [object()] * 3

    def move(self, ctx, body, axes, what):
        self.moves.append((body.what, axes))
        return body

    def face_loops(self, body, z, min_area, what):
        if body.what.startswith("arm") and "tool" not in body.what:
            return [(True, [object()] * 6), (False, [object()])]
        return [(True, [object()] * self.floor_edges)]

    def circular_edges_at(self, body, radius, z):
        return [object()]


class FakeLog:
    enabled = True

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


class PartsTest(unittest.TestCase):
    def load(self, **kw):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            for name in (f"{_PKG}.parts", f"{_PKG}.fusion", f"{_PKG}.build"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            build = importlib.import_module(f"{_PKG}.build")
            parts = importlib.import_module(f"{_PKG}.parts")
        fake = FakeFusion(**kw)
        fusion_patch = mock.patch.object(parts, "fusion", fake)
        fusion_patch.start()
        self.addCleanup(fusion_patch.stop)
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.parts", f"{_PKG}.build")])
        self.fake = fake
        self.parts = parts
        return fusion, build

    def ctx(self, **changes):
        p = dataclasses.replace(default_params(), **changes)
        return types.SimpleNamespace(comp=object(), p=p, dm=derive(p), log=FakeLog(), part="")

    def test_arm_cuts_in_the_gallery_order(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_arm(ctx)
        self.assertEqual(body.what, "arm extrude")
        self.assertEqual(self.fake.chamfers, [
            ("arm chamfer faces", 12, 0.5, False),
            ("arm outer face chamfer", 3, 0.5, False),
            ("arm ramp top chamfer", 1, 0.5, False),
            ("arm bore rim chamfer", 3, 0.5, False),
        ])
        self.assertEqual(self.fake.outer_calls, [(8.0, 17.0, 10.0, ctx.dm.ramp_foot, 55.0, 1.3)])
        self.assertEqual(self.fake.rim_calls, [("arm extrude", ctx.dm.bore_radius, "arm bore rim", 1)])
        cuts = [tools for _, tools, _ in self.fake.cuts]
        self.assertEqual(len(cuts), 11)  # the rim chamfer runs after the last cut
        self.assertEqual([t[0] for t in cuts], [
            "arm relief tool_extrude",
            "arm slit tool_extrude", "arm bore tool_extrude", "arm pocket tool_extrude",
            "arm pin head pocket tool_extrude",
            "arm clamp 1 nut pocket tool_extrude", "arm clamp 1 head pocket tool_extrude",
            "arm clamp 1 hole tool_extrude",
            "arm clamp 2 nut pocket tool_extrude", "arm clamp 2 head pocket tool_extrude",
            "arm clamp 2 hole tool_extrude",
        ])
        self.assertEqual(self.fake.joins, [])

    def test_no_bridge_layer_unless_the_box_is_checked(self):
        self.load()
        self.parts.build_arm(self.ctx())
        self.assertEqual(self.fake.joins, [])

    def test_bridge_layer_sits_on_the_head_pockets_roof(self):
        self.load()
        ctx = self.ctx(sacrificial_bridging=True)
        self.parts.build_arm(ctx)
        self.assertEqual(self.fake.joins, [("arm extrude", ["arm bridge 1_extrude"])])
        extrudes = {c[1]: c[2:] for c in self.fake.calls if c[0] == "extrude"}
        self.assertEqual(extrudes["arm bridge 1_extrude"], (2.0, 0.3))
        circles = [c for c in self.fake.calls if c[0] == "draw_circle" and c[1] == "arm bridge 1"]
        self.assertEqual([c[2] for c in circles], [(0.0, 55.0)])
        self.assertAlmostEqual(circles[0][3], 1.4)  # the 1.3 hole and 0.1 of wall
        self.assertEqual(len(self.fake.cuts), 11)  # the layer is joined, not a cut

    def test_pin_has_no_bridge_layer(self):
        self.load()
        self.parts.build_pin(self.ctx(sacrificial_bridging=True))
        self.assertEqual(self.fake.joins, [("pin stub_extrude", ["pin turned_revolve"])])

    def test_double_flat_rim_has_three_lines(self):
        self.load()
        ctx = self.ctx(double_flat=True)
        self.parts.build_arm(ctx)
        self.assertEqual(self.fake.rim_calls[0][3], 3)

    def test_arm_tools_start_and_length(self):
        self.load()
        self.parts.build_arm(self.ctx())
        extrudes = {c[1]: c[2:] for c in self.fake.calls if c[0] == "extrude"}
        self.assertEqual(extrudes["arm extrude"], (0.0, 17.0))
        self.assertEqual(extrudes["arm slit tool_extrude"], (-1.0, 19.0))
        self.assertEqual(extrudes["arm bore tool_extrude"], (-1.0, 17.0))  # to z = 16, 1 mm of floor
        self.assertEqual(extrudes["arm pocket tool_extrude"], (3.25, 5.75))
        self.assertEqual(extrudes["arm pin head pocket tool_extrude"], (-1.0, 3.0))
        for i in (1, 2):
            # 4 mm to the face, 1 mm of stock
            self.assertEqual(extrudes[f"arm clamp {i} nut pocket tool_extrude"], (0.0, 5.0))
            # to 1 mm past the tip, 18 from the head
            self.assertEqual(extrudes[f"arm clamp {i} hole tool_extrude"], (-1.0, 20.0))
        symmetric = [c[1:] for c in self.fake.calls if c[0] == "extrude_symmetric"]
        self.assertEqual(symmetric, [("arm relief tool_extrude", 22.0)])  # x from -11 to 11

    def test_arm_clamp_tools_move_onto_the_clamp_sites(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_arm(ctx)
        moved = {what: axes for what, axes in self.fake.moves}
        for i, site in enumerate(ctx.dm.clamp_sites, start=1):
            self.assertEqual(moved[f"arm clamp {i} hole tool_extrude"], site.axes())
            self.assertEqual(moved[f"arm clamp {i} head pocket tool_extrude"], site.axes())
            self.assertEqual(moved[f"arm clamp {i} nut pocket tool_extrude"], site.axes(site.cavity))
        self.assertEqual([z for _, _, z in ((m, 0, a[0][2]) for m, a in self.fake.moves
                                            if "clamp" in m and "hole" in m)], [4.0, 12.0])
        self.assertEqual(self.fake.filleted, [("arm clamp 1 nut pocket tool round_floor", 6, 0.6),
                                              ("arm clamp 2 nut pocket tool round_floor", 6, 0.6)])

    def test_floor_round_falls_back_with_a_log_line(self):
        self.load(fail_fillet=True)
        ctx = self.ctx()
        self.parts.build_arm(ctx)
        self.assertEqual([r[0] for r in ctx.log.records], ["fallback", "fallback"])
        self.assertIn("round_floor", ctx.log.records[0][1]["step"])
        self.assertEqual(len(self.fake.cuts), 11)

    def test_rim_chamfer_falls_back_with_a_log_line(self):
        self.load(fail_rim_chamfer=True)
        ctx = self.ctx()
        self.parts.build_arm(ctx)
        self.assertEqual([r[0] for r in ctx.log.records], ["fallback"])
        self.assertEqual(ctx.log.records[0][1]["step"], "arm bore rim chamfer")

    def test_floor_edges_must_be_six(self):
        fusion, _ = self.load(floor_edges=5)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_arm(self.ctx())

    def test_pin_cuts(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_pin(ctx)
        self.assertEqual(self.fake.joins, [("pin stub_extrude", ["pin turned_revolve"])])
        names = [tools[0] for _, tools, _ in self.fake.cuts]
        self.assertEqual(len(names), 4 + 2 + 3 * 2)
        self.assertEqual(names[:4], ["pin flat 1 extrude"] * 2 + ["pin flat 2 extrude"] * 2)
        self.assertEqual(names[4:6], ["pin bolt hole tool_revolve", "pin bolt cavity tool_revolve"])
        self.assertEqual(names[6:9], ["pin cross 1 hole tool_extrude", "pin cross 1 head pocket tool_extrude",
                                     "pin cross 1 nut pocket tool_extrude"])
        self.assertEqual(body.what, "pin stub_extrude")
        moved = dict(self.fake.moves)
        self.assertEqual(moved["pin turned_revolve"][0], (0.0, 55.0, 0.0))
        self.assertEqual(moved["pin bolt hole tool_revolve"], ctx.dm.site.axes())
        self.assertEqual(moved["pin cross 2 nut pocket tool_extrude"],
                         ctx.dm.cross_sites[1].axes(ctx.dm.cross_sites[1].cavity))

    def test_pin_flats(self):
        self.load()
        self.parts.build_pin(self.ctx())
        rects = [c for c in self.fake.calls if c[0] == "draw_rectangle"]
        # Each cross bolt's two flats: +Y beyond 4 mm from the pin axis at 55, then -Y.
        self.assertEqual([(c[2][1], c[3][1]) for c in rects], [(59.0, 62.0), (48.0, 51.0)] * 2)

    def test_handle_moves_to_the_pin_axis(self):
        self.load()
        body = self.parts.build_handle(self.ctx(throw=80.0))
        self.assertEqual(body.what, "handle_revolve")
        self.assertEqual(self.fake.moves[0][1][0], (0.0, 80.0, 0.0))

    def test_bolt_and_nut_land_on_their_sites(self):
        self.load()
        ctx = self.ctx()
        for name in bodies.BOLTS:
            self.fake.moves.clear()
            self.parts.build_part(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).bolt_axes(), name)
        for name in bodies.NUTS:
            self.fake.moves.clear()
            self.parts.build_part(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).nut_axes(), name)

    def test_bolt_underhead_fillet_needs_one_edge(self):
        self.load()
        self.fake.circular_edges_at = lambda *a: []
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_part(self.ctx(), bodies.PIN_BOLT)

    def test_cut_logs_a_cut_that_removes_nothing(self):
        fusion, _ = self.load()
        log = FakeLog()
        ctx = types.SimpleNamespace(log=log)
        box = types.SimpleNamespace(minPoint=types.SimpleNamespace(x=0, y=0, z=0),
                                    maxPoint=types.SimpleNamespace(x=1, y=1, z=1))
        tool = types.SimpleNamespace(preciseBoundingBox=box)
        for after, want in ((1.0, 1), (0.9, 0)):
            log.records.clear()
            target = types.SimpleNamespace(volume=1.0, preciseBoundingBox=box)
            result = types.SimpleNamespace(volume=after, preciseBoundingBox=box)
            with mock.patch.object(fusion, "_combine", return_value=result):
                self.assertIs(fusion.cut(ctx, target, [tool], "pin cut 5"), result)
            self.assertEqual(len(log.records), want)
        # the no-op case: the last pass is 0 lines; rerun it to read the line
        target = types.SimpleNamespace(volume=1.0, preciseBoundingBox=box)
        result = types.SimpleNamespace(volume=1.0, preciseBoundingBox=box)
        log.records.clear()
        with mock.patch.object(fusion, "_combine", return_value=result):
            fusion.cut(ctx, target, [tool], "pin cut 5")
        event, fields = log.records[0]
        self.assertEqual((event, fields["step"], fields["result"]), ("cut", "pin cut 5", "FAIL"))
        self.assertEqual(fields["tool_bounds"], (0.0, 0.0, 0.0, 10.0, 10.0, 10.0))

    def _plane(self, origin_y, normal_y):
        return types.SimpleNamespace(
            geometry=types.SimpleNamespace(origin=types.SimpleNamespace(y=origin_y),
                                           normal=types.SimpleNamespace(y=normal_y)))

    def _comp(self, base, made_origin_y=None, count=2):
        comp = mock.MagicMock()
        comp.xZConstructionPlane = base
        made = self._plane(made_origin_y, base.geometry.normal.y) if made_origin_y is not None else None
        comp.constructionPlanes.add.return_value = made
        item = lambda i: types.SimpleNamespace(
            boundingBox=types.SimpleNamespace(minPoint=types.SimpleNamespace(y=[7.0, 5.0][i]),
                                              maxPoint=types.SimpleNamespace(y=[9.0, 5.4][i])), name="", i=i)
        comp.features.splitBodyFeatures.add.return_value = types.SimpleNamespace(
            bodies=types.SimpleNamespace(count=count, item=item))
        return comp, made

    def test_split_body_offsets_the_xz_plane_to_the_pin_axis(self):
        fusion, _ = self.load()
        for normal in (1.0, -1.0):
            # The plane is at y = 0 and the pin axis at 55 mm = 5.5 cm; the offset runs along the normal.
            comp, made = self._comp(self._plane(0.0, normal), made_origin_y=5.5)
            ctx = types.SimpleNamespace(comp=comp)
            halves = fusion.split_body(ctx, object(), 55.0, "Pin split")
            inp = comp.constructionPlanes.createInput.return_value
            offset = inp.setByOffset.call_args.args[1]
            self.assertEqual(offset, fusion.adsk.core.ValueInput.createByReal.return_value)
            fusion.adsk.core.ValueInput.createByReal.assert_called_with(5.5 * normal)
            # the half whose box centre is lower in y comes first
            self.assertEqual([h.i for h in halves], [1, 0])
            self.assertFalse(made.isLightBulbOn)

    def test_split_body_uses_the_base_plane_when_it_is_already_there(self):
        fusion, _ = self.load()
        comp, _ = self._comp(self._plane(5.5, 1.0))
        fusion.split_body(types.SimpleNamespace(comp=comp), object(), 55.0, "Pin split")
        comp.constructionPlanes.add.assert_not_called()

    def test_split_body_checks_the_plane_and_the_count(self):
        fusion, _ = self.load()
        comp, _ = self._comp(self._plane(0.0, 1.0), made_origin_y=5.0)
        with self.assertRaises(fusion.BuildError) as cm:
            fusion.split_body(types.SimpleNamespace(comp=comp), object(), 55.0, "Pin split")
        self.assertIn("off y = 55", str(cm.exception))
        comp, _ = self._comp(self._plane(5.5, 1.0), count=3)
        with self.assertRaises(fusion.BuildError) as cm:
            fusion.split_body(types.SimpleNamespace(comp=comp), object(), 55.0, "Pin split")
        self.assertIn("expected 2", str(cm.exception))
        comp, _ = self._comp(self._plane(0.0, 0.5))
        with self.assertRaises(fusion.BuildError):
            fusion.split_body(types.SimpleNamespace(comp=comp), object(), 55.0, "Pin split")

    def test_move_returns_the_moved_body(self):
        fusion, _ = self.load()
        moved = object()
        feat = types.SimpleNamespace(bodies=types.SimpleNamespace(count=1, item=lambda i: moved))
        feats = mock.MagicMock()
        feats.moveFeatures.add.return_value = feat
        ctx = types.SimpleNamespace(comp=types.SimpleNamespace(features=feats), placement_axes=fusion._IDENTITY_AXES)
        body = object()
        self.assertIs(fusion.move(ctx, body, ((0.0, 1.0, 0.0),) + fusion._IDENTITY_AXES[1:], "m"), moved)
        self.assertIs(fusion.move(ctx, body, fusion._IDENTITY_AXES, "m"), body)

    def test_build_part_dispatch(self):
        self.load()
        ctx = self.ctx()
        for name in bodies.BODY_NAMES:
            with self.subTest(body=name):
                self.assertTrue(self.parts.build_part(ctx, name).isSolid)

    def test_not_solid_rejected(self):
        self.load()
        self.fake.cut = lambda ctx, body, tools, what: types.SimpleNamespace(isSolid=False)
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.parts.build_arm(self.ctx())
        self.assertIn("not a solid", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
