"""Existing-runner child: installed API, owned local browser, exact cleanup."""
import sys
sys.dont_write_bytecode = True
import os, json, pathlib, subprocess, socket, time, signal, selectors, traceback
from uuid import uuid4
Q=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/home/kali/OmnisAI')
cfg=json.loads((Q/'dispatch.json').read_text()); attestation=json.loads((Q/'preflight.json').read_text())
assert cfg['acceptance']['verdict']=='APPROVED_SCOPED' and cfg['acceptance']['launch_authorized'] is True
PY=cfg['api_python']; NODE=str(pathlib.Path(cfg['tools_bin'])/'node'); WEB=pathlib.Path(cfg['web_root'])
os.umask(0o077)
sys.path.insert(0,str(R/'api/tests'))
sys.path.append(str(R/'api/.venv/lib/python3.13/site-packages')) # pytest helper only; no pth processing
from conftest import connect_test_database,verify_test_database
from e2e_processes import owned_children,cleanup_all,_identity
from sqlalchemy.engine import make_url
from psycopg import sql
import httpx,omnis.api
assert pathlib.Path(omnis.api.__file__).parent==pathlib.Path(attestation['installed_root'])
report={'snapshot':cfg['acceptance']['snapshot'],'wheel_sha256':cfg['api_wheel_sha256'],'actual_api_module':str(omnis.api.__file__),'commands':[],'resources':[],'cleanup':{},'errors':[],'status':'RUNNING'}
def persist(): (Q/'journey.json').write_text(json.dumps(report,indent=2))
base={'PATH':os.environ['PATH'],'HOME':str(Q/'home'),'TMPDIR':str(Q),'PYTHONDONTWRITEBYTECODE':'1','XDG_CACHE_HOME':str(Q/'home/.cache'),'XDG_CONFIG_HOME':str(Q/'home/.config'),'XDG_DATA_HOME':str(Q/'home/.local/share')}
def cmd(args,env,timeout=30):
    p=subprocess.run(args,cwd=Q,env=env,capture_output=True,text=True,timeout=timeout)
    report['commands'].append({'argv':args,'cwd':str(Q),'exit':p.returncode})
    (Q/f'command-{len(report["commands"])}.private.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0,'Command failed; private log retained'
url=make_url(os.environ['OMNIS_TEST_DATABASE_URL']); dbname='omnis_p01_'+uuid4().hex; db=url.set(database=dbname)
created=False; processes=[]; listener=None; restart=None; logs=[]; port=None
readfd,writefd=os.pipe();os.set_blocking(readfd,False)
try:
    receipt=verify_test_database(url)
    report['fixture']={**receipt.model_dump(),'root':str(pathlib.Path(os.environ['OMNIS_TEST_FIXTURE']).parent)}
    report['database']=dbname
    with connect_test_database(url,autocommit=True) as c:
        verify_test_database(url); c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname))); created=True
    env={**base,'OMNIS_DATABASE_URL':db.render_as_string(hide_password=False),'OMNIS_CONTROL_DIR':str(Q/'ipc'),'OMNIS_WEB_ROOT':str(WEB),'OMNIS_EXPECTED_SYSTEM_ID':receipt.system_identifier}
    cmd([PY,'-I','-B','-m','omnis.migrate','--initialize'],env)
    with connect_test_database(db) as c:
        report['schema']=c.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        assert report['schema']==cfg['schema']
    with owned_children() as family:
        try:
            sup=subprocess.Popen([PY,'-I','-B','-m','omnis.supervisor'],cwd=Q,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            processes.append((sup,False)); report['resources'].append({'role':'supervisor','pid':sup.pid,'identity':_identity(sup.pid)})
            assert sup.stdout is not None
            with selectors.DefaultSelector() as sel:
                sel.register(sup.stdout,selectors.EVENT_READ); assert sel.select(12); assert sup.stdout.readline().strip()=='SUPERVISOR_READY'
            listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(16)
            port=listener.getsockname()[1]; origin=f'http://127.0.0.1:{port}'; report['origin']=origin; restart=listener.dup()
            def launch(sock):
                args=[PY,'-I','-B','-m','uvicorn','omnis.api:create_app','--factory','--fd',str(sock.fileno()),'--no-access-log','--no-proxy-headers','--log-level','warning','--timeout-graceful-shutdown','3']
                p=subprocess.Popen(args,cwd=Q,env={**env,'OMNIS_HTTP_PORT':str(port)},pass_fds=(sock.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                processes.append((p,False)); report['resources'].append({'role':'api','pid':p.pid,'identity':_identity(p.pid),'argv':args}); persist()
                deadline=time.monotonic()+15
                with httpx.Client(base_url=origin,trust_env=False,timeout=1) as h:
                    while time.monotonic()<deadline:
                        assert p.poll() is None,'API early exit'
                        try:
                            r=h.get('/health/ready')
                            if r.status_code==200 and r.json()['dashboard_ready']:
                                assert r.json()['assessment_ready'] is False
                                report.setdefault('readiness',[]).append({'pid':p.pid,**r.json()}); return p
                        except httpx.TransportError: pass
                        time.sleep(.1)
                raise AssertionError('Readiness deadline')
            api=launch(listener); listener.close(); listener=None
            with httpx.Client(base_url=origin,trust_env=False,timeout=3) as h:
                assets=[]
                for rel,digest in cfg['web_files'].items():
                    target='/' if rel=='index.html' else '/'+rel
                    res=h.get(target)
                    if rel=='omnis-web.json':
                        report['manifest_http_status']=res.status_code; continue
                    assert res.status_code==200 and res.content==(WEB/rel).read_bytes()
                    assets.append({'path':target,'sha256':digest,'status':res.status_code})
                report['http_asset_bindings']=assets
            for stage in ['before','after','supplement']:
                if stage=='after':
                    api.terminate(); logs.extend(api.communicate(timeout=8)); assert api.returncode==-signal.SIGTERM
                    oldpid=api.pid; api=launch(restart)
                    report['restart']={'old_api_pid':oldpid,'new_api_pid':api.pid,'same_database':True}
                script='supplement.mjs' if stage=='supplement' else 'driver.mjs'
                args=[NODE,str(Q/script),stage]
                driver=subprocess.Popen(args,cwd=Q,env={**base,'QA_ORIGIN':origin,'QA_MARKER_FD':str(writefd)},pass_fds=(writefd,),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
                processes.append((driver,True)); report['resources'].append({'role':'browser_driver','stage':stage,'pid':driver.pid,'identity':_identity(driver.pid)}); persist()
                output=driver.communicate(timeout=240); logs.extend(output)
                (Q/f'driver-{stage}.private.log').write_text(''.join(output))
                report['commands'].append({'argv':args,'exit':driver.returncode}); persist()
                browser_receipt=Q/f'browser-{stage}.json'
                assert driver.returncode==0 and browser_receipt.is_file(),'Browser stage failed'
                assert json.loads(browser_receipt.read_text())['browser_closed'] is True
            report['status']='PASS_SCOPED_AUTOMATED_PENDING_SCREENSHOT_INSPECTION'
        finally:
            try:
                logs.extend(x for pair in cleanup_all(processes,ownership=family) for x in pair)
                report['cleanup']['family_drained']=True
            finally:
                if listener: listener.close()
                if restart: restart.close()
            report['cleanup']['processes']=[{'pid':p.pid,'exit':p.returncode,'absent':_identity(p.pid) is None} for p,_ in processes]
            report['cleanup']['control_socket_absent']=not (Q/'ipc/control.sock').exists()
            listening=[]
            if port is not None:
                for path in ['/proc/net/tcp','/proc/net/tcp6']:
                    for line in pathlib.Path(path).read_text().splitlines()[1:]:
                        f=line.split()
                        if f[3]=='0A' and int(f[1].split(':')[1],16)==port: listening.append(path)
            report['cleanup']['port_listener_absent']=not listening
            assert not listening and all(r['absent'] for r in report['cleanup']['processes'])
            assert report['cleanup']['control_socket_absent']
except BaseException as exc:
    report['status']='FAIL'
    report['errors'].append({'type':type(exc).__name__,'trace_frames':[{'file':f.filename,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(exc.__traceback__)]})
finally:
    os.close(writefd)
    try: markers=os.read(readfd,65536)
    finally: os.close(readfd)
    secret_values=[x[7:] for x in markers.decode().splitlines() if x.startswith('SECRET ')]+[url.password or '']
    private_artifacts=[p for p in Q.glob('*.private.log')]+list(Q.glob('browser-*.json'))+list(Q.glob('*-failure-dom.txt'))
    combined=''.join(logs)+json.dumps(report)+''.join(p.read_text() for p in private_artifacts)
    report['log_secret_check']=all(s and s not in combined for s in secret_values)
    try:
        if created and report['cleanup'].get('family_drained',not processes):
            verify_test_database(url)
            with connect_test_database(url,autocommit=True) as c:
                c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(dbname)))
                report['cleanup']['test_database_absent']=c.execute('SELECT datname FROM pg_database WHERE datname=%s',(dbname,)).fetchone() is None
        elif created: report['cleanup']['test_database_drop']='NOT_ATTEMPTED_UNSETTLED_FAMILY'
    except BaseException as exc:
        report['status']='FAIL';report['errors'].append({'cleanup_type':type(exc).__name__})
    report['retention']={'root':str(Q),'draft_snapshot':str(Q/'retained.json'),'pgdata':report.get('fixture',{}).get('root','')+'/data','note':'Only per-test DB dropped after family drain; runner retains cluster PGDATA; captures still require actual independent inspection.'}
    persist()
raise SystemExit(0 if report['status']=='PASS_SCOPED_AUTOMATED_PENDING_SCREENSHOT_INSPECTION' and report['log_secret_check'] and report['cleanup'].get('test_database_absent') else 1)
