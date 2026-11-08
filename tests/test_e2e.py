import os
import subprocess
import sys
import unittest

from tests import support
from tests.support import ROOT, make_fake_addin, scratch_dir


class EndToEndTest(unittest.TestCase):
    def test_full_cycle(self):
        scratch = scratch_dir(self)
        dest = scratch / "AddIns" / "e2edemo"
        dest.parent.mkdir(parents=True)
        src = make_fake_addin(scratch / "src", "e2edemo")
        env = {**os.environ, "FUSION_ADDIN_DIR": str(dest)}

        def cli(*args):
            return subprocess.run(
                [sys.executable, str(ROOT / "deploy.py"), *args],
                capture_output=True,
                text=True,
                env=env,
            )

        r = cli("check", str(src))
        self.assertEqual(r.returncode, 0, r.stderr)
        check_lines = r.stdout.splitlines()
        self.assertEqual(check_lines[0], "check ok: e2edemo: 10 files shipped, 8 Python files compile")
        check_digest = check_lines[1].removeprefix("fingerprint ")

        r = cli("fingerprint", str(src))
        self.assertEqual(r.returncode, 0, r.stderr)
        digest = r.stdout.strip()
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(check_digest, digest)

        r = cli("deploy", str(src))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"fingerprint {digest}", r.stdout.splitlines())

        deployed_fp = support.load_module("deployed_fp", dest / "lib" / "addinkit" / "fingerprint.py")
        self.assertEqual(deployed_fp.compute(str(dest)), digest)

        r = cli("verify", str(src))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.rstrip("\n").endswith(f"match {digest}"), r.stdout)

        with open(dest / "config.py", "ab") as fh:
            fh.write(b"# edited\n")
        r = cli("verify", str(src))
        self.assertEqual(r.returncode, 1)
        self.assertIn("mismatch", r.stdout)
        self.assertIn("  changed: config.py", r.stdout.splitlines())

        self.assertEqual(cli("deploy", str(src)).returncode, 0)
        self.assertEqual(cli("verify", str(src)).returncode, 0)


if __name__ == "__main__":
    unittest.main()
