import unittest

import _support  # noqa: F401
from gen import bodies
from gen.params import Params
from gen.validate import derive


class LayoutTest(unittest.TestCase):
    def test_counts_and_names(self):
        self.assertEqual(len(bodies.body_names(False)), 10)
        self.assertEqual(len(bodies.body_names(True)), 17)
        self.assertEqual(bodies.expected_count(True), 17)
        self.assertEqual(bodies.containers(False), ("Hub", "Ring", "Plates", "Bolts", "Nuts"))
        self.assertEqual(bodies.containers(True)[-1], "Adapter")

    def test_every_body_has_a_container(self):
        for name in bodies.body_names(True):
            self.assertIn(bodies.BODY_CONTAINER[name], bodies.containers(True))

    def test_expected_bodies_per_container(self):
        want = bodies.expected_bodies(True)
        self.assertEqual(want["Plates"], ["Back Plate", "Cover"])
        self.assertEqual(len(want["Bolts"]), 6)  # two lengths, as in the gallery's adapter document
        self.assertEqual(len(want["Nuts"]), 6)
        self.assertEqual(want["Adapter"], ["Adapter"])
        self.assertNotIn("Adapter", bodies.expected_bodies(False))

    def test_sites_of_fasteners(self):
        dm = derive(Params())
        for i in range(3):
            self.assertIs(bodies.site_of(bodies.BOLTS[i], dm), dm.sites[i])
            self.assertIs(bodies.site_of(bodies.NUTS[i], dm), dm.sites[i])
            self.assertIs(bodies.site_of(bodies.MOUNT_BOLTS[i], dm), dm.mount_sites[i])
        with self.assertRaises(KeyError):
            bodies.site_of(bodies.HUB, dm)


class TreeTest(unittest.TestCase):
    def found(self, adapter=False):
        return [bodies.Found(c, tuple(n), ()) for c, n in bodies.expected_bodies(adapter).items()]

    def test_correct_tree(self):
        for adapter in (False, True):
            top, results = bodies.check_tree(self.found(adapter), 0, adapter)
            self.assertTrue(top.ok, top.detail)
            self.assertTrue(all(r.ok for r in results))
            self.assertEqual(len(results), len(bodies.containers(adapter)))

    def test_suffixed_names_are_the_same_container(self):
        found = [bodies.Found(f.name + " (1)", f.bodies, f.children) for f in self.found()]
        top, results = bodies.check_tree(found, 0, False)
        self.assertTrue(top.ok and all(r.ok for r in results))

    def test_problems(self):
        found = self.found()
        top, results = bodies.check_tree(found[:-1], 2, False)
        self.assertFalse(top.ok)
        self.assertIn("2 bodies outside containers", top.detail)
        self.assertIn("missing container Nuts", top.detail)
        self.assertEqual(results[-1].detail, "no component")
        found[0] = bodies.Found("Hub", (), ("x",))
        _, results = bodies.check_tree(found, 0, False)
        self.assertIn("missing Hub", results[0].detail)
        self.assertIn("extra child x", results[0].detail)

    def test_adapter_container_not_expected_without_the_adapter(self):
        top, _ = bodies.check_tree(self.found(True), 0, False)
        self.assertIn("extra container Adapter", top.detail)


if __name__ == "__main__":
    unittest.main()
