import json
import re
import unittest

from tests.support import ROOT, deploy, fp, scratch_dir

ADDINS_DIR = ROOT / "addins"


def addin_dirs():
    if not ADDINS_DIR.is_dir():
        return []
    return sorted(
        d for d in ADDINS_DIR.iterdir() if d.is_dir() and (d / f"{d.name}.manifest").is_file()
    )


class AddinInvariantsTest(unittest.TestCase):
    def test_no_init_in_root_or_addin_roots(self):
        self.assertFalse((ROOT / "__init__.py").exists())
        self.assertFalse((ROOT / "lib" / "__init__.py").exists())
        self.assertFalse((ADDINS_DIR / "__init__.py").exists())
        for d in addin_dirs():
            self.assertFalse((d / "__init__.py").exists(), d.name)

    def test_addin_folders_have_no_bundled_paths(self):
        dirs = addin_dirs()
        if not dirs:
            self.skipTest("no add-ins yet")
        for d in dirs:
            with self.subTest(addin=d.name):
                self.assertEqual(deploy.bundled_collisions(fp.shipped_files(str(d))), [])

    def test_checkout_layout(self):
        allowed = {"addins", "lib", "deploy.py", "LICENSE", "README.md", "tests"}
        names = {
            p.name for p in ROOT.iterdir() if not p.name.startswith(".") and p.name != "__pycache__"
        }
        self.assertEqual(sorted(names - allowed), [])

    def test_manifest_ids_unique(self):
        dirs = addin_dirs()
        if not dirs:
            self.skipTest("no add-ins yet")
        owners = {}
        for d in dirs:
            ident = json.loads((d / f"{d.name}.manifest").read_bytes()).get("id")
            owners.setdefault(ident, []).append(d.name)
        dupes = {i: names for i, names in owners.items() if len(names) > 1}
        self.assertEqual(dupes, {})

    def test_each_addin_passes_check(self):
        dirs = addin_dirs()
        if not dirs:
            self.skipTest("no add-ins yet")
        scratch = scratch_dir(self)
        for d in dirs:
            with self.subTest(addin=d.name):
                self.assertEqual(deploy.check(d, scratch)[0], [])

    def test_geometry_has_no_adsk_import(self):
        dirs = addin_dirs()
        if not dirs:
            self.skipTest("no add-ins yet")
        pattern = re.compile(r"^\s*(import|from)\s+adsk\b", re.MULTILINE)
        offenders = []
        for d in dirs:
            gen = d / "lib" / f"{d.name}gen"
            for path in sorted(gen.rglob("*.py")):
                if pattern.search(path.read_text(encoding="utf-8")):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
