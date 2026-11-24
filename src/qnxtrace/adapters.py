"""Target-specific log adapters.

QnxSlogAdapter parses a captured QNX 8.0 target console log — the
stream the QSTI/QEMU startup scripts and on-target programs write to
the serial console — plus, when present, the slog2info dump of the
target's structured slog2 buffers (delimited in our captures by
QNXT:SLOG2INFO-BEGIN / QNXT:SLOG2INFO-END).

The console half is written against real captured output
(canary/canary-qnx-boot.log, QNX 8.0.0 x86_64 under QEMU, captured
2026-11-21): the "---> Starting <service>" lines, the closing
"QNX <host> <release> ... <arch>" banner, and — the finding that
motivated the crash tier in the health report — a genuine
"Memory fault (core dumped)" from the stock image's sshd, which a
marker-only check would have waved through.

Event kinds produced: banner, service, marker, failure, crash,
warning, info. "crash" is a process-level fault (core dump): real,
worth naming, but not a kernel failure. The health report treats
crashes as warnings unless --strict is given.
"""
from __future__ import annotations

import re

from .logparse import Event, _FAILURE_PATTERNS

# "---> Starting sshd" — the real log also carries control-char and
# '#'-prefixed variants, so anchor on the word "Starting".
_SERVICE_RE = re.compile(r"Starting\s+([A-Za-z0-9_.\-]+)\s*$")
_CRASH_RE = re.compile(r"Memory fault|core dumped|Segmentation fault", re.IGNORECASE)
_BANNER_RE = re.compile(
    r"^QNX\s+(\S+)\s+(\d+\.\d+\.\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$"
)
_PROCESS_COUNT_RE = re.compile(r"Process count:\s*(\d+)")
_SLOG_SECTION_BEGIN = "QNXT:SLOG2INFO-BEGIN"
_SLOG_SECTION_END = "QNXT:SLOG2INFO-END"

# slog2info default output carries a syslog-style timestamp
# ("Nov 22 18:03:11.123456 ..."); with -S it also carries a severity
# name, with -s a severity number (0=SHUTDOWN .. 7=DEBUG2). The
# parser is deliberately tolerant about the middle columns, which
# vary with flags (-t thread id, -f epoch timestamps).
_SLOG_TS_RE = re.compile(
    r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\s+"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+(.*)$"
)
_SLOG_EPOCH_RE = re.compile(r"^\d{9,}\.\d{3}\s+(.*)$")
_SLOG_SEV_NAME_RE = re.compile(
    r"\bSLOG2_(SHUTDOWN|CRITICAL|ERROR|WARNING|NOTICE|INFO|DEBUG1|DEBUG2)\b"
)

_SEV_KIND = {
    "SHUTDOWN": "failure",
    "CRITICAL": "failure",
    "ERROR": "failure",
    "WARNING": "warning",
}


def _clean(line: str) -> str:
    """Strip control characters the serial capture picks up."""
    return "".join(ch for ch in line if ch == "\t" or ord(ch) >= 0x20).strip()


class QnxSlogAdapter:
    """Parse QNX target console output (+ optional slog2info dump)
    into qnxtrace events."""

    def parse(self, text: str, marker_names: list[str] | None = None) -> list[Event]:
        marker_names = marker_names or []
        events: list[Event] = []
        last_service: str | None = None
        in_slog = False
        for i, raw_line in enumerate(text.splitlines()):
            line = _clean(raw_line)
            if _SLOG_SECTION_BEGIN in line:
                in_slog = True
                events.append(Event(index=i, raw=raw_line, text=line, kind="info"))
                continue
            if _SLOG_SECTION_END in line:
                in_slog = False
                events.append(Event(index=i, raw=raw_line, text=line, kind="info"))
                continue
            if in_slog:
                events.append(self._slog_event(i, raw_line, line, marker_names))
                continue
            events.append(self._console_event(i, raw_line, line, marker_names,
                                              last_service))
            m = _SERVICE_RE.search(line)
            if m:
                last_service = m.group(1)
        return events

    def _console_event(self, i, raw, line, marker_names, last_service) -> Event:
        kind = "info"
        text = line
        m = _BANNER_RE.match(line)
        if m:
            kind = "banner"
            text = (f"QNX banner: host={m.group(1)} release={m.group(2)} "
                    f"build={m.group(3)} machine={m.group(4)} arch={m.group(5)}")
        elif _SERVICE_RE.search(line):
            kind = "service"
            text = f"service starting: {_SERVICE_RE.search(line).group(1)}"
        elif _CRASH_RE.search(line):
            kind = "crash"
            svc = f" (service: {last_service})" if last_service else ""
            text = f"process crash{svc}: {line}"
        elif any(p.search(line) for p in _FAILURE_PATTERNS):
            kind = "failure"
        elif _PROCESS_COUNT_RE.search(line):
            text = f"process count: {_PROCESS_COUNT_RE.search(line).group(1)}"
        hits = [mk for mk in marker_names if mk in line]
        if hits:
            kind = "marker"
        return Event(index=i, raw=raw, text=text, kind=kind, markers=hits)

    def _slog_event(self, i, raw, line, marker_names) -> Event:
        kind = "info"
        text = line
        m = _SLOG_TS_RE.match(line) or _SLOG_EPOCH_RE.match(line)
        if m:
            sev = _SLOG_SEV_NAME_RE.search(line)
            if sev:
                kind = _SEV_KIND.get(sev.group(1), "info")
                text = f"slog2 [{sev.group(1)}] {m.group(1)}"
            else:
                text = f"slog2 {m.group(1)}"
        hits = [mk for mk in marker_names if mk in line]
        if hits:
            kind = "marker"
        return Event(index=i, raw=raw, text=text, kind=kind, markers=hits)
