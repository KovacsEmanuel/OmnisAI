# Owner Stop-only — remedieri R1–R4

Scope exclusiv worktree `omnis-sl04-owner-integration`, branch
`sl04-stop-owner-integration`, bază `97d6c4f0cded396616098d8c3f631e6e84c3bd77`.
Raport final scoped; **nu aprobă SL04**, nu integrează în main. Reviewul independent
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

## R4 — cleanup independent, diagnosticul inițial păstrat

`run_stop_owner` păstrează excepția inițială, închide ambele canale independent,
închide pidfd în finally exterior și încearcă reap bounded după eșec de semnal.
Eșecul primului wait nu sare peste semnal/reap. Cleanup-ul eșuat adaugă
`STOP_OWNER_CLEANUP_UNCERTAIN`, nu maschează motivul inițial și nu produce succes.
Dacă nu exista eroare inițială, cleanup incert produce STOP_OWNER_UNCERTAIN/4.
Niciun fallback PID numeric și niciun LOCK_UN/OFD reopen.

Test permanent nou `cli/tests/test_stop_owner_cleanup.py`:

- ACK child propriu, originalele FD moștenite; ținut viu pe pipe-ul observerului,
  alarmă 12s numai ca fuse de ultimă instanță. Observerul deține pidfd independent
  înainte de handoff, nu împrumută handle-ul produsului după eroare.
- Signal OSError, al doilea wait OSError și primul wait OSError sunt cazuri separate.
  În cazurile wait syscall-ul de semnal este explicit no-op ca să nu lase moartea
  procesului să ascundă lipsa reap-ului. Nu este semnal fizic de produs reușit.
- În toate trei: două wait-uri bounded încercate, canale închise, pidfd fără leak,
  motiv inițial STOP_OWNER_TIMEOUT/4 + nota UNCERTAIN, PREPARED, zero mutații;
  copil încă viu la observație. Observerul face SIGKILL real, citește
  `waitid(P_PIDFD)` CLD_KILLED/SIGKILL, reap=-9 și apoi ECHILD. Rescue-ul nu este
  creditat ca succes al produsului.
- RED înainte de cod: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_stop_owner_cleanup.py -v`
  → exit1/3 failures, `r4-red.log`; fiecare a verificat rescue/reap înainte de FAIL.
- GREEN aceeași comandă → exit0/3 teste, `r4-green.log`; ulterior aserțiunea notei
  UNCERTAIN a fost inclusă în toate gate-urile finale de mai jos.

R3 commit: `a017909282a4b0e98ffc648e23741f01212b3b51`. R4 este commitul care
conține această secțiune și testul cleanup; SHA-ul se citește prin
`git log -1 --format=%H -- cli/tests/test_stop_owner_cleanup.py` (fără auto-referință).

## Gate-uri finale după ultima editare de cod/test

Toate rulările au umask077 și TMPDIR scratch. Interpretoare Python3.13.15,
Ruff0.16.9, mypy2.3.1, uv0.12.19. Comenzile/exits/logurile integrale sunt salvate
și în `owner-r1r4-evidence/commands.jsonl`; raportul păstrează rezultatele importante
independent de retenția scratchului.

```sh
# cwd worktree owner; P=cli/.venv/bin/python, Q=api/.venv/bin/python
$P -I -B -m unittest discover -s cli/tests -p 'test_stop_*.py' -v
# exit0, 23 teste OK; final-targeted.log
$P -I -B -m unittest discover -s cli/tests -v
# exit0, 201 teste OK; final-source.log
$Q -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests
# exit0; final-ruff.log
$Q -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests
# exit0, 48 fișiere deja formatate; final-format.log
env -u PYTHONPATH -u MYPYPATH $Q -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json cli/src
# exit0, fără diagnostice; final-mypy.log
```

Wheel nou, construit după ultima editare și instalat într-un venv nou, fără rețea:

```sh
UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
E=/home/kali/.hermes/cache/scratch/owner-r1r4-evidence
$UV build --no-config --offline --wheel cli --out-dir "$E/dist"
$UV venv --no-config --no-python-downloads --python 3.13.15 "$E/wheel-env"
$UV pip install --no-config --offline --python "$E/wheel-env/bin/python" --no-deps "$E/dist/omnis_cli-0.1.0-py3-none-any.whl"
# toate exit0; wheel-build.log, wheel-venv.log, wheel-install.log
# cwd extern $E:
$E/wheel-env/bin/python -I -B /home/kali/.hermes/cache/scratch/owner-r1r4-artifact.py
$E/wheel-env/bin/python -I -B -m unittest discover -s /home/kali/.hermes/cache/scratch/omnis-sl04-owner-integration/cli/tests -v
$E/wheel-env/bin/python -I -B /home/kali/.hermes/cache/scratch/owner-r1r4-artifact.py
# exit0/0/0; 201 teste OK; wheel-provenance/final-wheel/wheel-stable-inputs.log
```

Proveniență verificată: import din `wheel-env/lib/python3.13/site-packages`,
19 module identice byte-for-byte sursă → wheel → instalare; 48 intrări sursă/test
stabile între începutul și sfârșitul gate-ului wheel. Numărătoarea logurilor a fost
recalculată programatic: 201 nume unice, aceleași în sursă și wheel; 23 targeted,
fără ResourceWarning/FAIL/ERROR. Nu sunt 402 teste distincte.

| Artefact | SHA256 |
|---|---|
| `dist/omnis_cli-0.1.0-py3-none-any.whl` | `c0e0c1b7c88a68dc7d861277d40671788a5765b9f60919a093db648227a948a3` |
| `stop_owner.py` | `3a6c84b00894aaa4bd75fe14c9415ae570581aa3d2c5810d486099020957ec9b` |
| `stop_engine.py` | `d8d99cf01f8bd71c1d3fb032b5077d2f648f7a622464cf572fd92e2e3116445f` |
| `stop_receipt.py` nemodificat | `286d82f827b1a755b8315ca999cfe1173adae5f36fe592e0477b768faf727e79` |

Reproducerul părintelui, nemodificat, a fost rerulat de implementer pe bytes noi:

`cli/.venv/bin/python -I -B /home/kali/.hermes/cache/scratch/owner-review-97d6c4f-probes.py MODE`

MODE `offline_schema`, `null_absence`, `headers`, `fd_cleanup`,
`no_effect_without_grant` → **exit0 fiecare**; loguri `parent-probe-MODE.log`.
Nu se pretinde review independent doar pentru rerularea acestor probe. R1 are zero
requesturi noi pe fiecare refuz; R2 null refuzat, 404 absent păstrat; R3 toate
supradimensionările refuzate; R4 nu pierde pidfd și păstrează TIMEOUT/4, cu rescue
verificat; granturile invalide și fsync failure au zero efect.

Self-review diff: doar două module produs, teste și acest raport; scanul liniilor
adăugate pentru shell=True/os.system/eval/pickle/SQL interpolat nu are match.
Fără oracle modificat, fără modificare grant/issuer UUID. Re-review independent
al părintelui este încă necesar, nu APPROVED_SCOPED implicit.

Documentare: `python scripts/render_docs.py --check` → exit0;
`python -m unittest discover -s tests/documentation -v` → exit0/62 teste OK
(`docs-render.log`, `docs-tests.log`). Nu s-a modificat Markdown normativ/HTML.
După gate-urile produsului s-au schimbat numai notele de verificare, nu codul,
testele sau artefactul. `git diff --check` → exit0.

## Predare / NOT_RUN

| Perimetru | Cod / probe | Review / limită |
|---|---|---|
| P0.1–P0.3, SL01–SL03 | Neschimbate; credit istoric netransferat | Nu se redeschid/arbitrează aici |
| **AICI: R1–R4 owner neactivat** | Implementate; RED→GREEN; source201/wheel201/targeted23 | Părinte: re-review pe SHA final |
| SL04 integrare Stop/Start | PARTIAL, neactivată în acest scope | NOT_RUN: grant DB real, fence/reconcile, Docker/cgroup/PG |
| S04–S06 fizice | NOT_RUN | Nu certifică ACK/drain Docker, crash/fsync cuts, sentinel PG |
| G00/M03/M22/CI remote | Niciun credit nou | Rămân deschise |
| P1/runtime/provider/target | În afara scopului, NOT_RUN | Niciun efect sau trafic |

Reticle NOT_APPLICABLE (CLI/procese); Chisel BLOCKED/NO-GO, neexecutat.
`make check`, `check-installed-start`, `check-installed-pair-open`,
`check-installed-stop`: NOT_RUN aici (interzise); gate-urile fizice sunt ale
părintelui. Nicio integrare în main, niciun push, nicio aprobare SL04.
Lecția generică signal/reap/finally a fost păstrată în skillul
`local-service-lifecycle`, fără modificare a altui profil sau checkout produs.
Rollback numai prin reverturile locale în ordine inversă; Git nu reconciliază DB.
