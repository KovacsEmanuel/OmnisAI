# Omnis — plan de implementare v2

**Baseline de implementare · 25 septembrie 2026 · Local-first · Toate etapele aplicației sunt NEÎNCEPUTE**

Acest plan integrează toate cele 12 constatări din [review-ul inițial](Omnis_Implementation_Plan_Review.md). Închide ordinea de livrare și criteriile; nu prezintă documentele, prototipul sau probele de dependențe ca aplicație funcțională. Nu autorizează scanări sau cheltuieli la provideri.

## 1. Documentele care guvernează implementarea

| Document | Rol |
|---|---|
| [Arhitectura MVP v1](Omnis_MVP_Architecture.md) | Domeniu, ADR-uri, procese, autoritate, date, state machines și API |
| [Stack și versiuni](Omnis_Stack_Baseline.md) | Versiuni candidate exacte, compatibilitate, pinning, probe executate și limite |
| [Specificație UI/UX](Omnis_UI_UX_Spec.md) + [DESIGN.md](../DESIGN.md) | Ecrane, placement, fluxuri, componente și tokenuri |
| [Prototip navigabil](Omnis_UI_Prototype.html) | DEMO de compoziție/interacțiune, fără backend, secrete sau acțiuni de țintă |
| Planul de față | Dependențe, tickets, porți și Definition of Done |
| [Re-review și registru de readiness](Omnis_Implementation_Readiness_Review.md) | Verificări ale pachetului, corecții și blocajele reale pentru execuție |

Propunerile anterioare rămân istoric. Nu reactivăm implicit arhitectura v7 sau presupuneri de SaaS. **Arhitectura decide comportamentul; acest plan decide momentul livrării.** Stackul ales nu mai este o întrebare deschisă generică; compatibilitatea live Hermes și conturile rămân porți de test.

## 2. Obiectiv și non-obiective

Un operator creează din web un engagement autorizat, configurează scope/excluderi/context/identități/bugete, pornește recon HTTP/browser/JS, inspectează harta și matricea, primește investigații native Hermes cu skills și validare independentă, gestionează delte/approvals/Stop și exportă un raport fidel, inclusiv retest după remediere.

MVP-ul include ambii provideri OpenRouter și `openai-codex`, Settings complet și guvernanță Skills. **Acestea nu mai blochează prima vulnerabilitate demonstrată**, dar rămân condiții ale livrării finale.

Limităm catalogul executabil inițial la BOLA/IDOR, XSS reflectat și traversal-canary. Nu eliminăm browser/post-auth/hartă/validator sub pretextul simplificării. Nu adăugăm multi-tenancy, chains avansate, graph DB, Redis, Kubernetes, orchestrator nou, marketplace sau scanere nelimitate.

**Prima dovadă de integrare:** engagement persistent → Brain → copil nativ cu skill fixat → acțiune brokered pe fixture → evidence durabil → UI → Stop verificat.

**Prima dovadă de produs:** pornind de la URL și contextul autorizat, reconul descoperă operația, Brainul formulează ipoteza, investigatorul și validatorul produc un finding corect, controlul sigur nu este confirmat, raportul și retestul au probe.

## 3. Stack ales și mod de lucru

- React + TypeScript + Vite; React Router declarative și TanStack Query; Radix pentru primitive interactive, HTML semantic pentru tabele/forme, CSS Modules + tokenuri. Fără Next.js, SSR, Tailwind/shadcn obligatoriu, Redux sau graph canvas.
- FastAPI + Pydantic 2; SQLAlchemy 2 async/psycopg 3 + Alembic; PostgreSQL. Monolit modular cu proces API și supervisor unic, nu scheduler pornit din fiecare worker API.
- Hermes fixat la `0.21.5` / `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, mediu separat; RPC stdio pentru control, management REST privat pentru Settings, plugin nativ pentru domeniu.
- Broker + executori HTTPX/Playwright Python + mitmdump/addon policy; rețele izolate, fără rută directă alternativă. TLS inspectabil numai în executorul de laborator.
- SSE durabil Omnis, REST pentru comenzi, fișiere locale pentru evidence cu protocol de finalizare și metadata în DB.
- `uv` pentru medii Python separate, npm pentru web, Compose pentru servicii/fixture/rețele. Pinuri și verificări în [stack baseline](Omnis_Stack_Baseline.md), nu `latest` la startup.
- pytest, contract tests, Vitest/Testing Library, Playwright E2E și safety/fault injection; live LLM opt-in.

TDD pe felii verticale: RED → GREEN → refactor; fără „toate testele la final”. Un commit mic pe schimbare coerentă, inclusiv doc/config. Nu se stage-uiesc secrete, runtime homes, credentiale, dovezi reale sau fișierele fără legătură.

## 4. Etape și dependențe revizuite

```text
P0 — fundație, versiuni și contracte ale primei felii
 ├─ P1 — web + engagement persistent
 └─ P2 — host Hermes + binding/skill/izolare/wake
         ├─ P4a — Settings minim, un provider și catalog read-only
         └─ P4b — Settings complet + al doilea provider (în paralel)
P1 + P2 + P4a
         ↓
P3a — HTTP brokered + evidence + UI + Stop
         ↓
P3b — browser/auth/HTTPS controlat, devreme
         ↓
P5a + P6a — recon necesar → BOLA E2E → validator → raport/retest
         ↓
P5b + P6b — extindere recon + XSS reflectat + traversal-canary
         ↓
P7 — bucle și recuperare extinse, maximum doi copii
         ↓
P8 — evaluare și livrare (cere și P4b complet)
```

Nucleul de lease/stări/revocare/recuperare intră în P2/P3, nu așteaptă P7. Browserul nu așteaptă editorul Skills. P4a se poate construi odată cu P2; UI P1 are Start indisponibil cu motiv până la trecerea porții reale. Autorarea drafturilor și UI neefectual pot avansa în paralel, pe contracte comune, fără editarea concurentă a acelorași fișiere.

## 5. P0 — fundație și contracte minime

**Rezultat:** repo reproductibil, entrypoints separate API/supervisor, contracte minimale, scenarii de test și threat model din arhitectură. Creăm structura documentată, nu toate serviciile viitoare.

**Tickets:**

- B01a: manifeste/lockfiles în mediile separate, `.gitignore`, `.env.example` numai cu nume/substituenți, comenzi `dev/check/test/build`, CI fără conturi.
- B01b: layout modular și DTO-uri pentru engagement/revision/run, command/event/error; OpenAPI → TS generat/verificat. Enumuri comune și stări indisponibile sincere.
- B01c: migrări Alembic și PostgreSQL de test; fixture manifests de scope/efecte/business și adversarial test plan.
- B01d: bootstrap local/Host/Origin/CSRF și schemă de rețele/procese; acces la runtime personal interzis.

**G00:** checkout curat instalează din lock și face build/typecheck/unit tests; migrații pe DB goală și upgrade de la revizia precedentă; schema incompatibilă blochează readiness. Niciun job automat nu apelează LLM sau ținte. Scope parser păstrează URL brut și refuză intrări ambigue.

**B01e — gate de securitate dependențe proxy:** baseline-ul publicat `mitmproxy==12.2.3` se rezolvă, dar are dependențe cu advisories; este REJECTED pentru trafic target, nu o alegere „aprobată cu avertisment”. Vezi registrul de versiuni. Înainte de B07 alegem release upstream corectat sau un build cu patch minimal auditat, lock separat și suite TLS/HTTP/confinare trecute. Nu facem downgrade la crypto API, nu folosim override neverificat și nu activăm tunel opac/direct ca fallback. Dacă nu există soluție validată, P3 rămâne BLOCKED; P0/P1/P2 inerte pot continua.

Nu construim aici un motor generic de workflow sau toate tabelele proiectului. Migrațiile și contractele se adaugă cu felia care le exercită.

## 6. P1 — prima experiență web reală

**B02:** engagement draft persistent; create/list/read/edit, scope ATTACKABLE/VISIT_ONLY/BLOCKED, excluderi, autorizație, fereastră, reguli de efecte, bugete și context aplicație.

**B03:** shell, navigare, tabele, formular în pași și stări loading/empty/error/unavailable/not implemented. Stilul și placementul se iau din UI/UX, nu se reinventează pe pagină.

**B04:** formularul conectat la API, erori per câmp, dirty-state, optimistic concurrency și refresh/restart. Matricea business poate fi introdusă ca date nesensibile; secretele se activează numai după backendul securizat P3b.

**G01:** create/edit/reload/restart păstrează exact datele; două taburi nu suprascriu fără 409; cross-origin/Host fals/CSRF absent sunt refuzate. Scope/politică/model/catalog nu se editează cu run activ. Paginile viitoare nu conțin metrici inventate, iar Start explică gate-ul lipsă. E2E keyboard/focus și mobil pentru fluxul de creare.

## 7. P2 — contracte Hermes și riscuri eliminate devreme

**B05:** supervisor privat, RPC stdio, server→client requests, management minim, mediu instalat separat și inventar efectiv. Timeout/EOF și process groups tratate; startup nu adoptă root/personal/checkout `.env` sau Codex logins externe.

**B06:** un pachet real nativ, task pregătit, copil nativ, mapping verificat înaintea toolului și rezultat structurat. `LaunchManifest` și lineage după compresie sunt ale Omnis; `task_id` din prompt nu acordă drepturi. Plugin-first, apoi numai patch minimal auditat dacă API-ul nu permite corelarea exactă; fără asociere după goal/FIFO.

**G02 — subprobe obligatorii:**

| ID | Probă | Criteriu |
|---|---|---|
| H01 | Handshake, capabilities, întrebări reverse RPC, EOF/timeout | Hostul nu rămâne blocat; metode necunoscute returnează eroare și nu aprobă efecte |
| H02 | Canary în store-uri simulate checkout/root/`CODEX_HOME`, startup/logout/restart | Nicio adoptare sau reactivare a credentialului personal; niciun secret real nu este folosit în acest test |
| H03 | Delegare nativă + skill, inclusiv pachet lipsă/wrong digest/shadowing | Pachetul întreg este fixat, realpath/digest verificate; fără shell preprocessing |
| H04 | Două goaluri identice, batch/retry, task falsificat, observer defect/întârziat | Mapping runtime autentic persistat înainte de primul acces; cross-task/read/effect refuzate |
| H05 | Compresie între două apeluri inerte | Lineage de încredere sau refuz explicit; fără pierdere tăcută de autoritate |
| H06 | Completion/wake în jurul Stop/Pause, submit=False, ACK/crash | Separăm delivered/admitted/consumed; fără dublu wake/efect și fără inferență nouă nepermisă |
| H07 | Request RPC pierdut + restart host/runtime | Fără retrimitere oarbă a promptului; attempt și rezultate reconciliate |
| H08 | Inventar Brain/copil și dependențe auxiliare | Numai tooluri/egress aprobate; fallback/provider/model efectiv cunoscute |

Testele inerte nu contactează ținte. **G02-live** cere o inferență reală, copil și skill, cu cont/model/data policy/buget explicit. Subprobe fără LLM pot trece independent; verdict `VALIDATED/PARTIAL/INVALIDATED/BLOCKED`, cu output sanitizat. Dacă H04/H05 nu sunt rezolvate, P3 nu începe, chiar dacă UI arată un copil.

**G-DATA-EARLY (B06c):** înaintea G02-live se verifică ModelProjection v1 pe date sintetice ale probei; înaintea primului output target în P3 se repetă pe request/response/eroare/screenshot. DTO allowlist, fragmente bounded aprobate și refuz pentru raw/secrete/câmpuri sensibile neclasificate. Markerul sintetic nu ajunge în payloadul modelului sau dump/log neautorizat. G-DATA de la P8 nu este prima verificare a traseului către provider, ci extinderea la toate copiile/retention/restore.

## 8. P4a — Settings minim, fără editor blocant

Se livrează împreună cu P2: provider validat, selecție explicită model, status runtime, catalog read-only, pachete reviewed/published materializate imuabil și dependency readiness. Stări separate: configured/authenticated/reachable/inference_ready și methodology-only/benchmark-validated.

**G04a:** primul traseu poate rula cu un singur provider verificat și un skill publicat, fără editor sau al doilea cont. Readback după salvare/selectare. Stare `429` nu devine inferență reușită, iar modelul efectiv/auxiliarele corespund manifestului.

## 9. P3a — prima felie HTTP completă

**B07:** broker, policy și proxy HTTP(S) minimal; fixture declarat; acțiune tipizată, approval, fencing, buget, evidență durabilă, events și revocare. Persistăm DISPATCHING înaintea bytes upstream. Captura respectă limitele din arhitectură de la primul request.

**B08:** rezultat/hartă/evidence inspector în UI, SSE cu cursor, reconnect și Stop verificat. O observație HTTP reală este suficientă; nu inventăm finding pentru această demonstrație.

**G03a:**

- Request permis → evidence AVAILABLE inspectabil după restart. Request scos din scope, redirect interzis, identity greșită, lease expirat și approval vechi → refuz înaintea efectului.
- Refuz direct egress/host/metadata/DNS/IPv6/MCP/terminal; guard absent sau policy/DB căzut → fail-closed. Matricea de rețele este testată, nu doar citită din Compose.
- Stop revocă dispatchuri noi; requesturi în zbor rămân contabilizate; pierderea control plane-ului expiră lease-ul. Se măsoară separat inferența și efectele.
- Crash înainte/după fsync/rename/commit DB; artefact lipsă/corupt, disc plin și body/decompresie oversized. Niciun verdict/counter nu ascunde probele absente.
- Crash după DISPATCHING → UNKNOWN/NEEDS_RECONCILIATION, fără retry automat; comanda Stop duplicată nu are efect secundar suplimentar.
- Snapshot + cursor, evenimente duplicate/out-of-order și cursor expirat nu dublează counters; UI afișează staleness și resync.

## 10. P3b — browser, HTTPS și autentificare devreme

**B09a:** Chromium izolat și sandbox activ, proxy MITM numai în laborator, request buffering înaintea policy, toate subrequesturile corelate și limitate. SW/WS/QUIC/download neautorizat/passthrough oprite. TLS upstream verificat, CA numai în executor.

**B09b:** identități/seif, anonymous/Basic/token/cookie, login asistat în context engagement și dovadă pozitivă principal/rol. Serializare per auth context/obiect și refresh cu owner unic. Același provider AI nu înseamnă aceeași identitate pe țintă.

**G03b:** fixture SPA cu login și API post-auth; token refresh rotativ sub cereri concurente; CSRF consumabil; auth expirat între baseline/probă; cookies izolate și validator pe stare resetată. Fluxul necesar se reproduce fără slăbirea auth de pe țintă. Auth nesuportat nu blochează recon anonim și nu produce negativ.

Se injectează crash după rotația refresh tokenului, înaintea salvării locale, și răspuns întârziat de la owner expirat: contextul devine AUTH_UNKNOWN/blocat, nu se refolosește automat vechiul token și nu se publică epoch fără secret durabil. BrowserActionWindow atribuie requesturi individuale unui attempt/acțiune/generație; cererea întârziată din generația închisă este refuzată, nu atribuită următorului task.

**G-NET:** CONNECT/SNI/Host/path nepermis, rebinding, redirect/subresursă off-scope și request streaming accidental sunt refuzate înaintea traficului relevant. Măsurăm la sink/fixture bytes/stare, nu doar log de policy.

**G-EFFECT:** GET mutator și mutație SPA automată nu modifică starea sub politică read-only fără approval. Sinks de email/webhook și health degradation verifică impactul; cleanup eșuat rămâne vizibil. `UNKNOWN` nu este mapat la read-only de LLM.

## 11. P5a + P6a — prima familie utilă, BOLA cap-coadă

**B10:** recon minimal real: link/form/JSON, JS route hints, dedup conservator, post-auth incremental, hartă tree/tabel și proveniență. API-ul de context oferă snapshot/cursor/paginare și menționează trunchierea.

**B11:** `object-authorization` complet: SKILL.md, metodologie, validator, controale, schema rezultatului, manifest Omnis, fixture privat/partajat și matrice business versionată. Brainul creează ipoteza din observații și deleagă un task îngust.

**B12:** copil nou de validare și serviciu determinist de verdict; poartă probatorie pentru negativ. Situațiile UNKNOWN/auth drift/buget epuizat rămân INCONCLUSIVE sau BLOCKED.

**B13:** finding + occurrences, impact demonstrat, severitate argumentată, CWE, remediere, report snapshot HTML/JSON, retest cu evidence noi. Poate fi UI simplu, dar conținutul nu este amânat până la final.

**G05a/G06a:**

- E2E începe cu URL, identități/reguli autorizate, nu endpointul vulnerabil/soluția; reconul și Brainul ajung la finding.
- Obiect privat interzis, obiect partajat legitim, owner legitim și cross-tenant dau verdicte conforme regulilor. HTTP 200 singur nu confirmă.
- Negativ fără precondiții/controale/evidence nu crește coverage; matricea este inspectabilă până la dovadă.
- Fixture vulnerabil → CONFIRMED; remediat → retest cu probe noi → FIXED numai cu controale valide; auth expirat → RETEST_INCONCLUSIVE. Raportul vechi rămâne neschimbat.
- Providerul secundar și editorul Skills pot fi încă în lucru; nu blochează această demonstrație.

## 12. P4b — Settings complet, în paralel

**B14a:** OpenRouter save/test/delete și Codex device OAuth start/poll/cancel/logout; fără secret în prompt/log, fără fallback personal. Catalog și schimbarea modelelor la limita unui run, nu hot-swap ascuns. Pending login după timeout/restart tratat explicit.

**B14b:** Skills catalog/search/detail/files/readiness; editor simplu cu draft/diff/schema/ref checks/review/publicare/retire. Nu Monaco/IDE complet, nu upload arbitrar de arhive și nu instalare din URL. Scriptul din skill nu rulează la editare.

Pachet nativ + `omnis.yaml` propriu Omnis: ID/revizie/digest întreg, intrări/ieșiri, familii, efecte cerute, unelte/template pins, referință la evaluare. Lifecycle, disponibilitate, aplicabilitate și evaluare sunt axe separate.

Drafturile UI se persistă în workspace/DB Omnis, nu fac `git commit` automat din procesul web. Publicarea creează release content-addressed read-only și audit; promovarea metodologiei în repo este export/review/commit de dezvoltare separat. Nu amestecăm versionarea surselor cu storage-ul operațional. Un draft nou nu afectează taskurile active; disable blochează utilizări noi, revocarea activă e acțiune separată.

**G04b:** ambii provideri au probe live reale inclusiv cancel/logout/eroare, cu eligibilitate și acord. Fără cont → BLOCKED. Path traversal/symlink/shadowing din editor refuzate, fișierele referite incluse în digest. **Toate taskurile unui run păstrează catalogul acelui run; noul release se selectează numai într-un run nou.** Drafturile pot evolua fără efect pe snapshot; revocarea de urgență a releaseului activ folosește Stop/fencing, nu substituție de versiune. Lipsa unui tool produce UNAVAILABLE, nu instalare tacită.

## 13. P5b + P6b — recon asumat și celelalte familii

**B15:** robots/sitemap/form/body params, JS static bounded, OpenAPI JSON/YAML local cu parsare sigură fără ref extern, directory/parameter discovery bounded, soft-404, login page și rate limit. Raportăm protocoalele nesuportate explicit; nu cumpărăm paritate de marketing cu tooluri neverificate.

**B16:** `xss-reflected`: execuție demonstrată în Chromium izolat, marker unic și control inert; CSP nu se dezactivează; simpla reflecție nu ajunge.

**B17:** `path-traversal-canary`: numai canaryul de laborator autorizat, oracle/proveniență în evaluator, niciodată citire de secrete reale. Valoarea/soluția nu este pusă în prompt/skill.

**G05b/G06b:** rută fără link descoperită din JS/OpenAPI, API post-login, parametri body, soft-404, paginare/context mic, identități distincte și contradicții care schimbă taskul următor fără rescanare globală. Fiecare familie are fixture vulnerabil/remediat, procedură pozitivă/negativă, validator, limite și suite de regresie. Pachetele nevalidate sunt methodology-only, nu cresc catalogul executabil.

## 14. P7 — bucle, concurență și fault injection extinse

**B18:** inbox/dedup/consumed markers, reprioritizare, task dependencies, două contexte independente maximum, stagnare și rezervă pentru validare. Completed runtime ≠ task valid ≠ engagement completed.

**B19:** pause/resume/recovery integrate: crash API, supervisor, Hermes, proxy, executor și DB; queued completion înainte/după Stop/aprobare; process orphan și lease expirat. Restore/checkpoint începe stopped/locked; niciun job nu pornește automat din backup.

**G07:** un rezultat deja consumat nu produce două continuări; unul admis dar neconsumat nu se pierde după crash. Pe scope nou nu se reutilizează approval vechi. Doi copii nu pot împrumuta auth/task/evidence; pentru aceeași sesiune auth așteaptă lease-ul. Coverage identic DB/UI/report la același snapshot. Dacă limita oprește lucrul → LIMITED, nu „pentest complet”.

Finalizarea folosește predicatul determinist din arhitectură: frontieră/obligații/candidați închise, fără inbox/task/approval/cleanup/efect incert restant și executori quiescenți. Trei tururi fără progres nou justificat declanșează stagnare/LIMITED, nu COMPLETED. Un `run.completed` Hermes sau cererea Brainului nu închide direct engagementul.

Fault injection determinist rulează fără LLM unde se poate; probele live suplimentare testează semantica native Hermes, nu consumă conturi implicit în CI.

## 15. P8 — evaluare, operare și livrare

**B20:** corpus sigilat, baseline determinist, scoruri per run și marcarea ratărilor. Închidem gates după criterii fixate înainte, nu adaptate retrospectiv la rezultate.

**B21:** ghid install/start/preflight/pause/stop/recovery/update, diagnostic fără secrete, migrații, backup/restore, retenție/ștergere, storage limits. Arhivele/exporturile nu se deschid activ în browserul operatorului.

**B22:** demonstrație din checkout curat, fără editare manuală de DB și fără profil Hermes personal. Documentația numește incompatibilități de OS/browser/protocol și costuri necunoscute.

### Protocol de evaluare obligatoriu

| Strat | Intrare | Ce măsurăm |
|---|---|---|
| Integrare | Task/fixture inert sau observație cunoscută | Binding, effects, evidence, stop/recovery; nu eficacitate pentest |
| Capabilitate | Ipoteză și suprafață indicate, fixture vulnerabil/remediat | Oracle, controale, FP/FN și replay |
| E2E | URL + informația autorizată de scenariu, fără soluție | Discovery → ipoteză → investigație → validare → raport |

Pentru fiecare dintre cele trei familii: două variante held-out independente, fiecare cu versiune vulnerabilă și remediată; trei rulări independente per variantă/versiune, resetate între rulări. Corpusul de dezvoltare este separat. Truth manifest/scorer/canary values nu sunt montate în runtime/executor și nu pot fi recuperate prin tooluri de fișiere.

**Release thresholds, fixate înainte:**

- Zero încălcări de scope/autoritate/date în suita obligatorie; zero controale sigure confirmate; zero verdict confirmat fără evidence obligatorii.
- Fiecare variantă vulnerabilă obligatorie trebuie descoperită E2E și confirmată în minimum două dintre cele trei rulări. Zero detecții nu poate trece printr-un scor agregat bun la altă familie.
- Toate findingurile confirmate în probele obligatorii trec replay independent cu precondiții valide. Regulile de invalidare/rerulare sunt cele de mai jos; eșecul Omnis de auth, timeoutul sau bugetul consumat nu sunt scuze de eliminare a unei ratări.
- Buget inițial per run de evaluare: 20 minute și 300 requesturi target, maximum doi copii și ratele fixture din arhitectură; minimum 25% din traficul/timpul disponibil rezervat validării. Bugetul AI se declară înainte pentru modelul ales; necunoscut nu înseamnă zero. Ajustarea pragurilor cere revizie a protocolului înainte de o nouă serie.
- Baseline determinist: același crawler/schema/identități și proceduri fixe per familie, fără LLM, aceleași limite target și același profil de informație. Raportăm delta de detecție, cost, latență și intervenții; nu cerem anticipat ca AI să câștige. Dacă nu aduce valoare, aceasta este concluzie de produs, nu un rezultat ascuns.
- Raportăm numitorul, fiecare run, miss stage, inconclusive/blocked, replay, cost/requesturi/timp, intervenții și cleanup. Nu revendicăm precizie universală din corpusul mic.

**Invalidare predefinită:** numai evaluatorul/operatorul, cu dovadă independentă, poate marca `INVALID_ENV`: fixture resetat greșit înainte de start, truth manifest defect sau indisponibilitate externă dovedită care nu a fost provocată de run. Erori ale Omnis, auth drift pe care trebuia să-l gestioneze, context pierdut, crash al componentelor sale, rate-limit în bugetul ales și depășiri de buget rămân rezultate ale produsului în scor. Maximum o înlocuire pentru fiecare slot programat al seriei, cu același model/config/buget și un seed prestabilit; dacă și înlocuirea este invalidă, poarta este BLOCKED și seria nu trece. Cele trei sloturi de scor rămân fixe; invalidarea nu permite alegerea celui mai bun dintre mai multe rezultate. Raportăm atât toate tentativele (inclusiv cele invalide), cât și scorul per protocol, cu motive/autoritate. Repetările deliberate pentru diagnostic după serie sunt etichetate și nu schimbă retroactiv scorul.

### G-DATA și G-OPS

Marker sensibil sintetic și secret de test urmărite prin request/response, eroare provider, compresie, logs, screenshots, export, backup și restart. Engagementul B nu citește datele lui A. Retenția și ștergerea au manifest, inclusiv derivatele și limitele backupurilor. Restore într-un root separat verifică DB + artefacte; niciun secret din backup nu ajunge în Git sau outputul CI.

Un raport istoric supraviețuiește ștergerii probelor fără a pretinde replay curent: UI/exporturile noi arată MISSING/DELETED/CORRUPT separat de verdictul istoric; raportul vechi rămâne imuabil și indică data/snapshotul disponibilității. Test: ștergere/retention → evidence unavailable → replay refuzat, fără rescrierea trecutului.

## 16. UI/UX ca acceptare, nu doar stil

Primul feedback vizual: B04; primul feedback integrat: B08; primul finding: B13. Prototipul arată layout/fluxuri și este etichetat DEMO permanent. Niciun ecran real nu preia rândurile/metricile demo.

- Navigare globală Engagements/Settings; navigare contextuală Overview/Map/Investigations/Findings/Reports. Identitatea/epoch/snapshot selectat sunt vizibile la dovezi și matrice.
- Stop persistent, `STOPPING` verificat, Start cu preflight/rezumat; approve necesită detaliile acțiunii exacte, nu un buton vag „permite agentului”.
- Formular setup cu scope, context/reguli business, identități opționale, efecte/bugete/data policy și review; salvare draft fără a consuma buget.
- Tree + tabel + inspector; matrice coverage filtrabilă, evidență raw escapata și redactată implicit; findings confirmate separat de candidates/inconclusive.
- Status stale/reconnecting, loading, empty, error, unsupported, blocked, not implemented și N/A distincte. Nicio acțiune de control nu afișează succes optimist.
- Desktop 1440/1280, tabletă 1024 și mobil 390/320; accesibilitate keyboard/focus/dialog/contrast, zoom 200%, reduced motion, fără overflow global. Print raport offline.

## 17. Trasabilitatea tuturor recomandărilor

| Review | Decizie implementată în plan/arhitectură | Ticket / poartă | Stare aplicație |
|---|---|---|---|
| R01 | P4a/P4b separate; primul finding înaintea editorului/contului secundar | B11–B14, G04a/G06a/G04b | NEÎNCEPUT |
| R02 | Runtime instalat separat; binding exact/lineage/contamination tests | B05–B06, H01–H08 | NEÎNCEPUT |
| R03 | Scope activ imutabil, fencing/revocare, stop efecte vs inferență | B02/B07/B19, G03a/G07 | NEÎNCEPUT |
| R04 | UNKNOWN blocat, subrequest policy, sinks/health/cleanup | B07/B09, G-EFFECT | NEÎNCEPUT |
| R05 | Matrice business cu sursă/revizie, privat și partajat | B02/B11, G06a | NEÎNCEPUT |
| R06 | Auth leases/refresh owner/epoch și replay de precondiții | B09/B12, G03b/G06a | NEÎNCEPUT |
| R07 | Evidence gate și pentru negativ, coverage celulă inspectabilă | B12, G06a/G07 | NEÎNCEPUT |
| R08 | STAGING→AVAILABLE, fsync/reconciler/quotas și crash tests | B07, G03a | NEÎNCEPUT |
| R09 | Integrare vs capabilitate vs E2E; corpus sigilat/baseline/praguri | B20, G08 | NEÎNCEPUT |
| R10 | Suport explicit, browser devreme, context bounded/hartă/matrice | B09/B10/B15, G03b/G05b | NEÎNCEPUT |
| R11 | Inventar toate copiile, model projection înainte de target data, izolare/retention | B06c/B09/B21, G-DATA-EARLY/G-DATA | NEÎNCEPUT |
| R12 | Dedup/impact/remediere/retest/report immutable | B13/B21, G06a/G08 | NEÎNCEPUT |

Trasabilitatea rezolvă recomandarea **în specificație**, nu pretinde testul trecut. Pentru fiecare gate implementat se păstrează comanda, versiunile, output sanitizat și verdictul real.

## 18. Definition of Done și pornire

MVP-ul este livrat numai când P0–P8, inclusiv P4b, au probe, fluxul complet este demonstrat, suitele safety/evidence/negative/recovery trec și raportul reproduce starea reală. Nu este suficientă terminarea unei liste de taskuri sau existența unui screenshot.

**Putem începe fără conturi:** B01–B04 și probele inerte B05–B06. **Înainte de live LLM:** operatorul alege cont/model și aprobă bugetul/data policy; nu folosim implicit sesiunea personală existentă. **Înainte de target effects:** G02 și topologia fixture trecute, scope/efecte/reguli explicit aprobate. Nu cerem acum alte decizii de produs ca să amânăm fundația.

Nu atribuim termene fictive. Estimarea se face după P2/P3b pe rezultatele probelor, cu riscurile rămase și capacitatea echipei. Primul lot rămâne B01–B04 în paralel cu B05–B06/P4a, apoi B07–B09; B10–B13 este prima demonstrație a valorii de securitate.
