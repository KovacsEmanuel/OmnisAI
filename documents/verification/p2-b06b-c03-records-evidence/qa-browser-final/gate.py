"""Prepare-only by default. Final dispatch requires explicit reviewed artifact pins."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import zipfile

Q = Path(__file__).resolve().parent
R = Path('/home/kali/OmnisAI')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def regular(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Expected regular nonlinked evidence/artifact'

def preflight(cfg):
    approval = cfg['acceptance']
    assert cfg['schema_version'] == 1
    assert approval['verdict'] == 'APPROVED_SCOPED' and approval['launch_authorized'] is True, 'Review acceptance / separate live dispatch required'
    assert approval.get('pg_serial_slot_granted') is True, 'Parent must reserve serial PostgreSQL execution'
    assert re.fullmatch(r'[0-9a-f]{40}', approval['snapshot']), 'Frozen commit required'
    assert approval['api_wheel_sha256'] == cfg['api_wheel_sha256']
    assert approval['web_files'] == cfg['web_files'] and cfg['web_files']
    assert approval['receipts'], 'Exact independent review receipts required'
    for receipt in approval['receipts']:
        path = Path(receipt['path']); regular(path)
        assert digest(path) == receipt['sha256'], 'Review receipt changed'
    for name, expected in cfg['helper_pins'].items():
        path = Path(name); regular(path)
        assert digest(path) == expected, 'Reviewed QA helper changed'
    wheel = Path(cfg['api_wheel']); regular(wheel)
    assert re.fullmatch(r'[0-9a-f]{64}', cfg['api_wheel_sha256'])
    assert digest(wheel) == cfg['api_wheel_sha256'], 'Final wheel mismatch'
    tools = Path(cfg['tools_bin'])
    for name in ['node','npm','uv']:
        assert (tools/name).is_file() and os.access(tools/name,os.X_OK), 'Pinned local tool missing'
    assert Path(cfg['browser_executable']).is_file()
    assert Path(cfg['api_python']).is_absolute() and Path(cfg['api_python']).is_file()
    assert type(cfg['timeout_seconds']) is int and 120 <= cfg['timeout_seconds'] <= 900
    env = {'PATH':str(tools)+':/usr/bin:/bin','HOME':str(Q),'TMPDIR':str(Q)}
    # No product module imports and no installation; interpreter metadata only.
    info = subprocess.run([cfg['api_python'],'-I','-B','-c','import site,json,sys;print(json.dumps({"prefix":sys.prefix,"sites":site.getsitepackages()}))'],env=env,cwd=Q,capture_output=True,text=True,timeout=10,check=True)
    meta = json.loads(info.stdout)
    roots = [Path(p)/'omnis' for p in meta['sites'] if (Path(p)/'omnis').is_dir()]
    assert len(roots) == 1 and Path(meta['prefix']) in roots[0].parents, 'Installed API package not isolated'
    root = roots[0]; installed = {}
    with zipfile.ZipFile(wheel) as package:
        names = [n for n in package.namelist() if n.startswith('omnis/') and not n.endswith('/')]
        assert names and len(names) == len(set(names))
        for name in names:
            rel = Path(name).relative_to('omnis')
            assert '..' not in rel.parts
            path = root/rel; regular(path)
            assert path.read_bytes() == package.read(name), 'Installed wheel bytes differ'
            installed[str(rel)] = digest(path)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert actual == set(installed), 'Unexpected installed package files'
    web = Path(cfg['web_root']); assert web.is_absolute() and web.is_dir()
    for name, expected in cfg['web_files'].items():
        rel = Path(name); assert not rel.is_absolute() and '..' not in rel.parts
        path = web/rel; regular(path); assert digest(path) == expected, 'Final web asset mismatch'
    actual_web = {str(p.relative_to(web)) for p in web.rglob('*') if p.is_file()}
    assert actual_web == set(cfg['web_files']) and 'index.html' in actual_web and 'omnis-web.json' in actual_web
    return {'verdict':'PREFLIGHT_ONLY','snapshot':approval['snapshot'],'api_wheel_sha256':cfg['api_wheel_sha256'],'installed_root':str(root),'installed_bindings':installed,'web_files':cfg['web_files'],'review_receipts':approval['receipts']}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--execute-after-acceptance',action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    cfg = json.loads(args.config.read_text())
    evidence = preflight(cfg)
    if not args.execute_after_acceptance:
        print('PREFLIGHT_ONLY: no services started'); return 0
    # Single use: failed runs are retained, never overwritten/retried in place.
    with (Q/'launch-once').open('x') as f: f.write(cfg['acceptance']['snapshot']+'\n')
    with (Q/'dispatch.json').open('x') as f: json.dump(cfg,f,indent=2)
    with (Q/'preflight.json').open('x') as f: json.dump(evidence,f,indent=2)
    home = Q/'home'; home.mkdir(mode=0o700)
    for child in ['.cache','.config','.local/share/uv']:
        (home/child).mkdir(mode=0o700,parents=True,exist_ok=True)
    # Read-only executable discovery link; no downloads or global writes.
    (home/'.local/share/uv/python').symlink_to('/home/kali/.local/share/uv/python',target_is_directory=True)
    # LocalControl requires an existing owned 0700 IPC directory; no adoption.
    (Q/'ipc').mkdir(mode=0o700)
    assert stat.S_IMODE((Q/'ipc').stat().st_mode)==0o700
    (Q/'captures').mkdir(mode=0o700)
    os.environ.clear()
    os.environ.update(PATH=cfg['tools_bin']+':/usr/bin:/bin',HOME=str(home),TMPDIR=str(Q))
    spec = importlib.util.spec_from_file_location('qa_existing_runner',R/'ops/run_test_db_gate.py')
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runner; spec.loader.exec_module(runner)
    original = runner.run_gate
    setattr(runner,'run_gate',lambda argv,env,log,timeout: original([cfg['api_python'],'-I','-B',str(Q/'journey.py')],env,log,timeout))
    signal.signal(signal.SIGTERM,runner._request_stop); signal.signal(signal.SIGINT,runner._request_stop)
    code = 2
    try:
        code = runner.prove_private_fixture('test-e2e',str(Path(cfg['tools_bin'])/'uv'),cfg['timeout_seconds'])
    finally:
        (Q/'gate-exit.json').write_text(json.dumps({'exit':code,'scope':'TARGETED_INSTALLED_UI_NOT_CANONICAL'}))
    return code

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError,KeyError,TypeError,ValueError,OSError,subprocess.SubprocessError) as exc:
        print('DISPATCH_BLOCKED '+type(exc).__name__+'; no raw exception/credential dump',file=sys.stderr)
        raise SystemExit(2)
