#!/usr/bin/env python3
"""One-off CRASH_CONSISTENT preservation; never a cold STOPPED receipt.

Only --check (read-only) or --execute; no source/destination/SQL overrides.
Execution requires two independent reviews of these exact bytes first.
Retain every partial artifact and PGDATA on nonzero; never auto-retry.
shortcut: 1 GiB and local single-operator Docker, reconsider for larger/remote storage.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import tarfile
import time

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "cli/src"))
from omnis_cli.backup import archive, digest, private_bytes, validate_tar, ARCHIVE_LIMIT
from omnis_cli.instance import load_instance, private_dir
from omnis_cli.lifecycle import StartError, lifecycle_lock, remaining
from omnis_cli.release import _put, _sync_dir
from omnis_cli.start_runtime import ControlRuntime, private_identity, refuse_upgrade

BASE = Path('/home/kali/.local/share/omnis-settings-c-9e51d10')
SOURCE = BASE / 's/omnis'
DATA = BASE / 'd'
OUTPUT = Path('/home/kali/.local/share/omnis-backups/t1-crash-preservation-20261031-r2')
QUERIES = Path('/home/kali/.local/share/omnis-backups/t1-finalization-20261029T194541Z/comparison-queries.json')
QUERY_SHA = 'a85fdef4700f455f51af9afdf80df1f4136732aabb3aebc00e880d42c440cff2'
JOURNAL_SHA = '3e88e9e6e8a87a3186031dad173ccbb9bd36822c6bb078c684ad97c7ff34e264'
INSTANCE = 'd694129b-a3e5-446d-9e5b-fe9bc19abed8'
SYSTEM = '7701260249314795563'
PROJECT = 'omnis-local-7734af95b492440daeaeb5eea953fdce'
CONTAINERS = {
    'db': '12a60dacb788e4818ca85208436cced99b5fc3a5784be7cb102a79676f9ecc77',
    'api': '01af3c9361d6b924dcd7f8f6fe3a37e2333002f505fa452e54913ef968f528e4',
    'supervisor': 'df6b1ab2fe2e07e1e26486e9928a6513268eb1cc0e974c5771ba4ac2935ce9d0',
}
HELPERS = {
    'backup.py': '59a23420b11d64f04483b0b902b95a75f392f07fbd4c0ed8edd35ff4cfaad1a8',
    'lifecycle.py': '2b3b08b97d09da2a0f5a5a408044757e4b7dd145665b2a227752dec4aae84562',
    'release.py': 'a406d3d7dc416eaf9b53d68be467d246695d38bd8d48c5bbad631bda29bbe9e4',
    'start_runtime.py': '83d8daf87d8023d7eba72fa62a60b461d72ceee9cd63f265b1c27525342c298f',
}
COPY = {'startup.json': 16384, 'instance.json': 4096, 'db-password': 64,
        'vault/vault.json': 8 * 1024 * 1024}


def require(condition, reason):
    if not condition:
        raise StartError(reason, 4)


def stamp(path, *, directory=False):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'UNSAFE_TYPE')
    if not directory:
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1, 'UNSAFE_FILE')
    fields = ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_mode', 'st_nlink')
    if not directory:
        fields += ('st_size', 'st_mtime_ns', 'st_ctime_ns')
    return [getattr(info, field) for field in fields]


def original_containers(runtime, record):
    require(set(runtime.ids()) == set(CONTAINERS.values()), 'SOURCE_CONTAINER_SET_CHANGED')
    for role, cid in CONTAINERS.items():
        item = runtime.inspect('container', cid)
        require(isinstance(item, dict), 'SOURCE_CONTAINER_MISSING')
        state, host = item['State'], item['HostConfig']
        labels = item['Config']['Labels']
        require(item['Id'] == cid and labels['com.docker.compose.project'] == PROJECT
                and labels['com.docker.compose.service'] == role
                and labels['org.omnis.start-attempt'] == record['attempt']
                and item['Image'] == (runtime.pg_image if role == 'db' else record['image_id'])
                and state['Status'] == 'exited' and state['Running'] is False
                and state['Pid'] == 0 and state['Paused'] is False
                and state['Restarting'] is False
                and host['RestartPolicy'] == {'Name': 'no', 'MaximumRetryCount': 0},
                'SOURCE_NOT_EXITED_EXACT')
    runtime.attest(CONTAINERS['db'], 'db', SOURCE, Path(record['control_dir']), record['port'])
    # Observe foreign resources only; their names never authorize an effect.
    ids = runtime.run('ps', '-a', '--no-trunc', '--format', '{{.ID}}').stdout.splitlines()
    require(len(ids) <= 1000 and len(set(ids)) == len(ids), 'CONTAINER_INVENTORY_LIMIT')
    for cid in ids:
        require(re.fullmatch(r'[0-9a-f]{64}', cid), 'CONTAINER_ID_INVALID')
        item = runtime.inspect('container', cid)
        require(isinstance(item, dict), 'MOUNT_INVENTORY_CHANGED')
        state = item['State']
        if state['Status'] in ('created', 'exited', 'dead') and not any(
            state[key] for key in ('Running', 'Paused', 'Restarting', 'Pid')
        ):
            continue
        for mount in item['Mounts']:
            path = Path(mount['Source']).resolve()
            require(path.is_absolute() and not (path == SOURCE or path in SOURCE.parents
                    or SOURCE in path.parents), 'LIVE_SOURCE_MOUNT')


def source_guard(runtime):
    private_identity(SOURCE)
    require(stamp(SOURCE, directory=True)[:2] == [2049, 4852972], 'SOURCE_ROOT_CHANGED')
    pg = stamp(SOURCE / 'postgres', directory=True)
    require(pg[:2] == [2049, 4852979] and pg[2] == os.getuid()
            and stat.S_IMODE(pg[4]) == 0o711, 'SOURCE_PG_CHANGED')
    raw = private_bytes(SOURCE / 'startup.json', 16384)
    require(hashlib.sha256(raw).hexdigest() == JOURNAL_SHA, 'SOURCE_JOURNAL_CHANGED')
    record = json.loads(raw)
    require((record['phase'], record['format'], record['generation'], record['supervisor_epoch'])
            == ('READY', 5, 27, 16) and record['containers'] == CONTAINERS
            and record['instance_id'] == INSTANCE and record['system_id'] == SYSTEM
            and record['project'] == PROJECT and record['pgdata_identity'] == pg[:2],
            'SOURCE_BINDING_CHANGED')
    require(runtime.receipt.project == PROJECT and runtime.provider_settings
            and runtime.release.name == '0.1.1' and runtime.schema == '0017_model_removal'
            and runtime.digest == record['release_digest'], 'RELEASE_BINDING_CHANGED')
    instance = load_instance(SOURCE)
    require((instance.instance_id, instance.release, instance.schema, instance.project, instance.origin)
            == (INSTANCE, '0.1.1', '0017_model_removal', PROJECT, 'http://127.0.0.1:8780'),
            'SOURCE_INSTANCE_CHANGED')
    runtime.attempt = record['attempt']
    require(private_identity(SOURCE / 'vault') == record['vault_identity']
            and private_identity(SOURCE / 'vault-key') == record['vault_key_identity'],
            'VAULT_PATH_CHANGED')
    master = stamp(SOURCE / 'vault-key/master.key')  # Metadata only: never open the key.
    require(master[:2] == [2049, 4894026] and master[6] == 32, 'MASTER_METADATA_CHANGED')
    files = {name: stamp(SOURCE / name) for name in COPY}
    locks = {str(root): stamp(root / 'lifecycle.lock') for root in (DATA / 'omnis', SOURCE)}
    refuse_upgrade(DATA / 'omnis')
    runtime.check_daemon()
    original_containers(runtime, record)
    metadata = {str(path): digest(path, 1024 * 1024) for path in (
        DATA / 'omnis/installed.json', DATA / 'omnis/image.json', runtime.release / 'release.json')}
    require(json.loads(private_bytes(DATA / 'omnis/installed.json', 16384))
            == {'format': 1, 'release': '0.1.1'}, 'INSTALLED_POINTER_CHANGED')
    return {'files': files, 'metadata': metadata, 'master_stat_only': master, 'pg_identity': pg, 'locks': locks,
            'data_identity': private_identity(DATA / 'omnis'),
            'root_identity': stamp(SOURCE, directory=True), 'journal_sha256': JOURNAL_SHA}


def preflight():
    deadline = time.monotonic() + 840
    for name, expected in HELPERS.items():
        require(hashlib.sha256((REPO / 'cli/src/omnis_cli' / name).read_bytes()).hexdigest()
                == expected, 'HELPER_BYTES_CHANGED')
    require(OUTPUT.is_absolute() and OUTPUT.resolve() == OUTPUT and not os.path.lexists(OUTPUT),
            'DESTINATION_EXISTS_OR_ALIASED')
    private_dir(OUTPUT.parent)
    require(not (OUTPUT == SOURCE or SOURCE in OUTPUT.parents or OUTPUT in SOURCE.parents),
            'SOURCE_DESTINATION_OVERLAP')
    raw = private_bytes(QUERIES, 16384)
    require(hashlib.sha256(raw).hexdigest() == QUERY_SHA, 'QUERY_BYTES_CHANGED')
    queries = json.loads(raw)
    recovery_sql(queries)  # Pure validation: discover input/oracle failures before effects.
    runtime = ControlRuntime(DATA, deadline)
    return runtime, source_guard(runtime), queries


def put_json(path, value):
    _put(path, (json.dumps(value, sort_keys=True) + '\n').encode())
    _sync_dir(path.parent)


def tar_content(path, deadline):
    validate_tar(path, deadline)
    members = {}
    with tarfile.open(path, 'r:') as source:
        for member in source:
            remaining(deadline)
            name = member.name.removeprefix('./').rstrip('/')
            if name == '.':
                continue
            value = hashlib.sha256()
            if member.isfile():
                with source.extractfile(member) as content:
                    while part := content.read(65536):
                        remaining(deadline)
                        value.update(part)
            members[name] = [member.type.decode(), member.uid, member.gid, member.mode,
                             member.size, value.hexdigest()]
    # Exact source header: postgres UID 999 uses owner bits even with copy GID 999.
    require(members['18/docker'][:4] == ['5', 999, 0, 0o700], 'PGDATA_OWNER_OR_MODE')
    return hashlib.sha256(json.dumps(members, sort_keys=True).encode()).hexdigest()


def make_archive(runtime, root, path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        archive(runtime, root, fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    return tar_content(path, runtime.deadline)


def retire_body():
    raw = (REPO / 'api/src/omnis/core/provider_schema.py').read_bytes()
    require(hashlib.sha256(raw).hexdigest() ==
            '0f27c097d9a6928f17bcc528ad860a405b39eb0506c6e1496da9b3fc75b9f7e9',
            'SCHEMA_ORACLE_CHANGED')
    return next(ast.literal_eval(node.value) for node in ast.parse(raw).body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == 'MODEL_RETIRE_GUARD')


SHAPE_SQL = """SELECT jsonb_build_object(
'system_id', (SELECT system_identifier::text FROM pg_control_system()),
'inventory', (SELECT jsonb_agg(relname ORDER BY relname) FROM pg_class
 WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p')),
'column', (SELECT jsonb_build_array(format_type(a.atttypid,a.atttypmod),a.attnotnull,d.adbin IS NULL)
 FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE a.attrelid='public.provider_model_entry'::regclass
 AND a.attname='removed_registry_revision' AND NOT a.attisdropped),
'index', (SELECT jsonb_build_array(indisunique,indisvalid,indisready,indkey::text,
 pg_get_expr(indpred,indrelid)) FROM pg_index
 WHERE indexrelid=to_regclass('public.provider_model_available_unique')
 AND indrelid='public.provider_model_entry'::regclass),
'fk', (SELECT pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conrelid='public.provider_model_entry'::regclass
 AND conname='provider_model_removed_registry_fk' AND convalidated),
'old_unique', EXISTS(SELECT 1 FROM pg_constraint
 WHERE conrelid='public.provider_model_entry'::regclass
 AND conname='provider_model_entry_instance_id_connection_id_model_key'),
'triggers', (SELECT jsonb_agg(jsonb_build_array(t.tgname,t.tgtype,t.tgenabled,p.proname,p.prosrc,
 l.lanname,p.prosecdef,p.pronargs,t.tgnargs,t.tgqual IS NULL,t.tgattr::text,
 p.prorettype::regtype::text) ORDER BY t.tgname)
 FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_language l ON l.oid=p.prolang
 WHERE t.tgrelid='public.provider_model_entry'::regclass AND NOT t.tgisinternal))"""


def recovery_sql(queries):
    retire_body()
    sql = ("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY; "
           "SET LOCAL statement_timeout=15000; SET LOCAL timezone='UTC'; "
           + ';'.join([queries[key] for key in ('baseline', 'census', 'domain_sha256')]
                      + [SHAPE_SQL]) + '; COMMIT;')
    require(len(sql.encode()) <= 16384, 'SQL_INPUT_LIMIT')
    return sql


def projection(raw):
    lines = raw.strip().splitlines()
    require(len(lines) == 4, 'PROJECTION_LINES')
    result = dict(zip(('baseline', 'census', 'domain_sha256', 'shape'), map(json.loads, lines)))
    shape = result['shape']
    require(result['baseline']['schema'] == '0017_model_removal'
            and result['baseline']['instance']['instance_id'] == INSTANCE
            and shape['system_id'] == SYSTEM, 'RESTORED_DATABASE_IDENTITY')
    require(set(shape['inventory']) == set(result['census'])
            and set(result['domain_sha256']) == set(result['census']) - {
                'pairing_challenge', 'pairing_issuance', 'ui_session'}, 'TABLE_COVERAGE_CHANGED')
    require(shape['column'] == ['bigint', False, True]
            and shape['index'] == [True, True, True, '1 3 4', '(removed_registry_revision IS NULL)']
            and shape['fk'] == 'FOREIGN KEY (instance_id, removed_registry_revision) REFERENCES provider_model_registry_revision(instance_id, revision)'
            and shape['old_unique'] is False
            and shape['triggers'] == [
                ['provider_model_retire', 19, 'O', 'provider_model_retire_guard', retire_body(),
                 'plpgsql', False, 0, 0, True, '', 'trigger'],
                ['provider_settings_no_change', 42, 'O', 'provider_settings_immutable',
                 "BEGIN\n        RAISE EXCEPTION 'provider Settings history is immutable';\n        END;",
                 'plpgsql', False, 0, 0, True, '', 'trigger']], 'SCHEMA_0017_SHAPE_MISMATCH')
    return result


PG_COMMAND = ['-D', '/var/lib/postgresql/18/docker', '-c', 'listen_addresses=',
              '-c', 'unix_socket_directories=/tmp', '-c', 'default_transaction_read_only=on',
              '-c', 'statement_timeout=15000']


def attest_copy(runtime, cid, name, copy):
    runtime.check_daemon()
    item = runtime.inspect('container', cid)
    require(isinstance(item, dict), 'COPY_CONTAINER_MISSING')
    config, host = item['Config'], item['HostConfig']
    mounts = item['Mounts']
    require(item['Id'] == cid and item['Name'] == '/' + name
            and config['Labels'] == {'org.omnis.crash-preservation': name}
            and item['Image'] == runtime.pg_image and config['User'] == '999:999'
            and config['Entrypoint'] == ['postgres'] and config['Cmd'] == PG_COMMAND
            and host['NetworkMode'] == 'none' and host['Privileged'] is False
            and host['ReadonlyRootfs'] is True and host['CapDrop'] == ['ALL']
            and host['CapAdd'] in (None, []) and host['SecurityOpt'] == ['no-new-privileges:true']
            and host['RestartPolicy'] == {'Name': 'no', 'MaximumRetryCount': 0}
            and host['PortBindings'] in (None, {}) and host['PublishAllPorts'] is False
            and host['PidMode'] in ('', None) and host['IpcMode'] == 'private'
            and host['Devices'] in (None, []) and host['DeviceRequests'] in (None, [])
            and set(host['Tmpfs']) == {'/tmp'} and len(mounts) == 1
            and mounts[0]['Type'] == 'bind' and mounts[0]['Source'] == str(copy / 'postgres')
            and mounts[0]['Destination'] == '/var/lib/postgresql' and mounts[0]['RW'] is True
            and mounts[0]['Propagation'] == 'rprivate', 'COPY_CONTAINER_IDENTITY')
    return item


def recover_copy(runtime, copy, queries):
    from uuid import uuid4
    require(copy == OUTPUT / 'restored' and copy != SOURCE, 'COPY_ONLY')
    identity = private_identity(copy)
    require((copy / 'postgres').resolve() == copy / 'postgres', 'COPY_PGDATA_ALIAS')
    pg_identity = stamp(copy / 'postgres', directory=True)
    require(pg_identity[:2] != [2049, 4852979] and pg_identity[2] == os.getuid()
            and stat.S_IMODE(pg_identity[4]) == 0o711, 'COPY_PGDATA_IDENTITY')
    sql = recovery_sql(queries)
    name = 'omnis-crash-' + uuid4().hex
    put_json(OUTPUT / 'copy-owner.json', {'name': name, 'root': str(copy),
             'deadline_monotonic': runtime.deadline, 'cleanup_reserve_seconds': 60})
    cid = None
    try:
        runtime.check_daemon()
        created = runtime.run('create', '--name', name, '--label',
            'org.omnis.crash-preservation=' + name, '--network', 'none', '--pull', 'never',
            '--platform', 'linux/amd64', '--restart', 'no', '--user', '999:999',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--stop-signal', 'SIGINT', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
            '--mount', f'type=bind,src={copy}/postgres,dst=/var/lib/postgresql',
            '--entrypoint', 'postgres', runtime.pg_image, *PG_COMMAND, effect=True)
        cid = created.stdout.strip()
        require(re.fullmatch(r'[0-9a-f]{64}', cid) and cid not in CONTAINERS.values(), 'COPY_CID')
        put_json(OUTPUT / 'copy-cid.json', {'cid': cid})
        require(attest_copy(runtime, cid, name, copy)['State']['Status'] == 'created', 'COPY_NOT_NEW')
        require(stamp(copy / 'postgres', directory=True) == pg_identity, 'COPY_PGDATA_CHANGED')
        runtime.run('start', cid, effect=True)
        until = min(runtime.deadline, time.monotonic() + 45)
        while True:
            require(attest_copy(runtime, cid, name, copy)['State']['Status'] == 'running', 'COPY_EXITED')
            ready = runtime.run('exec', cid, 'pg_isready', '-h', '/tmp', '-U', 'omnis',
                                '-d', 'omnis', success=False)
            if ready.returncode == 0:
                break
            time.sleep(min(0.2, remaining(until)))
        result = runtime.run('exec', '-i', cid, 'psql', '-X', '-qAt', '-h', '/tmp',
            '-U', 'omnis', '-d', 'omnis', '-v', 'ON_ERROR_STOP=1', stdin=sql.encode(), cap=180)
        value = projection(result.stdout)
        require(not result.stderr, 'COPY_SQL_DIAGNOSTIC')
        runtime.run('stop', '--time', '30', cid, effect=True, cap=40)
        state = attest_copy(runtime, cid, name, copy)['State']
        require(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
                and state['ExitCode'] == 0, 'COPY_STOP_UNCERTAIN')
        return value
    finally:
        runtime.deadline += 60  # One reserved cleanup window; total from preflight <=900s.
        # A failed create may have reached the daemon: inspect only our unique name.
        item = runtime.inspect('container', name)
        if item is not None:
            owned = item['Id']
            require(owned not in CONTAINERS.values(), 'CLEANUP_SOURCE_REFUSED')
            attest_copy(runtime, owned, name, copy)
            require(private_identity(copy) == identity, 'COPY_PATH_CHANGED')
            runtime.run('rm', '-f', owned, effect=True, cap=30)
            require(runtime.inspect('container', owned) is None, 'COPY_CLEANUP_UNCERTAIN')
        require(private_identity(copy) == identity, 'COPY_DATA_NOT_RETAINED')


def execute():
    runtime, seal, queries = preflight()
    with lifecycle_lock(DATA / 'omnis', runtime.deadline), lifecycle_lock(SOURCE, runtime.deadline):
        require(source_guard(runtime) == seal, 'SOURCE_CHANGED_UNDER_LOCK')
        OUTPUT.mkdir(mode=0o700)
        _sync_dir(OUTPUT.parent)
        (OUTPUT / 'vault').mkdir(mode=0o700)
        for name, limit in COPY.items():
            _put(OUTPUT / name, private_bytes(SOURCE / name, limit))
        (OUTPUT / 'release-metadata').mkdir(mode=0o700)
        for name, path in {
            'installed.json': DATA / 'omnis/installed.json',
            'image.json': DATA / 'omnis/image.json',
            'manifest.json': runtime.release / 'release.json',
        }.items():
            _put(OUTPUT / 'release-metadata' / name, private_bytes(path, 1024 * 1024))
        _sync_dir(OUTPUT / 'vault')
        _sync_dir(OUTPUT / 'release-metadata')
        physical = make_archive(runtime, SOURCE, OUTPUT / 'postgres.tar')
        require(source_guard(runtime) == seal, 'SOURCE_CHANGED_DURING_ARCHIVE')
        require(all(private_bytes(SOURCE / name, limit) == private_bytes(OUTPUT / name, limit)
                    for name, limit in COPY.items()), 'OPAQUE_SOURCE_CHANGED')
        files = {name: digest(OUTPUT / name, limit) for name, limit in COPY.items()}
        files['postgres.tar'] = digest(OUTPUT / 'postgres.tar', ARCHIVE_LIMIT)
        put_json(OUTPUT / 'manifest.json', {
            'consistency': 'CRASH_CONSISTENT', 'source': str(SOURCE), 'seal': seal,
            'release': '0.1.1', 'schema': '0017_model_removal', 'system_id': SYSTEM,
            'instance_id': INSTANCE, 'pg_image': runtime.pg_image, 'files': files,
            'physical_sha256': physical, 'master': 'EXCLUDED_STAT_ONLY',
            'journal': 'original READY bytes; not a Stop completion',
        })
        copy = OUTPUT / 'restored'
        copy.mkdir(mode=0o700)
        (copy / 'postgres').mkdir(mode=0o711)
        (copy / 'postgres').chmod(0o711)
        _sync_dir(copy)
        fd = os.open(OUTPUT / 'postgres.tar', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = stamp(OUTPUT / 'postgres.tar')
            info = os.fstat(fd)
            require([info.st_dev, info.st_ino] == before[:2]
                    and digest(OUTPUT / 'postgres.tar', ARCHIVE_LIMIT) == files['postgres.tar'],
                    'ARCHIVE_CHANGED')
            archive(runtime, copy, fd, restore=True)
            require(stamp(OUTPUT / 'postgres.tar') == before, 'ARCHIVE_CHANGED')
        finally:
            os.close(fd)
        copied = make_archive(runtime, copy, OUTPUT / 'restored-before-wal.tar')
        require(copied == physical, 'PHYSICAL_RESTORE_MISMATCH')
        put_json(OUTPUT / 'physical-copy.json', {'before_wal_equal': True, 'sha256': physical})
        require(source_guard(runtime) == seal, 'SOURCE_CHANGED_BEFORE_COPY_RECOVERY')
        projection = recover_copy(runtime, copy, queries)
        require(source_guard(runtime) == seal, 'SOURCE_CHANGED_AFTER_COPY_RECOVERY')
        require(not runtime.uncertain and runtime.family_drained, 'OWNER_UNCERTAIN')
        put_json(OUTPUT / 'recovered-baseline.json', projection)
        put_json(OUTPUT / 'result.json', {
            'verdict': 'PHYSICAL_RESTORE_OPENED_AND_READ', 'source_fence_unchanged': True,
            'wal_recovery': 'PostgreSQL startup; replay only if needed',
            'operator_same_data_comparison': 'PENDING_RECOVERY',
            'decryption': 'NOT_RUN_MASTER_EXCLUDED', 'pgdata': 'RETAINED',
        })
    print('PRESERVED_AND_RESTORED_COPY: original journal retained; source recovery NOT_RUN')


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main(argv):
    if argv not in (['--check'], ['--execute']):
        print('REFUSED: use exactly --check or reviewed --execute; no overrides')
        return 4
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        if argv == ['--check']:
            preflight()
            print('CHECK_ONLY: pinned inputs available; no backup/restore/SQL executed')
        else:
            execute()
        return 0
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, KeyboardInterrupt) as error:
        reason = error.reason if isinstance(error, StartError) else type(error).__name__
        print(f'REFUSED_OR_UNCERTAIN {reason}: retain artifacts and PGDATA; no automatic retry')
        return 4
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
