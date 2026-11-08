import contextlib
import io
import json
import unittest
from unittest import mock

from tests.support import deploy, make_fake_addin, scratch_dir, write


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = deploy.main(argv)
    return rc, out.getvalue(), err.getvalue()


def set_manifest(addin_dir, **overrides):
    path = addin_dir / "demo.manifest"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.scratch = scratch_dir(self)
        self.check_dir = self.scratch / "check"

    def make(self, **kwargs):
        return make_fake_addin(self.scratch / "src", **kwargs)

    def test_check_ok(self):
        d = self.make()
        self.assertEqual(deploy.check(d, self.check_dir), ([], 10, 8, deploy.bundle_digest(d)))

    def test_check_cli_ok(self):
        d = self.make()
        with mock.patch.object(deploy, "CHECK_DIR", self.check_dir):
            rc, out, _ = run_main(["check", str(d)])
        self.assertEqual(rc, 0)
        self.assertEqual(
            out.splitlines(),
            [
                "check ok: demo: 10 files shipped, 8 Python files compile",
                f"fingerprint {deploy.bundle_digest(d)}",
            ],
        )

    def test_check_rejects_bundled_license(self):
        d = self.make()
        write(d / "LICENSE", "x")
        self.assertEqual(
            deploy.check(d, self.check_dir)[0],
            ["bundled by deploy.py, remove from the add-in folder: LICENSE"],
        )
        with mock.patch.object(deploy, "CHECK_DIR", self.check_dir):
            rc, _, _ = run_main(["check", str(d)])
        self.assertEqual(rc, 1)

    def test_check_rejects_bundled_kit(self):
        d = self.make()
        write(d / "lib" / "addinkit" / "x.py", "")
        self.assertEqual(
            deploy.check(d, self.check_dir)[0],
            ["bundled by deploy.py, remove from the add-in folder: lib/addinkit/x.py"],
        )

    def test_check_missing_config(self):
        d = self.make()
        (d / "config.py").unlink()
        self.assertEqual(deploy.check(d, self.check_dir)[0], ["missing config.py"])
        with mock.patch.object(deploy, "CHECK_DIR", self.check_dir):
            rc, _, err = run_main(["check", str(d)])
        self.assertEqual(rc, 1)
        self.assertTrue(err.startswith("check failed: demo"), err)

    def test_check_syntax_error(self):
        d = self.make()
        write(d / "commands" / "bad.py", "def x(:\n")
        problems = deploy.check(d, self.check_dir)[0]
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("does not compile: commands/bad.py:1:"), problems)

    def test_check_manifest_version(self):
        d = self.make()
        set_manifest(d, version="1.0")
        self.assertEqual(
            deploy.check(d, self.check_dir)[0],
            ['manifest version must be "" (the fingerprint identifies the build)'],
        )

    def test_check_manifest_id(self):
        expected = ["manifest id must be a lowercase hyphenated UUID"]
        d = self.make()
        set_manifest(d, id="ABC")
        self.assertEqual(deploy.check(d, self.check_dir)[0], expected)
        set_manifest(d, id="ABCDEF00-0000-4000-8000-000000000001")
        self.assertEqual(deploy.check(d, self.check_dir)[0], expected)

    def test_check_manifest_not_json(self):
        d = self.make()
        write(d / "demo.manifest", "{")
        problems = deploy.check(d, self.check_dir)[0]
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("manifest is not valid JSON:"), problems)

    def test_violations(self):
        got = deploy.violations(
            ["demo.py", "README.md", "tests/a.py", "lib/__pycache__/a.pyc", "lib/é.py"], "demo"
        )
        self.assertEqual(
            got,
            [
                "not in allowlist: README.md",
                "not in allowlist: tests/a.py",
                "excluded artifact shipped: lib/__pycache__/a.pyc",
                "non-ASCII path: lib/é.py",
            ],
        )

    def test_check_leaves_no_bytecode(self):
        d = self.make()
        deploy.check(d, self.check_dir)
        self.assertEqual([p for p in self.check_dir.rglob("__pycache__")], [])


if __name__ == "__main__":
    unittest.main()
