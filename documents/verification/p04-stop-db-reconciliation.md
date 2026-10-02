# SL04 — armare și reconciliere DB Stop: contract și predare scoped

## Snapshot și verdict

- Worktree exclusiv: `/home/kali/.hermes/cache/scratch/omnis-sl04-db-reconcile`, branch `sl04-db-reconcile`, bază `19457b1eb8640849cd185c85bdf2b0b137cddeff`.
- Commituri de produs, în ordine: `ac98fdd` (armare IPC, issuer UUID, migrare), `2e0352b` (quote pentru identificatorul SQL rezervat `grant`), `53f6c20` (reconciliere tranzacțională și job real), `b5c2975` (atestarea triggerului necondiționat). **Integrare și review independent: PENDING.** Nu promova separat primul commit fără corecția SQL și consumerul complet.
- Implementat în API, nu doar design. Probele fără DB au trecut pe ultimii bytes de produs. **PostgreSQL real, migrare fizică, imagine OCI reconstruită, Stop/Start instalat și toate gate-urile Docker: NOT_RUN**, în mod deliberat; părintele deține execuția lor serială. Nu este închiderea SL04/G00.
- Nicio modificare CLI/Makefile/ops, nici în checkoutul principal, alte worktree-uri, profilul Hermes sau HTML-ul original. Niciun Docker/PG existent nu a fost contactat; nu s-a făcut push. Arhitectura §4.3 și planul §4.2 rămân neschimbate.

## 1. Wire exact: arm_stop pe LocalControl existent

Același UDS `control.sock`, peer UID și capability per boot. JSON unic, newline final, frame **maxim 4096 bytes**, deadline-ul existent 4s. Nu se introduce HTTP admin și nu se modifică `InstanceView` sau contractul HTTP exportat.

```json
{
  "version": 1,
  "capability": "<capability existentă, numai pe canalul privat>",
  "command": {
    "op": "arm_stop",
    "instance_id": "<UUID canonic>",
    "command_id": "<UUID al comenzii SHUTDOWN>",
    "finalize_command_id": "<UUID al comenzii FINALIZE>",
    "generation": 2,
    "owner_epoch": 1,
    "daemon_id": "<ID daemon atestat de host>",
    "inventory": {"<inventarul public exact al hostului>": "<valoare>"}
  }
}
```

Seturile de chei sunt exacte. **Requestul nu acceptă `owner_uuid`**. `owner_epoch` trebuie să coincidă cu epochul LocalControl; `owner_uuid` din grant este ownerul real al LocalControl și este păstrat în fence. UUID-urile sunt lowercase/hyphen canonice, nu sunt normalizate tacit. Counters integer exact în `[1, 9223372036854775807]`, fără bool/float/string. Version integer exact `1`, inclusiv pentru envelope-ul ControlRequest. `daemon_id` respectă `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`.

Inventory: obiect JSON nonempty, chei string, recursive dict/list și primitive string/integer/bool/null, fără float/NaN/Infinity, tuple ori chei coercibile; adâncime maximă 16 în validator, maxim 8192 bytes serializați compact cu `ensure_ascii=True`. Limita frame-ului IPC de 4096 rămâne limita efectivă pentru armare. Ordinea cheilor nu conferă identitate; tipurile da (`true` nu este `1`). Inventarul este binding opac pentru DB, **nu dovadă Docker**. Hostul trimite numai identificatori publici/non-secret; nu pune DSN, capability, token, parolă ori conținut de dovezi secrete în inventory.

Reply de succes, **exact separat de InstanceView**:

```json
{
  "ok": true,
  "correlation_id": "<UUID al răspunsului IPC>",
  "grant": {
    "version": 1,
    "state": "STOP_PENDING",
    "instance_id": "<același UUID>",
    "command_id": "<același SHUTDOWN UUID>",
    "finalize_command_id": "<același FINALIZE UUID>",
    "generation": 2,
    "owner_epoch": 1,
    "owner_uuid": "<ownerul real LocalControl>",
    "daemon_id": "<același ID>",
    "inventory": {"<același inventar>": "<valoare>"}
  }
}
```

`state` poate fi `STOP_PENDING` sau `STOP_UNCERTAIN` la replay/readback. Un grant `STOP_UNCERTAIN` nu autorizează traseul normal de reconciliere. Nu există `status`, `result_generation`, capability ori alte câmpuri în acest succes. Eșecul păstrează envelope-ul existent `{ok:false,correlation_id,error}`; nu există grant pe refuz, timeout ori pierderea autorității la readback.

`arm_stop(...) -> StopFenceState` rămâne interfața Python existentă. Persistă `owner_uuid`, citește înapoi în tranzacția de armare și verifică starea finalized/closed. `stop_grant_readback(command: ArmStopCommand, owner: UUID) -> dict[str, object]` face încă o tranzacție după commit, compară bindingul integral și starea DB. Toate succesele de armare/replay/readback termină cu `_require_owner` după ultimul await DB de date; nu este o promisiune că lease-ul nu poate expira la momentul fizic al COMMIT. Include deja guardul de replay anunțat separat de părinte; **nu s-a cherry-pick-uit ramura părintelui**. Fixul părintelui este `1aa6332`, raportat cu RED PostgreSQL 2 failed/87 passed și GREEN 89/89 + cleanup propriu verificat; acestea sunt probele **părintelui pe ramura lui**, nu probele acestei ramuri. Părintele îl integrează înaintea commiturilor de aici. Suprapunerea explicită: `ac98fdd` adaugă deja `await self._require_owner(connection, lease, owner, epoch)` imediat înainte de `return fence.state`, plus `_closed_stop` anterior acestui check; la rezolvare se păstrează **un singur check final**, după `_closed_stop`, și ambele teste PG ale părintelui.

## 2. Migrare și tranzacția de reconciliere

Noua revizie API: **`0006_stop_reconciliation`**, după `0005_stop_fence`.

- `instance_stop_fence.owner_uuid uuid NULL`: armările noi stochează issuerul real. Fence-urile existente la upgrade rămân cu NULL, fără presupunere/rebind al ownerului; rămân blocate și sunt refuzate de reconcilierea nouă.
- Tabela `instance_stop_reconciliation`: `reconciliation_id uuid PRIMARY KEY`, `system_identifier text NOT NULL`, `"grant" jsonb NOT NULL`, `completion_sha256 text NOT NULL`. Conține grantul integral, inclusiv version/state/owner, plus hashul exact transmis de host. Envelope version este fix 1; niciun timestamp/TTL nu dezarmează fence-ul.
- Trigger statement `stop_reconciliation_immutable` refuză UPDATE, DELETE și TRUNCATE. Schema verifier verifică nume, event bits, enablement, corpul/limbajul funcției, aritate, absența WHEN/attribute-filter și return type. DBA-ul cu autoritate DDL poate elimina protecții: aceasta nu este criptografie împotriva administratorului DB; driftul verificabil refuză înaintea reconciliării.
- `downgrade()` refuză ștergerea istoricului. Git revert nu anulează efecte DB; nu se migrează date istorice fără plan de backup/recovery separat.

Interfață Python:

```text
await InstanceService(engine).reconcile_stop(request: StopReconciliation)
    -> dict[str, object]  # payloadul version-1 exact, după commit și readback
```

Ordine: `instance_control FOR UPDATE` → `supervisor_lease FOR UPDATE`, apoi verificarea clusterului conectat (`pg_catalog.pg_control_system()`), numelui DB din engine URL și a schemei fizice/reviziei pe **aceeași conexiune**, înaintea oricărui write. Identitatea instanței, generation, epoch, owner (dacă lease.owner nu este NULL), `admission_open=false`, shutdown UUID, quiescence și ambele receipts SHUTDOWN/FINALIZE sunt comparate exact. SHUTDOWN expected generation este `generation-1`; FINALIZE expected/result sunt `generation` și același epoch.

Nu cere lease viu, nu face heartbeat, acquire ori OPEN. `STOP_UNCERTAIN` este refuzat. Pentru prima cerere, grantul din fence trebuie să fie exact `STOP_PENDING`; **insert receipt + delete fence cu predicate pe fiecare binding** sunt atomice. Verifică receiptul exact și fence absent înainte de commit, apoi într-o a doua tranzacție verifică din nou schema/clusterul/starea closed și receiptul. Absența fence-ului fără receipt exact nu este succes.

Replay-ul aceluiași `reconciliation_id` este doar readback dacă întreg payloadul coincide și generația/epochul/starea closed nu s-au schimbat. ID nou după fence absent, hash străin, inventory/owner/epoch străin, schema incompatibilă ori OPEN refuză fără write. Takeover între commitul valid și readback poate produce refuz/lipsa ACK-ului chiar dacă receiptul a fost persistat: **nu este rollback pretins**; hostul păstrează recovery/ACK incert. Nu autoreia Start și nu deduce succes din resurse absente.

## 3. Job real în pachetul/imaginea API existentă

Entrypoint fix, fără argumente:

```text
python -I -m omnis.stop_reconcile
```

Hostul execută rolul DB-only cu aceeași protecție de env/secrete ca migratorul, în imaginea API pinuită; nu acordă Docker socket jobului. Modulul este inclus automat de build-ul wheelului API, fără dependențe noi. Reconstruirea/legarea imaginii și rolului Compose aparțin părintelui.

Env obligatoriu: `OMNIS_DATABASE_URL`, `OMNIS_EXPECTED_SYSTEM_ID`. URL-ul folosește validatorul migratorului, fără query overrides sau ambient `PG*`; system ID este string `[0-9]{1,20}`, egal cu inputul și cu clusterul conectat. Secretele rămân în env protejat, niciodată argv/stdout/diagnostic. Nu există input SQL, argv, path, DSN ori operații Docker.

Stdin: **un singur JSON UTF-8, EOF obligatoriu**, maxim **16384 bytes inclusiv whitespace**, chei duplicate și extra refuzate. Deadline total input **3s**, coroutine DB **10s**, dispose **2s**, backstop SIGALRM job **15s** (include un client async blocat și output). Hostul impune și propria limită de proces și tratează orice EOF/timeout/output incomplet ca nereconciliat.

Payload exact:

```json
{
  "version": 1,
  "reconciliation_id": "<UUID canonic nou, persistat înainte de job>",
  "system_identifier": "<ID original atestat al clusterului>",
  "grant": {"<grantul exact integral returnat de arm_stop>": "<fără modificări>"},
  "completion_sha256": "<64 caractere lowercase hex>"
}
```

Placeholderul `grant` de mai sus reprezintă **obiectul complet** din §1, nu un schema alternativ. Hostul produce și verifică dovada completă de ACK Docker/drain/receipturi fsynced/absență proprie/PGDATA originală și calculează hashul **bytes-ilor documentului său durabil de completion**. Jobul nu citește acel document, nu îi inventează schema și nu pretinde atestare Docker. Doar leagă hashul furnizat de grantul DB exact; un string SHA-256 singur nu dovedește host completion.

Succes: exit **0**, o linie JSON exact `{ok:true,correlation_id:<reconciliation_id>,receipt:<payloadul integral exact de mai sus>}` numai după commit+readback. Hostul compară exact correlation ID și receiptul cu cererea sa; apoi își persistă/citește înapoi ACK-ul înainte de continuarea unui Start explicit.

Eșec: exit **4**, o linie `{ok:false,correlation_id:<UUID>,error:<cod allowlisted>}`. Coduri: `INVALID_RECONCILIATION`, `RECONCILIATION_TIMEOUT`, `RECONCILIATION_REFUSED`, `RECONCILIATION_UNAVAILABLE`. La input valid, correlation ID este reconciliation ID; înaintea validării se generează UUID nou. Fără DSN/raw SQL, traceback ori grant pe eșec. Un output pierdut după commit nu autorizează retry Docker sau Start implicit; numai replay/readback exact și starea încă closed pot confirma jobul.

## 4. Probe efectiv executate

Toolchain propriu: uv **0.12.19**, Python **3.13.15**, `uv sync --locked --no-config --offline --directory api` → exit0. Executabil uv: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`.

RED-uri observate, nu fabricate:

1. `test_stop_control.py`: **9 failed** pentru op `arm_stop` necunoscut și lipsa replyului grant; apoi GREEN.
2. `test_stop_schema.py`: revizia rămânea 0005; apoi GREEN la migrarea nouă.
3. `test_stop_reconcile.py`: **4 failed** pentru metoda/modulul lipsă; apoi GREEN. Un test ulterior de stdin deschis a produs **1 failed** (`INVALID_RECONCILIATION` în loc de timeout); corectat separat în aceeași felie.
4. Migrarea nequoted `grant`: **1 failed** pe SQL-ul emis. Verificat și Appendix C PostgreSQL 18: GRANT este rezervat; corecția are commit propriu. Aceasta nu este o execuție PG.
5. Schema cu trigger condițional: **1 failed**, readiness `True` pe row-uri driver substituite; controlul pozitiv și negativ trec după guard. Nu este probă DDL live.

Ultima verificare de produs, după `b5c2975`:

```text
api/.venv/bin/python -I -m pytest -c api/pyproject.toml \
  api/tests/test_stop_control.py api/tests/test_stop_schema.py \
  api/tests/test_stop_reconcile.py -q --tb=short
# 49 passed, exit0

api/.venv/bin/python -I -m ruff check --config api/pyproject.toml api/src api/tests
# All checks passed, exit0
api/.venv/bin/python -I -m ruff format --config api/pyproject.toml --check api/src api/tests
# 71 files already formatted, exit0
api/.venv/bin/python -I -m mypy --config-file api/pyproject.toml --no-incremental api/src api/tests
# Success, 71 source files, exit0
api/.venv/bin/python -I scripts/export_contracts.py --check
# exit0; HTTP/InstanceView neschimbate
```

Testele includ peer/cap/epoch denials pe UDS real, reply separat, refuz după readback pierdut (DB substituit), DTO strict, 16KiB exact pozitiv/negativ, stdin fără EOF, env/argv/query denials, backstop de proces cu event loop blocat și invarianta closed fără lease viu. Ele **nu certifică tranzacțiile PostgreSQL**.

Build/install real, offline, din bytes `b5c2975`:

```text
uv build --no-config --offline --wheel api --out-dir api/.venv/proof/wheel
uv export --locked --offline --no-config --directory api --no-dev --no-emit-project \
  --format requirements-txt --output-file .venv/proof/requirements.txt
uv venv --no-config --no-python-downloads --python 3.13.15 api/.venv/proof/installed
uv pip sync --offline --no-config --python api/.venv/proof/installed/bin/python \
  --require-hashes api/.venv/proof/requirements.txt
uv pip install --offline --no-config --python api/.venv/proof/installed/bin/python \
  --no-deps api/.venv/proof/wheel/omnis_api-0.1.0-py3-none-any.whl
uv pip check --no-config --python api/.venv/proof/installed/bin/python
# toate exit0; 21 installed packages compatible
```

Wheel SHA-256: `d32a95a8ecf292b9374419b2256dfde019ba426654dfba2fe9e92aa6d81ddbe9`.
Readback efectiv: **34 fișiere Python identice source ↔ wheel ↔ site-packages instalat**. Din cwd extern `/home/kali/.hermes/cache/scratch`, interpreterul instalat cu `-I` importă `.../api/.venv/proof/installed/lib/python3.13/site-packages/omnis/stop_reconcile.py`; procesul real `-I -m omnis.stop_reconcile` cu `{}` pe stdin → exit4, `INVALID_RECONCILIATION`, stderr gol, markerul sintetic de secret absent. **Nu** este succes DB/OCI instalat.

Încercări de mediu relevante: o selecție inițială prea largă a inclus testul existent `test_incomplete_pairing_challenge_is_denied`; fixture-ul a refuzat înainte de contact pentru `OMNIS_TEST_DATABASE_URL` absent (13 passed/1 setup error). Nu s-au obținut credentials, nu s-a pornit DB. Un Ruff fără `--config api/pyproject.toml` a folosit clasificarea greșită a importurilor; comanda canonică explicită a trecut. Acestea nu sunt RED PG și nu sunt ascunse ca PASS global.

Verificări documentare: primul apel cu interpreterul API a refuzat rendererul pentru `markdown` absent, iar unittest a raportat 62 tests / 13 import errors. Prerechizitul a fost reparat **numai într-un venv docs propriu**, fără schimbarea mediului API/pinurilor: `uv venv --no-config --no-python-downloads --python 3.13.15 api/.venv/proof/docs`, apoi `uv pip install --offline --no-config --python api/.venv/proof/docs/bin/python -r documents/requirements-docs.txt` (`Markdown==3.10.2`). Cu acel interpreter, `-I scripts/render_docs.py --check` → toate cele cinci HTML canonice OK, exit0; `-I -m unittest discover -s tests/documentation -q` → **62 tests, OK, exit0**. Nu s-a regenerat sau modificat vreun HTML.

Scanul static al liniilor de produs adăugate: 0 shell/eval, 0 unsafe-deserialization, 0 SQL formatat, 0 credentials literal (scan limitat, nu review independent). Diff-ul de produs/test conține 15 fișiere, toate în scope API; contractul propriu este al șaisprezecelea fișier al predării.

## 5. PostgreSQL pregătit, numai părintele execută

`test_stop_fence.py` și `test_migrations.py` se colectează împreună: **93 tests collected, exit0**. Execuție PG a tuturor rândurilor: **NOT_RUN**.

Adăugate: grant readback/issuer, reconcile după release și expiry, replay exact, stale epoch după acquire, foreign ID/hash/inventory/owner/daemon/instance/system ID, bool-versus-int inventory, closed/schema/fence absent denials și snapshots complete neschimbate; receipt UPDATE/DELETE/TRUNCATE refuzat; fault la DELETE care trebuie să rollback-uiască și INSERT receipt; concurență reală cu lock waiter; job stdin real care commit/replay pe PG. Upgrade matrix include 0005 cu un fence preexistent păstrat și owner NULL, pairing existent păstrat. Testele vechi de formă fence includ acum owner_uuid.

Comenzi rămase la părinte: runnerul existent `ops/run_test_db_gate.py --check --target test-sl04-pg` și `--target test-migrations`, **serial**, cu propriul toolchain/fixture atestat, plus `make check` și gates instalate în ordinea canonică după integrare. Nu executa targeturile aici doar pentru un reminder.

## 6. Legături/pins de făcut de părinte (needitate)

Înlocuire pin schema 0005 → 0006, coordonată cu reconstrucția release-ului:

- `cli/src/omnis_cli/release.py` `_SCHEMA`, `instance.py` validator, `start.py` `EXPECTED_SCHEMA`.
- `ops/build_control_bundle.py` schema din manifest.
- Fixture-uri: `cli/tests/test_stop.py` (două locații), `test_status.py`, `test_install.py`, `test_ready_journal.py`, `test_installed_pointer_schema.py`; `cli/diagnostics/pgdata_identity_red.py`.
- Readback/integration: `cli/integration/installed_start.py`, `cli/integration/control_topology.py`.
- Textul de stare `cli/README.md` trebuie reconciliat factual după integrarea traseului host, nu doar înlocuit mecanic.
- `api/tests/test_cli_status.py` este deja pinuit la 0006 în această ramură și necesită CLI-ul parent actualizat înainte de gate.

Consumator host necesar: validează grantul exact; persistă grant/intenție înainte de efect; owner Stop-only produce dovada completă; la **Start explicit**, atestă originalul PGDATA și DB-ul propriu, pornește doar DB, rulează jobul fix cu payloadul de mai sus **înainte de supervisor acquire/OPEN**, verifică output+receipt exact și abia apoi continuă. Actualizează allowlisturile de entrypoint/env în atestarea rolului existent, fără SQL/argv/path generic și fără Docker socket în API. Nu activa armarea normală fără acest traseu complet.

## 7. Fișiere și status global scoped

Produs: `api/src/omnis/{core/db.py,core/schema.py,modules/instance/records.py,modules/instance/schemas.py,modules/instance/service.py,modules/instance/stop_contract.py,transport/local_control.py,stop_reconcile.py,migrations/versions/0006_stop_reconciliation.py}`.
Teste: `api/tests/{test_stop_control.py,test_stop_schema.py,test_stop_reconcile.py,test_stop_fence.py,test_migrations.py,test_cli_status.py}`. Contract/raport: acest document. Nicio modificare în alte subsisteme.

| Zonă | Cod/probe/review în această predare | Pas |
|---|---|---|
| P0.1–P0.3 / SL01–SL03 | Starea anterioară nu este recertificată | Părintele păstrează registrul |
| **AICI SL04 DB arm/reconcile** | IMPLEMENTED; no-DB/artefact local PASS; PG/OCI NOT_RUN; NOT_REVIEWED | PG serial, review exact, integrare host/CLI |
| SL04 owner/Stop/Start complet | Nu este certificat de acest job | Dovezi host + gates instalate |
| M03 / M22 | În afara feliei, rămân deschise | Workstreams separate |
| G00 / CI remote | Deschis / NOT_RUN | Nu se transferă verdele bazei |
| P1–P8 / rest MVP | Neînceput aici | Numai după porțile canonice |

Reticle: NOT_APPLICABLE pentru proprietățile DB/CLI ale feliei. Chisel: NO-GO/BLOCKED; nefolosit. Niciun review independent nu este inventat; părintele primește SHA-urile și acest raport pentru adjudicare.

Lecție reutilizabilă în limita scope-ului: când un wire field devine identificator SQL, verifică keyword-urile dialectului și quotează-l; păstrează probele de SQL emis distincte de execuția PG. La un receipt append-only verifică și lipsa predicatei triggerului, nu doar numele/enablement. Nu s-au modificat skill-uri/profiluri Hermes deoarece delegarea permite numai API și contractul propriu.
