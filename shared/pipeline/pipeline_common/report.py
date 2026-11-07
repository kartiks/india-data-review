"""The validation report every area writes after its checks.

Two files in the area's data/ folder:

- validation_report.md: for people. Every group of checks with its failures and notes (each allowed exception
  with its reason).
- validation_summary.json: for the site, which reads it instead of parsing the Markdown, and refuses to build unless
  it says PASSED:

      {"result": "PASSED" | "FAILED", "checks": N, "failures": M, "allowed": K,
       "sections": [{"title": ..., "checks": n, "failures": m, "allowed": k,
                     "allowed_reasons": [{"reason": ..., "cases": c}, ...]}, ...],
       "files": {"<name>": "<sha256>", ...}}

  "allowed" counts the exceptions recorded with Allowed (grouped by reason). Exceptions an area writes as plain notes
  are in the Markdown only, so every area records them with Allowed.

  "files" holds a SHA-256 of every data file the checks just validated: each .json, .csv and .md file in data/ apart
  from the report and the summary. The site's build (site/scripts/copy-data.mjs, via site/src/lib/validation.ts)
  works the hashes out again and refuses to build if any file differs, is missing or is not listed, so data changed
  after its checks ran cannot go live with an old PASSED. Each hash is of the file with every "generated_at" field
  (the build time, written by every build) removed, as scripts/ci.sh compares files: rebuilding the same data, which
  the tests also do, changes no hash.
"""

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

REPORT_FILE = "validation_report.md"
SUMMARY_FILE = "validation_summary.json"
FAILURE_MARK = "- FAIL: "
DATA_SUFFIXES = (".json", ".csv", ".md")
# The key of the build time in every area's data files: its value changes on every build, so the data hashes, the
# text check (data_text) and the new-text diff (labels) leave it out.
BUILD_TIME_KEY = "generated_at"
# The build time, '"generated_at": "..."' (or without the space, in compact JSON). Keep in step with
# site/src/lib/validation.ts and the STRIP in scripts/ci.sh.
GENERATED_AT = re.compile(rb'"generated_at": ?"[^"]*"')


def data_hash(path: Path) -> str:
    """SHA-256 of a data file with its build time removed."""
    return hashlib.sha256(GENERATED_AT.sub(b"", path.read_bytes())).hexdigest()


def data_hashes(data_dir: Path) -> dict[str, str]:
    """The hash of every data file in data_dir (not the report or the summary), by file name."""
    return {p.name: data_hash(p) for p in sorted(data_dir.iterdir())
            if p.is_file() and p.suffix in DATA_SUFFIXES and p.name not in (REPORT_FILE, SUMMARY_FILE)}


Rule = tuple[Hashable, Callable[[str], bool], str]


class Exceptions:
    """The known exceptions to an area's checks, each with its written reason.

    - known: {(check, message prefix): reason}. One known case, or every case whose message starts with the prefix
      (an empty prefix matches every message of that check). Where several prefixes match, the longest wins.
    - contains: {(check, fragment): reason}. Every case whose message contains the fragment anywhere; tried after
      `known`, the longest matching fragment winning.
    - rules: [(check, test, reason)]. A family of cases recognised by test(message), tried last, in order.

    `check` names a check ('growth') or is any other hashable key, such as a (budget, table) tuple. reason() also
    remembers which `known` and `contains` entries matched, so an area can list those no longer needed (unused()).
    """

    def __init__(self, known: Mapping[tuple[Hashable, str], str] | None = None, rules: Iterable[Rule] = (),
                 contains: Mapping[tuple[Hashable, str], str] | None = None) -> None:
        self.known = dict(known or {})
        self.contains = dict(contains or {})
        self.rules = list(rules)
        self.used: set[tuple[str, Hashable, str]] = set()

    def reason(self, check: Hashable, message: str) -> str | None:
        """The reason this message of this check is allowed, or None if it is a failure."""
        for mode, entries, matches in (("known", self.known, str.startswith),
                                       ("contains", self.contains, str.__contains__)):
            hits = [text for (c, text) in entries if c == check and matches(message, text)]
            if hits:
                best = max(hits, key=len)
                self.used.add((mode, check, best))
                return entries[(check, best)]
        for c, test, reason in self.rules:
            if c == check and test(message):
                return reason
        return None

    def unused(self) -> list[tuple[Hashable, str]]:
        """The known and contains entries no message has matched since the last reset()."""
        return ([k for k in self.known if ("known", *k) not in self.used]
                + [k for k in self.contains if ("contains", *k) not in self.used])

    def reset(self) -> None:
        self.used.clear()


class Allowed:
    """Allowed exceptions grouped under their reason, so each reason is printed once with its cases.

    Add a case under a reason the check worked out itself with add(), or let file() and sort_out() look the reason
    up in the area's Exceptions. Pass it to Report.add, which lists the cases (one bullet each) and counts them in
    the summary. `more_hint` follows "and N more" when a reason has more cases than the report shows."""

    def __init__(self, exceptions: Exceptions | None = None, *, more_hint: str = " (see the CSV)") -> None:
        self.exceptions = exceptions
        self.more_hint = more_hint
        self.cases: dict[str, list[str]] = defaultdict(list)

    def add(self, reason: str, case: str) -> None:
        self.cases[reason].append(case)

    def file(self, check: Hashable, message: str, case: str | None = None) -> bool:
        """If the exceptions know this message, record it under its reason and return True. `case` is what to
        record and print, when the message matched is a key rather than readable text (default: the message)."""
        reason = self.exceptions.reason(check, message) if self.exceptions else None
        if reason:
            self.add(reason, message if case is None else case)
        return bool(reason)

    def sort_out(self, check: Hashable, messages: Iterable[str], cases: Iterable[str] | None = None) -> list[str]:
        """File each message the exceptions know under its reason; return the others, which are failures. With
        `cases` (one per message), the messages are keys to match and the cases are what is recorded or returned."""
        messages = list(messages)
        cases = messages if cases is None else list(cases)
        if len(cases) != len(messages):
            raise ValueError("sort_out: one case per message")
        return [c for m, c in zip(messages, cases) if not self.file(check, m, c)]

    def notes(self, limit: int = 60) -> list[str]:
        """One note per reason: the reason, then up to `limit` of its cases as nested bullets."""
        out = []
        for reason, cases in self.cases.items():
            lines = [f"Allowed ({len(cases)}): {reason} Cases:", *(f"  - {c}" for c in cases[:limit])]
            if len(cases) > limit:
                lines.append(f"  - and {len(cases) - limit} more{self.more_hint}")
            out.append("\n".join(lines))
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

    def summary(self, files: dict[str, str] | None = None) -> dict:
        """The summary; `files` (data_hashes) is added when given."""
        sections = [{"title": s.title, "checks": s.checks, "failures": len(s.failures),
                     "allowed": sum(a["cases"] for a in s.allowed), "allowed_reasons": s.allowed}
                    for s in self.sections]
        out = {"result": "FAILED" if self.failed else "PASSED", "checks": self.checks, "failures": self.failures,
               "allowed": sum(s["allowed"] for s in sections), "sections": sections}
        if files is not None:
            out["files"] = files
        return out

    def write(self, data_dir: Path) -> int:
        """Write both files, print one line per group of checks, and return the exit code (1 if anything failed).

        Call it after every data file is written: the summary records their hashes as they are now."""
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / REPORT_FILE).write_text(self.markdown())
        summary = self.summary(data_hashes(data_dir))
        (data_dir / SUMMARY_FILE).write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
        for s in self.sections:
            print(f"{'FAIL' if s.failures else 'ok  '} {s.title}: {s.checks} checks, {len(s.failures)} failures")
        return 1 if self.failed else 0
