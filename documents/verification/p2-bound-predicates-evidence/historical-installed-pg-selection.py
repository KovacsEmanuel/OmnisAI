"""Selection only; original private runner owns fixture and family."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/kali/OmnisAI')
PYTHON = ROOT / 'api/.venv/bin/python'
UV = '/home/kali/.local/share/omnis-toolchains/bin/uv'
PREREQUISITES = '/home/kali/.hermes/cache/scratch/h01-h02-installed-3913234cdfbd/prerequisites.json'
REVIEWED = '54dfc960f32e59197eab64c214b4b56fc455adf5b46d26a8c3c849c773aa050f'


def selected_argv(collect_only=False):
    return [str(PYTHON), '-I', '-B', '-m', 'pytest', '-p', 'pytest_asyncio.plugin',
            '-p', 'no:cacheprovider', '-c', str(ROOT / 'api/pyproject.toml'),
            str(ROOT / 'api/tests/test_contract_method_pg.py'), '-k', 'historical-installed',
            '-q', '--tb=line', *(['--collect-only'] if collect_only else [])]


def environment(base):
    return {**base, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
            'OMNIS_CONTRACT_METHOD_NATIVE_PG': '1',
            'OMNIS_HISTORY_PREREQUISITES': PREREQUISITES,
            'OMNIS_HISTORY_REVIEWED': REVIEWED}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--review-adjudicated', action='store_true')
    args = parser.parse_args()
    if args.collect_only:
        clean = {k:v for k,v in os.environ.items() if k not in
                 ('PYTHONPATH','PYTHONHOME','MYPYPATH','PYTEST_ADDOPTS','PYTEST_PLUGINS')}
        return subprocess.call(selected_argv(True), cwd=ROOT, env=environment(clean))
    if not args.review_adjudicated:
        parser.error('Two exact complementary reviews and parent adjudication required')
    spec = importlib.util.spec_from_file_location('db_gate', ROOT / 'ops/run_test_db_gate.py')
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    original_gate = runner.run_gate
    def selected_gate(command, base, log, timeout_seconds):
        return original_gate(selected_argv(), environment(base), log, timeout_seconds)
    setattr(runner, 'run_gate', selected_gate)
    return runner.prove_private_fixture('test-contract-method-native-pg', UV, 240)


if __name__ == '__main__':
    raise SystemExit(main())
