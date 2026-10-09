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

Produsul inițial este comis în `bca03d7`. Integrarea PG inițială `proc_2cc6b37bde0a` a avut 32 PASS / 4 FAIL, exit2: răspunsul execute conținea câmpuri suplimentare și testul folosea un factory inexistent. Părintele a reparat forma contractuală și testul; oracle-ul revision folosește separat bytes consumerului + evaluatorul. `proc_6f0ed7f451d1`: 36 PASS în234s, exit0/family_drained=true, nouă hashes stabile, cleanup CID/rețele/socket exact și date păstrate. Nu este acceptare nativă sau canonical final.

### R1-PURE-01 — constatare reală și frontieră restrânsă

Reviewurile `deleg_b9276e81` au aceleași nouă hashes: safety APPROVED_SCOPED; compliance CHANGES_REQUESTED. R1 arată că `compile_catalog` reevaluează inputul calificării dependențelor RELEASE, inclusiv când este chemat de readback. Patchul doar pe aliasul `pure_probe.evaluate_pure` nu observa acest apel indirect. Părintele a reprodus componenta reală (o execuție pe fiecare dintre două compilări) și apoi **o publicație/snapshot reale pe PostgreSQL**: testul nou a eșuat `DID NOT RAISE`, exit1/12.36s (`proc_4dde810e73f0`). RELEASE extern este produsul test-only calificat B06a, local capture/review/freeze/eval/confirm/publish/snapshot sunt CLI reale; nu numim fixture-ul extern publicație de produs.

Decizie: consumerul intermediar admite numai seed-ul cu `dependency_artifact_refs=[]`. Refuză nonempty/missing/malformed înainte de `_readback`, cu `RELEASE_DEPENDENCY_NOT_SUPPORTED`; suportul RELEASE din catalog/C01 rămâne neschimbat. Aceasta restrânge explicit breadth-ul noii comenzi, nu elimină controale sau obligațiile B06b. Suportul viitor cere revalidare pinned fără execuție și probe proprii, nu simpla eliminare a guardului.

GREEN focalizat: `proc_9b0158497475`, două scenarii PG pe fixture nouă, exit0/drained: refuzul publicației cu dependență înainte de apelul PURE și replay/readback pozitiv fără dependențe, observând ambele aliasuri ale evaluatorului. Runnerul original de provisioning/atestare/cleanup este reutilizat; helperul scratch înlocuiește numai argv-ul testelor selectate, nu rezultatele/executorul. Cleanup exact/date păstrate. Formatarea ulterioară a dicționarului testului nu schimbă logica; canonicalul final va proba snapshotul final. Re-review focalizat și QA installed sunt încă în lucru; nu există închidere anticipată a feliei.

### Re-review și canonical final

Re-reviewul `deleg_5ec6b927` a închis **R1-PURE-01 / APPROVED_SCOPED** pe `14723a3`, cu12/12 bindings la commit. Safety original rămâne aprobat pe bytes lui, iar concluzia sa generală „fără rerun” este calificată de R1, nu folosită pentru a ignora reproducerul. Reviewerul a recitit privat dovezile RED/GREEN și a verificat guardul înainte de readback cu10 refuzuri și controlul `[]` (component seam, nu PG nou).

**Corecție de proveniență:** corpul commitului `14723a3` a scris eronat25.75s. Logul original și re-reviewul confirmă **2 PASS în24.25s**, exit0/drained. Istoria nu este rescrisă; acea durată din commit nu este folosită drept probă.

[Canonical final](p2-b06b-pure-canonical.json) pe `14723a3`, `proc_3e531ea9a2cb`: `make check` **exit0/family_drained=true**,616 fișiere versionate neschimbate,795API/23migrare/75web/9E2E,287CLI source+287wheel/61release/134runtime+6AST. Părintele a citit receiptul exact și hashuit logul, apoi a verificat independent absența CID/rețele/socket și păstrarea PGDATA. Commiturile documentare ulterioare nu schimbă produsul testat. QA independentă installed rămâne în curs; native/C02 integral/B06b/G02 nu primesc credit din acest PASS.
