"""Runs each body builder against a recording fake of the Fusion helpers: the order of cuts, the tools' sketches and
the moves onto each site. It checks the builders' own logic; the Fusion calls themselves are checked in Fusion."""

import dataclasses
import importlib
import math
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import blade, bodies
from gen.constants import CLUTCH_MOUNT, LEFT_HAND
from gen.params import default_params
from gen.validate import derive

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

    def __init__(self, fail_fillet=False, corner_edges=3):
        self.calls = []
        self.moves = []
        self.cuts = []
        self.joins = []
        self.sketches = []
        self.sections = []
        self.lofts = []
        self.patterns = []
        self.fail_fillet = fail_fillet
        self.corner_edges = corner_edges
        self.chamfers = []
        self.filleted = []

    def new_sketch(self, comp, name):
        self.sketches.append(name)
        return name

    new_sketch_xz = new_sketch

    def new_sketch_at_z(self, comp, name, z):
        self.sketches.append(name)
        return (name, z)

    def draw_loop(self, sk, loop):
        self.calls.append(("draw_loop", sk, len(loop)))

    draw_loop_xz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.calls.append(("draw_circle", sk, center, radius))

    def draw_section(self, sk, pts, z):
        self.sections.append((sk, len(pts), z))

    def profile_with_loops(self, sk, loops, what, only=False):
        self.calls.append(("profile", what, loops))
        return what

    def extrude(self, ctx, profile, z, length, what):
        self.calls.append(("extrude", what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        self.calls.append(("revolve", what))
        return FakeBody(what)

    def loft(self, ctx, profiles, what):
        self.lofts.append(list(profiles))
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append((body.what, [t.what for t in tools], what))
        return body

    def join(self, ctx, body, tools, what):
        self.joins.append((body.what, [t.what for t in tools]))
        return body

    def fillet(self, ctx, edges, radius, what):
        self.filleted.append((what, len(edges), radius))
        if self.fail_fillet:
            raise self.BuildError(f"{what}: rejected")

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))

    def move(self, ctx, body, axes, what):
        self.moves.append((body.what, axes))
        return body

    def pattern(self, ctx, body, count, what):
        self.patterns.append((body.what, count))
        return [body] + [FakeBody(f"{what} copy {i}") for i in range(1, count)]

    def face_loops(self, body, z, min_area, what):
        return [(True, [object()]), (False, [object()])]

    def long_loop_edges(self, body, z, min_area, min_length, what):
        return [object()] * 2

    def z_edges_at(self, body, points):
        return [object()] * self.corner_edges

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

    def extrudes(self):
        return {c[1]: c[2:] for c in self.fake.calls if c[0] == "extrude"}

    def test_hub_cuts_in_the_gallery_order(self):
        self.load()
        body = self.parts.build_hub(self.ctx())
        self.assertEqual(body.what, "hub extrude")
        self.assertEqual(self.fake.chamfers, [("hub chamfer faces", 4, 0.5, False)])
        names = [tools[0] for _, tools, _ in self.fake.cuts]
        self.assertEqual(names, [
            "socket tool_extrude", "socket tool pattern copy 1", "socket tool pattern copy 2",
            "hub blade 1 head pocket tool_extrude", "hub blade 1 nut slot tool_extrude",
            "hub blade 2 head pocket tool_extrude", "hub blade 2 nut slot tool_extrude",
            "hub blade 3 head pocket tool_extrude", "hub blade 3 nut slot tool_extrude",
            "hub counterbore tool_revolve", "hub set screw hole tool_extrude", "hub set screw nut slot tool_extrude",
            "hub adapter bolt 1 hole tool_extrude", "hub adapter bolt 1 nut slot tool_extrude",
            "hub adapter bolt 2 hole tool_extrude", "hub adapter bolt 2 nut slot tool_extrude",
        ])
        self.assertEqual(len(names), 16)
        self.assertEqual(self.fake.patterns, [("socket tool_extrude", 3)])

    def test_hub_outline_has_the_bore_and_three_bolt_holes(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_hub(ctx)
        circles = [c for c in self.fake.calls if c[0] == "draw_circle" and c[1] == "hub outline"]
        self.assertEqual([c[3] for c in circles], [18.9, 1.3, 1.3, 1.3])  # the hub's radius at the default 192 mm
        self.assertEqual([c[2] for c in circles][1:], [(s.head[0], s.head[1]) for s in ctx.dm.blade_sites])
        self.assertIn(("draw_loop", "hub outline", 2), self.fake.calls)  # the D bore: an arc and its flat
        self.assertIn(("profile", "hub outline_sketch", 5), self.fake.calls)  # the outline and four holes

    def test_hub_tools_start_and_length(self):
        self.load()
        self.parts.build_hub(self.ctx(rotor_diameter=128.0))
        e = self.extrudes()
        self.assertEqual(e["hub extrude"], (0.0, 20.0))
        self.assertEqual(e["socket tool_extrude"], (0.0, 9.3))  # from y 5.7 out to 1 past the rim
        self.assertEqual(e["hub blade 1 head pocket tool_extrude"], (-1.0, 3.0))
        self.assertEqual(e["hub blade 1 nut slot tool_extrude"], (0.0, 2.0))
        self.assertEqual(e["hub set screw hole tool_extrude"], (-1.0, 10.0))  # 1 + tip 8 + 1
        self.assertEqual(e["hub set screw nut slot tool_extrude"], (0.0, 2.0))
        self.assertEqual(e["hub adapter bolt 1 hole tool_extrude"], (-1.0, 14.0))

    def test_hub_tools_start_and_length_at_192(self):
        self.load()
        self.parts.build_hub(self.ctx())
        e = self.extrudes()
        self.assertEqual(e["hub extrude"], (0.0, 30.0))
        self.assertAlmostEqual(e["socket tool_extrude"][1], 18.9 + 1 - 7.695)  # from the floor out to 1 past the rim
        self.assertEqual(e["hub blade 1 head pocket tool_extrude"], (-1.0, 3.0))
        self.assertEqual(e["hub blade 1 nut slot tool_extrude"], (0.0, 2.0))
        self.assertEqual(e["hub set screw hole tool_extrude"], (-1.0, 14.0))  # 1 + tip 12 (M2 x 10) + 1
        self.assertEqual(e["hub adapter bolt 1 hole tool_extrude"], (-1.0, 14.0))  # the clutch's adapter: no change

    def test_tools_move_onto_their_sites_at_192(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_hub(ctx)
        moved = dict(self.fake.moves)
        socket = moved["socket tool_extrude"]
        self.assertAlmostEqual(socket[0][1], 7.695)
        self.assertEqual((socket[0][2], socket[1:]), (15.0, ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))))
        origin = moved["hub blade 2 nut slot tool_extrude"][0]
        self.assertAlmostEqual(origin[2], 3.4)  # 30 - (24.6 + 2)
        # The slot's reach runs from the bolt's line (12.825 from the axis) out past the rim: 18.9 + 1 - 12.825.
        slot = [c for c in self.fake.calls if c[0] == "draw_loop" and "blade 2 nut slot" in c[1]]
        self.assertTrue(slot)

    def test_tools_move_onto_their_sites(self):
        self.load()
        ctx = self.ctx(rotor_diameter=128.0)
        self.parts.build_hub(ctx)
        moved = dict(self.fake.moves)
        dm = ctx.dm
        self.assertEqual(moved["socket tool_extrude"],
                         ((0.0, 5.7, 10.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
        b = dm.blade_sites[1]
        self.assertEqual(moved["hub blade 2 head pocket tool_extrude"], b.axes())
        # the blade nut slot: z = 20 - (15.6 + 2) = 2.4, along the radial line
        origin, x, y, z = moved["hub blade 2 nut slot tool_extrude"]
        self.assertAlmostEqual(origin[2], 2.4)
        self.assertEqual((origin[:2], x, z), (b.head[:2], b.corner, (0.0, 0.0, 1.0)))
        self.assertAlmostEqual(y[0], -b.corner[1])
        self.assertAlmostEqual(y[1], b.corner[0])
        # the adapter slot: z = -6.25 + 7.75 = 1.5
        self.assertAlmostEqual(moved["hub adapter bolt 2 nut slot tool_extrude"][0][2], 1.5)
        self.assertEqual(moved["hub adapter bolt 1 hole tool_extrude"], dm.adapter_sites[0].axes())
        self.assertEqual(moved["hub set screw hole tool_extrude"], dm.set_screw_site.axes())

    # Sacrificial bridging (directive: the hub, front face down, in both mounts)

    def test_hub_bridge_layers_are_discs_above_each_pocket_and_slot_roof(self):
        self.load()
        ctx = self.ctx(sacrificial_bridging=True)
        self.parts.build_hub(ctx)
        extrudes = self.extrudes()
        moved = dict(self.fake.moves)
        layers = self.parts.bridge.hub_layers(ctx.p, ctx.dm)
        self.assertEqual(len(layers), 8)
        self.assertEqual(len(self.fake.joins), 8)
        for i, layer in enumerate(layers, start=1):
            tool = f"hub bridge {i} tool_extrude"
            self.assertEqual(extrudes[tool], (layer.start, 0.3))
            self.assertEqual(moved[tool], layer.site.axes())
            self.assertEqual(self.fake.joins[i - 1], ("hub extrude", [tool]))
        circles = [c for c in self.fake.calls if c[0] == "draw_circle" and "bridge" in c[1]]
        self.assertEqual(len(circles), 8)
        for c in circles:
            self.assertAlmostEqual(c[3], 1.4, places=9)

    def test_hub_bridge_layers_follow_the_cuts(self):
        self.load()
        ctx = self.ctx(sacrificial_bridging=True)
        order = []
        cut, join = self.fake.cut, self.fake.join
        self.fake.cut = lambda *a: order.append("cut") or cut(*a)
        self.fake.join = lambda *a: order.append("join") or join(*a)
        self.parts.build_hub(ctx)
        self.assertEqual(order, ["cut"] * order.count("cut") + ["join"] * 8)

    def test_no_hub_bridge_layers_unless_the_box_is_checked(self):
        self.load()
        for changes in ({}, {"mount": CLUTCH_MOUNT}):
            self.fake.joins.clear()
            self.parts.build_hub(self.ctx(**changes))
            self.assertEqual(self.fake.joins, [])
        self.assertFalse([c for c in self.fake.calls if c[0] == "draw_circle" and "bridge" in c[1]])

    def test_the_blades_get_no_bridge_layers(self):
        self.load()
        ctx = self.ctx(sacrificial_bridging=True)
        self.parts.build_blades(ctx)
        self.assertFalse([c for c in self.fake.calls if "bridge" in str(c)])
        self.assertTrue(all("bridge" not in str(j) for j in self.fake.joins))

    def test_set_screw_slot_and_counterbore_frames(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_hub(ctx)
        moved = dict(self.fake.moves)
        fb = ctx.dm.bore_flat
        self.assertEqual(moved["hub set screw nut slot tool_extrude"],
                         ((0.0, -(fb + 1.6), 4.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)))
        origin, x, y, z = moved["hub counterbore tool_revolve"]
        self.assertAlmostEqual(origin[1], -11.55)  # the floor at rho_f (7.55 at 128 mm)
        self.assertEqual((origin[0], origin[2], x, y, z), (0.0, 4.0, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))
        # every edge of both slot faces: two faces with one outer loop each
        self.assertIn(("hub set screw nut slot tool round_faces", 2, 0.5), self.fake.filleted)
        self.assertIn(("hub blade 1 nut slot tool round_corners", 3, 0.5), self.fake.filleted)
        self.assertIn(("socket tool round_start", 1, 0.5), self.fake.filleted)

    def test_a_rejected_round_falls_back_with_a_log_line(self):
        self.load(fail_fillet=True)
        ctx = self.ctx()
        self.parts.build_hub(ctx)
        steps = [r[1]["step"] for r in ctx.log.records]
        self.assertEqual({r[0] for r in ctx.log.records}, {"fallback"})
        self.assertIn("socket tool round_start", steps)
        self.assertEqual(len(self.fake.cuts), 16)

    def test_slot_corner_edges_must_be_three(self):
        self.load(corner_edges=2)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_hub(self.ctx())

    def test_blades(self):
        # (rotor diameter, stud start, stud end, bolt circle, stud radius, hub mid): the stud's cutter starts 2 mm past
        # the stud's radius from its axis and the blade turns into place about (0, 0, hub mid).
        for d, start, end, at, radius, mid in ((128.0, 6.1, 16.0, 9.5, 3.0, 10.0),
                                               (192.0, 8.095, 21.6, 12.825, 4.05, 15.0)):
            with self.subTest(d=d):
                self.setUp()
                self.load()
                ctx = self.ctx(rotor_diameter=d)
                bladies = self.parts.build_blades(ctx)
                self.assertEqual(len(bladies), 3)
                self.assertEqual([round(s[2], 9) for s in self.fake.sections],
                                 [round(st.r, 9) for st in blade.stations_for(ctx.dm.size)])
                self.assertTrue(all(n == 21 for _, n, _ in self.fake.sections))
                self.assertEqual(len(self.fake.lofts), 1)
                self.assertEqual(len(self.fake.lofts[0]), 10)
                # the default pitch is the drawn pitch: no turn; then the stud's hole and the move into the hub frame
                self.assertEqual([what for what, _ in self.fake.moves], ["blade stud hole tool_extrude", "blade loft"])
                self.assertEqual(self.fake.chamfers, [("blade stud chamfer", 1, 0.3, False)])
                self.assertEqual(self.fake.cuts,
                                 [("blade stud_extrude", ["blade stud hole tool_extrude"], "blade stud cut")])
                self.assertEqual(self.fake.joins, [("blade loft", ["blade stud_extrude"])])
                self.assertEqual(self.fake.patterns, [("blade loft", 3)])
                e = self.extrudes()
                self.assertAlmostEqual(e["blade stud_extrude"][0], start)
                self.assertAlmostEqual(e["blade stud_extrude"][1], end - start)
                # The hole's cutter is 2 (radius + 2) long, from -(radius + 2) about the stud's axis.
                self.assertAlmostEqual(e["blade stud hole tool_extrude"][1], 2 * (radius + 2))
                axes = self.fake.moves[0][1]
                self.assertAlmostEqual(axes[0][1], -(radius + 2))
                self.assertAlmostEqual(axes[0][2], at)
                self.assertEqual(self.fake.moves[-1][1], ((0.0, 0.0, mid), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)))

    def test_blade_is_turned_to_the_pitch_before_the_stud_joins(self):
        self.load()
        self.parts.build_blades(self.ctx(blade_pitch=math.radians(40)))
        what, axes = self.fake.moves[0]
        self.assertEqual(what, "blade loft")
        turn = math.radians(15)
        self.assertAlmostEqual(axes[1][0], math.cos(turn))
        self.assertAlmostEqual(axes[1][1], math.sin(turn))
        self.assertEqual(axes[3], (0.0, 0.0, 1.0))
        self.assertEqual(len(self.fake.moves), 3)

    def test_left_hand_blade_draws_unflipped_sections_and_turns_the_other_way(self):
        self.load()
        seen = []
        original = self.fake.draw_section
        self.fake.draw_section = lambda sk, pts, z: (seen.append(pts), original(sk, pts, z))
        ctx = self.ctx(hand=LEFT_HAND, blade_pitch=math.radians(40))
        self.parts.build_blades(ctx)
        sz = ctx.dm.size
        self.assertEqual(seen[0], blade.fit_points(blade.stations_for(sz)[0], True, sz))
        axes = self.fake.moves[0][1]
        self.assertAlmostEqual(axes[1][1], -math.sin(math.radians(15)))

    def test_bolt_and_nut_land_on_their_sites(self):
        self.load()
        ctx = self.ctx(mount=CLUTCH_MOUNT)
        for name in bodies.bolts(CLUTCH_MOUNT):
            self.fake.moves.clear()
            self.parts.build_fastener(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).bolt_axes(), name)
        for name in bodies.nuts(CLUTCH_MOUNT):
            self.fake.moves.clear()
            self.parts.build_fastener(ctx, name)
            self.assertEqual(self.fake.moves[-1][1], bodies.site_of(name, ctx.dm).nut_axes(), name)

    def test_bolt_underhead_fillet_needs_one_edge(self):
        self.load()
        self.fake.circular_edges_at = lambda *a: []
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_fastener(self.ctx(), "Blade Bolt 1")

    def test_every_fastener_builds(self):
        self.load()
        ctx = self.ctx()
        for name in bodies.body_names(0)[4:]:
            with self.subTest(body=name):
                self.assertTrue(self.parts.build_fastener(ctx, name).isSolid)

    def test_not_solid_rejected(self):
        self.load()
        self.fake.cut = lambda ctx, body, tools, what: types.SimpleNamespace(isSolid=False)
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.parts.build_hub(self.ctx())
        self.assertIn("not a solid", str(cm.exception))


class FusionHelperTest(unittest.TestCase):
    """The helpers added to the shared ones: pattern, loft, section sketch, section plane and edge finders."""

    def load(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            sys.modules.pop(f"{_PKG}.fusion", None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
        self.addCleanup(lambda: sys.modules.pop(f"{_PKG}.fusion", None))
        return fusion

    def test_pattern_returns_the_input_first(self):
        fusion = self.load()
        body, b2, b3 = object(), object(), object()
        feat = types.SimpleNamespace(bodies=types.SimpleNamespace(count=3, item=lambda i: (body, b2, b3)[i]))
        comp = mock.MagicMock()
        comp.features.circularPatternFeatures.add.return_value = feat
        fusion.adsk.core.ObjectCollection.create.side_effect = lambda: _Collection()
        got = fusion.pattern(types.SimpleNamespace(comp=comp), body, 3, "p")
        self.assertEqual(got, [body, b2, b3])
        with self.assertRaises(fusion.BuildError):
            fusion.pattern(types.SimpleNamespace(comp=comp), body, 4, "p")

    def test_loft_checks_the_body_count(self):
        fusion = self.load()
        comp = mock.MagicMock()
        inp = comp.features.loftFeatures.createInput.return_value
        comp.features.loftFeatures.add.return_value = types.SimpleNamespace(
            bodies=types.SimpleNamespace(count=1, item=lambda i: "body"))
        profiles = [types.SimpleNamespace(parentSketch=types.SimpleNamespace(isLightBulbOn=True)) for _ in range(3)]
        self.assertEqual(fusion.loft(types.SimpleNamespace(comp=comp), profiles, "loft"), "body")
        self.assertEqual([c.args[0] for c in inp.loftSections.add.call_args_list], profiles)
        self.assertTrue(inp.isSolid)
        self.assertEqual([p.parentSketch.isLightBulbOn for p in profiles], [False, False, False])
        comp.features.loftFeatures.add.return_value = types.SimpleNamespace(bodies=types.SimpleNamespace(count=2))
        with self.assertRaises(fusion.BuildError):
            fusion.loft(types.SimpleNamespace(comp=comp), profiles[:2], "loft")

    def test_section_plane_is_offset_along_the_normal_and_checked(self):
        fusion = self.load()
        for normal in (1.0, -1.0):
            comp = mock.MagicMock()
            comp.xYConstructionPlane.geometry = types.SimpleNamespace(
                origin=types.SimpleNamespace(z=0.0), normal=types.SimpleNamespace(z=normal))
            made = types.SimpleNamespace(geometry=types.SimpleNamespace(
                origin=types.SimpleNamespace(z=2.5), normal=types.SimpleNamespace(z=normal)))
            comp.constructionPlanes.add.return_value = made
            fusion.new_sketch_at_z(comp, "s", 25.0)
            fusion.adsk.core.ValueInput.createByReal.assert_called_with(2.5 * normal)
            self.assertFalse(made.isLightBulbOn)
            comp.sketches.add.assert_called_with(made)
        made.geometry.origin.z = 2.0
        with self.assertRaises(fusion.BuildError) as cm:
            fusion.new_sketch_at_z(comp, "s", 25.0)
        self.assertIn("off z = 25", str(cm.exception))

    def test_section_shares_the_spline_ends_with_the_lines(self):
        fusion = self.load()
        sk = mock.MagicMock()
        sk.modelToSketchSpace.side_effect = lambda p: p
        sk.sketchPoints.add.side_effect = lambda p: ("sp", p)
        fusion.adsk.core.ObjectCollection.create.side_effect = lambda: _Collection()
        pts = [(float(i), float(i * i)) for i in range(5)]
        fusion.draw_section(sk, pts, 30.0)
        spline_points = sk.sketchCurves.sketchFittedSplines.add.call_args.args[0].items
        self.assertEqual(len(spline_points), 5)
        first, last = spline_points[0], spline_points[-1]
        self.assertEqual(first[0], "sp")
        self.assertEqual(last[0], "sp")
        lines = [c.args for c in sk.sketchCurves.sketchLines.addByTwoPoints.call_args_list]
        self.assertEqual(lines[0][0], last)
        self.assertEqual(lines[1][1], first)
        self.assertEqual(lines[0][1], lines[1][0])  # both lines meet at the tail point
        self.assertEqual(lines[0][1][0], "sp")

    def test_z_edges_at_picks_the_corner_edges(self):
        fusion = self.load()

        def edge(a, b):
            return types.SimpleNamespace(
                geometry=object(),
                startVertex=types.SimpleNamespace(geometry=types.SimpleNamespace(x=a[0] / 10, y=a[1] / 10, z=a[2] / 10)),
                endVertex=types.SimpleNamespace(geometry=types.SimpleNamespace(x=b[0] / 10, y=b[1] / 10, z=b[2] / 10)))

        edges = [edge((1, 2, 0), (1, 2, 2)), edge((1, 2, 0), (3, 2, 0)), edge((5, 5, 0), (5, 5, 2)),
                 edge((1, 2, 0), (1, 2, 0.5))]
        body = types.SimpleNamespace(edges=types.SimpleNamespace(count=4, item=lambda i: edges[i]))
        self.assertEqual(fusion.z_edges_at(body, [(1.0, 2.0)]), [edges[0]])

    def test_long_loop_edges_keeps_the_long_loops(self):
        fusion = self.load()
        short, long_ = [types.SimpleNamespace(length=0.5)], [types.SimpleNamespace(length=2.0)]
        with mock.patch.object(fusion, "face_loops", return_value=[(True, long_), (False, short)]):
            self.assertEqual(fusion.long_loop_edges(object(), 0.0, 100.0, 20.0, "w"), long_)
            self.assertEqual(fusion.long_loop_edges(object(), 0.0, 100.0, 60.0, "w"), [])


class _Collection:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def contains(self, item):
        return item in self.items


if __name__ == "__main__":
    unittest.main()
