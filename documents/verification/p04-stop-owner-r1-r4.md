# Owner Stop-only — remedieri R1–R4

Scope exclusiv worktree `omnis-sl04-owner-integration`, branch
`sl04-stop-owner-integration`, bază `97d6c4f0cded396616098d8c3f631e6e84c3bd77`.
Raport incremental; **nu aprobă SL04**, nu integrează în main. Reviewul independent
și Docker/PG real rămân ale părintelui. Oracle-ul, grantul (inclusiv `owner_uuid`),
IPC, cgroup și supervisorul nu sunt redesenate.

## Interfețe păstrate

`prepare_stop_inventory(runtime, root, control, record)`,
`verify_stop_completion(runtime, root, control, record, grant=None)` și
`run_stop_owner(runtime, root, control, record, grant, *, lock_fds, deadline=None)`.
Ambele lockuri/OFD originale, data → state; deadline monotonic absolut.
STOPPING valid cu `teardown_completed=[]` și receipt separat COMPLETED rămâne
recuperabil. Erorile nu acordă STOPPED, nu autorizează retry/fallback destructiv.

## R1 — validator Stop strict comun

`_static` folosește `_stopping_record`, fără schemă paralelă. Test permanent:
`cli/tests/test_stop_owner_review.py::test_offline_stop_journal_strict_before_engine`.
Pozitive STOPPING gol și STOPPED complet pe același fixture COMPLETED;
negative etape malformed/non-prefix/incomplete, generație divergentă/bool,
fază malformed și cheie necunoscută. Ambele frontiere publice refuză exit4 înainte
oricărei cereri Engine; jurnalul rămâne identic, fără mutație suplimentară.

Comenzi din root, umask077, loguri în
`/home/kali/.hermes/cache/scratch/owner-r1r4-evidence/`:

- RED înainte de cod: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_stop_owner_review.py -v`
  → exit1, 16 subcazuri failing (acceptare sau refuz tardiv după Engine), `r1-red.log`.
- GREEN: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p 'test_stop_*.py' -v`
  → exit0, 17 teste OK, `r1-green.log`.
- Ruff check scoped exit0. Format check inițial exit1 (o linie test), corectat cu
  formatterul pinuit; regresia se rerulează după formatare.

## Limite de autoritate / verificare

Fișiere, UDS/TCP, pidfd, semnale și copii proprii sunt reale. Engine și grantul
sunt sintetice; pozitivele complete substituie numai `_ContainerFamily` cu
`SyntheticFamily`. Nu reprezintă dovadă Docker/cgroup/PG. Niciun provider, target,
serviciu existent, push ori mutare de resurse istorice.

R2–R4 și gate-urile finale source/wheel/Ruff/format/mypy: în lucru.
Reticle NOT_APPLICABLE (CLI/procese); Chisel BLOCKED/NO-GO, neexecutat.
`make check` și gate-urile installed-start/pair-open/stop fizice: NOT_RUN aici.
Rollback numai prin reverturile locale în ordine inversă; Git nu reconciliază DB.
