"""Run the scheme checks on their own: uv run python -m budget_pipeline.schemes [-v]"""

import argparse
import csv
import logging
import sys

from pipeline_common import log as pipeline_log

from . import ROOT, checks, load_all

log = logging.getLogger(__name__)

pipeline_log.setup(__package__)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("-v", "--verbose", action="store_true", help="also list each group's notes")
verbose = p.parse_args().verbose
data = load_all()
obs_path = ROOT / "data" / "observations.csv"
with obs_path.open() as f:
    summary = list(csv.DictReader(f))
failed = False
for title, n, fails, notes in checks(data, summary):
    log.info(f"{'FAIL' if fails else 'ok  '} {title}: {n} checks, {len(fails)} failures")
    for x in fails[:15]:
        log.info(f"   x {x}")
    if verbose:
        for x in notes[:40]:
            log.info(f"   - {x}")
    failed |= bool(fails)
sys.exit(1 if failed else 0)
