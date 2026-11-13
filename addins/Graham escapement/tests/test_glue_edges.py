import importlib
import os
import sys
import types
import unittest
from unittest import mock

import _support  # noqa: F401

_ADDINS = _support.ADDINS


def _edge(geometry):
    return types.SimpleNamespace(geometry=geometry)


def _circle(adsk, radius_cm, z_cm):
    centre = types.SimpleNamespace(x=0.0, y=0.0, z=z_cm)
    return types.SimpleNamespace(
        curveType=adsk.core.Curve3DTypes.Circle3DCurveType, center=centre, radius=radius_cm
    )


class EdgeHelpersTest(unittest.TestCase):
    """Edge searches with adsk mocked: an edge without curve geometry is skipped, not an error."""

    def test_degenerate_edge_is_skipped(self):
        adsk = mock.MagicMock()
        adsk.core.Circle3D.cast = lambda g: g
        adsk.core.Arc3D.cast = lambda g: g
        adsk.core.Line3D.cast = lambda g: g
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Graham escapement.commands.escapement.fusion")
            edges = [_edge(None), _edge(_circle(adsk, 0.1, 0.0)), _edge(_circle(adsk, 0.3, 0.0))]
            body = types.SimpleNamespace(
                edges=types.SimpleNamespace(count=len(edges), item=lambda i: edges[i])
            )
            found = fusion.circular_edges_at(body, 1.0, 0.0)
            self.assertEqual(found, [edges[1]])
            self.assertFalse(fusion._is_axial_line(edges[0], 1e-3))
            self.assertEqual(fusion.axial_edges_at(body, [(0.0, 0.0)]), [])

    def test_flat_face_loops(self):
        adsk = mock.MagicMock()
        adsk.core.Plane.cast = lambda g: g
        adsk.core.Circle3D.cast = lambda g: g
        adsk.core.Arc3D.cast = lambda g: g
        adsk.core.SurfaceTypes.PlaneSurfaceType = 0
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}

        def listing(items):
            return types.SimpleNamespace(count=len(items), item=lambda i: items[i])

        line = types.SimpleNamespace(curveType=adsk.core.Curve3DTypes.Line3DCurveType)

        def edge(x, y, geometry=line, length=1.0):
            point = types.SimpleNamespace(x=x, y=y, z=0.0)
            return types.SimpleNamespace(
                startVertex=types.SimpleNamespace(geometry=point), geometry=geometry, length=length
            )

        def loop(outer, edges):
            return types.SimpleNamespace(isOuter=outer, edges=listing(edges))

        def plane_face(nz, oz_cm, area_cm2, loops, nx=0.0):
            normal = types.SimpleNamespace(x=nx, y=0.0, z=nz, length=abs(nz) or 1.0)
            geometry = types.SimpleNamespace(
                surfaceType=0, normal=normal, origin=types.SimpleNamespace(x=0.0, y=0.0, z=oz_cm)
            )
            return types.SimpleNamespace(geometry=geometry, area=area_cm2, loops=listing(loops))

        # A circle of radius 0.9 cm centred at (0.1, 0.2) cm, and a line edge.
        round_geometry = _circle(adsk, 0.9, 0.0)
        round_geometry.center.x, round_geometry.center.y = 0.1, 0.2
        a1, a2, c1 = edge(4.4, 0.0), edge(0.0, 0.9, round_geometry, 5.65), edge(4.4, 0.0)
        a3 = edge(4.4, 0.5, length=0.5)
        degenerate = edge(1.0, 1.0, None)
        faces = [
            plane_face(-1, 0.0, 20.0, [loop(True, [a1, a3]), loop(False, [a2])]),
            plane_face(1, 0.0, 1.431, [loop(True, [edge(1.1, 0.0)])]),
            plane_face(1, 0.3, 20.0, [loop(True, [c1]), loop(False, [degenerate])]),
            types.SimpleNamespace(geometry=types.SimpleNamespace(surfaceType=1)),
            plane_face(0.0, 0.0, 20.0, [loop(True, [edge(4.4, 0.0)])], nx=1.0),
        ]
        body = types.SimpleNamespace(faces=listing(faces))
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Graham escapement.commands.escapement.fusion")
            got = fusion.flat_face_loops(body, 0.0, 400.0, "w")
            self.assertEqual(len(got), 2)
            self.assertEqual((got[0][0], got[0][1], got[0][2]), (True, [a1, a3], None))
            self.assertAlmostEqual(got[0][4], 15.0, places=9)  # 1.0 + 0.5 cm
            self.assertAlmostEqual(got[0][3][0], 44.0, places=9)
            self.assertAlmostEqual(got[0][3][1], 0.0, places=9)
            self.assertEqual((got[1][0], got[1][1]), (False, [a2]))
            self.assertAlmostEqual(got[1][4], 56.5, places=9)
            circle = got[1][2]
            self.assertEqual([round(v, 9) for v in circle], [1.0, 2.0, 9.0])
            self.assertAlmostEqual(got[1][3][1], 9.0, places=9)
            got = fusion.flat_face_loops(body, 3.0, 400.0, "w")
            self.assertEqual(len(got), 2)
            self.assertEqual((got[0][0], got[0][1]), (True, [c1]))
            # The degenerate edge is skipped, so the loop has no edge, no circle and no start.
            self.assertEqual(got[1], (False, [], None, None, 0.0))

    def test_chamfer_tangent_chain_and_none(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Graham escapement.commands.escapement.fusion")
            ctx = mock.MagicMock()
            sets = ctx.comp.features.chamferFeatures.createInput2.return_value.chamferEdgeSets
            fusion.chamfer(ctx, [1, 2], 0.5, "w", tangent_chain=False)
            self.assertIs(sets.addEqualDistanceChamferEdgeSet.call_args.args[2], False)
            fusion.chamfer(ctx, [1, 2], 0.5, "w")
            self.assertIs(sets.addEqualDistanceChamferEdgeSet.call_args.args[2], True)
            ctx.comp.features.chamferFeatures.add.return_value = None
            with self.assertRaises(fusion.BuildError) as cm:
                fusion.chamfer(ctx, [1, 2], 0.5, "w")
            self.assertEqual(str(cm.exception), "w: Fusion created no chamfer")


if __name__ == "__main__":
    unittest.main()
