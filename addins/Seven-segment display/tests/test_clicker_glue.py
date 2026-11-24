"""Runs each click-indexer builder against recording fakes of the Fusion helpers: the order of the features, the tools'
sketches, the teeth calls and the move onto each frame. It checks the builders' own logic; the Fusion calls themselves
are checked in Fusion."""

import importlib
import math
import sys
import types
import unittest
from dataclasses import replace
from unittest import mock

import _support  # noqa: F401

from gen import bodies, clicker_params as cp, clicker_teeth as ct, poses
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"
_MODULES = ("parts", "parts_clicker", "fusion", "fusion_clicker")


class FakeBody:
    def __init__(self, what, solid=True):
        self.what = what
        self.isSolid = solid


class FakeFusion:
    class BuildError(RuntimeError):
        pass

    def __init__(self):
        self.calls = []
        self.sketches = []
        self.profiles = []
        self.extrudes = []
        self.joins = []
        self.cuts = []
        self.moves = []
        self.chamfers = []
        self.loops = {}

    def new_sketch(self, comp, name):
        self.sketches.append(name)
        return name

    new_sketch_xz = new_sketch

    def draw_loop(self, sk, loop):
        self.loops[sk] = loop
        self.calls.append(("draw_loop", sk))

    draw_loop_xz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.calls.append(("draw_circle", sk, center, radius))

    def profile_with_loops(self, sk, loops, what, only=False):
        self.profiles.append((what, loops, only))
        return sk

    def profiles_with_loops(self, sk, loops, count, what, only=True):
        self.profiles.append((what, loops, only))
        return [sk] * count

    def cut_extrude(self, ctx, profiles, body, z, length, what):
        self.extrudes.append((what, z, length))
        self.cuts.append((what, len(profiles)))
        return FakeBody(what)

    def extrude(self, ctx, profile, z, length, what):
        self.extrudes.append((what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        self.calls.append(("revolve", what))
        return FakeBody(what)

    def join(self, ctx, body, tools, what):
        self.joins.append((what, len(tools)))
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append((what, tools[0].what))
        return FakeBody(what)

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))

    def move(self, ctx, body, axes, what):
        self.moves.append((what, axes))
        return FakeBody(what)

    def face_loops(self, body, z, min_area, what, tol=1e-3):
        return [(True, [object()] * 2), (False, [object()] * 2)]


class FakeClicker:
    """Stands in for `fusion_clicker`."""

    def __init__(self):
        self.paths = []
        self.prisms = []
        self.intersects = []
        self.patterns = []
        self.planes = []
        self.circles = []
        self.lofts = []

    def axis_path(self, ctx, length, what):
        self.paths.append((what, length))
        return what

    def twisted_prism(self, ctx, profile, path, length, twist, cap_angle, what):
        self.prisms.append((what, length, twist, cap_angle))
        return FakeBody(what)

    def intersect(self, ctx, target, tool, what):
        self.intersects.append((what, target.what, tool.what))
        return FakeBody(what)

    def pattern(self, ctx, body, count, what):
        self.patterns.append((what, count))
        return [FakeBody(f"{what} {i}") for i in range(count)]

    def plane_through_axis(self, ctx, angle, what):
        self.planes.append(angle)
        return ("plane", angle)

    def circle_profile(self, ctx, plane, centre, radius, what):
        self.circles.append((plane, centre, radius))
        return what

    def loft(self, ctx, profiles, what):
        self.lofts.append((what, len(profiles)))
        return FakeBody(what)


class ClickerPartsTest(unittest.TestCase):
    def setUp(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        patch = mock.patch.dict(sys.modules, fakes)
        patch.start()
        self.addCleanup(patch.stop)
        path = mock.patch.object(sys, "path", [_ADDINS] + sys.path)
        path.start()
        self.addCleanup(path.stop)
        for name in _MODULES:
            sys.modules.pop(f"{_PKG}.{name}", None)
        self.pc = importlib.import_module(f"{_PKG}.parts_clicker")
        self.parts = importlib.import_module(f"{_PKG}.parts")
        self.addCleanup(lambda: [sys.modules.pop(f"{_PKG}.{n}", None) for n in _MODULES])

    def build(self, name, digit=2):
        fake = FakeFusion()
        fc = FakeClicker()
        p = replace(default_params(), digit=digit)
        ctx = types.SimpleNamespace(comp=None, p=p, dm=derive(p), log=mock.MagicMock(), part=name)
        with mock.patch.object(self.pc, "fusion", fake), mock.patch.object(self.pc, "fc", fc), \
                mock.patch.object(self.parts, "fusion", fake):
            body = self.pc.build_clicker_part(ctx, name)
        return body, fake, fc

    def test_names_are_the_clicker_bodies(self):
        stage3 = tuple(n for n, s in bodies.BODY_STAGE.items() if s == 3)
        self.assertEqual(set(self.pc.CLICKER_PART_NAMES), set(stage3))
        self.assertEqual(len(self.pc.CLICKER_PART_NAMES), 5)
        for name in stage3:
            self.assertTrue(bodies.BODY_CONTAINER[name].startswith("Click Indexer/"))

    def test_every_part_builds_a_solid_and_moves_once(self):
        for name in self.pc.CLICKER_PART_NAMES:
            body, f, _ = self.build(name)
            self.assertTrue(body.isSolid)
            self.assertEqual(f.moves[-1][0], f"{name} move")
            # Only the housing moves tools (its two bolts' holes and pockets) before the body's own move.
            self.assertEqual(len(f.moves), 5 if name == "Housing" else 1)

    def test_an_unknown_name_is_refused(self):
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.build("Shaft")
        self.assertIn("not a click-indexer body", str(cm.exception))

    def test_moves_onto_the_frames_and_turns_with_the_shaft(self):
        for digit in (0, 3, 9):
            theta = 36.0 * digit
            moves = {name: self.build(name, digit)[1].moves[-1][1] for name in self.pc.CLICKER_PART_NAMES}
            self.assertEqual(moves["Hub"], cp.hub_axes(theta))
            self.assertEqual(moves["Rotor"], cp.rotor_axes(theta))
            self.assertEqual(moves["Spring"], cp.spring_axes(theta))
            self.assertEqual(moves["Housing"], cp.housing_axes())
            self.assertEqual(moves["Button"], cp.button_axes())

    def test_hub_order(self):
        _, f, _ = self.build("Hub")
        self.assertIn(("revolve", "Hub meridian_revolve"), f.calls)
        self.assertEqual(f.joins, [("Hub join keys", 3)])
        self.assertEqual(f.cuts, [("Hub cut D bore", 1)])
        extr = {e[0]: e[1:] for e in f.extrudes}
        for i in (1, 2, 3):
            z, length = extr[f"Hub key {i}_extrude"]
            self.assertAlmostEqual(z, 3.0)
            self.assertAlmostEqual(length, 6.4)
        self.assertEqual(extr["Hub cut D bore"], (-1.0, 5.5))

    def test_rotor_order(self):
        _, f, fc = self.build("Rotor")
        self.assertEqual(f.chamfers, [("Rotor chamfer z=-1.5", 2, 0.5, False)])
        self.assertEqual(f.cuts, [("Rotor cut slots", 3)])
        self.assertEqual(f.joins, [("Rotor inner join teeth", 10), ("Rotor outer join teeth", 10)])
        self.assertEqual(fc.patterns, [("Rotor inner teeth", 10), ("Rotor outer teeth", 10)])
        self.assertEqual(fc.intersects, [("Rotor inner tooth", "Rotor inner rising prism", "Rotor inner falling prism"),
                                         ("Rotor outer tooth", "Rotor outer rising prism",
                                          "Rotor outer falling prism")])
        extr = {e[0]: e[1:] for e in f.extrudes}
        z, length = extr["Rotor cut slots"]
        self.assertAlmostEqual(z, -7.5)
        self.assertAlmostEqual(length, 6.0)

    def test_rotor_prisms_carry_the_ring_specs(self):
        _, _, fc = self.build("Rotor")
        got = {p[0]: p[1:] for p in fc.prisms}
        inner, outer = ct.rotor_inner_teeth(), ct.rotor_outer_teeth()
        rising = got["Rotor inner rising prism"]
        self.assertAlmostEqual(rising[0], inner.top)
        self.assertAlmostEqual(rising[1], inner.rise_twist)
        self.assertAlmostEqual(rising[2], ct.cap_angle(inner, ct.ROTOR_INNER_SHIFT, True))
        falling = got["Rotor outer falling prism"]
        self.assertAlmostEqual(falling[0], outer.top)
        self.assertAlmostEqual(falling[1], outer.fall_twist)
        self.assertAlmostEqual(falling[2], ct.cap_angle(outer, ct.ROTOR_OUTER_SHIFT, False))

    def test_rotor_sectors_are_drawn_at_the_shift(self):
        _, f, _ = self.build("Rotor")
        loop = f.loops["Rotor inner rising sector"]
        arcs = [c for c in loop if hasattr(c, "center")]
        self.assertAlmostEqual(math.degrees(math.atan2(arcs[0].start[1], arcs[0].start[0])), ct.ROTOR_INNER_SHIFT,
                               places=4)

    def test_housing_order(self):
        _, f, fc = self.build("Housing")
        self.assertEqual(f.cuts[0], ("Housing cut slots", 3))
        self.assertEqual(f.joins, [("Housing crown join teeth", 10)])
        self.assertEqual(fc.patterns, [("Housing crown teeth", 10)])
        self.assertEqual([c[0] for c in f.cuts[1:]], ["Housing cut H1", "Housing cut H1", "Housing cut H2",
                                                      "Housing cut H2"])
        self.assertEqual(f.extrudes[-1][0].split(" ")[1], "H2")

    def test_housing_bolt_tools_are_in_the_housing_frame(self):
        _, f, _ = self.build("Housing")
        moves = dict(f.moves)
        origin = moves["Housing H1 hole tool move"][0]
        axes = cp.housing_axes()
        site = poses.site_in(derive(default_params()).sites[8], axes)
        self.assertEqual(origin, site.axes()[0])

    def test_button_order(self):
        _, f, fc = self.build("Button")
        self.assertEqual(f.joins[:3], [(f"Button join key {i}", 2) for i in (1, 2, 3)])
        self.assertEqual(f.joins[3], ("Button join teeth", 10))
        self.assertEqual(fc.patterns, [("Button teeth", 10)])
        got = {p[0]: p[1:] for p in fc.prisms}
        self.assertAlmostEqual(got["Button rising prism"][1], ct.button_teeth().rise_twist)

    def test_spring_is_a_loft_through_the_wire_circles(self):
        _, f, fc = self.build("Spring")
        self.assertEqual(fc.lofts, [("Spring coil", 53)])
        self.assertEqual(len(fc.circles), 53)
        # Angle and angle + 180 share a plane: four planes through the axis.
        self.assertEqual(sorted(fc.planes), [0.0, 45.0, 90.0, 135.0])
        for _, centre, radius in fc.circles:
            self.assertAlmostEqual(radius, 0.3)
            self.assertAlmostEqual(centre[0] ** 2 + centre[1] ** 2, 3.2 ** 2)
        self.assertAlmostEqual(fc.circles[-1][1][2], 7.4)


class TwistedPrismTest(unittest.TestCase):
    """The sweep's twist sign is checked against the cap and redone with the other sign when it is reversed."""

    def setUp(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        patch = mock.patch.dict(sys.modules, fakes)
        patch.start()
        self.addCleanup(patch.stop)
        path = mock.patch.object(sys, "path", [_ADDINS] + sys.path)
        path.start()
        self.addCleanup(path.stop)
        for name in _MODULES:
            sys.modules.pop(f"{_PKG}.{name}", None)
        self.fc = importlib.import_module(f"{_PKG}.fusion_clicker")
        self.addCleanup(lambda: [sys.modules.pop(f"{_PKG}.{n}", None) for n in _MODULES])

    def run_prism(self, caps, twist=10.0, want=15.0):
        ctx = mock.MagicMock()
        profile = mock.MagicMock()
        inputs = []
        ctx.comp.features.sweepFeatures.createInput.side_effect = lambda *a: inputs.append(mock.MagicMock()) or inputs[-1]
        feats = [mock.MagicMock(), mock.MagicMock()]
        ctx.comp.features.sweepFeatures.add.side_effect = feats
        for f in feats:
            f.bodies.count = 1
        with mock.patch.object(self.fc, "_cap_angle", side_effect=caps):
            body = self.fc.twisted_prism(ctx, profile, "path", 3.0, twist, want, "p")
        return body, feats, inputs

    def test_a_matching_cap_keeps_the_first_sweep(self):
        body, feats, inputs = self.run_prism([15.05])
        self.assertIs(body, feats[0].bodies.item.return_value)
        self.assertEqual(len(inputs), 1)
        feats[0].deleteMe.assert_not_called()

    def test_a_reversed_twist_is_redone_with_the_other_sign(self):
        body, feats, inputs = self.run_prism([-5.0, 15.0])
        feats[0].deleteMe.assert_called_once()
        self.assertIs(body, feats[1].bodies.item.return_value)
        self.assertEqual(len(inputs), 2)

    def test_a_cap_that_matches_neither_sign_fails(self):
        with self.assertRaises(self.fc.BuildError):
            self.run_prism([100.0, 100.0])

    def test_angle_gap_wraps(self):
        self.assertAlmostEqual(self.fc._angle_gap(179.0, -179.0), 2.0)


if __name__ == "__main__":
    unittest.main()
