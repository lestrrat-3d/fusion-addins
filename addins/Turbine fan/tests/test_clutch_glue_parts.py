"""Runs each body builder against a recording fake of the Fusion helpers: the order of cuts, the tools' sketches and
the moves onto each site. It checks the builders' own logic; the Fusion calls themselves are checked in Fusion."""

import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen.clutch import bodies
from gen.clutch.params import Params
from gen.clutch.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Turbine fan.commands.turbinefan"


class FakeBody:
    def __init__(self, what):
        self.what = what
        self.isSolid = True


class FakeFusion:
    """Stands in for the `fusion` module: every call is recorded."""

    class BuildError(RuntimeError):
        pass

    def __init__(self, fail_chamfer=False, arm_arcs=1, loops=None):
        self.calls = []
        self.moves = []
        self.cuts = []
        self.joins = []
        self.chamfers = []
        self.sketches = []
        self.fail_chamfer = fail_chamfer
        self.arm_arcs = arm_arcs
        self.loops = loops

    def new_sketch(self, comp, name):
        self.sketches.append(name)
        return name

    new_sketch_xz = new_sketch

    def draw_loop(self, sk, loop):
        self.calls.append(("draw_loop", sk, len(loop)))

    draw_loop_xz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.calls.append(("draw_circle", sk, center, radius))

    def profile_with_loops(self, sk, loops, what, only=False):
        self.calls.append(("profile", what, loops))
        return sk

    def extrude(self, ctx, profile, z, length, what):
        self.calls.append(("extrude", what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        self.calls.append(("revolve", what))
        return FakeBody(what)

    def join(self, ctx, body, tools, what):
        self.joins.append((body.what, [t.what for t in tools], what))
        return body

    def cut(self, ctx, body, tools, what):
        self.cuts.append((body.what, [t.what for t in tools], what))
        return body

    def fillet(self, ctx, edges, radius, what):
        self.calls.append(("fillet", what, len(edges), radius))

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))
        if self.fail_chamfer:
            raise self.BuildError(f"{what}: rejected")

    def move(self, ctx, body, axes, what):
        self.moves.append((body.what, axes))
        return body

    def loop_length(self, edges):
        return float(len(edges))

    def face_loops(self, body, z, min_area, what):
        if self.loops is not None:
            return self.loops
        # An outer loop of 30 edges and two inner loops: a long one (25 edges) and a short one (3 edges). The fake's
        # loop length is its edge count.
        return [(True, [object()] * 30), (False, [object()] * 25), (False, [object()] * 3)]

    def circular_edges_at(self, body, radius, z):
        return [object()] * self.arm_arcs


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
            for name in (f"{_PKG}.clutch_parts", f"{_PKG}.fusion", f"{_PKG}.clutch_build"):
                sys.modules.pop(name, None)
            importlib.import_module(f"{_PKG}.fusion")
            importlib.import_module(f"{_PKG}.clutch_build")
            parts = importlib.import_module(f"{_PKG}.clutch_parts")
        fake = FakeFusion(**kw)
        patch = mock.patch.object(parts, "fusion", fake)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.clutch_parts", f"{_PKG}.clutch_build")])
        self.fake = fake
        self.parts = parts

    def ctx(self, **changes):
        p = dataclasses.replace(Params(), **changes)
        return types.SimpleNamespace(comp=object(), p=p, dm=derive(p), log=FakeLog(), part="")

    def extrudes(self):
        return {c[1]: c[2:] for c in self.fake.calls if c[0] == "extrude"}

    # Hub

    def test_hub_605zz_is_chamfered_on_the_arm_arcs(self):
        self.load(arm_arcs=3)
        ctx = self.ctx()
        body = self.parts.build_hub(ctx)
        self.assertEqual(body.what, "hub_extrude")
        self.assertEqual(self.extrudes()["hub_extrude"], (4.25, 10.0))
        self.assertEqual(self.fake.chamfers, [("hub chamfer faces", 12, 0.25, True)])
        self.assertEqual(self.fake.cuts, [])  # no Boolean
        self.assertEqual([c for c in self.fake.calls if c[0] == "profile"], [("profile", "hub_sketch", 5)])
        self.assertEqual(ctx.log.records, [])

    def test_hub_8mm_is_chamfered_on_the_arm_arcs_and_the_d_loop(self):
        # Every hub's faces are over 400 mm^2. The 8 mm presets' D loop is 20 mm or more, so it is chamfered whole: the
        # fake's long D loop has 25 edges on each of the two faces.
        self.load(arm_arcs=3)
        ctx = self.ctx(shaft="608ZZ")
        self.parts.build_hub(ctx)
        self.assertEqual(self.fake.chamfers, [("hub chamfer faces", 12 + 2 * 25, ctx.dm.hub_chamfer, True)])
        self.assertAlmostEqual(ctx.dm.hub_chamfer, 0.212, places=3)
        self.assertEqual(ctx.log.records, [])

    def test_hub_8mm_needs_one_long_d_loop_per_face(self):
        self.load(arm_arcs=3, loops=[(True, [object()] * 30), (False, [object()] * 3)])
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_hub(self.ctx(shaft="608ZZ"))

    def test_hub_chamfer_falls_back_with_a_log_line(self):
        self.load(arm_arcs=3, fail_chamfer=True)
        ctx = self.ctx()
        self.assertEqual(self.parts.build_hub(ctx).what, "hub_extrude")
        self.assertEqual([r[0] for r in ctx.log.records], ["fallback"])
        self.assertEqual(ctx.log.records[0][1]["step"], "hub chamfer faces")

    def test_hub_needs_twelve_arm_arcs(self):
        self.load(arm_arcs=2)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_hub(self.ctx())

    # Ring

    def test_ring_order_of_operations(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_ring(ctx)
        self.assertEqual(body.what, "ring_extrude")
        self.assertEqual(self.extrudes()["ring_extrude"], (-1.25, 21.0))
        self.assertEqual(self.fake.chamfers, [("ring chamfer faces", 60, 0.5, False)])  # the outer loop of both ends
        tools = [t[0] for _, t, _ in self.fake.cuts]
        self.assertEqual(tools, ["ring back counterbore tool_revolve", "ring front counterbore tool_revolve",
                                 "ring mount nut pocket 1 tool_extrude", "ring mount nut pocket 2 tool_extrude",
                                 "ring mount nut pocket 3 tool_extrude"])
        self.assertEqual([c for c in self.fake.calls if c[0] == "profile"][0], ("profile", "ring_sketch", 5))

    def test_ring_pockets_open_through_the_rear_face(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_ring(ctx)
        moved = dict(self.fake.moves)
        for i, site in enumerate(ctx.dm.mount_sites):
            self.assertEqual(moved[f"ring mount nut pocket {i + 1} tool_extrude"], site.axes(site.cavity))
        self.assertEqual(self.extrudes()["ring mount nut pocket 1 tool_extrude"], (0.0, 3.0))  # z 0.75 to -2.25

    def test_ring_takes_only_outer_loops(self):
        self.load(loops=[(True, [object()] * 30), (True, [object()] * 30)])
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_ring(self.ctx())

    # Plates

    def test_back_plate(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_back_plate(ctx)
        self.assertEqual(self.extrudes()["back plate_extrude"], (0.0, 4.0))
        # The outer circle (30 edges) and the long inner loop (25); the 3-edge loop stays sharp.
        self.assertEqual(self.fake.chamfers, [("back plate chamfer faces", 55, 0.5, False)])
        tools = [t[0] for _, t, _ in self.fake.cuts]
        self.assertEqual(tools, ["back plate inner face tool_revolve"] + [
            f"back plate nut pocket {i} tool_extrude" for i in (1, 2, 3)])
        self.assertEqual(body.what, "back plate_extrude")
        moved = dict(self.fake.moves)
        for i, site in enumerate(ctx.dm.sites):
            self.assertEqual(moved[f"back plate nut pocket {i + 1} tool_extrude"], site.axes(site.cavity))

    def test_cover(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_cover(ctx)
        self.assertEqual(self.extrudes()["cover_extrude"], (14.5, 4.0))
        tools = [t[0] for _, t, _ in self.fake.cuts]
        self.assertEqual(tools, ["cover inner face tool_revolve"] + [
            f"cover head pocket {i} tool_extrude" for i in (1, 2, 3)])
        self.assertEqual(self.extrudes()["cover head pocket 1 tool_extrude"], (-1.0, 3.0))
        moved = dict(self.fake.moves)
        for i, site in enumerate(ctx.dm.sites):
            self.assertEqual(moved[f"cover head pocket {i + 1} tool_extrude"], site.axes())

    def test_plate_chamfer_falls_back_to_the_outer_loop(self):
        self.load(fail_chamfer=True)
        ctx = self.ctx()
        with self.assertRaises(FakeFusion.BuildError):  # the fake rejects the fallback too, so the build stops there
            self.parts.build_back_plate(ctx)
        self.assertEqual([c[:3] for c in self.fake.chamfers],
                         [("back plate chamfer faces", 55, 0.5), ("back plate chamfer outer faces", 30, 0.5)])
        self.assertEqual([r[0] for r in ctx.log.records], ["fallback"])

    def test_ring_chamfer_has_no_fallback(self):
        self.load(fail_chamfer=True)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_ring(self.ctx())
        self.assertEqual(len(self.fake.chamfers), 1)

    def test_plate_without_a_long_loop_is_an_error(self):
        self.load(loops=[(False, [object()] * 3)])
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_back_plate(self.ctx())

    # Adapter

    def test_adapter(self):
        self.load()
        ctx = self.ctx(adapter=True)
        self.parts.build_adapter(ctx)
        self.assertEqual(self.extrudes()["adapter_extrude"], (20.0, 6.0))
        self.assertEqual([c for c in self.fake.calls if c[0] == "profile"][0], ("profile", "adapter_sketch", 11))
        circles = [c for c in self.fake.calls if c[0] == "draw_circle" and c[1] == "adapter"]
        self.assertEqual(len(circles), 11)  # the outside, the bore, three ear holes, three face holes, three access
        self.assertEqual(self.fake.chamfers, [("adapter chamfer faces", 110, 0.5, False)])  # (30 + 25) on both faces
        tools = [t[0] for _, t, _ in self.fake.cuts]
        self.assertEqual(tools, [f"adapter mount head pocket {i} tool_extrude" for i in (1, 2, 3)]
                         + [f"adapter face head pocket {i} tool_extrude" for i in (1, 2, 3)])
        moved = dict(self.fake.moves)
        self.assertEqual(moved["adapter face head pocket 2 tool_extrude"], ctx.dm.face_sites[1].axes())

    # Sacrificial bridging (directive: back plate, cover and adapter ring)

    def _bridge_calls(self, build, name, what, sites, start):
        """Builds the body with the box checked and checks each layer: a disc of the hole radius plus the overlap,
        `start` along the site's direction for one printed layer, moved onto the site and joined into the body."""
        ctx = self.ctx(adapter=True, sacrificial_bridging=True)
        body = build(ctx)
        self.assertEqual(body.what, f"{what}_extrude" if what != "adapter" else "adapter_extrude")
        extrudes = self.extrudes()
        moved = dict(self.fake.moves)
        self.assertEqual(len(self.fake.joins), 3)
        for i, site in enumerate(sites(ctx.dm)):
            tool = f"{what} bridge {i + 1} tool_extrude"
            self.assertEqual(extrudes[tool], (start(site), 0.3))
            self.assertEqual(moved[tool], site.axes())
            self.assertEqual(self.fake.joins[i], (body.what, [tool], f"{what} bridge {i + 1}_join"))
        circles = [c for c in self.fake.calls if c[0] == "draw_circle" and "bridge" in c[1]]
        self.assertEqual(len(circles), 3)
        for c in circles:
            self.assertAlmostEqual(c[3], 1.4, places=9)

    def test_back_plate_bridge_layers_sit_above_the_nut_pocket_roofs(self):
        self.load()
        self._bridge_calls(self.parts.build_back_plate, bodies.BACK_PLATE, "back plate", lambda dm: dm.sites,
                           lambda s: s.cavity - 0.3)

    def test_cover_bridge_layers_sit_above_the_head_pocket_roofs(self):
        self.load()
        self._bridge_calls(self.parts.build_cover, bodies.COVER, "cover", lambda dm: dm.sites, lambda s: 2.0)

    def test_adapter_bridge_layers_sit_above_the_ear_head_pocket_roofs_only(self):
        self.load()
        self._bridge_calls(self.parts.build_adapter, bodies.ADAPTER, "adapter", lambda dm: dm.mount_sites,
                           lambda s: 2.0)

    def test_no_bridge_layers_unless_the_box_is_checked(self):
        self.load()
        ctx = self.ctx(adapter=True)
        for build in (self.parts.build_back_plate, self.parts.build_cover, self.parts.build_adapter):
            build(ctx)
        self.assertEqual(self.fake.joins, [])
        self.assertFalse([c for c in self.fake.calls if c[0] == "draw_circle" and "bridge" in c[1]])

    def test_the_hub_and_the_ring_get_no_bridge_layers(self):
        self.load(arm_arcs=3)
        ctx = self.ctx(adapter=True, sacrificial_bridging=True)
        self.parts.build_hub(ctx)
        self.parts.build_ring(ctx)
        self.assertEqual(self.fake.joins, [])

    def test_the_adapter_has_no_layers_without_the_adapter_ring(self):
        self.load()
        ctx = self.ctx(sacrificial_bridging=True)
        self.parts.build_adapter(ctx)
        self.assertEqual(self.fake.joins, [])

    # Bolts and nuts

    def test_bolt_and_nut_land_on_their_sites(self):
        self.load()
        ctx = self.ctx(adapter=True)
        for name in bodies.BOLTS + bodies.MOUNT_BOLTS:
            self.fake.moves.clear()
            self.parts.build_part(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).bolt_axes(), name)
        for name in bodies.NUTS + bodies.MOUNT_NUTS:
            self.fake.moves.clear()
            self.parts.build_part(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).nut_axes(), name)

    def test_bolt_underhead_fillet_needs_one_edge(self):
        self.load(arm_arcs=0)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_part(self.ctx(), bodies.BOLTS[0])

    def test_build_part_dispatch(self):
        self.load(arm_arcs=3)
        ctx = self.ctx(adapter=True)
        for name in bodies.body_names(True):
            with self.subTest(body=name):
                if name in bodies.BOLTS + bodies.MOUNT_BOLTS:
                    self.fake.arm_arcs = 1
                self.assertTrue(self.parts.build_part(ctx, name).isSolid)

    def test_not_solid_rejected(self):
        self.load()
        self.fake.cut = lambda ctx, body, tools, what: types.SimpleNamespace(isSolid=False)
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.parts.build_cover(self.ctx())
        self.assertIn("not a solid", str(cm.exception))


class FusionHelpersTest(unittest.TestCase):
    def load(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            sys.modules.pop(f"{_PKG}.fusion", None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
        self.addCleanup(lambda: sys.modules.pop(f"{_PKG}.fusion", None))
        return fusion

    def test_cut_logs_a_cut_that_removes_nothing(self):
        fusion = self.load()
        log = FakeLog()
        ctx = types.SimpleNamespace(log=log)
        box = types.SimpleNamespace(minPoint=types.SimpleNamespace(x=0, y=0, z=0),
                                    maxPoint=types.SimpleNamespace(x=1, y=1, z=1))
        tool = types.SimpleNamespace(preciseBoundingBox=box)
        target = types.SimpleNamespace(volume=1.0, preciseBoundingBox=box)
        result = types.SimpleNamespace(volume=1.0, preciseBoundingBox=box)
        with mock.patch.object(fusion, "_combine", return_value=result):
            self.assertIs(fusion.cut(ctx, target, [tool], "ring cut 5"), result)
        event, fields = log.records[0]
        self.assertEqual((event, fields["step"], fields["result"]), ("cut", "ring cut 5", "FAIL"))
        self.assertEqual(fields["tool_bounds"], (0.0, 0.0, 0.0, 10.0, 10.0, 10.0))
        log.records.clear()
        result = types.SimpleNamespace(volume=0.9, preciseBoundingBox=box)
        with mock.patch.object(fusion, "_combine", return_value=result):
            fusion.cut(ctx, target, [tool], "ring cut 5")
        self.assertEqual(log.records, [])

    def test_loop_length_sums_edges_in_mm(self):
        fusion = self.load()
        edges = [types.SimpleNamespace(length=1.5), types.SimpleNamespace(length=0.5)]
        self.assertAlmostEqual(fusion.loop_length(edges), 20.0)

    def test_move_returns_the_moved_body(self):
        fusion = self.load()
        moved = object()
        feat = types.SimpleNamespace(bodies=types.SimpleNamespace(count=1, item=lambda i: moved))
        feats = mock.MagicMock()
        feats.moveFeatures.add.return_value = feat
        ctx = types.SimpleNamespace(comp=types.SimpleNamespace(features=feats), placement_axes=fusion._IDENTITY_AXES)
        body = object()
        self.assertIs(fusion.move(ctx, body, ((0.0, 1.0, 0.0),) + fusion._IDENTITY_AXES[1:], "m"), moved)
        self.assertIs(fusion.move(ctx, body, fusion._IDENTITY_AXES, "m"), body)


if __name__ == "__main__":
    unittest.main()
