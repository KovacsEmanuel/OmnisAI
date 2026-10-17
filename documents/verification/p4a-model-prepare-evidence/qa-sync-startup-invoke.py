"""Invoke only the approved existing run_gate selection seam once."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

os.umask(0o077)
R=Path('/home/kali/OmnisAI'); Q=Path('/home/kali/.hermes/cache/scratch/ms-xxfxw95l')
TEST='f612941716b889ca53b3e0d6f3a92c4e2a3b4936269068eaab32e819d86a08fa'
UV=Path('/home/kali/.local/share/omnis-toolchains/uv-0.12.19')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sys.dont_write_bytecode
assert sha(R/'api/tests/test_contract_method_pg.py')==TEST
assert json.loads((Q/'preflight.json').read_bytes())['status']=='PASS_NO_EFFECT_CURRENT_PREREQUISITES'
assert all(sha(R/n)==h for n,h in json.loads((Q/'before.json').read_bytes()).items())
assert all(sha(Path('/home/kali/.hermes/cache/scratch/mp-_i844ny7/prepared')/n)==h for n,h in json.loads((Q/'closure-before.json').read_bytes()).items())
assert Path(os.environ['TMPDIR']).resolve(strict=True)==Q/'t'
assert Path(os.environ['HOME']).resolve(strict=True)==Q/'home'
assert not list((Q/'t').glob('db-*')) and not (Q/'t/mtp').exists()
assert not any(k.startswith('OMNIS_BATCH2_') for k in os.environ)
final=json.loads((R/'documents/verification/p4a-model-prepare-evidence/sync-startup-version-fixture-author.json').read_bytes())['final_files']
assert len(final)==6 and all(sha(R/row['path'])==row['sha256'] for row in final)
assert all(sha(R/row['path'])==row['sha256'] for row in json.loads((Q/'reader.json').read_bytes())['current']['files'])
pins=json.loads((Q/'pins.json').read_bytes())
assert pins=={'OMNIS_BATCH2_NORMATIVE_REVIEWED':TEST,'OMNIS_BATCH2_INPUT_REVIEWED':TEST,'OMNIS_BATCH2_ARTIFACT':'/home/kali/.hermes/cache/scratch/mq-lseqdyzi/artifact.json','OMNIS_BATCH2_ARTIFACT_SHA':'3f44032637982ddd6b99ec7b3399dbf3f15d49cb1033cedefa4dcbd8e79a55e5','OMNIS_BATCH2_API_PREREQUISITES':str(Q/'reader.json'),'OMNIS_BATCH2_API_PREREQUISITES_SHA':'38774dd167b8da23480e8175545888855bc426c2b20817d79ad829afc98d811d'}
assert sha(Path(pins['OMNIS_BATCH2_ARTIFACT']))==pins['OMNIS_BATCH2_ARTIFACT_SHA']
assert sha(Path(pins['OMNIS_BATCH2_API_PREREQUISITES']))==pins['OMNIS_BATCH2_API_PREREQUISITES_SHA']
spec=importlib.util.spec_from_file_location('db_gate',R/'ops/run_test_db_gate.py'); runner=importlib.util.module_from_spec(spec); sys.modules[spec.name]=runner; spec.loader.exec_module(runner)
original_run_gate=runner.run_gate
record={'status':'ATTEMPT_INTENT','attempts':1,'timeout_seconds':180,'pins':pins,'test_sha256':TEST,'product_review_snapshot':'5ebfd02ecd1bdfb0f854018205227729f77cf7ef','head':'edafa6c8053231ab882cd93ddfcda64b533b00f7','original_owner':'ops/run_test_db_gate.py:prove_private_fixture/run_gate','selected_seam':'h03-process-fixed-pg-selection.py:253-265; same command/base copy plus six explicit pins/same log/same timeout','outer_owner_added':False,'product_edits':False,'gate_invocations':0}
def save(): (Q/'qa-attempt.json').write_text(json.dumps(record,indent=2)+chr(10))
def selected_gate(command,base,log,timeout_seconds):
    assert command==['make','--no-print-directory','test-model-test-prepare-native-pg',f'UV={UV.resolve(strict=True)}']
    assert timeout_seconds==180 and log.is_relative_to(Q/'t')
    assert not any(k.startswith('OMNIS_BATCH2_') for k in base)
    record.update(gate_invocations=record['gate_invocations']+1,command=command,gate_log=str(log),family_receipt=str(log.with_name(log.name+'.result.json')))
    assert record['gate_invocations']==1
    save()
    return original_run_gate(command,{**base,**pins},log,timeout_seconds)
runner.__dict__['run_gate']=selected_gate
save(); began=time.monotonic()
try:
    with (Q/'pg-owner.private.log').open('x') as output, contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        code=runner.prove_private_fixture('test-model-test-prepare-native-pg',str(UV),180)
    record.update(status='ORIGINAL_OWNER_RETURNED_REQUIRES_PRODUCT_AND_CLEANUP_READBACK',exit_code=code)
except BaseException as error:
    record.update(status='ORIGINAL_OWNER_EXCEPTION_REQUIRES_CLEANUP_READBACK',exception_type=type(error).__name__)
record['elapsed_seconds']=round(time.monotonic()-began,3); save()
print(json.dumps({k:record[k] for k in ('status','attempts','gate_invocations','exit_code','elapsed_seconds') if k in record}))
