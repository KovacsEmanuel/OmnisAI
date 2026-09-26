# API/control P0.2 — utilizare și limite

Acesta este control plane-ul API/PostgreSQL și supervisorul **inert, pornit separat**. Nu există încă `omnis`, dashboard, Hermes, provideri sau evaluări. `/health/live` arată procesul; `/health/ready` este 200 numai după conectarea la PostgreSQL cu schema `0004_pairing_receipts` compatibilă, în timp ce `dashboard_ready` și `assessment_ready` rămân false. Proba de integrare folosește imaginea fixată PostgreSQL 18.6; endpointul nu verifică separat numărul de versiune al serverului, aceasta fiind o precondiție a instalării testate. API-ul se pornește explicit pe loopback; Host-ul este exact `127.0.0.1:8765`, sau portul ales explicit prin `OMNIS_HTTP_PORT`. Setarea portului nu modifică singură bindul Uvicorn.

## Pregătirea unui test izolat

Sunt necesare Python 3.13.15, uv 0.12.19, Docker/Compose și `postgres:18.6-bookworm` din digestul fixat în `ops/compose.test.yaml`. **Nu folosiți DB personală.** Din root, într-un shell interactiv; valoarea parolei generate este sintetică și nu se afișează sau salvează în repo:

```sh
uv sync --locked --no-config --no-python-downloads --python 3.13.15 --directory api --group dev
export OMNIS_TEST_PROJECT="omnis-p01-$(openssl rand -hex 8)"
export OMNIS_TEST_DB_PASSWORD="$(openssl rand -hex 24)"
docker compose -f ops/compose.test.yaml up -d --wait db
port="$(docker compose -f ops/compose.test.yaml port db 5432)"
export OMNIS_TEST_DATABASE_URL="postgresql+psycopg://omnis_test:${OMNIS_TEST_DB_PASSWORD}@${port}/omnis_test"
make check
```

Volumul este `OMNIS_TEST_PROJECT` + `_pgdata`, montat la `/var/lib/postgresql` (PG18 are `PGDATA=/var/lib/postgresql/18/docker`). Portul este atribuit dinamic **numai pe 127.0.0.1**; citiți-l din nou după orice `up`/recreare a containerului. Fixture-urile cer un context Docker pe socket Unix local (fără `DOCKER_*` moștenite), verifică proiectul, imaginea, bindul și volumul, apoi compară identitatea clusterului PostgreSQL conectat cu cea a containerului înainte de CREATE/DROP pe baze disposable cu nume UUID. Un daemon Docker remote nu atestă `127.0.0.1` al hostului de test; orice precondiție lipsă dă exit nenul, nu SQLite/skip. Verificați numele proiectului și al volumului înainte de orice intervenție Docker. Docker inspect poate expune parola sintetică administratorilor hostului; nu folosiți această topologie cu date reale.

Conexiunile API/migrator și fixture-urile refuză orice setare moștenită `PG*` din libpq și orice parametru query în `OMNIS_DATABASE_URL`/`OMNIS_TEST_DATABASE_URL`: acestea pot redirecționa hostul efectiv chiar dacă autoritatea URL pare să indice instanța test. Configurați doar URL-ul explicit, fără `?host=`, `?port=` sau fișier service. Readiness compară schema fizică a `InstanceControl` din PG18, inclusiv **toate** defaulturile și constrângerile `NOT NULL` validate și enforced; un stamp Alembic sau `attnotnull` singur nu dovedește compatibilitatea.

`make check` cere și dependențele existente de documentație/anti-slop din `tools/development/README.md`; nu instalează automat nimic. Dacă `uv` din PATH nu este 0.12.19, instalați pinul separat și transmiteți `UV=/cale/către/uv-0.12.19` la Make. `make test-api` descoperă toate testele API/control, în afara migrărilor executate separat de `make test-migrations`. Wheelul este instalat cu dependențe exportate din lock într-un venv scratch, apoi migrează o DB goală și rulează supervisorul/API-ul real **din afara checkoutului**, prin socket Unix și TCP loopback. Guardul Python de test are control negativ de egress; nu este sandbox OS și nu închide G-NET.

Migrarea este un job explicit înaintea pornirii procesului API:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -I -m omnis.migrate
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -m uvicorn omnis.api:create_app --factory --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

Se poate folosi același modul `omnis.migrate` dintr-un wheel instalat; `api/alembic.ini` este doar pentru comenzi Alembic din checkout. API nu migrează la startup și nu repară singletonuri lipsă. Migrarea `downgrade` este refuzată deliberat: un revert Git nu readuce datele; pentru o DB existentă cereți backup/restore verificat înainte de orice upgrade. P0.2 adaugă `0002_local_sessions`, `0003_instance_lifecycle` și `0004_pairing_receipts`; testele fac upgrade de la P0.1 păstrând identitatea/admiterea închisă. Nu s-a migrat nicio DB personală sau de producție.

La final, opriți **numai** proiectul de test verificat: `docker compose -f ops/compose.test.yaml down` în același shell cu `OMNIS_TEST_PROJECT` setat. Nu folosiți `down -v`; volumul rămâne disponibil pentru inspecție sau restaurare. Nu opriți containere selectate doar după port/PID. Absența DB/uv/Docker blochează gate-ul, nu certifică readiness.

## Supervisor și control privat

`OMNIS_CONTROL_DIR` este o cale absolută/canonică spre un director **existent**, al operatorului, mod `0700`, în afara repo-ului. Ancestorii nu pot fi deținuți de alt UID sau world-writable; un segment group-writable este acceptat numai dacă se află deja sub o frontieră owner-only. Nu folosiți un root temporar public, symlinkuri sau runtime-ul personal Hermes. Pentru Linux, calea completă a socketului trebuie să încapă în limita AF_UNIX. P0.4 va crea/verifica rootul XDG și mappingul UID în instalare; P0.2 exercită procese locale cu același UID.

Pornire separată, după migrare și provisionarea explicită a directorului privat:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" OMNIS_CONTROL_DIR="/cale/privata/existenta" api/.venv/bin/python -I -m omnis.supervisor
```

Singurul anunț de startup este `SUPERVISOR_READY`. Acesta înseamnă control inert cu lease, **nu admitere deschisă**. Procesul nu folosește Docker, shell sau conturi; un al doilea owner este refuzat. Heartbeat la 1 secundă, lease 5 secunde; pierderea autorității/DB închide serviciul bounded. SIGTERM închide controlul și eliberează lease-ul; un kill lasă expirarea și takeoverul să fence-uiască ownerul vechi. API restart nu creează supervisor și nu deschide admiterea.

Protocolul local: un obiect JSON pe linie, versiune `1`, capability per boot și comandă tipizată; maximum 4096 bytes, 16 clienți activi, 4 secunde pentru request și 1 secundă pentru răspuns. `control.sock`, `control.cap` și lockul sunt `0600`; capability se rotește la restart și nu apare în output. Peer-ul Linux `SO_PEERCRED` și capability sunt ambele obligatorii. Același UID/root malițios rămâne exclus din garanție. Nu copiați capability în chat/argv/URL/loguri.

Operații: `status`; `pairing` cu `instance_id`, UUID `issuance_id` și digest SHA-256; `open`, `shutdown`, `finalize` cu `instance_id`, UUID `command_id` și `expected_generation`. Nu există clientul CLI de produs încă. Emitentul local de pairing va fi launcherul P0.4; testele generează numai coduri sintetice, trimise ca digest prin IPC. O emitere nouă invalidează codul anterior fără resetarea rate limitului. Receiptul durabil leagă UUID-ul de digest și de expirarea inițială: retryul nu prelungește TTL și nu reactivează un cod consumat/expirat/înlocuit; UUID cu alt digest sau cod refolosit cu alt UUID dă `PAIRING_CONFLICT`. Migrarea `0004` invalidează codurile pending anterioare, fără identitate de emitere, și păstrează sesiunile existente. Nu se șterg receipturi ca mecanism de reemitere.

Shutdown persistă întâi bariera. Receipturile păstrează rezultatul original, iar răspunsul include separat statusul curent; UUID refolosit cu payload diferit sau generație stale dă conflict. `finalize` este numai finalizarea controlului **inert**, după quiescență; nu atestă containere oprite. Redeschiderea cere și un epoch nou plus comandă explicită. P0.4 trebuie să verifice separat identitatea/receiptul serviciilor oprite. Un shutdown incomplet rămâne închis la restart.

## Suprafața browserului, fără UI încă

| Rută | Contract |
|---|---|
| `POST /api/pairing` | Body JSON `{code: ...}` numai prin canalul HTTP local; Origin exact obligatoriu. Cod de 5 minute, consum atomic, cel mult 5 încercări/minut per instanță, inclusiv cele reușite. Nu îl puneți în URL. |
| `GET /api/session` | Sesiune validă; întoarce tokenul CSRF legat de ea. |
| `POST /api/logout` | Origin exact, cookie și `X-CSRF-Token`; revocare server-side, nu oprirea instanței. |
| `GET /api/instance` | Proiecția DB autenticată: identitate/generație/barieră/lease/quiescență; fără configurații secrete sau metrici inventate. |

Sesiuni opace de 12 ore, digest-only în DB; cookie `HttpOnly; SameSite=Strict; Path=/`, fără Domain. `Secure` nu este pretins pe HTTP loopback. Răspunsurile `/api` sunt `no-store`; erorile nu reflectă inputul și au cod tipizat plus UUID server-side `correlation_id`, identic cu headerul `X-Correlation-ID`. ID-urile primite de la client nu sunt adoptate; răspunsurile IPC au și ele un correlation ID propriu. Body maximum 4096 bytes/3 secunde; pairing, logout și citirea statusului au separat deadline de 3 secunde pentru operația DB, cu rollback verificat pentru tranzacțiile încă necomise și `503 CONTROL_TIMEOUT` fără cookie de succes. Anularea în timpul COMMIT poate avea rezultat incert: este necesar readback, nu retry orb; deadline-ul este per operație, nu plafon total HTTP sau certificare a oricărui cleanup de driver. Query strings refuzate. Origin străin/`null`/multiplu este refuzat și la citiri; mutațiile refuză și Origin absent. Toate rutele `/api`, în afara schimbului de pairing, cer sesiune; toate mutațiile autentificate cer CSRF. Nu există CORS wildcard/SSE/admin generic. Formula „fără codes în JSON” privește outputul CLI/status/log; codul secret trebuie transmis în body-ul schimbului local, nu reflectat în răspuns. Dezactivați access logul Uvicorn conform comenzii de mai sus.

O excepție neașteptată înainte de începerea răspunsului produce `500 INTERNAL_ERROR`, `no-store` și același UUID în body/header/logul structurat, fără textul excepției. După începerea răspunsului conexiunea este întreruptă cu diagnostic sanitizat, nu se emite un al doilea răspuns. Anulările taskului nu sunt convertite în 500.
