"""Population, for figures per person: GDP, national income and household spending per person.

MoSPI divides its national totals by India's population at the middle of the financial year (1 October). It
prints that population in its press notes, rounded to the million; the RBI's Handbook of Statistics on the Indian
Economy reprints it to the lakh. The population differs a little between the two GDP series, so it is kept per
series and year:

- 2011-12 series, 2011-12 to 2021-22: the official projections (Census of India 2011, Population Projections for
  India and States 2011-2036, Report of the Technical Group on Population Projections, November 2019, Table 14:
  population on 1 October). MoSPI's population for these years is the projection (checked against the RBI's
  reprint below).
- Later years, and the 2022-23 series: the population MoSPI's own per-person figures imply (its GDP divided by
  its GDP per person, to about a thousand people), from its press notes (population_sources/mospi_press_notes.json,
  each row quoted and found in the document), or, where no press note here covers the year, from the RBI's reprint
  of MoSPI's tables. Per-person figures here then reproduce MoSPI's to the rupee whenever the totals are the same
  estimate.

Per-person figures are worked out for every estimate of both series: the total (from MoSPI's API, refreshed weekly)
divided by the population. Net national income is not in the API; it is GNI less depreciation, worked out as
NDP + GNI − GDP (the same thing, and available in the years MoSPI's API gives no depreciation figure).

A year with national accounts but no population yet (a new year's first estimate) has no per-person figures; the
validation report lists it, to be added from MoSPI's press note.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURATED = Path(__file__).resolve().parent / "population_sources"

PROJECTIONS = {
    "key": "population/projections-2019",
    "url": "https://nhm.gov.in/New_Updates_2018/Report_Population_Projection_2019.pdf",
    "title": "Census of India 2011: Population Projections for India and States 2011-2036, Report of the Technical "
             "Group on Population Projections (National Commission on Population, November 2019)",
    "table": "Table 14: projected total population as on 1st October ('000)",
    "pdf_page": 125,
}
# The last year for which MoSPI's population is the projection (from 2022-23 it uses its own, higher figures).
PROJECTIONS_UNTIL = "2021-22"

RBI_EDITION = "2025-26"
RBI_TABLES = {
    "cur": {
        "key": "population/rbi-hbs-table-1",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/1T_HBIE310720260FBAA53A59A94B94A78CB8313C150B62.XLSX",
        "title": f"RBI, Handbook of Statistics on the Indian Economy {RBI_EDITION}, Table 1: Macro-Economic Aggregates (at current prices)",
    },
    "con": {
        "key": "population/rbi-hbs-table-2",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/2T_HBIE310720261ED415A38F9E465C9B9BEDEA897741FB.XLSX",
        "title": f"RBI, Handbook of Statistics on the Indian Economy {RBI_EDITION}, Table 2: Macro-Economic Aggregates (at constant prices)",
    },
}

MEASURES = {"gdp": "GDP", "gni": "GNI", "nni": "NNI", "pfce": "PFCE"}
SERIES = ("2011-12", "2022-23")

# Tolerances.
IMPLIED_TOL = 2e-5  # population implied by different per-person figures in one table (each rounded to ₹1)
SAME_ESTIMATE_TOL = 2  # ₹ crore: a published total and the API's total are the same estimate
PER_PERSON_TOL = 2  # ₹: a per-person figure here and MoSPI's printed one
LAKH_TOL = 0.501  # lakh: population against the RBI's figure, printed to the nearest lakh
PROJECTION_TOL = 1e-4  # MoSPI's population (as implied) against the projection, 2011-12 to 2021-22


def fy_start(y: str) -> int:
    return int(y[:4])


def fy(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def num(s: str) -> float:
    return float(s.replace(",", ""))


# ---- downloads -------------------------------------------------------------------

def press_notes() -> list[dict]:
    return json.loads((CURATED / "mospi_press_notes.json").read_text())


def note_key(url: str) -> str:
    import hashlib

    return "population/press-note-" + hashlib.sha1(url.encode()).hexdigest()[:12]


def documents() -> list[tuple[str, str, str]]:
    """(manifest key, url, extension) of every document this module reads."""
    out = [(PROJECTIONS["key"], PROJECTIONS["url"], "pdf")]
    out += [(t["key"], t["url"], "xlsx") for t in RBI_TABLES.values()]
    out += [(note_key(n["url"]), n["url"], "pdf") for n in press_notes()]
    return out


def fetch(manifest: dict, force: bool) -> None:
    from .fetch import RAW, get, save

    for key, url, ext in documents():
        if key in manifest and not force:
            continue
        try:
            content = get(url)
        except Exception as exc:  # noqa: BLE001 - report and carry on; the checks will fail
            print(f"{key}: {url} -> {exc}")
            continue
        save(manifest, key, RAW / f"{key}.{ext}", content, url)
        print(f"{key}: saved {url} ({len(content):,} bytes)")


def path_of(manifest: dict, key: str) -> Path | None:
    entry = manifest.get(key)
    return ROOT / entry["file"] if entry and (ROOT / entry["file"]).exists() else None


def page_text(path: Path, page: int) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return (pdf.pages[page - 1].extract_text() or "") if page <= len(pdf.pages) else ""


# ---- reading the sources ---------------------------------------------------------

def read_projections(manifest: dict) -> tuple[dict, list[str]]:
    """{fiscal year: {persons, male, female}} in thousands, from Table 14 (India columns)."""
    path = path_of(manifest, PROJECTIONS["key"])
    if not path:
        return {}, [f"{PROJECTIONS['title']}: not downloaded"]
    text = page_text(path, PROJECTIONS["pdf_page"])
    problems = []
    if "Projected Total Population by Sex as on 1st October" not in text or "INDIA" not in text:
        problems.append(f"page {PROJECTIONS['pdf_page']} is not Table 14 for India")
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(20[1-3]\d) ([\d,]+) ([\d,]+) ([\d,]+) ", line)
        if m:
            out[fy(int(m[1]))] = {"persons": num(m[2]), "male": num(m[3]), "female": num(m[4])}
    return out, problems


def numbers(quote: str) -> list[float]:
    """The figures in a quoted statement row, leaving out its row number."""
    body = re.sub(r"^\d+\s+", "", quote)
    return [num(x) for x in re.findall(r"(?<![\w.,])\d[\d,]*(?![\w.])", body)]


def read_notes(manifest: dict) -> tuple[list[dict], list[str], int]:
    """Each press-note table with its figures by year, and any quote not found in its document."""
    out, problems, checked = [], [], 0
    for n in press_notes():
        path = path_of(manifest, note_key(n["url"]))
        for t in n["tables"]:
            text = page_text(path, t["pdf_page"]) if path else ""
            flat = re.sub(r"\s+", " ", text)
            figures = {}
            for row, quote in t["rows"].items():
                checked += 1
                where = f"{n['document']}, {t['statement']}, '{row}'"
                if not path:
                    problems.append(f"{where}: document not downloaded ({n['url']})")
                elif quote not in flat:
                    problems.append(f"{where}: row not found on PDF page {t['pdf_page']}: “{quote}”")
                vals = numbers(quote)
                if len(vals) != len(n["years"]):
                    problems.append(f"{where}: {len(vals)} figures for {len(n['years'])} years in “{quote}”")
                    continue
                figures[row] = dict(zip(n["years"], vals))
            out.append({"document": n["document"], "date": n["date"], "base": n["base"], "url": n["url"],
                        "statement": t["statement"], "prices": t["prices"], "years": n["years"], "figures": figures})
    return out, problems, checked


RBI_ROWS = {
    "Population (in Lakhs)": "population_lakh",
    "Gross Domestic Product": "gdp", "Gross National Income": "gni", "Net National Income": "nni",
    "Private Final Consumption Expenditure": "pfce",
    "Per Capita GDP (₹)": "pc_gdp", "Per Capita GNI (₹)": "pc_gni", "Per Capita NNI (₹)": "pc_nni",
    "Per Capita PFCE (₹)": "pc_pfce",
}


def read_rbi(manifest: dict) -> tuple[list[dict], list[str]]:
    """The RBI's tables as press-note-like records: one per (prices, base)."""
    import openpyxl

    out, problems = [], []
    for prices, t in RBI_TABLES.items():
        path = path_of(manifest, t["key"])
        if not path:
            problems.append(f"{t['title']}: not downloaded")
            continue
        rows = list(openpyxl.load_workbook(path, data_only=True).active.iter_rows(values_only=True))
        head = next((r for r in rows if "Item/Year" in r), None)
        base_row = next((r for r in rows if any(isinstance(c, str) and c.startswith("(Base Year") for c in r)), None)
        if not head or not base_row:
            problems.append(f"{t['title']}: layout changed (no year or base-year row)")
            continue
        bases, current = [], None
        for c in base_row:
            if isinstance(c, str) and (m := re.search(r"Base Year: (\d{4}-\d{2})", c)):
                current = m[1]
            bases.append(current)
        label = head.index("Item/Year")
        by_base: dict[str, dict] = {}
        for r in rows:
            name = r[label].strip() if isinstance(r[label], str) else None
            if name not in RBI_ROWS:
                continue
            for i in range(label + 1, len(r)):
                if isinstance(head[i], str) and re.fullmatch(r"\d{4}-\d{2}", head[i]) and bases[i] and isinstance(r[i], (int, float)):
                    by_base.setdefault(bases[i], {}).setdefault(RBI_ROWS[name], {})[head[i]] = float(r[i])
        if not by_base:
            problems.append(f"{t['title']}: no figures read")
        for base, figures in by_base.items():
            years = sorted({y for v in figures.values() for y in v})
            out.append({"document": t["title"], "date": None, "base": base, "url": t["url"], "statement": "",
                        "prices": prices, "years": years, "figures": figures})
    return out, problems


# ---- population and per-person figures -------------------------------------------

def implied(table: dict, year: str) -> list[float]:
    """Population (million) implied by each total and its per-person figure in a table."""
    f = table["figures"]
    out = []
    for m in MEASURES:
        if year in f.get(m, {}) and f.get(f"pc_{m}", {}).get(year):
            out.append(f[m][year] * 1e7 / f[f"pc_{m}"][year] / 1e6)
    return out


def population(manifest: dict) -> tuple[dict, dict]:
    """{series: {year: {million, source, ...}}} and the parsed sources (for the checks)."""
    proj, proj_problems = read_projections(manifest)
    notes, note_problems, note_checked = read_notes(manifest)
    rbi, rbi_problems = read_rbi(manifest)
    out: dict[str, dict] = {s: {} for s in SERIES}
    for y, p in proj.items():
        if y <= PROJECTIONS_UNTIL:
            out["2011-12"][y] = {"million": round(p["persons"] / 1000, 3), "source": "projections"}
    # MoSPI's own figures: press notes first (latest first), then the RBI's reprint for years no note covers.
    for t in sorted(notes, key=lambda t: t["date"], reverse=True) + rbi:
        if t["base"] not in out:
            continue
        for y in t["years"]:
            vals = implied(t, y)
            if not vals or y in out[t["base"]] or y <= PROJECTIONS_UNTIL:
                continue
            printed = t["figures"].get("population", {}).get(y)
            lakh = t["figures"].get("population_lakh", {}).get(y)
            out[t["base"]][y] = {"million": round(vals[0], 3), "source": "mospi", "document": t["document"],
                                 **({"printed_million": printed} if printed else {}),
                                 **({"printed_lakh": lakh} if lakh else {})}
    sources = {"projections": proj, "notes": notes, "rbi": rbi, "note_checked": note_checked,
               "problems": proj_problems + note_problems + rbi_problems}
    return {s: dict(sorted(v.items())) for s, v in out.items()}, sources


def nni(node: dict, price: str) -> float | None:
    """Net national income = GNI − depreciation = NDP + GNI − GDP."""
    parts = [node.get(k, {}).get(price) for k in ("ndp", "gni", "gdp")]
    return parts[0] + parts[1] - parts[2] if all(v is not None for v in parts) else None


def totals(node: dict, price: str) -> dict:
    out = {m: node.get(m, {}).get(price) for m in ("gdp", "gni", "pfce")}
    out["nni"] = nni(node, price)
    return {m: v for m, v in out.items() if v is not None}


def per_person(node: dict, million: float) -> dict:
    """₹ per person, for each measure and price basis available."""
    out: dict = {}
    for price in ("cur", "con"):
        for m, v in totals(node, price).items():
            out.setdefault(m, {})[price] = round(v * 1e7 / (million * 1e6))
    return out


def write_csv(tree: dict, pop: dict, path: Path) -> int:
    """per_person.csv: one row per series, year, estimate and measure."""
    import csv

    from .build import STAGE_ORDER

    rows = []
    for series in SERIES:
        for year, stages in sorted(tree.get(series, {}).get("annual", {}).items()):
            for stage in sorted(stages, key=lambda s: STAGE_ORDER.get(s, 99)):
                for m, v in stages[stage].get("per_person", {}).items():
                    rows.append({"series": series, "year": year, "stage": stage, "measure": m,
                                 "population_million": pop[series][year]["million"],
                                 "current_prices_rupees": v.get("cur", ""), "constant_prices_rupees": v.get("con", "")})
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def build(manifest: dict, tree: dict) -> dict:
    """Adds per_person to every annual estimate that has a population; returns the population block."""
    pop, _ = population(manifest)
    for series in SERIES:
        for year, stages in tree.get(series, {}).get("annual", {}).items():
            p = pop[series].get(year)
            if not p:
                continue
            for node in stages.values():
                pp = per_person(node, p["million"])
                if pp:
                    node["per_person"] = pp
    return {
        "description": "Population at the middle of the financial year (1 October), in millions, as MoSPI uses it "
                       "for figures per person. Per-person figures are in rupees.",
        "by_series": pop,
        "sources": {
            "projections": {k: PROJECTIONS[k] for k in ("title", "table", "url")},
            "press_notes": [{k: n[k] for k in ("document", "date", "url")} for n in press_notes()],
            "rbi": [{k: t[k] for k in ("title", "url")} for t in RBI_TABLES.values()],
        },
        "projections_until": PROJECTIONS_UNTIL,
    }


# ---- checks ----------------------------------------------------------------------

def latest(stages: dict) -> tuple[str, dict]:
    from .build import STAGE_ORDER

    s = max(stages, key=lambda x: STAGE_ORDER.get(x, 99))
    return s, stages[s]


def check(ds: dict, report, manifest: dict | None = None) -> None:
    manifest = manifest or json.loads((ROOT / "sources" / "manifest.json").read_text())
    pop, src = population(manifest)
    failures = list(src["problems"])
    notes: list[str] = []
    checked = src["note_checked"]

    # 1. The projections table reads cleanly: 2011 to 2036, persons = male + female, rising.
    proj = src["projections"]
    years = sorted(proj)
    checked += 1
    if years != [fy(y) for y in range(2011, 2037)]:
        failures.append(f"projections: years read {years[:1]}…{years[-1:]} ({len(years)}), expected 2011 to 2036")
    for i, y in enumerate(years):
        checked += 1
        p = proj[y]
        if abs(p["male"] + p["female"] - p["persons"]) > 1:
            failures.append(f"projections {y}: male + female = {p['male'] + p['female']:,.0f}, persons {p['persons']:,.0f}")
        if i and p["persons"] <= proj[years[i - 1]]["persons"]:
            failures.append(f"projections {y}: population does not rise from {years[i - 1]}")

    # 2. Within each table, every per-person figure implies the same population, and it rounds to the printed one.
    for t in src["notes"] + src["rbi"]:
        for y in t["years"]:
            vals = implied(t, y)
            if not vals:
                continue
            checked += 1
            label = f"{t['document']}{', ' + t['statement'] if t['statement'] else ''}, {y}"
            if max(vals) / min(vals) - 1 > IMPLIED_TOL:
                failures.append(f"{label}: per-person figures imply different populations "
                                f"({', '.join(f'{v:.3f}' for v in vals)} million)")
            printed = t["figures"].get("population", {}).get(y)
            if printed is not None and abs(vals[0] - printed) > 0.5:
                failures.append(f"{label}: implied population {vals[0]:.3f} million, printed {printed:,.0f}")

    # 3. Population used here, against the RBI's reprint (to the lakh): both the projections and MoSPI's own.
    for t in src["rbi"]:
        for y, lakh in t["figures"].get("population_lakh", {}).items():
            p = pop.get(t["base"], {}).get(y)
            if not p:
                continue
            checked += 1
            if abs(p["million"] * 10 - lakh) > LAKH_TOL:
                failures.append(f"{t['base']} series, {y}: population {p['million']:.3f} million here, "
                                f"RBI {lakh:,.0f} lakh")

    # 4. Where MoSPI's own figure and the projection both exist, they agree up to 2021-22 (so the projections are
    #    MoSPI's population for the earlier years); from 2022-23 the difference is listed.
    for t in src["rbi"] + src["notes"]:
        for y in t["years"]:
            vals = implied(t, y)
            if not vals or y not in proj:
                continue
            diff = vals[0] / (proj[y]["persons"] / 1000) - 1
            if y <= PROJECTIONS_UNTIL:
                checked += 1
                if abs(diff) > PROJECTION_TOL:
                    failures.append(f"{t['base']} series, {y}: MoSPI's population (implied, {vals[0]:.3f} million) "
                                    f"differs from the projection ({proj[y]['persons'] / 1000:.3f}) by {diff:+.3%}")
    for series, years_ in pop.items():
        later = [(y, p) for y, p in years_.items() if p["source"] == "mospi" and y in proj]
        if later:
            notes.append(f"{series} series: MoSPI's population from 2022-23 is above the 2019 projections ("
                         + "; ".join(f"{y}: {p['million']:,.1f} million against {proj[y]['persons'] / 1000:,.1f}"
                                     for y, p in later) + ").")

    # 5. Per-person figures here reproduce every published one where the published total is the same estimate as
    #    the API's latest.
    data = ds["data"]
    reproduced = newer = 0
    for t in src["notes"] + src["rbi"]:
        series = t["base"]
        for y in t["years"]:
            stages = data.get(series, {}).get("annual", {}).get(y)
            if not stages:
                continue
            stage, node = latest(stages)
            for m in MEASURES:
                pub_total = t["figures"].get(m, {}).get(y)
                pub_pp = t["figures"].get(f"pc_{m}", {}).get(y)
                if pub_total is None or pub_pp is None:
                    continue
                ours_total = totals(node, t["prices"]).get(m)
                if ours_total is None or abs(ours_total - pub_total) > SAME_ESTIMATE_TOL:
                    newer += 1
                    continue
                checked += 1
                reproduced += 1
                ours = node.get("per_person", {}).get(m, {}).get(t["prices"])
                if ours is None or abs(ours - pub_pp) > PER_PERSON_TOL:
                    failures.append(f"{series} series, {y} ({stage}), {MEASURES[m]} per person at "
                                    f"{'current' if t['prices'] == 'cur' else 'constant'} prices: {ours} here, "
                                    f"{pub_pp:,.0f} in {t['document']}")
    notes.append(f"{reproduced} published per-person figures reproduced to within ₹{PER_PERSON_TOL}; {newer} others "
                 "are for an earlier estimate than the API's latest and are not compared.")

    # 6. Years with national accounts but no population (for review: add the year from MoSPI's press note).
    for series in SERIES:
        missing = [y for y in data.get(series, {}).get("annual", {}) if y not in pop[series]]
        if missing:
            notes.append(f"{series} series: no population for {', '.join(sorted(missing))}, so no per-person figures; "
                         "add the year from MoSPI's press note (population_sources/mospi_press_notes.json).")
    report.add("Population and figures per person", checked, failures, notes)
