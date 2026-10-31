"""SOURCE only: no Docker, operator writes, SQL or backup execution."""
import contextlib
import io
import importlib.util
import json
import os
import pathlib
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

RECIPE = pathlib.Path(__file__).with_name("crash-preservation-20261031.py")


class SourceControls(unittest.TestCase):
    def test_recipe_has_effect_free_default_and_explicit_execution(self):
        self.assertTrue(RECIPE.is_file(), "bounded crash preservation recipe missing")
        spec = importlib.util.spec_from_file_location("crash_recipe", RECIPE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, "preflight", return_value={}) as check, patch.object(
            module, "execute", create=True, side_effect=AssertionError("effect reached")
        ):
            self.assertEqual(module.main(["--check"]), 0)
            check.assert_called_once()
            self.assertEqual(module.main([]), 4)
            self.assertEqual(module.main(["--execute", "foreign-path"]), 4)


    def module(self):
        spec = importlib.util.spec_from_file_location("crash_recipe", RECIPE)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_physical_copy_is_verified_before_recovery_and_source_is_unchanged(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'execute'), 'physical preservation path missing')
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            root = pathlib.Path(temp)
            source, data, output = root/'source', root/'data', root/'backup'
            for p in (source, data, data/'omnis', source/'vault'):
                p.mkdir(mode=0o700)
            payloads = {name: b'SOURCE opaque '+name.encode() for name in m.COPY}
            for name, raw in payloads.items():
                m._put(source/name, raw)
            for name in ('installed.json', 'image.json'):
                m._put(data/'omnis'/name, b'{}')
            release = data/'omnis/releases/0.1.1'
            release.mkdir(mode=0o700, parents=True)
            m._put(release/'release.json', b'{}')
            events = []
            runtime = SimpleNamespace(deadline=time.monotonic()+60, uncertain=False,
                                      family_drained=True, release=release, pg_image='SOURCE')

            def archive_double(runtime, path, fd, *, restore=False):
                events.append(('archive', path, restore))
                self.assertFalse(restore and path == source)
                if restore:
                    return  # OCI boundary double; equality is exercised by real tar parser below.
                with os.fdopen(os.dup(fd), 'wb') as stream, tarfile.open(fileobj=stream, mode='w') as tar:
                    for name, raw in [('18/docker', None), ('18/docker/PG_VERSION', b'18\n'),
                                      ('18/docker/global/pg_control', b'SOURCE physical bytes')]:
                        info = tarfile.TarInfo(name)
                        info.uid = info.gid = 999
                        info.mode = 0o700 if raw is None else 0o600
                        info.type = tarfile.DIRTYPE if raw is None else tarfile.REGTYPE
                        info.size = 0 if raw is None else len(raw)
                        tar.addfile(info, None if raw is None else io.BytesIO(raw))

            def recovered(runtime, copy, queries):
                self.assertTrue((output/'physical-copy.json').exists())
                self.assertTrue((output/'manifest.json').exists())
                events.append(('recover', copy))
                return {'SOURCE': 'not PostgreSQL evidence'}

            @contextlib.contextmanager
            def lock(path, deadline):
                events.append(('lock', path))
                yield 123

            with patch.object(m, 'SOURCE', source), patch.object(m, 'DATA', data), \
                 patch.object(m, 'OUTPUT', output), \
                 patch.object(m, 'preflight', return_value=(runtime, {}, {})), \
                 patch.object(m, 'source_guard', return_value={}), \
                 patch.object(m, 'archive', side_effect=archive_double), \
                 patch.object(m, 'lifecycle_lock', side_effect=lock), \
                 patch.object(m, 'recover_copy', create=True, side_effect=recovered), \
                 patch('subprocess.Popen', side_effect=AssertionError('real subprocess')):
                m.execute()
                self.assertEqual({name: (source/name).read_bytes() for name in m.COPY}, payloads)
                self.assertEqual(events[:2], [('lock', data/'omnis'), ('lock', source)])
                self.assertEqual(events[2:5], [('archive', source, False),
                    ('archive', output/'restored', True), ('archive', output/'restored', False)])
                self.assertEqual(json.loads((output/'manifest.json').read_bytes())['consistency'],
                                 'CRASH_CONSISTENT')
                self.assertFalse((output/'completion.json').exists())
                self.assertFalse((output/'master.key').exists())
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                with self.assertRaises(FileExistsError):
                    m.execute()
            self.assertTrue((output/'postgres.tar').exists())


    def test_recovery_is_copy_only_and_has_exact_owned_cleanup(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'recover_copy'), 'isolated native recovery missing')
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            copy = pathlib.Path(temp)/'restored'
            copy.mkdir(mode=0o700)
            (copy/'postgres').mkdir(mode=0o711)
            (copy/'postgres').chmod(0o711)
            calls = []
            cid = 'f'*64
            runtime = SimpleNamespace(deadline=time.monotonic()+60, uncertain=False,
                                      family_drained=True, pg_image='sha256:'+'a'*64,
                                      check_daemon=lambda: None)
            state = {'removed': False, 'status': 'created'}
            def run(*argv, **kwargs):
                calls.append((argv, kwargs))
                if argv[0] == 'create':
                    self.assertNotIn(str(m.SOURCE/'postgres'), ' '.join(argv))
                    self.assertIn(f'type=bind,src={copy}/postgres,dst=/var/lib/postgresql', argv)
                    for value in ('none', '999:999', '--read-only', 'ALL', '--pull', 'never'):
                        self.assertIn(value, argv)
                    return SimpleNamespace(stdout=cid+'\n', stderr='', returncode=0)
                if argv[0] == 'start':
                    self.assertEqual(argv, ('start', cid))
                    state['status'] = 'running'
                    return SimpleNamespace(stdout=cid, stderr='', returncode=0)
                if argv[0] == 'exec':
                    if 'psql' in argv:
                        self.assertIn(b'READ ONLY', kwargs['stdin'])
                    return SimpleNamespace(stdout='SOURCE projection', stderr='', returncode=0)
                if argv[0] == 'stop':
                    self.assertEqual(argv, ('stop', '--time', '30', cid))
                    state['status'] = 'exited'
                    return SimpleNamespace(stdout=cid, stderr='', returncode=0)
                if argv[0] == 'rm':
                    self.assertEqual(argv, ('rm', '-f', cid))
                    state['removed'] = True
                    return SimpleNamespace(stdout=cid, stderr='', returncode=0)
                raise AssertionError(argv)
            runtime.run = run
            def owned(*args):
                return {'Id': cid, 'State': {'Status': state['status'], 'Running': False,
                                  'Pid': 0, 'ExitCode': 0}}
            runtime.inspect = lambda kind, ident: None if state['removed'] else owned()
            with patch.object(m, 'OUTPUT', pathlib.Path(temp)), \
                 patch.object(m, 'attest_copy', side_effect=owned), \
                 patch.object(m, 'recovery_sql', return_value='BEGIN READ ONLY;SELECT 1;COMMIT;'), \
                 patch.object(m, 'projection', return_value={'SOURCE': True}), \
                 patch('subprocess.Popen', side_effect=AssertionError('real subprocess')):
                self.assertEqual(m.recover_copy(runtime, copy, {}), {'SOURCE': True})
                self.assertTrue(state['removed'])
                self.assertTrue(copy.exists())
                before = len(calls)
                with self.assertRaises(m.StartError):
                    m.recover_copy(runtime, m.SOURCE, {})
                self.assertEqual(len(calls), before)


    def test_originals_refuse_running_replacement_and_overlapping_mount(self):
        m = self.module()
        record = {'attempt': 'SOURCE', 'image_id': 'APP', 'control_dir': '/SOURCE/control', 'port': 8780}
        items = {cid: {'Id': cid, 'Image': 'PG' if role == 'db' else 'APP',
            'Config': {'Labels': {'com.docker.compose.project': m.PROJECT,
                'com.docker.compose.service': role, 'org.omnis.start-attempt': 'SOURCE'}},
            'State': {'Status': 'exited', 'Running': False, 'Pid': 0,
                      'Paused': False, 'Restarting': False},
            'HostConfig': {'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}},
            'Mounts': []} for role, cid in m.CONTAINERS.items()}
        runtime = SimpleNamespace(ids=lambda: list(m.CONTAINERS.values()), pg_image='PG',
            inspect=lambda kind, cid: items[cid], attest=lambda *args: None,
            run=lambda *args: SimpleNamespace(stdout='\n'.join(items)))
        m.original_containers(runtime, record)
        db = items[m.CONTAINERS['db']]
        for key, value in [('Running', True), ('Status', 'running'), ('Pid', 42),
                           ('Paused', True), ('Restarting', True)]:
            with self.subTest(key=key), patch.dict(db['State'], {key: value}):
                with self.assertRaisesRegex(m.StartError, 'SOURCE_NOT_EXITED_EXACT'):
                    m.original_containers(runtime, record)
        with patch.object(runtime, 'ids', return_value=[m.CONTAINERS['db']]):
            with self.assertRaisesRegex(m.StartError, 'SOURCE_CONTAINER_SET_CHANGED'):
                m.original_containers(runtime, record)
        items['f'*64] = {'State': {'Status': 'running'},
                         'Mounts': [{'Source': str(m.SOURCE.parent)}]}
        with self.assertRaisesRegex(m.StartError, 'LIVE_SOURCE_MOUNT'):
            m.original_containers(runtime, record)

    def test_partial_archive_is_retained_on_failure(self):
        m = self.module()
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            target = pathlib.Path(temp)/'partial.tar'
            def failure(runtime, root, fd):
                os.write(fd, b'SOURCE partial')
                raise m.StartError('SOURCE_FAILURE', 4)
            with patch.object(m, 'archive', side_effect=failure), \
                 patch('subprocess.Popen', side_effect=AssertionError('real subprocess')):
                with self.assertRaisesRegex(m.StartError, 'SOURCE_FAILURE'):
                    m.make_archive(SimpleNamespace(deadline=time.monotonic()+10), pathlib.Path(temp), target)
            self.assertEqual(target.read_bytes(), b'SOURCE partial')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_projection_checks_actual_0017_shape_and_full_inventory(self):
        m = self.module()
        baseline = {'schema': '0017_model_removal', 'instance': {'instance_id': m.INSTANCE}}
        census = {'t': 1, 'pairing_challenge': 0, 'pairing_issuance': 0, 'ui_session': 0}
        shape = {'system_id': m.SYSTEM, 'inventory': list(census),
                 'column': ['bigint', False, True],
                 'index': [True, True, True, '1 3 4', '(removed_registry_revision IS NULL)'],
                 'fk': 'FOREIGN KEY (instance_id, removed_registry_revision) REFERENCES provider_model_registry_revision(instance_id, revision)',
                 'old_unique': False, 'triggers': [
                 ['provider_model_retire', 19, 'O', 'provider_model_retire_guard', m.retire_body(),
                  'plpgsql', False, 0, 0, True, '', 'trigger'],
                 ['provider_settings_no_change', 42, 'O', 'provider_settings_immutable',
                  "BEGIN\n        RAISE EXCEPTION 'provider Settings history is immutable';\n        END;",
                  'plpgsql', False, 0, 0, True, '', 'trigger']]}
        def raw():
            return '\n'.join(map(json.dumps, (baseline, census, {'t': 'a'*64}, shape)))
        self.assertEqual(m.projection(raw())['census'], census)
        for key, value in [('column', None), ('index', None), ('fk', None), ('triggers', []),
                           ('old_unique', True), ('inventory', ['missing'])]:
            with self.subTest(key=key), patch.dict(shape, {key: value}):
                with self.assertRaises(m.StartError):
                    m.projection(raw())


    def test_recovery_rejects_source_pgdata_alias_before_any_effect(self):
        m = self.module()
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            root = pathlib.Path(temp)
            copy = root/'restored'
            copy.mkdir(mode=0o700)
            (copy/'postgres').symlink_to(m.SOURCE/'postgres', target_is_directory=True)
            runtime = SimpleNamespace(deadline=time.monotonic()+60)
            with patch.object(m, 'OUTPUT', root), \
                 patch.object(m, 'recovery_sql', return_value='SOURCE'), \
                 patch.object(m, 'put_json', side_effect=AssertionError('effect reached')):
                with self.assertRaisesRegex(m.StartError, 'COPY_PGDATA'):
                    m.recover_copy(runtime, copy, {})


    def test_sigterm_unwinds_the_existing_owner(self):
        import signal
        m = self.module()
        previous = signal.getsignal(signal.SIGTERM)
        def interrupted():
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler), 'SIGTERM bypasses finally/owned cleanup')
            handler(signal.SIGTERM, None)
        with patch.object(m, 'execute', side_effect=interrupted):
            self.assertEqual(m.main(['--execute']), 4)
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)


    def test_existing_archive_helper_mounts_source_read_only(self):
        m = self.module()
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            root = pathlib.Path(temp)
            (root/'postgres').mkdir(mode=0o711)
            (root/'postgres').chmod(0o711)
            calls = []
            runtime = SimpleNamespace(receipt=SimpleNamespace(project='SOURCE'), pg_image='SOURCE',
                check_daemon=lambda: None, inspect=lambda *args: None,
                uncertain=False, family_drained=True,
                run=lambda *args, **kwargs: (calls.append((args, kwargs)) or SimpleNamespace(stderr='')))
            fd = os.open(root/'archive', os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            try:
                with patch('subprocess.Popen', side_effect=AssertionError('real subprocess')):
                    m.archive(runtime, root, fd)
            finally:
                os.close(fd)
            argv, options = calls[0]
            self.assertIn(f'type=bind,src={root}/postgres,dst=/data,readonly', argv)
            self.assertIn('none', argv)
            self.assertEqual(options['stdout_fd'], fd)
            self.assertNotIn('--extract', argv)


if __name__ == "__main__":
    unittest.main(verbosity=2)
