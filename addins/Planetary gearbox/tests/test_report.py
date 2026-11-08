import unittest

import _support  # noqa: F401
from planetarygearboxgen import report
from planetarygearboxgen.report import Expect


class ReportTest(unittest.TestCase):
    def test_fmt_num(self):
        cases = [
            (6.0, "6"),
            (3.4, "3.4"),
            (float("nan"), "NaN"),
            (float("inf"), "+Inf"),
            (float("-inf"), "-Inf"),
            (0.0, "0"),
            (1e6, "1e+06"),
            (1234567.5, "1.2345675e+06"),
            (1e-05, "1e-05"),
            (123456.0, "123456"),
            (-2.5, "-2.5"),
            (0.0001, "0.0001"),
        ]
        for v, want in cases:
            with self.subTest(v=v):
                self.assertEqual(report.fmt_num(v), want)

    def test_format_record(self):
        got = report.format_record("body", [("name", "Sun Gear 1"), ("solid", True), ("v", 1.5)])
        self.assertEqual(got, 'body name="Sun Gear 1" solid=true v=1.5')

    def test_fmt_field(self):
        self.assertEqual(report.fmt_field((1.0, 2.5, 3.0)), "(1,2.5,3)")
        self.assertEqual(report.fmt_field(7), "7")
        self.assertEqual(report.fmt_field("ok"), "ok")

    def test_within(self):
        self.assertTrue(report.within(1.0, Expect(1.1, 0.2)))
        self.assertFalse(report.within(1.0, Expect(1.5, 0.2)))

    def test_sink_log(self):
        lines: list[str] = []
        log = report.SinkLog(lines.append)
        self.assertTrue(log.enabled)
        log.write("start", [("n", 1)])
        log.close()
        self.assertEqual(lines, ["start n=1"])

    def test_null_log(self):
        log = report.NullLog()
        self.assertFalse(log.enabled)
        log.write("x", [])
        log.close()


if __name__ == "__main__":
    unittest.main()
