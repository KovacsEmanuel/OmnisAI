# R1 — review independent SOURCE, snapshot 4044fa9

## Verdict

**CHANGES_REQUESTED_SCOPED; nu admit încă cei doi selectori installed-QA în forma înghețată.** Nu cer ca QA să fi trecut deja: există un regres concret în callerul Stop0016 și un oracle de succes incompatibil determinist cu migrarea intenționată. Remediile sunt locale; SOURCE aprobat pe scope-ul neschimbat Remove nu este redeschis. Integrarea/rollout/închiderea aparțin părintelui, nu acestui raport.

Snapshot: `/home/kali/.hermes/cache/scratch/t1-upgrade-20261029`, HEAD `4044fa952cadae8d491f215d62551b11e488065f`, tree `e83286037bfabf6a100d818bb98bccc84d1cda9c`, base `ed611aa40c90f62f4f511cc1951a68970e2ba51b`.
FREEZE SHA256 verificat `fa2f1953d0afa53b65f646e86d2698ece96a6dbf0503e6a5432b93ab8bff9515`; toate cele29 SHA SOURCE corespund. Bundle nou parsabil, cele10 payloaduri corespund manifestului; manifestul vechi0016 este parsabil. Modulele upgrade/start executate din wheelul privat sunt byte-identice cu sursa frozen. Main/operator nemodificate.

## Findings

### R1-01
- **severity:** HIGH
- **file:line:** `cli/src/omnis_cli/stop_owner.py:60–67` (schema pierdută în `_View`; consumatorul este `:569`, `_static(view,...)`; comparația dependentă nouă în `cli/src/omnis_cli/start.py:1026–1029`).
- **reproducer:** O instanță validă release0.1.0/schema0016 cu runtime-ul nou încărcat are `runtime.schema='0016_provider_models'`. `_bound_instance(runtime,...)` o admite; `_View(runtime,engine)` nu copiază `schema`, iar `_bound_instance(view,...)` cade pe `EXPECTED_SCHEMA='0017_model_removal'`, refuzând aceeași identitate cu `RECOVERY_REQUIRED`, code4. Stop owner folosește tocmai acest view la `prepare(stage)` înaintea etapelor de teardown; noul CLI nu poate retrage normal instalația0016 după ce a admis grantul. Reprodus fără DB/Docker, pe fixture SOURCE existentă, cu control pozitiv pe runtime-ul original și negativ pe view; ieșire: `positive: original0016 runtime binding accepted`, `view preserves schema: None`, `negative: Stop owner view rejects same0016 binding RECOVERY_REQUIRED 4`.
- **violatedcriterion:** Arhitectură MAIN§5.5: CLI-ul tranziției admite citirea/**retragerea**/backupul instalării0016; callerii Stop existenți trebuie păstrați, fără a crea RECOVERY_REQUIRED artificial.
- **minimalremedy:** Păstrează schema admisă în `_View` în același loc cu release/digest/receipt, fără a relaxa `_bound_instance`. Un test SOURCE pe Stop owner/view cu0016 trebuie să distingă binding valid de schema greșită; affected Stop/source test, apoi focused re-review.

Reproducer inert executat (interpreter privat0.1.1, `-I -B`):
```python
import sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('cli/tests').resolve()))
import test_cold_backup as f
from omnis_cli.lifecycle import write_record,StartError
from omnis_cli.start import _bound_instance
from omnis_cli.stop_owner import _View
from omnis_cli.start_runtime import POSTGRES
with f.ColdBackupTest().source() as (_base,root,stopped,runtime):
    runtime.schema='0016_provider_models'
    runtime.pg_image=POSTGRES
    raw=json.loads((root/'instance.json').read_text())
    raw['schema']=runtime.schema
    write_record(root/'instance.json',raw,replace=True)
    control=Path(stopped['control_dir'])
    _bound_instance(runtime,root,control,stopped)  # control pozitiv
    view=_View(runtime,SimpleNamespace(deadline=runtime.deadline))
    assert getattr(view,'schema',None) is None
    try:
        _bound_instance(view,root,control,stopped)
    except StartError as e:
        assert (e.reason,e.code)==('RECOVERY_REQUIRED',4)
    else:
        raise AssertionError('Regresia nu s-a reprodus')
```

### R1-02
- **severity:** HIGH (oracle installed-QA, nu dovadă că produsul corupe datele)
- **file:line:** `cli/integration/installed_stop.py:400–403` și `:662–669`.
- **reproducer:** Selectorul `test_t1_populated0016_upgrade_installed` introduce o intrare nenulă în `provider_model_entry` în setupul SQL imediat anterior censusului, calculează înainte `md5(string_agg(to_jsonb(t)::text,...))`, apoi compară aceeași expresie după0017. Migrarea frozen `api/src/omnis/migrations/versions/0017_model_removal.py:15–16` adaugă coloana `removed_registry_revision`; JSONB al fiecărui rând după upgrade include noul câmp null. Digestul comparat nu mai reprezintă aceeași proiecție, chiar când toate datele vechi sunt păstrate. Calea pozitivă va eșua la acest tabel după un upgrade perfect corect. Confirmare SOURCE prin perechea query/DDL exactă; reproducerea PG nu a fost executată, fiind exclusă explicit din mandatul reviewerului.
- **violatedcriterion:** CONTRIBUTING§Preflight fără efecte și planMAIN§8: oracle-ul trebuie să corespundă producerului real; prima QA bounded trebuie să poată distinge un upgrade corect de pierderea datelor, nu să consume ciclul într-un mismatch de schemă cunoscut.
- **minimalremedy:** Pentru acest tabel compară explicit coloanele0016 pe ambele părți (sau scoate numai noul câmp din proiecție), plus assert separat că intrările anterioare au `removed_registry_revision IS NULL`; păstrează comparația exactă pentru celelalte tabele. Un control SOURCE al proiecției înainte/după este suficient înaintea următoarei QA reale; nu e nevoie de alt harness.

Reproducer SQL minimal de folosit într-o fixture deja admisă, NU executat aici:
```sql
WITH old_row AS (
 SELECT 'synthetic/upgrade'::text AS model
), new_row AS (
 SELECT model,NULL::bigint AS removed_registry_revision FROM old_row
)
SELECT (SELECT to_jsonb(t) FROM old_row t),
       (SELECT to_jsonb(t) FROM new_row t),
       (SELECT md5(to_jsonb(t)::text) FROM old_row t)
       = (SELECT md5(to_jsonb(t)::text) FROM new_row t) AS same_digest;
```

### R1-03
- **severity:** MEDIUM (gol concret al oracle-ului solicitat)
- **file:line:** `cli/integration/installed_stop.py:353–408`, `:619–627`, `:661–669`.
- **reproducer:** Fixture-ul nou creează numai connection/model/registry/entry-revision/selection și sentinel. Nu creează niciun ModelTestV2/operație/dispatch/event istoric înainte de snapshot. Tabelele `model_record_v2`, `system_operation`, `model_command_v2`, `model_dispatch_v2`, `model_dispatch_event_v2`, `system_operation_event` sunt doar incluse în census. Pe această fixture fresh fără Test/provider, ele sunt goale; pierderea tuturor rândurilor istorice ar avea aceeași observație ca păstrarea lor. Atât upgrade, cât și rollback pot trece aceste comparații fără a proba vreun operationID/rezultat/usage istoric. Acesta este un gol SOURCE demonstrabil în setup, nu o cerere ca QA să fi trecut deja și nu o afirmație de corupere în produs.
- **violatedcriterion:** Mandat§3/§5/§9 și arhitecturăMAIN§5.5: aceeași instanță/date/chei/**istoric**; însăși sarcina R1 cere ca installed consumer să poată valida istoricul/same-ID/rollback.
- **minimalremedy:** Refolosește producerul/fixture-ul existent pentru un singur istoric ModelTestV2 settled nenul, cu ID și rezultat/usage/receipt cunoscute, fără provider IO. Assert non-empty înainte, exact aceleași ID-uri/payloaduri după upgrade și după rollback; nu adăuga matrice universală, owner sau harness nou.

## Scope citit și probe efectiv executate

Contract: mandatul finalizării, README CURRENT și SL12/SL33 din main, arhitecturăMAIN§5.5/planMAIN§8; AGENTS/CONTRIBUTING/team-slice și skills review/status/release/Ponytail. Delta29paths; focus upgrade/start/restart/stopowner/release/runtime/backup și oracle-ul instalat, migrare fizică/grant0016 și0017. Remove neschimbat nu a fost reaudit.

- `git status --short --branch`, diff/stat/check și HEAD/tree pe candidat: tracked curate, numai cele3 symlinkuri partajate preexistente. Main HEAD observat `06040a97e1066e5faf8807c7410a9315d40b1811`, cele2 untracked protejate doar în status, necitite/nehashete.
- `_manifest` pe ambele bundleuri,29SHA SOURCE,10SHA bundle, SHA FREEZE, byte equality upgrade/start wheel↔source: exit0.
- Interpreter privat: Python3.13.15 / omnis-cli0.1.1.
- `python -I -B -m unittest discover -s <candidate>/cli/tests -p test_upgrade.py -v`: **8PASS,0.241s,exit0**. Doubles explicite OCI/PG, nu installed QA.
- `python -I -B -m unittest discover -s <candidate>/cli/tests -p test_restart_wiring.py -v`: **12PASS,1.497s,exit0**. Reconcile-before-supervisor/OPEN, old completion byte-exact și lost-ACK no-resend sunt SOURCE, nu probe OCI live.
- Compilarea AST a seam-ului exact de failure installed: PASS; nu a fost executat seam-ul/efectul.
- R1-01 control pozitiv/negativ de mai sus: exit0, regresie reprodusă.

Ordinea intent-before-effect, migrare separată0016 fără consumarea grantului, reconcile nou înainte de supervisor/OPEN, quarantină+restore absent/same-digest și refuzul rollbackului OPEN_PENDING/necunoscut sunt reprezentate în cod/testele SOURCE citite; nu am găsit alt blocker R1 confirmat în acestea. Asta nu este runtime PASS și nu înlocuiește reviewul complementar R2.

Creat numai acest raport original în scratch; niciun fișier de produs/config modificat, niciun commit. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Neexecutate: DB/Docker/build/browser/provider/operator/upgrade real/rollback real/canonical; nu certific istorii vechi neverificate sau întreaga siguranță/concurență (R2). Riscul rămas: callerul Stop0016 și oracle-ul trebuie corectate înaintea primei QA bounded; apoi dovada instalată rămâne de produs, nu prerechizit circular.
