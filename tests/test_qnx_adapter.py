"""Tests for the QNX adapter and the crash-tier health report.

The real-log tests run against the genuine captured QNX 8.0 boot log
(canary/canary-qnx-boot.log — QNX 8.0.0 x86_64 under QEMU, captured
2026-11-21). The slog2 cases are synthetic but use the slog2info
output shapes documented in the QNX SDP 8.0 utilities reference
(syslog-style timestamp; severity names as shown by slog2info -S).
"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qnxtrace.adapters import QnxSlogAdapter
from qnxtrace.cli import main as cli_main
from qnxtrace.report import build_report

ROOT = os.path.join(os.path.dirname(__file__), "..")
QNX_LOG = os.path.join(ROOT, "canary", "canary-qnx-boot.log")
MARKERS = ["CANARY-GUEST-HELLO", "CANARY-GUEST-DONE"]


class RealQnxLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(QNX_LOG, errors="replace") as f:
            cls.text = f.read()
        cls.events = QnxSlogAdapter().parse(cls.text, marker_names=MARKERS)

    def test_events_parsed(self):
        self.assertEqual(len(self.events), 31)

    def test_banner_parsed_with_version(self):
        banners = [e for e in self.events if e.kind == "banner"]
        self.assertEqual(len(banners), 1)
        self.assertIn("release=8.0.0", banners[0].text)
        self.assertIn("arch=x86_64", banners[0].text)

    def test_services_tracked(self):
        services = [e.text for e in self.events if e.kind == "service"]
        self.assertTrue(any("slogger2" in s for s in services))
        self.assertTrue(any("sshd" in s for s in services))

    def test_markers_found(self):
        report = build_report(self.events, MARKERS)
        self.assertEqual(report.markers_missing, [])
        self.assertTrue(report.clean_exit)

    def test_sshd_crash_surfaced_as_crash_not_failure(self):
        crashes = [e for e in self.events if e.kind == "crash"]
        self.assertEqual(len(crashes), 1)
        self.assertIn("sshd", crashes[0].text)
        report = build_report(self.events, MARKERS)
        self.assertEqual(report.failures, [])
        self.assertEqual(len(report.crashes), 1)

    def test_crash_is_warning_by_default_and_fatal_when_strict(self):
        relaxed = build_report(self.events, MARKERS)
        self.assertTrue(relaxed.ok)
        strict = build_report(self.events, MARKERS, strict=True)
        self.assertFalse(strict.ok)
        self.assertTrue(any("crash" in r for r in strict.reasons))

    def test_json_shape(self):
        d = build_report(self.events, MARKERS).to_dict()
        self.assertEqual(d["verdict"], "PASS")
        self.assertEqual(d["event_count"], 31)
        self.assertEqual(len(d["crashes"]), 1)


class SyntheticSlogTests(unittest.TestCase):
    """Synthetic slog2info-section cases (documented output shapes)."""

    SLOG_CAPTURE = """\
payload ran
QNXT:SLOG2INFO-BEGIN
Nov 22 18:03:11.100000 slog2 [SLOG2_INFO] qnxtrace payload self-test started pid=42
Nov 22 18:03:11.101000 slog2 [SLOG2_WARNING] self-test severity probe (deliberate, not a fault)
Nov 22 18:03:11.102000 slog2 [SLOG2_ERROR] simulated disk controller reset
QNXT:SLOG2INFO-END
"""

    def setUp(self):
        self.events = QnxSlogAdapter().parse(self.SLOG_CAPTURE, marker_names=[])

    def test_severity_mapping(self):
        kinds = [e.kind for e in self.events if "slog2" in e.text]
        self.assertEqual(kinds, ["info", "warning", "failure"])

    def test_slog_error_fails_report(self):
        report = build_report(self.events, [])
        self.assertFalse(report.ok)
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(len(report.warnings), 1)


class CliTests(unittest.TestCase):
    def test_cli_qnx_json_passes(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["check", "--target", "qnx", "--format", "json",
                           "--log", QNX_LOG,
                           "--expect", "CANARY-GUEST-HELLO",
                           "--expect", "CANARY-GUEST-DONE"])
        self.assertEqual(rc, 0)
        d = json.loads(buf.getvalue())
        self.assertEqual(d["verdict"], "PASS")
        self.assertEqual(len(d["crashes"]), 1)

    def test_cli_qnx_strict_fails_on_real_log(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["check", "--target", "qnx", "--strict",
                           "--log", QNX_LOG,
                           "--expect", "CANARY-GUEST-HELLO",
                           "--expect", "CANARY-GUEST-DONE"])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
