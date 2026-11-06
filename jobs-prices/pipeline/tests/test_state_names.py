"""state_key against the spellings shared with the site's stateKey (shared/fixtures/state-names.json), so the
two rules, kept in step by hand, cannot drift apart."""

import json
from pathlib import Path

from jobs_prices_pipeline.checks.states import state_key

FIXTURE = Path(__file__).resolve().parents[3] / "shared" / "fixtures" / "state-names.json"


def test_state_key_matches_the_shared_fixture():
    names = json.loads(FIXTURE.read_text(encoding="utf-8"))["names"]
    assert len(names) > 10
    for name, key in names.items():
        assert state_key(name) == key, name
