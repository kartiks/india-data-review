"""Stable ids for schemes across budgets, through the reviewed name map (data_maps/scheme_names.csv)."""

import csv
import re
from collections import defaultdict

from .common import NAME_MAP, SCHEME_TYPES


def normalise_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def slug(name: str) -> str:
    return normalise_name(name).replace(" ", "_")[:80]


def load_name_map() -> dict[tuple[str, str], list[dict]]:
    """(scheme_type, normalised printed name) -> rows {budgets, scheme_id, scheme_name, evidence}.
    A row applies to the budgets listed (blank = all)."""
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if NAME_MAP.exists():
        with NAME_MAP.open() as f:
            for r in csv.DictReader(f):
                r["budget_set"] = set(b for b in r["budgets"].split() if b)
                out[(r["scheme_type"], normalise_name(r["printed_name"]))].append(r)
    return out


def item_id(i: dict, names: dict, budget: str = "") -> str:
    t = i["scheme_type"]
    if i["level"] == "grand_total":
        return f"{t}:grand_total"
    if i["level"] == "demand_subtotal":
        return f"{t}:demand:{i['demand_no']}"
    if i["level"] == "category_subtotal":
        return f"{t}:category:{i['category']}"
    rows = names.get((t, normalise_name(i["label_as_printed"])), [])
    m = next((r for r in rows if not r["budget_set"] or budget in r["budget_set"]), None)
    base = m["scheme_id"] if m else slug(i["label_as_printed"])
    if i["level"] == "component":
        return f"{t}:component:{base}"
    return f"{t}:{base}"


# Renames that the name-similarity rule cannot see, each backed by the same Budget Estimate
# printed under the old name in one budget and under the new name in the next.
SEMANTIC_RENAMES: dict[str, list[tuple[str, str]]] = {
    "css": [
        ("rashtriya swasthya bima yojna", "pradhan mantri jan arogya yojana including rsby"),
        ("pradhan mantri jan arogya yojana including rsby", "rashtriya swasthya bima yojna"),
        ("rashtriya swasthya bima yojna", "prime minister jan aarogya yojana by subsuming rsby"),
        ("integrated child development services", "umbrella icds"),
        ("rashtriya pashudhan vikash yojana", "development programmes animal husbandry"),
        ("digitalization of primary agriculture cooperative societies",
         "computerization of primary agricultural credit societies"),
        ("national rural drinking water mission", "jal jeevan mission jjm national rural drinking water mission"),
        ("mahatma gandhi national rural employment guarantee programme", "mgnrega programme component"),
        ("swachh bharat mission gramin", "sbm grameen"),
        ("pradhan mantri awas yojna pmay urban", "pmay urban"),
        ("swachh bharat mission urban", "swachh bharat mission"),
        ("swachh bharat mission", "swachh bharat mission sbm urban"),
    ],
    "central_sector": [],
}

_STOP = {"of", "and", "the", "for", "in", "to", "on", "a", "an", "scheme", "schemes", "programme", "program"}


def _tokens_of(name: str) -> set[str]:
    return set(normalise_name(name).split()) - _STOP


def _link_names(all_parsed: dict) -> tuple[list[list[tuple]], dict[tuple, list[str]]]:
    """Groups of (scheme_type, budget, normalised name) that are one scheme, and the evidence for each link."""
    budgets = sorted(all_parsed["budgets"])
    parent: dict[tuple, tuple] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    evidence: dict[tuple, list[str]] = defaultdict(list)
    for t in SCHEME_TYPES:
        sem = {(a, b) for a, b in SEMANTIC_RENAMES.get(t, [])}
        by_budget = {}
        for y in budgets:
            e = all_parsed["budgets"][y][t]
            rows = [i for i in (e["parsed"] or {}).get("items", []) if i["level"] == "scheme"
                    and not i.get("ambiguous_name") and "@" not in i["item_id"]]
            by_budget[y] = {normalise_name(i["label_as_printed"]): i for i in rows}
            for n in by_budget[y]:
                find((t, y, n))
        for a, b in zip(budgets, budgets[1:]):
            A, B = by_budget[a], by_budget[b]

            def be(i, yr=a):
                v = i["values"].get((yr, "BE"))
                return v["total"] if v else None
            for n in set(A) & set(B):
                va, vb = be(A[n]), be(B[n])
                if va and vb and abs(va - vb) > 0.5 * max(abs(va), abs(vb)):
                    evidence[(t, b, n)].append(f"name kept but BE {a} changed {va:,.2f} -> {vb:,.2f}: treated as a new scheme")
                    continue
                union((t, a, n), (t, b, n))
            only_a = [n for n in A if n not in B]
            only_b = [n for n in B if n not in A]
            for n in only_a:
                va = be(A[n])
                if not va:
                    continue
                cands = []
                for m in only_b:
                    vb = be(B[m])
                    if vb is None or abs(va - vb) > 0.005:
                        continue
                    ta, tb = _tokens_of(n), _tokens_of(m)
                    jac = len(ta & tb) / max(1, len(ta | tb))
                    if jac >= 0.5 or (n, m) in sem or (len(ta & tb) >= 2 and (ta <= tb or tb <= ta)):
                        cands.append(m)
                if len(cands) == 1:
                    m = cands[0]
                    union((t, a, n), (t, b, m))
                    evidence[(t, b, m)].append(f"BE {a} {va:,.2f} printed as '{A[n]['label_as_printed']}' in "
                                               f"budget {a} and as '{B[m]['label_as_printed']}' in budget {b}")
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for node in list(parent):
        groups[find(node)].append(node)
    return list(groups.values()), evidence


def _name_map_rows(groups: list[list[tuple]], evidence: dict[tuple, list[str]], all_parsed: dict) -> list[dict]:
    """One name-map row per printed name of every group that needs mapping."""
    rows = []
    used_ids: dict[str, int] = defaultdict(int)
    for members in sorted(groups, key=lambda g: (g[0][0], max(m[1] for m in g))):
        names = {m[2] for m in members}
        t = members[0][0]
        latest = max(members, key=lambda m: m[1])
        latest_label = next(i for i in all_parsed["budgets"][latest[1]][t]["parsed"]["items"]
                            if i["level"] == "scheme" and normalise_name(i["label_as_printed"]) == latest[2])["label_as_printed"]
        sid = slug(latest_label)
        used_ids[(t, sid)] += 1
        if used_ids[(t, sid)] > 1:
            sid += f"_{min(m[1] for m in members)[:4]}"
        if len(names) == 1 and all(not evidence.get(m) for m in members) and used_ids[(t, slug(latest_label))] == 1:
            continue  # one unchanged name, nothing to map
        by_name: dict[str, list[str]] = defaultdict(list)
        for m in members:
            by_name[m[2]].append(m[1])
        for n, ys in sorted(by_name.items()):
            label = next(i for i in all_parsed["budgets"][ys[0]][t]["parsed"]["items"]
                         if i["level"] == "scheme" and normalise_name(i["label_as_printed"]) == n)["label_as_printed"]
            ev = "; ".join(e for y in ys for e in evidence.get((t, y, n), []))
            rows.append({"scheme_type": t, "printed_name": label, "budgets": " ".join(sorted(ys)),
                         "scheme_id": sid, "scheme_name": latest_label, "evidence": ev})
    return rows


def build_name_map(all_parsed: dict) -> list[dict]:
    """Propose the scoped name map from the parsed statements (run by hand, then reviewed).

    Two printed names are the same scheme when, in consecutive budgets, one disappears and
    the other appears with the same non-zero BE figure for the year both budgets print, and
    either the names share most words or the pair is listed in SEMANTIC_RENAMES. An
    unchanged name in consecutive budgets is the same scheme unless that shared BE figure
    differs by more than half (then the name changed meaning, e.g. "Swachh Bharat Mission").
    """
    groups, evidence = _link_names(all_parsed)
    return _name_map_rows(groups, evidence, all_parsed)
