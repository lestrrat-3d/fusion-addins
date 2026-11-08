import os
import re
import unittest

from tests.support import KIT_DIR, fp, make_fake_addin, scratch_dir, write


def try_symlink(src, dst):
    try:
        os.symlink(src, dst)
    except (OSError, NotImplementedError):
        return False
    return True


class FingerprintTest(unittest.TestCase):
    def test_golden_digest(self):
        d = scratch_dir(self) / "demo"
        write(d / "commands" / "__init__.py", b"")
        write(d / "config.py", b"A = 1\r\n")
        write(d / "demo.manifest", b"{}\n")
        write(d / "demo.py", b"")
        write(d / "lib" / "k" / "__init__.py", b"X = 2\n")
        self.assertEqual(
            fp.compute(str(d)),
            "bfbc3cc68fa01b1ed45355039c5c7db78c0f46877a146120aeaf022646a63021",
        )
        write(d / "config.py", b"A = 1\n")
        self.assertEqual(
            fp.compute(str(d)),
            "864e189f28ec4d937eed4cb2f27a8b7f1b452570772e2d1134237fad29789364",
        )

    def test_shipped_files_allowlist(self):
        d = make_fake_addin(scratch_dir(self))
        self.assertEqual(
            fp.shipped_files(str(d)),
            ["commands/__init__.py", "config.py", "demo.manifest", "demo.py", "lib/demogen/__init__.py"],
        )

    def test_optional_files_ship(self):
        d = make_fake_addin(scratch_dir(self))
        for name in ("LICENSE", "NOTICE", "AddInIcon.svg", "other.txt"):
            write(d / name, b"x")
        shipped = fp.shipped_files(str(d))
        for name in ("LICENSE", "NOTICE", "AddInIcon.svg"):
            self.assertIn(name, shipped)
        self.assertNotIn("other.txt", shipped)

    def test_artifacts_do_not_change_digest(self):
        d = make_fake_addin(scratch_dir(self), extras=False)
        before = fp.compute(str(d))
        for rel in (
            ".tmp/run.log",
            "lib/x.log",
            "lib/demogen/__pycache__/a.pyc",
            "commands/.DS_Store",
            "tests/t.py",
            "README.md",
        ):
            write(d / rel, b"junk")
        self.assertEqual(fp.compute(str(d)), before)

    def test_content_and_name_changes_digest(self):
        d = make_fake_addin(scratch_dir(self), extras=False)
        before = fp.compute(str(d))
        write(d / "config.py", b"DEBUG = True\n")
        changed = fp.compute(str(d))
        self.assertNotEqual(changed, before)
        (d / "lib" / "demogen" / "__init__.py").rename(d / "lib" / "demogen" / "core.py")
        self.assertNotEqual(fp.compute(str(d)), changed)

    def test_is_excluded(self):
        for rel in (".tmp/run.log", "lib/__pycache__/a.py", "a.pyc", "lib/x.log", "lib/.hidden/a.py"):
            self.assertTrue(fp.is_excluded(rel), rel)
        for rel in ("lib/a.py", "commands/logger.py"):
            self.assertFalse(fp.is_excluded(rel), rel)

    def test_symlink_rejected(self):
        scratch = scratch_dir(self)
        d = make_fake_addin(scratch, "demo")
        if not try_symlink(d / "config.py", d / "lib" / "demogen" / "link.py"):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            fp.shipped_files(str(d))
        d2 = make_fake_addin(scratch / "second", "demo")
        (d2 / "lib").rename(scratch / "reallib")
        os.symlink(scratch / "reallib", d2 / "lib")
        with self.assertRaises(ValueError):
            fp.shipped_files(str(d2))

    def test_posix_paths(self):
        d = make_fake_addin(scratch_dir(self))
        for rel in fp.shipped_files(str(d)):
            self.assertNotIn("\\", rel)

    def test_digest_map_matches_digest_files(self):
        scratch = scratch_dir(self)
        d = make_fake_addin(scratch, extras=False)
        rels = fp.shipped_files(str(d))
        by_root = fp.digest_files(str(d), rels)
        self.assertEqual(by_root, fp.digest_map({rel: str(d / rel) for rel in rels}))
        # Sources in two different dirs hash like the same files copied into one folder.
        left, right, joined = scratch / "left", scratch / "right", scratch / "joined"
        for rel in rels:
            side = left if rel.startswith(("lib/", "commands/")) else right
            write(side / rel, (d / rel).read_bytes())
            write(joined / rel, (d / rel).read_bytes())
        mapped = {rel: str((left if (left / rel).exists() else right) / rel) for rel in rels}
        self.assertEqual(fp.digest_map(mapped), fp.compute(str(joined), "demo"))

    def test_autodesk_headers(self):
        for name in ("event_utils.py", "general_utils.py"):
            first = (KIT_DIR / name).read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, "#  Copyright 2022 by Autodesk, Inc.", name)

    def test_short(self):
        self.assertEqual(fp.short("ab" * 32), "ab" * 6)

    def test_stdlib_only(self):
        text = (KIT_DIR / "fingerprint.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*(import|from)\s+(adsk|\.)", text, re.MULTILINE))

    def test_canonical_kit_contents(self):
        self.assertEqual(
            fp.tree_files(str(KIT_DIR)),
            ["__init__.py", "event_utils.py", "fingerprint.py", "general_utils.py"],
        )


if __name__ == "__main__":
    unittest.main()
