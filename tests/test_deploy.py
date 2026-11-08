import contextlib
import io
import unittest
from unittest import mock

from tests.support import (
    KIT_DIR,
    ROOT,
    bundle_rels,
    deploy,
    fake_checkout,
    fp,
    make_fake_addin,
    scratch_dir,
    write,
)


def run_main(argv, environ):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = deploy.main(argv, environ)
    return rc, out.getvalue(), err.getvalue()


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.scratch = scratch_dir(self)
        patcher = mock.patch.object(deploy, "CONF_PATH", self.scratch / "none.conf")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.src = make_fake_addin(self.scratch / "src")
        self.dest = self.scratch / "AddIns" / "demo"
        self.env = {"FUSION_ADDIN_DIR": str(self.dest)}
        self.dest.parent.mkdir(parents=True)

    def test_deploy_ships_exact_set(self):
        rc, _, _ = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(fp.tree_files(str(self.dest)), bundle_rels(self.src))
        self.assertTrue((self.dest / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes())
        for rel in fp.tree_files(str(KIT_DIR)):
            same = (self.dest / "lib" / "addinkit" / rel).read_bytes() == (KIT_DIR / rel).read_bytes()
            self.assertTrue(same, rel)
        for name in ("tests", "README.md", "docs", ".tmp", "__pycache__"):
            self.assertFalse((self.dest / name).exists(), name)

    def test_deploy_output(self):
        rc, out, _ = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 0)
        self.assertEqual(
            out.splitlines(),
            [
                f"destination {self.dest} (from FUSION_ADDIN_DIR)",
                "deployed demo: 10 files",
                f"fingerprint {deploy.bundle_digest(self.src)}",
            ],
        )

    def test_deploy_mirrors(self):
        write(self.dest / "lib" / "old.py", b"x")
        write(self.dest / "lib" / "olddir" / "x.py", b"x")
        write(self.dest / ".tmp" / "run.log", b"x")
        write(self.dest / "commands" / "__pycache__" / "c.pyc", b"x")
        rc, _, _ = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 0)
        self.assertFalse((self.dest / "lib" / "old.py").exists())
        self.assertFalse((self.dest / "lib" / "olddir").exists())
        self.assertTrue((self.dest / ".tmp" / "run.log").exists())
        self.assertTrue((self.dest / "commands" / "__pycache__" / "c.pyc").exists())
        self.assertEqual(fp.compute(str(self.dest), "demo"), deploy.bundle_digest(self.src))

    def test_deploy_overlap_rejected(self):
        before = fp.shipped_files(str(self.src))
        rc, _, err = run_main(["deploy", str(self.src)], {"FUSION_ADDIN_DIR": str(self.src)})
        self.assertEqual(rc, 2)
        self.assertIn("overlaps", err)
        self.assertEqual(fp.shipped_files(str(self.src)), before)

    def test_deploy_rejects_collision(self):
        write(self.src / "LICENSE", "x")
        rc, _, err = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 2)
        self.assertIn("LICENSE", err)
        self.assertFalse(self.dest.exists())

    def test_deploy_missing_checkout_license(self):
        checkout = fake_checkout(self)
        (checkout / "LICENSE").unlink()
        rc, _, err = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 2)
        self.assertIn("missing", err)

    def test_deploy_into_kit_rejected(self):
        checkout = fake_checkout(self)
        before = fp.tree_files(str(checkout / "lib" / "addinkit"))
        overlap = checkout / "lib" / "addinkit" / "demo"
        rc, _, err = run_main(["deploy", str(self.src)], {"FUSION_ADDIN_DIR": str(overlap)})
        self.assertEqual(rc, 2)
        self.assertIn("overlaps", err)
        self.assertEqual(fp.tree_files(str(checkout / "lib" / "addinkit")), before)

    def test_deploy_missing_required(self):
        (self.src / "config.py").unlink()
        rc, _, _ = run_main(["deploy", str(self.src)], self.env)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
