"""Run the checks on the downloaded files: uv run python -m jobs_prices_pipeline.checks"""

import sys

from . import main

sys.exit(main())
