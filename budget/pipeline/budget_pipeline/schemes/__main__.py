"""Run the scheme checks on their own: uv run python -m budget_pipeline.schemes [-v]"""

import csv
import sys

from . import ROOT, checks, load_all

data = load_all()
obs_path = ROOT / "data" / "observations.csv"
with obs_path.open() as f:
    summary = list(csv.DictReader(f))
failed = False
for title, n, fails, notes in checks(data, summary):
    print(f"{'FAIL' if fails else 'ok  '} {title}: {n} checks, {len(fails)} failures")
    for x in fails[:15]:
        print("   x", x)
    if "-v" in sys.argv:
        for x in notes[:40]:
            print("   -", x)
    failed |= bool(fails)
sys.exit(1 if failed else 0)
