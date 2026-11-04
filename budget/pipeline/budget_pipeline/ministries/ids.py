"""Stable department ids across renames, through the reviewed name map (data_maps/ministry_names.csv)."""

from __future__ import annotations

import csv
import re

from ..parse import ParseError
from .common import NAME_MAP


def _map_key(name: str) -> str:
    """Strip list markers ('a.', 'aa.', '(iii)', '(1)') and normalise spaces for map lookup."""
    s = re.sub(r"^(\(?[ivx]+\)|\(\d+\)|[a-z]{1,2}\.)\s+", "", name.strip())
    return re.sub(r"\s+", " ", s).strip()


def load_name_map() -> list[dict]:
    with NAME_MAP.open() as f:
        return list(csv.DictReader(f))


def lookup(name: str, budget: str, name_map: list[dict]) -> dict:
    key = _map_key(name)
    hits = [
        r for r in name_map
        if r["printed_name"] == key
        and (not r["budget_from"] or r["budget_from"] <= budget)
        and (not r["budget_to"] or budget <= r["budget_to"])
    ]
    if len(hits) != 1:
        raise KeyError(f"Budget {budget}: printed name {key!r} has {len(hits)} entries in {NAME_MAP.name}")
    return hits[0]


def assign_ids(budget: str, parsed: dict, name_map: list[dict]) -> None:
    """Give every line a stable id. Fails loudly if a printed name is not in the map."""
    for it in parsed["items"]:
        if it["level"] == "grand_total":
            it["item_id"] = "grand_total"
            continue
        if it["level"] == "subtotal":
            it["item_id"] = "subtotal:" + re.sub(r"[^a-z0-9]+", "_", _map_key(it["name"]).lower()).strip("_")
            continue
        row = lookup(it["name"], budget, name_map)
        prefix = "state_plans:" if it["level"] == "state_plan_assistance" else ""
        it["item_id"] = prefix + row["department_id"]
        it["department_name"] = row["department_name"]
        it["ministry_id"] = row["ministry_id"]
        it["ministry_name"] = row["ministry_name"]
    ids = [it["item_id"] for it in parsed["items"] if it["level"] not in ("subtotal",)]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ParseError(f"Budget {budget}: the same id appears twice: {sorted(dupes)}")
