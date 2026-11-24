import unittest

import _support  # noqa: F401
from gen import bodies
from gen.bodies import Found


def tree_for(spec=None, drop=(), extra=None):
    """A Found tree that matches the container tree, with the built bodies in place. `drop` names containers left out."""
    want = bodies.expected_bodies()

    def make(node):
        kids = tuple(make(c) for c in node.children if c.key not in drop)
        return Found(node.name, tuple(want[node.key]), kids)

    return [make(n) for n in bodies.TREE if n.key not in drop]


class LayoutTest(unittest.TestCase):
    def test_the_gallery_has_75_bodies_and_the_add_in_builds_all_of_them(self):
        self.assertEqual(len(bodies.ALL_BODY_NAMES), bodies.FULL_BODY_COUNT)
        self.assertEqual(len(set(bodies.ALL_BODY_NAMES)), 75)
        self.assertEqual(bodies.EXPECTED_BODY_COUNT, 75)
        self.assertEqual(bodies.BODY_NAMES, bodies.ALL_BODY_NAMES)

    def test_body_groups(self):
        self.assertEqual(sum(1 for s in bodies.ALL_SPECS if s.stage == 1), 2 + 1 + 7 + 2 + 10 + 10)
        self.assertEqual(bodies.BODY_NAMES[:3], ("Front Wall", "Rear Wall", "Guide Plate"))

    def test_flag_and_clicker_bodies(self):
        later = {s.name: s.stage for s in bodies.ALL_SPECS if s.stage > 1}
        self.assertEqual(sum(1 for v in later.values() if v == 2), 3 + 7 + 14 + 14)
        self.assertEqual(sum(1 for v in later.values() if v == 3), 5)
        for name in ("Guide Plate", "Cradle Plate", "Top Plate", "Slider A", "Yellow Face G", "Black Body A"):
            self.assertEqual(later[name], 2)
        for name in ("Hub", "Rotor", "Housing", "Button", "Spring"):
            self.assertEqual(later[name], 3)

    def test_every_body_has_a_container(self):
        keys = {n.key for n in bodies.walk()}
        for spec in bodies.ALL_SPECS:
            self.assertIn(spec.container, keys, spec.name)

    def test_container_names_of_the_gallery(self):
        names = {n.name for n in bodies.walk()}
        self.assertEqual(names, {"Frame", "Walls", "Plates", "Camshaft", "Shaft", "Cams", "Click Indexer", "Hub",
                                 "Rotor", "Housing", "Button", "Spring", "Segment Sliders", "Flags", "Flag",
                                 "Yellow Face", "Black Body", "Pivot Blocks", "Bearings", "Bolts", "Nuts"})
        self.assertEqual(sum(1 for n in bodies.walk() if n.name == "Flag"), 7)

    def test_body_counts_per_container_when_complete(self):
        counts = {}
        for s in bodies.ALL_SPECS:
            counts[s.container] = counts.get(s.container, 0) + 1
        self.assertEqual(counts["Frame/Walls"], 2)
        self.assertEqual(counts["Frame/Plates"], 3)
        self.assertEqual(counts["Camshaft/Cams"], 7)
        self.assertEqual(counts["Segment Sliders"], 7)
        self.assertEqual(counts["Pivot Blocks"], 14)
        self.assertEqual(counts["Bearings"], 2)
        self.assertEqual(counts["Bolts"], 10)
        self.assertEqual(counts["Nuts"], 10)

    def test_site_names(self):
        self.assertEqual(bodies.site_index("Bolt T1"), 0)
        self.assertEqual(bodies.site_index("Nut G4"), 7)
        self.assertEqual(bodies.site_index("Bolt H2"), 9)
        self.assertTrue(bodies.is_bolt("Bolt H1") and not bodies.is_nut("Bolt H1"))

    def test_base_name(self):
        self.assertEqual(bodies.base_name("Bolts (1)"), "Bolts")
        self.assertEqual(bodies.base_name("Flag (12)"), "Flag")
        self.assertEqual(bodies.base_name("Bolts"), "Bolts")


class CheckTreeTest(unittest.TestCase):
    def test_a_matching_tree_passes(self):
        top, results = bodies.check_tree(tree_for(), 0)
        self.assertTrue(top.ok, top.detail)
        self.assertEqual(len(results), sum(1 for _ in bodies.walk()))
        self.assertTrue(all(r.ok for r in results), [(r.name, r.detail) for r in results if not r.ok])

    def test_fusion_numbered_names_pass(self):
        found = tree_for()
        renamed = [Found(f.name + " (1)", f.bodies, f.children) for f in found]
        top, results = bodies.check_tree(renamed, 0)
        self.assertTrue(top.ok and all(r.ok for r in results))

    def test_a_body_outside_a_container_fails(self):
        top, _ = bodies.check_tree(tree_for(), 1)
        self.assertFalse(top.ok)
        self.assertIn("1 bodies outside containers", top.detail)

    def test_missing_container(self):
        top, results = bodies.check_tree(tree_for(drop=("Bolts",)), 0)
        self.assertFalse(top.ok)
        self.assertIn("missing container Bolts", top.detail)
        self.assertEqual([r.name for r in results if not r.ok], ["Bolts"])

    def test_missing_and_extra_bodies(self):
        found = tree_for()
        walls = found[0].children[0]
        broken = Found(walls.name, ("Front Wall", "Stray"), walls.children)
        found[0] = Found(found[0].name, found[0].bodies, (broken,) + found[0].children[1:])
        _, results = bodies.check_tree(found, 0)
        bad = {r.name: r.detail for r in results if not r.ok}
        self.assertEqual(list(bad), ["Frame/Walls"])
        self.assertIn("missing Rear Wall", bad["Frame/Walls"])
        self.assertIn("extra Stray", bad["Frame/Walls"])

    def test_extra_child_is_reported_on_its_parent(self):
        found = tree_for()
        cams = found[1].children[1]
        found[1] = Found(found[1].name, found[1].bodies,
                         (found[1].children[0], Found(cams.name, cams.bodies, (Found("Oops", (), ()),))))
        _, results = bodies.check_tree(found, 0)
        bad = {r.name: r.detail for r in results if not r.ok}
        self.assertEqual(list(bad), ["Camshaft/Cams"])
        self.assertIn("extra child Oops", bad["Camshaft/Cams"])

    def test_flag_and_clicker_containers_hold_their_bodies(self):
        want = bodies.expected_bodies()
        self.assertEqual(want["Frame/Plates"], ["Guide Plate", "Cradle Plate", "Top Plate"])
        self.assertEqual(want["Click Indexer/Hub"], ["Hub"])
        self.assertEqual(len(want["Segment Sliders"]), 7)
        self.assertEqual(want["Flags/Flag 1/Yellow Face"], ["Yellow Face A"])
        self.assertEqual(want["Pivot Blocks"][:2], ["Pivot Block A -u", "Pivot Block A +u"])
        self.assertEqual(len(want["Pivot Blocks"]), 14)
        self.assertEqual(bodies.PIVOT_ENDS["Pivot Block G +u"], (6, 1.0))


if __name__ == "__main__":
    unittest.main()
