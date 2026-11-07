"""Whether the next Union Budget is due: the probe of indiabudget.gov.in, with the network replaced by stubs and a
fixed date."""

import urllib.error
from datetime import date
from pathlib import Path

import pytest

from budget_pipeline import due
from pipeline_common import log as pipeline_log
from pipeline_common.due import DUE

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "sources" / "raw" / "2026-27" / "summary.pdf"
MANIFEST = {"2026-27/summary/pdf": {"sha256": due.sha256(COMMITTED.read_bytes()).hexdigest()}}
ROOT_URL = "https://www.indiabudget.gov.in/doc/Budget_at_Glance/bag1.pdf"
MOVED_URL = "https://www.indiabudget.gov.in/budget2026-27/doc/Budget_at_Glance/bag1.pdf"
NOV = date(2026, 11, 8)


def site(pages: dict[str, bytes | Exception]):
    """A fetch that answers from pages (a 404 for any other address) and records what was asked."""
    asked = []

    def fetch(url):
        asked.append(url)
        if url not in pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        answer = pages[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    fetch.asked = asked
    return fetch


def run(pages, today=NOV, text=None, monkeypatch=None):
    if text is not None:
        monkeypatch.setattr(due, "pdf_text", lambda content: text)
    return due.check(today, site(pages), MANIFEST, latest=2026)


def test_the_year_is_read_from_the_headline_table():
    assert due.budget_year(due.pdf_text(COMMITTED.read_bytes())) == 2026
    assert due.budget_year("Actuals 2024-2025 BE 2025-2026 RE 2025-2026 BE 2026-2027") == 2026
    assert due.budget_year("BE 2027-28 and 2026-27 and 12345-67 and 2027-29") == 2027
    assert due.budget_year("no years") is None


def test_nothing_due_while_the_site_has_the_committed_budget():
    f = run({ROOT_URL: COMMITTED.read_bytes()})
    assert (f.due, f.warnings) == ([], [])
    assert f.ok == ["Union Budget 2027-28: not out yet (indiabudget.gov.in's Budget at a Glance is the committed "
                    "2026-27 copy)"]
    assert f.finish() == 0


def test_a_new_budget_is_due(monkeypatch, capsys):
    pipeline_log.setup()  # as the command does
    f = run({ROOT_URL: b"%PDF new"}, text="Actuals 2025-2026 BE 2026-2027 RE 2026-2027 BE 2027-2028", monkeypatch=monkeypatch)
    assert len(f.due) == 1 and f.due[0].startswith("Union Budget 2027-28: Budget at a Glance for 2027-28 is on "
                                                   "indiabudget.gov.in")
    assert "budget/README.md" in f.due[0] and "budget_glance.py" in f.due[0]
    assert f.finish() == DUE == 11
    assert capsys.readouterr().out.startswith("DUE: Union Budget 2027-28")


def test_an_interim_budget_is_not_due(monkeypatch):
    f = run({ROOT_URL: b"%PDF interim"}, text="Interim Budget 2029-2030 ... BE 2029-2030", monkeypatch=monkeypatch)
    assert f.due == [] and "Interim Budget 2029-30 is out" in f.ok[0]


def test_a_corrected_copy_of_the_same_budget_is_a_warning(monkeypatch):
    f = run({ROOT_URL: b"%PDF corrected"}, text="BE 2025-2026 BE 2026-2027", monkeypatch=monkeypatch)
    assert f.due == [] and "differs from the committed copy" in f.warnings[0]
    assert f.finish() == 0


def test_an_unreadable_year_is_due_only_if_the_budget_moved(monkeypatch):
    moved = run({ROOT_URL: b"%PDF ?", MOVED_URL: b"%PDF old"}, text="", monkeypatch=monkeypatch)
    assert len(moved.due) == 1 and f"has moved 2026-27 to {MOVED_URL}" in moved.due[0]
    still = run({ROOT_URL: b"%PDF ?"}, text="", monkeypatch=monkeypatch)
    assert still.due == [] and "its year could not be read" in still.warnings[0]
    monkeypatch.undo()  # the real reader, on a file that is not a PDF inside
    broken = due.check(NOV, site({ROOT_URL: b"%PDF-1.7 broken", MOVED_URL: b"%PDF old"}), MANIFEST, latest=2026)
    assert "could not read the PDF" in broken.warnings[0] and len(broken.due) == 1


@pytest.mark.parametrize("answer", [urllib.error.URLError("timed out"), TimeoutError("slow"), b"<html>maintenance</html>",
                                    urllib.error.HTTPError(ROOT_URL, 503, "Unavailable", {}, None)])
def test_network_trouble_is_a_warning_not_a_failure(answer, capsys):
    pipeline_log.setup()  # as the command does
    f = run({ROOT_URL: answer})
    assert f.due == [] and len(f.warnings) == 1 and "could not check indiabudget.gov.in" in f.warnings[0]
    assert f.finish() == 0
    assert "WARNING: Union Budget 2027-28: could not check" in capsys.readouterr().err
    if isinstance(answer, urllib.error.HTTPError):
        assert answer.fp.closed  # closed by the probe


def test_due_from_august_whatever_the_probe_says():
    f = run({ROOT_URL: urllib.error.URLError("down")}, today=date(2027, 8, 1))
    assert len(f.due) == 1 and f.due[0].startswith("Union Budget 2027-28: due since 1 February 2027")
    assert run({ROOT_URL: COMMITTED.read_bytes()}, today=date(2027, 7, 31)).due == []


def test_the_command(monkeypatch, capsys):
    monkeypatch.setattr(due, "check", lambda today: due.Findings(due=["x"]))
    assert due.main([]) == 11
    assert capsys.readouterr().out == "DUE: x\n"
    with pytest.raises(SystemExit) as e:
        due.main(["--bogus"])
    assert e.value.code == 2
