"""Tests for qnxtrace. The real-log tests run against the genuine
captured QEMU canary boot log (canary/canary-boot.log) — a Linux guest
standing in for the gated QNX target. Synthetic cases are labeled."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qnxtrace.logparse import parse_log
from qnxtrace.report import build_report

ROOT = os.path.join(os.path.dirname(__file__), "..")
CANARY_LOG = os.path.join(ROOT, "canary", "canary-boot.log")
MARKERS = ["CANARY-GUEST-HELLO", "CANARY-GUEST-DONE"]


class RealCanaryLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CANARY_LOG, errors="replace") as f:
            cls.text = f.read()
        cls.events = parse_log(cls.text, marker_names=MARKERS)

    def test_events_parsed(self):
        self.assertGreater(len(self.events), 100)

    def test_banner_classified(self):
        self.assertTrue(any(e.kind == "banner" for e in self.events))

    def test_markers_found(self):
        report = build_report(self.events, MARKERS)
        self.assertEqual(report.markers_missing, [])
        self.assertTrue(report.clean_exit)

    def test_no_failures_in_real_log(self):
        report = build_report(self.events, MARKERS)
        self.assertEqual(report.failures, [])
        self.assertTrue(report.ok)


class SyntheticCaseTests(unittest.TestCase):
    def test_missing_marker_fails(self):
        events = parse_log("boot ok\nCANARY-GUEST-HELLO\n", marker_names=MARKERS)
        report = build_report(events, MARKERS)
        self.assertFalse(report.ok)
        self.assertIn("CANARY-GUEST-DONE", report.markers_missing)

    def test_panic_detected(self):
        events = parse_log("[ 1.0] Kernel panic - not syncing: boom\n", marker_names=[])
        self.assertTrue(any(e.kind == "failure" for e in events))

    def test_benign_error_word_not_failure(self):
        events = parse_log("[ 1.0] pci 0000:00:02.0: error handling enabled\n", marker_names=[])
        self.assertFalse(any(e.kind == "failure" for e in events))


if __name__ == "__main__":
    unittest.main()
