# Omnis — re-review și readiness pentru implementare

**25 septembrie 2026 · Review de specificație și probe de dependențe/documente · Nu validare a produsului**

## 1. Verdict de arhitectură

**Readiness tehnic pentru P0/P1 și probele inerte Hermes, dar G-DESIGN este PENDING:** utilizatorul cere aprobarea UI/UX și stabilirea structurii sistemului/comenzii `omnis` înaintea acordului de implementare. **NO-GO pentru trafic target până la G-DEPENDENCIES, G-RUNTIME și G-NET.** Planul v2 și arhitectura v1, cu amendamentele §12, rămân singura bază. „Final” nu înseamnă integrare nativă sau eficacitate demonstrată.

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

**Verificarea curentă a părintelui a trecut:** 16 teste unitare/contracte documentare; regenerare și `render_docs.py --check` pentru cele cinci cititoare; **101 verificări Chromium** pentru prototip și documente, fără eșecuri, erori JavaScript sau requesturi HTTP(S) neașteptate. Pe lângă Stop/modal/drawer/focus, PAUSING/drain/Resume și context/epoch, suita verifică Brain stream, linkuri probatorii după filtre incompatibile, finding detail, evidence indisponibilă cu verdict păstrat, pixeli de focus și repoziționarea findingului pe mobil. Include reduced-motion, forced-colors și un stress test CSS zoom 200% (nu certificare pentru zoomul nativ al browserului). Raportul este în [browser-check.json](verification/browser-check.json). Nu este certificare WCAG, test screen-reader/cross-browser sau E2E al aplicației inexistente.

Referința `omnis-cockpit-v5.html` este interpretată în UI/UX §0: cockpit cald monocrom, fără sidebar permanent/brain graph/council, Brain stream și finding inspector cu validator/evidence. Comparația vizuală a fost făcută pe randări reale desktop 1440 și mobil 390. Review-urile independente au identificat legături care pierdeau contextul și focus invizibil/scroll păstrat; regresiile RED→GREEN și remedierile sunt în commituri. Toate datele rămân explicit sintetice. **Aceasta este propunerea pentru feedback, nu aprobarea vizuală a utilizatorului.**

DESIGN.md a trecut CLI 0.4.0 fără erori/warnings și are export DTCG. Verificarea documentară a folosit Playwright Python 1.60.0 și Chromium 145.0.7632.159 de pe host; nu certifică executorul planificat Playwright 1.63.0 sau imaginea lui. Prototipul este etichetat DEMO, cu conexiuni/form submit blocate; rendererul este numai pentru Markdown trusted al proiectului, nu pentru target evidence.

## 7. Necunoscute păstrate vizibil

| Gate | Owner | Închidere necesară |
|---|---|---|
| G-DESIGN | Operator | Feedback/aprobare cockpit/findings, structură sistem și contract `omnis`, apoi acord explicit de implementare |
| L01–L10 / G-OPS | Integrare + operare | Executabil `omnis` instalat, startup inert/readiness/pairing, runtime-host privat, stop/recovery și zero efecte la boot; toate probele NEÎNCEPUTE |
| G-DEPENDENCIES / B01e | Integrare/executori | Proxy remediat, lock/build provenance, audit și teste TLS/HTTP/confinare |
| G-RUNTIME / H01–H08 | Integrare Hermes | Child binding/lineage, skill pin, surse auth, wake/Stop și efecte de crash, inclusiv live cu acord |
| G-DATA-EARLY | API/securitate | Proiecție model-facing și markeri înainte de date de țintă către provider |
| G-NET / G03 | Broker/executori | Trasee blocate măsurate, subrequest attribution, limits, scope și lease fail-closed |
| G-PROVIDER | Operator + integrare | Cont/model eligibil, data policy și buget explicit; ambii provideri până la MVP final |
| G00 DB/build | Backend/dev environment | Lockuri finale de produs, migrații și DB reală; imaginile nu sunt certificate prin metadata |
| G08 | Evaluare/operator | Corpus sigilat, threshold fixat, rezultate reale, baseline și retest |

Owner înseamnă rol de implementare, nu o persoană inventată. Fără aceste probe nu există declarație de MVP funcțional. Configurația de rețea/seccomp și calitatea testelor de vulnerabilitate nu pot fi certificate printr-un document.

## 8. Concluzie și controlul schimbării

După acordul G-DESIGN, primul lot rămâne fundație/web/persistență și probe inerte în paralel, fără redeschiderea stackului după preferințe. Arborele `api/` + `web/` + `cli/`, responsabilitățile fișierelor și standardele sunt acum descrise în arhitectură §12, nu create ca schelet gol. Primul finding vine devreme; browserul/auth nu sunt amânate după editorul Skills. Proxyul respins și bindingul nativ rămân porți reale.

Un rezultat nou din P2/P3 poate cere amendament, dar acesta trebuie să numească motivul, alternativa, impactul de scope și testul. Nu prezentăm un plan ca dovadă de siguranță, cost sau performanță și nu compensăm o probă ratată cu date simulate.
