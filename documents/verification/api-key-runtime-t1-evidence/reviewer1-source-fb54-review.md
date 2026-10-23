# R1 — SOURCE 80→fb54: APPROVED_SOURCE_CORRECTIONS_SCOPED

## Verdict și identitate exactă

**APPROVED_SOURCE_CORRECTIONS_SCOPED** numai pentru corecțiile de mai jos, pe commitul `fb54beace973b7c49422b197404f04c8baa6a9dd`, tree `d112d081cb7b3b8a34a6ab6f00f24db87685d249`, față de base `80c3ecd7d4618bf998cc573bf4a7c36834283e91` (tree `02045ec990426bc1ed7e08d69f69ebcae733951b`). Niciun finding concret nou în delta cerută. Nu este aprobare full relay, integrare, T1 sau artefact instalat.

Checkout inspectat: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-fb54`, detached și curat la început și la final. Delta: exact 7 fișiere, +284/-15. Am verificat programatic toate cele 7 perechi old/new blob și SHA256 ale fișierelor locale față de `parent-source-fb54-freeze.json`; toate coincid. Nu am citit surse din `runtime-src` mutabil; acel pathname apare numai în handoff/logurile istorice citite.

| Fișier din scope | Blob final |
|---|---|
| `api/src/omnis/supervisor/model_relay.py` | `6118e04b4fc09146f4066387285fac46c311789c` |
| `api/src/omnis/supervisor/model_sender.py` | `b1bd97ba39898135619c9dcdec4a4c54df528ab8` |
| `api/tests/test_model_relay_protocol.py` | `0cb46f19001b194a1d6a0001854b4d8ea58c2e30` |
| `api/tests/test_model_relay_scopes.py` | `488881037fdb8640c77e97cedf74bdf7d071fee1` |
| `api/tests/test_model_sender.py` | `3925c976a48d528a65213d39e58d956c46dfe558` |
| `cli/src/omnis_cli/model_relay.py` | `0d072a045f57e71fa048f383d94a55136c988ff8` |
| `cli/tests/test_start.py` | `1174ad0f66e330375125e48c40922daa310db2a1` |

Commiturile coerente sunt `57bd0497e00b7f17a81a0ef2f9d9f0078b6a2efb` DNS, `e60b9b7028e7c1a4a50e698c9a8219332dd94077` TLS, `37915d576950c5136583ecdbb059a65484d01fe4` ACK și `fb54beace973b7c49422b197404f04c8baa6a9dd` izolarea fixture-ului CLI. Candidat, nu auto-integrare.

## Cerință → cod/test/oracle → dispoziție

### R1 DNS și R2-80-02 — CLOSED_SOURCE_SCOPED

`cli/src/omnis_cli/model_relay.py:159–163,217–220`: numai răspunsul DNS gol după terminarea resolverului devine explicit OSError; ramura existentă emite `UPSTREAM_UNAVAILABLE` și închide Connection. Eroarea getaddrinfo prinsă de resolver produce același răspuns gol. Taskul OPEN este eliminat în finally, resolverul finit este păstrat în ownership-ul existent, iar un nou OPEN explicit nu mai întâlnește un stream rămas live. Non-global și malformed continuă prin `auth_addresses`/ValueError→DENIED, deci RelayFailure și latch fatal; fixul nu relaxează policy/autoritatea.

Am citit cele patru cazuri reale din `api/tests/test_model_relay_scopes.py:19–80`: empty/error verifică statusul upstream, `relay.failed == False`, exact o rezoluție înainte de noul apel explicit și apoi OPEN OK cu a doua rezoluție; nonglobal/malformed cer RelayFailure, latch și un singur lookup. FENCE/DRAIN și închiderea brokerului sunt păstrate. Este brokerul production peste UDS, cu DNS substituit, fără TCP/HTTP/PG în acest test. Nu pretinde receipt API persistent. Backend-ul real din `model_sender.py:120–127` transformă statusul non-OK în ConnectError; metadata îl sanitizează la `METADATA_UNAVAILABLE`, nu în control sănătos fals și nu într-un retry.

### R2-80-01 — CLOSED_SOURCE_SCOPED

`api/src/omnis/supervisor/model_sender.py:60–94`: streamul raw rămâne deținut până când public `TLSStream.wrap` întoarce cu succes. `wrapped is None` determină `self.aclose()` în finally inclusiv la excepții neclasificate și cancellation; succesul transferă streamul TLS fără închiderea prematură a raw-ului. EOF, erorile SSL/certificat și rețea (OSError), Broken/ClosedResourceError, NetworkError și TimeoutException sunt singurele clase normalizate aici la ConnectError. TimeoutError al timeoutului asyncio este OSError. Nu există catch BaseException/general care să transforme CancelledError, RelayFailure sau RuntimeError DB/control în outage.

Închiderea production ajunge în `CipherStream.aclose` (`api/src/omnis/supervisor/model_relay.py:224–228`), adică FENCE și DRAIN pe scope, nu doar close local al poolului. Orice excepție de cleanup se propagă, inclusiv peste eroarea upstream în curs; nu există confirmare falsă de drain. Erorile control/DB/cancellation nu primesc aici un rezultat provider normal. Aceasta nu este certificare a tuturor claselor posibile de erori DB: controlul nou folosește un RuntimeError-double, iar guardul este sintetic.

Am citit toate noile oracole din `api/tests/test_model_sender.py:39–197`: 9 fault controls la public wrap, cleanup fatal și consumerul real metadata. Cele 9 controale folosesc Mock/AsyncMock pentru raw/wrap, cer exact o închidere și păstrează identitatea excepției pentru cancellation/relay/control; cleanup-failure cere exact RelayFailure. Nu sunt teste PG.

Cazul `test_tls_handshake_cut_allows_explicit_healthy_metadata_attempt` folosește efectiv ModelSender.metadata → HTTPX/httpcore → public AnyIO TLS → CipherStream → brokerul production → TCP loopback owned. Primul peer citește ClientHello real și închide înainte de handshake: rezultatul cerut este `METADATA_UNAVAILABLE`, un singur connect, niciun HTTP request, fără retry implicit, `relay.failed == False`, apoi DRAIN ACK OK. Numai al doilea apel explicit, cu id de scope nou, ajunge la peerul TLS sănătos și produce exact un `GET /api/v1/models` și `{}`. DNS și destinația sock_connect sunt substituite la frontiera fixture-ului; autoritatea este `current_guard` sintetic, nu SQL/admission real. `tls_contexts` (`test_model_test_v2.py:42–70`) creează certificatul owned cu SAN openrouter.ai și clientul cu CA explicită; Transport cere CERT_REQUIRED/check_hostname. Nu este CERT_NONE, provider live sau certificare de Refresh/owner/receipt PG. Peerii, brokerul și taskurile sunt în cleanup-ul existent.

### R2-80-03 — CLOSED_SOURCE_SCOPED

`api/src/omnis/supervisor/model_relay.py:118–125` validează `version` int strict 1, `sequence` int strict în `[0, MAX_INT]` și întreg Scope prin `Scope.parse` ÎNAINTE de corelare. Helperul comun folosește `type(value) is int`; Scope validează UUID-uri canonice, strings/provider/deadline și toate epoch/generation bounded. Bool/float coerciv nu mai poate trece egalitatea cu wire-ul legitim. Excepția de validare ajunge la latchul `RELAY_CONTROL_UNCERTAIN`; cheia/status/length/correlation existente nu sunt relaxate.

`api/tests/test_model_relay_protocol.py:101–171`: bool version, bool sequence=False pentru sequence0 și bool owner_epoch=True trebuie să refuze quiescența, să păstreze scope-ul și să seteze failed. Pozitivul ACK valid golește scope-urile fără latch; missing și non-OK DRAIN continuă să refuze. Este ACK-double UDS, nu broker/PG emitent rău demonstrat și nu bypass nou de UID.

### Izolare CLI din R1 §3 / R2 provenance CLI — CLOSED_SOURCE_SCOPED pentru fixture, NU cold-start

`cli/tests/test_start.py:255–269`: singura linie adăugată este `XDG_CONFIG_HOME` în patch.dict deja existent, către root-ul privat al TemporaryDirectory deja deținut/curățat. DATA/STATE/RUNTIME și restore-ul env sunt păstrate. `cli/src/omnis_cli/config.py:48–88`, startupul și toate validările de produs sunt neschimbate. Cele 8 teste Start existente sunt doubles de fază/OCI, nu format5 instalat. Pozitivul părintelui pe frozen80 cu config privat (8/8) și finalul autorului (8/8) susțin închiderea gapului de izolare, nu identifică predicatul exact al vechiului CONFIG_INVALID ambiental. Configurația personală nu a fost citită. Cerința de probă cold-start din findingul R1 original rămâne BLOCKED/NOT_RUN.

## Semantica neschimbată reutilizată, nu reaprobată global

Reutilizez strict reviewul SOURCE80 pentru fizicalitatea protocolului/guardului și scope-ul NONRELAY029 neschimbat (cele șapte corecții anterioare). Noua delta nu editează producătorii persistenti, SENT, CAS Cancel, Stop/Revoke, epoch/deadline, physical_window sau reconcile. Am urmărit callerii afectați metadata/run/drain din `model_test_runtime.py` și mapperii senderului: transportul normalizat rămâne METADATA_UNAVAILABLE pentru metadata, respectiv UNKNOWN pentru rezultatul model fără răspuns cunoscut; SENT nu devine NOT_SENT, nu apare resend/refund sau retry, pool retries și SDK max_retries rămân 0. Latchul RelayFailure și refuzul de settlement/drain rămân distincte. Testele existente de streaming outage UNKNOWN și metadata control/cancellation sunt incluse în finalul afectat, dar folosesc MockTransport, nu provider/PG. Nu am constatat regresie semantică din aceste căi schimbate; nu acord un PASS nou întregului Stop/Cancel.

## Dovezi existente recitite, fără rerulare

Am citit handofful `source-fixes-handoff.md`, scriptul și JSON-ul original `parent-relay-80-defects.{py,json}` și rawurile de mai jos. Diagnosticul părintelui dovedește pe80 DNS latch/OPEN rămas live, zero raw-close la EOF/cert/timeout și cele trei ACK booleene acceptate; este SOURCE diagnostic, nu QA PG. RED-urile autorului păstrează aceste defecte și consumerul real TLS, nu le înlocuiesc cu verdict inventat.

Prefix API literal din handoff (NEEXECUTAT de acest reviewer):

```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml
```

| Argumente adăugate prefixului | Raw | Rezultat autor înregistrat |
|---|---|---|
| `api/tests/test_model_relay_scopes.py -k dns_failure -q --tb=short` | `source-dns-red.txt` | exit1, 2 failed/2 passed/1 deselected |
| `api/tests/test_model_relay_scopes.py -q --tb=short` | `source-dns-green.txt` | exit0, 5 passed |
| `api/tests/test_model_sender.py -k tls_ -q --tb=short` | `source-tls-red.txt` | exit1, 11 failed/22 deselected; inclusiv ClientHello real |
| aceleași argumente TLS | `source-tls-green.txt`, `source-tls-green-final.txt` | exit0, 11 passed/22 deselected; final după assertion de narrowing |
| `api/tests/test_model_relay_protocol.py -k scoped_ack -q --tb=short` | `source-ack-red.txt` | exit1, 3 failed/3 passed/23 deselected |
| `api/tests/test_model_relay_protocol.py -q --tb=short` | `source-ack-green.txt` | exit0, 29 passed |
| `api/tests/test_model_relay_protocol.py api/tests/test_model_relay_scopes.py api/tests/test_model_sender.py api/tests/test_model_test_v2_contract.py -k 'not original_usage and not redacts_before and not usage_bounds' -q --tb=short` | `source-final-affected-tests.txt` | exit0, 52 passed/20 deselected, 1.88s |

**Binding după ultima editare:** commits DNS/TLS/ACK/CLI la03:40:00/03:42:52/03:44:02/03:44:36 UTC; raw final API are mtime03:45:54 UTC, quality API03:45:22, quality CLI03:45:24, fence CLI03:45:54. Aceasta susține ordinea handoffului, nu este jurnal de execuție independent al reviewerului. Snapshotul final este legat de toate bloburile verificate; comanda API selectează api/src prin pythonpath din config, iar rawurile CLI imprimă sursele selectate. Nu am importat produsul pentru a pretinde o a doua execuție.

Am numărat prin AST cele patru fișiere: exact72 cazuri, dintre care **20 excluderi = 15 original_usage + 2 redacts_before + 3 usage_bounds**, toate cu AST identic față de80; întreg `test_model_test_v2_contract.py` este byte-neschimbat. Deci52 este totalul SELECTAT, nu întregul suite/PG; excluderile sunt corect deliberate pe scope neschimbat, nu blind total sau teste noi omise.

Comenzile CLI literale din handoff (NEEXECUTATE aici):

```sh
private=$(mktemp -d "$TMPDIR/source-cli-XXXXXX"); trap 'rmdir "$private"' EXIT; XDG_CONFIG_HOME="$private/config" TMPDIR="$private" cli/.venv/bin/python -I -B -c 'import pathlib,sys,unittest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root/"cli/src")); import omnis_cli.start as s; print("SELECTED",s.__file__,flush=True); unittest.main(module=None,argv=["unittest","discover","-s","cli/tests","-p","test_start.py","-v"])'
private=$(mktemp -d "$TMPDIR/source-fence-XXXXXX"); trap 'rmdir "$private"' EXIT; XDG_CONFIG_HOME="$private/config" TMPDIR="$private" cli/.venv/bin/python -I -B -c 'import pathlib,sys,unittest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root/"cli/src")); import omnis_cli.model_relay as s; print("SELECTED",s.__file__,flush=True); unittest.main(module=None,argv=["unittest","discover","-s","cli/tests","-p","test_model_relay_fence.py","-v"])'
```

`source-cli-start-green.txt`: exit0, 8/8,0.228s; `parent-cli-80-isolated-start.log`: 8/8,0.284s pe frozen80 privat; `source-final-cli-fence.txt`: exit0,1/1,0.072s (held DNS), nu frontiera connect/write. Nu am rerulat suite neschimbate.

Quality din handoff/raw și rețetele Makefile citite: `make --no-print-directory lint-api typecheck-api` exit0 (`source-final-api-quality.txt`, `[][]`); `api/.venv/bin/python -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests`, `api/.venv/bin/python -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests`, `env -u PYTHONPATH -u MYPYPATH api/.venv/bin/python -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json cli/src` exit0 (`source-final-cli-quality.txt`: checks passed,77 formatted). Aceste exit-uri sunt înregistrarea autorului, nu rerulări R1. Configurile/pinii/Makefile nu sunt în delta. Propria comandă `git diff --check 80c3ecd7d4618bf998cc573bf4a7c36834283e91 HEAD` a ieșit0.

## Limite deschise și corecția explicită a cronologiei vechi

- R2-NEW-01 HIGH / frontiera fizică Cancel connect/write rămâne **BLOCKED, NOT_CLOSED**; două cicluri harness-only sunt epuizate, fără al treilea framework/runner/probe și fără slăbirea ACK/counter/CAS/oracle-ului. Sursa corectată nu dovedește post-ACK quiescență.
- **Corecție a propriului raport R1-80 și a raportului R2-80:** steer-ul vechi despre ordine a fost greșit. Ordinea efectivă transmisă/adjudecată de părinte este21PASS la02:54 →24PASS/2FAIL fizice la02:59 →47PASS/2FAIL Cancel409 la03:03.47/2 este latest; nu raportez freeze stale. Nu agreg totalurile și nu convertesc extra-counter-urile în efect post-ACK demonstrat. Cele două409 rămân REVISION_CONFLICT, nu Cancel ACK și nu cauză atribuită prin presupunere.
- Nicio probă PG după ultimele schimbări80/fb54; **cold format5 instalat, crash/SENT/restart și metadata PENDING owner-loss rămân BLOCKED/NOT_RUN** în limitele rândurilor lor. Metadata owner-loss are separat două cicluri/neatribuire; nu este închis de EOF/DNS source recovery.
- Niciun bundle nou/installed/native/provider/canonical/T1 acceptat; fără backup/restore, T2, target, credentiale, profile/global, push sau efecte de serviciu. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

## Execuția reviewerului / predare

Doar citiri Git/source/log, Python stdlib AST/hash/count/readback; fără import/executare produs, teste noi, PG, rețea, servicii, instalare sau schimbare de Git. Un output documentar prea lung a fost trunchiat; regulile relevante CONTRIBUTING/team-slice au fost recuperate focalizat, fără presupuneri din conținut omis. Singurul write este acest raport; niciun produs/test/docs/skill/config modificat și niciun commit.

Părintele adjudecă și decide integrarea împreună cu reviewul complementar; verdictul R1 închide numai corecțiile SOURCE DNS/TLS/ACK și izolarea fixture-ului pe bytes exacți fb54. Nu autorizează altă probă fizică peste frontiera BLOCKED.

Necontrolat: execuție independentă nouă, PG/cold format5/crash-SENT/metadata owner-loss și installed/provider/canonical.
Risc rămas: source fixes aprobate nu demonstrează frontieră fizică post-Cancel/Stop și nu transformă lipsa probei în T1 PASS.
