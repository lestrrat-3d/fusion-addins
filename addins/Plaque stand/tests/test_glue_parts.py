"""Runs each body builder against a recording fake of the Fusion helpers: the order of cuts, the tools' sketches and
the moves onto each site. It checks the builders' own logic; the Fusion calls themselves are checked in Fusion."""

import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, expected, sections
from gen.params import default_params
from gen.validate import derive

_ADDINS = _support.ADDINS
_PKG = "Plaque stand.commands.plaquestand"


class FakeBody:
    def __init__(self, what):
        self.what = what
        self.isSolid = True


class FakeFusion:
    """Stands in for the `fusion` module: every call is recorded."""

    class BuildError(RuntimeError):
        pass

    def __init__(self, fail_fillet=False, floor_edges=6, outer_loops=1):
        self.calls = []
        self.moves = []
        self.cuts = []
        self.chamfers = []
        self.filleted = []
        self.faces = []
        self.fail_fillet = fail_fillet
        self.floor_edges = floor_edges
        self.outer_loops = outer_loops

    def new_sketch(self, comp, name):
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
        return sk

    def extrude(self, ctx, profile, z, length, what):
        self.calls.append(("extrude", what, z, length))
        return FakeBody(what)

    def revolve(self, ctx, profile, what):
        return FakeBody(what)

    def cut(self, ctx, body, tools, what):
        self.cuts.append((body.what, [t.what for t in tools], what))
        return body

    def fillet(self, ctx, edges, radius, what):
        self.filleted.append((what, len(edges), radius))
        if self.fail_fillet:
            raise self.BuildError(f"{what}: rejected")

    def chamfer(self, ctx, edges, distance, what, tangent_chain=True):
        self.chamfers.append((what, len(edges), distance, tangent_chain))

    def move(self, ctx, body, axes, what):
        self.moves.append((what, axes))
        return body

    def face_loops(self, body, z, min_area, what):
        self.faces.append((body.what, z))
        if "tool" in body.what:  # a nut pocket tool: the floor's hexagon
            return [(True, [object()] * self.floor_edges)]
        return [(True, [object()] * 26)] * self.outer_loops  # a bracket's side face: the profile's 26 edges

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
            importlib.import_module(f"{_PKG}.fusion")
            importlib.import_module(f"{_PKG}.build")
            parts = importlib.import_module(f"{_PKG}.parts")
        fake = FakeFusion(**kw)
        patch = mock.patch.object(parts, "fusion", fake)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in (f"{_PKG}.parts", f"{_PKG}.build")])
        self.fake, self.parts = fake, parts

    def ctx(self, **changes):
        p = dataclasses.replace(default_params(), **changes)
        return types.SimpleNamespace(comp=object(), p=p, dm=derive(p), log=FakeLog(), part="")

    def extrudes(self):
        return {c[1]: c[2:] for c in self.fake.calls if c[0] == "extrude"}

    def test_bracket_is_extruded_chamfered_moved_and_cut(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_bracket(ctx, bodies.BRACKET_1)
        self.assertEqual(body.what, "Bracket 1 extrude")
        self.assertEqual(self.extrudes()["Bracket 1 extrude"], (0.0, 20.0))
        self.assertIn(("draw_loop", "Bracket 1 profile", 26), self.fake.calls)
        # one chamfer call over both side faces' outer loops (26 edges each), the chain not followed
        self.assertEqual(self.fake.chamfers, [("Bracket 1 chamfer faces", 52, 0.5, False)])
        self.assertEqual([z for _, z in self.fake.faces if z in (0.0, 20.0)][:2], [0.0, 20.0])
        # the extrusion is turned onto +X: sketch x -> world Y, sketch y -> world Z, extrusion -> world X
        what, axes = self.fake.moves[0]
        self.assertEqual(what, "Bracket 1 move")
        self.assertEqual(axes, ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)))
        self.assertEqual([tools for _, tools, _ in self.fake.cuts],
                         [["Bracket 1 nut pocket tool_extrude"], ["Bracket 1 bolt hole tool_extrude"]])

    def test_second_bracket_moves_to_the_far_end_of_the_span(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_bracket(ctx, bodies.BRACKET_2)
        self.assertEqual(self.fake.moves[0][1][0], (180.0, 0.0, 0.0))  # S - w_b

    def test_tools_move_onto_the_bolt_site(self):
        self.load()
        ctx = self.ctx()
        self.parts.build_bracket(ctx, bodies.BRACKET_2)
        moved = dict(self.fake.moves)
        site = ctx.dm.sites[1]
        self.assertEqual(moved["Bracket 2 bolt hole tool move"], site.axes())
        self.assertEqual(moved["Bracket 2 nut pocket tool move"], site.axes(site.cavity))
        e = self.extrudes()
        self.assertEqual(e["Bracket 2 nut pocket tool_extrude"], (0.0, 3.0))  # NutCavityHeight + Stock
        self.assertEqual(self.fake.filleted, [("Bracket 2 nut pocket tool round_floor", 6, 0.6)])

    def test_floor_round_falls_back_with_a_log_line(self):
        self.load(fail_fillet=True)
        ctx = self.ctx()
        self.parts.build_bracket(ctx, bodies.BRACKET_1)
        self.assertEqual([r[0] for r in ctx.log.records], ["fallback"])
        self.assertIn("round_floor", ctx.log.records[0][1]["step"])
        self.assertEqual(len(self.fake.cuts), 2)

    def test_floor_edges_must_be_six(self):
        self.load(floor_edges=5)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_bracket(self.ctx(), bodies.BRACKET_1)

    def test_a_bracket_needs_one_outer_loop_per_side_face(self):
        self.load(outer_loops=2)
        with self.assertRaises(FakeFusion.BuildError):
            self.parts.build_bracket(self.ctx(), bodies.BRACKET_1)

    def test_rail(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_rail(ctx)
        self.assertEqual(body.what, "rail extrude")
        self.assertEqual(self.extrudes()["rail extrude"], (0.0, 200.0))
        self.assertIn(("draw_loop", "rail section", 8), self.fake.calls)
        what, axes = self.fake.moves[0]
        self.assertEqual(what, "rail move")
        self.assertEqual(axes[0], (0.0, ctx.dm.rail_center, 6.4))  # the section's centre: T_b - h_r/2 + j
        self.assertEqual(axes[1:], ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)))
        names = [t[0] for _, t, _ in self.fake.cuts]
        self.assertEqual(names, ["rail head pocket 1 tool_extrude", "rail bolt hole 1 tool_extrude",
                                 "rail head pocket 2 tool_extrude", "rail bolt hole 2 tool_extrude"])
        self.assertEqual(self.fake.chamfers, [])  # the rail takes no chamfer

    def test_plaque_is_a_box_turned_onto_its_pose(self):
        self.load()
        ctx = self.ctx()
        body = self.parts.build_plaque(ctx)
        self.assertEqual(body.what, "plaque extrude")
        self.assertIn(("draw_rectangle", "plaque", (0.0, 0.0), (250.0, 12.8)), self.fake.calls)
        self.assertEqual(self.extrudes()["plaque extrude"], (0.0, 305.0))
        self.assertEqual(self.fake.moves, [("plaque move", expected.plaque_axes(ctx.p, ctx.dm))])

    def test_every_body_builds(self):
        self.load()
        ctx = self.ctx()
        for name in bodies.BODY_NAMES:
            with self.subTest(body=name):
                self.assertTrue(self.parts.build_part(ctx, name).isSolid)

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

    def test_not_solid_rejected(self):
        self.load()
        self.fake.cut = lambda ctx, body, tools, what: types.SimpleNamespace(isSolid=False)
        with self.assertRaises(FakeFusion.BuildError) as cm:
            self.parts.build_bracket(self.ctx(), bodies.BRACKET_1)
        self.assertIn("not a solid", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
