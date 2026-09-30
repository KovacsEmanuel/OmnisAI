# P0.4 — integrarea autorizată a fixture-ului DB privat

**Contract de lucru, încă în curs.** Bază locală `7916dea86a74ea96932285d65b27ae46b9516fe5`, branch `p04-control-topology-wip`. Operatorul a autorizat explicit integrarea WIP/DB disposable după amendamentele arhitecturale. Nu este autorizarea unui assessment, provider, launcher sau promovarea ownerului exec.

## Scop și conservare

Integrarea adoptă cele șase fișiere WIP enumerate în plan §19.2: suport URL în `api/src/omnis/core/db.py`, testele URL/fixture, `ops/compose.test.yaml`, `ops/run_test_db_gate.py` și testele development ale runnerului. Extinde numai conftest, Make/CI și documentele de utilizare/status necesare aceluiași contract. Sursa `documents/Omnis_Notite_Originale.html` rămâne untracked, nemodificată și nestaged. Fără reset/stash sau includerea altor schimbări.

Backupul WIP și hashurile before sunt în `/home/kali/.hermes/cache/scratch/omnis-db-integration-7916dea/`; nu sunt runtime data și nu se publică drept implementare. La descoperire existau containere pornite străine, inclusiv un proiect DB Omnis anterior; niciunul nu este adoptat/oprit. Imaginea PG18.6 fixată există local. API/CLI venv sunt Python 3.13.15; Node/npm/uv ambientale nu sunt pinurile, deci folosim executabilele izolate verificate, fără schimbarea toolurilor globale.

## Acceptare și implementare minimă

1. URL PostgreSQL cu host UDS codificat canonic ajunge la același socket prin SQLAlchemy/psycopg; host absent, query/PG overrides și encodări ambigue refuzate; TCP intern de produs păstrat.
2. Un root scratch **nou**, privat, cu date/secret sintetice și proiect unic. PG rulează cu UID-ul operatorului, network_mode=none, fără porturi/privileged/capabilities adăugate; SCRAM inclusiv local. Nu migrează date existente.
3. Runnerul atestă endpoint/daemon, image/container/project/mounts/socket și system_identifier; scrie un manifest privat fără parolă. Același attestor este consumat de conftest înainte de CREATE/DROP, plus verificarea identității conexiunii reale. Configurația nu se rezolvă prin port lookup sau loopback presupus.
4. Runnerul rulează gate-ul complet existent, nu îl înlocuiește cu o suită redusă; Make/CI folosesc aceeași cale și medii exacte. Timeout/interrupt trebuie să oprească grupul de teste propriu înainte de DB teardown, cu rezultate incerte distincte.
5. Probe pozitive/negative înainte de DDL, apoi `make check` real pe DB proprie nouă, inclusiv migrări/installed wheel/backend E2E. Review independent pe cod și corecții. Pe lipsă prerechizit se raportează blocker, nu date sintetizate ca output.
6. La final se verifică absența exactului container/rețelei/socketului propriu și păstrarea PGDATA/manifestului/logurilor private, fără cleanup global. Cod/config/docs în commituri mici; checkoutul de verificare finală fără modificări tracked intenționate.

## Efecte și rollback

Before: rootul/proiectul/CID-ul probei sunt absente; intenția și ID-urile nesensibile sunt înregistrate înainte/după creare. Singurele DDL sunt în clusterul nou atestat. După test runnerul oprește și elimină **numai CID-ul verificat**, păstrând bind data. Recuperarea manuală cere reatestarea endpoint/daemon/CID/image/labels/mounts înainte de `docker --host <endpoint> stop <cid>` și `rm <cid>`; fără prune/down -v/ștergere de date ori selectare numai după prefix. Un revert Git nu oprește containere sau restaurează DB.

## Stare inițială verificată

- Patru teste URL WIP: PASS fără DB; baseline HEAD urmează să fie comparat inert pentru RED.
- Opt teste development ale runnerului: PASS (config și cleanup cu controale sintetice), nu dovadă live.
- Conftest/CI TCP versus Compose UDS: incompatibilitatea este prezentă; runnerul este încă probe-only.
- Nicio DB nouă nu a fost pornită la acest checkpoint. G00 rămâne deschis și launcherul nu intră în această felie.

Rezultatele finale PASS/FAIL/BLOCKED/NOT-RUN, review-urile și commiturile se adaugă după execuție.
