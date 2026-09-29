# API/control și bootstrap web P0.3 — utilizare și limite

Acesta este control plane-ul API/PostgreSQL și supervisorul **inert, pornit separat**, cu [bootstrap web real](../web/README.md). CLI-ul parțial `omnis status/install/install-image` există; launcherul start/pair/open/stop, experiența P1, Hermes, provideri și evaluări nu sunt implementate. `/health/live` arată procesul; `/health/ready` este 200 numai după conectarea la PostgreSQL cu schema `0004_pairing_receipts` compatibilă. `dashboard_ready` cere suplimentar buildul trusted și controlul privat sănătos; `dashboard_reason` explică indisponibilitatea, iar `assessment_ready` rămâne false. Proba de integrare folosește imaginea fixată PostgreSQL 18.6; endpointul nu verifică separat numărul de versiune al serverului, aceasta fiind o precondiție a instalării testate. În exemplul de dezvoltare de mai jos, API-ul se pornește explicit pe loopback; Host-ul este exact `127.0.0.1:8765`, sau portul ales explicit prin `OMNIS_HTTP_PORT`. Setarea portului nu modifică singură bindul Uvicorn.

## Prerechizit curent BLOCKED și rețetă istorică

**Nu executați rețeta TCP de mai jos pe checkoutul WIP actual.** Recontrol HF10: Compose este `network_mode: none` cu socket privat, însă conftest încă cere host/port TCP și CI folosește vechiul port lookup. `ops/run_test_db_gate.py` este WIP `--probe-only`, nu runnerul gate-ului. Integrarea aparține autorului WIP și cere acord/DB disposable/ownership/teardown; nu o tratăm ca green. `make check`/`make test` sunt BLOCKED, nu rerulate în sesiunea de amendare; plan §19.1–19.2 este calea actuală. Secțiunea următoare păstrează rețeta/proba istorică pentru trasabilitate, nu instrucțiuni curente acceptate.

### Pregătirea istorică a testului TCP

Sunt necesare Python 3.13.15, uv 0.12.19, Docker/Compose și `postgres:18.6-bookworm` din digestul fixat în `ops/compose.test.yaml`. **Nu folosiți DB personală.** Din root, într-un shell interactiv; valoarea parolei generate este sintetică și nu se afișează sau salvează în repo:

**Fixture revizuit pentru Docker 27:** `compose.test.yaml` nu mai publică port prin Docker; PostgreSQL rulează numai în proiectul disposable, în namespace-ul hostului, cu `listen_addresses=127.0.0.1` și port ales explicit. Host networking este o capabilitate largă: folosiți numai imaginea digest-pinned și o DB sintetică, verificați lipsa `route_localnet` pe toate interfețele și nu tratați acest control local drept o probă negativă dintr-un peer L2. Nu schimbați firewallul/daemonul și nu adoptați proiecte străine. [Proba WIP și limitele ei](../documents/verification/p04-safe-test-db.md) nu închid G00.

```sh
UV=/cale/absoluta/uv-0.12.19
"$UV" --version # trebuie să fie 0.12.19, nu uv global implicit
"$UV" sync --locked --no-config --no-python-downloads --python 3.13.15 --directory api --group dev
test "$(node --version)" = "v24.21.0"
test "$(npm --version)" = "11.19.0"
python -c 'from pathlib import Path; p=list(Path("/proc/sys/net/ipv4/conf").glob("*/route_localnet")); assert p and all(x.read_text().strip()=="0" for x in p)'
docker context inspect "$(docker context show)" --format '{{(index .Endpoints "docker").Host}}' | python -c 'import pathlib,sys; x=sys.stdin.read().strip(); assert x.startswith("unix://") and pathlib.Path(x[7:]).is_socket()'
export OMNIS_TEST_PROJECT="omnis-p01-$(openssl rand -hex 8)"
export OMNIS_TEST_DB_PASSWORD="$(openssl rand -hex 24)"
export OMNIS_TEST_DB_PORT="$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
docker compose -f ops/compose.test.yaml up -d --wait db
export OMNIS_TEST_DATABASE_URL="postgresql+psycopg://omnis_test:${OMNIS_TEST_DB_PASSWORD}@127.0.0.1:${OMNIS_TEST_DB_PORT}/omnis_test"
make check UV="$UV"
```

Volumul este `OMNIS_TEST_PROJECT` + `_pgdata`, montat la `/var/lib/postgresql` (PG18 are `PGDATA=/var/lib/postgresql/18/docker`). Portul liber este propus de host, apoi fixat explicit în Compose/URL; o cursă de ocupare blochează startupul, **nu** permite adoptarea unui alt PostgreSQL. Nu există Docker `ports`/NAT: verificați `docker compose ps` cu `Publishers=[]` și `ss` cu listener numai `127.0.0.1` pe acel port. Fixture-urile cer context Docker pe socket Unix local (fără `DOCKER_*` moștenite), verifică proiectul, imaginea, commandul, volumele, absența publicațiilor și identitatea `system_identifier` a clusterului conectat față de container înainte de CREATE/DROP pe baze UUID. Un daemon Docker remote nu atestă loopbackul hostului; orice precondiție lipsă dă exit nenul, nu SQLite/skip. Verificați numele proiectului și volumul înainte de orice intervenție Docker. Docker inspect poate expune parola sintetică administratorilor hostului; nu folosiți această topologie cu date reale.

Conexiunile API/migrator și fixture-urile refuză orice setare moștenită `PG*` din libpq și orice parametru query în `OMNIS_DATABASE_URL`/`OMNIS_TEST_DATABASE_URL`: acestea pot redirecționa hostul efectiv chiar dacă autoritatea URL pare să indice instanța test. Configurați doar URL-ul explicit, fără `?host=`, `?port=` sau fișier service. Readiness compară schema fizică a `InstanceControl` din PG18, inclusiv **toate** defaulturile și constrângerile `NOT NULL` validate și enforced; un stamp Alembic sau `attnotnull` singur nu dovedește compatibilitatea.

`make check` cere și dependențele de documentație/anti-slop din `tools/development/README.md`, plus lockul web și browserul fixat din [web/README.md](../web/README.md); nu instalează automat nimic. Dacă `uv` din PATH nu este 0.12.19, instalați pinul separat și transmiteți `UV=/cale/către/uv-0.12.19` la Make. `make test-api` descoperă testele API/control, în afara migrărilor din `make test-migrations` și a E2E-ului din `make test-e2e`; toate intră în `make check`, fără skipuri implicite. Wheelul este instalat cu dependențe exportate din lock într-un venv scratch, apoi migrează o DB goală și rulează supervisorul/API-ul real **din afara checkoutului**, prin socket Unix și TCP loopback. Guardul Python de test are control negativ de egress; nu este sandbox OS și nu închide G-NET. E2E servește buildul real de pe un root explicit; împachetarea OCI/launcherul instalării rămân P0.4.

Migrarea este un job explicit înaintea pornirii procesului API:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -I -m omnis.migrate
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -m uvicorn omnis.api:create_app --factory --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

Se poate folosi același modul `omnis.migrate` dintr-un wheel instalat; `api/alembic.ini` este doar pentru comenzi Alembic din checkout. API nu migrează la startup și nu repară singletonuri lipsă. Migrarea `downgrade` este refuzată deliberat: un revert Git nu readuce datele; pentru o DB existentă cereți backup/restore verificat înainte de orice upgrade. P0.2 adaugă `0002_local_sessions`, `0003_instance_lifecycle` și `0004_pairing_receipts`; testele fac upgrade de la P0.1 păstrând identitatea/admiterea închisă. Nu s-a migrat nicio DB personală sau de producție.

La final, opriți **numai** proiectul de test verificat: `docker compose -f ops/compose.test.yaml down` în același shell cu `OMNIS_TEST_PROJECT` setat. Nu folosiți `down -v`; volumul rămâne disponibil pentru inspecție sau restaurare. Nu opriți containere selectate doar după port/PID. Absența DB/uv/Docker blochează gate-ul, nu certifică readiness.

## Entrypoint OCI P0.4: socket Unix, nu port Docker

Comanda imaginii instalate este `python -I -m omnis.serve`, distinctă de exemplul Uvicorn pe loopback de mai sus (numai dezvoltare). API-ul din release ascultă exclusiv pe `api.sock` în directorul privat 0700, cu socket/lock 0600; HTTP-ul din browser este forwardat doar de procesul host după verificarea peer UID. Un proces părinte fără event loop de API deține copilul Uvicorn prin `pidfd`: la SIGTERM/SIGINT așteaptă cel mult 10 s, apoi trimite SIGKILL copilului și reap bounded. Oprirea normală întoarce 0; depășirea termenului/efectul nereconciliat întoarce 4. Un kill poate lăsa pathname-ul socketului stale, validat și reconciliat numai la o pornire explicită sub lock. Compose acordă API-ului `stop_grace_period: 15s`, mai mult decât deadline-ul ownerului; [proba instalată](../documents/verification/p04-host-uds.md) a observat `ExitCode=4` pentru un event loop blocat și recuperarea UDS la restart explicit. Nu interpretați acest exit drept barieră durabilă `InstanceControl` sau quiescență completă a produsului.

`make check-installed-control UV=/cale/uv-0.12.19` a probat din afara checkoutului un release disposable cu PostgreSQL/API/supervisor reale, schema nemigrată 503, apoi migrare/readiness/assets/IPC și cleanup fără `down -v`; [evidența exactă și limitele](../documents/verification/p04-host-uds.md). Nu este `omnis start/stop`, nu testează un crash al launcherului sau un peer LAN, iar `make check` a trecut pe [fixture-ul disposable](../documents/verification/p04-safe-test-db.md) la o revizie anterioară; pe checkoutul actual este BLOCKED de contractul fixture/conftest/CI neintegrat, nu doar nerulat. Nu sunt porniți provideri, Hermes ori assessmenturi.

## Gate-uri Python reproductibile

După `uv sync --locked --group dev --directory api`, `make lint-api` verifică Ruff **0.16.9** (lint E4/E7/E9/F/I/B și format stabil), iar `make typecheck-api` rulează mypy **2.3.1**, strict, cu pluginul Pydantic tipizat. Se verifică `api/src` și `api/tests`, inclusiv migrațiile și harnessurile, fără excluderi de cod, casts sau ignores pentru a ascunde erori. Uneltele sunt dev-only; comenzile nu instalează dependențe și nu fac autofix.

`make check-api` și `make check` includ aceste gate-uri; CI apelează aceleași comenzi. Controalele pozitive/negative verifică diagnosticele exacte și propagarea erorilor prin Make. Verificările folosesc configurația proiectului, Python izolat și importul propriei copii de surse; `PYTHONPATH`, `MYPYPATH` și opțiunile pytest ambientale nu pot restrânge implicit suita. Detalii și limite: [proba de calitate Python](../documents/verification/p02-python-quality.md).

## Supervisor și control privat

`OMNIS_CONTROL_DIR` este o cale absolută/canonică spre un director **existent**, al operatorului, mod `0700`, în afara repo-ului. Ancestorii nu pot fi deținuți de alt UID sau world-writable; un segment group-writable este acceptat numai dacă se află deja sub o frontieră owner-only. Nu folosiți un root temporar public, symlinkuri sau runtime-ul personal Hermes. Pentru Linux, calea completă a socketului trebuie să încapă în limita AF_UNIX. P0.4 va crea/verifica rootul XDG și mappingul UID în instalare; P0.2 exercită procese locale cu același UID.

Pornire separată, după migrare și provisionarea explicită a directorului privat:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" OMNIS_CONTROL_DIR="/cale/privata/existenta" api/.venv/bin/python -I -m omnis.supervisor
```

Singurul anunț de startup este `SUPERVISOR_READY`. Acesta înseamnă control inert cu lease, **nu admitere deschisă**. Procesul nu folosește Docker, shell sau conturi; un al doilea owner este refuzat. Heartbeat la 1 secundă, lease 5 secunde; pierderea autorității/DB este tratată fail-closed, dar termenul complet de shutdown sub I/O suspendat nu este certificat: heartbeat/quiesce/release pot rămâne suspendate, restanță P0.4 înainte de acceptarea Stop. Statusul privat și health verifică owner/epoch/expiry fără a reînnoi lease-ul; numai bucla supervisorului îl reînnoiește. SIGTERM închide controlul și eliberează lease-ul; un kill lasă expirarea și takeoverul să fence-uiască ownerul vechi. API restart nu creează supervisor și nu deschide admiterea.

Protocolul local: un obiect JSON pe linie, versiune `1`, capability per boot și comandă tipizată; maximum 4096 bytes, 16 clienți activi, 4 secunde pentru request și 1 secundă pentru răspuns. `control.sock`, `control.cap` și lockul sunt `0600`; capability se rotește la restart și nu apare în output. Peer-ul Linux `SO_PEERCRED` și capability sunt ambele obligatorii. Același UID/root malițios rămâne exclus din garanție. Nu copiați capability în chat/argv/URL/loguri.

Operații: `status`; `pairing` cu `instance_id`, UUID `issuance_id` și digest SHA-256; `open`, `shutdown`, `finalize` cu `instance_id`, UUID `command_id` și `expected_generation`. CLI-ul are status read-only; comenzile de produs pairing/open/shutdown/finalize nu sunt încă expuse prin launcher. Emitentul local de pairing va fi launcherul P0.4; testele generează numai coduri sintetice, trimise ca digest prin IPC. O emitere nouă invalidează codul anterior fără resetarea rate limitului. Receiptul durabil leagă UUID-ul de digest și de expirarea inițială: retryul nu prelungește TTL și nu reactivează un cod consumat/expirat/înlocuit; UUID cu alt digest sau cod refolosit cu alt UUID dă `PAIRING_CONFLICT`. Migrarea `0004` invalidează codurile pending anterioare, fără identitate de emitere, și păstrează sesiunile existente. Nu se șterg receipturi ca mecanism de reemitere.

Shutdown persistă întâi bariera. Receipturile păstrează rezultatul original, iar răspunsul include separat statusul curent; UUID refolosit cu payload diferit sau generație stale dă conflict. `finalize` este numai finalizarea controlului **inert**, după quiescență; nu atestă containere oprite. Redeschiderea cere și un epoch nou plus comandă explicită. P0.4 trebuie să verifice separat identitatea/receiptul serviciilor oprite. Un shutdown incomplet rămâne închis la restart.

## Suprafața browserului

| Rută | Contract |
|---|---|
| `POST /api/pairing` | Body JSON `{code: ...}` numai prin canalul HTTP local; Origin exact obligatoriu. Cod de 5 minute, consum atomic, cel mult 5 încercări/minut per instanță, inclusiv cele reușite. Nu îl puneți în URL. |
| `GET /api/session` | Sesiune validă; întoarce tokenul CSRF legat de ea. |
| `POST /api/logout` | Origin exact, cookie și `X-CSRF-Token`; revocare server-side, nu oprirea instanței. |
| `GET /api/instance` | Proiecția DB autenticată: identitate/generație/barieră/lease/quiescență; fără configurații secrete sau metrici inventate. |

Sesiuni opace de 12 ore, digest-only în DB; cookie `HttpOnly; SameSite=Strict; Path=/`, fără Domain. `Secure` nu este pretins pe HTTP loopback. Răspunsurile `/api` sunt `no-store`; erorile nu reflectă inputul și au cod tipizat plus UUID server-side `correlation_id`, identic cu headerul `X-Correlation-ID`. ID-urile primite de la client nu sunt adoptate; răspunsurile IPC au și ele un correlation ID propriu. Body maximum 4096 bytes/3 secunde; pairing, logout și citirea statusului au separat deadline de 3 secunde pentru operația DB, cu rollback verificat pentru tranzacțiile încă necomise și `503 CONTROL_TIMEOUT` fără cookie de succes. Anularea în timpul COMMIT poate avea rezultat incert: este necesar readback, nu retry orb; deadline-ul este per operație, nu plafon total HTTP sau certificare a oricărui cleanup de driver. Query strings refuzate. Origin străin/`null`/multiplu este refuzat și la citiri; mutațiile refuză și Origin absent. Toate rutele `/api`, în afara schimbului de pairing, cer sesiune; toate mutațiile autentificate cer CSRF. Nu există CORS wildcard/SSE/admin generic. Formula „fără codes în JSON” privește outputul CLI/status/log; codul secret trebuie transmis în body-ul schimbului local, nu reflectat în răspuns. Dezactivați access logul Uvicorn conform comenzii de mai sus.

O excepție neașteptată înainte de începerea răspunsului produce `500 INTERNAL_ERROR`, `no-store` și același UUID în body/header/logul structurat, fără textul excepției. După începerea răspunsului conexiunea este întreruptă cu diagnostic sanitizat, nu se emite un al doilea răspuns. Anulările taskului nu sunt convertite în 500.

`create_app().openapi()` descrie erorile efective prin `ErrorEnvelope`, inclusiv validarea 422, în timp ce health503 are schema distinctă `HealthReady`. Nu a fost activat un endpoint public de documentație. `make generate-contracts` exportă `contracts/omnis.openapi.json` și generează `web/src/shared/api/generated.ts`; `make test-contracts` verifică driftul, iar gate-ul comun/CI îl include. Tipurile generate nu înlocuiesc validarea runtime a răspunsurilor în client.

`OMNIS_WEB_ROOT` indică buildul explicit. Numai `/` și asseturile allowlisted/hash-verified sunt servite same-origin, cu CSP și `no-store`; nu există fallback de fișiere sau rutare către DEMO. Asseturile lipsă/incompatibile sau deadline-ul de 1 secundă produc indisponibilitate explicită, cu maximum un worker filesystem în zbor per aplicație. `dashboard_ready=false` în statusul brut al supervisorului este conservator: acel proces nu atestă servirea HTTP; consumatorii folosesc proiecția HTTP de health/instanță. Instrucțiuni complete și limite: [web/README.md](../web/README.md).
