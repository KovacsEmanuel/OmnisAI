# R2 focused — corecții SOURCE 80 → fb54

## Verdict

**APPROVED_SOURCE_CORRECTIONS_SCOPED**, exclusiv pe `fb54beace973b7c49422b197404f04c8baa6a9dd`, tree `d112d081cb7b3b8a34a6ab6f00f24db87685d249`, pentru cele trei corecții DNS/TLS/ACK și izolarea fixture-ului CLI de mai jos. **Niciun finding nou confirmat în această deltă.** R2-80-01/02/03 sunt remediate SOURCE, cu RED→GREEN înregistrat și re-review independent pe bytes finali. Aceasta nu este aprobarea întregului relay sau acceptare/integrări T1.

**R2-NEW-01 HIGH, physical connect/write, PG final, lifecycle și crash/SENT rămân OPEN/BLOCKED sau NOT_RUN la frontiera lor.** Cele două cicluri harness-only connect/write sunt epuizate; metadata PENDING/owner-loss are separat două cicluri și cauză neatribuită. Niciun counter, CAS, oracle sau control nu este slăbit prin această aprobare.

## Snapshot, scope și metodă

- Checkout revizuit: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-fb54`, detached, clean la intrare și la ultima citire. Nu am citit sursa mutabilă `runtime-src`; acea cale apare numai în proveniența înregistrată a autorului.
- Bază: `80c3ecd7d4618bf998cc573bf4a7c36834283e91`, tree `02045ec990426bc1ed7e08d69f69ebcae733951b`. Delta reală: **7 fișiere, +284/−15**. Trei module de produs: DNS +2 linii, TLS +25/−schimbările aferente, ACK +13; restul sunt testele afectate și o linie de mediu în fixture-ul Start.
- `parent-source-fb54-freeze.json`: toate cele șapte căi, blobs base/final și SHA-256 ale fișierelor au fost comparate programatic cu Git și bytes checkoutului: `FREEZE_ALL_7_BASE_FINAL_BLOBS_AND_SHA256_MATCH`.
- Cerință → consumer → risc → decizie: recuperare explicită după upstream DNS/TLS și ACK strict → ModelSender/relay/broker → OPEN blocat, raw stream neînchis ori false quiescence din booleeni → aprobare numai pentru corecțiile concrete; fără promovarea SOURCE la PG/physical acceptance.
- Citite: CURRENT/CONTRIBUTING/team-slice, rândurile T1 afectate, raportul R2-80 original, freeze/handoff, reproducerul părintelui prin outputul său original, noile teste și raw RED/GREEN/final/CLI/quality. Refolosesc aprobările celor șapte scope-uri NONRELAY029 neschimbate; nu le-am reaudiat global.
- Comenzi proprii read-only: `git status --short --branch`, `git rev-parse HEAD HEAD^{tree}`, `git diff --stat`, `git diff --unified=12` pe module/fixture și `--unified=5` pe teste, `git log --format='%H %s' <base>..<head>`, `git diff --check <base> HEAD`; citiri numerotate și scripturi Python stdlib pentru hashes/blobs/AST. Snapshot și diff-check: exit0. O citire a presupus inițial calea greșită `api/src/omnis/supervisor/model_test_runtime.py` și a primit FileNotFoundError; căutarea a identificat calea reală `api/src/omnis/modules/runs/model_test_runtime.py`, apoi citită. Nu a fost o execuție de test sau un defect al produsului.
- **Nu am lansat teste, PG, broker/server, serviciu, browser, provider, instalare sau consumer.** Rezultatele de teste de mai jos sunt readback al execuțiilor reale ale autorului/părintelui, nu execuții independente ale R2.

### Cele șapte fișiere și identitatea finală

| Cale | Blob final | Semantica revizuită |
|---|---|---|
| `api/src/omnis/supervisor/model_relay.py` | `6118e04b4fc09146f4066387285fac46c311789c` | Tipizare ACK înainte de corelare |
| `api/src/omnis/supervisor/model_sender.py` | `b1bd97ba39898135619c9dcdec4a4c54df528ab8` | Ownership TLS/cleanup și taxonomie de transport |
| `api/tests/test_model_relay_protocol.py` | `0cb46f19001b194a1d6a0001854b4d8ea58c2e30` | ACK valid/missing/non-OK și bool controls |
| `api/tests/test_model_relay_scopes.py` | `488881037fdb8640c77e97cedf74bdf7d071fee1` | DNS empty/error versus denials și explicit fresh OPEN |
| `api/tests/test_model_sender.py` | `3925c976a48d528a65213d39e58d956c46dfe558` | Wrap faults, fatal cleanup, actual handshake cut/recovery |
| `cli/src/omnis_cli/model_relay.py` | `0d072a045f57e71fa048f383d94a55136c988ff8` | Numai clasificarea răspunsului DNS gol |
| `cli/tests/test_start.py` | `1174ad0f66e330375125e48c40922daa310db2a1` | Numai `XDG_CONFIG_HOME` în env-ul fixture-ului |

Commituri coerente, fără alte fișiere în deltă: DNS `57bd0497e00b7f17a81a0ef2f9d9f0078b6a2efb`; TLS `e60b9b7028e7c1a4a50e698c9a8219332dd94077`; ACK `37915d576950c5136583ecdbb059a65484d01fe4`; fixture CLI `fb54beace973b7c49422b197404f04c8baa6a9dd`.

## Dispoziția fiecărui finding original

### R2-80-02 MEDIUM — DNS: REMEDIAT_SOURCE_SCOPED

`cli/src/omnis_cli/model_relay.py:136–163,217–231`: resolverul păstrează OSError drept răspuns gol; noul `if not rows: raise OSError(...)` intră în ramura existentă UPSTREAM_UNAVAILABLE, care apelează `Connection.close()`. Închiderea setează `closed`, închide socketul dacă există și păstrează contabilizarea task/resolver pentru drain (`33–44`); handlerul își elimină taskul înaintea ACK-ului. Un nou OPEN explicit poate trece verificarea one-live-stream, nu se lansează implicit alt lookup.

Nu există relaxarea răspunsurilor DNS ne-goale: continuă prin `auth_addresses(rows)` (`forwarder.py:220–253`), care respinge integral sockaddr malformed/non-global, loopback/private/reserved și celelalte clase interzise. ValueError rămâne DENIED/control-fatal, nu upstream-retryable. Testul nou `api/tests/test_model_relay_scopes.py:22–82` folosește brokerul real și clientul Relay pe UDS owned, cu resolver substituit: empty/error → upstream, `relay.failed == False`, exact un lookup, apoi OPEN explicit sănătos; nonglobal/malformed → RelayFailure, failed latch și un singur lookup. FENCE/DRAIN închid scope-ul. Nu există TCP/provider în acest test DNS.

Dovadă: `source-dns-red.txt` are 2 FAIL/2 PASS/1 deselected (empty/error control-fatal); `source-dns-green.txt` are 5 PASS. Reproducerul original al părintelui `parent-relay-80-defects.json:3–6` păstrează defectul de bază: control latch și healthy OPEN refuzat înainte de lookup.

### R2-80-01 MEDIUM — TLS: REMEDIAT_SOURCE_SCOPED

`api/src/omnis/supervisor/model_sender.py:60–94`: raw stream rămâne deținut până când public `TLSStream.wrap` returnează. `wrapped is None` în `finally` execută întotdeauna `self.aclose()` la wrap nereușit; nu este adăugat un al doilea transport sau raw socket fallback. Ruta reală de închidere este `CipherStream.aclose()` → FENCE și DRAIN ACK (`api/src/omnis/supervisor/model_relay.py:224–228`), iar brokerul închide socketul prin scope (`cli/src/omnis_cli/model_relay.py:101–113,33–44`). Nu este confundată închiderea poolului local cu dovada fizică.

EOF, BrokenResourceError, ClosedResourceError, OSError (inclusiv SSL/cert și timeout) și erorile publice httpcore network/timeout sunt convertite la `ConnectError("UPSTREAM_UNAVAILABLE")`; `metadata()` le expune ca `SendDenied("METADATA_UNAVAILABLE")` (`sender:271–283`). Nu sunt capturate generic BaseException/Exception/RuntimeError: RelayFailure, cancellation și erorile de control/DB nu sunt normalizate la outage. Cleanup este în afara handlerului de normalizare; dacă eșuează, rămâne fatal, nu devine succes. Testele de fault păstrează identitatea excepțiilor cancel/relay/control, iar cleanup-failure cere exact RelayFailure, nu un mesaj sanitizat de upstream.

TLS rămâne verificat: Transport refuză context fără CERT_REQUIRED/check_hostname (`149–160`), public AnyIO TLS primește hostname și context, iar contextul fixture-ului `test_model_test_v2.py:47–70` folosește CA sintetic explicit și SAN `openrouter.ai`, nu verify=False. `standard_compatible=False` nu dezactivează verificarea certificatului. Nu există private SDK/backend APIs noi.

**Proba end-to-end SOURCE specifică:** `api/tests/test_model_sender.py:107–195` folosește actual ModelSender.metadata → HTTPX/httpcore/public AnyIO TLS → actual Relay/broker UDS → TCP owned. DNS-ul sintetic răspunde cu global `8.8.8.8:443`; seam-ul existent de connect verifică acel target și îl redirecționează exclusiv la peer-ul local owned. Primul peer citește bytes ClientHello real și închide înainte de handshake; nu este TLS-wrap double în acest caz. Rezultatul cerut este exact METADATA_UNAVAILABLE, un singur connect, zero cereri HTTP, relay fără failed latch și DRAIN OK. Apoi testul schimbă explicit command/scope ID și execută un nou metadata GET: TLS verificat sănătos, `{}` și exact `GET /api/v1/models`, două connect-uri total/un singur request. Nu există retry/fallback automat. Peer tasks/listeners sunt închise/joined prin cleanup-ul fixture-ului.

**Limită de autoritate:** `guard()`/`current_guard()` din test (`21–35,168–170`) produc Scope/Authority sintetice și ferestre locale; nu sunt autoritatea legitimă din PG. Producătorul real neschimbat este `api/src/omnis/modules/runs/model_test_runtime.py:475–514` pentru metadata, respectiv `598–706` pentru dispatch, cu admission, command/owner/generation/epoch/deadline și ledger SENT/proiecție/config. Source test-ul nu certifică SQL/CAS/owner settlement/recovery PG, Cancel post-ACK sau lifecycle.

Dovadă: `source-tls-red.txt` păstrează 11 FAIL/22 deselected, inclusiv stack-ul real de ClientHello cut → AnyIO EndOfStream; `source-tls-green-final.txt` are 11 PASS/22 deselected. Wrap doubles din `sender test:49–103` sunt controale suplimentare ale taxonomiei/cleanup, nu handshake/cert-failure fizic. Reproducerul părintelui la80 (`parent-relay-80-defects.json:7–19`) rămâne fault-double cu raw_close_count=0, nu PG/TLS consumer QA.

### R2-80-03 LOW — ACK: REMEDIAT_SOURCE_SCOPED

`api/src/omnis/supervisor/model_relay.py:108–142`: după envelope exact, `integer(version,1,1)`, `integer(sequence,0,MAX_INT)` și `Scope.parse(scope)` sunt executate **înainte de** corelarea Python cu requestul. Helperul cere `type(value) is int`, iar Scope.parse aplică aceeași regulă pentru generation/owner_epoch/cancel_epoch și validează identități/forma exactă/deadline (`model_relay_protocol.py:18–20,69–95`). Astfel bool nu mai poate trece prin `True == 1`/`False == 0`; ValueError setează failed latch și RelayFailure.

`api/tests/test_model_relay_protocol.py:100–175` păstrează valid → drain reușit/scopes clear; missing → fail closed; DRAIN UPSTREAM_UNAVAILABLE → nu quiescence; adaugă bool version/sequence/nested owner_epoch → failed și scope păstrat. Parsingul tuturor epoch-urilor este comun; nu a fost extinsă suprafața wire. `source-ack-red.txt`: 3 bool FAIL/3 PASS/23 deselected, DID NOT RAISE; `source-ack-green.txt`: 29 PASS. Outputul original al părintelui păstrează acceptarea eronată a celor trei câmpuri la80.

### Izolare CLI — GAP fixture REMEDIAT; nu verdict de lifecycle

`cli/tests/test_start.py:255–270`: singura editare este `XDG_CONFIG_HOME = self.root / "config"` în patch-ul existent cu cleanup. Nicio schimbare în config parser/validarea de producție, claim format5, startup, journal sau instalare. `parent-cli-80-isolated-start.log` arată deja 8 PASS/0.284s pe frozen80 cu config privat gol, înainte de această editare. `source-cli-start-green.txt` confirmă 8 PASS/0.228s după editare, cu cele șapte nume anterior eșuate. Configul personal/predicatul exact al vechiului CONFIG_INVALID nu au fost citite sau inventate. OCI/native/readiness rămân mocks în aceste teste; format5 instalat, broadCLI și lifecycle nu sunt demonstrate.

## Comenzi, producători și rezultate înregistrate

Producător: autorul, conform `source-fixes-handoff.md:20–68`; module selectate din sursa candidatului prin pythonpath API/CLI prefix explicit. Python3.13.15, httpcore1.0.9, HTTPX0.28.1, OpenAI2.24.0, AnyIO4.15.1; fără instalări/pin changes. Exituri raportate de handoff; raw-urile citite confirmă rezultatele/assertion failures. Nu am relansat aceleași verificări.

Prefix API literal:

```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml
```

| Sufix la prefix | Exit / rezultat | Raw |
|---|---|---|
| `api/tests/test_model_relay_scopes.py -k dns_failure -q --tb=short` | 1; 2FAIL/2PASS/1deselected | `source-dns-red.txt` |
| `api/tests/test_model_relay_scopes.py -q --tb=short` | 0; 5PASS | `source-dns-green.txt` |
| `api/tests/test_model_sender.py -k tls_ -q --tb=short` | 1; 11FAIL/22deselected, apoi 0; 11PASS/22deselected | `source-tls-red.txt`, `source-tls-green.txt`, `source-tls-green-final.txt` |
| `api/tests/test_model_relay_protocol.py -k scoped_ack -q --tb=short` | 1; 3FAIL/3PASS/23deselected | `source-ack-red.txt` |
| `api/tests/test_model_relay_protocol.py -q --tb=short` | 0; 29PASS | `source-ack-green.txt` |
| `api/tests/test_model_relay_protocol.py api/tests/test_model_relay_scopes.py api/tests/test_model_sender.py api/tests/test_model_test_v2_contract.py -k 'not original_usage and not redacts_before and not usage_bounds' -q --tb=short` | **0; 52PASS/20deselected/1.88s** după ultima editare | `source-final-affected-tests.txt` |

Cele20deselected sunt excluderi explicite ale usage/redaction/bounds neschimbate, nu gate slăbit pentru noile corecții. Am comparat AST base/final pentru `test_redacts_before_bounding_response_identifiers`, `test_original_usage_is_not_coerced`, `test_usage_bounds_match_public_and_outcome`: toate sunt identice. Niciun test nou DNS/TLS/ACK nu are nume exclus de selecție. Aceste verificări și celelalte scope-uri NONRELAY029 rămân reutilizabile numai la limita lor, fără fresh runtime PASS.

CLI Start, comandă literală a autorului:

```sh
private=$(mktemp -d "$TMPDIR/source-cli-XXXXXX"); trap 'rmdir "$private"' EXIT; XDG_CONFIG_HOME="$private/config" TMPDIR="$private" cli/.venv/bin/python -I -B -c 'import pathlib,sys,unittest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root/"cli/src")); import omnis_cli.start as s; print("SELECTED",s.__file__,flush=True); unittest.main(module=None,argv=["unittest","discover","-s","cli/tests","-p","test_start.py","-v"])'
```

Exit0, 8PASS/0.228s. Comanda de fence este identică procedural, cu prefix `source-fence-XXXXXX`, import `omnis_cli.model_relay` și pattern `test_model_relay_fence.py`: exit0, 1PASS/0.072s (`source-final-cli-fence.txt`), numai held-DNS fence/resolver drain, nu connect/write final.

Quality după ultima editare:

- `make --no-print-directory lint-api typecheck-api` — exit0, raw `source-final-api-quality.txt` = `[][]`. Definițiile reale `Makefile:201–207` folosesc Ruff check/format și strict mypy pe api/src+api/tests, cu pin mypy2.3.1; nu target inventat/dry-run.
- `api/.venv/bin/python -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests` — exit0.
- `api/.venv/bin/python -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests` — exit0, 77 deja formatate.
- `env -u PYTHONPATH -u MYPYPATH api/.venv/bin/python -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json cli/src` — exit0.
- Ultimele trei sunt comenzile quality din `Makefile:275–277`, nu întregul `check-cli`; raw `source-final-cli-quality.txt`. Lint/typecheck nu certifică comportamentul runtime.

## Limite păstrate / următoarea decizie

- **Corecție explicită a raportului R2-80:** array-ul fixtures nu era cronologic. Ordinea stabilită și în Main `4c4d1f1` este **21PASS → 24PASS/2FAIL physical counters → 47PASS/2FAIL Cancel409**. Rezumatul autorului cu ultimul47/2 este corect. Nu preiau vechiul finding „freeze stale/latest24/2”. Am folosit corecția din registrul T1:184–203, nu am reexecutat PG sau rescanat infrastructura.
- Ambele negative istorice rămân: intermediate counters și ultimul Cancel409. Nici409 nu este ACK, nici contorul cumulativ fără ordinea exactă nu dovedește singur leak post-ACK. Cauza nu este atribuită generic harness-ului. **Physical R2-NEW-01 HIGH nu este închis** de DNS/TLS/ACK, de52SOURCE sau de8Start.
- Nicio editare nouă a PG/harness/observer/oracle, nici retry, fallback, relaxare policy, control swallow sau efect implicit în cele șapte fișiere. SDK/pool retries=0, trust_env=false, redirects=false și allow_fallbacks=false sunt păstrate.
- PG final/lifecycle/canonical/crash nesettled SENT, installed/native/provider, backup/restore și T1 global rămân neprobate aici. Nu bundle/reseal, instalare, profil/global/secrete/date operator, HTML protejat sau T2. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
- Părintele păstrează adjudecarea, reviewul complementar, integrarea/acceptarea și admiterea primului consumer real bounded; acest raport nu autorizează o a treia rundă harness-only sau lansarea de către reviewer.

**Singurul fișier creat de R2:** acest raport. Nicio modificare Git/produs/teste/docs/skill și niciun commit.

Neexecutat: teste noi proprii, PG/consumer/lifecycle/installed/provider/native/canonical/crash/backup și audit global al scope-urilor neschimbate.
Risc: corecțiile SOURCE sunt aprobate numai pe fb54; quiescența fizică și recuperarea ownerului legitim PG rămân BLOCKED/NOT_RUN, nu full T1.
