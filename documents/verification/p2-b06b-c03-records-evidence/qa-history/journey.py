#!/usr/bin/env python3
"""Bounded derivative of the historical C03 journey, fresh artifacts/resources only.
Executed ONLY by gate.py inside the unchanged private PG/family runner.
"""
import asyncio
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tarfile
import time
import traceback
from contextlib import contextmanager
from uuid import uuid4

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
Q = HERE / 'run'
R = Path('/home/kali/OmnisAI')
if not (Q / 'config.json').is_file() or 'OMNIS_TEST_FIXTURE' not in os.environ:
    print(json.dumps({'status': 'NOT_RUN', 'reason': 'existing-runner-required'}))
    raise SystemExit(2)
CFG = json.loads((Q / 'config.json').read_text())
ATTEST = json.loads((Q / 'attestation.json').read_text())
NEW = Path(CFG['api']['python'])
OLD = Path(CFG['history_api']['python'])
I = CFG['native_image']
sys.path[:0] = [CFG['api']['site_packages'], str(R / 'api/tests')]
import omnis
assert Path(omnis.__file__).is_relative_to(Path(CFG['api']['site_packages']))
from conftest import empty_database_url, verify_test_database, connect_test_database
from fixtures.b06b_publication.consumer import canonical, strict_json, confirmed, publish_request
from fixtures.b06b_pure_probe.consumer import Probe
from fixtures.c03_records import EVALUATION_VALUE, qualify_records, records_seed
from fixtures.b06b_composition import new_two_skill_seed, qualify_two
from fixtures.c03_journey import qualify_capture, publish_capture
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.tasks.managed_composition import stage_payload
from omnis.modules.runs.managed_admission import ManagedAdmission
from sqlalchemy import text

os.umask(0o077)
os.environ['OMNIS_B06B_INSTALLED'] = '1'
os.environ['OMNIS_B06B_PYTHON'] = str(NEW)
report = {'status': 'RUNNING', 'reviewed_head': CFG['reviewed_head'], 'criteria': [],
          'commands': [], 'cleanup': [], 'uncertain': False, 'public_artifacts': {},
          'domain_stage_effects': [], 'domain_effect_status': 'NO_UNRECONCILED_STAGE_OBSERVED',
          'limits': ['TARGETED QA, not canonical or browser QA',
                     'No model/provider/target/personal profile/r1 access',
                     'Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO',
                     'Historical graphs newly authored by pinned OLD CLI; no historical DB adopted',
                     'No physical crash/transaction-overlap proof or exhaustive native mutations',
                     'No independent evaluator-call observer: byte-stable replay is not execution census']}


def save():
    (Q / 'journey-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')


def check(key, condition, **fields):
    report['criteria'].append({'id': key, 'status': 'PASS' if condition else 'FAIL', **fields})
    save()
    if not condition:
        raise AssertionError(key)


def snap(name, value):
    p = Q / (name + '.json')
    raw = canonical(value)
    p.write_bytes(raw)
    return {'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest()}


# Reuse the fixture transport, recording only public command identity/results.
from fixtures.b06b_publication.consumer import Seed
_seed_invoke, _seed_confirm = Seed.invoke, Seed.confirm


def seed_invoke(self, operation, request, database_url, **kwargs):
    started = time.monotonic()
    try:
        result = _seed_invoke(self, operation, request, database_url, **kwargs)
    except subprocess.TimeoutExpired:
        report['uncertain'] = True
        save()
        raise
    entry = {'python': os.environ['OMNIS_B06B_PYTHON'],
             'module': result.args[result.args.index('-m') + 1], 'operation': operation,
             'exit': result.returncode, 'seconds': time.monotonic() - started}
    if result.returncode == 2:
        diagnostic = strict_json(result.stderr)
        reason = diagnostic.get('reason')
        if type(reason) is str and re.fullmatch(r'[A-Z][A-Z0-9_]+', reason):
            entry['reason'] = reason
    if result.returncode not in (0, 2):
        report['uncertain'] = True
    report['commands'].append(entry)
    save()
    return result


def seed_confirm(self, request, database_url, answer='yes'):
    try:
        result, transcript = _seed_confirm(self, request, database_url, answer)
    except BaseException:
        report['uncertain'] = True
        save()
        raise
    report['commands'].append({'python': os.environ['OMNIS_B06B_PYTHON'],
                               'module': 'omnis.modules.settings.catalog_publication',
                               'operation': 'confirm', 'exit': result.returncode,
                               'real_pty': True, 'transcript_retained': False})
    save()
    return result, transcript


Seed.invoke, Seed.confirm = seed_invoke, seed_confirm


def cli(seed, module, operation, value, dsn, control=None, expected=0, raw=None, python=None):
    request = seed.directory / ('request-qa-' + uuid4().hex + '.json')
    request.write_bytes(canonical(value) if raw is None else raw)
    argv = [str(python or NEW), '-I', '-B', '-m', module]
    if operation:
        argv.append(operation)
    argv += ['--request', str(request)]
    if control:
        argv += ['--control-dir', str(control)]
    elif module.endswith(('contract_inputs', 'managed_admission')):
        argv += ['--catalog-root', str(seed.root)]
    start = time.monotonic()
    try:
        result = subprocess.run(argv, cwd=seed.directory, env=seed.environment(dsn),
                                capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        report['uncertain'] = True
        save()
        raise
    entry = {'python': str(python or NEW), 'module': module, 'operation': operation, 'exit': result.returncode,
             'seconds': time.monotonic() - start}
    report['commands'].append(entry)
    save()
    if result.returncode not in (0, 2):
        report['uncertain'] = True
        save()
    if result.returncode == 2:
        denied = strict_json(result.stderr)
        if set(denied) == {'status', 'reason'} and denied['status'] == 'BLOCKED':
            reason = denied['reason']
            if type(reason) is str and re.fullmatch(r'[A-Z][A-Z0-9_]+', reason):
                entry['reason'] = reason
                if reason in {'TASK_INDETERMINATE', 'CONTROL_TIMEOUT'}:
                    report['uncertain'] = True
                save()
        if module == D and expected == 0:
            back = asyncio.run(bound_read(dsn, value))
            report['failed_task_readback'] = snap('failed-task-readback', back)
            if back['stage_started'] is True and back['binding_ref'] is None:
                report['domain_effect_status'] = 'UNRECONCILED'
                report['domain_stage_effects'].append({
                    'command_id': value['command_id'], 'status': 'UNRECONCILED',
                    'stage_started': True, 'binding_ref': None,
                    'reason': entry.get('reason', 'UNKNOWN'),
                    'resource_family_settlement_is_separate': True})
            save()
    assert result.returncode == expected, 'CLI exit mismatch'
    assert not (result.stderr if expected == 0 else result.stdout), 'contradictory CLI output'
    output = strict_json(result.stdout if expected == 0 else result.stderr)
    if expected:
        assert set(output) == {'status', 'reason'} and output['status'] == 'BLOCKED'
        reason = output['reason']
        assert type(reason) is str and re.fullmatch(r'[A-Z][A-Z0-9_]+', reason)
        assert reason not in {'DATABASE_UNAVAILABLE', 'INPUT_UNAVAILABLE', 'INVALID_ARGUMENTS', 'UNSAFE_FILE'}
        entry['reason'] = reason
        save()
    return output


C = 'omnis.modules.runs.contract_inputs'
M = 'omnis.modules.runs.managed_admission'
N = 'omnis.modules.runs.native_preparation'
D = 'omnis.supervisor.native_tasks'


def ident(seed):
    return {'schema_version': 1, 'owner_id': seed.owner, 'command_id': str(uuid4())}


def readreq(value):
    return {'schema_version': 1, **{k: value[k] for k in ('owner_id', 'command_id')}}


def reference(value):
    return {k: value[k] for k in ('kind', 'id', 'revision', 'digest')}


def stable(value):
    return {k: v for k, v in value.items() if k != 'created'}


async def current(dsn):
    engine = database_engine(dsn)
    try:
        return await InstanceService(engine).status()
    finally:
        await engine.dispose()


async def graph(dsn, owner, run):
    from omnis.modules.tasks import managed_store
    engine = database_engine(dsn)
    try:
        async with engine.begin() as conn:
            return await managed_store.graph(conn, owner, run)
    finally:
        await engine.dispose()


async def bound_read(dsn, request):
    engine = database_engine(dsn)
    try:
        return await ManagedAdmission(engine).readback(readreq(request))
    finally:
        await engine.dispose()


async def owner_state(dsn, owner):
    engine = database_engine(dsn)
    try:
        async with engine.begin() as conn:
            records = list((await conn.execute(text(
                'SELECT envelope FROM managed_record WHERE owner_id=:owner ORDER BY id'),
                {'owner': owner})).scalars())
            runs = list((await conn.execute(text(
                'SELECT to_jsonb(r) FROM managed_run r WHERE owner_id=:owner ORDER BY command_id'),
                {'owner': owner})).scalars())
            return canonical({'records': records, 'runs': runs})
    finally:
        await engine.dispose()


def docker(*argv, raw=False, input=None, timeout=30):
    try:
        return subprocess.run(['docker', *argv], capture_output=True,
                              text=not raw, input=input, timeout=timeout, check=False,
                              env={'HOME': os.environ['HOME'], 'PATH': '/usr/bin:/bin'})
    except subprocess.TimeoutExpired:
        report['uncertain'] = True
        save()
        raise


def native_bytes(cid):
    """Static image files only. Never read/copy runtime mounts or bootstrap receipts."""
    expected = {'/opt/hermes/venv/lib/python3.13/site-packages/' + n: sha
                for n, sha in ATTEST['adapter']['files'].items()}
    prefix = 'integrations/hermes/upstream/managed-source/'
    expected.update({'/opt/hermes/source/' + n[len(prefix):]: sha
                     for n, sha in ATTEST['source_sha256'].items() if n.startswith(prefix)})
    observed = {}
    for name, sha in expected.items():
        result = docker('cp', cid + ':' + name, '-', raw=True)
        assert result.returncode == 0 and len(result.stdout) < 4 * 1024 * 1024, 'native static file read'
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:*') as archive:
            files = archive.getmembers()
            assert len(files) == 1 and files[0].isfile() and files[0].size < 2 * 1024 * 1024
            source = archive.extractfile(files[0])
            assert source is not None
            digest = hashlib.sha256(source.read()).hexdigest()
            assert digest == sha, 'native file pin mismatch'
            observed[name] = digest
    check('NATIVE_IMAGE_BYTES', observed == expected, image=I,
          snapshot=snap('native-image-files-' + cid[:12], observed))


def native_validate(cid, wire):
    # Installed finite validator only: no AIAgent/RPC launch/qualification and no grant refresh.
    code = ('import json,sys;from omnis_hermes.managed_admission_contract import validate_stage;'
            'v=json.load(sys.stdin);m=validate_stage(v);'
            'print(json.dumps({"kind":m["kind"],"id":m["id"],"revision":m["revision"],"digest":m["digest"]}))')
    result = docker('exec', '-i', cid, '/opt/hermes/venv/bin/python', '-I', '-B', '-c', code,
                    input=canonical(wire).decode(), timeout=15)
    assert result.returncode == 0 and result.stderr == '', 'installed native validator'
    return strict_json(result.stdout)


def attest_container(cid, name, rt, state):
    result = docker('inspect', cid)
    assert result.returncode == 0, 'owned native inspect'
    value = json.loads(result.stdout)[0]
    host = value['HostConfig']
    assert value['Id'] == cid and value['Image'] == I
    assert value['Config']['Labels']['org.omnis.c03.records.qa'] == name
    assert value['Config']['User'] == f'{os.getuid()}:{os.getgid()}'
    assert host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True
    assert host['Privileged'] is False and host['CapDrop'] == ['ALL'] and not host['CapAdd']
    assert host['PidsLimit'] == 128 and host['Memory'] == 768 * 1024 * 1024
    assert host['PidMode'] in ('', None) and host['IpcMode'] in ('private', '', None)
    assert set(value['NetworkSettings']['Networks']) <= {'none'}
    assert host['SecurityOpt'] in (['no-new-privileges:true'], ['no-new-privileges'])
    assert not host['PortBindings'] and not value['NetworkSettings']['Ports']
    mounts = {(m['Type'], m['Source'], m['Destination'], m['RW']) for m in value['Mounts']}
    assert len(value['Mounts']) == 2 and mounts == {
        ('bind', str(rt), '/runtime', True), ('bind', str(state), '/state', True)}
    expected_env = {'HERMES_OMNIS_INERT': '1', 'HERMES_DISABLE_LAZY_INSTALLS': '1',
                    'HERMES_SKIP_NODE_BOOTSTRAP': '1', 'HERMES_MANAGED_DIR': '/state/managed-empty',
                    'HOME': '/state/os-home', 'HERMES_HOME': '/state/active',
                    'CODEX_HOME': '/state/codex', 'TMPDIR': '/state/tmp'}
    env = dict(s.split('=', 1) for s in value['Config']['Env'])
    assert all(env.get(k) == v for k, v in expected_env.items()), 'inert image environment'
    return value


def start_supervisor(seed, dsn, runtime_dir, control, log, python=None):
    environment = {**seed.environment(dsn), 'OMNIS_CONTROL_DIR': str(control),
                   'OMNIS_RUNTIME_DIR': str(runtime_dir), 'OMNIS_RUNTIME_INERT_PROBE': '1',
                   'OMNIS_NATIVE_PREPARATION_CATALOG_ROOT': str(seed.root), 'OMNIS_MANAGED_TASKS': '1'}
    process = subprocess.Popen([str(python or NEW), '-I', '-B', '-m', 'omnis.supervisor'],
                               cwd=seed.directory, env=environment, stdout=subprocess.PIPE,
                               stderr=log, start_new_session=True)
    report['commands'].append({'python': str(python or NEW), 'module': 'omnis.supervisor',
                               'operation': 'start', 'pid': process.pid})
    save()
    deadline = time.monotonic() + 20
    raw = b''
    try:
        while time.monotonic() < deadline:
            assert process.poll() is None, 'supervisor early exit'
            if select.select([process.stdout], [], [], 0.1)[0]:
                raw += os.read(process.stdout.fileno(), 4096 - len(raw))
                assert len(raw) < 4096, 'supervisor output bound'
                if b'SUPERVISOR_READY\n' in raw:
                    return process
        raise AssertionError('supervisor READY deadline')
    except BaseException:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            report['uncertain'] = True
            save()
            # Existing enclosing family owner is the rescue authority.
        raise


@contextmanager
def runtime(seed, dsn, tag, python=None):
    base = Q / tag
    base.mkdir(mode=0o700)
    rt, control, state = (base / s for s in ('r', 'c', 's'))
    for path in (rt, control, state):
        path.mkdir(mode=0o700)
    for name in ('active', 'work', 'os-home', 'codex', 'tmp', 'managed-empty',
                 'xdg/config', 'xdg/cache', 'xdg/state', 'xdg/data'):
        (state / name).mkdir(parents=True, mode=0o700)
    name = 'omnis-c03r-' + uuid4().hex
    intent = {'name': name, 'label': name, 'image': I, 'root': str(base),
              'before': 'fresh roots/no adopted container',
              'inverse': 'join supervisor; attest/stop/rm exact owned CID; preserve state/images'}
    snap(tag + '-intent', intent)
    cid, process = None, None
    clean = {'tag': tag, 'errors': []}
    log = (base / 'supervisor-private.log').open('xb')
    try:
        result = docker('create', '--name', name, '--label', 'org.omnis.c03.records.qa=' + name,
                        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                        '--security-opt', 'no-new-privileges:true', '--pids-limit', '128',
                        '--memory', '768m', '--user', f'{os.getuid()}:{os.getgid()}',
                        '--mount', f'type=bind,src={rt},dst=/runtime',
                        '--mount', f'type=bind,src={state},dst=/state', I)
        assert result.returncode == 0, 'native create'
        cid = result.stdout.strip()
        assert re.fullmatch('[0-9a-f]{64}', cid)
        intent['cid'] = cid
        snap(tag + '-intent', intent)
        attest_container(cid, name, rt, state)
        native_bytes(cid)
        assert docker('start', cid).returncode == 0, 'native start'
        deadline = time.monotonic() + 15
        while not (rt / 'runtime.sock').exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (rt / 'runtime.sock').is_socket(), 'native runtime socket'
        process = start_supervisor(seed, dsn, rt, control, log, python)
        yield control, asyncio.run(current(dsn)), cid
    finally:
        # Attempt each exact owned cleanup independently. Never convert rescue to PASS.
        if process is not None:
            try:
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                process.wait(timeout=12)
                clean['supervisor_exit'] = process.returncode
            except BaseException as exc:
                clean['errors'].append('supervisor:' + type(exc).__name__)
                report['uncertain'] = True
        log.close()
        if cid is None:
            # Missing create ACK is uncertainty, not permission to adopt a named container.
            report['uncertain'] = True
            clean['errors'].append('no-pinned-native-CID')
        elif process is None or process.poll() is not None:
            try:
                value = attest_container(cid, name, rt, state)
                if value['State']['Running']:
                    assert docker('stop', '-t', '3', cid).returncode == 0
                assert docker('rm', cid).returncode == 0
                result = docker('inspect', cid)
                clean.update(cid=cid, exact_cid_absent=result.returncode == 1 and 'No such object' in result.stderr)
            except BaseException as exc:
                clean['errors'].append('native:' + type(exc).__name__)
                report['uncertain'] = True
        else:
            clean['errors'].append('unsettled-supervisor-native-preserved')
        clean.update(control_socket_absent=not os.path.lexists(control / 'control.sock'),
                     runtime_socket_absent=not os.path.lexists(rt / 'runtime.sock'),
                     workers_absent=not list((state / 'tmp').glob('native-prep-*')))
        report['cleanup'].append(clean)
        save()
        assert not clean['errors'] and clean.get('supervisor_exit') == 0
        assert all(clean.get(k) is True for k in ('exact_cid_absent', 'control_socket_absent',
                                                 'runtime_socket_absent', 'workers_absent'))


def preparation(seed, selected, dsn, control, instance, python=None, tag='native'):
    request = {**ident(seed), 'instance_id': str(instance.instance_id),
               'expected_generation': instance.generation, 'expected_epoch': instance.supervisor_epoch,
               'selection_ref': selected['selection_ref']}
    prepared = cli(seed, N, 'prepare', request, dsn, control, python=python)
    back = cli(seed, N, 'readback', readreq(request), dsn, python=python)
    check(tag + '_NATIVE_PREPARATION', prepared['preparation_status'] == 'PREPARED'
          and back['receipt']['payload']['loader_result']['loader'] == 'tools.skills_tool.skill_view',
          receipt_ref=prepared['receipt_ref'], snapshot=snap(tag + '-preparation', back))
    return request


def prepare_case(seed, selected, pre, dsn, value, tag, assign=True):
    creq = {**ident(seed), 'schema_version': 2, 'selection_ref': selected['selection_ref'],
            'preparation_command_id': pre['command_id']}
    ctx = cli(seed, C, 'create-context', creq, dsn)
    prefix = asyncio.run(graph(dsn, seed.owner, ctx['run_ref']['id']))
    bundle = next(r for r in prefix if r['kind'] == 'prompt-bundle')
    check(tag + '_METADATA_BEFORE_BRIEF', not any(r['kind'] == 'task-brief' for r in prefix)
          and 'brief_ref' not in bundle['payload'])
    ireq = {**ident(seed), 'schema_version': 2, 'context_ref': ctx['context_ref'], 'input': value}
    inp = cli(seed, C, 'create-input', ireq, dsn)
    iback = cli(seed, C, 'read-input', readreq(ireq), dsn)
    assert iback['input']['payload']['value'] == value
    assert iback['context']['payload']['namespace'] == 'RUN'
    assert iback['context']['payload']['version'] == 2
    req = {**ident(seed), 'schema_version': 3, 'selection_ref': selected['selection_ref'],
           'preparation_command_id': pre['command_id'], 'task_count': 1,
           'context_ref': ctx['context_ref'], 'slot_values': [{'slot_name': 'records', 'refs': [inp['input_ref']]}]}
    if not assign:
        return {'creq': creq, 'ctx': ctx, 'ireq': ireq, 'inp': inp, 'iback': iback, 'req': req}
    made = cli(seed, M, 'prepare-composed', req, dsn)
    sections = json.loads(next(r for r in made['records'] if r['kind'] == 'prompt-composition')['payload']['text'])
    bound = next(r for r in made['records'] if r['kind'] == 'bound-procedure')['payload']['resolved_procedure']
    check(tag + '_COMPOSITION', sections[4]['version'] == 2 and sections[4]['input'] == iback['input']
          and sections[4]['input']['payload']['value'] == value and bound['slots'] == []
          and len(bound['probe']) == 2
          and bound['probe'][0]['input_bindings'] == [{'name': 'records', 'source_ref': inp['input_ref'], 'selector': 'records'}]
          and bound['probe'][1]['input_bindings'] == [{'name': 'operations', 'source_ref': {'kind': 'STEP_OUTPUT', 'step_id': bound['probe'][0]['id'], 'output_name': 'operations'}, 'selector': None}]
          and [x['required'] for x in made['briefs'][0]['payload']['method_plan']['requirements']] == [True, True, False]
          and made['briefs'][0]['payload']['prompt_bundle_ref'] == reference(bundle),
          snapshot=snap(tag + '-prepared', made), input_ref=inp['input_ref'])
    schema_bytes = base64.b64decode(sections[4]['schema']['source_b64'], validate=True)
    authority = json.loads((R / 'skills/recon-mapping-contract/templates/schemas/records.schema.json').read_bytes())
    check(tag + '_AUTHORITATIVE_SCHEMA', json.loads(schema_bytes) == authority)
    wire = stage_payload(made['manifest'], made['records'])
    assert wire['protocol'] == 'omnis-managed-admission-v3'
    assert made['manifest']['payload']['composition_version'] == 3
    snap(tag + '-stage', wire)
    return {'creq': creq, 'ctx': ctx, 'ireq': ireq, 'inp': inp, 'iback': iback,
            'req': req, 'made': made, 'sections': sections, 'wire': wire}


def release_case(seed, case, dsn, control, instance, tag):
    request, made = case['req'], case['made']
    command = {**readreq(request), 'op': 'native_task', 'instance_id': str(instance.instance_id),
               'expected_generation': instance.generation, 'expected_epoch': instance.supervisor_epoch,
               'manifest_ref': made['manifest_ref'], 'action': 'stage'}
    start = time.monotonic()
    staged = cli(seed, D, None, command, dsn, control)
    # Installed service readback is warm/in-process to avoid spending the short stage lease on CLI startup.
    bound = asyncio.run(bound_read(dsn, request))
    assert bound['binding_ref'] == staged['binding_ref'] and not bound['results'] and not bound['checks']
    case['binding_before_release'] = bound['binding']
    released = cli(seed, D, None, {**command, 'action': 'release'}, dsn, control)
    check(tag + '_NATIVE_BIND_RELEASE', released['task_status'] == 'BLOCKED',
          seconds=time.monotonic() - start, binding_ref=bound['binding_ref'],
          snapshot=snap(tag + '-committed-before-release', bound))
    blocked = cli(seed, M, 'readback', readreq(request), dsn)
    receipt = next(r for r in blocked['records'] if r['kind'] == 'native-task-receipt')
    check(tag + '_NO_MODEL_INCOMPLETE', receipt['payload']['reason'] == 'NO_MODEL'
          and blocked['results'][0]['payload']['status'] == 'BLOCKED'
          and blocked['results'][0]['payload']['consumed_input_refs'] == []
          and blocked['checks'][0]['payload']['status'] == 'INCOMPLETE'
          and all(not x['turn_completed'] and not x['admitted'] for x in blocked['inbox']),
          snapshot=snap(tag + '-blocked', blocked))
    cli(seed, D, None, {**command, 'action': 'release'}, dsn, control)
    assert cli(seed, M, 'readback', readreq(request), dsn) == blocked
    consumed = cli(seed, M, 'reconcile', readreq(request), dsn)
    check(tag + '_RECONCILE_REPLAY', cli(seed, M, 'reconcile', readreq(request), dsn) == consumed
          and all(x['domain_result_consumed'] and not x['turn_completed'] for x in consumed['inbox']))
    case['terminal'] = consumed


def denials(seed, case, evaluation, dsn):
    # UNASSIGNED context reaches resolver guards; valid binding follows all negatives.
    req, inp = case['req'], case['inp']
    slot = req['slot_values'][0]
    variants = [
        ('missing-slot', {**req, 'slot_values': []}, 'MANAGED_REJECTED'),
        ('duplicate-slot', {**req, 'slot_values': [slot, slot]}, 'MANAGED_REJECTED'),
        ('unknown-slot', {**req, 'slot_values': [{**slot, 'slot_name': 'unknown'}]}, 'MANAGED_REJECTED'),
        ('zero-ref', {**req, 'slot_values': [{**slot, 'refs': []}]}, 'MANAGED_REJECTED'),
        ('two-ref', {**req, 'slot_values': [{**slot, 'refs': [inp['input_ref'], inp['input_ref']]}]}, 'MANAGED_REJECTED'),
        ('package-eval-in-run', {**req, 'slot_values': [{**slot, 'refs': [evaluation['input_ref']]}]}, None),
        ('foreign-owner', {**req, 'owner_id': str(uuid4())}, None),
        ('digest', {**req, 'context_ref': {**case['ctx']['context_ref'], 'digest': 'a' * 64}}, None),
        ('bool-revision', {**req, 'context_ref': {**case['ctx']['context_ref'], 'revision': True}}, None),
        ('capture-wire-version', {**req, 'schema_version': 2}, None),
        ('capture-ref-kind', {**req, 'slot_values': [{**slot, 'refs': [{**inp['input_ref'], 'kind': 'contract-case-input'}]}]}, None),
    ]
    for label, request, reason in variants:
        request = {**request, 'command_id': str(uuid4())}
        before = asyncio.run(owner_state(dsn, seed.owner))
        denied = cli(seed, M, 'prepare-composed', request, dsn, expected=2)
        check('DENY_' + label, (reason is None or denied['reason'] == reason)
              and denied['reason'] != 'CONTEXT_ALREADY_ASSIGNED'
              and asyncio.run(owner_state(dsn, seed.owner)) == before, reason=denied['reason'],
              reason_oracle='exact' if reason else 'bounded-domain-refusal; exact reason observed')
    row = {'method': 'GET', 'path': '/valid', 'status': 200}
    bad_values = [('missing', {}), ('extra', {'records': [], 'extra': 1}),
                  ('type', {'records': 'not-array'}), ('capture', {'capture': '[]'}),
                  ('method', {'records': [{**row, 'method': 'TRACE'}]}),
                  ('path-space', {'records': [{**row, 'path': '/bad path'}]}),
                  ('path-backslash', {'records': [{**row, 'path': '/bad\\path'}]}),
                  ('status-bool', {'records': [{**row, 'status': True}]}),
                  ('status-range', {'records': [{**row, 'status': 600}]}),
                  ('129', {'records': [row] * 129}),
                  ('control', {'records': [{**row, 'path': '/bad\u0080'}]})]
    for label, value in bad_values:
        request = {**case['ireq'], 'command_id': str(uuid4()), 'input': value}
        before = asyncio.run(owner_state(dsn, seed.owner))
        denied = cli(seed, C, 'create-input', request, dsn, expected=2)
        expected_reason = 'INVALID_JSON' if label == '129' else 'INVALID_CASE_INPUT'
        check('DENY_INPUT_' + label, denied['reason'] == expected_reason
              and asyncio.run(owner_state(dsn, seed.owner)) == before, reason=denied['reason'])
    for label, raw in [('BOM', b'\xef\xbb\xbf' + canonical(case['ireq'])),
                       ('UTF8', b'\xff' + canonical(case['ireq']))]:
        before = asyncio.run(owner_state(dsn, seed.owner))
        denied = cli(seed, C, 'create-input', case['ireq'], dsn, expected=2, raw=raw)
        check('DENY_ENCODING_' + label, denied['reason'] == 'INVALID_JSON'
              and asyncio.run(owner_state(dsn, seed.owner)) == before)
    conflict = {**case['ireq'], 'input': {'records': []}}
    before = asyncio.run(owner_state(dsn, seed.owner))
    denied = cli(seed, C, 'create-input', conflict, dsn, expected=2)
    check('DENY_COMMAND_CONFLICT', denied['reason'] == 'COMMAND_CONFLICT'
          and asyncio.run(owner_state(dsn, seed.owner)) == before)
    case['made'] = cli(seed, M, 'prepare-composed', req, dsn)
    check('VALID_BIND_AND_REPLAY_AFTER_DENIALS', stable(cli(seed, C, 'create-input', case['ireq'], dsn)) == stable(inp)
          and stable(cli(seed, M, 'prepare-composed', req, dsn)) == stable(case['made']))


def history_material(cid):
    supplied = CFG.get('history_material', [])
    for item in supplied:
        raw = Path(item['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        value = json.loads(raw)
        # Shape: {manifest: RecordEnvelope, records: [...], stage: original frozen wire}.
        assert set(value) == {'manifest', 'records', 'stage'}
        expected_version = {'wire1': None, 'composition1': 1, 'capture2': 2}[item['label']]
        assert value['manifest']['payload'].get('composition_version') == expected_version
        rebuilt = stage_payload(value['manifest'], value['records'])
        check('HISTORY_MATERIAL_' + item['label'], rebuilt == value['stage']
              and native_validate(cid, rebuilt) == reference(value['manifest']),
              source_sha256=item['sha256'], limit='receive-only installed validators; no eligibility or DB replay')
        assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() == item['sha256']
    report['historical_material_status'] = ('CHECKED_SUPPLIED_ONLY' if supplied else 'NOT_RUN_MISSING_FRESH_EXPORTS')
    save()


async def lexical_state(dsn, seed, review_request):
    engine = database_engine(dsn)
    try:
        async with engine.connect() as conn:
            review = (await conn.execute(text(
                'SELECT result FROM catalog_command WHERE owner_id=:owner AND command_id=:command'),
                {'owner': seed.owner, 'command': review_request['command_id']})).scalar_one()
            counts = {kind: int((await conn.execute(text(
                'SELECT count(*) FROM catalog_record WHERE owner_id=:owner AND kind=:kind'),
                {'owner': seed.owner, 'kind': kind})).scalar_one()) for kind in (
                    'candidate-snapshot', 'evaluation-admission', 'evaluation-receipt',
                    'contract-input-context', 'contract-case-records')}
            return review, counts
    finally:
        await engine.dispose()


def lexical_schema(dsn):
    # R2-F01 at the actual installed catalog review/admission/evaluation boundary.
    lexical_owner = str(uuid4())
    for label, suffix, accepted in [('CR', b'\r', False), ('CRLF', b'\r\n', False),
                                    ('LF', b'\n', True), ('TAB', b'\t', True)]:
        original = records_seed(Q / ('lexical-' + label))
        seed = Seed(original.directory, original.package, original.profile, original.root, lexical_owner)
        path = seed.package / 'templates/schemas/records.schema.json'
        raw = path.read_bytes() + suffix
        path.write_bytes(raw)
        captured = seed.success('capture', seed.capture(), dsn, candidate=True)
        refs = {k: captured[k] for k in ('draft_ref', 'source_draft_refs')}
        request = seed.write(**refs)
        result = seed.invoke('review', request, dsn, candidate=True)
        assert result.returncode == (0 if accepted else 2)
        if accepted:
            assert not result.stderr
            review = strict_json(result.stdout)
            frozen = seed.success('freeze', seed.write(**refs, technical_review_ref=review['technical_review_ref']), dsn, candidate=True)
            admitted = seed.success('admit-evaluation-records', seed.write(schema_version=3,
                snapshot_ref=frozen['snapshot_ref'], value={'records': []}), dsn, candidate=True)
            evaluated = seed.success('evaluate', seed.write(schema_version=3,
                snapshot_ref=frozen['snapshot_ref'], input_ref=admitted['input_ref'], evaluation_kind='PURE'), dsn, candidate=True)
            check('R2_F01_' + label, base64.b64decode(admitted['material']['schema']['source_b64']) == raw
                  and evaluated['status'] == 'PURE_PASS'
                  and [json.loads(v) for v in evaluated['outputs']] == [{'operations': []}, {'surface_map': []}],
                  snapshot=snap('lexical-' + label, {'admitted': admitted, 'evaluated': evaluated}))
        else:
            assert not result.stdout
            assert strict_json(result.stderr) == {'status': 'BLOCKED', 'reason': 'INVALID_CASE_INPUT'}
            review, before = asyncio.run(lexical_state(dsn, seed, request))
            result = seed.invoke('freeze', seed.write(**refs, technical_review_ref=review['technical_review_ref']), dsn, candidate=True)
            assert result.returncode == 2 and not result.stdout
            check('R2_F01_' + label, not any(before.values())
                  and asyncio.run(lexical_state(dsn, seed, request))[1] == before
                  and path.read_bytes() == raw, review_reason='INVALID_CASE_INPUT',
                  freeze_reason=strict_json(result.stderr)['reason'], no_qualified_records=before)


def historical_database(dsn):
    # Only fresh fixture sources/data. OLD writes, then NEW receives existing records.
    os.environ['OMNIS_B06B_PYTHON'] = str(OLD)
    history = []
    legacy = new_two_skill_seed()
    qualified = qualify_two(legacy, dsn)
    publication = legacy.success('publish', publish_request(qualified, confirmed(qualified, dsn)), dsn)
    published = legacy.success('snapshot', legacy.write(publication_ref=publication['publication_ref']), dsn)
    probe = Probe(legacy.directory, legacy.package, legacy.profile, legacy.root, legacy.owner)
    selected = probe.success('select', probe.write(snapshot_ref=published['snapshot_ref'], recipe_key='publication-probe'), dsn)
    check('HISTORY_OLD_REAL_SLOTLESS_QUALIFICATION', qualified.static['status'] == 'STATIC_PASS'
          and qualified.pure['status'] == 'PURE_PASS', snapshot=snap('history-slotless-qualification',
          {'static': qualified.static, 'pure': qualified.pure, 'publication': publication}))
    with runtime(legacy, dsn, 'history-slotless', python=OLD) as (control, instance, cid):
        pre = preparation(legacy, selected, dsn, control, instance, python=OLD, tag='history-slotless')
        for operation, version in [('prepare', None), ('prepare-composed', 1)]:
            request = {**ident(legacy), 'selection_ref': selected['selection_ref'],
                       'preparation_command_id': pre['command_id'], 'task_count': 1}
            made = cli(legacy, M, operation, request, dsn, python=OLD)
            back = cli(legacy, M, 'readback', readreq(request), dsn, python=OLD)
            check('HISTORY_OLD_' + operation, stable(made) == back
                  and back['manifest']['payload'].get('composition_version') == version,
                  snapshot=snap('history-old-' + operation, back))
            history.append((legacy, operation, request, back, None))
    qualified, evaluation = qualify_capture(Path(os.environ['TMPDIR']) / 'history-capture-source', dsn)
    capture = qualified.seed
    publication, published = publish_capture(qualified, dsn)
    probe = Probe(capture.directory, capture.package, capture.profile, capture.root, capture.owner)
    selected = probe.success('select', probe.write(snapshot_ref=published['snapshot_ref'], recipe_key='capture-mapper'), dsn)
    check('HISTORY_OLD_REAL_CAPTURE_QUALIFICATION', qualified.static['status'] == 'STATIC_PASS'
          and qualified.pure['status'] == 'PURE_PASS', snapshot=snap('history-capture-qualification',
          {'static': qualified.static, 'pure': qualified.pure, 'admission': evaluation, 'publication': publication}))
    with runtime(capture, dsn, 'history-capture', python=OLD) as (control, instance, cid):
        pre = preparation(capture, selected, dsn, control, instance, python=OLD, tag='history-capture')
        creq = {**ident(capture), 'selection_ref': selected['selection_ref'], 'preparation_command_id': pre['command_id']}
        context = cli(capture, C, 'create-context', creq, dsn, python=OLD)
        ireq = {**ident(capture), 'context_ref': context['context_ref'],
                'input': {'capture': '[{"method":"POST","path":"/prior-synthetic-run","status":201}]'}}
        inp = cli(capture, C, 'create-input', ireq, dsn, python=OLD)
        iback = cli(capture, C, 'read-input', readreq(ireq), dsn, python=OLD)
        request = {**ident(capture), 'schema_version': 2, 'selection_ref': selected['selection_ref'],
                   'preparation_command_id': pre['command_id'], 'task_count': 1,
                   'context_ref': context['context_ref'], 'slot_values': [{'slot_name': 'capture', 'refs': [inp['input_ref']]}]}
        made = cli(capture, M, 'prepare-composed', request, dsn, python=OLD)
        back = cli(capture, M, 'readback', readreq(request), dsn, python=OLD)
        check('HISTORY_OLD_CAPTURE2', stable(made) == back
              and back['manifest']['payload']['composition_version'] == 2,
              snapshot=snap('history-old-capture2', back))
        history.append((capture, 'prepare-composed', request, back, (ireq, iback)))
    os.environ['OMNIS_B06B_PYTHON'] = str(NEW)
    # No NEW select/evaluate/prepare with a new command ID is permitted here.
    for index, (seed, operation, request, old, input_pair) in enumerate(history):
        before = asyncio.run(owner_state(dsn, seed.owner))
        got = cli(seed, M, 'readback', readreq(request), dsn)
        replay = cli(seed, M, operation, request, dsn)
        reconciliation = cli(seed, M, 'reconcile', readreq(request), dsn, expected=2)
        check('HISTORY_UNSTAGED_RECONCILE_DENIED_' + str(index),
              reconciliation['reason'] == 'NEEDS_RECONCILIATION'
              and asyncio.run(owner_state(dsn, seed.owner)) == before)
        check('HISTORY_NEW_READBACK_REPLAY_' + str(index), got == old and stable(replay) == old
              and asyncio.run(owner_state(dsn, seed.owner)) == before
              and not got['binding_ref'] and not got['results'] and not got['checks'],
              old_sha256=hashlib.sha256(canonical(old)).hexdigest(),
              snapshot=snap('history-new-' + str(index), got))
        if input_pair:
            ireq, iback = input_pair
            check('HISTORY_NEW_CAPTURE_INPUT', cli(seed, C, 'read-input', readreq(ireq), dsn) == iback)
    with runtime(capture, dsn, 'history-readback') as (control, instance, cid):
        for index, (seed, operation, request, old, input_pair) in enumerate(history):
            check('HISTORY_NEW_RESTART_' + str(index), cli(seed, M, 'readback', readreq(request), dsn) == old
                  and stable(cli(seed, M, operation, request, dsn)) == old)
    report['historical_material_status'] = 'GENUINE_OLD_TO_NEW_DATABASE_READBACK_REPLAY_3'
    save()


def main(url):
    dsn = url.render_as_string(hide_password=False)
    identity = verify_test_database(url.set(database='omnis_test'))
    # Installed migrations, not the checkout alembic fixture.
    cwd = Q / 'migration-home'
    cwd.mkdir(mode=0o700)
    result = subprocess.run([str(NEW), '-I', '-B', '-m', 'omnis.migrate', '--initialize'], cwd=cwd,
                            env={'PATH': '/usr/bin:/bin', 'HOME': str(cwd), 'TMPDIR': str(cwd),
                                 'OMNIS_DATABASE_URL': dsn, 'OMNIS_EXPECTED_SYSTEM_ID': identity.system_identifier},
                            capture_output=True, text=True, timeout=30, check=False)
    check('INSTALLED_MIGRATION', result.returncode == 0, exit=result.returncode)
    # Final narrowed frontier: genuine history only; all prior assertions retained.
    historical_database(dsn)
    report['status'] = 'SCENARIOS_PASS_AWAITING_GATE_TEARDOWN'
    save()


database = None
try:
    try:
        with contextmanager(empty_database_url.__wrapped__)() as database:
            report['per_test_database'] = database.database
            identity = verify_test_database(database.set(database='omnis_test'))
            report['pg_fixture'] = identity.model_dump()
            save()
            main(database)
    finally:
        # Independent connection after the existing DROP finalizer, not an inference.
        if database is not None and report['uncertain'] is False:
            with connect_test_database(database.set(database='omnis_test'), autocommit=True) as conn:
                observed = conn.execute(
                    'SELECT datname FROM pg_database WHERE datname IN (%s, %s) ORDER BY datname',
                    ('omnis_test', database.database)).fetchall()
            absent = observed == [('omnis_test',)]
            report['per_test_database_dropped'] = absent
            report['post_drop_readback'] = {
                'database': database.database, 'exists': not absent,
                'administrative_database_observed': ('omnis_test',) in observed,
                'independent_connection': True}
            save()
            assert absent, 'per-test database still present after fixture unwind'
        else:
            report['per_test_database_dropped'] = None
            report['post_drop_readback'] = {'status': 'NOT_RUN_UNSETTLED_OR_NO_DATABASE'}
            save()
except BaseException as exc:
    report['status'] = 'FAIL'
    report['error'] = {'type': type(exc).__name__, 'frames': [
        {'file': f.filename, 'line': f.lineno, 'function': f.name}
        for f in traceback.extract_tb(exc.__traceback__)]}
    # Never emit exception args, raw traceback, DB URL, bootstrap receipt or environment.
    save()
    raise SystemExit(1)
print(json.dumps({'status': report['status'], 'report': str(Q / 'journey-report.json')}))
