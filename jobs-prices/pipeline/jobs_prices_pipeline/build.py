"""Turn the downloaded files into the site's datasets.

Outputs (in jobs-prices/data/):
- plfs_rates.csv       participation, worker ratio and unemployment, one line per published combination
- plfs_workers.csv     distribution of workers (type of work, industry, employer, occupation)
- plfs_conditions.csv  regular employees without a written contract, paid leave or social security
- plfs_earnings.csv    average earnings (regular wage, casual wage, self-employment)
- cpi.csv, cpialrl.csv consumer price indices and inflation (base 2012; farm and rural labourers)
- cpi2024.csv          every figure read from the base-2024 CPI press releases, with the release it came from
- hces.csv             household spending
- hces_overall.csv     rural + urban spending per person, weighted by HCES Table A2's estimated persons
- rbi_states.csv       every value read from the RBI handbook's state tables
- sources.csv          every downloaded file: key, URL, SHA-256, date (each CSV row names its source key)
- jobs_prices.json     what the site uses, in compact form

Every CSV keeps the publisher's values and names as printed. Nothing here
changes a published number.

Run: uv run python -m jobs_prices_pipeline.build
"""

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime

from pipeline_common.numbers import number

from . import cpi2024, hces, plfs, prices, rbi
from .common import MANIFEST, ROOT
from .plfs import RATE_DIMS, STATE_BREAKDOWNS

DATA = ROOT / "data"


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    """'..._as_printed' columns are filled only where MoSPI's text is not simply the number (e.g. 'NaN', 'l0.8')."""
    with open(DATA / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {k: ("" if r.get(k) is None else r.get(k)) for k in fields}
            for k in fields:
                if k.endswith("_as_printed"):
                    v = r.get(k.removesuffix("_as_printed"))
                    if v is not None and number(out[k]) == v:
                        out[k] = ""
            w.writerow(out)


def fields_of(rows: list[dict], first: list[str]) -> list[str]:
    seen = list(first)
    for r in rows:
        for k in r:
            if k not in seen:
                seen.append(k)
    return [f for f in seen if f != "source"] + ["source"]


ALRL_FIELDS = ["month", "base_year", "state", "index_al", "index_rl", "inflation_al", "inflation_rl"]
# HCES indicators the site shows -> short ids
HCES_SITE = {
    "Average monthly per capita consumption expenditure (MPCE)": "mpce",
    "Average monthly per capita consumption expenditure (MPCE) Over 12 Fractile Classes": "classes",
    "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days": "shares",
    "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Household Type": "household_type",
    "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Social Group": "social_group",
    "Gini Coefficient for Per Capita Consumption Expenditure": "gini",
}
HCES_SITE_FIELDS = ["indicator", "year", "state", "sector", "imputation_type", "category", "value"]


def table(fields: list[str], rows: list[list]) -> dict:
    """Compact table: text columns store each distinct value once ('labels'), rows hold its position."""
    text = [i for i, _ in enumerate(fields) if any(isinstance(r[i], str) for r in rows)]
    labels = {fields[i]: sorted({r[i] for r in rows if r[i] is not None}) for i in text}
    pos = {fields[i]: {v: n for n, v in enumerate(labels[fields[i]])} for i in text}
    out = [[pos[fields[i]][v] if i in text and v is not None else v for i, v in enumerate(r)] for r in rows]
    return {"fields": fields, "labels": labels, "rows": out}


def site_json(ds: dict) -> dict:
    """What the site reads: compact arrays, the slices it shows."""
    p = ds["plfs"]
    rate_fields = ["frequency"] + RATE_DIMS + ["lfpr", "wpr", "ur"]
    # Usual status (PS+SS), except broad industry, which MoSPI publishes only in current weekly status (CWS).
    workers = [r for r in p["distribution"] if r["frequency"] == "annual"
               and (r["status"] == "PS+SS" or (r["breakdown"] == "broad_industry_work" and r["status"] == "CWS"))
               and r["category"].lower() != "all"
               and (r["breakdown"] in STATE_BREAKDOWNS or r["state"] == "All India")
               # MoSPI's All-India shares by type of work do not add up (see the checks); states only
               and not (r["breakdown"] == "broad_status_employment" and r["state"] == "All India")]
    wf = ["year", "state", "sector", "gender", "status", "breakdown", "category", "value"]
    cf = ["year", "state", "sector", "gender", "condition", "value"]
    ef = ["year", "state", "sector", "gender", "kind", "value"]
    cpi_all: dict = defaultdict(lambda: defaultdict(list))
    cpi_states: dict = defaultdict(lambda: defaultdict(list))
    for r in ds["cpi"]:
        point = [r["month"], r["index"], r["inflation"]]
        if r["state"] == "All India":
            cpi_all[f"{r['group']}|{r['subgroup']}"][r["sector"]].append(point)
        if r["subgroup"] == "General-Overall":
            cpi_states[r["state"]][r["sector"]].append(point)
    return {
        "description": ds["description"],
        "generated_at": ds["generated_at"],
        "sources": ds["sources"],
        "plfs": {
            "indicators": p["indicators"],
            "rates": table(rate_fields, [[r[f] for f in rate_fields] for r in p["rates"] if not r["left_out"]]),
            "workers": table(wf, [[r[f] for f in wf] for r in workers]),
            # Annual figures only: the site's keys have no period, so quarterly or monthly rows would merge into them.
            "conditions": table(cf, [[r[f] for f in cf] for r in p["conditions"] if r["frequency"] == "annual"]),
            "earnings": table(ef, [[r[f] for f in ef] for r in p["earnings"] if r["frequency"] == "annual"]),
        },
        "cpi": {"point_fields": ["month", "index", "inflation"], "all_india": cpi_all, "states": cpi_states},
        "cpialrl": table(ALRL_FIELDS, [[r.get(f) for f in ALRL_FIELDS] for r in ds["cpialrl"]
                                       if r.get("indicator") == "General Index"]),
        "hces": table(HCES_SITE_FIELDS, [[HCES_SITE[r["indicator"]]] + [r.get(f) for f in HCES_SITE_FIELDS[1:]]
                                         for r in ds["hces"] if r["indicator"] in HCES_SITE and not r["left_out"]]),
        "cpi2024": cpi2024.site(ds["cpi2024"]),
        "rbi": {
            "editions": sorted(set(ds["rbi_editions"].values())),
            "titles": {r["table_id"]: r["title"] for r in ds["rbi"]},
            "units": {r["table_id"]: r["unit"] for r in ds["rbi"]},
            **table(["table_id", "variant", "state", "year", "value"],
                    [[r["table_id"], r["variant"], r["state"], r["year"], r["value"]] for r in ds["rbi"]]),
        },
        "hces_overall": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "source"} for r in ds["hces_overall"]],
        "source_problems": ds["source_problems"],
    }


def assemble() -> dict:
    """Read every downloaded file into one dataset (all rows, as dicts). Used by the checks."""
    manifest = json.loads(MANIFEST.read_text())
    problems: list[str] = []
    ds: dict = {
        "description": ("Jobs (PLFS), consumer prices (CPI, CPI-AL/RL) and household spending (HCES) from MoSPI's official data API; "
                        "the base-2024 CPI from MoSPI's press releases; state comparisons from the RBI's Handbook of "
                        "Statistics on Indian States."),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": {k: {"url": v["url"], "sha256": v["sha256"], "fetched_at": v["fetched_at"], "records": v.get("records")}
                    for k, v in sorted(manifest.items()) if not v.get("empty")},
    }
    ds["plfs"] = plfs.read(manifest, problems)
    ds["cpi"] = prices.cpi(manifest, problems)
    ds["cpialrl"] = prices.cpialrl(manifest, problems)
    ds["hces"] = hces.read(manifest, problems)
    ds["hces_population"] = hces.population(manifest)
    ds["hces_overall"] = hces.overall(ds["hces_population"], ds["hces"])
    ds["rbi"], ds["rbi_problems"], ds["rbi_editions"] = rbi.read_all(manifest)
    ds["cpi2024"] = cpi2024.dataset(manifest)
    ds["source_problems"] = problems
    return ds


def outputs(ds: dict) -> dict[str, tuple[list[dict], list[str]]]:
    """CSV file name -> (rows, its first columns; any other field of the rows follows)."""
    p = ds["plfs"]
    return {
        "plfs_rates.csv": (p["rates"], ["frequency", "year_type"] + RATE_DIMS + ["lfpr", "wpr", "ur", "left_out"]),
        "plfs_workers.csv": (p["distribution"], ["frequency", "year_type", "year", "state", "sector", "gender", "status",
                                                 "breakdown", "category", "value", "value_as_printed", "unit"]),
        "plfs_conditions.csv": (p["conditions"], ["frequency", "year_type", "year", "state", "sector", "gender",
                                                  "condition", "value", "value_as_printed", "unit"]),
        "plfs_earnings.csv": (p["earnings"], ["frequency", "year_type", "year", "period", "state", "sector", "gender",
                                              "kind", "indicator", "value", "value_as_printed", "unit"]),
        "cpi.csv": (ds["cpi"], ["month", "state", "sector", "group", "subgroup", "index", "inflation"]),
        "cpialrl.csv": (ds["cpialrl"], ["month"]),
        "hces.csv": (ds["hces"], ["year", "state", "sector", "indicator"]),
        "rbi_states.csv": (ds["rbi"], ["table", "table_id", "title", "variant", "unit", "state", "year", "value",
                                        "value_as_printed", "flag"]),
        "hces_overall.csv": (ds["hces_overall"], ["year", "state", "imputation_type", "persons_rural_00", "persons_urban_00",
                                                  "mpce_rural", "mpce_urban", "mpce", "food_share"]),
        "cpi2024.csv": (cpi2024.csv_rows(ds["cpi2024"]), ["table", "month", "code", "name", "sector", "index", "inflation", "status", "release_month"]),
    }


def main() -> dict:
    ds = assemble()
    DATA.mkdir(parents=True, exist_ok=True)
    for name, (rows, first) in outputs(ds).items():
        fields = fields_of(rows, first)
        if name.startswith("plfs_"):  # columns that are blank in every row add nothing
            fields = [f for f in fields if any(r.get(f) not in (None, "") for r in rows)]
        write_csv(name, fields, rows)
        print(f"{name}: {len(rows)} rows")
    write_csv("sources.csv", ["key", "url", "sha256", "fetched_at", "records"],
              [{"key": k, **v} for k, v in ds["sources"].items()])
    (DATA / "jobs_prices.json").write_text(json.dumps(site_json(ds), ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"jobs_prices.json written; {len(ds['source_problems'])} problems")
    return ds


if __name__ == "__main__":
    main()
