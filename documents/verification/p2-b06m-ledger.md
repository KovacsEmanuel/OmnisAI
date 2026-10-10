# B06m — checkpoint contabil, nu G-MODEL

**Stare curentă după continuarea serială:** READY_FOR_INTEGRATION accounting-only și READY_FOR_NEXT_HOLDER_INTEGRATION. [Proba PG finală](p2-b06m-pg-final.json) consemnează parent și QA independentă pe biblioteca sursă reală: 33 PASS fiecare (aceleași 23 unit + 10 PG, nu 66 teste unice), exit0/family_drained, inputuri fixate și cleanup exact. Secțiunile inițiale de mai jos păstrează cronologia PG_NOT_RUN, nu starea curentă a acestor zece criterii. Native/projection/fullSDK/installed consumer/Settings rămân NOT_INTEGRATED; SL11 PARTIAL și faza2 NOT_CLOSED.

## Livrat și nelivrat

Sursa inițială: `ae22022`. `policy/budgets.py` livrează nucleul PostgreSQL al ledgerului în schema0011 existentă: un buget per owner/run, carve-out VALIDATION în total, rezervare imuabilă, tranziții și receipturi append-only. Blocarea tranzacțională folosește ownerul managed și scope-ul runului. Funcțiile nu fac commit, nu trimit date, nu autentifică un tur și nu emit permis de send.

`create_budget`, `reserve`, `mark_sent`, `release`, `settle`, `readback` primesc conexiunea tranzacțională READ COMMITTED fără autocommit. Consumatorul trusted trebuie să țină InstanceControl→lease→Stop înainte de lockurile ledgerului și să confirme commitul SENT înainte de bytes. RESERVED→SENT→SETTLED; RELEASED numai înainte de SENT. SENT/UNKNOWN ori PARTIAL păstrează capul rezervat; un call SENT rămâne consumat inclusiv cu output zero. KNOWN eliberează doar outputul neconsumat; overrunul observat rămâne contabilizat. Nu există refund pe timeout/restart și nici retry în acest modul.

Admiterea, bindingul nativ/purpose autentificat, proiecția B06c integrală, Settings și frontiera reală pre-send sunt încă **NOT_IMPLEMENTED/NOT_INTEGRATED**. `trusted_purpose` este o intrare internă a viitorului owner trusted, nu dovadă că JSON-ul a fost autentificat. `native-turn` din contract este referință necesară de rezolvat, nu tur emis aici. Joburile Settings/Jev nu au producător: scope-urile lor sunt refuzate. Nu există guard fictiv, model/default personal, provider SDK ori downgrade NO_MODEL.

## Interoperare B06c

Propunerea B06c a devenit disponibilă în timpul implementării: `ModelProjections.prepare/read`, `serialize_model_input/validate_serialized_input`. Nu este încă importată: este PROPOSED, nu FROZEN/reviewed. `projection_digest=SHA256(CanonicalJSON(model_input))` diferă de digestul envelope/ref. Implementarea inițială confunda aceste valori; părintele a reprodus testul RED exit1 și a corectat înainte de primul commit de sursă. Ledgerul verifică formatul și egalitatea digestului model_input cu metadata din proiecția rezolvată. Aceasta **nu** înlocuiește validarea câmpurilor/bytes de către B06c și nu certifică un request SDK. Nicio dependență WIP nu a fost importată.

## Probe executate pe sursa inițială

Din worktree-ul b06m, numai venvul nou owned, Python3.13.15/uv0.12.19 și dependențele lockuite offline:

- `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_budget.py -q`: **14 PASS, exit0**, după ultima editare; RED separat pentru corecția digestului.
- Aceeași invocare, `api/tests/test_model_budget_pg.py --collect-only -q`: **9 colectate, exit0; execuție NOT_RUN**.
- Ruff `check --no-fix` și `format --check`, configul `api/pyproject.toml`, pe cele patru fișiere noi: **exit0**. Prima verificare format după corecție: exit1, newline/line wrapping corectat, apoi rerulat.
- `mypy --config-file api/pyproject.toml --no-incremental` pe cele patru fișiere: **exit0**, strict fără ignore/Any nou.
- Scan heuristic numai pe fișierele noi: zero potriviri pentru shell=True/os.system, eval/exec/pickle, execute(f-string) și literal secret. Nu dovedește absența tuturor problemelor; reviewurile sunt separate.
- `git diff --check` și `git diff --cached --check`: exit0.
- Documentare: `python scripts/render_docs.py --check` **exit0, cinci cititoare existente identice**; `python -m unittest discover -s tests/documentation -v` **72 PASS, exit0**. Rendererul folosește allowlistul său, iar fixture-urile testelor sunt noi în scratch; originalul protejat nu este inclus. Nu s-a regenerat/modificat HTML.

Locatori RED/GREEN ai writerului: `/home/kali/.hermes/cache/delegation/live/deleg_f70b5490/task-0.log`. Probele părintelui sunt în sesiunea `20261010_185056_95cc16`; reviewerii primesc commitul exact, nu un verdict dorit.

## Probe restante și ownership

Effects registry: holder `c03-records`, niciun target worker acordat, inclusiv la checkpoint. **PostgreSQL/persist/readback/restart/concurență/imutabilitate SQL NOT_RUN**, nu înlocuite prin in-memory store. PG tests folosesc fixture-ul existent `migrated_database_url`, conexiuni SQLAlchemy/psycopg reale, un reader în proces nou și overlap observat prin pg_locks. Metadata sintetică din aceste teste este exclusiv accounting-only; nu este ModelProjection/turn/binding admis și nu poate produce PASS de integrare.

`documents/verification/p2-b06m-serial-integration.patch` propune numai targetul focalizat și allowlistul runnerului. `git apply --check` exit0; Makefile/runnerul NU sunt modificate. Aplicarea aparține integrării seriale; abia apoi, cu effects holder/targets aprobate, se poate rula runnerul existent cu `--check --target test-model-budget-pg`. Nu se rulează canonical make check aici.

Synthetic pre-send sink: **NOT_RUN/NOT_IMPLEMENTED**. Native pinned installed: **NOT_RUN/BLOCKED_NATIVE_SEAM**. Provider live: **NOT_RUN, neautorizat**. Stop între reserve/send, bytes zero la refuz și rezerva/intenția durabilă observată înainte de bytes rămân obligații ale consumerului, nu sunt dovedite de reducer. Fără proba fizică a unui cap, nu se revendică enforcement de output/deadline. Costul necunoscut rămâne null; orice cerere de plafon monetar strict este refuzată.

## Review final scoped și predare

Cele două reviewuri inițiale pe ae22022 au cerut schimbări; [constatările și reproducerile](p2-b06m-review-initial.json) rămân istorice. F1 a fost reprodus prin `settle` cu rânduri SQL dublate: receiptul altui run nu provoca refuz. `a183108` verifică identitatea receiptului owner-wide sub lockul existent și adaugă test PG cu două runuri. F2 a fost reprodus în readerii reali cu rânduri SQL dublate: șase envelope-uri schema/revision invalide acceptate, două valide păstrate. `f55b44e` aplică validarea strictă `record` și fallbackului catalog.

După ultima editare de produs: **23 teste offline PASS, exit0**, Ruff lint/format și strict mypy pe patru fișiere **exit0**. **10 teste PG colectate, exit0; execuție NOT_RUN**. Inițialele erori de formatare și importul de test neexportat au fost corectate fără ignorarea gate-urilor. Patchul documentar avea context cu whitespace invalid pentru diff-check; `b46391f` corectează numai contextul, păstrează aplicabilitatea și `git diff c0261a7 HEAD --check` exit0.

Două re-reviewuri independente **APPROVED_SCOPED** pe snapshotul exact `b46391f6e3f2ad84e601b998c226b94912b334bf`, numai ledgerul intern/F1/F2: `/home/kali/.hermes/cache/delegation/live/deleg_4a8cbb6f/task-0.log` și `task-1.log`. Ambii au rerulat 23 teste cu exit0. Părintele a verificat diff gol pentru cele patru fișiere față de snapshotul revizuit. Aceste aprobări nu certifică PostgreSQL, admission, B06c, Settings sau bariera pre-send.

Predarea **inițială** a fost READY_FOR_INSTALLED_QA numai pentru ledgerul contabil; SL11 PARTIAL și native BLOCKED_NATIVE_SEAM. Atunci QA independentă PG/nativă era NOT_RUN, B06c PROPOSED și nu existau fixture-uri DB proprii. [Contractul continuării](p2-b06m-pg-contract.md) și proba finală de mai sus consemnează acordul serial ulterior și noile efecte, fără a transfera automat rezultatul la native.

## Predare serială contabilă

Configurația minimală `23f835c` și recorderul stdout sincron au review independent APPROVED_SCOPED (`deleg_509afca7/task-0.log`); runnerul diferă numai prin opțiunea noului target, fără semantică/security nouă. Cele două reviewuri sursă pe b46391f sunt păstrate, bytes contabilitate/teste neschimbate. QA independentă `deleg_c5670172/task-0.log` a executat o singură fixture nouă pe `2cdf4fcc6aea78747ba2bfbfc1e260c7c17c47b4`: import real din checkout, PostgreSQL18.6 UDS/no-network, persistență/replay/UNKNOWN, reader nou și overlap observat în pg_locks. Nu este instalare wheel și nici restart fizic PostgreSQL/restore.

Părintele a verificat raportul QA la SHA256 `e20c9437ed4eb5d1e494e7c0b6710c673b381357cb0805480b475368286d383d`, ambele family receipts și absența GET404 a celor două CIDs. Proiecte/networks/UDS/locks proprii absente; PGDATA/receipts păstrate; 13 containere și 9 rețele străine neschimbate; 82 inputuri fixate identice în fiecare gate. Linkul CLI temporar înregistrat a fost retras, venvul țintă păstrat, checkoutul curat. Nu s-a reluat teardownul pentru verificare.

B06c FROZEN `3c1c15a7b95565a6ef51295ab02fb436c5ef5400` este disponibil și verificat curat/byte-equivalent cu d1b8e01 pentru surse/teste/Makefile, dar nu a fost importat: proba contabilă nu depinde de producerul proiecției. Integrarea serială trebuie să păstreze ambele targeturi PG și să lege consumatorul real înaintea modelului. `effects.json` rămâne nemodificat la holder b06m; numai coordonatorul eliberează rândul după predarea explicită. Fără native/provider/target/global config/r1/main/push.
