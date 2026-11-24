"""qnxtrace CLI: check a captured target log for boot health.

Usage:
  python -m qnxtrace.cli check --log canary/canary-boot.log \
      --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE

  # Real QNX 8.0 target capture (console + optional slog2info dump):
  python -m qnxtrace.cli check --target qnx \
      --log canary/canary-qnx-boot.log \
      --expect CANARY-GUEST-HELLO --expect CANARY-GUEST-DONE

Exit code 0 = PASS, 1 = FAIL. --format json emits a machine-readable
report for CI pipelines. --strict additionally fails the check when a
userspace process crashed during boot (a core dump is otherwise a
named warning, not a failure).
"""
from __future__ import annotations

import argparse
import json
import sys

from .adapters import QnxSlogAdapter
from .logparse import parse_log
from .report import build_report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qnxtrace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="health-check a captured target log")
    chk.add_argument("--log", required=True, help="path to the captured console/serial log")
    chk.add_argument("--expect", action="append", default=[], metavar="MARKER",
                     help="marker string that must appear (repeatable)")
    chk.add_argument("--clean-exit", default=r"Power down|CANARY-.*-DONE",
                     help="regex for the clean-exit line (empty string disables)")
    chk.add_argument("--target", choices=["generic", "qnx"], default="generic",
                     help="log format: generic console, or QNX 8.0 console + slog2info")
    chk.add_argument("--strict", action="store_true",
                     help="fail the check if any userspace process crashed (core dump)")
    chk.add_argument("--format", choices=["text", "json"], default="text",
                     help="report format (json is for CI consumption)")
    args = ap.parse_args(argv)

    with open(args.log, "r", errors="replace") as f:
        text = f.read()
    if args.target == "qnx":
        events = QnxSlogAdapter().parse(text, marker_names=args.expect)
    else:
        events = parse_log(text, marker_names=args.expect)
    report = build_report(events, args.expect,
                          clean_exit_re=args.clean_exit or None,
                          strict=args.strict)
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
