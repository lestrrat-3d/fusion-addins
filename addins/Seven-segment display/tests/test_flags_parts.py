"""Runs the flag builders against a recording fake of the Fusion helpers: the order of cuts and joins, the tools'
sketches and the moves onto each frame. It checks the builders' own logic; the Fusion calls are checked in Fusion."""

import importlib
import sys
import types
import unittest
from dataclasses import replace
from unittest import mock

import _support  # noqa: F401

from gen import bodies, flags_common as fc, flags_pivot as fv, frames
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Seven-segment display.commands.sevensegment"


class FakeBody:
    def __init__(self, what, centre=(1.0, 2.0, 3.0)):
        self.what = what
        self.isSolid = True
        self.centre = centre


class FakeFusion:
    class BuildError(RuntimeError):
        pass

    def __init__(self, outer_loops=1):
        self.profiles, self.extrudes, self.revolves = [], [], []
        self.cuts, self.joins, self.moves = [], [], []
        self.chamfers, self.fillets, self.circles = [], [], []
        self.outer_loops = outer_loops
        self.copies = []

    def new_sketch(self, comp, name):
        return name

    new_sketch_xz = new_sketch

    def draw_loop(self, sk, loop):
        pass

    draw_loop_xz = draw_loop

    def draw_circle(self, sk, center, radius):
        self.circles.append((sk, center, radius))

    def profile_with_loops(self, sk, loops, what, only=False):
        self.profiles.append((what, loops, only))
        return sk

    def cut_extrude(self, ctx, profile, body, z, length, what):
        self.extrudes.append((what, z, length))
        self.cuts.append(what)
        return FakeBody(what)

    def cut_revolve(self, ctx, profile, body, what):
        self.revolves.append(what)
        self.cuts.append(what)
        return FakeBody(what)

    def extrude(self, ctx, profile, z, length, what):
        self.extrudes.append((what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        self.revolves.append(what)
        return FakeBody(what)

    def join(self, ctx, body, tools, what):
        self.joins.append(what)
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append(what)
        return FakeBody(what)

    def fillet(self, ctx, edges, radius, what):
        self.fillets.append((what, len(edges), radius))

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))

    def move(self, ctx, body, axes, what):
        self.moves.append((what, axes))
        return FakeBody(what, frames.apply(axes, body.centre))

    def copy_body(self, ctx, body, what):
        self.copies.append(what)
        return FakeBody(what, body.centre)

    def centre_mm(self, body):
        return body.centre

    def face_loops(self, body, z, min_area, what, tol=1e-3):
        return [(True, [object()] * 4)] * self.outer_loops


class FlagPartsTest(unittest.TestCase):
    def setUp(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        for patch in (mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path)):
            patch.start()
            self.addCleanup(patch.stop)
        names = [f"{_PKG}.parts_flags", f"{_PKG}.fusion"]
        for n in names:
            sys.modules.pop(n, None)
        self.pf = importlib.import_module(f"{_PKG}.parts_flags")
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in names])
        self.intersects = []

    def build(self, name, digit=2, fake=None, shared=None):
        fake = fake or FakeFusion()
        fake.BuildError = FakeFusion.BuildError
        p = replace(default_params(), digit=digit)
        ctx = types.SimpleNamespace(comp=None, p=p, dm=derive(p), log=mock.MagicMock(), part=name,
                                    shared={} if shared is None else shared)
        self.ctx = ctx

        def intersect(c, a, b, what):
            self.intersects.append(what)
            return FakeBody(what)

        with mock.patch.object(self.pf, "fusion", fake), mock.patch.object(self.pf, "_intersect", intersect), \
                mock.patch.object(self.pf, "_stem_run_edges", lambda body, run, what: [object()] * len(run)):
            body = self.pf.build_flag_part(ctx, name)
        return body, fake

    def build_all(self, names, digit=2):
        """Build `names` in order with one shared prototype table and one fake, as a build does."""
        fake, shared = FakeFusion(), {}
        for name in names:
            self.build(name, digit, fake, shared)
        return fake, shared

    def test_yellow_bodies_are_built_once_and_copied(self):
        names = [bodies.yellow_name(s) for s in range(7)]
        fake, shared = self.build_all(names, digit=3)
        self.assertEqual(sorted(shared), ["yellow"])
        # One build: its rotor and slab intersects, then six copies, each moved once.
        self.assertEqual(self.intersects.count("Yellow Face A yellow"), 1)
        self.assertEqual(len([i for i in self.intersects if i.endswith(" yellow")]), 1)
        self.assertEqual(fake.copies, [f"{n} copy" for n in names[1:]])
        moves = dict(fake.moves)
        theta = 108.0
        proto = fc.rotor_axes(0, fc.flag_angle(0, theta))
        for s in range(1, 7):
            want = frames.compose(fc.rotor_axes(s, fc.flag_angle(s, theta)), frames.inverse(proto))
            got = moves[f"{names[s]} move"]
            for a, b in zip(got, want):
                for x, y in zip(a, b):
                    self.assertAlmostEqual(x, y, places=9)

    def test_black_bodies_share_by_their_notches(self):
        # a, g, d have one notch; b, c, e, f have two.
        names = [bodies.black_name(s) for s in range(7)]
        fake, shared = self.build_all(names)
        self.assertEqual(len(shared), 2)
        self.assertEqual(len(fake.copies), 5)
        cut_notches = [c for c in fake.cuts if "cut notch" in c]
        self.assertEqual(len(cut_notches), 1 + 2)  # type A once (1 notch), type B once (2 notches)

    def test_pivot_blocks_are_built_once_and_copied_to_their_ends(self):
        names = list(bodies.PIVOT_ENDS)
        fake, shared = self.build_all(names)
        self.assertEqual(len(names), 14)
        self.assertEqual(len(fake.copies), 13)
        self.assertEqual(sorted(shared), ["pivot block"])
        first = names[0]
        pivot_moves = {w: a for w, a in fake.moves}
        self.assertIn(f"{first} move", pivot_moves)
        s0, g0 = bodies.PIVOT_ENDS[first]
        self.assertEqual(pivot_moves[f"{first} move"], fv.segment_axes(s0, g0))
        for name in names[1:]:
            s, g = bodies.PIVOT_ENDS[name]
            want = frames.compose(fv.segment_axes(s, g), frames.inverse(fv.segment_axes(s0, g0)))
            got = pivot_moves[f"{name} move"]
            for a, b in zip(got, want):
                for x, y in zip(a, b):
                    self.assertAlmostEqual(x, y, places=9)

    def test_a_refused_copy_is_built_instead(self):
        class Refusing(FakeFusion):
            def copy_body(self, ctx, body, what):
                raise FakeFusion.BuildError("no copy")

        fake, shared = Refusing(), {}
        for name in (bodies.yellow_name(0), bodies.yellow_name(1)):
            self.build(name, 2, fake, shared)
        self.assertEqual(len([i for i in self.intersects if i.endswith(" yellow")]), 2)
        written = [c.args for c in self.ctx.log.write.call_args_list]
        self.assertEqual([w[0] for w in written], ["copy"])

    def test_a_copy_off_its_place_stops_the_build(self):
        class Drifting(FakeFusion):
            def centre_mm(self, body):
                return (body.centre[0] + (1.0 if "copy" not in body.what and "move" in body.what else 0.0),
                        body.centre[1], body.centre[2])

        fake, shared = Drifting(), {}
        self.build(bodies.yellow_name(0), 2, fake, shared)
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.build(bodies.yellow_name(1), 2, fake, shared)
        self.assertIn("the copy's centre is at", str(cm.exception))

    def test_the_names_are_the_flag_bodies(self):
        self.assertEqual(len(self.pf.FLAG_PART_NAMES), 38)
        self.assertEqual(set(self.pf.FLAG_PART_NAMES), {n for n, st in bodies.BODY_STAGE.items() if st == 2})

    def test_every_flag_body_has_a_builder(self):
        for name in self.pf.FLAG_PART_NAMES:
            body, _ = self.build(name)
            self.assertTrue(body.isSolid)

    def test_other_bodies_are_refused(self):
        for name in ("Hub", "Front Wall", "Cam A"):
            with self.assertRaises(FakeFusion.BuildError):
                self.build(name)

    def test_yellow_is_the_slab_inside_the_rotor(self):
        for s, c in enumerate("abcdefg"):
            name = f"Yellow Face {c.upper()}"
            _, f = self.build(name, digit=3)
            self.assertEqual(self.intersects, [f"{name} tips", f"{name} rotor", f"{name} slab", f"{name} yellow"])
            self.intersects.clear()
            self.assertEqual(f.cuts, [])
            self.assertEqual(f.moves[-1][1], fc.rotor_axes(s, fc.flag_angle(s, 108.0)))

    def test_black_cuts_and_pivot_bores(self):
        for s, c in enumerate("abcdefg"):
            name = f"Black Body {c.upper()}"
            _, f = self.build(name)
            notches = 1 if c in "agd" else 2
            want = [f"{name} black", f"{name} cut flat"]
            for i in range(1, notches + 1):
                want += [f"{name} cut notch {i}", f"{name} cut pocket {i}"]
            want += [f"{name} cut upper bore", f"{name} cut upper roof", f"{name} cut lower bore",
                     f"{name} cut lower roof"]
            self.assertEqual(f.cuts, want)
            # No notch ends within 0.8 of the tip slant at this size (type B's first notch is at u0 -14.1, 0.9 off),
            # so none gets the mouth chamfer.
            mouth = False
            self.assertEqual(f.joins, [f"{name} notch 1 mouth"] if mouth else [])
            self.assertEqual(f.fillets, [(f"{name} pocket {i} tool round the floor", 4, 0.9)
                                         for i in range(1, notches + 1)])
            self.assertEqual(len(self.intersects), 3 + 2 * notches + mouth)
            if mouth:
                self.assertIn(f"{name} notch 1 mouth tool", self.intersects)
            self.assertEqual(len(f.revolves), 2)
            self.intersects.clear()
            self.assertEqual(f.moves[-1][1], fc.rotor_axes(s, fc.flag_angle(s, 72.0)))

    def test_slider_joins_and_lift(self):
        # digit 2 lights a, b, d, e, g; c and f stay down.
        for s, c in enumerate("abcdefg"):
            name = f"Slider {c.upper()}"
            _, f = self.build(name, digit=2)
            joins = 2 if c in "agd" else 3
            self.assertEqual(len(f.joins), joins)
            self.assertTrue(f.joins[-1].endswith("union groove pin"))
            edges = 4 if c in "agd" else 8  # a, g, d: the four vertical edges; b, c, e, f: two runs of 3 and 1 per face
            self.assertEqual(f.chamfers, [(f"{name} stem chamfers", edges, 0.5, False)])
            lifted = [m for m in f.moves if m[0].endswith("lift")]
            self.assertEqual(len(lifted), 1 if c in "abdeg" else 0)
            if lifted:
                self.assertEqual(lifted[0][1][0], (0.0, 0.0, 4.5))

    def test_slider_with_a_missing_stem_edge_fails(self):
        fake = FakeFusion()
        fake.BuildError = FakeFusion.BuildError
        p = default_params()
        ctx = types.SimpleNamespace(comp=None, p=p, dm=derive(p), log=mock.MagicMock(), part="Slider A")
        body = mock.MagicMock()
        body.edges.count = 0
        with mock.patch.object(self.pf, "fusion", fake):
            with self.assertRaises(FakeFusion.BuildError) as cm:
                self.pf._chamfer_stem(ctx, body, 0, "Slider A")
        self.assertIn("found 0 edges", str(cm.exception))

    def test_a_refused_stem_chamfer_falls_back_to_runs_then_edges(self):
        calls = []

        class Refusing(FakeFusion):
            def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
                calls.append((what, len(edges)))
                if len(edges) > 1 or "run 1" in what:
                    raise FakeFusion.BuildError("refused")

        fake = Refusing()
        fake.BuildError = FakeFusion.BuildError
        p = default_params()
        log = mock.MagicMock()
        ctx = types.SimpleNamespace(comp=None, p=p, dm=derive(p), log=log, part="Slider B")
        with mock.patch.object(self.pf, "fusion", fake), \
                mock.patch.object(self.pf, "_stem_run_edges", lambda body, run, what: [object()] * len(run)):
            self.pf._chamfer_stem(ctx, object(), 1, "Slider B")
        self.assertEqual(calls[0], ("Slider B stem chamfers", 8))
        self.assertEqual(calls[1], ("Slider B stem chamfer run 0", 3))
        self.assertIn(("Slider B stem chamfer run 0 edge 0", 1), calls)
        skipped = [c for c in log.write.call_args_list if c.args[0] == "skipped_chamfer"]
        self.assertEqual(len(skipped), 1)  # run 1 is one edge and refused alone

    def test_guide_plate(self):
        _, f = self.build("Guide Plate")
        self.assertIn(("Guide Plate plate_sketch", 12, False), f.profiles)
        self.assertEqual([c[:2] for c in f.chamfers], [("Guide Plate chamfer z=81", 4), ("Guide Plate chamfer z=87", 4)])
        self.assertEqual(f.cuts, [f"Guide Plate cut nut pocket {i}" for i in range(1, 5)])
        self.assertEqual(f.joins, ["Guide Plate union column 1", "Guide Plate union column peg 1",
                                   "Guide Plate union column 2", "Guide Plate union column peg 2"])
        self.assertEqual(len(f.circles), 4)

    def test_cradle_plate(self):
        _, f = self.build("Cradle Plate")
        self.assertIn(("Cradle Plate plate_sketch", 9, False), f.profiles)
        self.assertEqual(len(f.cuts), 7 + 7 + 14 + 2)
        self.assertEqual(f.cuts[0], "Cradle Plate cut passage A")
        self.assertEqual(f.cuts[-2:], ["Cradle Plate cut mouth cone 1", "Cradle Plate cut mouth cone 2"])
        pockets = [c for c in f.cuts if "pivot pocket" in c]
        self.assertEqual(len(pockets), 14)
        self.assertEqual(pockets[:2], ["Cradle Plate pivot pocket a- cut", "Cradle Plate pivot pocket a+ cut"])
        # One pocket tool is built; 13 of the cuts use copies of it and the last uses the tool itself.
        self.assertEqual([i for i in self.intersects if "pivot pocket" in i], ["Cradle Plate pivot pocket tool"])
        self.assertEqual(len([c for c in f.copies if "pivot pocket" in c]), 13)
        pocket_moves = [w for w, _ in f.moves if "pivot pocket" in w and "tool" not in w]
        self.assertEqual(len(pocket_moves), 14)
        # The pockets are cut after the seven bores, before the mouth cones.
        bores = [i for i, c in enumerate(f.cuts) if "cut bore" in c]
        first = f.cuts.index(pockets[0])
        self.assertTrue(max(bores) < first < f.cuts.index("Cradle Plate cut mouth cone 1"))
        self.assertEqual([c[0] for c in f.chamfers], ["Cradle Plate chamfer z=120", "Cradle Plate chamfer z=124"])
        self.assertEqual(len(f.circles), 8)

    def test_top_plate(self):
        _, f = self.build("Top Plate")
        self.assertEqual(len(f.joins), 7 + 2)
        self.assertEqual(len([c for c in f.cuts if "pivot pocket" in c]), 14)
        windows = [c for c in f.cuts if "window" in c or "T hole" in c]
        self.assertEqual(len(windows), 11)
        self.assertEqual(len([c for c in f.cuts if "blade hole" in c]), 7)
        self.assertEqual(len([c for c in f.cuts if "head pocket" in c]), 4)
        # The head pockets come last, after the chamfers.
        self.assertTrue(f.cuts[-1].endswith("cut head pocket 4"))
        self.assertEqual([c[0] for c in f.chamfers], ["Top Plate chamfer z=124.25", "Top Plate chamfer z=132.25"])

    def test_pivot_blocks(self):
        for name, (s, sgn) in bodies.PIVOT_ENDS.items():
            _, f = self.build(name)
            self.assertEqual(self.intersects, [f"{name} body"])
            self.intersects.clear()
            self.assertEqual(f.joins, [f"{name} union pin"])
            self.assertEqual(f.cuts, [])
            self.assertEqual(len(f.revolves), 1)
            self.assertEqual(f.moves[-1][1], fv.segment_axes(s, sgn))

    def test_a_plate_with_several_outer_loops_fails(self):
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.build("Cradle Plate", fake=FakeFusion(outer_loops=2))
        self.assertIn("found 2 outer loops", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
