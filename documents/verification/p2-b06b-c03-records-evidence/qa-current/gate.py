#!/usr/bin/env python3
"""C03 records QA dispatcher. Inert by default; no build or installation path."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path('/home/kali/OmnisAI')
HERE = Path(__file__).resolve().parent
SHA = re.compile(r'[0-9a-f]{64}')
PACKAGE_FILES = (
    'SKILL.md', 'NOTICE.md', 'omnis.yaml', 'references/methodology.md',
    'templates/procedures/map-records.yaml', 'templates/schemas/records.schema.json',
    'templates/schemas/operations.schema.json', 'templates/schemas/surface_map.schema.json',
    'templates/schemas/empty.schema.json',
)
HELPERS = (
    'ops/run_test_db_gate.py', 'ops/compose.test.yaml', 'ops/Dockerfile.hermes',
    'ops/prepare_hermes_runtime.py', 'api/pyproject.toml', 'api/uv.lock',
    'integrations/hermes/pyproject.toml', 'api/tests/conftest.py',
    'api/tests/fixtures/__init__.py', 'api/tests/fixtures/b06b_publication/__init__.py',
    'api/tests/fixtures/b06b_publication/consumer.py',
    'api/tests/fixtures/b06b_pure_probe/__init__.py',
    'api/tests/fixtures/b06b_pure_probe/consumer.py', 'api/tests/fixtures/c03_records.py',
    'api/tests/fixtures/b06b_composition.py', 'api/tests/fixtures/c03_journey.py',
    'api/tests/fixtures/c03_capture.py', 'api/tests/fixtures/b06a/consumer.py',
    'api/tests/fixtures/b06a_durable/consumer.py', 'profiles/recon-mapping-contract.yaml',
    'profiles/records-mapping-contract.yaml', 'integrations/hermes/pin.json',
    'integrations/hermes/upstream/managed-patch-manifest.json',
    'integrations/hermes/upstream/omnis-managed.patch',
    'skills/recon-mapping-contract/templates/schemas/records.schema.json',
)


def need(ok, label):
    if not ok:
        raise ValueError(label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def data(path, limit=16 * 1024 * 1024, single=False):
    p = Path(path)
    info = p.lstat()
    need(stat.S_ISREG(info.st_mode) and not p.is_symlink(), 'not-regular-file')
    need(not single or info.st_nlink == 1, 'installed-hardlink-refused')
    need(info.st_size <= limit, 'file-limit')
    with p.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'file-limit')
    return raw


def read_json(path):
    def pairs(items):
        need(len({k for k, _ in items}) == len(items), 'duplicate-json-key')
        return dict(items)
    return json.loads(data(path), object_pairs_hook=pairs)


def emit(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def inventory(base):
    # Only these explicitly bounded source subtrees; never inventory the repository/home.
    found = {}
    for p in sorted(base.rglob('*')):
        if '__pycache__' in p.parts or p.suffix == '.pyc' or p.is_dir():
            continue
        found[p.relative_to(base).as_posix()] = digest(data(p))
    return found


def snapshot():
    found = {}
    for prefix in ('api/src/omnis', 'integrations/hermes/src/omnis_hermes',
                   'api/tests/fixtures/b06b_publication/source'):
        found.update({prefix + '/' + k: v for k, v in inventory(ROOT / prefix).items()})
    paths = [*HELPERS, *('skills/records-mapping-contract/' + s for s in PACKAGE_FILES)]
    paths += ['skills/recon-mapping-contract/' + s for s in (
        'SKILL.md', 'omnis.yaml', 'NOTICE.md', 'references/methodology.md',
        'templates/procedures/map-capture.yaml', 'templates/schemas/capture.schema.json',
        'templates/schemas/operations.schema.json', 'templates/schemas/surface_map.schema.json',
        'templates/schemas/empty.schema.json')]
    managed = read_json(ROOT / 'integrations/hermes/upstream/managed-patch-manifest.json')
    for name in managed['files']:
        need(not name.startswith('/') and '..' not in Path(name).parts, 'native-path')
        paths.append('integrations/hermes/upstream/managed-source/' + name)
    for name in paths:
        p = ROOT / name
        # Namespace packages legitimately have no __init__.py.
        if name.endswith('__init__.py') and not p.exists():
            continue
        found[name] = digest(data(p))
    return dict(sorted(found.items()))


def wheel_attest(spec, prefix, source_prefix, source, installed=False):
    wheel = Path(spec['wheel'])
    need(wheel.is_absolute() and not wheel.is_relative_to(ROOT), 'wheel-outside-checkout-required')
    raw = data(wheel, 128 * 1024 * 1024)
    need(digest(raw) == spec['wheel_sha256'], 'wheel-pin')
    with zipfile.ZipFile(wheel) as z:
        members = [n for n in z.namelist() if n.startswith(prefix + '/') and not n.endswith('/')]
        need(len(members) == len(set(members)), 'wheel-duplicate-member')
        expected = {prefix + k[len(source_prefix):]: v for k, v in source.items()
                    if k.startswith(source_prefix + '/')}
        need(set(members) == set(expected), 'wheel-source-inventory')
        for name in members:
            need('..' not in Path(name).parts and not name.startswith('/'), 'wheel-member-path')
            need(z.getinfo(name).file_size <= 16 * 1024 * 1024, 'wheel-member-limit')
            need(digest(z.read(name)) == expected[name], 'source-wheel-bytes')
        if installed:
            site = Path(spec['site_packages'])
            need(site.is_absolute() and site.resolve() == site and not site.is_relative_to(ROOT), 'install-outside-checkout')
            need((site / prefix).resolve() == site / prefix, 'installed-package-symlink')
            actual = inventory(site / prefix)
            need({prefix + '/' + k: v for k, v in actual.items()} == expected, 'install-inventory')
            for name, sha in expected.items():
                need(digest(data(site / name, single=True)) == sha, 'install-bytes')
    return {'wheel_sha256': digest(raw), 'files': expected, 'count': len(expected)}


def history_attest(spec):
    need(spec['source_base'] == '5ccf90af410e14abf5bf5d9e9807a44824323b9b', 'history-base')
    need(digest(data(spec['wheel'])) == spec['wheel_sha256'], 'history-wheel-pin')
    expected = {}
    with zipfile.ZipFile(spec['wheel']) as archive:
        names = [n for n in archive.namelist() if n.startswith('omnis/') and not n.endswith('/')]
        need(len(names) == len(set(names)) == 71, 'history-wheel-count')
        for name in names:
            source = subprocess.run(['git', 'show', spec['source_base'] + ':api/src/' + name],
                                    cwd=ROOT, capture_output=True, timeout=5, check=True).stdout
            expected[name] = digest(source)
            need(digest(archive.read(name)) == expected[name], 'history-source-wheel')
            need(digest(data(Path(spec['site_packages']) / name, single=True)) == expected[name], 'history-install')
    need({'omnis/' + k: v for k, v in inventory(Path(spec['site_packages']) / 'omnis').items()} == expected,
         'history-installed-inventory')
    return {'source_base': spec['source_base'], 'wheel_sha256': spec['wheel_sha256'],
            'files': expected, 'count': len(expected), 'singlelink': True}


def preflight(cfg):
    need(cfg['schema_version'] == 1 and type(cfg['schema_version']) is int, 'config-version')
    need(re.fullmatch('[0-9a-f]{40}', cfg['reviewed_head']) is not None, 'head-format')
    current = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                             capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    need(current == cfg['reviewed_head'], 'head-drift')
    expected = cfg['source_sha256']
    need(expected and all(SHA.fullmatch(s) for s in expected.values()), 'source-pins-required')
    observed = snapshot()
    need(observed == expected, 'reviewed-source-drift')
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', cfg['native_image']) is not None, 'image-id-required')
    api = wheel_attest(cfg['api'], 'omnis', 'api/src/omnis', expected, installed=True)
    adapter = wheel_attest(cfg['adapter'], 'omnis_hermes', 'integrations/hermes/src/omnis_hermes', expected)
    history_api = history_attest(cfg['history_api'])
    acceptance = read_json(cfg['review_acceptance'])
    need(acceptance['snapshot'] == current and acceptance['verdict'] == 'APPROVED_SCOPED', 'review-acceptance')
    for review in acceptance['reports']:
        need(digest(data(review['path'])) == review['sha256'], 'review-report-pin')
    composer = ast.parse(data(ROOT / 'api/src/omnis/modules/tasks/managed_composition.py'))
    pins = {node.targets[0].id: ast.literal_eval(node.value) for node in composer.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'COMPOSER_REVISION'}
    need(pins['COMPOSER_REVISION'] == expected['integrations/hermes/src/omnis_hermes/prompt_bundle.py'], 'composer-pin')
    pin = read_json(ROOT / 'integrations/hermes/pin.json')
    need(pin['commit'] == 'ee5ee84a345204a3b1d6ef6ba1ab747e602867b9', 'native-upstream-pin')
    need(pin['runtime_inference_authorized'] is False, 'no-model-pin')
    managed_prefix = 'integrations/hermes/upstream/'
    need(expected[managed_prefix + 'managed-patch-manifest.json'] == pin['managed_patch_manifest_sha256'], 'managed-manifest-pin')
    need(expected[managed_prefix + 'omnis-managed.patch'] == pin['managed_patch_sha256'], 'managed-patch-pin')
    managed = read_json(ROOT / managed_prefix / 'managed-patch-manifest.json')
    need(managed['base_commit'] == pin['commit'], 'managed-base-pin')
    need(all(expected[managed_prefix + 'managed-source/' + name] == item['patched_sha256']
             for name, item in managed['files'].items()), 'managed-source-pins')
    need(Path(cfg['api']['python']).is_absolute()
         and not Path(cfg['api']['python']).is_relative_to(ROOT), 'installed-python-required')
    history = cfg.get('history_material', [])
    need(len(history) <= 3, 'history-limit')
    labels = [h['label'] for h in history]
    need(len(labels) == len(set(labels)) and set(labels) <= {'wire1', 'composition1', 'capture2'}, 'history-labels')
    for h in history:
        p = Path(h['path'])
        need(p.is_relative_to(HERE) and p.is_absolute(), 'history-new-owned-copy-required')
        need(digest(data(p)) == h['sha256'], 'history-copy-pin')
    return {'status': 'ATTESTED_OFFLINE_ONLY', 'reviewed_head': current,
            'source_sha256': observed, 'api': api, 'adapter': adapter, 'history_api': history_api,
            'review_acceptance_sha256': digest(data(cfg['review_acceptance'])),
            'native_image': cfg['native_image'], 'upstream_commit': pin['commit'],
            'composer_revision': pins['COMPOSER_REVISION']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--snapshot', action='store_true', help='read-only source hashes, no product imports')
    parser.add_argument('--authorize-final-qa', action='store_true', help='ONLY after new explicit parent dispatch')
    args = parser.parse_args()
    if args.snapshot:
        need(not args.authorize_final_qa, 'incompatible-modes')
        print(json.dumps(snapshot(), indent=2))
        return 0
    if not args.authorize_final_qa:
        print(json.dumps({'status': 'NOT_RUN', 'reason': 'explicit-final-QA-dispatch-required'}))
        return 0
    need(args.config is not None, 'config-required')
    os.umask(0o077)
    cfg = read_json(args.config)
    need(cfg['parent_dispatch'] == 'FINAL_C03_RECORDS_QA_AFTER_REVIEWS', 'dispatch-required')
    need(cfg['docker_slot_exclusive'] is True, 'parent-serial-Docker-slot-required')
    # One shot: never reuse a failed run or silently retry a settled/uncertain resource.
    run = HERE / 'run'
    run.mkdir(mode=0o700)
    attestation = preflight(cfg)
    emit(run / 'attestation.json', attestation)
    emit(run / 'config.json', cfg)
    (run / 'home').mkdir(mode=0o700)
    (run / 'tmp').mkdir(mode=0o700)
    tools = Path(cfg['tools'])
    need(all((tools / n).is_file() for n in ('uv', 'node', 'npm')), 'toolchain-required')
    os.environ.clear()
    os.environ.update(HOME=str(run / 'home'), TMPDIR=str(run / 'tmp'),
                      PATH=f'{tools}:/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8')
    probe = subprocess.run([cfg['api']['python'], '-I', '-B', '-c',
                            'import json,omnis,platform;print(json.dumps({"origin":omnis.__file__,"python":platform.python_version()}))'],
                           cwd=run, env=dict(os.environ), capture_output=True, text=True, timeout=15)
    need(probe.returncode == 0 and not probe.stderr, 'installed-import-prerequisite')
    observed = json.loads(probe.stdout)
    need(observed == {'origin': str(Path(cfg['api']['site_packages']) / 'omnis/__init__.py'),
                      'python': '3.13.15'}, 'installed-consumer-origin-pin')
    emit(run / 'installed-origin.json', observed)
    # The dedicated existing owner alone owns the DB and descendant-family lifecycle.
    spec = importlib.util.spec_from_file_location('c03_existing_runner', ROOT / 'ops/run_test_db_gate.py')
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    original = runner.run_gate
    def journey(argv, env, log, timeout):
        need(argv[2] == 'test-c03-pg', 'gate-target')
        emit(run / 'runner-locator.json', {'log': str(log), 'family_receipt': str(log) + '.result.json'})
        result = original([str(ROOT / 'api/.venv/bin/python'), '-I', '-B', str(HERE / 'journey.py')],
                          env, log, timeout)
        outcome = read_json(run / 'journey-report.json') if (run / 'journey-report.json').exists() else None
        if (outcome is None or outcome.get('uncertain') is not False
                or outcome.get('status') not in ('FAIL', 'SCENARIOS_PASS_AWAITING_GATE_TEARDOWN')):
            raise runner.GateCleanupUncertain('Unsettled installed/native journey; preserve DB')
        return result
    setattr(runner, 'run_gate', journey)
    signal.signal(signal.SIGTERM, runner._request_stop)
    signal.signal(signal.SIGINT, runner._request_stop)
    code = runner.prove_private_fixture('test-c03-pg', str(tools / 'uv'), 900)
    emit(run / 'gate-exit.json', {'exit': code, 'scope': 'TARGETED_INSTALLED_NATIVE_NOT_CANONICAL'})
    outcome = read_json(run / 'journey-report.json') if (run / 'journey-report.json').exists() else {}
    source_unchanged = snapshot() == cfg['source_sha256']
    final_artifacts_unchanged = False
    if source_unchanged:
        final_artifacts_unchanged = preflight(cfg) == attestation
    passed = (code == 0 and outcome.get('status') == 'SCENARIOS_PASS_AWAITING_GATE_TEARDOWN'
              and outcome.get('uncertain') is False and outcome.get('per_test_database_dropped') is True
              and outcome.get('domain_effect_status') == 'NO_UNRECONCILED_STAGE_OBSERVED'
              and source_unchanged and final_artifacts_unchanged)
    emit(run / 'final.json', {'status': 'PASS_SCOPED' if passed else 'NOT_PASS',
                            'gate_exit': code, 'source_unchanged': source_unchanged,
                            'final_artifacts_unchanged': final_artifacts_unchanged,
                            'history_material_status': outcome.get('historical_material_status', 'NOT_RUN'),
                            'scope': 'TARGETED_INSTALLED_NATIVE_NOT_CANONICAL',
                            'criteria_pass': sum(c['status'] == 'PASS' for c in outcome.get('criteria', [])),
                            'criteria_fail': sum(c['status'] == 'FAIL' for c in outcome.get('criteria', [])),
                            'journey_report': str(run / 'journey-report.json'),
                            'limits': outcome.get('limits', [])})
    return 0 if passed else (code or 2)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)
