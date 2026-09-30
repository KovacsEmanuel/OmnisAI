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

## Probe de integrare în curs

- Review-ul independent inițial (`preintegration-review.md` în scratch) a identificat virgula libpq în host UDS, nepotrivirea conftest/CI, limitele lifecycle și lungimea căii. Virgula și aliasurile de cale au fost reproduse RED, corectate și verificate în 11 teste URL/dialect; commit `132c6f0`. Niciun driver nu a fost conectat de aceste teste pure.
- Conftest folosește acum receiptul JSON strict de la același attestor `--attest`, apoi verifică system_identifier pe conexiunea reală; URI-ul encoded rămâne în env/fixture, decode numai în engine/kwargs driver. Controalele unit/config/process ale runnerului au 18 PASS, inclusiv timeout, exit timpuriu cu descendent și SIGTERM real către procesul de test, nu containere străine. Ruff/format și mypy API au trecut; nu este încă verdictul review-ului final.
- **Prima probă reală țintită: PASS, nu gate complet.** Comandă `api/.venv/bin/python -I ops/run_test_db_gate.py --check --target test-db-contract --uv <uv-0.12.19> --timeout-seconds 300`, exit 0; 31 teste fixture/URL trecute, inclusiv CREATE/INSERT/reconectare/readback/DROP pe DB UUID proprie și refuzul contextului/clusterului greșit. Proiect `omnis-p01-9268bb62401b48f0b8742f734eab5482`, CID `acd66ba8357b97f1a11228b00e88677ec8459924e21540ede57b1651de9316c4`, PG system ID `7691278540931186718`. Root privat păstrat `/home/kali/.hermes/cache/scratch/db-2ac5d6da834441c2`, log `gate.log`; manifest/parolă 0600, root 0700. Readback separat a confirmat zero containere/rețele pentru proiect, socket absent și PG_VERSION=18 păstrat. Nu s-a adoptat DB-ul anterior.
- Primul `make check` în shell background a fost refuzat la preflight, exit 2, înainte de intenție/creare DB; mediul shellului background nu a păstrat selecția executabilelor din cel foreground. Relansarea declară PATH-ul pin-uit în aceeași invocare și a confirmat Node 24.21.0/npm 11.19.0, fără override-uri Docker/Compose/PG. Gate-ul complet rulează separat pe proiect nou `omnis-p01-869d4d59e8c9481e964162b9c6e98623`, root `/home/kali/.hermes/cache/scratch/db-d615a743646d416b`; **încă fără verdict** la acest checkpoint.

## Eșecuri reale și remedieri delimitate

- Gate-ul de pe `db-d615a743646d416b` a trecut 214 API și 9/10 migrări, dar `test_installed_wheel_migrates_without_checkout` a eșuat în consumatorul `process_guard.py`, încă TCP-only. Guardul a fost adaptat strict la DB UDS declarată, cu RED→GREEN pentru pozitiv și deny Unix străin/TCP/DNS, fără lărgirea la toate socketurile. Pe o DB nouă `omnis-p01-2add2f92f79b4145923c9893ca7f439f`, root `db-f89720813e574595`, toate **10 migrări** au trecut; cleanup/readback separate au confirmat lipsa resurselor proprii și păstrarea datelor.
- Gate-ul următor, `omnis-p01-b34ec0441f1641ab94f58d40472464d4` / `db-3048442fbd734e6b`, a trecut 218 API și 10 migrări, dar a eșuat la verificarea web care încă presupunea `make -n check` reușit. Testul păstrează acum includerea reală a contractelor web prin check-components/check-web și CI, verificând separat refuzul unui dry-run canonic. Șase teste web tooling și `make test-contracts` au trecut după corecție; nu am eliminat poarta web. Cleanup-ul acestui proiect a fost verificat separat.
- Review-ul de cod (`integration-code-review.md` în scratch) a găsit un P1: grupul make nu acoperea descendenții detașați de suita existentă. Reproducerul real a lăsat copilul viu sub un fuse de rescue ținut de observator; testul a eșuat înaintea corecției. Remediul este numai în runnerul existent: owner de gate dedicat/subreaper înainte de spawn, adoptați pin-uiți prin pidfd, drain/reap în runde pentru nepoți târzii, receipt strict family_drained înainte de DB teardown. Incertitudinea păstrează DB pentru recuperare. Nu s-a modificat ownerul produsului sau launcherul.
- Suitele runner au **22 teste PASS**, cu cazuri reale detached early-exit/timeout/TERM, nepot adoptat după moartea părintelui și copil străin lansat ulterior lăsat viu. Observatorul păstrează fuse-ul până după verificarea rezultatului, apoi face rescue independent; nu credităm EOF/natural timeout drept cleanup. Re-review-ul punctual este în curs, iar gate-ul complet se rerulează pe acest cod.

## Gate complet local și ultimul guard de teardown

**make check, exit 0**, pe proiectul `omnis-p01-8f7785230f2c402c9dafff56a83bff3b`, CID `870cf96dcf80c2bda885cfed97e433280d0e718bfe875690c6003a1644c0fc4a`, root `/home/kali/.hermes/cache/scratch/db-689c6a1176554f06`: documentație 54, development 34, API 218, migrări 10, web tooling 6, web unit 20, browser E2E 7, CLI 43 sursă + 43 wheel, CLI/DB 1, release 31. Lint/type/contracts/audit/build incluse. Receiptul real `gate.log.result.json` este `{schema_version:1,code:0,family_drained:true}`. Readback Docker separat: zero containere/rețele ale proiectului, socket absent, PG_VERSION=18 păstrat. Aceste valori sunt rezultate, nu sume transferate de la alte încercări; verificarea remote CI și G00 nu rezultă din ele.

Re-review-ul bounded (`cleanup-fix-review.md`) a confirmat ownership-ul dedicat și consumatorii, dar a demonstrat un ultim P1: OSError din semnalizarea ownerului putea lăsa flagul părintelui family_drained=true și permite DB teardown. Remediul exact recomandat a fost reprodus RED și aplicat: **False înainte de run_gate, True numai după întoarcerea lui validată**. Regresia fault-injected cere zero apeluri cleanup DB; 24 teste runner trec. Această corecție conservatoare nu este atribuită retrospectiv gate-ului complet de mai sus; primește re-review punctual și rerulare finală pe codul comis.

Între aceste două review-uri, integrarea a probat și reap-ul adoptaților deja terminați **în timpul** gate-ului: testul existent `test_owner_death_before_server_marker_releases_its_child` a rămas nemodificat, iar runnerul a preluat obligația de reaper. Inițial full gate a dat 1 failed/217 passed; după fix, regresia focalizată și acel test real au trecut, cu receipt family_drained=true. Nu am slăbit oracolul produsului și nu am schimbat ownerul P0.

## Commituri și închidere

- `dcb75c3` — autorizare, scope și rollback înainte de efecte.
- `132c6f0` — URL UDS canonic/single-destination + probe.
- `3750bff` — consumatorul installed-process guard acceptă numai DB UDS declarată.
- `0c61a78` — fixture/attestor/runner/Make/CI integrate, inclusiv guardul final de teardown și controalele sale.

Codul, istoricul erorilor și documentele de utilizare sunt păstrate separat de datele private. Următoarea felie este launcherul instalat din plan §19.2, nu încă o extindere a harnessului. Verdictul final de re-review și rerularea pe revizia comisă se adaugă înaintea predării; fără push implicit.
