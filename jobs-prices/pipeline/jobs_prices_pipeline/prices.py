"""Consumer price indices from MoSPI's data service: CPI (base 2012) and the Labour Bureau's CPI for agricultural
and rural labourers (CPI-AL/RL)."""

from pipeline_common.numbers import number

from .common import MONTH_NO, load


def ym(r: dict) -> str:
    """'2025-12'. Years written '2024-2025' are agricultural years (July to June), as in the Labour Bureau's CPI-AL/RL."""
    m = MONTH_NO[r["month"]]
    y = str(r["year"])
    if "-" in y:
        start = int(y[:4])
        return f"{start if m >= 7 else start + 1}-{m:02d}"
    return f"{int(y)}-{m:02d}"


def cpi(manifest: dict, problems: list[str]) -> list[dict]:
    out, seen = [], {}
    for key, entry, body in load(manifest, "cpi/"):
        file = "all_india" if key.startswith("cpi/all_india/") else "states"
        for r in body["rows"]:
            if file == "states" and r.get("subgroup") != "General-Overall":
                problems.append(f"{key}: unexpected subgroup {r.get('subgroup')!r} in the general-index file")
                continue
            rec = {"month": ym(r), "state": r["state"], "sector": r["sector"], "group": r["group"],
                   "subgroup": r["subgroup"], "index": number(r.get("index")), "inflation": number(r.get("inflation")),
                   "index_as_printed": r.get("index"), "inflation_as_printed": r.get("inflation"),
                   "status": r.get("status") or "", "base_year": r.get("baseyear"), "source": key}
            k = (rec["month"], rec["state"], rec["sector"], rec["subgroup"])
            if k in seen:
                a = seen[k]
                if (a["index"], a["inflation"]) != (rec["index"], rec["inflation"]):
                    problems.append(f"{key}: {k} published twice with different values")
                continue  # All India's general index is in both files
            seen[k] = rec
            out.append(rec)
    out.sort(key=lambda r: (r["state"] != "All India", r["state"], r["group"], r["subgroup"], r["sector"], r["month"]))
    return out


def cpialrl(manifest: dict, problems: list[str]) -> list[dict]:
    out = []
    for key, entry, body in load(manifest, "cpialrl/"):
        for r in body["rows"]:
            rec = {"month": ym(r), **{k: v for k, v in r.items() if k not in ("year", "month")}, "source": key}
            for k in ("index_al", "index_rl", "inflation_al", "inflation_rl"):
                rec[k + "_as_printed"] = r.get(k)
                rec[k] = number(r.get(k))
            for who in ("al", "rl"):
                if rec[f"index_{who}"] == 0:  # an index of 0.00 means not compiled (Delhi has no farm labourers' index)
                    rec[f"index_{who}"] = rec[f"inflation_{who}"] = None
                    rec[f"not_compiled_{who}"] = True
            out.append(rec)
    out.sort(key=lambda r: (r.get("indicator", ""), r.get("state", ""), str(r.get("group", "")), r["month"]))
    return out
