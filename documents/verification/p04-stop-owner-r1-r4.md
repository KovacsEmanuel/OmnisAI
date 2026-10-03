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

## R2 — 200 inspect cere obiect, 404 rămâne distinct

Decoderul decide absența din status404 înainte de JSON; pentru `absent=True`
(endpointuri inspect) orice 200 non-obiect produce STOP_ENGINE_RESPONSE_INVALID.
Listele și politica ACK-urilor de mutație sunt neschimbate. Testul permanent
`test_inspect_null_is_not_absence_in_decoder_or_offline_consumer` trece 404,
200/obiect, 200/null/list/bool prin decoder și consumatorul offline pe același UDS;
faultul vizează exact inspect pe ID, nu listele. Nicio mutație după pozitivul inițial.

- R1 commit: `0a94e4fd4e33f32e5a6e218d354608e32800cbcf`.
- R1 după formatter: aceeași comandă focalizată → exit0/1 test, `r1-green-formatted.log`.
- R2 RED: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_stop_owner_review.py -k inspect_null -v`
  → exit1, null acceptat de ambele frontiere pentru ambele tipuri; liste/bool aveau
  diagnosticul generic INVALID_RECORD, `r2-red.log`.
- R2 GREEN: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p 'test_stop_*.py' -v`
  → exit0/18 teste OK, `r2-green.log`; Ruff check/format scoped exit0/0.

## R3 — buget întreg bloc status/headers

`line(limit)` verifică inclusiv delimitatorul pentru linii deja coalesced;
parserul scade statusul, fiecare CRLF și terminatorul gol din același 16384 bytes.
Test permanent: reason lung, câmp lung, multe câmpuri distincte, la 16383/16384/
16385/20500 bytes, atât un send coalesced cât și fragmente de 137 bytes. Positivele
la limita exactă trec; excesul refuză înainte de credit ACK, fără retry.

- R2 commit: `50ad705a039506e5a19b5cf44a0a18bfa872a0d1`.
- RED: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_stop_engine.py -k entire_status -v`
  → exit1, 7 subcazuri acceptau excesul, `r3-red.log`.
- Control înainte de cod: aceeași descoperire `-k wire_response_cap` → exit0,
  `r3-cap-control.log`, cap global exact 1048576 bytes inclusiv headers și +1.
- GREEN: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p 'test_stop_*.py' -v`
  → exit0/20 teste, `r3-green.log`; include 1MiB exact/+1, trickle deadline,
  chunked/nesting și 204 vs 304/404/500. Ruff check/format scoped exit0/0.

R4 și gate-urile finale source/wheel/Ruff/format/mypy: în lucru.
Reticle NOT_APPLICABLE (CLI/procese); Chisel BLOCKED/NO-GO, neexecutat.
`make check` și gate-urile installed-start/pair-open/stop fizice: NOT_RUN aici.
Rollback numai prin reverturile locale în ordine inversă; Git nu reconciliază DB.
