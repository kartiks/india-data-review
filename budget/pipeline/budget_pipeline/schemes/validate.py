"""Checks on the parsed statements, and the reviewed exceptions."""

from collections import defaultdict

from .common import PARTS, TOLERANCE

RAILWAYS_2017 = (
    "Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union "
    "Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' "
    "internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: "
    "55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed."
)
GROSS_2017 = (
    "Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal "
    "in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and "
    "some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the "
    "difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed."
)
MOHUA_2018 = (
    "Budget 2018-19 Statement 4B, Ministry of Housing and Urban Affairs, Actual 2016-17: the schemes' total "
    "matches the Demand subtotal, but 314.00 crore is classed as capital in the subtotal and as revenue in the "
    "scheme rows. Shown as printed."
)
FUNDS_2024 = (
    "Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and "
    "6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met "
    "from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to "
    "the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross."
)
GT_2025_CSS = (
    "Budget 2025-26 Statement 4A Grand Total, BE 2025-26: printed revenue 5,36,826.78 (read from the page image; "
    "the row is missing from the text layer) but printed total 5,41,850.21 = 5,41,826.78 + 23.43, and the "
    "Demand subtotals add to 5,41,826.78 revenue. The printed revenue figure is 5,000 crore short; shown as printed."
)

PMKSY_2023 = (
    "Budget 2024-25 Statement 4A prints the Watershed Development Component of PMKSY (Department of Land "
    "Resources, BE 2023-24 2,200.00) as a row of its own; Budget 2023-24 counted it in PMKSY. 10,787.23 - "
    "2,200.00 = 8,587.23, and the Grand Total for BE 2023-24 is the same in both budgets (4,76,104.59)."
)
PMKSY_2024 = (
    "Budget 2025-26 Statement 4A restates BE 2024-25 with PMKSY split up: Flood Management and Border Areas "
    "Programme (449.57) and Irrigation Census (40.00) become rows of their own, and 600.00 moves to 'Others "
    "(including amount met from & transfer to various funds)', -8,634.42 becoming -8,034.42. 9,339.37 - 449.57 "
    "- 40.00 - 600.00 = 8,249.80; no other row changes and the Grand Total for BE 2024-25 is the same in both "
    "budgets (5,05,978.07)."
)

# A BE reprinted in the next budget may be restated. A scheme row's difference above both limits fails unless
# listed below; a Grand Total fails on any difference beyond rounding unless listed (the reasons for scheme rows
# rely on the Grand Total being unchanged).
RESTATED_REL = 0.02
RESTATED_CRORE = 500

CENTRAL_SECTOR_2017 = (
    "Budget 2018-19 prints the central sector schemes' Grand Total for BE 2017-18 as 6,63,663.02, against 6,66,644.02 "
    "in Budget 2017-18 itself (-2,981.00, 0.4%). The statement was reorganised between the two budgets (36 rows "
    "printed only in Budget 2017-18, 60 only in Budget 2018-19), so the restatement cannot be traced to single rows; "
    "the rows printed in both agree."
)

# (budget, scheme_type, check, key) -> reason. Keys: rct "<level> <number>|<kind> <year>",
# group "<level> <number>|<kind> <year>" or "<level> <number>|*", grand "<kind> <year>|<part>".
# A figure that differs between the two budgets printing it: ("cross", scheme_type, item_id, "<kind> <year>").
# Each entry was verified by hand (page images, other columns, other budgets).
KNOWN_EXCEPTIONS: dict[tuple[str, str, str, str], str] = {
    ("2017-18", "central_sector", "group", "demand_subtotal 80|*"): RAILWAYS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 31|*"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 48|*"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 67|Actual 2015-16"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 81|Actual 2015-16"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 81|BE 2016-17"): GROSS_2017,
    ("2018-19", "central_sector", "group", "demand_subtotal 56|Actual 2016-17"): MOHUA_2018,
    ("2024-25", "central_sector", "group", "demand_subtotal 71|BE 2024-25"): FUNDS_2024,
    ("2024-25", "central_sector", "group", "demand_subtotal 86|BE 2024-25"): FUNDS_2024,
    ("2025-26", "css", "rct", "grand_total|BE 2025-26"): GT_2025_CSS,
    ("2025-26", "css", "grand", "BE 2025-26|revenue"): GT_2025_CSS,
    ("cross", "css", "css:pradhan_mantri_krishi_sinchai_yojna", "BE 2023-24"): PMKSY_2023,
    ("cross", "css", "css:pradhan_mantri_krishi_sinchai_yojna", "BE 2024-25"): PMKSY_2024,
    ("cross", "css", "css:others_including_amount_met_from_transfer_to_various_funds", "BE 2024-25"): PMKSY_2024,
    ("cross", "central_sector", "central_sector:grand_total", "BE 2017-18"): CENTRAL_SECTOR_2017,
}

# (budget, scheme_type, ext) -> why a secondary copy differs from the PDF (the PDF is used).
KNOWN_FORMAT_ISSUES: dict[tuple[str, str, str], str] = {
    ("2021-22", "css", "xlsx"): (
        "An earlier version: about 25,786 crore of BE 2021-22 sits in item 36 'Others' (26,446.35) instead of the "
        "named Core schemes (e.g. Saksham Anganwadi and Poshan 2.0, 20,105), so the Core and Others subtotals "
        "differ. The PDF's rows add up to its subtotals and Grand Total."
    ),
    ("2023-24", "css", "xls"): (
        "The Excel copy leaves BE 2023-24 blank for 'Assistance to States Agencies for Intra-State Movement of "
        "Foodgrains...' (the PDF and its page image show 7,424.60) and numbers two rows '58', so 'Others "
        "(Recoveries)' cannot be matched."
    ),
    ("2024-25", "central_sector", "xlsx"): (
        "A BE-2024-25-only copy that leaves out 8 Demands (5, 9, 43, 44, 45, 78, 92, 95) and their 79 schemes; "
        "every row it does have matches the PDF."
    ),
    ("2025-26", "css", "xlsx"): (
        "Has no Grand Total row, like the PDF's text layer (apparently converted from the PDF); every other row "
        "matches."
    ),
}


def _lab(i: dict) -> str:
    return f"{i['level']} {i['number']}".strip()


def _per(pk: tuple) -> str:
    return f"{pk[1]} {pk[0]}"


def _exc(year: str, t: str, check: str, key: str) -> str | None:
    if (year, t, check, key) in KNOWN_EXCEPTIONS:
        return KNOWN_EXCEPTIONS[(year, t, check, key)]
    wild = key.split("|")[0] + "|*"
    return KNOWN_EXCEPTIONS.get((year, t, check, wild))


def _v(x: float | None) -> float:
    return x or 0.0


def _revenue_plus_capital(budgets: dict) -> tuple[str, int, list[str], list[str]]:
    """(a) Revenue + Capital = Total, every row and period."""
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                fails.append(f"Budget {year} {t}: no copy could be read: {e['errors']}")
                continue
            for i in e["parsed"]["items"]:
                for pk, v in i["values"].items():
                    checked += 1
                    diff = _v(v["revenue"]) + _v(v["capital"]) - _v(v["total"])
                    if abs(diff) > TOLERANCE:
                        reason = _exc(year, t, "rct", f"{_lab(i)}|{_per(pk)}")
                        msg = (f"Budget {year} {t}: {i['label_as_printed'][:60]!r} {pk[1]} {pk[0]}: "
                               f"{_v(v['revenue']):.2f} + {_v(v['capital']):.2f} != {_v(v['total']):.2f}")
                        (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
    return ("Schemes: revenue + capital = total in every row", checked, fails, notes)


def _sums(budgets: dict) -> tuple[str, int, list[str], list[str]]:
    """(b) Schemes add up to their group subtotal; groups add up to the grand total."""
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            items = e["parsed"]["items"]
            schemes = [i for i in items if i["level"] == "scheme"]
            comps = [i for i in items if i["level"] == "component"]
            groups = [i for i in items if i["level"] in ("demand_subtotal", "category_subtotal")]
            grand = [i for i in items if i["level"] == "grand_total"]
            if len(grand) != 1:
                fails.append(f"Budget {year} {t}: expected one Grand Total row, found {len(grand)}")
                continue
            for pk in grand[0]["values"]:
                for part in PARTS:
                    # groups -> grand total
                    checked += 1
                    if groups:
                        # Group subtotals, plus any row printed outside every group (see lines_to_items).
                        s = sum(_v(g["values"][pk][part]) for g in groups) + sum(
                            _v(s_["values"][pk][part]) for s_ in schemes
                            if s_["demand_no"] is None and s_["category"] is None)
                    else:
                        s = sum(_v(s_["values"][pk][part]) for s_ in schemes)
                    gt = _v(grand[0]["values"][pk][part])
                    all_rows = sum(_v(s_["values"][pk][part]) for s_ in schemes)
                    if abs(s - gt) > 0.5 and abs(all_rows - gt) <= 0.5:
                        notes.append(f"Budget {year} {t} {pk[1]} {pk[0]} {part}: Grand Total equals the sum of all "
                                     f"scheme rows ({all_rows:,.2f}) but not of the group subtotals ({s:,.2f}).")
                    elif abs(s - gt) > 0.5:
                        reason = _exc(year, t, "grand", f"{_per(pk)}|{part}")
                        msg = f"Budget {year} {t} {pk[1]} {pk[0]} {part}: groups sum to {s:,.2f}, Grand Total {gt:,.2f}"
                        (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
                    # schemes -> each group
                    for g in groups:
                        members = [s_ for s_ in schemes if (s_["demand_no"] == g["demand_no"] if g["level"] == "demand_subtotal"
                                                            else s_["category"] == g["category"])]
                        checked += 1
                        s = sum(_v(m["values"][pk][part]) for m in members)
                        gv = _v(g["values"][pk][part])
                        if abs(s - gv) > 0.5:
                            reason = _exc(year, t, "group", f"{_lab(g)}|{_per(pk)}")
                            msg = (f"Budget {year} {t} {g['level']} {g['number']} ({(g['department'] or g['label_as_printed'])[:40]}) "
                                   f"{pk[1]} {pk[0]} {part}: schemes sum to {s:,.2f}, subtotal {gv:,.2f}")
                            (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
                    # components -> parent scheme (only where a scheme lists components)
                    for parent in {c["parent"] for c in comps}:
                        p_item = next((s_ for s_ in schemes if s_["number"] == parent), None)
                        members = [c for c in comps if c["parent"] == parent]
                        if p_item is None:
                            continue
                        checked += 1
                        s = sum(_v(m["values"][pk][part]) for m in members)
                        pv = _v(p_item["values"][pk][part])
                        if abs(s - pv) > 0.5:
                            reason = _exc(year, t, "component", f"scheme {parent}|{_per(pk)}")
                            msg = (f"Budget {year} {t} scheme {parent} {p_item['label_as_printed'][:40]!r} {pk[1]} {pk[0]} "
                                   f"{part}: components sum to {s:,.2f}, scheme {pv:,.2f}")
                            (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
    return ("Schemes add up to their subtotals and the Grand Total", checked, fails, notes)


def _across_budgets(budgets: dict) -> tuple[str, int, list[str], list[str]]:
    """(c) Same item, same period, printed in two budgets."""
    checked, fails, notes = 0, [], []
    seen: dict[tuple, list[tuple[str, float, str]]] = defaultdict(list)
    ambiguous = 0
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            for i in e["parsed"]["items"]:
                if i["level"] not in ("scheme", "grand_total"):
                    continue
                if i.get("ambiguous_name"):
                    ambiguous += 1
                    continue
                for pk, v in i["values"].items():
                    seen[(t, i["item_id"], pk)].append((year, _v(v["total"]), i["label_as_printed"], i["level"]))
    for (t, iid, pk), obs in sorted(seen.items(), key=lambda x: str(x[0])):
        if len(obs) < 2:
            continue
        checked += 1
        vals = {round(v, 2) for _, v, _, _ in obs}
        if len(vals) > 1:
            (a_year, a, lab, level), (b_year, b, _, _) = obs[0], obs[1]
            rel = abs(a - b) / max(abs(a), abs(b), 1)
            msg = (f"{t} {lab[:50]!r} {pk[1]} {pk[0]}: {a:,.2f} in budget {a_year} vs {b:,.2f} in budget {b_year} "
                   f"({b - a:+,.2f}, {rel:.1%})")
            reason = _exc("cross", t, iid, _per(pk))
            if reason:
                notes.append(msg + f". Explained: {reason}")
            elif level == "grand_total" and abs(a - b) <= TOLERANCE:
                notes.append("Rounding: " + msg)
            elif pk[1] == "BE" and level != "grand_total" and (rel <= RESTATED_REL or abs(a - b) <= RESTATED_CRORE):
                # The next budget may restate a BE (reclassification); a small change is only noted.
                notes.append("Restated: " + msg)
            else:
                fails.append(msg)
    notes.insert(0, f"{ambiguous} scheme rows not compared: the same name appears twice under one department "
                    "in that budget, so they cannot be matched across budgets by name.")
    return ("Same scheme figure agrees across the two budgets that print it", checked, fails, notes)


def _other_copies(budgets: dict) -> tuple[str, int, list[str], list[str]]:
    """(d) Other copies agree with the PDF."""
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            for ext, err in e["errors"].items():
                notes.append(f"Budget {year} {t}: {ext.upper()} copy could not be read ({err}).")
            for ext, diffs in e["differences"].items():
                checked += 1
                if not diffs:
                    notes.append(f"Budget {year} {t}: {ext.upper()} agrees with the PDF.")
                elif (year, t, ext) in KNOWN_FORMAT_ISSUES:
                    notes.append(f"Budget {year} {t}: {ext.upper()} differs in {len(diffs)} values (known): "
                                 f"{KNOWN_FORMAT_ISSUES[(year, t, ext)]}")
                else:
                    sample = "; ".join(f"{d.get('label', '')[:30]!r} {d.get('period', '')} {d.get('part', d.get('issue'))}: "
                                       f"{d.get('primary', '')} vs {d.get('other', '')}" for d in diffs[:3])
                    fails.append(f"Budget {year} {t}: {ext.upper()} differs from PDF in {len(diffs)} values ({sample})")
    return ("Scheme tables: other copies agree with the PDF", checked, fails, notes)


def _share_of_spending(budgets: dict, summary_observations: list[dict]) -> tuple[str, int, list[str], list[str]]:
    """(e) Share of total expenditure (context, not an identity)."""
    notes = []
    total_exp = {(r["source_budget"], r["fiscal_year"], r["kind"]): float(r["value_crore"])
                 for r in summary_observations if r["field"] == "total_expenditure" and r["value_crore"]}
    for year, by_type in budgets.items():
        parts = []
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            g = next((i for i in e["parsed"]["items"] if i["level"] == "grand_total"), None)
            if g is None:
                continue
            v = g["values"].get((year, "BE"))
            te = total_exp.get((year, year, "BE"))
            if v and te:
                parts.append(f"{t} {v['total'] / te:.1%}")
        if parts:
            notes.append(f"Budget {year}, BE {year}: share of total expenditure: " + ", ".join(parts))
    return ("Scheme spending as a share of total expenditure (context only)", 0, [], notes)


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple[str, int, list[str], list[str]]]:
    """Every scheme check, one group each: [(title, checked, failures, notes)]."""
    budgets = all_parsed["budgets"]
    return [
        _revenue_plus_capital(budgets),
        _sums(budgets),
        _across_budgets(budgets),
        _other_copies(budgets),
        _share_of_spending(budgets, summary_observations),
    ]
