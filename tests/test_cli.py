import contextlib
import io
import os
import unittest

from tests.support import KIT_DIR, deploy, fp, make_fake_addin, scratch_dir, write


def run_main(argv, environ=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = deploy.main(argv, environ if environ is not None else {})
    return rc, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def test_fingerprint_command(self):
        d = make_fake_addin(scratch_dir(self))
        rc, out, _ = run_main(["fingerprint", str(d)])
        self.assertEqual(rc, 0)
        self.assertEqual(out, deploy.bundle_digest(d) + "\n")

    def test_fingerprint_missing_required(self):
        d = make_fake_addin(scratch_dir(self))
        (d / "config.py").unlink()
        rc, _, err = run_main(["fingerprint", str(d)])
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("deploy.py: demo: missing"), err)

    def test_unknown_addin(self):
        rc, _, err = run_main(["fingerprint", "no-such-addin-xyz"])
        self.assertEqual(rc, 2)
        self.assertIn("no add-in directory", err)

    def test_fingerprint_collision(self):
        d = make_fake_addin(scratch_dir(self))
        write(d / "LICENSE", "x")
        rc, _, err = run_main(["fingerprint", str(d)])
        self.assertEqual(rc, 2)
        self.assertIn("LICENSE", err)

    def test_bundle_sources(self):
        d = make_fake_addin(scratch_dir(self))
        sources = deploy.bundle_sources(d)
        keys = list(sources)
        expected = fp.shipped_files(str(d))
        expected += [f"lib/addinkit/{f}" for f in fp.tree_files(str(KIT_DIR))] + ["LICENSE"]
        self.assertEqual(keys, sorted(expected, key=lambda r: r.encode("utf-8")))
        self.assertEqual(sources["LICENSE"], deploy.LICENSE_PATH)
        self.assertEqual(sources["lib/addinkit/fingerprint.py"], deploy.KIT_DIR / "fingerprint.py")
        self.assertEqual(sources["config.py"], d / "config.py")

    def test_mirror_replaces_dir_with_file(self):
        scratch = scratch_dir(self)
        src, dest = scratch / "src", scratch / "dest"
        write(src / "a.py", b"print(1)\n")
        write(dest / "a.py" / "inner.txt", b"x")
        deploy.mirror(fp, {"a.py": src / "a.py"}, dest)
        self.assertTrue((dest / "a.py").is_file())
        self.assertTrue((dest / "a.py").read_bytes() == b"print(1)\n")

    def test_mirror_does_not_write_through_symlink(self):
        scratch = scratch_dir(self)
        src, dest = scratch / "src", scratch / "dest"
        write(src / "a.py", b"new")
        write(scratch / "outside.py", b"keep")
        dest.mkdir()
        try:
            os.symlink(scratch / "outside.py", dest / "a.py")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        deploy.mirror(fp, {"a.py": src / "a.py"}, dest)
        self.assertTrue((scratch / "outside.py").read_bytes() == b"keep")
        self.assertFalse((dest / "a.py").is_symlink())
        self.assertTrue((dest / "a.py").read_bytes() == b"new")

    def test_mirror_missing_parent(self):
        scratch = scratch_dir(self)
        src = scratch / "src"
        write(src / "a.py", b"x")
        with self.assertRaises(deploy.ToolError) as cm:
            deploy.mirror(fp, {"a.py": src / "a.py"}, scratch / "nope" / "x")
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
