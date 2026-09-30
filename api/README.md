# API/control și bootstrap web P0.3 — utilizare și limite

Acesta este control plane-ul API/PostgreSQL cu supervisor **inert**, reutilizat de [comanda instalată SL02 `omnis start --no-open`](../cli/README.md). Pair/open/stop operaționale, experiența P1, Hermes, provideri și assessmenturi rămân neimplementate. `/health/live` reflectă procesul; `/health/ready` dă HTTP 200 numai cu DB/schema `0004_pairing_receipts` compatibile, dar dashboardul cere suplimentar assets/control verificate. `assessment_ready=false`. CLI-ul corelează și identitatea containerului/peer-ului API, originul și bytes-urile asseturilor. PostgreSQL 18.6 rămâne pinul instalației probate; health nu pretinde verificarea versiunii serverului. Probele Uvicorn TCP din acest README sunt numai dezvoltare; produsul păstrează `python -I -m omnis.serve` pe UDS privat.

## DB de test privată: o singură cale locală și CI

Integrarea autorizată P0.4 înlocuiește rețeta TCP cu runnerul `ops/run_test_db_gate.py`, folosit de **`make check`** (alias `make test`). Nu setați manual un URL către o DB existentă și nu adoptați un proiect anterior. Runnerul creează un root privat nou în `$TMPDIR`, un proiect unic și PostgreSQL 18.6 fără rețea și fără porturi Docker, cu socket Unix/SCRAM și UID explicit. [Probe, eșecuri și starea acceptării](../documents/verification/p04-test-db-integration.md). Aceasta nu implementează launcherul și nu închide G00.

Prerechizite: API/CLI Python 3.13.15 și lockuri sincronizate, uv 0.12.19, Node 24.21.0/npm 11.19.0, uneltele [development](../tools/development/README.md), [web/browser](../web/README.md), Docker/Compose pe endpoint Unix local și imaginea digest-pinned din `ops/compose.test.yaml` **deja prezentă**. Setupul explicit poate descărca imaginea; runnerul nu face pull/install și nu schimbă daemon/firewall. Selectați uneltele pin-uite în același shell/invocare care rulează gate-ul; un shell background nou poate să nu păstreze PATH-ul sesiunii precedente.

```sh
UV=/cale/absoluta/uv-0.12.19
"$UV" sync --locked --no-config --no-python-downloads --python 3.13.15 --directory api --group dev
"$UV" sync --locked --no-config --no-python-downloads --python 3.13.15 --directory cli
# Node/npm și dependențele docs/web sunt pregătite separat, conform ghidurilor.
make check UV="$UV"
```

Pentru diagnostic focalizat, nu ca substitut al gate-ului complet:

```sh
api/.venv/bin/python -I ops/run_test_db_gate.py --check --target test-db-contract --uv "$UV"
api/.venv/bin/python -I ops/run_test_db_gate.py --check --target test-migrations --uv "$UV"
api/.venv/bin/python -I ops/run_test_db_gate.py --probe-only
```

`check-components` păstrează întreaga listă originală documente/development/anti-slop/API/migrări/wheel/web/E2E/CLI/release; este consumatorul intern al runnerului, nu o suită redusă. Execuțiile focalizate au marker TARGETED_GATE, iar probe-only nu raportează un PASS canonic. Dry-run/touch/question/ignore-errors în Make sunt refuzate pentru verificare. CI pregătește aceleași medii și invocă același `make check`; configurarea CI nu este o rulare remote trecută.

### Ownership înainte de fiecare DDL

Runnerul verifică root/paths, endpointul și identitatea daemonului, imaginea exactă, CID/labels, bindurile, UID/securitatea runtime, lipsa rețelei/publicațiilor și socketul privat. Probează autentificarea corectă și refuzul parolei greșite înaintea gate-ului. Manifestul `fixture.json` este 0600 și fără parolă; secretul sintetic are fișier separat 0600, sub root 0700. Variabilele OMNIS_TEST_* sunt construite numai pentru copilul de test, nu exportate permanent în sesiunea operatorului.

Conftest folosește **același attestor read-only**, verifică receiptul strict și compară `system_identifier` al conexiunii reale înainte de CREATE/DROP pe DB-uri UUID. URL-ul rămâne encoded pentru `.set(database=...).render_as_string()`; hostul este decodat numai în engine ori transmis explicit ca director socket driverului. Query overrides, `PG*`, Docker/Compose overrides, destinații/identități străine și virgule libpq în calea UDS sunt refuzate. O eroare de conectare nu produce fallback TCP. Timeouturile de connect/statement/lock și deadline-ul exterior al gate-ului sunt distincte.

Pinurile/toolchain-ul greșite refuză provisioningul. Environmentul copilului nu moștenește selecții pytest, Make flags, configurație DB de produs sau probe OCI opt-in; configurațiile npm sunt goale și separate. Wrapperul pornește un owner de gate dedicat, în același script, cu adopție Linux stabilită înaintea comenzii. Acesta deține familia inclusiv după setsid/exit al liderului, fixează adoptații prin pidfd și îi drenează/reap bounded înaintea receiptului family_drained. TERM/INT/timeout și ieșirea timpurie sunt probate; procese străine nu sunt selectate după UID/prefix. Lipsa receiptului sau incertitudinea păstrează DB pentru recuperare, nu o oprește sub teste încă vii. Nu este ownerul de shutdown al produsului și nu certifică recuperare automată după uciderea brutală a întregului lanț.

### Readback, date păstrate și limite

Exit zero cere și cleanup/readback curate: numai CID-ul atestat este oprit/eliminat, fără `down -v`/prune. Rootul, PGDATA, manifestul, secretul sintetic și logul privat sunt păstrate pentru diagnostic/recuperare, iar calea este afișată. Nu comiteți sau publicați aceste fișiere. Eșec/timeout/identitate schimbată/readback incert rămân nenule; nu înseamnă că toate componentele au trecut. Rularea următoare creează alt root/proiect; nu reutilizează automat datele păstrate. O terminare brutală a runnerului necesită inspecția intenției și recuperare manuală owned-only; un revert Git nu oprește Docker.

Testele installed-wheel migrează din afara checkoutului și exercită procese API/supervisor reale. Guardul Python de probă permite numai socketul DB declarat (sau fixture TCP explicit în testele sale), păstrează controalele negative și nu este sandbox OS/G-NET. Migrațiile 0001–0004 și contractele produsului sunt neschimbate; nu a fost migrată nicio DB personală.

Pornirea manuală a API-ului/controlului, dacă este necesară pentru dezvoltare, cere separat o instanță proprie și `OMNIS_DATABASE_URL` configurat explicit. URL-ul efemer al gate-ului nu rămâne valid după teardown. API nu migrează la startup; modulul instalat `python -I -m omnis.migrate` este operația explicită, cu backup/restore pentru date existente. Schema fizică, defaulturile și constrângerile validate/enforced rămân verificate. Rețeta veche host/TCP este păstrată numai în [proba istorică](../documents/verification/p04-safe-test-db.md), nu ca o a doua cale curentă de setup.

## Entrypoint OCI P0.4: socket Unix, nu port Docker

Comanda imaginii instalate este `python -I -m omnis.serve`, distinctă de pornirea Uvicorn directă pe TCP folosită numai în probe de dezvoltare. API-ul din release ascultă exclusiv pe `api.sock` în directorul privat 0700, cu socket/lock 0600; HTTP-ul din browser este forwardat doar de procesul host după verificarea peer UID. Un proces părinte fără event loop de API deține copilul Uvicorn prin `pidfd`: la SIGTERM/SIGINT așteaptă cel mult 10 s, apoi trimite SIGKILL copilului și reap bounded. Oprirea normală întoarce 0; depășirea termenului/efectul nereconciliat întoarce 4. Un kill poate lăsa pathname-ul socketului stale, validat și reconciliat numai la o pornire explicită sub lock. Compose acordă API-ului `stop_grace_period: 15s`, mai mult decât deadline-ul ownerului; [proba instalată](../documents/verification/p04-host-uds.md) a observat `ExitCode=4` pentru un event loop blocat și recuperarea UDS la restart explicit. Nu interpretați acest exit drept barieră durabilă `InstanceControl` sau quiescență completă a produsului.

`make check-installed-control UV=/cale/uv-0.12.19` a probat din afara checkoutului un release disposable cu PostgreSQL/API/supervisor reale, schema nemigrată 503, apoi migrare/readiness/assets/IPC și cleanup fără `down -v`; [evidența exactă și limitele](../documents/verification/p04-host-uds.md). Nu este `omnis start/stop`, nu testează un crash al launcherului sau un peer LAN, iar `make check` a trecut pe [fixture-ul disposable](../documents/verification/p04-safe-test-db.md) la o revizie anterioară; integrarea curentă folosește runnerul UDS de mai sus, cu starea verificărilor consemnată separat în p04-test-db-integration.md. Nu sunt porniți provideri, Hermes ori assessmenturi.

## Gate-uri Python reproductibile

După `uv sync --locked --group dev --directory api`, `make lint-api` verifică Ruff **0.16.9** (lint E4/E7/E9/F/I/B și format stabil), iar `make typecheck-api` rulează mypy **2.3.1**, strict, cu pluginul Pydantic tipizat. Se verifică `api/src` și `api/tests`, inclusiv migrațiile și harnessurile, fără excluderi de cod, casts sau ignores pentru a ascunde erori. Uneltele sunt dev-only; comenzile nu instalează dependențe și nu fac autofix.

`make check-api` și `make check` includ aceste gate-uri; CI apelează aceleași comenzi. Controalele pozitive/negative verifică diagnosticele exacte și propagarea erorilor prin Make. Verificările folosesc configurația proiectului, Python izolat și importul propriei copii de surse; `PYTHONPATH`, `MYPYPATH` și opțiunile pytest ambientale nu pot restrânge implicit suita. Detalii și limite: [proba de calitate Python](../documents/verification/p02-python-quality.md).

## Supervisor și control privat

`OMNIS_CONTROL_DIR` este o cale absolută/canonică spre un director **existent**, al operatorului, mod `0700`, în afara repo-ului. Ancestorii nu pot fi deținuți de alt UID sau world-writable; un segment group-writable este acceptat numai dacă se află deja sub o frontieră owner-only. Nu folosiți un root temporar public, symlinkuri sau runtime-ul personal Hermes. Pentru Linux, calea completă a socketului trebuie să încapă în limita AF_UNIX. SL02 creează/verifică rooturile XDG și mappingul UID pentru startupul instalat; P0.2 exercită separat procese locale cu același UID.

Pornire separată, după migrare și provisionarea explicită a directorului privat:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" OMNIS_CONTROL_DIR="/cale/privata/existenta" api/.venv/bin/python -I -m omnis.supervisor
```

Singurul anunț de startup este `SUPERVISOR_READY`. Acesta înseamnă control inert cu lease, **nu admitere deschisă**. Procesul nu folosește Docker, shell sau conturi; un al doilea owner este refuzat. Heartbeat la 1 secundă, lease 5 secunde; pierderea autorității/DB este tratată fail-closed, dar termenul complet de shutdown sub I/O suspendat nu este certificat: heartbeat/quiesce/release pot rămâne suspendate, restanță P0.4 înainte de acceptarea Stop. Statusul privat și health verifică owner/epoch/expiry fără a reînnoi lease-ul; numai bucla supervisorului îl reînnoiește. SIGTERM închide controlul și eliberează lease-ul; un kill lasă expirarea și takeoverul să fence-uiască ownerul vechi. API restart nu creează supervisor și nu deschide admiterea.

Protocolul local: un obiect JSON pe linie, versiune `1`, capability per boot și comandă tipizată; maximum 4096 bytes, 16 clienți activi, 4 secunde pentru request și 1 secundă pentru răspuns. `control.sock`, `control.cap` și lockul sunt `0600`; capability se rotește la restart și nu apare în output. Peer-ul Linux `SO_PEERCRED` și capability sunt ambele obligatorii. Același UID/root malițios rămâne exclus din garanție. Nu copiați capability în chat/argv/URL/loguri.

Operații: `status`; `pairing` cu `instance_id`, UUID `issuance_id` și digest SHA-256; `open`, `shutdown`, `finalize` cu `instance_id`, UUID `command_id` și `expected_generation`. CLI-ul are status read-only; startul headless SL02 folosește operația privată `open` numai pentru admiterea noii instanțe verificate. Aceasta nu este comanda browser `omnis open`. Pairingul terminal și comenzile operaționale shutdown/finalize nu sunt încă expuse prin launcher. Emitentul local de pairing va fi launcherul P0.4; testele generează numai coduri sintetice, trimise ca digest prin IPC. O emitere nouă invalidează codul anterior fără resetarea rate limitului. Receiptul durabil leagă UUID-ul de digest și de expirarea inițială: retryul nu prelungește TTL și nu reactivează un cod consumat/expirat/înlocuit; UUID cu alt digest sau cod refolosit cu alt UUID dă `PAIRING_CONFLICT`. Migrarea `0004` invalidează codurile pending anterioare, fără identitate de emitere, și păstrează sesiunile existente. Nu se șterg receipturi ca mecanism de reemitere.

Shutdown persistă întâi bariera. Receipturile păstrează rezultatul original, iar răspunsul include separat statusul curent; UUID refolosit cu payload diferit sau generație stale dă conflict. `finalize` este numai finalizarea controlului **inert**, după quiescență; nu atestă containere oprite. Redeschiderea cere și un epoch nou plus comandă explicită. P0.4 trebuie să verifice separat identitatea/receiptul serviciilor oprite. Un shutdown incomplet rămâne închis la restart.

## Suprafața browserului

| Rută | Contract |
|---|---|
| `POST /api/pairing` | Body JSON `{code: ...}` numai prin canalul HTTP local; Origin exact obligatoriu. Cod de 5 minute, consum atomic, cel mult 5 încercări/minut per instanță, inclusiv cele reușite. Nu îl puneți în URL. |
| `GET /api/session` | Sesiune validă; întoarce tokenul CSRF legat de ea. |
| `POST /api/logout` | Origin exact, cookie și `X-CSRF-Token`; revocare server-side, nu oprirea instanței. |
| `GET /api/instance` | Proiecția DB autenticată: identitate/generație/barieră/lease/quiescență; fără configurații secrete sau metrici inventate. |

Sesiuni opace de 12 ore, digest-only în DB; cookie `HttpOnly; SameSite=Strict; Path=/`, fără Domain. `Secure` nu este pretins pe HTTP loopback. Răspunsurile `/api` sunt `no-store`; erorile nu reflectă inputul și au cod tipizat plus UUID server-side `correlation_id`, identic cu headerul `X-Correlation-ID`. ID-urile primite de la client nu sunt adoptate; răspunsurile IPC au și ele un correlation ID propriu. Body maximum 4096 bytes/3 secunde; pairing, logout și citirea statusului au separat deadline de 3 secunde pentru operația DB, cu rollback verificat pentru tranzacțiile încă necomise și `503 CONTROL_TIMEOUT` fără cookie de succes. Anularea în timpul COMMIT poate avea rezultat incert: este necesar readback, nu retry orb; deadline-ul este per operație, nu plafon total HTTP sau certificare a oricărui cleanup de driver. Query strings refuzate. Origin străin/`null`/multiplu este refuzat și la citiri; mutațiile refuză și Origin absent. Toate rutele `/api`, în afara schimbului de pairing, cer sesiune; toate mutațiile autentificate cer CSRF. Nu există CORS wildcard/SSE/admin generic. Formula „fără codes în JSON” privește outputul CLI/status/log; codul secret trebuie transmis în body-ul schimbului local, nu reflectat în răspuns. În probele Uvicorn de dezvoltare folosiți `--no-access-log`.

O excepție neașteptată înainte de începerea răspunsului produce `500 INTERNAL_ERROR`, `no-store` și același UUID în body/header/logul structurat, fără textul excepției. După începerea răspunsului conexiunea este întreruptă cu diagnostic sanitizat, nu se emite un al doilea răspuns. Anulările taskului nu sunt convertite în 500.

`create_app().openapi()` descrie erorile efective prin `ErrorEnvelope`, inclusiv validarea 422, în timp ce health503 are schema distinctă `HealthReady`. Nu a fost activat un endpoint public de documentație. `make generate-contracts` exportă `contracts/omnis.openapi.json` și generează `web/src/shared/api/generated.ts`; `make test-contracts` verifică driftul, iar gate-ul comun/CI îl include. Tipurile generate nu înlocuiesc validarea runtime a răspunsurilor în client.

`OMNIS_WEB_ROOT` indică buildul explicit. Numai `/` și asseturile allowlisted/hash-verified sunt servite same-origin, cu CSP și `no-store`; nu există fallback de fișiere sau rutare către DEMO. Asseturile lipsă/incompatibile sau deadline-ul de 1 secundă produc indisponibilitate explicită, cu maximum un worker filesystem în zbor per aplicație. `dashboard_ready=false` în statusul brut al supervisorului este conservator: acel proces nu atestă servirea HTTP; consumatorii folosesc proiecția HTTP de health/instanță. Instrucțiuni complete și limite: [web/README.md](../web/README.md).
