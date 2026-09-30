# Omnis — plan de implementare v2

**Baseline de implementare · Local-first · P0.3_IMPLEMENTED_LOCAL · P0.4 în curs: CLI status, bundle/imagine și topologie DB/API/supervisor instalată probată numai în harness; launcher neimplementat · CI remote NOT-RUN · G00 deschis**

Acest plan integrează constatări R01–R12 și amendamentele autorizate HF01–HF10, păstrate în §17. Review-urile Sol/OSS și suplimentul modular sunt surse/rațiuni istorice; recomandările înlocuite sunt adjudecate în §17, nu un plan concurent. Review-ul inițial este disponibil în istoricul Git la `b12e179`, nu ca document concurent în directorul curent. Planul închide ordinea de livrare și criteriile; nu prezintă documentele, prototipul sau probele de dependențe ca aplicație funcțională. Nu autorizează scanări sau cheltuieli la provideri.

## 1. Documentele care guvernează implementarea

| Document | Rol |
|---|---|
| [Arhitectura MVP v1](Omnis_MVP_Architecture.md) | Domeniu, ADR-uri, procese, autoritate, date, state machines și API |
| [Stack și versiuni](Omnis_Stack_Baseline.md) | Versiuni candidate exacte, compatibilitate, pinning, probe executate și limite |
| [Specificație UI/UX](Omnis_UI_UX_Spec.md) + [DESIGN.md](../DESIGN.md) | Ecrane, placement, fluxuri, componente și tokenuri |
| [Prototip navigabil](Omnis_UI_Prototype.html) | DEMO de compoziție/interacțiune, fără backend, secrete sau acțiuni de țintă |
| Planul de față | Dependențe, tickets, porți și Definition of Done |
| [Re-review și registru de readiness](Omnis_Implementation_Readiness_Review.md) | Verificări ale pachetului, corecții și blocajele reale pentru execuție |

Directorul curent conține numai baseline-ul și suportul necesar lui; propunerile anterioare rămân în istoricul Git. Nu reactivăm implicit arhitectura v7 sau presupuneri de SaaS. **Arhitectura decide comportamentul; acest plan decide momentul livrării.** Stackul ales nu mai este o întrebare deschisă generică; compatibilitatea live Hermes și conturile rămân porți de test.

## 2. Obiectiv și non-obiective

Un operator creează din web un engagement autorizat, configurează scope/excluderi/context/identități/bugete, pornește recon HTTP/browser/JS, inspectează harta și matricea, primește investigații native Hermes cu skills și validare independentă, gestionează delte/approvals/Stop și exportă un raport fidel, inclusiv retest după remediere.

MVP-ul include ambii provideri OpenRouter și `openai-codex`, Settings complet și guvernanță Skills. **Acestea nu mai blochează prima vulnerabilitate demonstrată**, dar rămân condiții ale livrării finale.

Prima probă rămâne BOLA/IDOR; nucleul executabil MVP adaugă XSS reflectat și traversal-canary **într-o campanie adaptivă**, G-LOOP/G-FOCUS/G-PATH și Jev integrat/evaluat. Nu eliminăm browser/post-auth/hartă/validator; HTTP-auth permite prima BOLA API-only fără a aștepta Chromium. Catalogul knowledge poate fi larg fără execuție certificată. Trei familii sau E1 nu sunt paritate Strix; extensiile sunt §15. Nu adăugăm multi-tenancy, chains nelimitate, graph DB, Redis, Kubernetes, orchestrator nou, marketplace sau scanere fără limite.

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

**G-DESIGN — VISUAL_ACCEPTED / P0.1–P0.4 autorizate:** utilizatorul a acceptat prototipul `df17a29` și a confirmat structura `api/`, `web/`, `cli/` și contractul `omnis` din arhitectură §4/§12. `api/`, bootstrapul `web/` și primul increment `cli/` au fost introduse incremental; launcherul complet rămâne neimplementat. Nu redeschidem designul fără motiv/cerere. Această poartă nu înlocuiește G00–G08, acordul de cont/model/buget sau autorizarea țintelor.

### Ordine verificabilă

Tabelul definește dependențele de **închidere**; citirile și probele disposable fără efecte pot preceda etapa, fără a o marca trecută. P0-control include bootstrapul web real necesar launcherului, nu formularul/experiența completă P1 și nu runtime-host P2. P1-data (B02) oferă persistența reală de care bindingul P2 are nevoie; P1-web și P2-inert pot continua apoi în paralel.

| Etapă | Dependențe | Livrare / condiție de ieșire |
|---|---|---|
| P0-control | — | Medii/build, DB/migrări, pairing/control, supervisor inert, launcher și bootstrap web real; G00, fără runtime/proxy/conturi |
| P1-data | P0-control | B02: draft/revizie persistentă și API, cu ownership/concurență |
| P1-web | P1-data | B03/B04: UI acceptat conectat la datele reale, G01 |
| P2-inert | P0-control, P1-data | B05/B06 și partea inertă H01–H08; fără adoptare credentiale sau rețea provider |
| P4a-minim | P2-inert | Configurare/readback/control provider și catalog, înainte de prima probă de inferență |
| P2-live | P2-inert, P4a-minim | B06m/G-MODEL + G-DATA-EARLY + acord cont/model/buget, apoi G02-live/G04a; fără target effects |
| B01e-build | — | Build proxy remediat/admis numai pentru testele izolate; nu ASSESSMENT_READY |
| P3a | P1-web, P2-live, B01e-build | B07 determinist mai întâi, B01e-integrated/G-NET HTTP, apoi tracerul nativ B08 și G03a |
| P3-auth | P3a | B09h/G-AUTH-HTTP: identități HTTP, seif, principal/epoch/refresh/replay; fără Chromium obligatoriu |
| P3b | P3-auth | Browser/SPA/auth asistat, extensia certificării și G03b/G-EFFECT; rămâne MVP obligatoriu |
| P5a+P6a | P3-auth | Discovery → BOLA → validator → review/raport/retest, G05a/G06a; prima probă API-only |
| P-LOOP | P5a+P6a | B18a/G-LOOP: clue→replan→recon/task nou, fără dublu consum |
| P-FOCUS | P5a+P6a | B10f/B12f/B13f/G-FOCUS: ambele moduri cu traces și raport distinct |
| P5b+P6b | P5a+P6a, P3b | Recon extins + XSS reflectat + traversal-canary, G05b/G06b |
| P-PATH | P-LOOP, P5b+P6b | B18c/G-PATH: două findings și tranziție probate, fără count dublu |
| P-JEV | P-LOOP, P4a-minim | B06j/B14j/G-JEV: shadow live și evaluare paired; dezvoltarea inertă începe din P2 |
| P4b | P4a-minim | Settings complet și ambii provideri verificați; poate avansa paralel |
| P7 | P-PATH, P-FOCUS, P-JEV | Recuperare/bucle/concurență extinse B18b/B19, G07 |
| P8 | P7, P4b | Evaluare și release; G08/G-DATA/G-OPS |

Nucleul de lease/stări/revocare/recuperare intră în P0-control/P2/P3, nu așteaptă P7. Browserul nu așteaptă editorul Skills. UI/config P4a se pot pregăti odată cu contractele P2, dar **P2-inert → P4a-minim → P2-live** închide dependența reală; nu cerem inferență înainte să existe configurarea sigură a contului. UI P1 are Start indisponibil cu motiv până la trecerea porții reale. Autorarea drafturilor și UI neefectual pot avansa în paralel, pe contracte comune, fără editarea concurentă a acelorași fișiere.

## 5. P0 — fundație și contracte minime

**Rezultat P0-control:** repo reproductibil și primul control plane real: PostgreSQL, API, supervisor inert, pairing/control local, launcher instalabil și build web minim cu starea efectivă. Bootstrapul reutilizează shellul/tokenurile acceptate și arată UNAVAILABLE/NOT_RUN; nu conține engagementuri sau findings fictive. Runtime-host, proxy și executori nu sunt cerințe de boot P0 și nu sunt porniți ca mockuri „healthy”. P1 adaugă experiența completă de engagement, P2 adaptorul Hermes. Creăm numai fișierele feliei executate; §19 definește primul increment, nu întregul P0 într-un singur commit.

**Tickets:**

- B01a: directoarele root `api/`, `web/`, `cli/` conform arhitecturii §12, create pe rând cu fișierele feliei; manifeste/lockfiles separate, `.gitignore`/build-context allowlist, `.env.example` numai substituenți, comenzi reale și CI fără conturi. Buildurile nu includ `.hermes/`, `.env`, documentele/fixture-urile DEMO sau runtime personal. Mediile Hermes/proxy/executori nu se amestecă cu API/CLI.
- B01b: numai DTO-urile primei felii plus envelope/revision/command/error comune; `ProjectionEnvelope` urmează arhitectură §9.1. `contracts/omnis.openapi.json` → `web/src/shared/api/generated.ts`, drift verificat când există consumatorul. Probe de import țin domainul independent de FastAPI/ORM/Hermes. Nu expunem toate endpointurile viitoare ca stuburi sănătoase.
- B01c: migrări Alembic și PostgreSQL de test; fixture manifests de scope/efecte/business și adversarial test plan.
- B01d: bootstrap local/Host/Origin/CSRF și schemă de rețele/procese; acces la runtime personal interzis.
- B01f: launcherul instalabil `cli/` pentru `omnis`, startup P0-control inert/idempotent, lock/identity, migrare dedicată, readiness și bootstrap web/pairing real same-origin; status/headless/erori fără secrete. Wheelul, buildul web și manifestul minim sunt produse/testate aici, nu presupuse existente până la B21. Contract arhitectură §4.1–4.5. L01–L04 și partea pairing/control L05 se probează fără conturi; partea SSE a L05 aparține B08. Componentele absente raportează UNAVAILABLE.

B01f include `InstanceControl`: barieră durabilă de shutdown și generație. G00 probează tranzacția reală de admitere concurentă cu shutdown și crash/restart pe PostgreSQL, cu o comandă de lucru strict inertă în harness și controale allow/deny; nu declară Start runtime funcțional înainte de B05/B07. Integrarea fiecărui producer real (Start/Resume/Settings/raport) cu aceeași barieră completează L08 în faza lui. Nucleul nu este amânat până la release. Supervisorul comandă adaptoarele/process groups, numai launcherul controlează containerele. Crash/restart nu redeschide automat admiterea.

**G00:** checkout curat instalează din lock și face build/typecheck/unit/integration pentru componentele introduse; DB reală, schema goală și migrare/upgrade conform reviziilor existente, schema incompatibilă blochează readiness. L01–L05-control/L08-core se închid numai pe artifactul/procesele reale; L05-SSE și runtime/execuție rămân NEÎNCEPUTE. Dashboard ready cere bootstrap real, assessment_ready=false. Boot/health/status nu fac nici inferență, nici validate/discovery/pricing/OAuth refresh către provider; zero trafic target. Lipsa Docker/DB/pinului este BLOCKED, nu fallback SQLite/mock sau skip raportat PASS. Scope parser păstrează URL brut și refuză intrări ambigue.

**B01e — gate de securitate dependențe proxy:** baseline-ul publicat `mitmproxy==12.2.3` se rezolvă, dar are dependențe cu advisories; este REJECTED pentru trafic target, nu o alegere „aprobată cu avertisment”. Vezi registrul de versiuni. **B01e-build**, înainte de a executa proxyul în testele B07, alege release upstream corectat sau patch minimal auditat, lock separat și probe upstream/TLS/HTTP de build. Rezultatul este LAB_TEST_ONLY. **B01e-integrated** se închide în B07/B09 odată cu contractele broker/addon și G-NET pentru transportul respectiv; împreună închid G-DEPENDENCIES, nu invers. Nu facem downgrade la crypto API, nu folosim override neverificat și nu activăm tunel opac/direct ca fallback. Dacă nu există build admis, execuția proxyului/efectele P3 rămân BLOCKED; P0/P1/P2 inerte pot continua. Testele izolate necesare certificării rulează numai într-un harness cu fixture/sinks explicit autorizate și egress extern închis; nu sunt assessmenturi sau o excepție ascunsă în Start. Mai întâi trec controalele deterministe allow/deny și absent-addon, apoi tracerul nativ. Buildul publicat respins nu primește derogare nici prin acest traseu.

Nu construim aici un motor generic de workflow sau toate tabelele proiectului. Migrațiile și contractele se adaugă cu felia care le exercită.

## 6. P1 — prima experiență web reală

**B02:** engagement draft persistent; create/list/read/edit, scope ATTACKABLE/VISIT_ONLY/BLOCKED, excluderi, autorizație, fereastră, reguli de efecte, bugete și context aplicație. Include `assessment_mode`, `objective_text`, `objective_constraints` și workflow_profile_ref nullable în draft conform arhitectură §9.3; profilul publicat devine obligatoriu numai la Start după B06/P4a-minim, cu selecție/revizie explicită; migrare în agregatul existent, fără chat DB. B04 conectează selectorul/textarea și readbackul exact. Salvarea/sintaxa sunt inerte, interpretarea Brain este la B06 după Start.

**B03:** portarea shellului și componentelor acceptate, navigare pe trei scope-uri, tabele, formular în pași și stări loading/empty/error/unavailable/not implemented. Home și cele cinci taburi de engagement urmează UI/UX/§16; metricile și acțiunile fără sursă reală sunt indisponibile, nu umplute cu fixture. Tokenurile și fonturile locale Geist/Geist Mono păstrează proveniența/licența; nu importăm modelul/scripturile DEMO în buildul produsului.

**B04:** formularul conectat la API, erori per câmp, dirty-state, optimistic concurrency și refresh/restart. Matricea business poate fi introdusă ca date nesensibile; formularul securizat de credențiale HTTP se activează cu B09h/G-AUTH-HTTP (P3-auth), înainte de prima BOLA API-only; numai assisted browser login așteaptă P3b. Până atunci câmpurile secret sunt indisponibile, nu mutate în prompt.

**G01:** create/edit/reload/restart păstrează exact datele; două taburi nu suprascriu fără 409; cross-origin/Host fals/CSRF absent sunt refuzate. Scope/politică/model/catalog nu se editează cu run activ. Paginile viitoare nu conțin metrici inventate, iar Start explică gate-ul lipsă. E2E keyboard/focus și mobil pentru fluxul de creare.

## 7. P2 — contracte Hermes și riscuri eliminate devreme

**B05:** supervisor privat, RPC stdio, server→client requests, management minim, mediu instalat separat și inventar efectiv. Timeout/EOF și process groups tratate; startup nu adoptă root/personal/checkout `.env` sau Codex logins externe.

B05 include adaptorul fix `runtime-host`, părinte al Hermes în containerul runtime, și IPC Unix privat către supervisor. Este cod Omnis de lifecycle/transport, nu scheduler alternativ sau endpoint Hermes inventat. Watchdog/lease oprește inclusiv inferența la pierderea controlului; exclusivitatea management/execuție și metodele allowlisted se probează pe pin. L06/L08 completează H01–H08; fără Docker socket în componente. Fără acord G-DESIGN, nu creăm adaptorul.

**B06:** un pachet real nativ, task pregătit, copil nativ, mapping verificat înaintea toolului și rezultat structurat. Livrează contractele minime SkillPackageRevision/TechniqueRevision/ProcedureRevision, PromptBundleRevision/TaskBriefV1/TaskResultV1 din arhitectură §9.4–9.5 și consumul lor real; inbox/ACK/consumed sunt aici, nu amânate la B18. Composerul adaptează S01/S03/S05/S10 din manifestul de reuse, cu golden/negative tests și context îngust, nu întreg istoricul. Importul minim include provenance/notices și BOLA/recon/counterevidence; biblioteca largă se importă în loturi fără activare automată. `LaunchManifest` și lineage după compresie sunt ale Omnis; `task_id` din prompt nu acordă drepturi. Plugin-first, apoi numai patch minimal auditat dacă API-ul nu permite corelarea exactă; fără asociere după goal/FIFO.

**B06a/B06b — bootstrap catalog și contracte, fără editor:** B06a compilează/îngheață CandidateSnapshot și closure completă, rezolvă LOCAL/RELEASE/case slots/StepOutputRef și evaluează seed-ul STATIC/PURE fără target/provider. B06b publică exact seed-ul calificat și leagă root/copil/TaskBrief/TaskResult, inbox și receipts; P4a îl selectează read-only. RunSnapshot.execution_purpose distinge CONTRACT_PROBE/PACKAGE_EVAL de ASSESSMENT, conform arhitectură §9.8. Candidatul nepublicat este accesibil numai evaluării admise, nu unui assessment normal. B11/B12 adaugă primul FIXTURE_PASS pentru BOLA; B14b expune ulterior același mecanism în UI. Nu așteptăm B07/validatorul de vulnerabilitate pentru o probă PURE și nu pretindem că PURE_PASS certifică BOLA.

**B06m / G-MODEL** — nucleu comun înainte de P2-live/G04a, conform arhitectură §5.2: `policy/admission.py`, `policy/budgets.py`, ModelDispatch/reservations/receipts și seam trusted pre-call din adaptorul Hermes. P2-inert probează ledger/refuz/Stop pe transport sintetic; P2-live probează callul real la pin cu acord. Caps calls/output/deadline și rezerva VALIDATION sunt efective, nu numai în prompt; retry/fallback/auxiliare fie sunt readmise și contabilizate, fie interzise. Lost response păstrează UNKNOWN, nu rambursare fictivă. Lipsa seam-ului pre-send blochează live; nu așteptăm B07 și nu inventăm un al doilea contabil. B07 extinde același ledger la trafic/effects. Nimic din B06m nu se implementează în P0.

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
| H08 | Inventar Brain/copil și dependențe auxiliare | Numai tooluri/egress aprobate; fallback/provider/model efectiv cunoscute; G-MODEL refuză calluri fără rezervă înainte de send |

Testele inerte nu contactează ținte. **G02-live** cere o inferență reală, copil și skill, cu cont/model/data policy/buget explicit. Subprobe fără LLM pot trece independent; verdict `VALIDATED/PARTIAL/INVALIDATED/BLOCKED`, cu output sanitizat. Dacă H04/H05 nu sunt rezolvate, P3 nu începe, chiar dacă UI arată un copil.

**G-DATA-EARLY (B06c):** înaintea G02-live se verifică ModelProjection v1 pe date sintetice ale probei; înaintea primului output target în P3 se repetă pe request/response/eroare/screenshot. DTO allowlist, fragmente bounded aprobate și refuz pentru raw/secrete/câmpuri sensibile neclasificate. Markerul sintetic nu ajunge în payloadul modelului sau dump/log neautorizat. G-DATA de la P8 nu este prima verificare a traseului către provider, ci extinderea la toate copiile/retention/restore.

## 8. P4a — Settings minim, fără editor blocant

P4a-minim urmează P2-inert pentru controlul sigur al Settings, apoi permite închiderea P2-live/G04a cu acord. Include selecție explicită model, status runtime, catalog read-only, pachete reviewed/published imuabile și dependency readiness. Configurarea/readbackul nu sunt inferență; fără cont/buget aprobate, partea live rămâne BLOCKED. Stări separate: configured/authenticated/reachable/inference_ready și methodology-only/benchmark-validated.

**G04a:** primul traseu poate rula cu un singur provider verificat și un skill publicat, fără editor sau al doilea cont. Readback după salvare/selectare. Stare `429` nu devine inferență reușită, iar modelul efectiv/auxiliarele corespund manifestului.

**B06j/B14j/G-JEV:** în paralel cu P2/P4a se introduc SDK/adaptor/typed questions/DecisionReceipt și Settings readback. Ordine: fixture/sentinel inert → shadow live cu acord → paired OFF/SHADOW/ADVISORY după G-LOOP; primele heads relevanță/triage și stagnare. Shadow nu schimbă schedulingul, invalid/missing/timeout→fallback și niciun verdict/scope din scor. Testul inspectează întreg payloadul/logurile, extra_body interzis, retries=0 și deny la sink după Stop/Pause. Mode/model/question/projection/threshold/data-policy fixate per run; advisory numai pe head calibrat. Jev este obligatoriu integrat/evaluat pentru MVP, nu pentru G05a/G06a; beneficiul poate fi nul și trebuie raportat.

## 9. P3a — prima felie HTTP completă

**B07:** contractele ToolDefinition/ToolInvocation/ToolResult din arhitectură §9.6, cu primul adaptor HTTP, apoi broker, policy și proxy HTTP(S) minimal; fixture declarat; acțiune tipizată, approval, fencing, buget, evidență durabilă, events și revocare. B07 adaugă și OPERATOR_CHECK pentru probe funcționale pre-run, conform arhitectură §9.7, pe același broker/ledger/evidence, nu HTTP direct din endpoint. Persistăm DISPATCHING înaintea bytes upstream. Captura respectă limitele din arhitectură de la primul request.

Launcherul pentru assessment integrează provisionarea L07 numai după B01e-build + B01e-integrated/G-NET pentru transport: proxy admis + policy/rețea + self-test negativ înaintea containerelor executor. Harnessul de certificare B07/B09 este separat și limitat la fixture/sinks autorizate; nu declară normal startup ready înaintea propriilor probe. Control plane-ul poate rula fără aceste componente, cu Start blocat; bootul complet tot nu începe un run. Containerele sunt create de launcherul host, nu prin acces Docker dat supervisorului/modelului.

**B08:** rezultat/inventar/evidence inspector și proiecții Overview/Brain stream în UI, SSE cu cursor, reconnect și Stop verificat. `ProjectionEnvelope`, summary server-side și `phase_active` urmează arhitectură §6/§9.1; phase/status nu se deduc din chat. O observație HTTP reală este suficientă; finding/severity/report review încă indisponibile nu sunt umplute cu demo.

**G03a:**

- Request permis → evidence AVAILABLE inspectabil după restart. Request scos din scope, redirect interzis, identity greșită, lease expirat și approval vechi → refuz înaintea efectului.
- Refuz direct egress/host/metadata/DNS/IPv6/MCP/terminal; guard absent sau policy/DB căzut → fail-closed. Matricea de rețele este testată, nu doar citită din Compose.
- Stop revocă dispatchuri noi; requesturi în zbor rămân contabilizate; pierderea control plane-ului expiră lease-ul. Se măsoară separat inferența și efectele.
- Crash înainte/după fsync/rename/commit DB; artefact lipsă/corupt, disc plin și body/decompresie oversized. Niciun verdict/counter nu ascunde probele absente.
- Crash după DISPATCHING → UNKNOWN/NEEDS_RECONCILIATION, fără retry automat; comanda Stop duplicată nu are efect secundar suplimentar.
- Snapshot + cursor, evenimente duplicate/out-of-order și cursor expirat nu dublează counters; UI afișează staleness și resync.
- `CURSOR_CONTEXT_MISMATCH` pentru token din alt run/engagement; paginare și citiri concurente nu amestecă revizii. După Stop/Pause, reconnect sau review/rerender, faza nu reapare activă. Summaries sunt server-side și nu totaluri ale paginii clientului.

## 10. P3-auth și P3b — identități HTTP, apoi browser

**B09h/G-AUTH-HTTP**, după G03a și înainte de G05a: consumă OPERATOR_CHECK/CheckPlan/CheckReceipt B07 pentru Verify login/health înainte de Start, fără copil sau MissionSpec fictive; Cancel/readback și revizii/expiry sunt probate după restart. Apoi livrează anonymous/Basic/token/cookie, seif, login funcțional bounded, pozitiv principal/rol, epoch/lease/refresh owner și replay cu controale noi. Rotated secret durabil înainte de epoch; drift/crash→AUTH_UNKNOWN/INCONCLUSIVE; izolarea A/B/validator și secret/data policy se probează fără browser. B09b extinde același modul la assisted login/SPA, nu duplică auth. Preflightul necesar BOLA include health și G-EFFECT pentru operațiile HTTP folosite. Excepția înlocuiește dependența veche P5a→P3b, **nu** elimină G03b din MVP.

**B09a:** Chromium izolat și sandbox activ, proxy MITM numai în laborator, request buffering înaintea policy, toate subrequesturile corelate și limitate. SW/WS/QUIC/download neautorizat/passthrough oprite. TLS upstream verificat, CA numai în executor.

**B09b:** identități/seif, anonymous/Basic/token/cookie, login asistat în context engagement și dovadă pozitivă principal/rol. Serializare per auth context/obiect și refresh cu owner unic. Același provider AI nu înseamnă aceeași identitate pe țintă.

**G03b:** fixture SPA cu login și API post-auth; token refresh rotativ sub cereri concurente; CSRF consumabil; auth expirat între baseline/probă; cookies izolate și validator pe stare resetată. Fluxul necesar se reproduce fără slăbirea auth de pe țintă. Auth nesuportat nu blochează recon anonim și nu produce negativ.

Se injectează crash după rotația refresh tokenului, înaintea salvării locale, și răspuns întârziat de la owner expirat: contextul devine AUTH_UNKNOWN/blocat, nu se refolosește automat vechiul token și nu se publică epoch fără secret durabil. BrowserActionWindow atribuie requesturi individuale unui attempt/acțiune/generație; cererea întârziată din generația închisă este refuzată, nu atribuită următorului task.

**G-NET:** CONNECT/SNI/Host/path nepermis, rebinding, redirect/subresursă off-scope și request streaming accidental sunt refuzate înaintea traficului relevant. Măsurăm la sink/fixture bytes/stare, nu doar log de policy.

**G-EFFECT:** GET mutator și mutație SPA automată nu modifică starea sub politică read-only fără approval. Sinks de email/webhook și health degradation verifică impactul; cleanup eșuat rămâne vizibil. `UNKNOWN` nu este mapat la read-only de LLM.

## 11. P5a + P6a — prima familie utilă, BOLA cap-coadă

**B10a/B10b:** recon minimal real prin reuse Katana/parsers: capture/import link/form/JSON și JS/OpenAPI/body hints necesare primei operații, apoi map/fingerprint/threat model, dedup conservator, post-auth incremental, tree/tabel și proveniență. Nu dăm endpointul vulnerabil ca soluție și nu scriem preventiv alt crawler. **B10c:** research contextual cu primul consumator justificat; **B10d:** wordlist/baseline cu primul discovery care îl cere. c/d sunt opționale per run și nu prerechizite universale BOLA; se închid pentru capabilitatea promisă MVP prin gates auxiliare de mai jos. API-ul de context oferă snapshot/cursor/paginare și menționează trunchierea. `denominator_revision` și materializarea celulelor inferred/unknown/parametru/epoch au owner în coverage, conform arhitectură §11; nicio obligație descoperită nu devine testată prin simpla existență în hartă.

**B11:** `object-authorization` complet: SKILL.md, metodologie, validator, controale, schema rezultatului, manifest Omnis, fixture privat/partajat și matrice business versionată. Brainul creează ipoteza din observații și deleagă un task îngust. B11/B12 îngheață candidatul și obțin FIXTURE_PASS în PACKAGE_EVAL autorizat înainte de publicarea executabilă; G05a/G06a folosește apoi releaseul exact. StepOutputRef produce input proaspăt din pasul anterior, nu token dintr-un prompt vechi; lipsă/forward-ref/ciclu/Stop refuzate.

**B12:** copil nou de validare și serviciu determinist de verdict; poartă probatorie pentru negativ. Situațiile UNKNOWN/auth drift/buget epuizat rămân INCONCLUSIVE sau BLOCKED.

**B13 — felii legate, nu un singur ticket vag:**

- **B13a:** finding + occurrences/RunFindingLink, impact demonstrat, severitate/CWE, claim_revision, remediere și disclosure-ul acceptat, cu migrare/API/DTO/UI împreună.
- **B13b:** policy `report_review_policy` din revizia runului (OPERATOR_REQUIRED preselectat explicit sau VALIDATOR_ONLY), persistență ReportReview/decizii, review_revision separat de material, comanda idempotentă și audit/readback; UI Accept for report/Hold. Owner findings, contract arhitectură §9.2.
- **B13c:** snapshot/export HTML/JSON server-side, eligibility, excluderi, istoric, stări pending/AVAILABLE/failed și download ownership-checked; nu exportăm pagina curentă din browser sau bytes indisponibili.
- **B13d:** retest autorizat într-un run nou, probe și reguli proaspete, legat de findingul inițial; FIXED/REGRESSED/RETEST_INCONCLUSIVE fără rescrierea raportului vechi.

Conținutul și designul acceptat nu sunt amânate până la P8. Review-ul editorial nu ține runtime-ul pornit și nu este operational approval.

**G05a/G06a:**

- E2E începe cu URL, identități/reguli autorizate, nu endpointul vulnerabil/soluția; reconul și Brainul ajung la finding.
- Obiect privat interzis, obiect partajat legitim, owner legitim și cross-tenant dau verdicte conforme regulilor. HTTP 200 singur nu confirmă.
- Negativ fără precondiții/controale/evidence nu crește coverage; matricea este inspectabilă până la dovadă.
- Coverage curent versus rezultat istoric: bytes indisponibili/context greșit nu califică numeratorul; refacerea epochului nu însumează vechile celule, iar filtrele nu schimbă numitorul global. DB/UI/report la același cursor și denominator_revision coincid; numitor gol → N/A.
- Fixture vulnerabil → CONFIRMED; remediat → retest cu probe noi → FIXED numai cu controale valide; auth expirat → RETEST_INCONCLUSIVE. Raportul vechi rămâne neschimbat.
- B13b: candidat sau ownership străin refuzate; CAS stale, schimbarea claim_revision/manifest/policy, revizia separată a review-ului, duplicate/same-key-different-payload și readback după restart. Accept cu evidence indisponibile este refuzat; Hold rămâne permis pentru CONFIRMED. Decizia nu schimbă verdictul sau statusul runului.
- B13c: generare concurentă cu Hold/claim nou/retention produce un snapshot coerent, nu un amestec. Descărcările reale HTML/JSON includ numai CONFIRMED eligibile; raport vechi identic după schimbări, bytes indisponibili și metadata interne excluse din exportul nou. Crash STAGING, quota/IO failure și retry idempotent nu publică un artifact fals AVAILABLE.
- Providerul secundar și editorul Skills pot fi încă în lucru; nu blochează această demonstrație.

### Gate dependent pentru ambele moduri

**G-FOCUS — B10f/B12f/B13f, după G05a/G06a, obligatoriu pentru MVP, nu retroactiv pentru prima probă BOLA.** B06 compune MissionSpec/FocusEnvelope și briefing; B10f materializează focusul pe operațiile descoperite, B12f verifică criterion outcomes/coverage, B13f raport/retest. Pe aceeași fixture full și focused pornesc de la informații egale: focused invoice-only admite login/health de suport, descoperă și testează numai obligațiile misiunii. Clue off-objective este deferred, auth attack exclus, focus nerezolvat/obiectiv nesuportat cere clarificare/LIMITED, prompt off-scope nu acordă acces. Fixtures verifică task/action traces, input stale, text ostil inert, zero LLM/target la Save și conflict 409; readback după restart și bytes HTML/JSON păstrează mode/mission/denominator. Criteriul funcțional FAIL nu devine finding sau negativ de securitate. Schimbarea materială cere Stop/run nou.

## 12. P4b — Settings complet, în paralel

**B14a:** OpenRouter save/test/delete și Codex device OAuth start/poll/cancel/logout; fără secret în prompt/log, fără fallback personal. Catalog și schimbarea modelelor la limita unui run, nu hot-swap ascuns. Pending login după timeout/restart tratat explicit.

**B14b:** Skills catalog/search/detail/files/readiness; editor simplu cu draft/diff/schema/ref checks/review/publicare/retire. Nu Monaco/IDE complet, nu upload arbitrar de arhive și nu instalare din URL. Scriptul din skill nu rulează la editare.

Pachet nativ + unicul `omnis.yaml`, conform arhitectură §9.4–9.5: tehnică generală distinctă de procedura bounded; schemas, overlays, templates și assets hash-uite. B06/P4a-minim livrează schema și releaseul read-only înaintea primei proceduri, B14b editorul complet. Draft → Review → Eval → Publish citează CandidateSnapshot/digestul exact din B06a/b; eval activ nu cere publicare prematură. Operatorul unic confirmă explicit după review/eval tehnic, autorul AI nu autoaprobă; metodologia-only nu este execuție certificată. Incompatibilitatea explicită se refuză. Lifecycle, disponibilitate, aplicabilitate și evaluare sunt axe separate.

Drafturile UI se persistă în workspace/DB Omnis, nu fac `git commit` automat din procesul web. Publicarea creează release content-addressed read-only și audit; promovarea metodologiei în repo este export/review/commit de dezvoltare separat. Nu amestecăm versionarea surselor cu storage-ul operațional. Un draft nou nu afectează taskurile active; disable blochează utilizări noi, revocarea activă e acțiune separată.

**G04b:** ambii provideri au probe live reale inclusiv cancel/logout/eroare, cu eligibilitate și acord. Fără cont → BLOCKED. Path traversal/symlink/shadowing din editor refuzate, fișierele referite incluse în digest. **Toate taskurile unui run păstrează catalogul acelui run; noul release se selectează numai într-un run nou.** Drafturile pot evolua fără efect pe snapshot; revocarea de urgență a releaseului activ folosește Stop/fencing, nu substituție de versiune. Lipsa unui tool produce UNAVAILABLE, nu instalare tacită.

**B14c:** ImprovementDraft cu material aprobat și slot maintenance după quiescență; reuse native background review/curator/staging, publisher separat. **B21m:** control maintenance și numai apoi cron `no_agent` enqueue; inițial scheduling manual este suficient pentru MVP, periodicitatea automată urmează după G-HERMES-BOUND, nu blochează prima dovadă/raport.

| Gate auxiliar / ticket | Dependențe reale / probă pozitivă | Negativ și readback obligatoriu |
|---|---|---|
| G-MODULE / B06, B14b | Schema/registry minimal B06; două subfaze recon/mapping și trei acțiuni PURE, profil compilat determinist; editor B14b schimbă ordine/config pentru run nou | Unknown handler/schema, cycle/missing dependency/core hook disabled/cod în config refuzate; GET profile/plan la aceeași revizie |
| G-REVISION / B06, B14b | Catalog/prompt/model fixate; input artifact nou sub recipe veche permis | Hot-swap code/config/catalog și stale review refuzate; run vechi identic, release nou doar run nou |
| G-RESEARCH / B10c | H03/H04/H06/H08 + G-DATA + research egress: facts publicabile→sursă primară→lead cu precondiții | Secret/private URL/version ambiguu/redirect/fallback neaprobat/lipsă sursă; GET result/receipt, zero findings din advisory singur |
| G-WORDLIST / B10d/B15 | Capture B10a/b + recipe/inputs fixate→artifact determinist; comparație randament pe fixture | PII/token/empty/oversize/duplicate/absolute origin/baseline drift; GET exact digest/order/provenance; builder nu face target IO |
| G-TOOLS / B07/B09/B15n | Port comun + adaptor certificat pe transport; invocation→Action receipts la sink | Installed≠permitted, digest/parser/template greșit, direct egress/late request/Stop/cancel; no verdict din exit 0 |
| G-IMPROVE / B14c | Draft/review/eval la același digest + G-REVISION, release pentru run nou | Autoapprove/publish, import failure, symlink/stale eval/held-out leakage; GET release și audit exact după restart |
| G-HERMES-BOUND / B19/B21m | G-IMPROVE + runtime slot/quiescence + G-RESEARCH pentru jobs online; maintenance Stop/status readback | Memory/MCP contamination, malformed wake, curator dry-run mutator, schedule paused fără worker stop; fără al doilea writer/grant copiat |

Aceste gates se livrează odată cu consumatorul și sunt obligatorii pentru funcțiile MVP promise, nu un mega-prerechizit al BOLA. Nicio capabilitate target/model/research nu primește derogare prin eticheta „auxiliar”.

## 13. P5b + P6b — recon asumat și celelalte familii

**B15:** consumă reutilizarea Katana/parserelor și ToolInvocation/Action attribution (stack §10 U10), robots/sitemap/form/body params, JS static bounded, OpenAPI JSON/YAML local cu parsare sigură fără ref extern, directory/parameter discovery bounded, soft-404, login page și rate limit. Raportăm protocoalele nesuportate explicit; nu cumpărăm paritate de marketing cu tooluri neverificate.

**B15n:** adaptor Nuclei de semnale, subset HTTP/templates separat fixat și evaluat, fără exec/code/JS/headless/OAST. Hit→Observation/Candidate, nu CONFIRMED; zero matches nu califică automat coverage. Demonstrația adaptorului este MVP; certificarea familiei exposure este E1. Installed/permitted, wrong digest, option injection, cancel/timeout/oversized output și sink attribution sunt probe obligatorii. B09 extinde același port la browser, nu alt registru; E2 adaugă Schemathesis.

**B16:** `xss-reflected`: execuție demonstrată în Chromium izolat, marker unic și control inert; CSP nu se dezactivează; simpla reflecție nu ajunge.

**B17:** `path-traversal-canary`: numai canaryul de laborator autorizat, oracle/proveniență în evaluator, niciodată citire de secrete reale. Valoarea/soluția nu este pusă în prompt/skill.

**G05b/G06b:** rută fără link descoperită din JS/OpenAPI, API post-login, parametri body, soft-404, paginare/context mic, identități distincte și contradicții care schimbă taskul următor fără rescanare globală. Fiecare familie are fixture vulnerabil/remediat, procedură pozitivă/negativă, validator, limite și suite de regresie. Pachetele nevalidate sunt methodology-only, nu cresc catalogul executabil.

## 14. P7 — bucle, concurență și fault injection extinse

**B18a/G-LOOP**, imediat după G06a: reutilizează inbox/ACK/consumed B06, adaugă STEER bounded și replan vizibil. Clue relevant→delta→revizie hartă/ipoteză→task diferit care citează basis; contraexemplul poate închide/no-op justificat. Replay/crash nu dublează taskul; Stop blochează wake; lipsă progres→LIMITED, research eșuat nu blochează fir independent. Nu așteaptă B15/B16/B17/editor/Jev.

**B18c/G-PATH**, după G-LOOP și G06b: canary traversal→operație nouă→BOLA în misiune; pașii și tranziția au replay/evidence/identity-state compatibile. `needs-review`/no-evidence/edge străin nu intră în frontieră ca probat. Counts root-cause nu includ path sau occurrence; UI timeline este extensie delimitată, cu verificare vizuală separată.

**B18b/G07:** extinde concurența/recovery la maximum doi copii inclusiv validator/researcher, task dependencies, stagnare și rezervă validare. Completed runtime ≠ task valid ≠ engagement completed.

**B19:** pause/resume/recovery integrate: crash API, supervisor, Hermes, proxy, executor și DB; queued completion înainte/după Stop/aprobare; process orphan și lease expirat. Restore/checkpoint începe stopped/locked; niciun job nu pornește automat din backup.

**G07:** un rezultat deja consumat nu produce două continuări; unul admis dar neconsumat nu se pierde după crash. Pe scope nou nu se reutilizează approval vechi. Doi copii nu pot împrumuta auth/task/evidence; pentru aceeași sesiune auth așteaptă lease-ul. Coverage identic DB/UI/report la același snapshot. Dacă limita oprește lucrul → LIMITED, nu „pentest complet”.

Finalizarea folosește predicatul determinist din arhitectură: frontieră/obligații/candidați închise, fără inbox/task/approval/cleanup/efect incert restant și executori quiescenți. Trei tururi fără progres nou justificat declanșează stagnare/LIMITED, nu COMPLETED. Un `run.completed` Hermes sau cererea Brainului nu închide direct engagementul.

Fault injection determinist rulează fără LLM unde se poate; probele live suplimentare testează semantica native Hermes, nu consumă conturi implicit în CI.

## 15. P8 — evaluare, operare și livrare

**B20:** corpus sigilat, baseline determinist, scoruri per run și marcarea ratărilor. Închidem gates după criterii fixate înainte, nu adaptate retrospectiv la rezultate.

**B21:** ghid install/start/preflight/pause/stop/recovery/update, diagnostic fără secrete, migrații, backup/restore, retenție/ștergere, storage limits. Arhivele/exporturile nu se deschid activ în browserul operatorului.

B21 închide `omnis` / `omnis start --no-open` / `omnis open` / `omnis status` / `omnis pair` / `omnis run stop` / `omnis stop` / `omnis doctor` pe pachetul instalat, din afara checkoutului. Build web static în imaginea API, manifest release cu wheel/OCI digests, fără install/pull/upgrade la startup. Închiderea browserului nu oprește serviciile; oprirea instanței păstrează datele; restartul cere reconcilierea runului. Probele L01–L10 din arhitectură sunt parte din G-OPS, nu acoperite de screenshotul prototipului.

**B22:** demonstrație din checkout curat, fără editare manuală de DB și fără profil Hermes personal. Documentația numește incompatibilități de OS/browser/protocol și costuri necunoscute.

Demonstrația finală folosește executabilul `omnis` instalat: o comandă pornește serviciile și deschide dashboardul ready, apoi pairing dacă sesiunea UI lipsește. Se verifică separat că launch/open/status nu fac inferență sau trafic target. Pe headless se afișează URL-ul fără secret și `browser_opened=false`. Nicio comandă propusă aici nu este raportată ca funcțională înaintea probei reale.

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

### Protocol comparativ Omnis–Strix

**HF09 / B20, protocol preregistrat, fără superioritate promisă înainte de măsurare.** Păstrăm pragurile corpusului minim de mai sus; comparația nu le înlocuiește și nu le relaxează. Evaluatorul/operatorul aprobă înaintea seriei metricile primare, marja de non-inferioritate/superioritate, intervalele de incertitudine, seeds/ordine, reseturile și invalidările; fără prag ales după rezultat. Dacă numărul de cazuri nu susține concluzia statistică, raportăm comparație descriptivă și incertitudine, nu paritate.

1. Pin Omnis/Strix/builduri, modelele/provider/fallback, PromptBundle/package/procedure/tool/template versions, hardware, profil informațional, buget AI/target/timp/storage și intervențiile permise. Aceleași misiuni, informații inițiale, identități/reguli business și bugete în pereche; unde paritatea tehnică nu este posibilă, o declarăm, nu ascundem avantajul de input.
2. Corpus **held-out vulnerable/fixed/benign**, izolat/resetat, fără soluții/truth/canary accesibile solverului. Fiecare variantă vulnerabilă/remediată din protocolul minim are și scenariu benign cu funcție legitimă asemănătoare; aceleași trei sloturi independente/resetate. Evaluatorul adjudecă independent toate claims și replay-ul; cazul Strix deja citit este numai development, niciodată held-out.
3. Piste separate black-box / grey-box / source-aware, și `FULL_ASSESSMENT` / `FOCUSED_TEST`: aceeași misiune/focus și aceeași informație autorizată în pereche. Nu comparăm focused reușit cu un full și nu atribuim avantajul accesului source motorului de investigație.
4. Raport per run: findings distincte adjudecate pe **cauze-rădăcină**, occurrences și attack paths separat; detecții și **ratări** cu miss stage recon/plan/execuție/validare; **FP** pe fixed/benign; independent **replay**, coverage calificat/numitor, scope/data violations, cleanup/efecte UNKNOWN, **cost**, **latență**, **intervenții**. LLM/decision calls ≠ requesturi target; cost per finding validat este N/A dacă numitorul este zero, UNKNOWN dacă usage nu poate fi verificat.
5. Pentru MVP comparăm numai familiile/subvariantele efectiv suportate și etichetăm subsetul. Raportăm separat breadthul total, unsupported și lipsurile; nu revendicăm paritate generală dintr-un subset favorabil. E1 singur nu acoperă runul Strix de referință; clasele E2 și capabilitățile E4 lipsă rămân vizibile.
6. OFF/SHADOW/ADVISORY Jev și heuristică deterministă au profil/buget egal, set de calibrare separat de held-out și toate fallback/disagreement raportate. Shadow nu influențează taskurile; live cu/fără advisor măsoară efectul, nu un run izolat. Nu ascundem costul decizional în buget „gratuit”.
7. Toate tentativele sunt publicate conform invalidărilor prestabilite; nu best-of/selectarea doar a reușitelor. „Comparabil” cere marja prestabilită și incertitudine; „mai bun” cere câștig pe metrica aleasă fără regresie tacită în siguranță/FP. Cost mai mic cu mai multe ratări este trade-off, nu victorie generală. Niciun rezultat nu este inventat dacă gate-ul este BLOCKED/NOT-RUN.

### Nucleu MVP și extindere competitivă

M0 = fundație P0.4/G00; M1 = prima BOLA G05a/G06a; M2 = MVP coerent cu ambele moduri, G-LOOP, browser/XSS/traversal, G-PATH, Jev real/evaluat, catalog/profil versionat, research/wordlist/improvement demonstrabile când sunt invocate și Settings/operare/evaluare P0–P8. Research și improvement **nu** sunt obligatorii într-un run sau înainte de raport, chiar dacă integrarea promisă trebuie demonstrată pentru release. Public research periodic nu blochează MVP-ul manual; când este activat cere B21m/G-HERMES-BOUND. Următoarele valuri sunt ordinea capabilităților, nu înlocuirea motorului:

| Val | Subfamilii și reuse | Gate observabil |
|---|---|---|
| E1 | Disclosure/config exposure; auth/session/JWT; BFLA/mass assignment; SQLi. Strix + Nuclei exposure + adaptor diferențial/SQLi fixat | Oracle și vulnerable/fixed/benign per subfamilie, funcțional auth-maintenance separat de auth attacks; nu dump implicit |
| E2 | CSRF, DOM/stored XSS, SSRF/XXE, business workflows/race bounded. Strix + Schemathesis stateful, browser/sinks dedicate | Timing/session/business invariant, server-side destinații secundare autorizate, replay și cleanup; fiecare variantă separată |
| E3 | Source-aware snapshot explicit revizuit, source-to-sink hints/remediere/retest; parsere OSS și Shannon R07 numai după decizia de import | G-SOURCE: zero exec la import, source data policy și corpus separat; source-supported ≠ runtime-confirmed |
| E4 | Workers suplimentari, GraphQL/WS/gRPC/OAST, upload/deserializare/RCE și integrări de echipă cerute explicit | Gate nou de protocol/familie/deployment; nu drepturi din import de skill, nu host/hardware implicit |

Inventarul celor 29 ghiduri de vulnerabilitate și al celor 46 suport rămâne complet în anexa JSON.

**Dispoziție exhaustivă a breadthului, fără scheduling inventat:** cele 16 ghiduri legate deja de nucleu/E1/E2/E4 sunt `idor`, `path_traversal_lfi_rfi`, `xss`, `information_disclosure`, `authentication_jwt`, `broken_function_level_authorization`, `mass_assignment`, `sql_injection`, `csrf`, `ssrf`, `xxe`, `business_logic`, `race_conditions`, `insecure_file_uploads`, `insecure_deserialization`, `rce`. Restul de 13 au dispoziție **METHODOLOGY_ONLY / EXECUTION_UNSCHEDULED** la import: `agentic_system_security`, `argument_injection`, `browser_security`, `header_injection`, `http_request_smuggling`, `llm_prompt_injection`, `nosql_injection`, `open_redirect`, `prototype_pollution`, `semantic_confusion`, `ssti`, `subdomain_takeover`, `weak_password_detection`. Nu dispar din catalog și nu devin implicit E1; o subprocedură executabilă cere ticket/oracle/transport/fixture/gate propriu. E3 este profil de informație, nu o familie în plus. În starea actuală toate cele 75 ghiduri sunt source-reviewed/not-imported și execution_certified=false.
 `extindere_apropiata` este prioritate de cercetare, **nu** sinonim E1: un ghid upload poate avea subprocedură inertă mai devreme, execuția riscantă rămâne E4; business modelling e MVP, mutațiile business sunt E2. HTTPX ProjectDiscovery din ghid nu este biblioteca Python HTTPX; tooling/python nu autorizează shell. Catalogul se raportează prin metodologie disponibilă, adaptor/transport gata, oracol evaluat și permisiune per run. Releaseul cu breadth apropiat de Strix cere lista explicită de subfamilii/scenarii din E1/E2/E4 și probele lor; nu redenumim trei familii „paritate”.

### G-DATA și G-OPS

Marker sensibil sintetic și secret de test urmărite prin request/response, eroare provider, compresie, logs, screenshots, export, backup și restart. Engagementul B nu citește datele lui A. Retenția și ștergerea au manifest, inclusiv derivatele și limitele backupurilor. Restore într-un root separat verifică DB + artefacte; niciun secret din backup nu ajunge în Git sau outputul CI.

Un raport istoric supraviețuiește ștergerii probelor fără a pretinde replay curent: UI/exporturile noi arată MISSING/DELETED/CORRUPT separat de verdictul istoric; raportul vechi rămâne imuabil și indică data/snapshotul disponibilității. Test: ștergere/retention → evidence unavailable → replay refuzat, fără rescrierea trecutului.

## 16. UI/UX ca acceptare, nu doar stil

**Baseline vizual acceptat în df17a29:** compoziția, pastilele, densitatea, stadiul și panourile cerute se păstrează în componentele conectate; G-DESIGN nu mai așteaptă încă o rundă de aprobare estetică. B04 verifică apoi experiența conectată la API; B08 prima dovadă integrată; B13 primul finding real. Prototipul rămâne DEMO permanent. Niciun ecran real nu preia rândurile/metricile demo.

- Navigare globală Home/Dashboard · Engagement · Settings; navigare contextuală **Overview · Brain stream · Findings · Coverage · Reports**. Candidates/Investigations și Setup sunt acțiuni secundare, iar Endpoints este subvedere Coverage. Identitatea/epoch/snapshot selectat rămân vizibile la dovezi și matrice; Settings nu intră în taburile engagementului.
- Stop persistent, `STOPPING` verificat, Start cu preflight/rezumat; approve necesită detaliile acțiunii exacte, nu un buton vag „permite agentului”.
- Formular setup cu scope, context/reguli business, identități opționale, efecte/bugete/data policy și review; salvare draft fără a consuma buget.
- Tree + tabel + inspector; matrice coverage filtrabilă, evidență raw escapata și redactată implicit; findings confirmate separat de candidates/inconclusive.
- Status stale/reconnecting, loading, empty, error, unsupported, blocked, not implemented și N/A distincte. Nicio acțiune de control nu afișează succes optimist.
- Desktop 1440/1280, tabletă 1024 și mobil 390/320; accesibilitate keyboard/focus/dialog/contrast, zoom 200%, reduced motion, fără overflow global. Print raport offline.

### Matrice UI → date/comandă → livrare → probe

Toate rândurile sunt **NEÎNCEPUTE în produs**. Contractele/API-urile sunt propuse în arhitectură §9; fiecare felie introduce împreună migrarea/DTO-ul/handlerul/componentele și testele necesare. Înaintea acelei felii, UI arată disponibilitatea reală, nu un buton care pretinde succes. URL/deep-link/back/refresh păstrează contextul; restabilirea selecției nu pornește un run. În matrice, subrutele abreviate moștenesc prefixul complet al resursei din același rând, nu `/api/v1/settings` generic. Fiecare mutare cere session/CSRF, ownership, If-Match/expected revision și command ID; GET readback trebuie să confirme exact ținta/revizia după restart, 202 este numai receipt. Migrarea/DTO/handler/UI se introduc împreună cu primul consumator, niciun endpoint viitor stub în P0.

| ID | Suprafață / acțiune | Owner, date/API și migrare | Ticket / gate | Probe pozitive și negative |
|---|---|---|---|---|
| UI01 | Home: creare/selectare/Recent engagements/Needs review | engagements/runs, draft+revision și GET dashboard; active run distinct de selecție | B02–B04 / G01 | create/read/restart; 409/cross-context; total global nu este pagina; fără run → NOT_RUN |
| UI02 | Overview: stadiu, metrici, Severity, budget, atenție | runs/policy/coverage/findings; ProjectionEnvelope + GET summary; câmpuri/run progress adăugate cu sursa lor | B08, B10/B12/B13 / G03a/G06a | counts distincte și aceeași revizie; unknown cost nu devine zero; Stop/Pause preced faza; lipsă API fără fallback demo |
| UI03 | Brain stream: filtre tip/actor, replay și linkuri | DomainEvent/SSE Omnis; cursor engagement-order legat de run, actor/refs redactate | B08 / G03a | replay/resync/session expiry; duplicate/out-of-order și token străin; nu log/chain-of-thought; linkul restabilește obiect/context |
| UI04 | Findings: disclosure, PoC/pași/validator/evidence | findings/validation/evidence; Finding/Occurrence/RunFindingLink și manifests; GET findings/evidence | B12/B13a / G06a | CONFIRMED separat de candidates; identitate/proveniență; MISSING/HTML/SVG/ID străin; focus și bytes indisponibili în toate view-urile |
| UI05 | Accept for report / Hold | findings/report_review; ReportReview/decizii + policy/revizii, POST report-review și readback | B13b / G06a | CAS/material schimbat, ownership, candidat, duplicate; Accept cere bytes, Hold nu falsifică verificarea; fără relansarea runului |
| UI06 | Coverage / Endpoints: filtre și inspectare | surfaces/coverage/evidence; operații/parametri/celule și denominator_revision; queries bounded | B08/B10/B12 / G03a/G05a/G06a | inferred/unknown/N/A, epoch nou, parametru, proveniență greșită; filtru nu schimbă totalul; gol → N/A |
| UI07 | Reports: generate/history/HTML/JSON/print | reports + snapshot/artifact refs; job durabil, POST reports/list/download salvat | B13c / G06a | confirmed eligibile, excluderi/partial, generare concurentă, STAGING/crash/quota; bytes descărcați și istoric imuabil după Hold/retention |
| UI08 | Setup / Verify login/health/Cancel check / preflight / Start/Pause/Resume/Stop / operational approval | engagements/runs/policy/InstanceControl + identities/vault; revision/Command/Action/Approval și Identity/AuthContext/secret refs/auth_epoch, migrare cu B09h; identity/check API conform arhitectură §9/§9.7, OPERATOR_CHECK și CheckReceipt; POST check commands pentru CANCEL, GET checks pentru readback | B02/B04/B05/B07/B09h/B19; G01/G02/G03/G-AUTH-HTTP/G07; assisted browser numai B09b/G03b | + save/restart și Verify fără Brain, principal/rol/auth_epoch din GET identity/check receipt, Cancel/shutdown înainte de send; − secret echo, identity străină, login invalid/expirat nu devin ready sau negativ; draft fără efect, run activ/409; Stop în overlay, 202≠STOPPED, deconectare/barieră/efect incert |
| UI09 | Settings providers/models: save/test/OAuth/cancel/logout | settings + runtime-host privat; projection/config command, grant numai în store dedicat | P4a/B14a / G04a/G04b | readback, 401/429/cancel/timeout; fără fallback personal/hot-swap; test live numai cu acord și buget |
| UI10 | Settings Skills/Runtime/Data | settings/catalog/evidence/ops; draft/release pin, inventory, retention/backup, comenzi tipizate | B14b/B21 / G04b/G-DATA/G-OPS | draft fără execuție, pin per run, path/symlink/shadowing; diagnostic fără secret; ștergere/restore cu manifest și startup locked |
| UI11 | HF01: selector/textarea/Save/Next/Back/Review | EngagementRevision mod/obiectiv/constraints → engagements; PUT/GET `/api/v1/engagements/{id}` și GET revisions; migrare B02 + RunSnapshot la B06 | B02/B04, apoi B06; G01/G-FOCUS | + exact text/mod/revizie după reload/restart; − gol focused/oversize/HTML activ/409, zero apeluri la Save; GET readback nu echo optimist |
| UI12 | HF02: mode/objective badge, clarificare/STEER, task reason | MissionSpec/FocusEnvelope/Task refs → runs/tasks/policy; GET summary/tasks și POST `/api/v1/runs/{run}/commands`; revizii append-only cu primul consumator | B06/B10f/B18a; G-FOCUS/G-LOOP | + operații și suport legate de obiectiv; − ref străin/stale/Stop, schimbare materială refuzată; command receipt + GET tasks/summary același cursor |
| UI13 | HF03: coverage focalizat/criterion outcomes, report/retest | mission/focus/denominator refs → coverage/reports; GET coverage, POST/GET reports, artifact download, POST findings retests; B10f/B12f/B13f extind persistence existentă | după G06a; G-FOCUS | + univers etichetat și outcomes distincte, retest run nou; − skip nu ascunde gap, funcțional nu umflă finding; GET și bytes HTML/JSON/restart identice snapshotului |
| UI14 | HF04: Skills file tree/technique/procedure/overlay, draft/diff/review/eval/publish/retire | SkillPackageRevision și receipts → settings; GET `/api/v1/settings/skills/{id}`, POST `/{id}/drafts`, PUT `/drafts/{draft}/files`, POST `/drafts/{draft}/validate`, `/review`, `/eval`, `/publish`, POST `/{id}/retire`; drafts DB/workspace și release RO la B14b | B06/P4a schema/release minim, B14b/G04b editor | + CandidateSnapshot→eval lab-only→Publish exact digest și GET release/files după restart; editul uman confirmat de operator după review/eval tehnic, nu al doilea cont; − stale review/eval, wrong ref/digest/symlink, autor AI autoapprove, unknown tool; run activ neschimbat; eval activ necesită acord separat |
| UI15 | HF05: briefing/debriefing redactat și handoff în stream/Investigations | TaskBriefV1/TaskResultV1/PromptBundleRevision → tasks + integrations/hermes; GET `/api/v1/runs/{run}/tasks`, `/events`; payloaduri versionate în Task/Attempt/Inbox B06 | B06/H03–H08, B08/G03a | + goaluri identice corelate independent, exact refs la refresh; − context mandatory trunchiat, role schimbat, cross-run, stale mission, Stop/double wake; GET tasks/events cu același cursor |
| UI16 | HF06: Runtime tool readiness, capability requests și invocation inspector | ToolDefinition/receipts → settings registry; ToolInvocation/Action → tasks/policy/evidence; GET `/api/v1/settings/runtime`, GET `/api/v1/runs/{run}/tasks` și events, POST commands pentru cancel admis; metadata/refs cu B07/B09/B15 | B07/G03a, B09/G03b, B15n/G-TOOLS | + installed/compatible/evaluated/permitted distincte și invocare→requests; − digest/dependency/lease/argument injection, zero≠failure; GET receipts + evidence/sink readback, nu exit code singur |
| UI17 | HF07: threat model, roster și plan/subphase inspector în Coverage/Brain stream | ThreatModelRevision/PlanInstance/RunProgress → runs/surfaces/tasks; GET `/api/v1/runs/{run}/threat-model`, `/plan`, `/tasks`, `/events`; refs/proiecții B10/B18a peste facts/taskuri | B10b/B18a, G-LOOP/G-MODULE | + clue→revizie→task și trigger/reason la refresh; − inferred≠observed, duplicate/reordered cursor; GET plan/summary/tasks coerente |
| UI18 | HF07: path timeline în finding inspector | AttackPath/steps/transitions → findings/validation; GET `/api/v1/runs/{run}/attack-paths`; migrare legături/evidence odată cu B18c | B18c/G-PATH după G-LOOP/G06b | + ambele defecte și tranziția probate; − same-host/edge străin/epoch incompatibil/lipsă evidence; GET path/raport fără count dublu; vizual separat |
| UI19 | HF08: Decision support mode/model/heads/buget, test explicit și receipts | DecisionSupportRevision/DecisionReceipt → settings + integrations/jev; GET/PUT `/api/v1/settings/decision-support`, POST `/test`, GET `/api/v1/runs/{run}/decisions`; config/revizii B06j/B14j | B06j/B14j/G-JEV; live cu acord | + save→GET exact config/digest după restart, shadow fără efect; − hot-swap/secret echo/invalid response/Stop; receipt/fallback/UNKNOWN vizibile |
| UI20 | HF07: profile clone/edit/order/validate/publish și catalog acțiuni | WorkflowProfileRevision/Phase/Subphase/ActionDefinition → settings; GET `/api/v1/settings/action-catalog`, GET/POST `/workflow-profiles`, POST `/{id}/drafts`, PUT `/drafts/{draft}`, POST `/drafts/{draft}/validate`, `/review`, `/eval`, `/publish`; drafts/release la B14b | B06 registry, B14b/G-MODULE/G-REVISION | + config/ordine schimbă doar run nou; − unknown/cycle/excluded dependency/core disable/cod; GET draft/release/plan exact, 409 păstrează draft |
| UI21 | HF07: Research sources/activity, wordlist recipe/files/preview | sources policy → settings/research adapters; GET/PUT `/api/v1/settings/research-sources`, GET `/api/v1/runs/{run}/research`; recipe/artifact → skills/evidence, operații draft/review/eval/publish UI14 și GET evidence | B10c/d/B14b/B15; G-RESEARCH/G-WORDLIST | + provenance/source/time/digest/caps și readback; − query secret/private URL, fallback, zero corpus, baseline drift; preview pasiv nu pornește fuzzer |
| UI22 | HF07: Improvements list/diff/accept/hold/reject/eval/publish; maintenance status/pause/stop | ImprovementDraft/receipts + maintenance jobs → settings/supervisor; GET `/api/v1/settings/improvements`, POST `/{id}/review`, `/eval`, `/publish`; GET `/api/v1/maintenance`, POST `/commands`; migrare B14c/B21m | G-IMPROVE/G-HERMES-BOUND; după quiescență, periodic ulterior | + release exact după eval și status WAITING_FOR_RUNTIME_SLOT; − AI autoapprove/stale/held-out leak/wake neadmis; command receipt + GET worker quiescent, pause schedule≠stop |
| UI23 | E3: import source snapshot revizionat | sources artifact/review → engagements/evidence; POST/GET `/api/v1/engagements/{id}/sources`; migrare cu E3, nu P0 | E3/G-SOURCE + data policy | + snapshot imuabil/readback restart; − symlink/remote ref/secret/import exec; zero execuție upload; source-supported≠runtime-confirmed |

P1 compară shellul și stările reale cu UI acceptat; B08 adaugă comparația cockpit/stream; B13 finding disclosure/review/report. Testele API/PostgreSQL verifică autoritatea și persistența, iar web component/E2E verifică contractul, focusul, staleness și layoutul. `browser_check.py` asupra DEMO rămâne separat și nu închide aceste gates.

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

### Amendamentele HF01–HF10 și recomandările înlocuite

Toate rândurile sunt **ADOPTAT ÎN SPECIFICAȚIE / RUNTIME NOT-RUN**, nu gates de produs trecute. Handofful final și review-urile păstrează proveniența deciziei; acest tabel trimite la unicul baseline, nu la încă un plan.

| ID | Contract canonic / UI | Owner / ticket / verificare |
|---|---|---|
| HF01 | Arhitectură §9.3, UI §3; selector și obiectiv, UI11 | engagements B02/B04, G01: save inert + reload/restart/409/limits/inert HTML |
| HF02 | Arhitectură §9.3/§5/§7; MissionSpec/FocusEnvelope, UI12 | runs/tasks/policy B06/B10f/B18a, G-FOCUS: suporta login, nu auth attack/global hunting |
| HF03 | Arhitectură §6/§9.2–9.3/§11; outcomes/coverage/report/retest, UI13 | coverage/validation/reports B12f/B13f, G-FOCUS: numerator onest și bytes export exact |
| HF04 | Arhitectură §9.4, stack §10; pachet/tehnică/procedură, UI14 | settings B06/P4a-minim→B14b, H03/G04b/G-REVISION: wrong digest/ref/edit-after-eval refuzate |
| HF05 | Arhitectură §5/§9.5; PromptBundle/brief/result, UI15 | tasks/integrations/hermes B06, H03–H08: binding corect, context îngust, stale/Stop/no double wake |
| HF06 | Arhitectură §3/§9.6, stack §10; tool registry/invocation/Action, UI16 | policy/evidence/adaptoare B07/B09/B15n, G-TOOLS/G-NET: installed≠permitted, fiecare request atribuit |
| HF07 | Arhitectură A15/A16/§6.1–6.2; modul/research/wordlist/improvement, UI17/18/20/21/22 | tasks/surfaces/settings B10/B14c/B18/B21m; G-LOOP/G-PATH și gates auxiliare, nu prerequisite BOLA |
| HF08 | Arhitectură §5.1, stack U07/U13; Jev UI19 | DecisionAdvisor B06j/B14j, G-JEV: shadow fără efect, advisory calibrat, fără verdict/permisiune |
| HF09 | Plan §15, arhitectură §11; corpus/comparație | evaluator B20/G08: matched inputs/budgets, root-cause/FP/FN/replay/cost, fără superioritate nemăsurată |
| HF10 | Plan §19, README/readiness și adjudecare P0.4 | fundație păstrată; WIP neintegrat, assessment_ready=false, niciun scaffold MVP sau promovare harness→G00 |

| Recomandare veche / conflict | Decizie normativă înlocuitoare |
|---|---|
| Sol: P4a-minim opțional, inbox doar la B18, toate importurile offline înainte de live | P4a este obligatoriu înainte P2-live; inbox/ACK/consumed B06; import numai cu primul consumator, nu mega-gate |
| P5a depindea de Chromium/P3b | P3-auth/G-AUTH-HTTP permite primul BOLA API-only; P3b rămâne obligatoriu pentru MVP/browser/XSS |
| Replan demonstrat abia la P7; „fără Chains” absolut | G-LOOP imediat după G06a; G-PATH dependent după familiile necesare. Fără graph/council/tab Chains; timeline bounded cu review vizual separat |
| Jev „dacă îl vrem”, validare Jev sau pruning definitiv | Integrare decisă OFF/SHADOW/ADVISORY, primele heads triage/stagnare, fără CONFIRMED/scope/publicare/ștergere coverage |
| Katana/Nuclei excluse din baseline; reuse doar conceptual | Stack §10 fixează U01–U14 și S/M/R/HM: cod/teste/prompturi/metode, pachete prin adaptoare; source-reviewed nu este installed/evaluated/permitted |
| Technique folosit ca procedură; al doilea manifest/workflow engine | Technique generală + Procedure bounded; SKILL.md nativ și unicul omnis.yaml, profile compozabile pe registry trusted |
| Research/improvement prezentate ca flux dominant/prerequisite | Bucla de pentest §6.1 este primară; auxiliare opționale per run, improvement pentru viitor după quiescență |
| Shannon doar reference-only în primul review versus port R07 în supliment | Shortlist tehnic R07 adoptat; importul AGPL cere decizie de distribuție separată, nu blocaj general sau runtime nou |
| E1 suficient pentru breadthul runului Strix; trei familii = competitor complet | Înlocuit de E1–E4 și protocol matched; runul include clase E2/capabilități E4, paritatea nu este declarată |
| Readiness preimplementare/P0.1 și fixture host-network descrise drept stare prezentă | Dovezi istorice etichetate; stare locală P0.4 și WIP UDS/TCP din §19, G00 deschis. AGENTS status vizual protejat rămâne excepție explicită |

Trasabilitatea rezolvă recomandarea **în specificație**, nu pretinde testul trecut. Pentru fiecare gate implementat se păstrează comanda, versiunile, output sanitizat și verdictul real.

## 18. Definition of Done și pornire

MVP-ul este livrat numai când P0–P8, inclusiv P4b, au probe, fluxul complet este demonstrat, suitele safety/evidence/negative/recovery trec și raportul reproduce starea reală. Nu este suficientă terminarea unei liste de taskuri sau existența unui screenshot.

**După acordul G-DESIGN putem începe fără conturi:** B01–B04 și probele inerte B05–B06. Până atunci lucrăm numai la prototip și specificații. **Înainte de live LLM:** operatorul alege cont/model și aprobă bugetul/data policy; nu folosim implicit sesiunea personală existentă. **Înainte de target effects:** G02 și topologia fixture trecute, scope/efecte/reguli explicit aprobate.

Nu atribuim termene fictive. Estimarea se face după P2/P3b pe rezultatele probelor. P0.1/P0.2 și bootstrapul P0.3 sunt implementate local; P0.4 are status/install/install-image și probe de topologie din §19, nu launcherul complet sau întregul arbore. După P0-control și B02, P1-web/P2-inert pot avansa în paralel conform §4; B10–B13 rămâne prima demonstrație a valorii de securitate.

## 19. Reluarea într-o sesiune nouă — stare și următoarea felie

**Stare actuală: P0.3_IMPLEMENTED_LOCAL / verificat și review-uit local; [dovezi și adjudecări](verification/p03-local-bootstrap.md); P0.4 IN_PROGRESS cu [CLI status](verification/p04-cli-status.md), [bundle/install](verification/p04-bundle-install.md), [image build](verification/p04-image-artifact.md), [contract Compose](verification/p04-compose-contract.md), [imagine instalată](verification/p04-image-install.md) și [topologie host-only probată](verification/p04-host-uds.md); CI remote NOT-RUN.** `P0.1_IMPLEMENTED_LOCAL` și `P0.2_IMPLEMENTED_LOCAL` sunt păstrate: [P0.1](verification/p01-local-readiness.md), [P0.2](verification/p02-local-control.md). Există bootstrap web real servit de API, pairing/sesiune/logout și status autentic, cu contracte generate și E2E PostgreSQL/browser. CLI-ul poate citi controlul privat, copia releaseul și instala explicit imaginea locală din afara checkoutului. Harnessul opt-in a pornit separat DB/API/supervisor din release instalat, fără porturi Docker publicate; **CLI-ul operațional nu verifică încă HTTP și nu pornește/oprește serviciile; G00 rămâne deschis**. Rulările vechi fără DB dedicată au eșuat; fixture-ul revizuit în `d8f79df` nu mai publică port prin Docker 27 și a permis un `make check` exit 0 pe WIP ([dovezi și limite](verification/p04-safe-test-db.md)), însă gate-ul pe checkoutul curent este BLOCKED de fixture/conftest/CI neintegrate, nu doar de lipsa unei rerulări; vezi §19.1. Contractele de mai jos sunt executate numai în limita incrementului probat. Citește README/AGENTS, §4–§5/§19, arhitectură §4/§12, stackul și dovezile/README-urile API, web și CLI. Nu reia brainstormingul/designul acceptat și nu folosi remote-ul ca bază dacă HEAD local este înainte.

**P0.1 — contract executat: API/DB readiness real, subfelie B01a/B01b/B01c.** Acesta a fost primul rezultat observabil, nu închiderea întregului P0. S-au introdus pachetul API instalabil, schema minimă InstanceControl necesară control plane-ului și probele sale; `admission_open` inițial false. Contracte implementate `GET /health/live` și `GET /health/ready`: primul reflectă procesul, al doilea verifică PostgreSQL și versiunea schemei. `api_ready` nu înseamnă `dashboard_ready` sau `assessment_ready`; ultimele rămân false cât lipsesc componentele. Nu folosi un răspuns constant „healthy” sau SQLite ca substitut.

- **Perimetru:** `api/pyproject.toml`, `uv.lock`, app factory/core config/DB/schemas strict necesare, Alembic/InstanceControl și teste unit/integration/migrations; `ops/compose.test.yaml`/imaginea DB fixată și harnessul izolat necesar; root Makefile/CI/.gitignore/.dockerignore numai pentru comenzile și artefactele reale ale feliei. Nu crea acum toate modulele/ports/repositories sau directoare goale web/cli/executors.
- **Mediu:** Python/uv și Postgres din stack, lock nou de produs rezolvat și auditat, mediu separat de Hermes. Instanță/volum DB de test dedicate și identificabile; niciun profil personal, `.env` existent, DB sau serviciu străin nu este adoptat/oprit/șters. Permisiunile/pașii privilegiați se cer separat; nu se modifică firewall global pe ascuns.
- **RED → GREEN:** app/liveness reală; readiness pozitiv pe PostgreSQL migrat și negativ la DB căzută/schema lipsă sau incompatibilă; Host nepermis refuzat; migrare pe DB goală, persistență/restart, lifecycle pool și output fără secrete. Upgrade se probează între revizii când există o revizie anterioară, nu se inventează una. Startup/reload/health nu importă/pornește Hermes, scheduler de assessment, proxy/executori și nu contactează provideri/ținte.
- **Comenzi implementate:** `make check-api`, `make test-api`, `make test-migrations` și `make check-api-wheel`; rădăcina `make check` integrează componentele care există. CI folosește aceleași comenzi. Lipsa unui prerechizit dă BLOCKED/exit nenul; nu un test skipped prezentat ca trecut. Salvează output real, review independent și commit coerent; verifică SHA/status înainte de pasul următor.
- **Non-obiective:** UI complet, `omnis` funcțional, SSE, provider/OAuth, secret vault, recon, finding, executori și evaluare. Nicio integrare nativă sau scanare pretinsă pe baza acestei felii.

**P0.2 — contract executat:** pairing/Host/Origin/CSRF, control local și supervisor inert cu barieră durabilă/admitere concurentă, receipturi idempotente, lease/fencing și erori corelate. Probe locale de procese reale pentru restart/crash/răspuns pierdut, migrare/upgrade și API/control instalate; comparația cerință→cod→probă și limitele sunt în [evidență](verification/p02-local-control.md). Quiescența/FINALIZE acoperă numai lucrul inert; nu atestă containere oprite. Niciun producător runtime sau endpoint Start fictiv.

**Restanța B01a înainte de P0.3 — închisă local:** lint/format Ruff și mypy strict sunt fixate și executate pe toate sursele/testele API, cu controale negative reale în Make/CI și reproducere din checkout curat. OpenAPI declară erorile efective; au fost remediate și cazurile de expiry NULL, anulare la teardown și import din alt worktree. [Proba și review-urile finale](verification/p02-python-quality.md) nu au blocante cunoscute pentru intrarea locală în P0.3. `make lint-api` și `make typecheck-api` sunt comenzi reale, incluse în gate-ul comun; CI remote rămâne NOT-RUN fără push separat.

**P0.3 — contract executat:** build React/TypeScript/Vite fixat, shell/tokenuri/fonturi locale portate fără model DEMO; pairing/session/logout cu readback, status real, loading/expiry/error/stale/UNAVAILABLE; OpenAPI → TS cu drift în gate; assets same-origin și readiness DB/schemă/assets/API/control. `assessment_ready=false`. Teste componente, E2E cu backend real și coduri sintetice emise numai privat, review/remedieri și capturi în [matricea P0.3](verification/p03-local-bootstrap.md). Nu este UI P1 complet sau o nouă aprobare vizuală.

**P0.4 — incrementele 1–5 și proba separată de topologie executate local:** `cli/` are wheel/lock proprii; `omnis status [--json]` verifică IPC privat/identitatea pe DB reală din afara checkoutului, fără a pretinde HTTP `dashboard_ready` ([probe](verification/p04-cli-status.md)). `omnis install --bundle` copiază idempotent un bundle API/CLI/web checksum-bound ([probe](verification/p04-bundle-install.md)); buildul OCI din release instalat a fost exercitat separat cu UID nonroot implicit/mapat ([probe](verification/p04-image-artifact.md)), iar `omnis install-image` construiește explicit imaginea și păstrează receiptul local ([probă](verification/p04-image-install.md)). Un harness opt-in a pornit PostgreSQL/API/supervisor, a migrat o DB disposable și a servit asseturile prin API UDS/forwarder host din artefactele instalate, fără port Docker publicat; a fault-injectat separat un event loop API blocat în imaginea instalată, a citit `ExitCode=4` după Docker stop cu grace de 15 s și a probat reconcilierea UDS la restart explicit ([rezultate și limite](verification/p04-host-uds.md)). **Aceasta nu este instalarea/rularea prin `omnis`**: startupul, pairingul terminal, deschiderea UI, stopul durabil și persistența stop/start nu sunt implementate sau certificate.

**Ordinea restului P0-control:** continuă P0.4 cu instalarea și lifecycle-ul **prin launcherul `omnis`**, preflight/lock/concurență, startup/pairing/open/stop, probe de topologie/UID și negativele complete L01–L05-control/L08-core din afara checkoutului. `d8f79df` este probă istorică, nu gate curent. Mai întâi trebuie adjudecat/integrat de autor fixture-ul WIP UDS/no-network împreună cu conftest/Make/CI/docs încă TCP; cere acord separat pentru această integrare/DB. Abia după aceea rulează gate-ul canonic pe checkout curat și păstrează separate negativele LAN, crash/restart și celelalte porți, fără a substitui rezultatul prin probele de harness. Numai după acestea se închide G00; apoi B02/P1-data. Review și commit după fiecare comportament, nu un singur commit de fază.

**Reluare P0.4 după clear:** citește întâi §19.1–19.2 și [adjudecarea buclei](verification/p04-loop-adjudication.md), apoi verifică HEAD/checkoutul, [dovezile P0.3](verification/p03-local-bootstrap.md), [incrementul CLI](verification/p04-cli-status.md), [bundleul](verification/p04-bundle-install.md), [imaginea](verification/p04-image-artifact.md), [contractul Compose](verification/p04-compose-contract.md), [instalarea imaginii](verification/p04-image-install.md) și [proba DB/API/supervisor host-only](verification/p04-host-uds.md), [fixture-ul DB de test fără publicație](verification/p04-safe-test-db.md), inclusiv eșecurile istorice și limitele TIME_WAIT. Remedierile forwarderului deja probate rămân în istoricul lor; restanțele curente sunt fixture/launcher/supervisor/owner și porțile neexecutate, nu redeschiderea defectelor reparate. Continuă exclusiv launcherul din P0.4 în felii TDD/review/commituri mici, fără refacerea webului, conturi/LLM/ținte. Nu pretinde că topologia de harness înseamnă `omnis start` sau gate-uri complete închise.



### 19.1. HF10 — impact asupra implementării existente

Recontrol static la amendarea pornită din `3fc3d46298720a1529a922247781fab435cda483`, pe `p04-control-topology-wip`, nu din remote. HEAD-ul acesta și WIP-ul observat sunt mai noi decât snapshotul adjudecării istorice. `assessment_ready=False` este încă în `api/src/omnis/api.py`; CLI-ul definește numai `status/install/install-image`; webul este bootstrap real cu run controls indisponibile; migrările existente sunt 0001–0004 pentru instance/sessions/lifecycle/receipts. **Nu există încă un motor pentest de rescris.** Niciun modul/tabel/endpoint de mission/skill/tool nu este creat în P0.4 prin amendament.

| Dispoziție | Cod/contract inspectat | Decizie, test necesar și limită |
|---|---|---|
| PĂSTRĂM | `api.py`, `core/db.py`, `core/schema.py`, `modules/instance/`, migrations 0001–0004 | API/DB/readiness, instanță/barieră/lease/fencing și schema fizică rămân fundația. WIP db.py nu este al acestei sarcini; fără migrare nouă acum. |
| PĂSTRĂM | `security/`, `transport/local_control.py`, `core/web_assets.py`, web bootstrap/client/generated | Pairing/session/logout/Host/Origin/CSRF, IPC privat și assets same-origin; nu înlocuim cu admin Hermes, chat store sau DEMO. assessment_ready=false și Start indisponibil rămân corecte. |
| PĂSTRĂM | `cli/src/omnis_cli/main.py`, `status.py`, `release.py`, `compose.py`, `forwarder.py`; `ops/Dockerfile.control` | Status privat, install bundle/image și UDS/forwarder existente. CMD este încă `omnis.serve`, nu owner exec WIP; nu afirmăm că `omnis start/pair/open/stop` funcționează. |
| CORECTĂM ACUM | Contracte documentare/status/readers/teste documentare | Rezolvăm premisele depășite și definim contracts/gates. **Cod de produs schimbat: niciunul**; nu a fost stabilit un defect mic cu reproducer sigur complet, independent de WIP/DB, care să justifice intervenția în această felie. |
| EXTINDEM ÎN FELIA VIITOARE | `ops/compose.test.yaml`, `ops/run_test_db_gate.py`, `api/tests/conftest.py`, Makefile/CI/docs | BLOCKED pentru integrare: WIP network_mode=none + UDS versus conftest TCP/port, runner `--probe-only`; CI încă folosește `compose port` și nu pregătește mediul CLI. Necesită acord/ownership/izolare/backup-teardown și integrarea autorului, nu un nou harness. |
| EXTINDEM ÎN FELIA VIITOARE | `supervisor/__main__.py::run`, `owner.py::_watch/main`, teste lifecycle | Deadline-ul stop.wait nu întrerupe heartbeat/quiesce/release suspendate; OSError waitpid/gate-write/reap rămân riscuri în owner WIP. Sunt constatări statice/istorice, nu repro live nou. Remediere focalizată cu TDD și DB/procese atestate înainte de Stop/owner promotion; nu schimbăm CMD acum. |
| EXTINDEM ÎN FELIA VIITOARE | CLI launcher B01f / P0.4 | start --no-open → pairing/open → stop durabil/persistență, pe artifact instalat, L01–L05-control/L08-core; harness nu ține locul comenzii. |
| EXTINDEM ÎN FELIA VIITOARE | B02/B04→B06/P4a→B07/B09/B10–B21 | Mission în agregatul engagement/run, package/brief cu primul copil, tool invocation cu primul adaptor, apoi loop/coverage/paths/Jev/auxiliare. DTO/migrare/API/UI/test împreună; fără scaffold general preventiv. |

WIP protejat, neintegrat: `api/src/omnis/core/db.py`, `api/tests/test_fixture_ownership.py`, `ops/compose.test.yaml`, `api/tests/test_database_url.py`, `ops/run_test_db_gate.py`, `tests/development/test_test_db_gate.py`. Snapshot de bytes la început și readback la final; nicio includere în commiturile amendamentului. Nu se execută DB/scans/paid models/accounts pentru această verificare. `make check`/`make test`: BLOCKED (fixture neintegrat și configurația DB dedicată absentă); CI remote NOT-RUN; G00 deschis. Testele de documente/Chromium offline nu schimbă această stare.

### 19.2. Următoarea felie implementabilă

**P0.4-prerequisite, cu acordul autorului WIP/operatorului pentru integrare și DB disposable:** un singur contract UDS/no-network în Compose + conftest + runner + Make/CI/docs. Succes observabil: allow pe clusterul propriu atestat (image/project/socket/system_identifier), deny înainte de CREATE/DROP pentru ownership/path/DSN greșit, apoi gate-ul canonic pe checkout curat, cleanup numai pe resursele proprii și date păstrate. Nu promite G00 și nu extinde harnessul owner. Fără acord rămâne BLOCKED; nu adoptăm WIP tacit.

**Următorul increment de produs după prerechizit:** `omnis start --no-open` instalat, executat din afara checkoutului, calea `omnis.serve` păstrată până la probă contrară. Succes: o singură instanță, release/instance identity verificate, migrare explicită/readiness HTTP+assets+control reale, zero provider/target; al doilea launch reutilizează, port străin/schema incompatibilă refuzate fără a atinge resurse străine. Pair/open/stop sunt felii distincte dependente; numai setul complet închide G00. În paralel este posibil un import offline Strix B06 delimitat (provenance/root/recon/BOLA/counterevidence + tests), dar nu ține locul launcherului și nu activează runtime.

**Excepție de predare:** README consemnează INSTRUCTIONS_UPDATE_BLOCKED. Statusul vizual vechi din AGENTS.md nu a putut fi actualizat deoarece aprobarea interactivă a expirat; fișierul protejat rămâne nemodificat. Pentru acea corecție este necesar acord separat prin mecanismul de protecție; nu se încearcă bypass sau o schimbare implicită a regulilor sale. Auditul tehnic și pașii de mai sus sunt păstrați în documentele permise.
