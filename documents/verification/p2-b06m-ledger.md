# B06m — checkpoint contabil, nu G-MODEL

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

Reviewurile complementare sunt în curs pe ae22022; nicio acceptare finală nu este încă revendicată. QA independentă a consumerului PG/nativ este NOT_RUN până la resursele seriale și implementarea connectorului. Nu s-au creat DB/containere/native processes; venvul și sursele exacte de pin din scratch sunt păstrate. Main, B06c, profilul r1 și documentul protejat au rămas neatinse. Fără push.
