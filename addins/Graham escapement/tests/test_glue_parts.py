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
    """Face loops (is_outer, edges, circle, start, length) that the part's rule keeps at exactly the gallery's
    count (plus extra_loop), together with loops it rejects."""
    fp = [f for f in edgefinish.finish_planes(part) if abs(f.z - z) < 1e-9][0]
    e = object()
    n = fp.loops + extra_loop
    rim = (fp.radii[0], 0.0) if fp.radii else None
    if fp.rule == edgefinish.PLATE:
        return [(True, [e] * 8, None, None, 0.0), (False, [e] * 11, None, None, 0.0),
                (False, [e] * 11, None, None, 0.0)] + [(False, [e], (0.0, 0.0, 5.0), None, 0.0)] * (n - 3)
    if fp.rule == edgefinish.RIM:
        # The outline, rim circles for the other kept loops, and a multi-edge inner loop the rule rejects.
        return [(True, [e] * 8, None, None, 0.0)] * min(n, 1) + [(False, [e], None, rim, 0.0)] * (n - 1) + [
            (False, [e] * 4, None, (1.0, 1.0), 0.0)
        ]
    if fp.rule == edgefinish.INNER_MULTI_OR_RIM:
        windows = min(n, 6)
        return ([(True, [e] * 90, None, None, 0.0)] + [(False, [e] * 4, None, (1.0, 1.0), 0.0)] * windows
                + [(False, [e], None, rim, 0.0)] * (n - windows) + [(False, [e], (0.0, 0.0, 2.55), (2.55, 0.0), 0.0)])
    if fp.rule == edgefinish.INNER_RIM:
        return [(True, [e] * 90, None, None, 0.0), (False, [e] * 2, None, (3.45, 0.0), 0.0)] + [
            (False, [e], None, rim, 0.0)
        ] * n
    if fp.rule == edgefinish.OUTER_OR_LONG_INNER:
        # Outer loop, then n - 1 inner loops of length 20.86 (the bore), and the eye hole of length 11.94.
        return [(True, [e] * 40, None, None, 900.0)] * min(n, 1) + [(False, [e] * 2, None, None, 20.86)] * (n - 1) + [
            (False, [e], None, None, 11.94)
        ]
    raise AssertionError(fp.rule)


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

    def test_great_wheel_order(self):
        calls = self.run_parts(only=["great_wheel"])
        steps = [c[1] for c in calls if c[0] in ("cut", "chamfer", "pattern")]
        self.assertEqual(
            steps,
            [
                "great_wheel pattern", "great_wheel bore_cut", "great_wheel counterbore_cut",
                "great_wheel edge_chamfer z=1.5", "great_wheel ratchet_pattern", "great_wheel ratchet_cut",
            ],
        )

    def test_extrude_spans(self):
        want = {
            "escape_wheel": {
                "escape_wheel front_counterbore_extrude": (23.95, 26.0),
                "escape_wheel bore_extrude": (-0.75, 26.75),
                "escape_wheel rear_counterbore_extrude": (0.5, 3.3),
            },
            "anchor": {"anchor counterbore_extrude": (24.7, 27.0), "anchor bore_extrude": (20.0, 28.75)},
            "crutch": {
                "crutch outline_extrude": (35.3, 38.3), "crutch pin_extrude": (37.8, 44.3),
                "crutch counterbore_extrude": (34.3, 37.3), "crutch bore_extrude": (34.3, 39.3),
            },
            "great_wheel": {"great_wheel counterbore_extrude": (0.5, 3.5)},
            "pawl_carrier": {
                "pawl_carrier layer_extrude": (5.25, 9.25), "pawl_carrier boss_extrude": (8.75, 11.0),
                "pawl_carrier bore_extrude": (4.25, 12.0),
            },
            "spring_spacer": {"spring_spacer disc_extrude": (17.5, 27.75), "spring_spacer bore_extrude": (16.5, 28.75)},
            "winding_knob": {
                "winding_knob disc_extrude": (35.3, 38.3), "winding_knob counterbore_extrude": (34.3, 37.3),
                "winding_knob bore_extrude": (34.3, 39.3),
            },
            "arbor_collar": {"arbor_collar ring_extrude": (0.0, 3.0), "arbor_collar bore_extrude": (-1.0, 4.0)},
            "end_collar": {"end_collar ring_extrude": (0.0, 3.0), "end_collar bore_extrude": (-1.0, 4.0)},
        }
        for part, spans in want.items():
            calls = self.run_parts(only=[part])
            got = {c[1]: (c[2], c[3]) for c in calls if c[0] == "extrude"}
            for what, span in spans.items():
                self.assertEqual(got[what], span, what)
        flats = {
            "escape_arbor": [(0.2, 23.95)], "pallet_arbor": [(21.0, 27.8), (34.25, 39.25)],
            "great_wheel_arbor": [(5.25, 27.8), (34.25, 39.25)], "suspension_pin": [(30.05, 33.95), (45.3, 47.75)],
        }
        for part, spans in flats.items():
            calls = self.run_parts(only=[part])
            got = [(c[2], c[3]) for c in calls if c[0] == "extrude" and c[1] == f"{part} flat_box_extrude"]
            self.assertEqual(got, spans, part)

    def test_pawl_carrier_is_one_layer_loop(self):
        calls = self.run_parts(only=["pawl_carrier"])
        profiles = [c for c in calls if c[0] == "profile"]
        self.assertIn(("profile", "pawl_carrier layer_sketch", 1, True), profiles)
        self.assertEqual(len([c for c in profiles if c[1].startswith("pawl_carrier layer")]), 1)
        self.assertFalse([c for c in calls if len(c) > 1 and isinstance(c[1], str) and "pawl_1" in c[1]])
        self.assertIn(("join", "pawl_carrier parts_join"), calls)

    def test_no_boss_builders(self):
        for part in ("escape_wheel", "anchor"):
            calls = self.run_parts(only=[part])
            self.assertFalse([c for c in calls if "boss" in c[1]], part)


if __name__ == "__main__":
    unittest.main()
