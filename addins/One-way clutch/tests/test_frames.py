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
        for site in derive(default_params()).sites:
            move = site.axes(site.cavity)
            given = frames.conjugate(move, w)
            applied = frames.compose(frames.compose(frames.inverse(w), given), w)
            for got, want in zip(applied, move):
                self.assertTrue(close(got, want), (got, want))

    def test_unplaced_clutch_is_unchanged(self):
        site = derive(default_params()).sites[1]
        move = site.bolt_axes()
        for got, want in zip(frames.conjugate(move, frame_axes(Frame())), move):
            self.assertTrue(close(got, want), (got, want))

    def test_a_turned_move_is_displaced_by_the_frames_translation(self):
        # knowledge/sketch-and-features.md: without the conjugation a move that turns the body comes out displaced by
        # (R - I) times the placement's translation (a bolt turned 180 degrees, placed at z = 48: 96 mm low).
        w = frame_axes(placement_frame((0.0, 0.0, 48.0), (0.0, 0.0, 1.0)))
        move = ((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0))  # a turn of 180 degrees about Y
        naive = frames.compose(frames.compose(frames.inverse(w), move), w)
        self.assertTrue(close(naive[0], (0.0, 0.0, -96.0)), naive[0])


if __name__ == "__main__":
    unittest.main()
