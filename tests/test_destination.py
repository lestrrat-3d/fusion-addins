import glob
import unittest
from pathlib import Path

from tests.support import deploy, scratch_dir, write


class DestinationTest(unittest.TestCase):
    def setUp(self):
        self.scratch = scratch_dir(self)
        self.no_conf = self.scratch / "none.conf"

    def parent(self, name):
        p = self.scratch / name
        p.mkdir(parents=True)
        return p

    def resolve(self, environ=None, conf=None, patterns=None, name="demo"):
        return deploy.resolve_destination(name, environ or {}, conf or self.no_conf, patterns or [])

    def conf(self, text):
        path = self.scratch / "deploy.conf"
        write(path, text)
        return path

    def test_env_wins(self):
        a = self.parent("A")
        b = self.parent("u1/AddIns")
        conf = self.conf(f"[deploy]\naddins_dir = {a}\n")
        env = {"FUSION_ADDIN_DIR": str(self.scratch / "e" / "demo")}
        dest, source = self.resolve(env, conf, [str(self.scratch / "u*/AddIns")])
        self.assertEqual((dest, source), (self.scratch / "e" / "demo", "FUSION_ADDIN_DIR"))
        self.assertTrue(b.is_dir())

    def test_env_basename_mismatch(self):
        with self.assertRaises(deploy.ToolError) as cm:
            self.resolve({"FUSION_ADDIN_DIR": str(self.scratch / "other")})
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("must be named demo", str(cm.exception))

    def test_conf_wins_over_discovery(self):
        a = self.parent("A")
        self.parent("u1/AddIns")
        conf = self.conf(f"[deploy]\naddins_dir = {a}\n")
        dest, source = self.resolve({}, conf, [str(self.scratch / "u*/AddIns")])
        self.assertEqual((dest, source), (a / "demo", ".deploy.conf"))

    def assert_conf_error(self, text):
        conf = self.conf(text)
        with self.assertRaises(deploy.ToolError) as cm:
            self.resolve({}, conf)
        self.assertEqual(cm.exception.code, 2)
        self.assertTrue(str(cm.exception).startswith(str(conf)), str(cm.exception))

    def test_conf_missing_key(self):
        self.assert_conf_error("[deploy]\nother = 1\n")

    def test_conf_relative_path(self):
        self.assert_conf_error("[deploy]\naddins_dir = rel/path\n")

    def test_conf_dir_missing(self):
        self.assert_conf_error(f"[deploy]\naddins_dir = {self.scratch / 'absent'}\n")

    def test_conf_parse_error(self):
        self.assert_conf_error("not ini")

    def test_discovery_one(self):
        match = self.parent("u1/AddIns")
        dest, source = self.resolve({}, None, [str(self.scratch / "u*/AddIns")])
        self.assertEqual((dest, source), (match / "demo", "auto-discovery"))

    def test_discovery_zero(self):
        with self.assertRaises(deploy.ToolError) as cm:
            self.resolve({}, None, [str(self.scratch / "u*/AddIns")])
        msg = str(cm.exception)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("found 0 standard AddIns folders", msg)
        for label in ("Windows from WSL:", "Windows:", "macOS:"):
            self.assertIn(label, msg)

    def test_discovery_several(self):
        a = self.parent("u1/AddIns")
        b = self.parent("u2/AddIns")
        with self.assertRaises(deploy.ToolError) as cm:
            self.resolve({}, None, [str(self.scratch / "u*/AddIns")])
        msg = str(cm.exception)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("found 2", msg)
        self.assertIn(str(a), msg)
        self.assertIn(str(b), msg)

    def test_standard_patterns(self):
        with_appdata = deploy.standard_patterns({"APPDATA": "C:/x[1]"}, Path("/h"))
        self.assertEqual(len(with_appdata), 3)
        self.assertIn(glob.escape("C:/x[1]"), with_appdata[1])
        without = deploy.standard_patterns({}, Path("/h"))
        self.assertEqual(len(without), 2)
        literal = "/mnt/c/Users/*/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns"
        self.assertEqual(with_appdata[0], literal)
        self.assertEqual(without[0], literal)

    def test_ensure_separate(self):
        d = self.parent("src/demo")
        for other in (d, d.parent, d / "inner"):
            with self.assertRaises(deploy.ToolError) as cm:
                deploy.ensure_separate(d, other)
            self.assertEqual(cm.exception.code, 2)
        deploy.ensure_separate(d, self.scratch / "elsewhere" / "demo")
        deploy.ensure_separate(d, d.parent / "demo2")


if __name__ == "__main__":
    unittest.main()
