import unittest

import _support  # noqa: F401
from gen import frames
from gen.params import Frame, default_params, frame_axes, placement_frame
from gen.validate import derive

IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class FramesTest(unittest.TestCase):
    def test_inverse_and_compose(self):
        w = frame_axes(placement_frame((3.0, -2.0, 48.0), (1.0, 2.0, 2.0)))
        both = frames.compose(w, frames.inverse(w))
        for got, want in zip(both, IDENTITY):
            self.assertTrue(close(got, want), (got, want))

    def test_conjugate_undoes_the_assembly_frame(self):
        # Fusion turns a transform T given for a body into W^-1 T W; conjugating first must give back the move.
        w = frame_axes(placement_frame((0.0, 0.0, 48.0), (0.0, 0.0, 1.0)))
        site = derive(default_params()).clamp_site
        move = site.axes(site.cavity)
        given = frames.conjugate(move, w)
        applied = frames.compose(frames.compose(frames.inverse(w), given), w)
        for got, want in zip(applied, move):
            self.assertTrue(close(got, want), (got, want))

    def test_unplaced_crank_is_unchanged(self):
        site = derive(default_params()).cross_sites[0]
        for axes in (site.axes(), site.bolt_axes(), site.nut_axes()):
            for got, want in zip(frames.conjugate(axes, IDENTITY), axes):
                self.assertTrue(close(got, want))

    def test_translation_only_move_is_unchanged_by_a_shifted_placement(self):
        w = frame_axes(Frame(origin=(5.0, 6.0, 48.0)))
        move = ((0.0, 55.0, 0.0), IDENTITY[1], IDENTITY[2], IDENTITY[3])
        for got, want in zip(frames.conjugate(move, w), move):
            self.assertTrue(close(got, want))

    def test_the_observed_displacement(self):
        # Fusion run with the crank placed at z = 48: the pin bolt, turned over, came out 96 mm low, and the clamp
        # nut pocket 48 mm off along X and Z, because the move was applied unconjugated.
        w = frame_axes(Frame(origin=(0.0, 0.0, 48.0)))
        dm = derive(default_params())
        for site, want in ((dm.site.bolt_axes(), (0.0, 0.0, -96.0)),
                           (dm.clamp_site.axes(dm.clamp_site.cavity), (-48.0, 0.0, -48.0))):
            applied = frames.compose(frames.compose(frames.inverse(w), site), w)
            self.assertTrue(close(tuple(a - b for a, b in zip(applied[0], site[0])), want))

    def test_rotated_placement(self):
        w = frame_axes(placement_frame((10.0, 20.0, 30.0), (1.0, 1.0, 0.0)))
        site = derive(default_params()).cross_sites[1]
        given = frames.conjugate(site.axes(), w)
        applied = frames.compose(frames.compose(frames.inverse(w), given), w)
        for got, want in zip(applied, site.axes()):
            self.assertTrue(close(got, want, 1e-9), (got, want))


if __name__ == "__main__":
    unittest.main()
