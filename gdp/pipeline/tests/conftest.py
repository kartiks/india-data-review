import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def fingerprint() -> dict[str, str]:
    """SHA-256 of every file in gdp/data/ and sources/manifest.json."""
    files = sorted((ROOT / "data").glob("*")) + [ROOT / "sources" / "manifest.json"]
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}


@pytest.fixture(autouse=True, scope="session")
def committed_files_untouched():
    """Tests must not write the committed data (the validation report is the site's build gate): they write to
    tmp_path. Fails the run if any test changed gdp/data/ or the manifest."""
    before = fingerprint()
    yield
    changed = sorted(k for k, v in fingerprint().items() if before.get(k) != v)
    assert not changed, f"tests changed committed files: {changed}"
