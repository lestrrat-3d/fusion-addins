import dataclasses
import math
import unittest

import _support  # noqa: F401
from gen import gears, layout
from gen.curves import Circle, loop_polygon, rotate
from gen.dims import derive
from gen.involute import gear_outline_polygon
from gen.params import KITS, default_params, default_params_for
from gen.phase import planet_orbit_angle, planet_tooth_angle, ring_tooth_angle
from gen.polygon import count_inside, point_in_polygon
from gen.probes import fastener_points, mesh_points, part_probes
from gen.sections import (
    bolt_hole_centers,
    carrier_plate_outline,
    cover_window_loops,
)

P1 = default_params()
D1 = derive(P1)
P2 = dataclasses.replace(P1, stages=2)
D2 = derive(P2)
A = P1.pressure_angle


def in_flat_tool(p, d, x, y):
    """The sun bore and carrier hole, written from the gallery's words: a disc 0.05 mm outside the shaft, cut by a flat
    0.05 mm outside the shaft's flat, which is Flat depth inside the disc's +X edge."""
    radius = d.shaft / 2 + 0.05
    if p.flat_depth == 0:
        return math.hypot(x, y) < d.shaft_bore / 2
    return math.hypot(x, y) < radius and x < radius - p.flat_depth


def in_thick_d(p, d, x, y, extra=0.0, pin=False):
    """The D thick part of a pin or shaft (extra = 0), or its socket and hole (extra = 0.05): a disc of the pin collar
    diameter (pin) or the shaft collar diameter, cut by a flat Flat depth inside the disc's +X edge."""
    radius = (d.pin_collar if pin else d.collar) / 2 + extra
    return math.hypot(x, y) < radius and (p.flat_depth == 0 or x < radius - p.flat_depth)


def in_flat(p, d, x):
    """The shaft's flat: the strip from Flat depth inside the shaft's +X edge outwards."""
    return x >= d.shaft / 2 - p.flat_depth


def in_nut_hex(lx, ly, half_width):
    """Inside a hexagon with corners on X (flats parallel to X) and the given apothem."""
    return all(abs(lx * math.cos(th) + ly * math.sin(th)) <= half_width for th in (math.pi / 6, math.pi / 2,
                                                                                    5 * math.pi / 6))


def in_spans(z, spans):
    return any(lo <= z <= hi for lo, hi in spans)


def in_ring_blank(p, d, x, y):
    """Is (x, y) inside the ring's outer wall or an ear, and outside every ear bore? Written from the gallery's words:
    an ear is a tab as long as the ring, 2 half-widths wide, out to a half circle round its bore."""
    half = p.ear_bore_diameter / 2 + 3
    centre = d.ring_outer + half
    in_ear = False
    for i in range(p.ear_count):
        a = math.pi / 2 + 2 * math.pi * i / p.ear_count
        along = x * math.cos(a) + y * math.sin(a)
        side = -x * math.sin(a) + y * math.cos(a)
        if math.hypot(along - centre, side) < p.ear_bore_diameter / 2:
            return False
        if abs(side) <= half and 0 <= along <= centre or math.hypot(along - centre, side) <= half:
            in_ear = True
    return math.hypot(x, y) <= d.ring_outer or in_ear


def material(p, d, part, pt):
    """Independent 2D oracle: is pt (part-local) inside the material of part?"""
    x, y, z = pt
    r = math.hypot(x, y)
    t, tc, tv = p.gear_thickness, p.carrier_thickness, p.cover_thickness
    wbp, wbs = d.planet_bearing.width, d.shaft_bearing.width
    if part == "sun":
        gd = gears.sun_gear(p)
        return 0 <= z <= t and point_in_polygon(gear_outline_polygon(gd, 60), (x, y)) and not in_flat_tool(p, d, x, y)
    if part == "planet":
        gd = gears.planet_gear(p)
        if not (0 <= z <= t) or not point_in_polygon(gear_outline_polygon(gd, 60), (x, y)):
            return False
        if r < d.planet_lip / 2:
            return False
        return not (z > t - wbp and r < d.planet_pocket / 2)
    if part == "ring":
        lo, hi = layout.part_local_z(p, d, "ring")
        gd = gears.ring_tool(p)
        tool = gear_outline_polygon(gd, 60, angle=ring_tooth_angle(p))
        if not (lo <= z <= hi) or not in_ring_blank(p, d, x, y) or point_in_polygon(tool, (x, y)):
            return False
        # Sacrificial bridge layers: the bolt hole is solid for 0.3 mm directly above each nut cavity, which is 2.0 mm
        # tall (1.6 mm nut and 0.2 mm each side) and starts 1 mm inside its end face.
        rm = layout.RING_MARGIN
        in_layer = p.sacrificial_bridging and (
            (rm + 3.0 <= z <= rm + 3.3) or (rm + d.ring_length - 1 <= z <= rm + d.ring_length - 0.7)
        )
        if not in_layer and not all(
            math.hypot(x - bx, y - by) > p.bolt_hole_diameter / 2 for bx, by in bolt_hole_centers(d)
        ):
            return False
        front = layout.RING_MARGIN + 1 <= z <= layout.RING_MARGIN + 2.8
        rear = layout.RING_MARGIN + d.ring_length - 2.8 <= z <= layout.RING_MARGIN + d.ring_length - 1
        if front or rear:
            for k, (sx, sy) in enumerate(bolt_hole_centers(d)):
                a = math.pi / 4 + k * math.pi / 2
                lx, ly = rotate((x - sx, y - sy), -(a - math.pi / 2))
                # Hexagon of 4.2 across flats (apothem 2.1) in the cavity's own frame.
                if in_nut_hex(lx, ly, 2.1):
                    return False
        return True
    if part == "cover":
        if tv - 2 <= z <= tv and any(
            math.hypot(x - bx, y - by) <= 2.0 for bx, by in bolt_hole_centers(d)
        ):
            return False
        if 0 <= z <= tv:
            if r > d.ring_outer or r < d.cover_lip / 2:
                return False
            if any(math.hypot(x - bx, y - by) < p.bolt_hole_diameter / 2 for bx, by in bolt_hole_centers(d)):
                return False
            return not any(point_in_polygon(loop_polygon(w), (x, y)) for w in cover_window_loops(p, d))
        return tv < z <= tv + wbs and d.cover_pocket / 2 < r < d.cover_boss / 2
    if part == "bolt":
        if -6 < z < 0:
            return r < 1.0
        if 0 <= z <= 2:
            if z >= 0.48 and r < 0.7:
                return False
            if z >= 1.0 and in_nut_hex(x, y, 0.75):
                return False
            return r < 1.9
        return False
    if part == "nut":
        return 0 <= z <= 1.6 and in_nut_hex(x, y, 2.0) and r > 1.0
    if part in ("housing_bearing", "planet_bearing"):
        b = d.shaft_bearing if part == "housing_bearing" else d.planet_bearing
        return 0 <= z <= b.width and b.bore_diameter / 2 + 1.5 < r < b.outer_diameter / 2 - 1.5
    if part == "carrier":
        if not 0 <= z <= tc:
            return False
        if not point_in_polygon(loop_polygon(carrier_plate_outline(p, d)), (x, y)) or in_thick_d(p, d, x, y, 0.05):
            return False
        # A D socket through the plate for each pin: the thick part's radius plus 0.05, flat on the outer side.
        for q in range(p.planet_count):
            lx, ly = rotate((x, y), -planet_orbit_angle(p, q))
            if in_thick_d(p, d, lx - d.orbit, ly, 0.05, pin=True):
                return False
        return True
    if part == "carrier_pin":
        g = p.stage_gap
        thick_bottom = -g + 0.5
        if -(p.gear_thickness + g) <= z <= thick_bottom:
            return r < d.pin / 2
        if thick_bottom < z <= tc:
            return in_thick_d(p, d, x, y, pin=True)
        return False
    spec = {
        "input_shaft": layout.input_shaft_spec,
        "link_shaft": layout.link_shaft_spec,
        "output_shaft": layout.output_shaft_spec,
    }[part](p, d)
    if not (spec.bottom <= z <= spec.top):
        return False
    if spec.thick_top is not None and z <= spec.thick_top:
        return in_thick_d(p, d, x, y)
    in_collar = spec.collar is not None and spec.collar[0] <= z <= spec.collar[1] and r < d.collar / 2
    if r >= d.shaft / 2 and not in_collar:
        return False
    return not (p.flat_depth > 0 and in_spans(z, spec.flats) and in_flat(p, d, x) and r < d.shaft / 2)


def fastener_target_material(p, d, target_name, pt):
    """Oracle material test for a cover or the ring in assembled coordinates (via the target's own pose)."""
    inst = next(i for i in layout.instances(p, d) if i.name == target_name)
    part = inst.part
    return material(p, d, part, inst.pose.unapply(pt))


class ProbesTest(unittest.TestCase):
    def check(self, p, d):
        probes = part_probes(p, d)
        want_parts = [x for x in layout.PARTS if x != "link_shaft" or p.stages > 1]
        self.assertEqual(sorted(probes), sorted(want_parts))
        for part, plist in probes.items():
            labels = [pr.label for pr in plist]
            self.assertEqual(len(labels), len(set(labels)), part)
            for pr in plist:
                with self.subTest(part=part, label=pr.label):
                    got = material(p, d, part, pr.point)
                    self.assertEqual(got, pr.expect == "inside", f"point {pr.point}")

    def test_probes_default(self):
        self.check(P1, D1)

    def test_probes_two_stages(self):
        self.check(P2, D2)

    def test_probes_every_kit(self):
        for kit in KITS:
            with self.subTest(kit=kit.name):
                p = default_params_for(kit.name)
                self.check(p, derive(p))
                p = dataclasses.replace(p, stages=2)
                self.check(p, derive(p))

    def test_probes_with_bridging(self):
        p = dataclasses.replace(P1, sacrificial_bridging=True)
        self.check(p, derive(p))

    def test_probes_ear_variants(self):
        for changes in ({"ear_count": 0}, {"ear_count": 1}, {"ear_count": 2, "ear_bore_diameter": 6.0},
                        {"ear_count": 6}, {"ear_count": 3, "ear_bore_diameter": 8.0}):
            with self.subTest(changes=changes):
                p = dataclasses.replace(P1, **changes)
                self.check(p, derive(p))
                labels = {pr.label for pr in part_probes(p, derive(p))["ring"]}
                self.assertEqual(sum(label.endswith(" bore") and label.startswith("ear ") for label in labels),
                                 p.ear_count)

    def test_probes_round_shafts(self):
        p = dataclasses.replace(P2, flat_depth=0.0)
        self.check(p, derive(p))

    def test_fastener_points(self):
        for p, d in ((P1, D1), (P2, D2)):
            pts = fastener_points(p, d)
            self.assertEqual(len(pts), 240)
            counts = {}
            for m in pts:
                counts[m.target] = counts.get(m.target, 0) + 1
                with self.subTest(label=m.label):
                    self.assertFalse(fastener_target_material(p, d, m.target, m.point), m.label)
            self.assertEqual(counts, {"Front Cover": 64, "Rear Cover": 64, "Ring Gear": 112})

    def test_probe_clearance_from_axial_faces(self):
        # Probes that expect material sit at least 0.5 mm from the part's end faces.
        for part, plist in part_probes(P1, D1).items():
            lo, hi = layout.part_local_z(P1, D1, part)
            for pr in (x for x in plist if x.expect == "inside"):
                with self.subTest(part=part, label=pr.label):
                    self.assertGreaterEqual(pr.point[2] - lo, 0.5 - 1e-9)
                    self.assertGreaterEqual(hi - pr.point[2], 0.5 - 1e-9)


def target_penetrations(p, d, points, tol=0.02):
    """Count mesh points that sit inside their target body's pure 2D outline by more than tol."""
    sun_gd = gears.sun_gear(p)
    planet_gd = gears.planet_gear(p)
    ring_gd = gears.ring_tool(p)
    sun = gear_outline_polygon(sun_gd, 60)
    ring = gear_outline_polygon(ring_gd, 60, angle=ring_tooth_angle(p))
    polys = {}
    for k in range(p.stages):
        polys[layout.sun_name(k)] = (sun, True)
        for i in range(p.planet_count):
            phi = planet_orbit_angle(p, i)
            center = (d.orbit * math.cos(phi), d.orbit * math.sin(phi))
            poly = gear_outline_polygon(planet_gd, 60, planet_tooth_angle(p, i), center)
            polys[layout.planet_name(k, i)] = (poly, True)
    polys[layout.RING_NAME] = (ring, False)
    total = 0
    for target, (poly, mat_inside) in polys.items():
        pts = [(m.point[0], m.point[1]) for m in points if m.target == target]
        total += count_inside(pts, poly, tol, material_inside=mat_inside)
    return total


class MeshPointsTest(unittest.TestCase):
    def test_default_has_no_penetration(self):
        pts = mesh_points(P1, D1)
        self.assertGreater(len(pts), 100)
        self.assertEqual(target_penetrations(P1, D1, pts), 0)

    def test_two_stages_targets_exist(self):
        names = {m.target for m in mesh_points(P2, D2)}
        self.assertIn("Sun Gear 2", names)
        self.assertIn("Planet Gear 2.3", names)
        self.assertIn("Ring Gear", names)

    def test_wrong_phase_has_penetration(self):
        pts = mesh_points(P1, D1, extra_turn=math.pi / 29)
        self.assertGreaterEqual(target_penetrations(P1, D1, pts), 1)


if __name__ == "__main__":
    unittest.main()
