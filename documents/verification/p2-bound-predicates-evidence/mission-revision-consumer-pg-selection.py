"""Selection only; existing private runner owns fixture and drain. NO launch on import."""

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path('/home/kali/OmnisAI')
PYTHON = ROOT / 'api/.venv/bin/python'
UV = '/home/kali/.local/share/omnis-toolchains/bin/uv'


def selected_argv(collect_only: bool = False) -> list[str]:
    return [str(PYTHON), '-I', '-B', '-m', 'pytest', '-p', 'pytest_asyncio.plugin',
            '-p', 'no:cacheprovider', '-c', str(ROOT / 'api/pyproject.toml'),
            str(ROOT / 'api/tests/test_contract_method_pg.py'), '-k', 'mission-consumer',
            '-q', '--tb=line', *(['--collect-only'] if collect_only else [])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--review-adjudicated', action='store_true')
    args = parser.parse_args()
    if args.collect_only:
        import os
        import subprocess
        environment = dict(os.environ)
        for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
            environment.pop(key, None)
        environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OMNIS_CONTRACT_METHOD_NATIVE_PG='1')
        return subprocess.call(selected_argv(True), cwd=ROOT, env=environment)
    if not args.review_adjudicated:
        parser.error('Two complementary reviews and parent adjudication required before launch')
    spec = importlib.util.spec_from_file_location('db_gate', ROOT / 'ops/run_test_db_gate.py')
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    actual_gate = runner.run_gate

    def selected_gate(command, environment, log, timeout_seconds):
        return actual_gate(selected_argv(), {**environment, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                                            'OMNIS_CONTRACT_METHOD_NATIVE_PG': '1'}, log, timeout_seconds)

    runner.run_gate = selected_gate
    return runner.prove_private_fixture('test-contract-method-native-pg', UV, 240)


if __name__ == '__main__':
    raise SystemExit(main())
