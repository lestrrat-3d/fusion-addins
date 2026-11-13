"""Runs the real part builders against stubbed Fusion wrappers.

Checks the feature order the builders emit: chamfer calls per part against edgefinish.finish_planes, the loop-count
guard, the ratchet cutter steps and the root-fillet edge counts. No Fusion is involved."""

import importlib
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import bodies, edgefinish
from gen.layout import layout
from gen.motion import state_at
from gen.params import default_params

_PKG = "Graham escapement.commands.escapement"


class Body:
    isSolid = True


def _loops_for(part, z, extra_loop=0):
    """Face loops that pass the part's rule with exactly the gallery's kept-loop count (plus extra_loop)."""
    fp = [f for f in edgefinish.finish_planes(part) if abs(f.z - z) < 1e-9][0]
    e = object()
    n = fp.loops + extra_loop
    if fp.rule == edgefinish.OUTER:
        return [(True, [e] * 8, None, (1.0, 1.0))] * n if n else []
    if fp.rule == edgefinish.INNER_MULTI:
        return [(True, [e] * 90, None, None)] + [(False, [e] * 4, None, (1.0, 1.0))] * n
    if fp.rule == edgefinish.PLATE:
        return [(True, [e] * 8, None, None), (False, [e] * 11, None, None), (False, [e] * 11, None, None)] + [
            (False, [e], (0.0, 0.0, 5.0), None)
        ] * (n - 3)
    return [(True, [e] * 8, None, None), (False, [e], None, (5.0, 0.0))]


class GluePartsTest(unittest.TestCase):
    def run_parts(self, only=None, extra_loop=0):
        adsk = mock.MagicMock()
        calls = []
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_support.ADDINS] + sys.path):
            for name in (f"{_PKG}.build", f"{_PKG}.checks", f"{_PKG}.fusion", f"{_PKG}.parts"):
                sys.modules.pop(name, None)
            fusion = importlib.import_module(f"{_PKG}.fusion")
            parts = importlib.import_module(f"{_PKG}.parts")
            build = importlib.import_module(f"{_PKG}.build")
            cur = {}

            def rec(name):
                def f(*a, **k):
                    calls.append((name, a[-1] if isinstance(a[-1], str) else k.get("what", "")))
                    return Body()

                return f

            def extrude(ctx, profile, z, length, what):
                calls.append(("extrude", what, round(z, 4), round(z + length, 4)))
                return Body()

            def pattern(ctx, body, n, what):
                calls.append(("pattern", what, n))
                return [body] + [Body() for _ in range(n - 1)]

            def profile_with_loops(sk, loops, what, only=False):
                calls.append(("profile", what, loops, only))
                return object()

            def flat_face_loops(body, z, min_area, what, tol=1e-3):
                return _loops_for(cur["part"], z, extra_loop)

            def chamfer(ctx, edges, d, what, tangent_chain=True):
                calls.append(("chamfer", what, len(edges), d, tangent_chain))

            def axial(body, pts, tol=1e-3):
                return [object()] * len(pts) if len(pts) == 5 else [object()] * 26

            patches = dict(
                new_sketch=mock.MagicMock(), new_sketch_xz=mock.MagicMock(), draw_loop=mock.MagicMock(),
                draw_loop_xz=mock.MagicMock(), draw_circle=mock.MagicMock(), draw_rectangle=mock.MagicMock(),
                profile_with_loops=profile_with_loops, extrude=extrude, revolve=rec("revolve"), join=rec("join"),
                cut=rec("cut"), pattern=pattern, fillet=rec("fillet"), chamfer=chamfer, move=rec("move"),
                flat_face_loops=flat_face_loops, axial_edges_at=axial,
                concave_axial_edges=lambda b, tol=1e-3: [object()] * 96,
                circular_edges_at=lambda *a, **k: [object()],
            )
            p = default_params()
            g = layout(p)
            ctx = build.BuildContext(
                occ=None, comp=mock.MagicMock(), top=None, p=p, g=g, s=state_at(g, p.phase), log=None,
                container_comps={},
            )
            self.fusion = fusion
            with mock.patch.multiple(fusion, **patches):
                for part in only or bodies.PARTS:
                    ctx.part = part
                    cur["part"] = part
                    calls.append(("PART", part))
                    getattr(parts, f"build_{part}")(ctx)
        return calls

    def test_every_builder_runs(self):
        calls = self.run_parts()
        self.assertEqual([c[1] for c in calls if c[0] == "PART"], list(bodies.PARTS))

    def test_chamfer_calls_match_finish_planes(self):
        calls = self.run_parts()
        part = None
        got = {}
        for c in calls:
            if c[0] == "PART":
                part = c[1]
            elif c[0] == "chamfer":
                got.setdefault(part, []).append(c)
        for name in bodies.PARTS:
            planes = edgefinish.finish_planes(name)
            self.assertEqual(len(got.get(name, [])), len(planes), name)
            for c in got.get(name, []):
                self.assertEqual(c[3], edgefinish.CHAMFER)
                self.assertIs(c[4], False)
        self.assertEqual([len(edgefinish.finish_planes(n)) for n in ("back_plate", "anchor", "mainspring")], [2, 2, 2])
        self.assertEqual(len(got["mainspring"]), 2)

    def test_loop_count_guard(self):
        with self.assertRaises(Exception) as cm:
            self.run_parts(only=["anchor"], extra_loop=1)
        self.assertIn("found 2 loops to chamfer, expected 1", str(cm.exception))

    def test_ratchet_cutter_is_disc_plus_patterned_triangle(self):
        calls = self.run_parts(only=["great_wheel"])
        patterns = [c for c in calls if c[0] == "pattern"]
        self.assertEqual([(c[1], c[2]) for c in patterns], [("great_wheel pattern", 48), ("great_wheel ratchet_pattern", 12)])
        spans = {c[1]: c[2:] for c in calls if c[0] == "extrude"}
        self.assertEqual(spans["great_wheel ratchet disc_extrude"], (5.0, 9.5))
        self.assertEqual(spans["great_wheel ratchet_tooth_extrude"], (5.0, 9.5))
        self.assertIn(("join", "great_wheel ratchet_join"), calls)
        self.assertIn(("cut", "great_wheel ratchet_cut"), calls)


if __name__ == "__main__":
    unittest.main()
