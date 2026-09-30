# P0.4 — integrarea autorizată a fixture-ului DB privat

**Integrare închisă — PASS local.** Gate-ul complet a trecut pe revizia `bd06bcd45671c1d45e804f955bf0abee6d6ef163`, cu review-uri și cleanup independent verificate. Secțiunile inițiale de mai jos păstrează cronologia checkpointurilor, nu blocaje încă active. G00, launcherul și CI remote rămân separate.

**Contract autorizat.** Bază locală `7916dea86a74ea96932285d65b27ae46b9516fe5`, branch `p04-control-topology-wip`. Operatorul a autorizat explicit integrarea WIP/DB disposable după amendamentele arhitecturale. Nu este autorizarea unui assessment, provider, launcher sau promovarea ownerului exec.

## Scop și conservare

Integrarea adoptă cele șase fișiere WIP enumerate în plan §19.2: suport URL în `api/src/omnis/core/db.py`, testele URL/fixture, `ops/compose.test.yaml`, `ops/run_test_db_gate.py` și testele development ale runnerului. Extinde conftest, Make/CI, documentele de utilizare/status și consumatorii necesari aceluiași contract; corecția fixture-ului CLI a primit autorizarea separată documentată mai jos. Sursa `documents/Omnis_Notite_Originale.html` rămâne untracked, nemodificată și nestaged. Fără reset/stash sau includerea altor schimbări.

Backupul WIP și hashurile before sunt în `/home/kali/.hermes/cache/scratch/omnis-db-integration-7916dea/`; nu sunt runtime data și nu se publică drept implementare. La descoperire existau containere pornite străine, inclusiv un proiect DB Omnis anterior; niciunul nu este adoptat/oprit. Imaginea PG18.6 fixată există local. API/CLI venv sunt Python 3.13.15; Node/npm/uv ambientale nu sunt pinurile, deci folosim executabilele izolate verificate, fără schimbarea toolurilor globale.

## Acceptare și implementare minimă

1. URL PostgreSQL cu host UDS codificat canonic ajunge la același socket prin SQLAlchemy/psycopg; host absent, query/PG overrides și encodări ambigue refuzate; TCP intern de produs păstrat.
2. Un root scratch **nou**, privat, cu date/secret sintetice și proiect unic. PG rulează cu UID-ul operatorului, network_mode=none, fără porturi/privileged/capabilities adăugate; SCRAM inclusiv local. Nu migrează date existente.
3. Runnerul atestă endpoint/daemon, image/container/project/mounts/socket și system_identifier; scrie un manifest privat fără parolă. Același attestor este consumat de conftest înainte de CREATE/DROP, plus verificarea identității conexiunii reale. Configurația nu se rezolvă prin port lookup sau loopback presupus.
4. Runnerul rulează gate-ul complet existent, nu îl înlocuiește cu o suită redusă; Make/CI folosesc aceeași cale și medii exacte. Timeout/interrupt trebuie să dreneze familia de procese de test proprie înainte de DB teardown, cu rezultate incerte distincte.
5. Probe pozitive/negative înainte de DDL, apoi `make check` real pe DB proprie nouă, inclusiv migrări/installed wheel/backend E2E. Review independent pe cod și corecții. Pe lipsă prerechizit se raportează blocker, nu date sintetizate ca output.
6. La final se verifică absența exactului container/rețelei/socketului propriu și păstrarea PGDATA/manifestului/logurilor private, fără cleanup global. Cod/config/docs în commituri mici; checkoutul de verificare finală fără modificări tracked intenționate.

## Efecte și rollback

Before: rootul/proiectul/CID-ul probei sunt absente; intenția și ID-urile nesensibile sunt înregistrate înainte/după creare. Singurele DDL sunt în clusterul nou atestat. După test runnerul oprește și elimină **numai CID-ul verificat**, păstrând bind data. Recuperarea manuală cere reatestarea endpoint/daemon/CID/image/labels/mounts înainte de `docker --host <endpoint> stop <cid>` și `rm <cid>`; fără prune/down -v/ștergere de date ori selectare numai după prefix. Un revert Git nu oprește containere sau restaurează DB.

## Stare inițială verificată

- Patru teste URL WIP: PASS fără DB; baseline HEAD urmează să fie comparat inert pentru RED.
- Opt teste development ale runnerului: PASS (config și cleanup cu controale sintetice), nu dovadă live.
- Conftest/CI TCP versus Compose UDS: incompatibilitatea este prezentă; runnerul este încă probe-only.
- Nicio DB nouă nu a fost pornită la acest checkpoint. G00 rămâne deschis și launcherul nu intră în această felie.

## Probe de integrare — cronologie

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

## Extindere punctuală autorizată: precondiția CLI de backpressure

Rerularea pe `afaae96` (`proc_51b5e8517cbf`, proiect `omnis-p01-64df6bdc092d46f68d9cb21d56bf92f4`, root `db-e55661ef203b4414`) s-a încheiat cu exit 2. Au trecut 54 docs, 35 development, 218 API, 10 migrări, 6 web tooling, 20 web unit și 7 E2E; CLI sursă a avut un eșec din 43 la `test_process_sigterm_aborts_nonreading_browser_after_large_asset`: `request did not reach backpressure`. Receiptul confirmă `code=2,family_drained=true`; readback separat: container/rețele/socket proprii absente, PGDATA păstrat. Nu reportăm această execuție ca PASS și nu îi transferăm rezultatul execuției anterioare.

Testul și forwarderul sunt neschimbate față de baza `7916dea`; aceeași aserțiune a eșuat în 0.441 s cu `cli/.venv/bin/python -I -m unittest discover -s cli/tests -p test_forwarder.py -k test_process_sigterm_aborts_nonreading_browser_after_large_asset -v`, fără DB sau runner. Operatorul a autorizat explicit investigarea/corectarea punctuală și rerularea gate-ului complet. Scop suplimentar: numai fixture-ul/regresiile CLI necesare acestei precondiții; fără launcher, rescriere a forwarderului, eliminarea aserțiunilor de progres/stop sau ajustări globale de kernel. Probe bounded pe buclă locală/UDS proprii, analiză înainte de editare, review independent, commit separat. Dacă mecanismul cere extindere de produs, se raportează înainte de intervenție. Rollback: revert al commitului punctual, fără schimbare de DB existentă.

### Diagnostic și remediu CLI fără schimbarea produsului

Diagnosticul pasiv al aceluiași test a dat 2 PASS/1 FAIL în trei execuții. În cazul FAIL, send_body s-a terminat normal (fără excepție), forwarderul era viu și drain-ul răspunsului era încă pending; bufferul TCP de recepție al forwarderului (`ss` rb) crescuse la 4210537 bytes, față de 987430 în cele două PASS, deși browserul avea SO_SNDBUF=8192 în toate. Corpul încăpea astfel în TCP fără să oblige senderul browserului să aștepte. Nu era regresie a runnerului DB sau a opririi forwarderului, ci precondiție de fixture dependentă de autotuning.

Remediul din `cli/tests/test_forwarder.py` fixează SO_RCVBUF numai pe listenerul fixture-ului, înainte de accept, cu readback 8192; shim-ul procesului copil execută apoi entrypointul real instalat prin `runpy`, cu aceleași argumente. Nu schimbă sursa produsului, limitele de trafic, deadline-urile, aserțiunile send/drain pending, observarea octeților reali, SIGTERM sau cleanup-ul. Niciun sysctl/global socket tuning. Probe: testul focalizat PASS, apoi trei repetări diagnostice PASS cu rb8192 și ambele direcții pending, 43 teste CLI sursă + 43 în wheel instalat din afara checkoutului PASS, Ruff/format și diff check PASS. Review independent al deltei: **PASS bounded** (`cli-backpressure-review.md`), inclusiv comparație AST care confirmă că toate aserțiunile existente au rămas intacte și entrypointul instalat este cel executat. Verificarea ad-hoc a diagnosticului a trecut separat cu trei observații reale; verificatorul temporar a fost șters. Noul gate complet se rulează după commit; aceste probe nu îl substituie.

## Verdict final și probe pe codul comis

**PASS — `make check`, exit 0**, proces `proc_9a588aebb70a`, revizie testată `bd06bcd45671c1d45e804f955bf0abee6d6ef163`. Checkoutul tracked a fost curat la pornire și după execuție; nu s-a schimbat cod/config/test în timpul gate-ului. Comanda efectivă, cu toolchain-ul izolat deja pregătit:

```sh
export PATH="/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin:/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools:$PATH"
make check UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
```

| Componentă executată în această rulare | Rezultat |
|---|---|
| Documente și readers | 54 teste PASS; cinci HTML sincronizate |
| Development | 35 teste PASS, inclusiv 24 controale ale runnerului; anti-slop PASS |
| API | 218 teste PASS |
| Migrări / installed wheel | 10 teste PASS |
| Web | 6 tooling + 20 unit + 7 E2E pe backend real PASS |
| CLI | 43 sursă + 43 wheel instalat din afara checkoutului + 1 integrare DB PASS |
| Release/install checks | 31 teste PASS |
| Lint / format / typecheck / contracte / audit / build | PASS; `git diff --check` final PASS |

Manifestul și logul execuției sunt în `/home/kali/.hermes/cache/scratch/db-be972dd092e64dcb/` (`fixture.json`, `gate.log`, `gate.log.result.json`). Proiect `omnis-p01-4712316ea42e4e39ae7dfcad5838b573`, CID `40d7f71271c0cf1b682b4c78b149c57dfdab21dc0237f60a0b08697748074a92`, PostgreSQL 18.6, system_identifier `7691317941618749470`; imaginea este pinul atestat de runner, nu un tag floating.

**Cleanup verificat independent:** interogare pe endpointul exact din manifest și comparație daemon_id înainte/după; CID absent, zero containere/rețele pentru proiect, socket absent prin lexists. Receipt `{schema_version:1,code:0,family_drained:true}`; PG_VERSION=18 păstrat. Root 0700, manifest și fișierul de credențiale 0600, toate deținute de operator; conținutul credențialelor nu a fost afișat/comis. Datele rămân în scratch, nu reprezintă backup permanent. Nu s-a adoptat sau oprit un cluster existent.

**Review și conservare:** review-ul de integrare și re-review-urile au toate constatările concrete închise; ultimul guard DB și delta fixture CLI au PASS independent bounded, nu certificare universală. Verificarea separată a cititoarelor a trecut 116 controale Chromium fără erori JS/cereri externe; cititoarele n-au fost schimbate de corecția CLI. Cele șase copii WIP originale au hashurile inițiale, iar HTML-ul original este byte-identic și rămâne untracked/nestaged. Codul produsului CLI nu s-a schimbat; nicio migrare de schemă nouă.

**NOT-RUN / neînchis în această felie:** CI remote, targeturile OCI opt-in `check-control-image` / `check-installed-image` / `check-installed-control`, launcherul, provideri/model/Jev, assessment sau comparație live Omnis–Strix. G00 rămâne deschis; gate-ul local nu produce assessment readiness. `make test` este aliasul aceleiași căi; nu este raportat ca a doua execuție independentă. Nu s-a făcut push.

Următoarea felie de produs rămâne launcherul instalat din plan §19.2, cu autorizare proprie. Eșecurile de mai sus sunt păstrate ca istoric; niciun rezultat parțial sau diagnostic ad-hoc nu a fost substituit acestui gate complet.

## Commituri și închidere

- `dcb75c3` — autorizare, scope și rollback înainte de efecte.
- `132c6f0` — URL UDS canonic/single-destination + probe.
- `3750bff` — consumatorul installed-process guard acceptă numai DB UDS declarată.
- `0c61a78` — fixture/attestor/runner/Make/CI integrate, inclusiv guardul final de teardown și controalele sale.
- `afaae96` — documentele de utilizare/status, readers și procedurile de proiect.
- `e2aab07` — verdictul review-ului DB, eșecul CLI și extinderea punctuală autorizată.
- `bd06bcd` — fixture CLI determinist pentru backpressure; revizia gate-ului final.

Codul, istoricul erorilor și documentele de utilizare sunt păstrate separat de datele private. Următoarea felie este launcherul instalat din plan §19.2, nu încă o extindere a harnessului.

**Re-review final al guardului DB: PASS bounded.** `final-guard-review.md` confirmă exact cele două atribuiri ale părintelui și regresia PermissionError, plus reap-ul non-blocking al adoptaților morți, fără semnalizare. Reviewerul a verificat AST/fluxul, nu a rerulat probele live. Codul relevant este în `0c61a78`; documentele și cititoarele în `afaae96`. Rerularea pe acel checkout tracked curat (numai HTML-ul original untracked) a eșuat ulterior la precondiția CLI documentată mai sus, fără editări de cod în timpul execuției. Eșecul nu a schimbat verdictul review-ului punctual, dar a blocat acceptarea până la remediul `bd06bcd` și gate-ul complet PASS consemnat mai sus. Commitul de închidere care conține acest verdict schimbă doar registrul de dovezi, nu codul testat. Fără push implicit.
