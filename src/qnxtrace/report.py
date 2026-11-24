"""Health report: did the target boot, hit its markers, and exit clean?"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .logparse import Event


@dataclass
class HealthReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    markers_seen: list[str] = field(default_factory=list)
    markers_missing: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    crashes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    clean_exit: bool = False
    event_count: int = 0
    strict: bool = False

    def render_text(self) -> str:
        verdict = "PASS" if self.ok else "FAIL"
        lines = [f"qnxtrace health report: {verdict}"]
        lines.append(f"  events parsed: {self.event_count}")
        lines.append(f"  markers seen: {', '.join(self.markers_seen) or '(none)'}")
        if self.markers_missing:
            lines.append(f"  markers MISSING: {', '.join(self.markers_missing)}")
        lines.append(f"  clean exit: {'yes' if self.clean_exit else 'no'}")
        if self.failures:
            lines.append("  failure lines:")
            lines += [f"    - {f}" for f in self.failures]
        if self.crashes:
            label = "process crashes (fatal in --strict mode):" if self.strict \
                else "process crash warnings (not fatal; use --strict to fail):"
            lines.append(f"  {label}")
            lines += [f"    - {c}" for c in self.crashes]
        if self.warnings:
            lines.append("  warnings:")
            lines += [f"    - {w}" for w in self.warnings]
        if self.reasons:
            lines.append("  reasons:")
            lines += [f"    - {r}" for r in self.reasons]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "verdict": "PASS" if self.ok else "FAIL",
            "ok": self.ok,
            "strict": self.strict,
            "event_count": self.event_count,
            "markers_seen": self.markers_seen,
            "markers_missing": self.markers_missing,
            "clean_exit": self.clean_exit,
            "failures": self.failures,
            "crashes": self.crashes,
            "warnings": self.warnings,
            "reasons": self.reasons,
        }


def build_report(
    events: list[Event],
    expected_markers: list[str],
    clean_exit_re: str | None = r"Power down|CANARY-.*-DONE",
    strict: bool = False,
) -> HealthReport:
    seen: list[str] = []
    for ev in events:
        for mk in ev.markers:
            if mk not in seen:
                seen.append(mk)
    missing = [m for m in expected_markers if m not in seen]
    failures = [ev.text or ev.raw for ev in events if ev.kind == "failure"]
    crashes = [ev.text or ev.raw for ev in events if ev.kind == "crash"]
    warnings = [ev.text or ev.raw for ev in events if ev.kind == "warning"]
    clean = False
    if clean_exit_re:
        pat = re.compile(clean_exit_re)
        clean = any(pat.search(ev.raw) for ev in events)
    reasons: list[str] = []
    if missing:
        reasons.append(f"expected markers not seen: {', '.join(missing)}")
    if failures:
        reasons.append(f"{len(failures)} failure line(s) in log")
    if strict and crashes:
        reasons.append(f"{len(crashes)} process crash(es) in log (strict mode)")
    if clean_exit_re and not clean:
        reasons.append("no clean-exit line matched")
    ok = not reasons
    return HealthReport(
        ok=ok,
        reasons=reasons,
        markers_seen=seen,
        markers_missing=missing,
        failures=failures,
        crashes=crashes,
        warnings=warnings,
        clean_exit=clean,
        event_count=len(events),
        strict=strict,
    )
