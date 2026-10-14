"""One H03 node; the existing private runner owns DB and family."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/kali/OmnisAI')
PYTHON = ROOT / 'api/.venv/bin/python'
UV = '/home/kali/.local/share/omnis-toolchains/bin/uv'
REVIEWED = '66a6e037062306c8b9def41461d023c87ec307e33b493ef8ebf0cb94169d885d'
ARTIFACT = Path('/home/kali/.hermes/cache/scratch/jsonschema-packaging-c19198cc5fa9474cb9f0f507d11f84c7/h03-artifact.json')
ARTIFACT_SHA = '2eb29fc2d45210390caf0ba5037d590f2cc9adbcf2e3d80bce7e60bbe5ed32c1'
API_PREREQUISITES = '/home/kali/.hermes/cache/scratch/h01-h02-installed-3913234cdfbd/prerequisites.json'


def selected_argv(case, collect_only=False):
    node = str(ROOT / 'api/tests/test_contract_method_pg.py') + '::test_contract_method_real_native_pg_owner_receipts_check_inbox[' + case + ']'
    return [str(PYTHON), '-I', '-B', '-m', 'pytest', '-p', 'pytest_asyncio.plugin',
            '-p', 'no:cacheprovider', '-c', str(ROOT / 'api/pyproject.toml'), node,
            '-q', '--tb=line', '--basetemp=/home/kali/.hermes/cache/scratch/jsonschema-h03-66a-attempt1-' + case, *(['--collect-only'] if collect_only else [])]


def environment(base):
    return {**{k: v for k, v in base.items() if k not in
               ('PYTHONPATH', 'PYTHONHOME', 'MYPYPATH', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS')},
            'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
            'OMNIS_CONTRACT_METHOD_NATIVE_PG': '1',
            'OMNIS_H03_ARTIFACT': str(ARTIFACT),
            'OMNIS_H03_ARTIFACT_SHA': ARTIFACT_SHA,
            'OMNIS_H03_API_PREREQUISITES': API_PREREQUISITES,
            'OMNIS_H03_NORMATIVE_REVIEWED': REVIEWED,
            'OMNIS_H03_INPUT_REVIEWED': REVIEWED}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=('runtime-restart', 'runtime-restart-no-final'))
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--review-adjudicated', action='store_true')
    args = parser.parse_args()
    if hashlib.sha256((ROOT / 'api/tests/test_contract_method_pg.py').read_bytes()).hexdigest() != REVIEWED:
        parser.error('Exact SOURCE snapshot changed; existing reviews cannot authorize it')
    if hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() != ARTIFACT_SHA:
        parser.error('Exact installed artifact receipt changed')
    if args.collect_only:
        return subprocess.call(selected_argv(args.case, True), cwd=ROOT, env=environment(os.environ))
    if not args.review_adjudicated:
        parser.error('Parent adjudication of both exact complementary re-reviews required')
    spec = importlib.util.spec_from_file_location('db_gate', ROOT / 'ops/run_test_db_gate.py')
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    original_gate = runner.run_gate
    def selected_gate(command, base, log, timeout_seconds):
        return original_gate(selected_argv(args.case), environment(base), log, timeout_seconds)
    setattr(runner, 'run_gate', selected_gate)
    return runner.prove_private_fixture('test-contract-method-native-pg', UV, 240)


if __name__ == '__main__':
    raise SystemExit(main())
