"""Write the detailed datasets (taxes, ministries, schemes) to web/data/.

Each table module returns long-format observations: one row per item, year,
estimate type and source budget. Most figures appear in two budgets, so this
module picks one value per (item, year, estimate type) using the same rules
as the headline data:

- BE for year Y from Budget Y (what was announced);
- RE for Y from Budget Y+1;
- Actual for Y from Budget Y+2 (latest published).
The BE as reprinted in Budget Y+1 is kept as `be_restated` when it differs.

For each table we write <name>.csv (every observation, with its source) and
<name>.json (the chosen values, ready for the website).
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Fields describing where a value came from; kept with each chosen value.
FIRST_YEAR = "2000-01"

SOURCE_FIELDS = ("source_budget", "document", "label_as_printed", "source_url")


def _next(fiscal_year: str, n: int) -> str:
    start = int(fiscal_year[:4]) + n
    return f"{start}-{str(start + 1)[-2:]}"


def consolidate(rows: list[dict], id_fields: tuple[str, ...], value_fields: tuple[str, ...]) -> dict:
    """{fiscal_year: {item_key: {"be"|"re"|"actual"|"be_restated": {values..., sources...}}}}."""
    index: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(r[f] for f in id_fields)
        k = (r["fiscal_year"], key, r["kind"], r["source_budget"])
        if k in index and any(index[k].get(f) != r.get(f) for f in value_fields):
            raise ValueError(f"two different values for the same figure in one document: {k}")
        index[k] = r

    def pick(r: dict) -> dict:
        out = {f: r.get(f) for f in value_fields}
        out.update({f: r[f] for f in SOURCE_FIELDS if f in r})
        if r.get("note"):
            out["note"] = r["note"]
        return out

    years: dict[str, dict] = defaultdict(dict)
    keys = {(r["fiscal_year"], tuple(r[f] for f in id_fields)) for r in rows}
    for year, key in sorted(keys):
        item: dict = {}
        be = index.get((year, key, "BE", year))
        restated = index.get((year, key, "BE", _next(year, 1)))
        re_ = index.get((year, key, "RE", _next(year, 1)))
        actual = index.get((year, key, "Actual", _next(year, 2)))
        for name, r in (("be", be), ("re", re_), ("actual", actual)):
            if r is not None and any(r.get(f) is not None for f in value_fields):
                item[name] = pick(r)
        # A BE always comes from its own budget. Mixing in a later budget's reprint would combine two
        # documents' layouts (e.g. across the 2017-18 reorganisation of demands) and double count.
        if be is None and restated is not None:
            item["be_restated"] = pick(restated)
        elif be and restated and any(
            be.get(f) is not None and restated.get(f) is not None and abs(be[f] - restated[f]) > 0.01
            for f in value_fields
        ):
            item["be_restated"] = pick(restated)
        if item:
            years[year]["/".join(key)] = item
    return dict(years)


def write_table(name: str, rows: list[dict], id_fields: tuple[str, ...], value_fields: tuple[str, ...],
                meta: dict) -> dict:
    DATA.mkdir(exist_ok=True)
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("fiscal_year", "kind", *id_fields), k))
    with (DATA / f"{name}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in ("fiscal_year", *id_fields, "source_budget", "kind"))))
    dataset = {
        **meta,
        "units": "Rs crore",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules": "BE from that year's budget; RE from the next; Actual from the one after. "
                 "be_restated = the BE as reprinted a year later, when different.",
        # The site covers 2000-01 onwards; earlier years appear only as old columns of early budgets.
        "years": {y: v for y, v in consolidate(rows, id_fields, value_fields).items() if y >= FIRST_YEAR},
    }
    (DATA / f"{name}.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {name}: {len(rows)} observations")
    return dataset


def build_taxes() -> tuple[dict, list[tuple]]:
    from . import taxes

    all_parsed = taxes.load_all()
    rows = taxes.observations(all_parsed)
    for r in rows:
        r["value"] = r.pop("value_crore")
    labels = {}
    for r in rows:
        labels.setdefault(r["item_id"], r["label_as_printed"])
    write_table(
        "taxes", rows, ("item_id",), ("value",),
        {
            "description": "Union Government of India: tax and non-tax revenue by type (gross taxes, states' share, "
                           "net tax), from the Budget at a Glance 'Receipts' table and, for actuals 2000-01 to "
                           "2007-08, Receipt Budget Annex 7.",
            "items": labels,
        },
    )
    return all_parsed, taxes.checks(all_parsed, taxes.load_summary_observations())


MINISTRY_VALUES = (
    "total_crore", "plan_crore", "non_plan_crore", "revenue_crore", "capital_crore",
    "central_sector_schemes_crore", "centrally_sponsored_schemes_crore", "establishment_crore",
    "other_central_sector_crore", "finance_commission_grants_crore", "other_transfers_crore",
)


def build_ministries() -> tuple[dict, list[tuple]]:
    from . import ministries, taxes

    all_parsed = ministries.load_all()
    rows = ministries.observations(all_parsed)
    items = {}
    for r in rows:
        items.setdefault(r["item_id"], {
            "department_name": r["department_name"], "ministry_id": r["ministry_id"],
            "ministry_name": r["ministry_name"], "level": r["level"], "section": r["section"],
        })
    for r in rows:
        r["document"] = "ministries"
    write_table(
        "ministries", rows, ("item_id",), MINISTRY_VALUES,
        {
            "description": "Union Government of India: total spending by ministry/department. Expenditure Budget "
                           "Vol. 1 Statement 2 (Plan/Non-plan) up to 2016-17; Expenditure Profile Statement 3/3A "
                           "(Revenue/Capital, with scheme categories) from 2017-18. Department ids are kept "
                           "across renames via data_maps/ministry_names.csv.",
            "comparability": "Up to 2016-17 a department's line excludes State Plan assistance routed through it "
                             "(listed separately as state_plans:<id>); from 2017-18 it is included. Several "
                             "demands were split or merged in 2017-18 (see the name map notes).",
            "items": items,
        },
    )
    return all_parsed, ministries.checks(all_parsed, taxes.load_summary_observations())


def _image_note(budget: str, scheme_type: str, item: dict) -> str | None:
    """Note for a figure that had to be read from the page image (missing from the PDF text layer)."""
    import re

    from . import schemes

    for r in schemes.IMAGE_READINGS:
        if r["budget"] != budget or r["scheme_type"] != scheme_type:
            continue
        if r.get("insert_grand_total") and item["level"] == "grand_total":
            return r["reason"]
        if r.get("label_re") and re.search(r["label_re"], item["label_as_printed"]):
            return r["reason"]
    return None


def scheme_observations(all_parsed: dict) -> list[dict]:
    from . import schemes

    names = schemes.load_name_map()
    rows = []
    for budget, types in sorted(all_parsed["budgets"].items()):
        for scheme_type, entry in types.items():
            parsed = entry["parsed"]
            if not parsed:
                continue
            src = entry["source"][entry["primary"]]
            for item in parsed["items"]:
                iid = item.get("item_id") or schemes.item_id(item, names, budget)
                note = _image_note(budget, scheme_type, item)
                for (fiscal_year, kind), v in item["values"].items():
                    if all(v.get(p) is None for p in ("revenue", "capital", "total")):
                        continue
                    rows.append({
                        "fiscal_year": fiscal_year, "kind": kind, "scheme_type": scheme_type, "item_id": iid,
                        "level": item["level"], "parent": item.get("parent"), "demand_no": item.get("demand_no"),
                        "department": item.get("department"), "category": item.get("category"),
                        "label_as_printed": item["label_as_printed"],
                        "revenue_crore": v.get("revenue"), "capital_crore": v.get("capital"),
                        "total_crore": v.get("total"),
                        "source_budget": budget, "document": scheme_type, "source_url": src["url"],
                        "source_sha256": src["sha256"], "note": note,
                    })
    return rows


def scheme_ministry_crosscheck(scheme_rows: list[dict], ministry_rows: list[dict]) -> tuple:
    """Grand totals of Statements 4A/4B vs the scheme sub-lines of Statement 3, same budget and column.

    Two different statements of the same budget, so this independently checks the
    scheme totals (including the 2025-26 4A Grand Total that had to be read from
    the page image). Known gross-vs-net presentation gaps are listed as notes.
    """
    field = {"css": "centrally_sponsored_schemes_crore", "central_sector": "central_sector_schemes_crore"}
    sums: dict[tuple, float] = defaultdict(float)
    present: set[tuple] = set()
    for r in ministry_rows:
        if r["level"] not in ("department", "union_territory") or int(r["source_budget"][:4]) < 2017:
            continue
        for t, f in field.items():
            if r.get(f) is not None:
                sums[(t, r["source_budget"], r["fiscal_year"], r["kind"])] += r[f]
                present.add((t, r["source_budget"]))
    failures, notes, checked = [], [], 0
    known = {
        ("central_sector", "2017-18"): "Budget 2017-18 4B lists some Demands (Railways etc.) at gross outlay "
                                       "while Statement 3 shows budgetary support.",
        ("central_sector", "2024-25"): "Budget 2024-25 4B nets transfers to funds in a final -8,000 row.",
    }
    for r in scheme_rows:
        if r["level"] != "grand_total" or (r["scheme_type"], r["source_budget"]) not in present:
            continue
        key = (r["scheme_type"], r["source_budget"], r["fiscal_year"], r["kind"])
        checked += 1
        diff = (r["total_crore"] or 0) - sums[key]
        if abs(diff) <= 1:
            continue
        msg = (f"Budget {r['source_budget']} {r['scheme_type']} {r['kind']} {r['fiscal_year']}: Statement 4 grand "
               f"total {r['total_crore']:,.2f} vs sum of Statement 3 sub-lines {sums[key]:,.2f} ({diff:+,.2f})")
        reason = known.get((r["scheme_type"], r["source_budget"]))
        (notes if reason else failures).append(msg + (f". {reason}" if reason else ""))
    return ("Schemes: grand totals match the scheme lines of the ministries statement", checked, failures, notes)


def build_schemes(ministry_rows: list[dict]) -> tuple[dict, list[tuple]]:
    from . import schemes, taxes

    all_parsed = schemes.load_all()
    rows = scheme_observations(all_parsed)
    items = {}
    for r in rows:
        items.setdefault(f"{r['scheme_type']}/{r['item_id']}", {
            "scheme_type": r["scheme_type"], "level": r["level"], "name": r["label_as_printed"],
            "department": r["department"], "parent": r["parent"],
        })
    write_table(
        "schemes", rows, ("scheme_type", "item_id"), ("revenue_crore", "capital_crore", "total_crore"),
        {
            "description": "Union Government of India: spending on each Centrally Sponsored Scheme (Expenditure "
                           "Profile Statement 4A) and Central Sector Scheme (Statement 4B), from Budget 2017-18. "
                           "Earlier budgets only show schemes as Plan outlays, which are not comparable.",
            "items": items,
        },
    )
    sections = schemes.checks(all_parsed, taxes.load_summary_observations())
    sections.append(scheme_ministry_crosscheck(rows, ministry_rows))
    return all_parsed, sections


def build_all() -> list[tuple]:
    """Build the three detailed datasets; return their check sections."""
    from . import ministries

    sections: list[tuple] = []
    _, s = build_taxes()
    sections += s
    m_parsed, s = build_ministries()
    sections += s
    _, s = build_schemes(ministries.observations(m_parsed))
    sections += s
    sections.append(check_prs())
    sections += check_published()
    return sections


PRS_FILE = ROOT / "sources" / "reference" / "prs" / "prs_union_budget_2026_27.csv"


def check_prs() -> tuple:
    """Compare with figures published by PRS Legislative Research (independent analysis, whole crore)."""
    fiscal = json.loads((DATA / "fiscal.json").read_text())["years"]
    taxes = json.loads((DATA / "taxes.json").read_text())["years"]
    mins = json.loads((DATA / "ministries.json").read_text())
    schemes = json.loads((DATA / "schemes.json").read_text())["years"]

    def ministry_total(mid: str, year: str, kind: str) -> float | None:
        vals = [
            v[kind]["total_crore"] for iid, v in mins["years"].get(year, {}).items()
            if mins["items"].get(iid, {}).get("ministry_id") == mid
            and mins["items"][iid]["level"] in ("department", "union_territory")
            and kind in v and v[kind].get("total_crore") is not None
        ]
        return sum(vals) if vals else None

    def ours(row: dict) -> float | None:
        y, k, item = row["fiscal_year"], row["kind"], row["item"]
        if row["dataset"] == "summary":
            return fiscal.get(y, {}).get(item, {}).get(k, {}).get("value")
        if row["dataset"] == "taxes":
            return taxes.get(y, {}).get(item, {}).get(k, {}).get("value")
        if row["dataset"] == "ministry":
            return ministry_total(item, y, k)
        return schemes.get(y, {}).get(item, {}).get(k, {}).get("total_crore")

    failures, checked = [], 0
    with PRS_FILE.open() as f:
        for row in csv.DictReader(f):
            checked += 1
            want, got = float(row["value_crore"]), ours(row)
            if got is None or abs(got - want) > 1:  # PRS rounds to whole crore
                failures.append(f"{row['dataset']} {row['item']} {row['kind'].upper()} {row['fiscal_year']}: "
                                f"ours {got}, PRS {want:,.0f}")
    return ("Matches PRS Legislative Research, Union Budget 2026-27 Analysis (independent)", checked, failures,
            [f"{checked - len(failures)} of {checked} published figures match to the crore: headline totals, "
             "taxes by type, five ministries and Defence, four schemes."])


def check_published() -> list[tuple]:
    """Checks on the published JSON files themselves (not only on the source documents).

    The chosen values for one year and estimate type come from one budget, so
    they must still add up: ministry lines to the grand total, and net tax to
    gross tax less the deductions.
    """
    sections = []
    mins = json.loads((DATA / "ministries.json").read_text())
    items = mins["items"]
    failures, checked = [], 0
    for year, entry in mins["years"].items():
        for kind in ("be", "re", "actual"):
            gt = entry.get("grand_total", {}).get(kind)
            if not gt:
                continue
            parts = [v[kind]["total_crore"] for k, v in entry.items()
                     if items.get(k, {}).get("level") in ("department", "union_territory", "state_plan_assistance")
                     and kind in v and v[kind].get("total_crore") is not None]
            checked += 1
            if abs(sum(parts) - gt["total_crore"]) > 1:
                failures.append(f"{kind.upper()} {year}: lines add to {sum(parts):,.2f}, grand total "
                                f"{gt['total_crore']:,.2f}")
    sections.append(("Published ministries.json: lines add up to the grand total for every year and estimate",
                     checked, failures, []))
    taxes = json.loads((DATA / "taxes.json").read_text())
    failures, checked = [], 0
    for year, entry in taxes["years"].items():
        for kind in ("be", "re", "actual"):
            g, n = entry.get("gross_tax_revenue", {}).get(kind), entry.get("net_tax_revenue", {}).get(kind)
            if not g or not n or g["source_budget"] != n["source_budget"]:
                continue
            ded = sum(entry.get(d, {}).get(kind, {}).get("value") or 0 for d in
                      ("states_share", "states_share_adjustment", "nccd_transferred", "ut_local_bodies_assignment")
                      if entry.get(d, {}).get(kind, {}).get("source_budget") == g["source_budget"])
            checked += 1
            if abs(g["value"] - ded - n["value"]) > 5:
                failures.append(f"{kind.upper()} {year}: gross {g['value']:,.0f} - deductions {ded:,.0f} != net "
                                f"{n['value']:,.0f}")
    sections.append(("Published taxes.json: net tax = gross tax - states' share - other deductions",
                     checked, failures, []))
    return sections
