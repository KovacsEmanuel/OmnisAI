# Review independent — cleanup wait, baf5922

**Verdict Stage 1: APPROVED_FOCUSED_SOURCE_SCOPED. Niciun blocker concret în cele două linii și contextul lor.** Review consemnat înaintea oricărei execuții QA; ceas observat 2026-10-29T23:01:59.405438+00:00. Admiterea Stage 2 este condițională pe preflightul fără efecte și mandatul explicit al părintelui, pentru o singură invocare existentă, nu retry automat.

## Identitate și scope

- Worktree `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`; HEAD `baf592220415b7e5d199d77b71c1538e9dcec748`; tree `aa53b50706e84ba494825a1581e4bdc6d9e75557`.
- Bază `0c8bff7676b0f0be23b27b77da63ff57ee08cdf0`; diff SHA256 `8db1242eca45f6a744a6f7c2aaa03f84882dc7bd52d474997044e15bae9bc20a`.
- Freeze `/home/kali/.hermes/cache/scratch/settings-inline-feedback-cleanup-wait-20261030/freeze-supplement.json`, SHA256 `94cea4956ed9c61267b5e8e86d703060bda83cc72d7bb08df2735f24ede30065`. Toate cele 11 intrări sursă și 5 assets verificate direct, egale cu freeze. Tracked/index curate; patru linkuri de dependențe preexistente păstrate.
- Singura deltă: `web/tests/e2e/settings-models.mjs:222,275`, `page.unroute(pattern)` devine `await page.unrouteAll({ behavior: 'wait' })`, după resolve-ul gate-ului existent. Citite callerul `runSettingsRemove`, cele trei route-uri locale și contextul `run.mjs`/consumerul API/PG.
- Reach necesar: finalizator Save & connect și finalizator receipt Assignments. Nu se schimbă produs/API/schema/fixtures/config/exports/dependencies/payload/oracle/deadline.

## Corectitudine, siguranță și dispoziții

1. La linia222, `releaseAdmission.resolve()` precede wait-ul nativ. Callbackul local205–209 a primit HTTP202 real și poate termina `route.fulfill` înaintea actualizării patternurilor. Nu se așteaptă un gate încă închis; callbackurile GET de pe același pattern doar continue. Deadlines120s driver/600s runner rămân intacte.
2. La linia275, `gate.resolve()` precede wait-ul. Callbackul local256 poate termina `route.continue`. În fiecare fază există numai acel route page-local: Remove116–123 este deja încheiat și unrouted la131; provider receipt gate256 este instalat abia după cleanup222. Prin urmare unrouteAll nu elimină un handler viitor ori străin în callerul actual.
3. Allowlistul extern este `context.route` în `run.mjs:85–89`, nu `page.route`; operația page-local nu-l elimină. Nu există schimbări de `ignoreErrors`, catch/promise-helper, timeout, secret checks ori oracle de siguranță.
4. Sursa instalată Playwright `coreBundle.js:61752–61774` confirmă: unroute folosește default și actualizează patterns fără `stop`; unrouteAll(wait) așteaptă `stop(wait)` înainte de update. `60168–60188` așteaptă invocările active și nu activează ignorarea excepțiilor. Este folosirea minimă a API-ului existent, nu o mască pentru eroare.
5. Diagnosticul nativ pereche al părintelui (server local inert+Chromium, fără App/PG) este păstrat drept mecanism suficient actual: default reproduce already-handled/202, wait nu. Nu demonstrează cauza exclusivă a aserțiunii inițiale istorice care nu a fost reținută, nici defect App.
6. Reviewurile produsului și reviewul final0c8bff sunt reutilizate numai pe bytes neschimbați; nu redeschid aici cele172 component și4 scenarii SOURCE native. FAIL55.01s/45.69s, legacy counter2 EXHAUSTED și două cicluri SOURCE rămân, fără reset. Lipsa probei fresh nu este blocker circular al reviewului acestei corecții.

## Stage 2 admis numai condiționat

Exact consumer existent, o singură dată din worktree, după no-effect argv/pins/volatile-access preflight:

`PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-remove-ui-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600`

Obligații neschimbate: Remove18→17/lost reply/no resend/history, readd newID18, Save & connect202/rowConnecting/Stop/COMPLETED-current-latest, al doilea Start separat64, Save assignments quiet/receipt/toast/roles, unsent replacement/no write, Disable/Reconnect rev3/stale,12browser mutations/8GET+2POST peer noi,13table deltas+istoric și restart API egal fără scrieri. Fixture fresh proprie; cleanup exact prin ownerul existent și readback separat. La orice FAIL se oprește după settlement, păstrând prima eroare observată; fără autofix/relansare.

Reviewul nu certifică runtime, integrare, instalare, T1 ori estetică. Nu am modificat cod/teste/repo/Git, nu am comis. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO.

Am omis re-auditul și rerunurile neschimbate; nu certific toate combinațiile/cross-browser/screen readers.
Risc: un singur consumer real mai trebuie executat și verificat; aprobarea și închiderea finală aparțin părintelui.
