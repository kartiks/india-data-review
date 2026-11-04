"""Consumer prices, base 2024, read from MoSPI's press releases: every release read in full, its figures agreeing
with each other, with the year before, with its PDF, with later releases and with the old series."""

from collections import Counter

from pipeline_common.report import Allowed, Report

from ..common import ROOT
from ..cpi2024 import pdf_numbers

BACKTICK = (
    "MoSPI's press release page prints this figure with a stray backtick (for example '109.`39'). It is read as "
    "missing and the rest of its row is kept; the next month's release repeats it as final, and that figure is used."
)


def check_cpi2024(ds: dict, report: Report) -> None:
    """Every check of the new series, or one failure if no release was read."""
    if not ds["cpi2024"]["releases"]:
        report.add("Prices, new series (base 2024): releases read", 0, ["no releases"], [])
        return
    for check in (check_releases_read, check_headline_agrees, check_inflation, check_combined, check_revisions,
                  check_linking_factor, check_pdf):
        check(ds, report)


def check_releases_read(ds: dict, report: Report) -> None:
    """12 divisions, 43 groups and 36 states, and an All-India series, in every release."""
    failures, allowed, checked = [], Allowed(), 0
    for m, r in sorted(ds["cpi2024"]["releases"].items()):
        checked += 1
        n = (len([d for d in r["divisions"] if d["code"] != "00"]), len(r["groups"]), len(r["states"]))
        if n != (12, 43, 36):
            failures.append(f"{m}: read {n[0]} divisions, {n[1]} groups, {n[2]} states (expected 12, 43, 36)")
        if not (r["series"] or r["series_combined"]):
            failures.append(f"{m}: no All-India series")
        for prob in r["problems"]:
            (allowed.add(BACKTICK, prob) if "`" in prob else failures.append(prob))
    report.add("Prices, new series (base 2024): every release read in full", checked, failures, allowed=allowed)


def check_headline_agrees(ds: dict, report: Report) -> None:
    """The headline sentence, the summary table and the annexures give the same inflation (rural, urban, combined)."""
    failures, checked = [], 0
    for m, r in sorted(ds["cpi2024"]["releases"].items()):
        h = r.get("headline", {})
        cur = r["summary"].get("current", {}).get("general_inflation")
        allrow = next((d["values"] for d in r["divisions"] if d["code"] == "00"), None)
        last = next((x["values"] for x in r["series"] if x["month"] == m), None)
        figures = {"headline sentence": [h.get("rural"), h.get("urban"), h.get("combined")], "summary table": cur,
                   "Annexure I, All India row": allrow[3:] if allrow else None, "Annexure IV": last[3:] if last else None}
        present = {k: v for k, v in figures.items() if v and None not in v}
        checked += 1
        ref = next(iter(present.values()), None)
        if len(present) < 2:
            failures.append(f"{m}: inflation found in only {list(present)}")
        elif any(v != ref for v in present.values()):
            failures.append(f"{m}: inflation (rural, urban, combined) differs: {present}")
    report.add("Prices, new series: headline, summary and annexures agree", checked, failures, [])


def check_inflation(ds: dict, report: Report) -> None:
    """Each release's All-India inflation is reproduced from its index a year earlier."""
    failures, checked = [], 0
    for m, r in sorted(ds["cpi2024"]["releases"].items()):
        idx = {x["month"]: x["values"] for x in r["series"]}
        for month, v in idx.items():
            before = idx.get(f"{int(month[:4]) - 1}{month[4:]}")
            if before is None:
                continue
            for i, sec in enumerate(("rural", "urban", "combined")):
                if v[i + 3] is None:
                    continue
                checked += 1
                calc = (v[i] / before[i] - 1) * 100
                if abs(calc - v[i + 3]) > 0.03:
                    failures.append(f"release {m}, {month} {sec}: index {v[i]} vs {before[i]} gives {calc:.2f}%, published {v[i + 3]}%")
    report.add("Prices, new series: inflation reproduced from the index a year earlier", checked, failures,
               ["Indices are printed to two decimals but compiled unrounded, so a difference of up to 0.03 points is allowed."])


def check_combined(ds: dict, report: Report) -> None:
    """In every table, the combined index lies between the rural and urban index."""
    failures, checked = [], 0
    for m, r in sorted(ds["cpi2024"]["releases"].items()):
        for table, rows in (("division", r["divisions"]), ("group", r["groups"]), ("state", r["states"]), ("series", r["series"])):
            for x in rows:
                v = x["values"]
                if None in v[:3]:
                    continue  # Chandigarh has no rural market
                checked += 1
                if not (min(v[0], v[1]) - 0.011 <= v[2] <= max(v[0], v[1]) + 0.011):
                    failures.append(f"{m} {table} {x.get('name', x.get('month'))}: combined {v[2]} outside rural {v[0]} and urban {v[1]}")
    report.add("Prices, new series: combined index lies between rural and urban", checked, failures, [])


def final_series(c: dict) -> dict[str, list]:
    """month -> the All-India values in the latest release (final, except its own month)."""
    return {x["month"]: x["values"] for x in c["series"]}


def check_revisions(ds: dict, report: Report) -> None:
    """Later releases revise only the previous month (provisional to final)."""
    c = ds["cpi2024"]
    failures, notes, checked = [], [], 0
    final = final_series(c)
    for m, r in sorted(c["releases"].items()):
        for x in r["series"]:
            if x["month"] not in final or m == c["latest"]:
                continue
            checked += 1
            if x["values"] != final[x["month"]]:
                diff = f"{x['month']} in the {m} release {x['values']} vs latest {final[x['month']]}"
                (notes.append(f"Provisional figure revised: {diff}") if x["month"] == m else failures.append(f"Final figure changed: {diff}"))
    report.add("Prices, new series: only provisional figures are revised", checked, failures, notes)


def check_linking_factor(ds: dict, report: Report) -> None:
    """Linking factor = average 2025 index on the new base ÷ on the old base (MoSPI's data service)."""
    c = ds["cpi2024"]
    final = final_series(c)
    failures, checked = [], 0
    old = {(r["sector"], r["month"]): r["index"] for r in ds["cpi"] if r["state"] == "All India" and r["subgroup"] == "General-Overall"}
    for i, sec in enumerate(("Rural", "Urban", "Combined")):
        f = c["linking"].get(sec)
        news = [final[m][i] for m in final if m.startswith("2025")]
        olds = [old.get((sec, m)) for m in final if m.startswith("2025")]
        if f is None or len(news) != 12 or None in olds:
            failures.append(f"linking factor {sec}: cannot check (factor {f}, {len(news)} months)")
            continue
        checked += 1
        calc = (sum(news) / 12) / (sum(olds) / 12)
        if abs(calc - f) > 0.00006:
            failures.append(f"linking factor {sec}: published {f}, 2025 averages give {calc:.4f}")
    report.add("Prices, new series: linking factor = 2025 average, new base ÷ old base", checked, failures,
               [f"Published factors {c['linking']}; old-base indices from MoSPI's data service, new-base from the press releases."])


def check_pdf(ds: dict, report: Report) -> None:
    """Every figure in the release page's tables is in its PDF."""
    failures, notes, checked = [], [], 0
    for m, r in sorted(ds["cpi2024"]["releases"].items()):
        if not r["pdf"]:
            notes.append(f"{m}: no PDF attached to the release; page only")
            continue
        have = Counter(pdf_numbers(ROOT / r["pdf"]))
        want = Counter(f"{v:.2f}" for rows in (r["divisions"], r["groups"], r["states"]) for x in rows for v in x["values"] if v is not None)
        want += Counter(f"{v:.2f}" for x in r["series"] for v in x["values"][:6] if v is not None)
        checked += 1
        missing = want - have
        if missing:
            failures.append(f"{m}: {sum(missing.values())} figures on the release page not found in its PDF: {sorted(missing)[:10]}")
    report.add("Prices, new series: release page tables match the PDF", checked, failures, notes)
