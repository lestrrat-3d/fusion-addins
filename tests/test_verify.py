import contextlib
import io
import unittest
from unittest import mock

from tests.support import deploy, fake_checkout, make_fake_addin, scratch_dir, write


def run_main(argv, environ):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = deploy.main(argv, environ)
    return rc, out.getvalue(), err.getvalue()


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.scratch = scratch_dir(self)
        patcher = mock.patch.object(deploy, "CONF_PATH", self.scratch / "none.conf")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.src = make_fake_addin(self.scratch / "src")
        self.dest = self.scratch / "AddIns" / "demo"
        self.dest.parent.mkdir(parents=True)
        self.env = {"FUSION_ADDIN_DIR": str(self.dest)}
        self.repo_hex = deploy.bundle_digest(self.src)

    def deploy(self):
        rc, _, _ = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 0)

    def verify(self):
        return run_main(["verify", str(self.src)], self.env)

    def test_verify_match(self):
        self.deploy()
        rc, out, _ = self.verify()
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines()[-1], f"match {self.repo_hex}")

    def test_verify_changed_file(self):
        self.deploy()
        with open(self.dest / "config.py", "ab") as fh:
            fh.write(b"# edited\n")
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        self.assertIn("mismatch", out)
        self.assertIn(f"  repo     {self.repo_hex}", out)
        self.assertIn("  changed: config.py", out.splitlines())

    def test_verify_extra_and_missing(self):
        self.deploy()
        write(self.dest / "lib" / "extra.py", b"")
        (self.dest / "commands" / "__init__.py").unlink()
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        lines = out.splitlines()
        self.assertIn("  only in repo: commands/__init__.py", lines)
        self.assertIn("  only in deployed: lib/extra.py", lines)

    def test_verify_deployed_kit_changed(self):
        self.deploy()
        with open(self.dest / "lib" / "addinkit" / "general_utils.py", "ab") as fh:
            fh.write(b"# edited\n")
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        self.assertIn("  changed: lib/addinkit/general_utils.py", out.splitlines())

    def test_verify_checkout_kit_changed(self):
        checkout = fake_checkout(self)
        self.deploy()
        with open(checkout / "lib" / "addinkit" / "general_utils.py", "ab") as fh:
            fh.write(b"# edited\n")
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        self.assertIn("  changed: lib/addinkit/general_utils.py", out.splitlines())

    def test_verify_ignores_artifacts(self):
        self.deploy()
        write(self.dest / ".tmp" / "run.log", b"x")
        write(self.dest / "__pycache__" / "a.pyc", b"x")
        rc, _, _ = self.verify()
        self.assertEqual(rc, 0)

    def test_verify_missing_dest(self):
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        self.assertIn("deployed folder missing:", out)
        self.assertIn("mismatch", out)

    def test_verify_truncates(self):
        self.deploy()
        for i in range(25):
            write(self.dest / "lib" / f"x{i}.py", b"")
        rc, out, _ = self.verify()
        self.assertEqual(rc, 1)
        lines = out.splitlines()
        self.assertEqual(len([ln for ln in lines if ln.startswith("  only in deployed:")]), 20)
        self.assertIn("  ... and 5 more", lines)


if __name__ == "__main__":
    unittest.main()
