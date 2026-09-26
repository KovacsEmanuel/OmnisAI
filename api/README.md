# API P0.1 — utilizare și limite

Acesta este numai control plane-ul API/PostgreSQL. Nu pornește `omnis`, dashboardul, supervisorul, Hermes, provideri sau evaluări. `/health/live` arată procesul; `/health/ready` este 200 numai pentru PostgreSQL 18 migrat și schema `0001_instance_control`, în timp ce `dashboard_ready` și `assessment_ready` rămân false. API-ul trebuie pornit explicit pe loopback; Host-ul permis în această felie este exact `127.0.0.1:8765`.

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

Volumul este `OMNIS_TEST_PROJECT` + `_pgdata`, montat la `/var/lib/postgresql` (PG18 are `PGDATA=/var/lib/postgresql/18/docker`). Portul este atribuit dinamic **numai pe 127.0.0.1**; citiți-l din nou după orice `up`/recreare a containerului. Fixture-urile testează proiectul, imaginea, bindul și volumul înainte de CREATE/DROP pe baze disposable cu nume UUID; lipsa unei precondiții dă exit nenul, nu SQLite/skip. Verificați numele proiectului și al volumului înainte de orice intervenție Docker. Docker inspect poate expune parola sintetică administratorilor hostului; nu folosiți această topologie cu date reale.

`make check` cere și dependențele existente de documentație/anti-slop din `tools/development/README.md`; nu instalează automat nimic. Dacă `uv` din PATH nu este 0.12.19, instalați pinul separat și transmiteți `UV=/cale/către/uv-0.12.19` la Make. `make test-api`, `make test-migrations` și `make check-api-wheel` sunt probele P0.1 individuale; wheelul este instalat cu dependențe exportate din lock într-un venv scratch, apoi migrează o DB goală **din afara checkoutului**.

Migrarea este un job explicit înaintea pornirii procesului API:

```sh
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -I -m omnis.migrate
OMNIS_DATABASE_URL="$OMNIS_TEST_DATABASE_URL" api/.venv/bin/python -m uvicorn omnis.api:create_app --factory --host 127.0.0.1 --port 8765 --no-proxy-headers
```

Se poate folosi același modul `omnis.migrate` dintr-un wheel instalat; `api/alembic.ini` este doar pentru comenzi Alembic din checkout. API nu migrează la startup și nu repară un `InstanceControl` lipsă. Migrarea `downgrade` este refuzată deliberat: un revert Git nu readuce datele; pentru o DB existentă cereți backup/restore verificat înainte de orice upgrade. P0.1 nu efectuează upgrade dintr-o revizie precedentă, fiind prima revizie.

La final, opriți **numai** proiectul de test verificat: `docker compose -f ops/compose.test.yaml down` în același shell cu `OMNIS_TEST_PROJECT` setat. Nu folosiți `down -v`; volumul rămâne disponibil pentru inspecție sau restaurare. Nu opriți containere selectate doar după port/PID. Absența DB/uv/Docker blochează gate-ul, nu certifică readiness.
