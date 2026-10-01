# Omnis — re-review și readiness pentru implementare

**Registru: review istoric 25 septembrie 2026 + status curent HF01–HF10 · Nu validare a produsului complet**

**Status curent:** P0.1/P0.2/P0.3_IMPLEMENTED_LOCAL; P0.4 parțial cu [SL02 start headless instalat](verification/p04-installed-start.md). G00 deschis, CI remote NOT-RUN, `assessment_ready=false`. [Auditul aprofundat](verification/p04-pre-sl03-deep-review.md) are **CHANGES_REQUESTED**: RT-F01/RT-F02, două P1 lifecycle, și AR01/AR02, două P2 validare, confirmate de părinte și neremediate. Corecțiile aparțin SL02 și preced continuarea SL03; nu cer SL04 deja implementat. [SC01/SC02 și gate-urile PASS anterioare](verification/p04-start-remediation.md) sunt păstrate în scope, fără completitudine implicită. DB veche rămâne RECOVERY_PENDING separat, fără stop/adopție automată. Integrarea DB/runnerul se păstrează; nu se reface harnessul. HF01–HF10 și restul MVP rămân specificații pentru consumatorii lor.

**Deep review de flux/livrare:** [adjudecarea curentă](verification/omnis-deep-review.md) păstrează F01–F04 și clarificările ulterioare, probele și limitele re-review-ului. Traseul de implementare este detaliat în plan §2.1/§4.2–4.3; contractele de bootstrap/eval/pre-run/model admission/replan sunt în arhitectură, nu într-un plan paralel. Continuarea P0.4 rămâne condiționată de prerechizitele §19.2, fără refactor preventiv.

**Notițele originale, NS01–NS19:** [adjudecare și probe](verification/omnis-skill-pattern-amendment.md). Patternul general (arhitectură §9.9), completitudinea/reviewerul (§9.10) și JS/discovery (§11.1) se livrează conform planului §4.4 și ticketurilor B06/B10d/B15/B18a.r/B14b. Prima BOLA, scope-ul P0 și limitele runtime rămân explicite; aceste amendamente nu închid G00.

**Secțiunile 1–8 de mai jos sunt auditul istoric preimplementare**, inclusiv START_PENDING_NEW_SESSION/P0.1, probele/numerele și arborele atunci necreat. Nu descriu starea prezentă, nu anulează autorizările P0.1–P0.4 ulterioare și nu sunt al doilea plan. Registrele RR/PA păstrează istoricul, nu primesc retroactiv PASS runtime din testele documentare.

## 1. Verdict de arhitectură

**VISUAL_ACCEPTED pentru prototipul df17a29; START_PENDING_NEW_SESSION pentru implementare.** Utilizatorul a aprobat aspectul și cere auditul final. Auditul a aliniat structura/contractul `omnis`, noul UI și succesiunea livrării; punctul de reluare este **P0.1, plan §19**, după mesajul explicit de pornire. Această sesiune nu implementează aplicația. Excepția administrativă INSTRUCTIONS_UPDATE_BLOCKED este declarată în README: AGENTS.md a rămas nemodificat după expirarea aprobării interactive, nu a fost ocolită protecția. **NO-GO pentru trafic target până la G-DEPENDENCIES, G-RUNTIME și G-NET.** Planul v2 și arhitectura v1, cu amendamentele §12, rămân singura bază. „Final” nu înseamnă integrare nativă sau eficacitate demonstrată.

Direcția rămâne cea cerută: local-first, UI progresivă, un operator/un engagement activ, Hermes nativ, recon/browser/JS/post-auth, hartă, ipoteze, validator, bucle și raport. Trei familii inițiale complete, nu un GET vândut ca MVP și nu un catalog nelimitat. Settings complet și ambii provideri rămân în livrarea finală, dar nu pe drumul critic al primului finding.

## 2. Ce s-a revizuit

- [Plan v2](Omnis_Implementation_Plan.md): etape, dependențe, backlog, porți și protocol de evaluare.
- [Arhitectura v1](Omnis_MVP_Architecture.md): granițe, RPC/binding, proxy/HTTPS, auth, date, stări, SSE și raportare.
- [Stack baseline](Omnis_Stack_Baseline.md): metadate primare, variante respinse, rezolvări și probe reale; [output](verification/stack-probe.json).
- [UI/UX](Omnis_UI_UX_Spec.md), [DESIGN.md](../DESIGN.md), [prototip](Omnis_UI_Prototype.html) și renderer/teste documentare.

Au existat review-uri independente pentru versiunile propuse și riscurile de arhitectură, apoi o a doua lectură independentă a documentelor revizuite și a UI/toolingului. Rezultatele lor sunt constatări, nu autoritate de a marca testele aplicației drept trecute. Snapshoturile citite de review pot preceda ultimele corecții; starea livrată este cea verificată de părinte după integrare.

## 3. Toate recomandările inițiale

Tabelul R01–R12 din plan a fost verificat programatic: fiecare ID apare exact o dată. Secvențierea Settings/browser/primul finding, probele Hermes, revocarea scope-ului, efectele necunoscute, regula business, auth concurent, negative evidence, persistența artefactelor, E2E/baseline, suportul recon, toate copiile datelor și raport/retest sunt acum decizii sau porți explicite.

**Stare: rezolvate în specificație, NEÎNCEPUTE în aplicație.** Aceasta nu este o declarație că 12 probleme de cod au fost remediate într-un produs existent.

## 4. Corecții suplimentare din re-review

| ID | Constatare | Rezolvare în baseline / probă obligatorie |
|---|---|---|
| RR01 | Contextul browserului nu identifică singur fiecare acțiune de fundal | BrowserActionWindow, binding run/attempt/action/epoch/generație; requesturi separate, generații închise refuzate; G03b |
| RR02 | Limită de fișier nu este limită de recepție/decompresie | Capuri incrementale wire/decompressed/stored înainte de buffering, inclusiv chunked; G03a măsoară consumul efectiv |
| RR03 | Politica datelor era verificată transversal prea târziu | ModelProjection v1 și G-DATA-EARLY înainte de LLM/target data; P8 extinde retention/restore |
| RR04 | Owner unic de refresh nu rezolvă crashul după rotație | Intenție durabilă, fencing la publicare, secret durabil înainte de epoch; AUTH_UNKNOWN fără retry token vechi |
| RR05 | Catalog per run versus „task nou vede release nou” | Taskurile unui run folosesc același snapshot; release nou numai în run nou; revocare prin Stop/fencing |
| RR06 | COMPLETED/stagnare fără predicat | Supervisor determinist, frontieră/obligații/candidați/efecte/cleanup închise; prag de trei tururi fără progres |
| RR07 | Regula de rerulare putea schimba numitorul benchmarkului | Motive exogene prestabilite, invalidare de evaluator, maximum o înlocuire per slot, toate tentativele publicate; erorile Omnis rămân în scor |
| RR08 | Raport istoric după ștergerea evidence | Verdict istoric separat de disponibilitatea curentă; UI/export nou arată MISSING/DELETED/CORRUPT și replay indisponibil |

Alte alegeri închise: pairing local distinct de tokenul admin Hermes, TCB explicit și copii care nu sunt sandboxes OS, cursor alocat sub lock în ordinea commiturilor, tranzacție comună pentru autoritate/buget/approval, un singur owner de refresh AI și slot activ de stare de caz arhivat numai cu procese oprite.

Amendamentul launcherului a trecut printr-un review separat de lifecycle. Două neconcordanțe au fost corectate **în contract, nu în cod de produs**: shutdownul instanței închide durabil admiterea `InstanceControl` înainte de oprirea runului (Start/Resume/Settings concurente și crash launcher sunt în L08/G00); supervisorul controlează process groups prin adaptoare, numai launcherul host controlează containerele. Bootstrapul Settings trece explicit prin runtime-host în namespace-ul corect. Arborele de fișiere și probele L01–L10 sunt propuneri pentru acordul utilizatorului, nu dovezi de operare deja executată.

Nu am acceptat automat sugestia de a trece la altă orchestrare/batch sincron pentru a evita wake-ul. Păstrăm contractul nativ dorit și gate-ul exact de continuare/reconciliere; o schimbare ulterioară necesită ADR, nu reducere tacită de scope.

### 4.1. Audit pre-implementare după acceptarea UI

Audit pe baseline-ul `aaab291`, apoi amendamente verificate în același plan/arhitectură; două review-uri independente read-only au verificat UI→date/API/etape și dependențele bootstrap/runtime/proxy. „Rezolvat” mai jos înseamnă contract clarificat, **nu implementare sau gate runtime trecut**.

| ID | Gap constatat | Remediu și statut |
|---|---|---|
| PA01 | Acceptarea vizuală lipsea din baseline; startul era confundabil cu aprobarea layoutului | VISUAL_ACCEPTED pentru df17a29 și START_PENDING_NEW_SESSION în documentele permise. Statusul AGENTS rămâne INSTRUCTIONS_UPDATE_BLOCKED, cu acord separat necesar. |
| PA02 | Nav vechi și stream sub overview în structura de fișiere | Plan §16/UI §2/arhitectură §12: cinci taburi, owners dashboard/stream/coverage; rutele demo nu sunt API de produs. SPEC_ALIGNED. |
| PA03 | Summary/global aggregation/cursor și faza nu aveau contract complet | ProjectionEnvelope, per-engagement sequence cu context run, citiri coerente, RunProgress/phase_active; B08 și negativele de replay/context. SPEC_ALIGNED. |
| PA04 | Denominatorul/epochurile și evidence actuale versus rezultat istoric erau ambigue | Arhitectură §11: materializare/revizie, inferred/unknown, epoch curent, provenance și verificabilitate; B10/B12. SPEC_ALIGNED. |
| PA05 | Report review fără default policy, owner/migrare și revizii separate | Arhitectură §6/§9.2, UI §3/§8, B13b: policy explicită, claim/review revisions, audit/CAS/idempotency, Hold fără bytes și candidat refuzat. SPEC_ALIGNED. |
| PA06 | Exportul nu era legat suficient de setul eligibil și disponibilitate | B13c: snapshot consistent, job durabil/AVAILABLE, allowlist, download salvat și controale concurrency/retention/bytes/istoric; review nu ține runul deschis. SPEC_ALIGNED. |
| PA07 | G00/launcher depindeau circular de web P1, runtime-host P2 și SSE P3 | P0-control include bootstrapul real; runtime absent UNAVAILABLE, L05/L08 împărțite pe subprobe reale. P0.1–P0.4 au ordine explicită. SPEC_ALIGNED. |
| PA08 | Gate proxy cerea G-NET înainte de adaptor; P2-live preceda configurarea providerului | B01e-build/LAB_TEST_ONLY apoi B01e-integrated în harness autorizat; P2-inert→P4a-minim→P2-live; DAG verificat, zero apeluri provider incidentale la boot. SPEC_ALIGNED; probele rămân neexecutate. |
| PA09 | Lipsea contractul compact pentru clear și repartizarea noilor componente | Plan §16 UI01–UI10 mapează fiecare suprafață la owner/migrare/ticket/probă; §19 definește perimetrul, non-obiectivele și acceptarea P0.1. SPEC_ALIGNED. |

Recontrolul [pinurilor](verification/preimplementation-pins.json) a găsit toate cele 33 de versiuni exacte solicitate în registre; nu a reinstalat/admis un lock nou. Checkoutul Hermes instalat corespunde SHA-ului baseline; documentația oficială de integrare a fost recitită, fără probă RPC/provider și fără schimbarea pinului. Scope-ul rămâne local-first, nu un redesign de stack sau permisiune de trafic.

**Relectură independentă după amendamente:** pe `7e90c09` nu a identificat blocaje substanțiale de specificație rămase în secțiunile verificate. A verificat ordinea etapelor, dimensiunea P0.1, separarea policy/reviziilor și raportul istoric versus evidence curente. Excepția AGENTS rămâne declarată; acest verdict nu închide gates runtime. Rezultatul comenzilor finale ale părintelui este păstrat în [preimplementation-check.json](verification/preimplementation-check.json), cu scope și limite, separat de probele aplicației încă inexistente.

## 5. Decizii schimbate de execuție reală

### Frontend

Cercetarea de metadata nu a prins conflictul de declarații TypeScript între Vitest 5.0.1 și jest-dom 7.0.1. `tsc --noEmit` l-a reprodus (TS2428). Baseline-ul selectează Vitest 4.1.11; același typecheck strict și testul de dialog/router au trecut. Nu am folosit `skipLibCheck`, `--force` sau `--legacy-peer-deps` pentru a ascunde incompatibilitatea.

Mediul moștenit production a făcut `React.act` indisponibil în primul test; scripturile de test cer acum `NODE_ENV=test` și instalarea include explicit devDependencies. Buildul Vite a trecut cu warnings `use client` consemnate, nu ca build perfect fără warnings.

### API

CPython 3.13.15/uv 0.12.19 au rezolvat și instalat mediul API separat; `uv pip check`, DTO valid/invalid, OpenAPI, ASGI in-process, dialect async psycopg și criptare sintetică au trecut. Nu s-a conectat DB și nu s-a implementat seiful. Testul ASGI evită calea TestClient/HTTPX depreciată observată în Starlette curent.

### Proxy — blocaj real rămas

Rezolvarea `mitmproxy 12.2.3` a reușit, dar metadatele advisories au marcat dependențe **cryptography, h2, msgpack și tornado**. Capurile pachetului împiedică selectarea simplă a versiunilor remediate. Buildul este **REJECTED_FOR_TARGET_USE**, nu aprobat cu un warning. B01e are owner, cale upstream/patch minimal auditat și suită obligatorie înainte de P3.

Nu afirmăm că fiecare advisory este exploatabil în Omnis; nici nu alegem o frontieră nouă de securitate pe baza absenței unui exploit demonstrat. API crypto nu a fost coborât, iar proxyul afectat nu a fost pornit.

## 6. UI și documente

Review-ul a identificat Stop inaccesibil în overlay-uri, stare inert rămasă după resize, focus pierdut la Stop/Start, identitate/epoch incoerente în inspector, Pause fără stări intermediare, touch targets sub prag și ancore imbricate în cuprinsul rendererului. Acestea au regresii dedicate în remedierea UI/tooling.

**Verificarea iterației UI acceptate a trecut:** 22 teste documentation/model la livrarea df17a29; regenerare și `render_docs.py --check` pentru cele cinci cititoare; **116 verificări Chromium** pentru prototip și documente, fără eșecuri, erori JavaScript sau requesturi HTTP(S) neașteptate. Pe lângă Stop/modal/drawer/focus, PAUSING/drain/Resume și context/epoch, suita verifică Brain stream, linkuri probatorii după filtre incompatibile, finding detail, evidence indisponibilă cu verdict păstrat, pixeli de focus și repoziționarea findingului pe mobil. Include reduced-motion, forced-colors și un stress test CSS zoom 200% (nu certificare pentru zoomul nativ al browserului). Raportul este în [browser-check.json](verification/browser-check.json). Nu este certificare WCAG, test screen-reader/cross-browser sau E2E al aplicației inexistente.

Referința `omnis-cockpit-v5.html` este interpretată în UI/UX §0: cockpit cald monocrom, fără sidebar permanent/brain graph/council, Brain stream și finding inspector cu validator/evidence. Comparația vizuală a fost făcută pe randări reale desktop 1440 și mobil 390. Review-urile independente au identificat legături care pierdeau contextul și focus invizibil/scroll păstrat; regresiile RED→GREEN și remedierile sunt în commituri. Toate datele rămân explicit sintetice. **Aprobarea vizuală a venit ulterior de la utilizator („arata bine. bravo”); nu este dedusă din testele sau review-ul automat.**

Placementul anterior amesteca nivelurile global și engagement și a fost corectat după feedback: **Dashboard central → engagement selectat**, cu **Settings separat** și **Brain stream în tab propriu**. Selectorul global de stări și previewurile evidence/replay/retest sunt în panouri demo pliante, nu în fluxul de operare. UI/UX §0 distinge cererea utilizatorului, baseline-ul, exemplele din template și copy-ul sintetic. Review-ul reordonării a reprodus step leakage în New engagement, identitate Stop/selecție globală lipsă în drawer și taburi acoperite după navigare; toate au regresii și remedieri verificate. Rutele au fost inspectate și după clickuri reale, nu numai prin încărcare directă.

DESIGN.md a trecut CLI 0.4.0 fără erori/warnings și are export DTCG. Verificarea documentară a folosit Playwright Python 1.60.0 și Chromium 145.0.7632.159 de pe host; nu certifică executorul planificat Playwright 1.63.0 sau imaginea lui. Prototipul este etichetat DEMO, cu conexiuni/form submit blocate; rendererul este numai pentru Markdown trusted al proiectului, nu pentru target evidence.

## 7. Necunoscute păstrate vizibil

| Gate | Owner | Închidere necesară |
|---|---|---|
| G-DESIGN | Operator | VISUAL_ACCEPTED pentru df17a29; START_PENDING_NEW_SESSION confirmă structura/contractul `omnis` și pornirea feliei, nu execuția live |
| L01–L10 / G-OPS | Integrare + operare | P0-control și L05-control/L08-core reale, apoi extensiile SSE/runtime/execuție în fazele lor; startup/readiness/pairing/stop/recovery, toate probele aplicației NEÎNCEPUTE |
| G-DEPENDENCIES / B01e | Integrare/executori | B01e-build remediat/admis pentru harness izolat, apoi B01e-integrated/G-NET; fără derogare pentru buildul respins |
| G-RUNTIME / H01–H08 | Integrare Hermes | Child binding/lineage, skill pin, surse auth, wake/Stop și efecte de crash, inclusiv live cu acord |
| G-DATA-EARLY | API/securitate | Proiecție model-facing și markeri înainte de date de țintă către provider |
| G-NET / G03 | Broker/executori | Trasee blocate măsurate, subrequest attribution, limits, scope și lease fail-closed |
| G-PROVIDER | Operator + integrare | Cont/model eligibil, data policy și buget explicit; ambii provideri până la MVP final |
| G00 DB/build | Backend/dev environment | Lockuri finale de produs, migrații și DB reală; imaginile nu sunt certificate prin metadata |
| G08 | Evaluare/operator | Corpus sigilat, threshold fixat, rezultate reale, baseline și retest |

Owner înseamnă rol de implementare, nu o persoană inventată. Fără aceste probe nu există declarație de MVP funcțional. Configurația de rețea/seccomp și calitatea testelor de vulnerabilitate nu pot fi certificate printr-un document.

## 8. Concluzie și controlul schimbării

**Pregătit tehnic pentru începerea P0.1 la cererea din sesiunea nouă**, nu pentru un assessment sau MVP declarat funcțional. Contractul primei felii și al P0-control este în plan §19, iar DAG-ul din §4 separă datele B02, P1-web, P2-inert, configurarea P4a și live. Arborele `api/` + `web/` + `cli/` există numai ca plan, nu ca schelet gol. UI-ul acceptat și matricea §16/contractele arhitectură §9 împiedică portarea numai a culorilor sau inventarea de date în produs. Browserul/auth și primul finding rămân înaintea editorului complet Skills; proxyul respins/bindingul/confinarea/live provider rămân porți reale.

**Înaintea predării fără excepții**, statusul vizual istoric din AGENTS.md ar trebui aliniat printr-o aprobare separată. Auditul nu a putut face acea scriere protejată; documentele permise au starea actuală și limitarea explicită, fără modificarea regulilor de siguranță sau auto-autorizarea implementării.

Un rezultat nou din P2/P3 poate cere amendament, dar acesta trebuie să numească motivul, alternativa, impactul de scope și testul. Nu prezentăm un plan ca dovadă de siguranță, cost sau performanță și nu compensăm o probă ratată cu date simulate.
