# B06b — consumer determinist al publicării

## Contract și autoritate

Bază: `4737154949404cd933af75c6d3a5f99a9159e65a`. Operatorul a cerut verificarea lucrului anterior și continuarea implementării către închiderea fazei 2. Aceasta extinde mandatul de dezvoltare, nu autorizează conturi, costuri de inferență, ținte, rollout/r1, schimbări globale sau push. Ordinea rămâne plan §7–8; P2-live cere acord separat cont/model/buget. Niciun plan concurent.

Auditul read-only `deleg_9c9aa31a` nu a identificat un blocker nou C01: părintele a verificat 43/43 hashes din receipt și digestul logului canonical; reviewerul a verificat suplimentar hashul agregat, artefactul QA și consumerii/testele. Nu se relansează canonicalul C01 neschimbat. Testele principale inspectate folosesc procese CLI/PTY și PostgreSQL reale; probele mock/fault sunt delimitate în sursă. Acceptarea rămâne scoped, nu garanție universală.

## Felia observabilă

Un snapshot `CONTRACT_PROBE` al publicației exacte → ExecutionSelection `NO_MODEL/effective=null` persistentă → execuția reală a recipe-ului PURE pe input nou → output/receipt persistente → readback și replay din proces nou, fără repetarea executorului după succes comis. Arhitectură §9.9 permite parser/PURE fără copil; **acest consumer intermediar nu este Task/Attempt/TaskResult/MethodCheck și nu închide C02 integral, C03–C12, H03–H08 sau B06b/G02**.

Intrare: modulul Python `omnis.modules.runs.pure_probe`, operații `select/execute/readback`, aceleași `--request`, `--catalog-root` și canal privat DB ca publisherul. Nu se inventează `omnis run` și nu se modifică UI/readiness.

- `select`: schema_version=1, owner_id, command_id, snapshot_ref de tip run-snapshot, recipe_key.
- `execute`: schema_version=1, owner_id, command_id, selection_ref de tip execution-selection, input obiect.
- `readback`: schema_version=1, owner_id, receipt_ref de tip pure-probe-receipt.
- Selection payload exact §9.9: snapshot_ref, recipe_key, selected_package_refs, requested, effective=null, resolution=NO_MODEL, reason=CONTRACT_PROBE_PURE, compatibility_receipt_refs=[]. Lipsa preferinței folosește defaultul explicit al compilerului, nu profilul personal.
- Receipt: selection_ref, input_ref, executor_revision, status=COMPLETED, outputs cu step_id/output/digest. Nu PURE_PASS de calificare ori succes Task.
- Select este comis înainte de execuție. Execute scrie input/receipt/comandă atomic sub lock owner; replay conflict refuzat. Succes returnat după recitire. Crash pre-commit poate necesita recomputare PURE; nu se promite exactly-once execution.
- Refolosire: ledgerul existent/schema0010, publicarea cu revalidare, compilerul pinned și executorul PURE. O singură recipe/procedură sunt suportate acum. Nu modificăm cele nouă BEHAVIOR_FILES pentru această felie și nu transferăm calificări peste bytes modificați.

## Ownership și verificare

Arhitect read-only: `deleg_9c9aa31a`, contract adjudecat de părinte. Doi dezvoltatori în worktree-uri noi din HEAD local:

- A: `api/src/omnis/modules/runs/pure_probe.py`, `api/src/omnis/modules/tasks/execution_selection.py`, seam minim `catalog_publication.py`; test unit propriu `api/tests/test_b06b_pure_probe_unit.py` pentru RED→GREEN înaintea produsului.
- B: `api/tests/test_b06b_pure_probe_contract.py`, `api/tests/test_b06b_pure_probe_pg.py`, fixture nouă `api/tests/fixtures/b06b_pure_probe/consumer.py`, target explicit în `Makefile` și allowlist/dry-run în `ops/run_test_db_gate.py`.
- Părinte: integrare byte-exact, probe PG, documentare, commituri. Fără adoptarea worktree-urilor istorice ori citirea originalului HTML neversionat.

Acceptare: input nou produce output real diferit de evaluarea calificării; refs/pins/NO_MODEL exacte; readback și replay CLI; niciun rerun după commit; concurență cu overlap PG observat; owner/ref/recipe/override/invalid input și material modificat refuzate; rollback fără receipt parțial. Validarea strictă precede replayul. Testele nu înlocuiesc executorul în pozitiv.

Comenzi afectate: noul target `test-b06b-pure-probe-pg` prin runnerul privat existent, Ruff/mypy, două reviewuri complementare pe snapshot exact și QA independentă pe wheel instalat `--link-mode copy`/PG real. Canonicalul rulează numai pe produsul final, nu la fiecare citire/remediere. Reticle NOT_APPLICABLE (CLI); Chisel NO_GO, neexecutate.

Resurse: numai PostgreSQL nou atestat UDS/no-network, familie urmărită și cleanup exact; PGDATA/loguri păstrate. Before: nicio resursă a acestei felii. After așteptat: CID/rețele/socket proprii absente, date păstrate. Fără DB de operator, migrare r1 sau ștergere date. Rollback cod: revert granular; nu inversează scrieri DB. Receipturile sintetice sunt păstrate, schema nu se downgradează.

## Stare

Contract adjudecat; implementare și dovezi încă în lucru. Fără PASS anticipat.
