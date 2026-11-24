"""Parse QEMU target console/serial logs into structured events.

The parser is target-agnostic: it understands bracketed kernel-style
timestamps and classifies lines into banner / marker / failure / info.
Target-specific formats (e.g. QNX slog output) plug in via adapters.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TS_RE = re.compile(r"^\[\s*(\d+\.\d+)\]\s?(.*)$")

# Strong failure signals only — benign logs are full of the word "error".
_FAILURE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"kernel panic",
        r"\bassertion\b.*\bfailed\b",
        r"\bassert\b\s*\(",
        r"\bfatal\b",
        r"\bBUG:\s",
        r"\bOops\b",
        r"watchdog.*timeout",
    )
]

# Process-level crashes: a userspace program died (core dump). Real and
# worth surfacing, but not a kernel failure — the health report lists
# them as crash warnings and only fails on them in --strict mode.
_CRASH_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"segfault",
        r"memory fault",
        r"core dumped",
    )
]


@dataclass
class Event:
    index: int
    raw: str
    ts: float | None = None
    text: str = ""
    kind: str = "info"  # banner | marker | failure | crash | warning | service | info
    markers: list[str] = field(default_factory=list)


def classify(text: str, marker_names: list[str]) -> tuple[str, list[str]]:
    low = text.lower()
    if "linux version" in low or low.startswith("qnx") or "neutrino" in low:
        kind = "banner"
    elif any(p.search(text) for p in _FAILURE_PATTERNS):
        kind = "failure"
    elif any(p.search(text) for p in _CRASH_PATTERNS):
        kind = "crash"
    else:
        kind = "info"
    hits = [m for m in marker_names if m in text]
    if hits:
        kind = "marker"
    return kind, hits


def parse_log(text: str, marker_names: list[str] | None = None) -> list[Event]:
    marker_names = marker_names or []
    events: list[Event] = []
    for i, line in enumerate(text.splitlines()):
        m = _TS_RE.match(line)
        if m:
            ts, body = float(m.group(1)), m.group(2)
        else:
            ts, body = None, line
        kind, hits = classify(body, marker_names)
        events.append(Event(index=i, raw=line, ts=ts, text=body, kind=kind, markers=hits))
    return events
