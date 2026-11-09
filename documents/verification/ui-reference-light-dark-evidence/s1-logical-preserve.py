#!/usr/bin/env python3
"""One attempt, exact installation, logical data proof only; REVIEW BEFORE EXECUTE.

python -I -B <this-file> --check is read-only (no locks, files or fixtures).
After independent review/parent admission only: same command with --execute.
The original installation is NEVER a restore target. No recover/start/reset here.
All partial output and isolated PGDATA survive failure; never automatically retry.
shortcut: local single operator, public-only COPY dump <=128 MiB expanded and
1 GiB archive; stop for review rather than generalize for another installation.
"""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import time

REPO = Path('/home/kali/OmnisAI')
BASE = Path('/home/kali/.local/share/omnis-settings-c-9e51d10')
SOURCE = BASE / 's/omnis'
CLI = BASE / 'cli/lib/python3.13/site-packages/omnis_cli'
OUTPUT = Path('/home/kali/.local/share/omnis-backups/s1-ui-current-3832f3a1')
UV = '/home/kali/.local/share/omnis-toolchains/bin/uv'
TOOL_PATH = '/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin'
INSTANCE = 'd694129b-a3e5-446d-9e5b-fe9bc19abed8'
PROJECT = 'omnis-local-7734af95b492440daeaeb5eea953fdce'
ATTEMPT = '6cd15979-1a8d-4bb9-a121-00fa92e6ca7d'
CIDS = {
    'supervisor': '91ca760a4df7c5c5174258f7e90c22e6d0b68f3c6df438d121276adfe0d02940',
    'api': 'db92db2675f825453a9c0e4c436b1fd47eabb6204cf5b01646b05352962b4772',
    'db': '88fc7e16fa59e76db98caccd1e5e45e8c7fe5b38b5235795be6d343e56508e48',
}
CLI_PIN = '50821094439b42126381dce74049e277d4a04bc916e941cead5889c5a4985eb0'
PINS = {
    'ops/run_test_db_gate.py': '7a65617ebff1628f5f095d3b31c535e25d66108bffdea2765aac5773bc3a4a7d',
    'ops/compose.test.yaml': '88a496df47496a5e079d6f173a07049e123c8cf2758d363b3abe00f8c58ebc4e',
}
JOURNAL_PIN = '879c6ecb3d3e921b435a861b5162cf8d00f3661c79126508b21e82c75a56d1ab'
LIMIT = 1024**3
EXPANDED_LIMIT = 128 * 1024**2
PG_ENV = ('-e', 'PGTZ=UTC', '-e', 'PGOPTIONS=-c DateStyle=ISO -c IntervalStyle=postgres -c extra_float_digits=3 -c bytea_output=hex')
META_SQL = """BEGIN READ ONLY; SET LOCAL statement_timeout=3000;
SELECT json_build_object('schema',(SELECT version_num FROM alembic_version),
'system_id',(SELECT system_identifier::text FROM pg_control_system()),
'owners',(SELECT json_agg(DISTINCT tableowner) FROM pg_tables WHERE schemaname='public'),
'schemas',(SELECT json_agg(nspname ORDER BY nspname) FROM pg_namespace
 WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'),
'largeobjects',(SELECT count(*) FROM pg_largeobject_metadata),
'tables',(SELECT json_agg(relname ORDER BY relname) FROM pg_class
 WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p'))); COMMIT;"""


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def copy_projection(raw):
    require(len(raw) <= EXPANDED_LIMIT, 'EXPANDED_LIMIT')
    tables, sequences, rows, name, columns = {}, [], [], None, ''
    for line in raw.splitlines(keepends=True):
        if name is not None:
            if line == b'\\.\n':
                tables[name] = {'columns': columns, 'count': len(rows),
                                'sha256': sha(b''.join(sorted(rows)))}
                name, rows = None, []
            else:
                require(line.endswith(b'\n'), 'COPY_ROW_INCOMPLETE')
                rows.append(line)
        elif line.startswith(b'COPY '):
            match = re.fullmatch(rb'COPY (public\.[a-z_][a-z_0-9]*) \(([a-z_0-9, ]+)\) FROM stdin;\n', line)
            if match is None:
                raise ValueError('UNSUPPORTED_COPY_HEADER')
            name, columns = (value.decode('ascii') for value in match.groups())
            require(name not in tables, 'DUPLICATE_COPY_TABLE')
        elif line.startswith(b'SELECT pg_catalog.setval('):
            sequences.append(line.decode('ascii'))
    require(name is None and bool(tables), 'INCOMPLETE_COPY')
    return {'tables': tables, 'sequences': sorted(sequences)}


def schema_bytes(raw):
    return b'\n'.join(line for line in raw.splitlines()
                      if not line.startswith((b'\\restrict ', b'\\unrestrict ')))


def cleanup_command(argv, endpoint):
    if len(argv) > 3 and argv[3] == 'rm':
        require(len(argv) == 6 and argv[:3] == ['docker', '--host', endpoint]
                and argv[4] == '-f' and re.fullmatch(r'[0-9a-f]{64}', argv[5])
                and argv[5] not in CIDS.values(), 'CLEANUP_COMMAND_REFUSED')
        return argv[:4] + [argv[5]]  # Preserve the existing attestor, remove only force.
    return argv


def stamp(path, directory=False):
    info = path.lstat()
    require(path.resolve() == path and info.st_uid == os.getuid(), 'PATH_OR_OWNER')
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'FILE_TYPE')
    require(not info.st_mode & 0o002 and (directory or info.st_nlink == 1), 'LINK_OR_MODE')
    fields = ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_mode', 'st_nlink')
    if not directory:
        fields += ('st_size', 'st_mtime_ns', 'st_ctime_ns')
    return [getattr(info, field) for field in fields]


def read(path, limit=EXPANDED_LIMIT):
    before = stamp(path)
    require(before[6] <= limit, 'FILE_LIMIT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        require([info.st_dev, info.st_ino] == before[:2], 'FILE_REPLACED')
        raw = source.read(limit + 1)
    require(len(raw) <= limit and stamp(path) == before, 'FILE_CHANGED')
    return raw


def put(path, raw):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def record(path, value):
    put(path, (json.dumps(value, sort_keys=True) + '\n').encode())


def helpers():
    require(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize,
            'REQUIRE_PYTHON_I_B_NO_OPTIMIZE')
    # Wheel code may be hardlinked; the exact content pin, not link count, binds it.
    tree = ''.join(str(p.relative_to(CLI)) + ':' + sha(p.read_bytes()) + '\n'
                   for p in sorted(CLI.rglob('*.py')))
    require(sha(tree.encode()) == CLI_PIN, 'CLI_INPUT_CHANGED')
    for name, expected in PINS.items():
        require(sha(read(REPO / name, 1024**2)) == expected, 'LIFECYCLE_INPUT_CHANGED')
    sys.path.insert(0, str(CLI.parent))
    from omnis_cli.start_runtime import ControlRuntime
    from omnis_cli.instance import private_dir
    spec = importlib.util.spec_from_file_location('s1_fixture_owner', REPO / 'ops/run_test_db_gate.py')
    if spec is None or spec.loader is None:
        raise ValueError('OWNER_IMPORT')
    owner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = owner
    spec.loader.exec_module(owner)
    private_dir(OUTPUT.parent)
    return ControlRuntime, owner


def source_guard(runtime):
    require(sha(read(SOURCE / 'startup.json', 16384)) == JOURNAL_PIN, 'SOURCE_JOURNAL_CHANGED')
    journal = json.loads(read(SOURCE / 'startup.json', 16384))
    require((journal['format'], journal['phase'], journal['generation'], journal['supervisor_epoch'],
             journal['attempt'], journal['instance_id'], journal['system_id'], journal['project']) ==
            (5, 'READY', 65, 36, ATTEMPT, INSTANCE, '7701260249314795563', PROJECT), 'SOURCE_BINDING')
    require(journal['containers'] == CIDS and runtime.schema == '0019_agent_runs'
            and runtime.release.name == '0.1.2' and runtime.receipt.project == PROJECT
            and runtime.digest == journal['release_digest'], 'RELEASE_BINDING')
    require(set(runtime.ids()) == set(CIDS.values()), 'SOURCE_CONTAINER_SET')
    runtime.attempt = ATTEMPT
    for role, cid in CIDS.items():
        item = runtime.inspect('container', cid)
        require(item is not None, 'SOURCE_MISSING')
        labels, state = item['Config']['Labels'], item['State']
        require(item['Id'] == cid and labels['com.docker.compose.project'] == PROJECT
                and labels['com.docker.compose.service'] == role
                and labels['org.omnis.start-attempt'] == ATTEMPT
                and item['Image'] == (runtime.pg_image if role == 'db' else journal['image_id'])
                and state['Status'] == ('exited' if role == 'supervisor' else 'running')
                and not state['Paused'] and not state['Restarting']
                and item['HostConfig']['RestartPolicy'] == {'Name': 'no', 'MaximumRetryCount': 0},
                'SOURCE_CONTAINER_BINDING')
    runtime.attest(CIDS['db'], 'db', SOURCE, Path(journal['control_dir']), journal['port'])
    master = stamp(SOURCE / 'vault-key/master.key')  # Never open/export the key.
    require(master[:3] == [2049, 4894026, 1000] and master[6] == 32, 'MASTER_METADATA')
    paths = {name: SOURCE / name for name in ('startup.json', 'instance.json', 'vault/vault.json')}
    paths.update({'release-metadata/' + name: path for name, path in {
        'installed.json': BASE / 'd/omnis/installed.json',
        'image.json': BASE / 'd/omnis/image.json',
        'release.json': runtime.release / 'release.json'}.items()})
    directories = {'catalog': stamp(SOURCE / 'catalog', True)}
    for base, names, files in os.walk(SOURCE / 'catalog', followlinks=False):
        for name in names:
            path = Path(base) / name
            directories[str(path.relative_to(SOURCE))] = stamp(path, True)
        for name in files:
            path = Path(base) / name
            paths[str(path.relative_to(SOURCE))] = path
    require(len(paths) == 63, 'CATALOG_INVENTORY_CHANGED')
    files = {name: {'stat': stamp(path), 'sha256': sha(read(path, 8 * 1024**2))}
             for name, path in paths.items()}
    require(sum(entry['stat'][6] for name, entry in files.items() if name.startswith('catalog/')) == 108829,
            'CATALOG_SIZE_CHANGED')
    return {'files': files, 'directories': directories, 'master_stat_only': master,
            'root': stamp(SOURCE, True), 'pgdata_identity': journal['pgdata_identity'],
            'daemon_id': runtime.receipt.docker_id}, paths


def preflight(require_absent=True):
    os.environ['PATH'] = TOOL_PATH
    Runtime, owner = helpers()
    require(OUTPUT.resolve() == OUTPUT and (not require_absent or not os.path.lexists(OUTPUT)),
            'DESTINATION_EXISTS_OR_ALIAS')
    require(shutil.disk_usage(OUTPUT.parent).free >= 4 * LIMIT, 'SPACE_REQUIRED')
    runtime = Runtime(BASE / 'd', time.monotonic() + 60)
    seal, paths = source_guard(runtime)
    for tool in ('pg_dump', 'pg_restore'):
        value = runtime.run('exec', '--user', 'postgres', CIDS['db'], tool, '--version').stdout
        require(value.startswith(tool + ' (PostgreSQL) 18.6 '), 'NATIVE_VERSION')
    result = runtime.run('exec', '--user', 'postgres', CIDS['db'], 'psql', '-X', '-qAt',
                         '-U', 'omnis', '-d', 'omnis', '-v', 'ON_ERROR_STOP=1', '-c', META_SQL)
    meta = json.loads(result.stdout)
    require(meta['schema'] == '0019_agent_runs' and meta['system_id'] == '7701260249314795563'
            and meta['owners'] == ['omnis'] and meta['schemas'] == ['public']
            and meta['largeobjects'] == 0 and len(meta['tables']) == 46, 'DATABASE_SHAPE')
    owner._preflight_gate(UV, 'test-db-contract')
    require(owner._docker_endpoint({'HOME': '/home/kali', 'PATH': TOOL_PATH}) == runtime.host,
            'FIXTURE_DAEMON_ENDPOINT_MISMATCH')
    require(len(os.fsencode(str(OUTPUT / 'r/socket/.s.PGSQL.5432'))) <= 107, 'SOCKET_PATH_LIMIT')
    require(not runtime.uncertain and runtime.family_drained, 'PREFLIGHT_UNSETTLED')
    return runtime, owner, seal, paths, meta


def native_file(runtime, name, args, *, source=None, env=None, cap=90):
    output = OUTPUT / name
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    source_fd = error_fd = None
    try:
        error_fd = os.open(OUTPUT / (name + '.stderr'),
                           os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        if source is not None:
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        result = runtime.run(*args, stdin_fd=source_fd, stdout_fd=fd, env=env,
                             cap=cap, success=False, effect=True)
        os.fsync(fd)
        with os.fdopen(os.dup(error_fd), 'wb') as diagnostics:
            diagnostics.write(result.stderr.encode())
            diagnostics.flush()
            os.fsync(diagnostics.fileno())
        record(OUTPUT / (name + '.exit.json'), {'exit': result.returncode})
        require(result.returncode == 0 and not runtime.uncertain and runtime.family_drained,
                'NATIVE_FAILED_OR_UNSETTLED')
    finally:
        os.close(fd)
        if source_fd is not None:
            os.close(source_fd)
        if error_fd is not None:
            os.close(error_fd)
    return read(output, LIMIT)


def restore():
    Runtime, owner = helpers()
    runtime = Runtime(BASE / 'd', time.monotonic() + 250)
    fixture = Path(os.environ['OMNIS_TEST_FIXTURE'])
    require(fixture == fixture.resolve() == OUTPUT / 'r/fixture.json'
            and json.loads(read(OUTPUT / 'fixture-owner.json', 16384))['fixture'] == str(fixture),
            'RESTORE_FIXTURE_BINDING')
    attested = owner.attest_fixture(fixture)
    manifest = json.loads(read(fixture, 16384))
    cid = attested['container_id']
    require(cid not in CIDS.values() and manifest['daemon_id'] == runtime.receipt.docker_id,
            'RESTORE_DESTINATION')
    saved = json.loads(read(OUTPUT / 'archive-manifest.json', 1024**2))
    for name, digest in saved['hashes'].items():
        require(sha(read(OUTPUT / name, LIMIT)) == digest, 'ARCHIVE_CHANGED')
    record(OUTPUT / 'restore-claim.json', {'one_shot': True, 'fixture': str(fixture), 'cid': cid})
    base = ['exec', '-i', '-e', 'PGPASSWORD', *PG_ENV, cid]
    env = {'PGPASSWORD': os.environ['OMNIS_TEST_DB_PASSWORD']}
    connection = ['-h', '/var/run/postgresql', '-U', 'omnis_test', '-d', 'omnis_test']
    psql = [*base, 'psql', '-X', '-qAt', *connection, '-v', 'ON_ERROR_STOP=1']
    empty = runtime.run(*psql, '-c', "SELECT count(*) FROM pg_tables WHERE schemaname='public'", env=env)
    require(empty.stdout.strip() == '0', 'RESTORE_NOT_EMPTY')
    runtime.run(*psql, '-c', 'CREATE ROLE omnis NOLOGIN', env=env, effect=True)
    native_file(runtime, 'restore.stdout', [*base, 'pg_restore', '--exit-on-error',
                '--single-transaction', *connection], source=OUTPUT / 'database.pgdump', env=env, cap=120)
    data = native_file(runtime, 'restored-data.sql', [*base, 'pg_dump', '--data-only', *connection], env=env)
    require(copy_projection(data) == saved['projection'], 'RESTORED_DATA_MISMATCH')
    schema = native_file(runtime, 'restored-schema.sql', [*base, 'pg_dump', '--schema-only', *connection], env=env)
    require(schema_bytes(schema) == schema_bytes(read(OUTPUT / 'schema.sql')), 'RESTORED_SCHEMA_MISMATCH')
    schema_row = runtime.run(*psql, '-c', 'BEGIN READ ONLY; SELECT version_num FROM alembic_version; COMMIT;', env=env)
    require(schema_row.stdout.strip() == '0019_agent_runs', 'RESTORED_REVISION')
    owner.attest_fixture(fixture)
    record(OUTPUT / 'restored-proof.json', {'verdict': 'ARCHIVE_TO_RESTORED_DATA_MATCH',
           'tables': len(saved['projection']['tables']), 'schema': '0019_agent_runs',
           'fixture': str(fixture), 'cid': cid, 'authority': 'NOT_REUSED',
           'vault_unlock': 'NOT_RUN_MASTER_EXCLUDED', 'domain_readers': 'NOT_RUN',
           'current_live_db_digest_comparison': 'NOT_RUN_NOT_SAME_SNAPSHOT'})


def work():
    runtime, owner, seal, paths, meta = preflight(require_absent=False)
    intent = json.loads(read(OUTPUT / 'intent.json', 1024**2))
    require(intent['source_seal'] == seal and intent['recipe_sha256'] == sha(read(Path(__file__))), 'INTENT_CHANGED')
    record(OUTPUT / 'worker-claim.json', {'one_shot': True})
    runtime.deadline = time.monotonic() + 420
    locks = []
    try:
        for root in (BASE / 'd/omnis', SOURCE):
            path = root / 'lifecycle.lock'
            before = stamp(path)
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            locks.append(fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(stamp(path) == before, 'LOCK_REPLACED')
        require(source_guard(runtime)[0] == seal, 'SOURCE_CHANGED_BEFORE_COPY')
        for name, path in paths.items():
            target = OUTPUT / 'files' / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            raw = read(path, 8 * 1024**2)
            require(sha(raw) == seal['files'][name]['sha256'], 'SOURCE_FILE_CHANGED')
            put(target, raw)
            require(sha(read(target)) == seal['files'][name]['sha256'], 'COPY_MISMATCH')
        base = ['exec', '-i', '--user', 'postgres', *PG_ENV, CIDS['db']]
        archive = native_file(runtime, 'database.pgdump', [*base, 'pg_dump', '-Fc',
                     '--serializable-deferrable', '--lock-wait-timeout=3000', '-U', 'omnis', '-d', 'omnis'], cap=150)
        require(archive.startswith(b'PGDMP'), 'ARCHIVE_FORMAT')
        native_file(runtime, 'archive.list', [*base, 'pg_restore', '--list'], source=OUTPUT / 'database.pgdump')
        schema = native_file(runtime, 'schema.sql', [*base, 'pg_restore', '--schema-only', '--file=-'], source=OUTPUT / 'database.pgdump')
        data = native_file(runtime, 'data.sql', [*base, 'pg_restore', '--data-only', '--file=-'], source=OUTPUT / 'database.pgdump')
        projection = copy_projection(data)
        require(set(projection['tables']) == {'public.' + name for name in meta['tables']}, 'TABLE_COVERAGE')
        require(source_guard(runtime)[0] == seal, 'SOURCE_CHANGED_DURING_DUMP')
        hashes = {'database.pgdump': sha(archive), 'schema.sql': sha(schema), 'data.sql': sha(data)}
        record(OUTPUT / 'archive-manifest.json', {'hashes': hashes, 'projection': projection,
               'source_seal': seal, 'consistency': 'POSTGRES_LOGICAL_SNAPSHOT_PLUS_STABLE_FILES',
               'excluded': ['master.key', 'db-password', '.env', 'live PGDATA', 'runtime IPC', 'logs'],
               'source_authority': 'HISTORICAL_BYTES_NOT_REPLAYABLE'})
        original_gate, original_paths = owner.run_gate, owner.prepare_paths
        original_run = owner._run
        owner._run = lambda argv, env, timeout=20: original_run(
            cleanup_command(argv, runtime.host), env, timeout=timeout)
        def selected(command, env, log, timeout_seconds):
            require(command[:3] == ['make', '--no-print-directory', 'test-db-contract'], 'GATE_SELECTION')
            record(OUTPUT / 'fixture-owner.json', {'log': str(log), 'fixture': env['OMNIS_TEST_FIXTURE']})
            return original_gate([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--restore'],
                                 env, log, timeout_seconds)
        owner.run_gate = selected
        # The existing fresh-root validator is retained; choose a short durable child.
        owner.prepare_paths = lambda requested: original_paths(OUTPUT / 'r')
        os.environ['TMPDIR'] = str(OUTPUT)
        signal.signal(signal.SIGTERM, owner._request_stop)
        signal.signal(signal.SIGINT, owner._request_stop)
        result = owner.prove_private_fixture('test-db-contract', UV, 270)
        require(result == 0 and not owner._STOP_REQUESTED, 'RESTORE_OWNER_OR_CLEANUP_FAILED')
        require(source_guard(runtime)[0] == seal, 'SOURCE_CHANGED_AFTER_RESTORE')
        for name, digest in hashes.items():
            require(sha(read(OUTPUT / name, LIMIT)) == digest, 'ARCHIVE_CHANGED_AFTER_RESTORE')
        record(OUTPUT / 'result.json', {'verdict': 'LOGICAL_RESTORE_VERIFIED_SOURCE_UNCHANGED',
               'source_recovery': 'NOT_RUN', 'same_instance_operational_ready': False,
               'master': 'ORIGINAL_ONLY_METADATA_UNCHANGED', 'retained_pgdata': str(OUTPUT / 'r/data')})
    finally:
        for fd in reversed(locks):
            os.close(fd)


def main(argv):
    require(sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize,
            'REQUIRE_PYTHON_I_B_NO_OPTIMIZE')
    if argv == ['--restore']:
        restore()
    elif argv == ['--work']:
        work()
    elif argv in (['--check'], ['--execute']):
        runtime, owner, seal, paths, meta = preflight()
        if argv == ['--check']:
            print('CHECK_ONLY_OK schema=0019 tables=46 catalog=57 output_absent=true no_writes=true')
            return 0
        os.umask(0o077)
        OUTPUT.mkdir(mode=0o700)
        parent_fd = os.open(OUTPUT.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        record(OUTPUT / 'intent.json', {'source': str(SOURCE), 'source_seal': seal,
               'recipe_sha256': sha(read(Path(__file__))), 'hard_deadline_seconds': 600,
               'no_source_restore': True, 'inverse': 'Only owned fixture cleanup; retain all output; no retry'})
        signal.signal(signal.SIGTERM, owner._request_stop)
        signal.signal(signal.SIGINT, owner._request_stop)
        env = {'HOME': '/home/kali', 'PATH': TOOL_PATH,
               'TMPDIR': '/home/kali/.hermes/cache/scratch'}
        result = owner.run_gate([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--work'],
                                env, OUTPUT / 'operation.log', 600)
        require(result == 0 and (OUTPUT / 'result.json').is_file(), 'OPERATION_NOT_VERIFIED')
        print('LOGICAL_RESTORE_VERIFIED: data proof only; original recovery NOT_RUN')
    else:
        raise ValueError('USE_EXACTLY_CHECK_OR_REVIEWED_EXECUTE')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        # Never expose SQL rows, stderr, credentials or arbitrary exception text.
        print('REFUSED_OR_UNCERTAIN ' + type(error).__name__ + '; retain artifacts; no retry')
        raise SystemExit(4) from None
