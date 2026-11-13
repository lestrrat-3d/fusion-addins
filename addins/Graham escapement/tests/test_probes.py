import math
import unittest

import _support  # noqa: F401
from gen import bodies, sections
from gen.constants import DEG
from gen.curves import loop_polygon
from gen.layout import layout
from gen.motion import state_at
from gen.params import default_params
from gen.gears import great_dims, pinion_dims
from gen.involute import gear_outline_polygon
from gen.polygon import point_in_polygon
from gen.pose import body_poses
from gen.probes import INSIDE, OUTSIDE, bore_points, collar_points, fastener_points, interaction_points, part_probes
from gen.spring import profile, spring_params

P = default_params()
G = layout(P)
STEP = math.radians(0.1)


def poly(loop):
    return loop_polygon(loop, max_step=STEP)


def inside(loop, x, y):
    return point_in_polygon(poly(loop), (x, y))


def near(c, r, x, y):
    return math.hypot(x - c[0], y - c[1]) < r


def d_void(d, x, y):
    """True inside the D family d = (arc radius, chord x)."""
    return math.hypot(x, y) < d[0] and x < d[1]


def d_bore(x, y):
    return d_void(sections.END_D, x, y)


def material(part, x, y, z):
    """Independent 2D oracle for a probe's part-local point, or None when z or the part is not a 2D case."""
    if part == "back_plate" and z == -3:
        if not inside(sections.plate_outline(98.0), x, y):
            return False
        if any(inside(sections.window_loop(G, sx), x, y) for sx in (-1.0, 1.0)):
            return False
        if any(near(c, 7.05, x, y) for c in sections.lip_centres(G)):
            return False
        return not any(near(c, 2.25, x, y) for c in sections.MOUNT_HOLES)
    if part == "front_plate" and z == 31:
        if not inside(sections.plate_outline(82.0), x, y):
            return False
        if any(inside(sections.window_loop(G, sx), x, y) for sx in (-1.0, 1.0)):
            return False
        return not any(near(c, 7.05, x, y) for c in sections.lip_centres(G))
    if part == "escape_wheel" and z == 23.5:
        if math.hypot(x, y) <= 33.0:
            return not any(inside(w, x, y) for w in sections.escape_windows()) and not d_void(sections.BODY_D, x, y)
        return inside(sections.escape_tooth(G), x, y)
    if part == "anchor" and z in (22.5, 23.5, 24.2):
        return inside(sections.anchor_outline(G), x, y) and not d_void(sections.BODY_D, x, y)
    if part == "anchor" and z == 25.0:
        return inside(sections.anchor_outline(G), x, y) and not near((0.0, 0.0), 3.75, x, y)
    if part in ("crutch", "winding_knob") and z == 36.5:
        base = inside(sections.crutch_outline(G), x, y) if part == "crutch" else math.hypot(x, y) < 9.0
        return base and not d_void(sections.KEYED_COUNTER_D, x, y)
    if part == "crutch" and z == 36.8:
        return inside(sections.crutch_outline(G), x, y) and not d_void(sections.KEYED_COUNTER_D, x, y)
    if part == "crutch" and z == 37.8:
        return inside(sections.crutch_outline(G), x, y) and not d_void(sections.END_D, x, y)
    if part == "pendulum" and z == 41.8:
        return (
            inside(sections.pendulum_outline(G), x, y)
            and not near((0.0, 0.0), 5.0, x, y)
            and not inside(sections.crutch_slot(), x, y)
        )
    if part == "great_wheel" and z == 7:
        return False if inside(sections.ratchet_tool_outline(), x, y) else None
    if part == "pawl_carrier" and z == 7:
        gang = 90 * DEG - G.carrier_offset
        core = math.hypot(x, y) < 7.5
        pawls = inside(sections.pawl_loop(gang), x, y) or inside(sections.pawl_loop(gang + math.pi), x, y)
        return (core or pawls) and not d_void(sections.DRIVE_D, x, y)
    if part == "mainspring" and z == 3:
        outer, bore, eye = profile(spring_params(), G.spring)
        hole = near(eye.center, eye.radius, x, y)
        return inside(outer, x, y) and not inside(bore, x, y) and not hole
    if part == "suspension_cap" and z == 46.05:
        return math.hypot(x, y) < 3.7 and not d_bore(x, y)
    if part == "spring_spacer" and z == 20:
        return math.hypot(x, y) < 3.7 and not d_void(sections.BODY_D, x, y)
    if part == "winding_knob" and z == 36.8:
        return math.hypot(x, y) < 9.0 and not d_void(sections.KEYED_COUNTER_D, x, y)
    if part == "winding_knob" and z == 37.8:
        return math.hypot(x, y) < 9.0 and not d_bore(x, y)
    if part == "arbor_collar" and z == 1.5:
        return math.hypot(x, y) < 3.7 and not d_void(sections.BODY_D, x, y)
    if part == "end_collar" and z == 1.5:
        return d_void(sections.KEYED_RING_D, x, y) and not d_bore(x, y)
    return None


class PartProbesTest(unittest.TestCase):
    def test_keys_and_expectations(self):
        probes = part_probes(G)
        self.assertEqual(set(probes), set(bodies.PARTS))
        for part, plist in probes.items():
            self.assertGreaterEqual(len(plist), 2, part)
            for pr in plist:
                self.assertIn(pr.expect, (INSIDE, OUTSIDE))
                self.assertEqual(len(pr.point), 3)

    def test_2d_probes_agree_with_outlines(self):
        checked = 0
        for part, plist in part_probes(G).items():
            for pr in plist:
                x, y, z = pr.point
                got = material(part, x, y, z)
                if got is None:
                    continue
                checked += 1
                self.assertEqual(got, pr.expect == INSIDE, f"{part} {pr.label} {pr.point}")
        self.assertGreater(checked, 60)

    def test_spring_strip_and_gap_are_one_pitch_apart(self):
        by = {pr.label: pr for pr in part_probes(G)["mainspring"]}
        self.assertAlmostEqual(by["strip"].point[1] - by["gap"].point[1], 1.5 / 2 + 1.1 / 2)

    def test_anchor_pallet_probes_sit_between_edge_angles(self):
        by = {pr.label: pr for pr in part_probes(G)["anchor"]}
        for label in ("entry pallet", "exit pallet"):
            self.assertAlmostEqual(math.hypot(*by[label].point[:2]), 40.0)


class InteractionTest(unittest.TestCase):
    def test_mesh_points_exist_and_are_near_mesh(self):
        pts = interaction_points(G, state_at(G, P.phase))
        mesh = [p for p in pts if p.label.startswith("mesh")]
        self.assertGreater(len(mesh), 40)
        self.assertEqual({p.target for p in mesh}, {"Great Wheel", "Escape Wheel"})
        for p in mesh:
            self.assertLessEqual(math.hypot(p.point[0], p.point[1] + 11.0), 15.0 + 1e-9)
            self.assertEqual(p.point[2], 5.0)

    def test_event_counts(self):
        pts = interaction_points(G, state_at(G, P.phase))
        self.assertEqual(len([p for p in pts if p.label.startswith("escapement")]), 30 * 2 * 5)
        self.assertEqual(len([p for p in pts if p.label.startswith("coupling")]), 16)
        self.assertEqual({p.target for p in pts if p.label.startswith("coupling")}, {"Pendulum"})
        self.assertEqual({round(p.point[2], 9) for p in pts if p.label.startswith("coupling")}, {41.55})
        self.assertEqual({p.target for p in pts if p.label.startswith("escapement")}, {"Anchor"})

    def test_escapement_and_coupling_points_outside_target_outline(self):
        """Points are posed back into the target's own frame and checked against its 2D outline at the pose."""
        for phase in (0.0, 0.25, 0.6):
            s = state_at(G, phase)
            poses = body_poses(G, s)
            anchor = poses[bodies.ANCHOR]
            pendulum = poses[bodies.PENDULUM]
            great = gear_outline_polygon(great_dims(P), 60)
            pinion = gear_outline_polygon(pinion_dims(P), 60, angle=G.pinion_phase)
            for pt in interaction_points(G, s):
                if pt.label.startswith("mesh"):
                    pose = poses[bodies.GREAT_WHEEL if pt.target == "Great Wheel" else bodies.ESCAPE_WHEEL]
                    x, y, _ = pose.unapply(pt.point)
                    outline = great if pt.target == "Great Wheel" else pinion
                    self.assertFalse(point_in_polygon(outline, (x, y)), f"phase {phase} {pt.label}")
                elif pt.label.startswith("escapement"):
                    x, y, _ = anchor.unapply(pt.point)
                    self.assertFalse(
                        inside(sections.anchor_outline(G), x, y) and not d_bore(x, y), f"phase {phase} {pt.label}"
                    )
                elif pt.label.startswith("coupling"):
                    x, y, _ = pendulum.unapply(pt.point)
                    self.assertFalse(
                        inside(sections.pendulum_outline(G), x, y)
                        and not inside(sections.crutch_slot(), x, y)
                        and not near((0.0, 0.0), 5.0, x, y),
                        f"phase {phase} {pt.label}",
                    )

    def test_collar_and_bore_counts(self):
        s = state_at(G, P.phase)
        col, bor = collar_points(G, s), bore_points(G, s)
        self.assertEqual((len(col), len(bor)), (94, 196))
        self.assertTrue(all(p.label.startswith("collar") and " #" in p.label for p in col))
        self.assertTrue(all(p.label.startswith("bore") and " #" in p.label for p in bor))
        self.assertEqual(
            {p.target for p in col},
            {"Escape Wheel", "Anchor", "Great Wheel", "Crutch", "Winding Knob"},
        )
        self.assertEqual(len([p for p in col if p.label.startswith("collar crutch")]), 15)
        self.assertEqual(len([p for p in bor if p.label.startswith("bore great wheel")]), 16)
        self.assertEqual(len({p.target for p in bor}), 13)

    def test_collar_and_bore_points_lie_in_the_target_hole(self):
        _, bore_loop, _ = profile(spring_params(), G.spring)
        bore_poly = poly(bore_loop)

        def hole(label, x, y):
            """True when (x, y), in the target's frame at the label's z, lies in the hole the label names."""
            r = math.hypot(x, y)
            rows = {
                "collar escape front": r < 3.75, "collar escape rear": r < 3.75, "collar pallet front": r < 3.75,
                "collar great wheel": r < 4.10, "collar crutch": d_void(sections.KEYED_COUNTER_D, x, y),
                "collar knob": d_void(sections.KEYED_COUNTER_D, x, y),
                "bore escape wheel": d_void(sections.BODY_D, x, y),
                "bore escape rear collar": d_void(sections.BODY_D, x, y),
                "bore anchor": d_void(sections.BODY_D, x, y),
                "bore pallet front collar": d_void(sections.BODY_D, x, y),
                "bore crutch collar": d_void(sections.END_D, x, y), "bore crutch": d_void(sections.END_D, x, y),
                "bore great wheel": r < 3.45, "bore pawl carrier": d_void(sections.DRIVE_D, x, y),
                "bore mainspring": point_in_polygon(bore_poly, (x, y)),
                "bore spring spacer": d_void(sections.BODY_D, x, y),
                "bore knob collar": d_void(sections.END_D, x, y), "bore knob": d_void(sections.END_D, x, y),
                "bore suspension cap": d_void(sections.END_D, x, y),
            }
            key = label.rsplit(" #", 1)[0]
            return rows[key]

        for phase in (0.0, 0.25, 0.6):
            s = state_at(G, phase)
            poses = body_poses(G, s)
            for pt in collar_points(G, s) + bore_points(G, s):
                x, y, _ = poses[pt.target].unapply(pt.point)
                self.assertTrue(hole(pt.label, x, y), f"phase {phase} {pt.label}")

    def test_fit_points(self):
        pts = fastener_points(G)
        self.assertEqual(len(pts), 4 * (8 * 4 + 6))
        targets = {p.target for p in pts}
        self.assertEqual(targets, {"Back Plate", "Front Plate"})
        for p in pts:
            self.assertTrue(p.label.startswith("fit"))
        shank = [p for p in pts if "shank z23" in p.label]
        self.assertEqual({p.target for p in shank}, {"Back Plate"})
        self.assertEqual(len(shank), 32)


if __name__ == "__main__":
    unittest.main()
