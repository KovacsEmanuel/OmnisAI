# QA independentă instalată — PASS scoped

Snapshot: `bb760e5b9bf9256f1ca31036d8a395590f2c0507`, tree `724d5cb1736cc0def5e0d3eb25eaef18b1d848ec`. FREEZE `7f560b785f037e0fcee24a0368eab599e7fdca41669e23ba3121e6dcb163a625`; 33 bindings SHA identice înainte/după. CLI privat0.1.1 și CLI vechi0.1.0 reale, Docker/PostgreSQL reale, două fixture-uri fresh distincte.

| Selector exact, clasa `test_release.ReleaseBundleTest` | Rezultat din aceeași execuție | Proces |
|---|---|---|
| `test_t1_populated0016_upgrade_installed` | 1PASS, exit0, 156.108s unittest /156.244515s wall | `proc_6c97efa7c721` |
| `test_t1_upgrade_known_preopen_failure_restores_installed_snapshot` | 1PASS, exit0, 162.782s unittest /162.905250s wall | `proc_83edc10378e0` |

Total2PASS/0FAIL/0SKIP,318.890s consumer;495.185s de la baseline până la integritatea finală, sub buget1800s. Fiecare comandă a avut timeout840s+grace20s. Nu a fost rerulat niciun consumer.

Comenzile au fost două invocări separate, secvențiale:
```text
/home/kali/.hermes/cache/scratch/t1-cli-r1r2-bb760e5-venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py -k test_t1_populated0016_upgrade_installed -v
/home/kali/.hermes/cache/scratch/t1-cli-r1r2-bb760e5-venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py -k test_t1_upgrade_known_preopen_failure_restores_installed_snapshot -v
```
Cwd frozen worktree; argv complet cu timeout și mediul exact `env -i`, HOME/XDG/TMPDIR private, în `commands.json`. Preflight parser/import/selectori și `upgrade_preflight(options)` fără daemon/subprocess:PASS. Pinurile node24.21.0/npm11.19.0/Python3.13.15/uv0.12.19 confirmate.

## Ce demonstrează
- Upgrade0016 populat→0017 în DEVELOPMENT configurat; următorul Start este reused, config byte-equal; identități/PGDATA/seif/chei/caps/assignments păstrate.
- Backup nativ/trial restore; operație/dispatch/receipt/outcome tipizate settled, UNKNOWN istoric și usage KNOWN9/7 păstrate exact. Census pe proiecția0016 egal, noul câmp removal NULL. Refuzuri reale prin CLI instalat.
- Failure seam cunoscut înainte de OPEN în interpreterul instalat: rollback0016, failed-data quarantine, grant/startup byte-exact, callerii concurenți refuzați, restart explicit CLI vechi și istoric/census identice. Nu este probă de crash fizic sau rollback pe rezultat necunoscut.

## Cleanup și retenție
Ambele receipts `PASS/VERIFIED`, jurnale `STOPPED`. Readback separat prin ownerul existent și Docker selected-fields/noEnv, același daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`:17CID-uri exacte absente, zero containere/rețele ale celor două proiecte, forwarderele PID/start_ticks absente, porturile34327/57925 fără listener și IPC/capabilities absente. Familii observator drained; fără rescue distructiv.

- Upgrade: `omnis-local-faa2b6c553ea4258b78a46039a53e481`, receipt `t/s4-k1zjkj8s/probe-receipt.json`.
- Rollback: `omnis-local-d698c3a1ff894ae4b0f6399c005e59df`, receipt `t/s4-cjjh4xq9/probe-receipt.json`.
- `cleanup-readback.json` conține toate ID-urile exacte, jurnalele, snapshoturile, carantina și cele4imagini proprii păstrate. Date/loguri/chei sintetice/backupuri/source copies păstrate pentru adjudecarea părintelui, fără ștergerea DB.

## Artefacte și incidente
Root privat: `/home/kali/.hermes/cache/scratch/q1-vnvrbh4o`. Raport JSON:`result.json`; comenzi:`commands.json`; raw:`upgrade.raw.log`,`rollback.raw.log`; rezumate/durate:`upgrade-result.json`,`rollback-result.json`; integritate:`integrity-final.json`.

Numai tooling, fără FAIL de consumer: importul read-only inițial `_POSTGRES_IMAGE` corectat la `POSTGRES`; prima lansare exit127 deoarece `/usr/bin/time` lipsește, înainte de Python/fixture, raw păstrat; o expresie inline de readback cu SyntaxError corectată înainte de execuție. S-a folosit ceasul bash existent, fără runner nou, instalare sau schimbare de produs.

Fără modificări produs/test/harness, commit sau integrare; tracked diff gol, symlinkurile preexistente păstrate și main încă `06040a97e1066e5faf8807c7410a9315d40b1811`. SOURCE approvals nu sunt reemise; QA scoped nu închide poarta globală.

Neexecutate: operator/provider/Refresh/model/target, browser/UI, canonical și suita largă release; Reticle NOT_APPLICABLE, Chisel BLOCKED_NO_GO.
Risc/limită: datele și4imagini QA sunt intenționat reținute; nu este validare de rollout/operator sau recuperare din efecte necunoscute.
