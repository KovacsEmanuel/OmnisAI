# Prompt de execuție P1 — B02 → B03/B04 → G01

> Instrucțiune de lucru versionată, **nu plan sau matrice nouă**. Arhitectura §7/§9.3 și UI/UX §0/§2/§3 decid comportamentul; planul §4.2/§6 decide ordinea. Rezultatele P0 sunt în [harta curentă](implementation-status.md). Citește HEAD/status/diff real la intrare; SHA-urile de mai jos sunt numai proveniența acestei pregătiri.

## Intrare și limite

- P0 local inert este `P0_LOCAL_USABLE=PASS_LOCAL_RECORDED` pe VM-ul unui singur operator, nu deployment public. P0 împins pe `origin/p04-control-topology-wip` la `d372295a5fa592e16443944b8ace4fdc0c3f1d18`, verificat prin `git ls-remote`; fără merge/deploy. `documents/Omnis_Notite_Originale.html` este neversionat și protejat.
- **CI remote: verdict necitit.** Repo privat returnează 404 fără login, iar în această sesiune nu este disponibil acces browser/API autentificat. Nu cere token/parolă în chat și nu repeta automat prompturi de login. `make check` local pe SHA-ul împins a ieșit **2 la `uv audit`/OSV** din cauza DNS-ului VM-ului (`https://api.osv.dev/v1/querybatch` timeout), nu dintr-un test de produs: `f0-push6/tmp/db-aae3cc6c81d54ec2`, receipt `code=2/family_drained=true`, CID/rețea/socket proprii absente, PGDATA păstrată și cele10 CID-uri/8 rețele/32 imagini/112 volume străine neschimbate. Docker/PG nu se rerulează pentru reminder. CI rămâne NOT_VERIFIED până la citire autentificată; P1 poate fi **pregătit** fără a pretinde acel PASS.
- P1 este **draft și UI inertă**: nicio inferență, provider, refresh/login target, proxy, browser executor, trafic țintă sau Pause/Run fictiv. Save/Next/Back citesc/scriu numai DB proprie; `assessment_ready=false`, Start run indisponibil cu motiv. Fără importul DEMO, credențiale în obiectiv, metrici fabricate ori alte module P2/P3.
- Skilluri de lucru: `.hermes/skills/omnis-project-status`, `omnis-delivery`, `omnis-api-data`, `omnis-review-qa`; pentru UI `omnis-frontend` și `omnis-accessibility`. Folosește Git/registrele, nu memoria unei sesiuni. Un singur autor pe cale; worktree-uri explicite din HEAD local dacă există autori paraleli. Nu porni Docker/PG în subagenți.

## Felii verticale — fiecare produce un rezultat folosibil

### P1-A / SL05-B02a — primul draft salvat și citit

**Observabil:** prin API autentificat se creează un engagement draft cu nume, autorizație/scope și `assessment_mode` + `objective_text` + `objective_constraints`, apoi se citește identic după o conexiune/proces nou; lista are paginare bounded. `workflow_profile_ref=null` este valid în draft. Full poate salva defaultul **explicit** din arhitectură §9.3; focused gol/whitespace este refuzat. Scope declarativ `ATTACKABLE/VISIT_ONLY/BLOCKED`, origin/port/path/excluderi și fereastra de autorizație nu declanșează IO spre țintă. Nu crea RunSnapshot/MissionSpec înainte de primul consumator.

**Cod atins numai când este necesar:** `api/src/omnis/modules/engagements/` nou (DTO/domain/service/persistence/routes), migrarea Alembic următoare, `api.py` și schema/readiness; teste API/migrări. În prezent nu există modul engagements, `create_app()` include numai sesiunile, iar headul exact este `0006_stop_reconciliation`. Dacă se introduce revizia nouă, actualizează **împreună** `api/core/db.py`, pinii de schema/release/instance/start din CLI, `ops/build_control_bundle.py`, verifierul fizic al schemei și fixture-urile lor; un release vechi refuză noua revizie. Migrează pe DB atestată **goală și din 0006 cu date vechi păstrate**, fără auto-upgrade la simplul `omnis start` și fără a atinge PGDATA/fixture-urile istorice. Nu presupune că Git revert restaurează DB.

**Două limite reale observate înainte de cod:** `LocalBoundary` din `api/security/host_origin.py` refuză orice query `/api` și taie mutările la **4096 bytes**, în timp ce obiectivul valid poate avea 32768 bytes plus context. Test RED pe endpointul real pentru payloadul valid maxim și lista paginată; lărgește **numai** ruta/forma necesară cu limită explicită, nu dezactiva global Host/Origin/session/CSRF sau plafonul Pairing. `core/errors.py` nu are încă un cod de conflict; păstrează eroarea tipizată și OpenAPI exact când apare 409.

**Probe:** create/read/list cu cookie+CSRF reale, refuz fără sesiune/Host/Origin greșite/CSRF absent, inputuri străine/malformate/oversized și zero IO target/model. PostgreSQL real numai prin `ops/run_test_db_gate.py` și manifestul privat; `test-migrations` empty→0006→noua revizie, inclusiv readback date vechi; targeted API tests pe conexiune nouă. RED→fix minim→GREEN, apoi Ruff/mypy, wheel API/CLI și contract OpenAPI (regenerează, nu edita TS generat manual). Commit mic cu schema+primul consumator și limitele sale.

### P1-B / SL05-B02b — editare, revizii și concurență

**Observabil:** `GET /api/v1/engagements/{id}/revisions` returnează istoric imuabil; `PUT /api/v1/engagements/{id}` cere `If-Match` și command ID, produce exact o nouă revizie pentru un edit admis. Un al doilea tab cu revizie veche primește **409** și nu suprascrie; retry identic nu dublează revizia, payload diferit sub același ID este conflict. Alte engagementuri/ref-uri sau run activ sunt refuzate. Datele mod/obiectiv/scope/buget sunt păstrate byte-for-byte după reload/restart. Fără Writer Settings/Run implicit.

**Implementare:** extinde numai modulul B02a, migrarea doar dacă invariantul demonstrat o cere. Cheile de autoritate, FK-urile și revizia rămân coloane/constrângeri PostgreSQL, nu JSONB liber; datele de draft versionate pot fi payload strict. Respectă tranzacția/ownership sub aceeași barieră locală unde există efecte de lifecycle; nu deschide admiterea dintr-un Save. Teste concurente pe două conexiuni, rollback/readback și 409 HTTP real; review independent pe diff-ul exact, remediu minim și re-review doar al blocantelor.

### P1-C / SL06-B03 — navigație și Dashboard pe date reale

**Observabil:** `/engagements` listează drafturile reale; `/engagements/new` și `/engagements/:id/setup` sunt navigabile după sesiune. Shellul păstrează separarea Home/Engagement/Settings din UI/UX §0/§2 și referința vizuală acceptată; restul taburilor apar `UNAVAILABLE` cu motiv, fără findings/coverage/cost zero inventate. Nu importa fixture-ul/scripturile DEMO în build. Stări loading/empty/error/stale și sesiune expirată sunt distincte.

**Căi:** extinde `web/src/app/App.tsx`, `features/engagements/`, `shared/api/client.ts`/decoders și tipurile **generate** din OpenAPI. Clientul folosește same-origin cookie+CSRF, fără secrete în URL/localStorage; Query cache nu devine ownerul reviziei. Teste de navigație/listă/reload/401/503, keyboard/focus și capturi reale la viewporturile din UI/UX; compară compoziția cu referința, nu doar paleta. Aprobarea vizuală a prototipului nu este un PASS automat pentru această portare.

### P1-D / SL06-B04 — wizard conectat și G01

**Observabil:** wizardul în cinci pași păstrează draftul real prin Save/Next/Back, selecția General/Focalizat și textul exact; refresh/restart rehidratează revizia. 409 păstrează modificările locale și explică reconcilierea, fără auto-overwrite. Profile/catalog lipsă → `CATALOG_UNAVAILABLE/NOT_SELECTED`, **Save posibil, Start blocat**. Identities/seif/Verify login și editorul de catalog sunt indisponibile până la B09h/P4a, nu stuburi cu succes. Preview local nu cheamă modelul/ținta. `GET` are readback după Save, nu succes optimist din cache.

**G01 real:** create→edit→reload→restart pe backend și PostgreSQL proprii; două taburi → 409, Host/Origin/CSRF negative, scope BLOCKED și cross-engagement refuzate. Test componentă + E2E browser pe API real, tastatură/focus/eroare per câmp și layout mobil/desktop; descarcă/verifică bytes dacă apare export, nu doar preview. Contracte OpenAPI→TS fără drift, lint/type/build ale webului și API, review independent scoped după fiecare felie. Absența unei verificări din cauza DNS/CI se raportează `BLOCKED/NOT_RUN`, nu `PASS` dintr-un target vecin.

## Disciplina de execuție și ieșire

Pentru **fiecare** felie: Git HEAD/status/diff → consumator real și un RED + control pozitiv/negativ relevant → fix minim → test țintit → verificări afectate → review independent pe bytes exacți → reproduce/fixează doar blocantele → commit granular cu comandă/exit/limite/rollback și readback. Nu deschide o buclă de harness când două încercări îmbunătățesc numai instrumentarea. Docker/PG serial, fixture nou declarat și readback exact; fără cleanup după prefix, prune global sau atingerea datelor istorice. P1 este gata numai după B02+B03+B04 și G01, nu la primul ecran sau la un număr de teste. CI remote al commitului P0 rămâne **NOT_VERIFIED** până la acces/citire efectivă; nu-l atribui promptului P1 ca PASS.
