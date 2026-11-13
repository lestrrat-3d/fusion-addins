import unittest

import _support  # noqa: F401
from gen import bodies
from gen.containers import (
    BODY_CONTAINER,
    CONTAINER_PATHS,
    TOP_LEVEL,
    TOP_NAME,
    ContainerResult,
    Found,
    check_tree,
    container_of_part,
    expected_bodies,
    expected_children,
)


def tree(expected):
    """A Found per path as Fusion would read it back, children taken from the paths."""
    out = []
    for path, names in expected.items():
        out.append(Found(path, tuple(names), tuple(expected_children(path))))
    return out


class BodiesTest(unittest.TestCase):
    def test_body_names(self):
        self.assertEqual(len(bodies.BODY_NAMES), 36)
        self.assertEqual(len(set(bodies.BODY_NAMES)), 36)
        self.assertEqual(bodies.EXPECTED_BODY_COUNT, 36)
        self.assertEqual(bodies.BODY_NAMES[:3], ("Back Plate", "Front Plate", "Back Escape Bearing"))
        self.assertEqual(bodies.BODY_NAMES[8], "Pendulum Bearing")
        self.assertEqual(bodies.BODY_NAMES[-1], "Nut 4")
        self.assertEqual(len(bodies.PARTS), 22)
        self.assertEqual(set(bodies.PARTS), set(bodies.PART_BODIES))
        self.assertEqual(sum(len(v) for v in bodies.PART_BODIES.values()), 36)
        self.assertEqual(bodies.COLLAR_NAMES, ("Escape Rear Collar", "Pallet Front Collar", "Crutch Collar", "Knob Collar"))
        self.assertEqual(bodies.BODY_NAMES[24:28], bodies.COLLAR_NAMES)
        self.assertEqual(bodies.PARTS[17:19], ("arbor_collar", "end_collar"))
        self.assertEqual(bodies.part_of("Knob Collar"), "end_collar")
        self.assertEqual(bodies.part_of("Escape Rear Collar"), "arbor_collar")
        self.assertEqual(bodies.part_of("Bolt 3"), "bolt")
        self.assertEqual(bodies.part_of("Pendulum Bearing"), "bearing")
        with self.assertRaises(KeyError):
            bodies.part_of("nope")


class ContainersTest(unittest.TestCase):
    def test_paths_and_membership(self):
        self.assertEqual(TOP_NAME, "Graham Escapement")
        self.assertEqual(len(CONTAINER_PATHS), 20)
        self.assertEqual(CONTAINER_PATHS[0], ("Frame",))
        self.assertEqual(CONTAINER_PATHS[4], ("Escapement", "Escape Wheel"))
        self.assertEqual(CONTAINER_PATHS[-1], ("Nuts",))
        for path in CONTAINER_PATHS:
            if len(path) > 1:
                self.assertIn(path[:-1], CONTAINER_PATHS)
                self.assertLess(CONTAINER_PATHS.index(path[:-1]), CONTAINER_PATHS.index(path))
        self.assertEqual(set(BODY_CONTAINER), set(bodies.BODY_NAMES))
        self.assertEqual(container_of_part("suspension_cap"), ("Pendulum Assembly", "Suspension"))
        self.assertEqual(container_of_part("bearing"), ("Bearings",))
        got = expected_bodies()
        self.assertEqual(list(got), list(CONTAINER_PATHS))
        self.assertEqual(got[("Frame",)], ["Back Plate", "Front Plate"])
        self.assertEqual(got[("Escapement",)], [])
        self.assertEqual(got[("Collars",)], list(bodies.COLLAR_NAMES))
        self.assertEqual(CONTAINER_PATHS[-3], ("Collars",))
        self.assertEqual(TOP_LEVEL[-3:], ("Collars", "Bolts", "Nuts"))
        self.assertEqual(len(TOP_LEVEL), 9)
        self.assertEqual(container_of_part("arbor_collar"), ("Collars",))
        self.assertEqual(container_of_part("end_collar"), ("Collars",))
        self.assertEqual(len(got[("Bearings",)]), 7)
        self.assertEqual(sum(len(v) for v in got.values()), 36)
        self.assertEqual(expected_children(("Drive",)).__len__(), 6)
        self.assertEqual(expected_children(()).__len__(), 9)

    def test_pass(self):
        top, results = check_tree(tree(expected_bodies()), 0)
        self.assertTrue(top.ok, top.detail)
        self.assertEqual(len(results), 20)
        self.assertTrue(all(r.ok for r in results), [r.detail for r in results if not r.ok])
        self.assertIsInstance(results[0], ContainerResult)

    def test_missing_component(self):
        found = [f for f in tree(expected_bodies()) if f.path != ("Drive", "Mainspring")]
        top, results = check_tree(found, 0)
        bad = [r for r in results if not r.ok]
        self.assertEqual([r.path for r in bad], [("Drive", "Mainspring")])
        self.assertEqual(bad[0].detail, "no component")

    def test_extra_and_duplicate_top_level(self):
        found = tree(expected_bodies()) + [Found(("Spare",), (), ()), Found(("Frame",), (), ())]
        top, results = check_tree(found, 0)
        self.assertFalse(top.ok)
        self.assertIn("extra container Spare", top.detail)
        self.assertIn("duplicate container Frame", top.detail)
        frame = results[0]
        self.assertFalse(frame.ok)
        self.assertEqual(frame.detail, "2 components")

    def test_body_outside_containers(self):
        top, _ = check_tree(tree(expected_bodies()), 2)
        self.assertFalse(top.ok)
        self.assertIn("2 bodies outside containers", top.detail)

    def test_misplaced_body(self):
        want = {k: list(v) for k, v in expected_bodies().items()}
        want[("Nuts",)].remove("Nut 4")
        want[("Bolts",)].append("Nut 4")
        _, results = check_tree(tree(want), 0)
        bad = {r.path: r.detail for r in results if not r.ok}
        self.assertEqual(bad[("Nuts",)], "missing Nut 4")
        self.assertEqual(bad[("Bolts",)], "extra Nut 4")

    def test_unexpected_child_and_group_body(self):
        found = tree(expected_bodies())
        found = [
            Found(f.path, f.bodies, f.children + ("Stray",)) if f.path == ("Drive",) else f
            for f in found
        ]
        found = [Found(f.path, ("Back Plate",), f.children) if f.path == ("Escapement",) else f for f in found]
        _, results = check_tree(found, 0)
        bad = {r.path: r.detail for r in results if not r.ok}
        self.assertEqual(bad[("Drive",)], "extra child Stray")
        self.assertEqual(bad[("Escapement",)], "extra Back Plate")

    def test_name_list_is_capped(self):
        found = tree(expected_bodies())
        found = [Found(f.path, (), f.children) if f.path == ("Bearings",) else f for f in found]
        _, results = check_tree(found, 0)
        bad = [r for r in results if not r.ok]
        self.assertEqual(len(bad), 1)
        self.assertEqual(
            bad[0].detail, "missing Back Escape Bearing, Back Great Wheel Bearing, Back Pallet Bearing +4"
        )


if __name__ == "__main__":
    unittest.main()
