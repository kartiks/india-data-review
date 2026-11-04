"""Parse every Receipts table and run the tax checks: uv run python -m budget_pipeline.taxes"""

from . import checks, load_all, load_summary_observations

data = load_all()
for b, info in sorted(data["budgets"].items()):
    p = info["parsed"]
    print(b, info["primary"], " ".join(f"{c.kind}:{c.fiscal_year}" for c in p["columns"]), len(p["items"]), "items")
    for u in p["unknown_rows"]:
        print("   ", u)
for title, checked, failures, notes in checks(data, load_summary_observations()):
    print(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
    for f in failures:
        print("   -", f)
