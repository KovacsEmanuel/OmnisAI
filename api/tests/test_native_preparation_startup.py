"""Optional preparation must not load catalog source hashing during P0 imports."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module",
    ["omnis.api", "omnis.supervisor.runtime_client", "omnis.supervisor.__main__"],
)
def test_ordinary_import_is_catalog_free(module: str) -> None:
    source = Path(__file__).resolve().parents[1] / "src"
    script = """
import importlib, sys
sys.path.insert(0, sys.argv[1])
class RefuseCatalog:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'omnis.modules.settings.candidate_catalog':
            raise ImportError('optional catalog imported on no-opt-in startup')
sys.meta_path.insert(0, RefuseCatalog())
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'omnis.api':
    assert module.create_app().routes
assert 'omnis.modules.settings.candidate_catalog' not in sys.modules
print('NO_OPT_IN_IMPORT_PASS')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source), module],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_OPT_IN_IMPORT_PASS"
