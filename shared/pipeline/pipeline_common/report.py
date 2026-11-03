"""The validation report every area writes after its checks.

Two files in the area's data/ folder:

- validation_report.md: for people. Every group of checks with its failures and notes (each allowed exception
  with its reason).
- validation_summary.json: for the site, which reads it instead of parsing the Markdown, and refuses to build unless
  it says PASSED:

      {"result": "PASSED" | "FAILED", "checks": N, "failures": M, "allowed": K,
       "sections": [{"title": ..., "checks": n, "failures": m, "allowed": k,
                     "allowed_reasons": [{"reason": ..., "cases": c}, ...]}, ...]}

  "allowed" counts the exceptions recorded with Allowed (grouped by reason). Exceptions an area writes as plain notes
  are in the Markdown only.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPORT_FILE = "validation_report.md"
SUMMARY_FILE = "validation_summary.json"
FAILURE_MARK = "- FAIL: "


class Allowed:
    """Allowed exceptions grouped under their reason, so each reason is printed once with its cases."""

    def __init__(self) -> None:
        self.cases: dict[str, list[str]] = defaultdict(list)

    def add(self, reason: str, case: str) -> None:
        self.cases[reason].append(case)

    def notes(self, limit: int = 60) -> list[str]:
        out = []
        for reason, cases in self.cases.items():
            shown = "; ".join(cases[:limit]) + (f"; and {len(cases) - limit} more (see the CSV)" if len(cases) > limit else "")
            out.append(f"Allowed ({len(cases)}): {reason} Cases: {shown}")
        return out

    def counts(self) -> list[dict]:
        return [{"reason": reason, "cases": len(cases)} for reason, cases in self.cases.items()]


@dataclass
class Section:
    title: str
    checks: int
    failures: list[str]
    notes: list[str] = field(default_factory=list)
    allowed: list[dict] = field(default_factory=list)  # [{"reason", "cases"}], from Allowed


class Report:
    def __init__(self, intro: str, title: str = "Data validation report") -> None:
        self.title = title
        self.intro = intro
        self.sections: list[Section] = []

    def add(self, title: str, checked: int, failures: list[str], notes: list[str] | tuple = (),
            allowed: Allowed | None = None, limit: int = 60) -> None:
        """One group of checks. Allowed exceptions (if any) are listed first, showing up to `limit` cases each."""
        allowed_notes = allowed.notes(limit) if allowed else []
        self.sections.append(Section(title, checked, list(failures), [*allowed_notes, *notes],
                                     allowed.counts() if allowed else []))

    @property
    def checks(self) -> int:
        return sum(s.checks for s in self.sections)

    @property
    def failures(self) -> int:
        return sum(len(s.failures) for s in self.sections)

    @property
    def failed(self) -> bool:
        return self.failures > 0

    def markdown(self) -> str:
        out = [f"# {self.title}", "", self.intro, "",
               f"**Result: {'FAILED' if self.failed else 'PASSED'}** ({self.checks} checks, {self.failures} failures)", ""]
        for s in self.sections:
            out += [f"## {'❌' if s.failures else '✅'} {s.title}", f"{s.checks} checks, {len(s.failures)} failures.", ""]
            out += [f"{FAILURE_MARK}{f}" for f in s.failures]
            out += [f"- {n}" for n in s.notes]
            out.append("")
        return "\n".join(out)

    def summary(self) -> dict:
        sections = [{"title": s.title, "checks": s.checks, "failures": len(s.failures),
                     "allowed": sum(a["cases"] for a in s.allowed), "allowed_reasons": s.allowed}
                    for s in self.sections]
        return {"result": "FAILED" if self.failed else "PASSED", "checks": self.checks, "failures": self.failures,
                "allowed": sum(s["allowed"] for s in sections), "sections": sections}

    def write(self, data_dir: Path) -> int:
        """Write both files, print one line per group of checks, and return the exit code (1 if anything failed)."""
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / REPORT_FILE).write_text(self.markdown())
        (data_dir / SUMMARY_FILE).write_text(json.dumps(self.summary(), indent=1, ensure_ascii=False) + "\n")
        for s in self.sections:
            print(f"{'FAIL' if s.failures else 'ok  '} {s.title}: {s.checks} checks, {len(s.failures)} failures")
        return 1 if self.failed else 0
