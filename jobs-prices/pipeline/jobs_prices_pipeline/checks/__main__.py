"""Run the checks on the downloaded files: uv run python -m jobs_prices_pipeline.checks"""

import sys

from pipeline_common import log as pipeline_log

from . import main

pipeline_log.setup(__package__)
sys.exit(main())
