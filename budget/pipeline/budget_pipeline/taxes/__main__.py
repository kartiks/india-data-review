"""Parse every Receipts table and run the tax checks: uv run python -m budget_pipeline.taxes"""

import argparse
import logging

from pipeline_common import log as pipeline_log

from . import checks, load_all, load_summary_observations

log = logging.getLogger(__name__)

pipeline_log.setup(__package__)
argparse.ArgumentParser(description=__doc__).parse_args()
data = load_all()
for b, info in sorted(data["budgets"].items()):
    p = info["parsed"]
    log.info(f"{b} {info['primary']} {' '.join(f'{c.kind}:{c.fiscal_year}' for c in p['columns'])} "
             f"{len(p['items'])} items")
    for u in p["unknown_rows"]:
        log.info(f"    {u}")
for title, checked, failures, _notes in checks(data, load_summary_observations()):
    log.info(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
    for f in failures:
        log.info(f"   - {f}")
