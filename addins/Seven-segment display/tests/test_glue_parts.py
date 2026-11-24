"""Runs each body builder against a recording fake of the Fusion helpers: the order of cuts, the tools' sketches and the
moves onto each frame. It checks the builders' own logic; the Fusion calls themselves are checked in Fusion."""

import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, poses
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"


class FakeBody:
    def __init__(self, what):
        self.what = what
        self.isSolid = True


class FakeFusion:
    """Stands in for the `fusion` module: every call is recorded."""

    class BuildError(RuntimeError):
        pass

    def __init__(self, wall_loops=None):
        self.calls = []
        self.moves = []
        self.cuts = []
        self.joins = []
        self.chamfers = []
        self.fillets = []
        self.sketches = []
        self.extrudes = []
        self.profiles = []
        self.wall_loops = wall_loops
        self.counts = {}

    def new_sketch(self, comp, name):
        self.sketches.append(name)
        return name

    new_sketch_xz = new_sketch

    def draw_loop(self, sk, loop):
        self.calls.append(("draw_loop", sk, len(loop)))

    draw_loop_xz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.calls.append(("draw_circle", sk, center, radius))

    def draw_rectangle(self, sk, a, b):
        self.calls.append(("draw_rectangle", sk, a, b))

    def profile_with_loops(self, sk, loops, what, only=False):
        self.profiles.append((what, loops, only))
        return sk

    def profiles_with_loops(self, sk, loops, count, what, only=True):
        self.profiles.append((what, loops, only))
        self.counts[what] = count
        return [sk] * count

    def cut_extrude(self, ctx, profiles, body, z, length, what):
        self.extrudes.append((what, z, length))
        self.cuts.append((what, "extrude"))
        return FakeBody(what)

    def cut_revolve(self, ctx, profile, body, what):
        self.calls.append(("revolve", what))
        self.cuts.append((what, "revolve"))
        return FakeBody(what)

    def extrude(self, ctx, profile, z, length, what):
        self.extrudes.append((what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        self.calls.append(("revolve", what))
        return FakeBody(what)

    def join(self, ctx, body, tools, what):
        self.joins.append(what)
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append((what, tools[0].what))
        return FakeBody(what)

    def fillet(self, ctx, edges, radius, what):
        self.fillets.append((what, len(edges), radius))

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))

    def move(self, ctx, body, axes, what):
        self.moves.append((what, axes))
        return FakeBody(what)

    def face_loops(self, body, z, min_area, what, tol=1e-3):
        if self.wall_loops is not None:
            return self.wall_loops
        outer = (True, [object()] * 4)
        if z == 0.0:
            return [outer] + [(False, [object()] * 4)] * 4
        return [outer]

    def circular_edges_at(self, body, radius, z, tol=1e-3):
        return [object()]


class PartsTest(unittest.TestCase):
    def setUp(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        patch = mock.patch.dict(sys.modules, fakes)
        patch.start()
        self.addCleanup(patch.stop)
        path = mock.patch.object(sys, "path", [_ADDINS] + sys.path)
        path.start()
        self.addCleanup(path.stop)
        for name in (f"{_PKG}.parts", f"{_PKG}.fusion"):
            sys.modules.pop(name, None)
        self.parts = importlib.import_module(f"{_PKG}.parts")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.parts", f"{_PKG}.fusion")])

    def build(self, name, digit=2, fake=None):
        fake = fake or FakeFusion()
        fake.BuildError = FakeFusion.BuildError
        from dataclasses import replace

        p = replace(default_params(), digit=digit)
        ctx = types.SimpleNamespace(comp=None, p=p, dm=derive(p), log=mock.MagicMock(), part=name, shared={})
        with mock.patch.object(self.parts, "fusion", fake):
            body = self.parts.build_part(ctx, name)
        return body, fake

    def test_shaft_revolve_flats_and_move(self):
        _, f = self.build("Shaft", digit=3)
        self.assertEqual([c for c in f.calls if c[0] == "revolve"], [("revolve", "shaft_revolve")])
        self.assertEqual([c[0] for c in f.cuts], ["shaft cut cam flat", "shaft cut cam back flat", "shaft cut stub flat"])
        # The flat tools are boxes y +-6 over the gallery's z ranges.
        got = [e[1:] for e in f.extrudes]
        for (z0, length), (w0, wl) in zip(got, [(-75.0, 133.5), (-75.0, 133.5), (-101.95, 15.35)]):
            self.assertAlmostEqual(z0, w0)
            self.assertAlmostEqual(length, wl)
        rects = [c for c in f.calls if c[0] == "draw_rectangle"]
        self.assertEqual([(r[2], r[3]) for r in rects], [((4.05, -6.0), (12.0, 6.0)), ((-12.0, -6.0), (-4.05, 6.0)),
                                                         ((2.0, -6.0), (12.0, 6.0))])
        self.assertEqual(len(f.moves), 1)
        self.assertEqual(f.moves[0][1], poses.shaft_axes(108.0))

    def test_cam_cut_order_marks_and_inscription(self):
        for s, name, marks in ((0, "Cam A", 4), (3, "Cam D", 1), (2, "Cam C", 3)):
            _, f = self.build(name)
            kinds = [c[0] for c in f.cuts]
            # The gallery's order: bore, groove, then the marks as the circles of one sketch, then the letter.
            self.assertEqual(kinds, [f"{name} cut D bore", f"{name} cut groove", f"{name} cut marks",
                                     f"{name} engrave"])
            self.assertEqual(f.counts[f"{name} cut D bore tool_sketch"], 1)
            self.assertEqual(f.counts[f"{name} cut marks tool_sketch"], marks)
            self.assertEqual(f.moves[0][1], poses.cam_axes(s, 72.0))

    def test_cam_groove_profile_has_one_hole(self):
        _, f = self.build("Cam E")
        groove = [p for p in f.profiles if p[0] == "Cam E cut groove tool_sketch"]
        self.assertEqual(groove, [("Cam E cut groove tool_sketch", 2, False)])
        extr = {e[0]: e[1:] for e in f.extrudes}
        # The groove cutter runs z -2.85 to +1.0; the bore and the marks run through the whole cam.
        self.assertEqual(extr["Cam E cut groove"], (-2.85, 3.85))
        self.assertAlmostEqual(extr["Cam E cut D bore"][1], 18.45)
        self.assertEqual(extr["Cam E cut D bore"][0], -6.7)
        self.assertEqual(extr["Cam E cut marks"], extr["Cam E cut D bore"])

    def test_cam_letter_profile_loops(self):
        for name, loops in (("Cam A", 2), ("Cam C", 1), ("Cam D", 2)):
            _, f = self.build(name)
            self.assertIn((f"{name} engrave tool_sketch", loops, loops == 1), f.profiles)

    def test_cam_turns_with_the_shaft(self):
        for digit in range(10):
            _, f = self.build("Cam B", digit=digit)
            self.assertEqual(f.moves[0][1], poses.cam_axes(1, 36.0 * digit))

    def test_wall_order(self):
        for front, name in ((True, "Front Wall"), (False, "Rear Wall")):
            _, f = self.build(name)
            self.assertEqual(f.joins, [f"{name} union rib {i}" for i in range(1, 5)])
            self.assertEqual([c[:2] for c in f.chamfers], [(f"{name} chamfer z=12", 4), (f"{name} chamfer z=0", 4)])
            self.assertTrue(all(c[2] == 0.5 and c[3] is False for c in f.chamfers))
            self.assertEqual(f.fillets, [(f"{name} round rib root {i}", 4, 0.5) for i in range(1, 5)])
            kinds = [c[0] for c in f.cuts]
            seat = kinds.index(f"{name} cut seat")
            # The fastener tools are cut before the seat, the marks after it.
            self.assertTrue(all("cut seat" not in k and "mark" not in k for k in kinds[:seat]))
            self.assertEqual(kinds[seat + 1:], [f"{name} cut marks"])
            self.assertEqual(f.counts[f"{name} cut marks tool_sketch"], 1 if front else 2)
            self.assertEqual(f.moves[-1][1], poses.wall_axes(front))

    def test_wall_fastener_tools(self):
        _, f = self.build("Front Wall")
        by_site = {}
        for what, tool in f.cuts:
            for label in bodies.SITE_LABELS:
                if what.endswith(f"cut {label}"):
                    by_site.setdefault(label, []).append(tool)
        self.assertEqual(sorted(by_site), ["G1", "G2", "H1", "H2", "T1", "T2"])
        self.assertEqual(by_site["T1"], ["Front Wall T1 hole tool move", "Front Wall T1 nut pocket tool move"])
        self.assertEqual(by_site["G1"], ["Front Wall G1 hole tool move", "Front Wall G1 head pocket tool move"])
        self.assertEqual(by_site["H2"], ["Front Wall H2 hole tool move", "Front Wall H2 nut pocket tool move"])
        _, r = self.build("Rear Wall")
        labels = {k for what, _ in r.cuts for k in bodies.SITE_LABELS if what.endswith(f"cut {k}")}
        self.assertEqual(labels, {"T3", "T4", "G3", "G4"})

    def test_wall_tool_moves_are_in_the_wall_frame(self):
        _, f = self.build("Front Wall")
        moves = dict(f.moves)
        # G1: head at world (-31.3, -51.3, 74.75) is 22.95 behind the inner face, at u -31.3, v 30.5.
        origin = moves["Front Wall G1 hole tool move"][0]
        self.assertAlmostEqual(origin[0], -31.3)
        self.assertAlmostEqual(origin[1], 30.5)
        self.assertAlmostEqual(origin[2], -22.95)

    def test_wall_with_a_wrong_loop_count_fails(self):
        fake = FakeFusion(wall_loops=[(True, [object()] * 4), (False, [object()] * 4)])
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.build("Front Wall", fake=fake)
        self.assertIn("found 1 rib roots, expected 4", str(cm.exception))

    def test_bearings_move_onto_the_wall_faces(self):
        for front, name in ((True, "Front Bearing"), (False, "Rear Bearing")):
            _, f = self.build(name)
            self.assertEqual(f.moves[0][1], poses.bearing_axes(front))
            self.assertIn((f"{name} ring_sketch", 2, False), f.profiles)
            self.assertEqual(f.extrudes, [(f"{name} ring_extrude", 0.0, 7.0)])
            draws = [c for c in f.calls if c[0] == "draw_circle"]
            self.assertEqual([c[3] for c in draws], [11.0, 4.0])

    def test_bolts_and_nuts_move_onto_their_sites(self):
        dm = derive(default_params())
        for label in bodies.SITE_LABELS:
            site = dm.sites[bodies.SITE_LABELS.index(label)]
            _, f = self.build(f"Bolt {label}")
            self.assertEqual(f.moves[-1][1], site.bolt_axes())
            _, f = self.build(f"Nut {label}")
            self.assertEqual(f.moves[-1][1], site.nut_axes())

    def test_an_unknown_body_is_refused(self):
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.build("Nonsense")
        self.assertIn("unknown body", str(cm.exception))

    def test_every_frame_and_camshaft_body_has_a_builder(self):
        for name in bodies.BODY_NAMES:
            if bodies.BODY_STAGE[name] != 1:
                continue
            body, _ = self.build(name)
            self.assertTrue(body.isSolid)

    def test_flag_and_clicker_bodies_go_to_their_modules(self):
        # The flag and clicker builders have their own tests (test_flags_parts, test_clicker_glue).
        for name in bodies.BODY_NAMES:
            group = bodies.BODY_STAGE[name]
            if group == 1:
                continue
            module, attr = (("parts_flags", "build_flag_part") if group == 2 else ("parts_clicker",
                                                                                   "build_clicker_part"))
            with mock.patch.object(self.parts, module) as m:
                getattr(m, attr).return_value = "body"
                ctx = types.SimpleNamespace(part=name)
                self.assertEqual(self.parts.build_part(ctx, name), "body")
                getattr(m, attr).assert_called_once_with(ctx, name)


if __name__ == "__main__":
    unittest.main()
