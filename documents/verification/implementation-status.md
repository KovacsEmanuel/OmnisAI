# Omnis — hartă globală de implementare și review

## Rol și surse

Aceasta este o **proiecție de status, nu un plan concurent**. [Arhitectura](../Omnis_MVP_Architecture.md) decide comportamentul; [planul §4/§4.2/§4.3/§15/§19](../Omnis_Implementation_Plan.md) decide ordinea, dependențele și gates. Git, codul și registrele din [verification](README.md) sunt memoria proiectului. Conversația, task list-ul și rezumatele subagenților sunt indicii, nu aprobări sau rezultate de teste.

**Referință produs inspectată:** `4113c785ae8cacccb44ba8db79e1805d271c21dd`. **Revizie de produs testată în ultimul registru complet:** `1dfa022f44e9f3e6154a91459a7b3801ded25db5`; diferența până la referință este numai registrul SL02, verificată prin Git. SHA-ul curent și ultimul autor al hărții se citesc din Git la fiecare folosire, nu se inventează o auto-referință la commitul care conține această pagină.

Nu s-au rerulat aici suitele de produs. `PASS_LOCAL_RECORDED` înseamnă rezultat real înregistrat la **revizie/scope** explicit, nu PASS transferat automat oricărui HEAD viitor. Harta nu spune că serviciile sunt încă active: probele instalate au fost retrase, datele private păstrate.

## Unde suntem

- **P0-control parțial:** P0.1/P0.2/P0.3 și SL01/SL02 au implementare și probe locale. Comanda instalată `omnis start --no-open` a trecut traseul real; aplicația nu este încă un MVP complet.
- **Următorul increment de produs din plan:** SL03 / P0.4c / B01f pair/open, apoi SL04 / P0.4d stop/recovery. B02/P1-data vine după G00, nu după un simplu start reușit.
- **G00 deschis; CI remote NOT-RUN; assessment_ready=false.** Pair/open în CLI, stop durabil, runtime Hermes, provideri și motorul de assessment nu sunt livrate de SL02.
- **Review aprobat în scope:** constatările F1/R1–R7/IPC/B1–B4 ale SL02 sunt închise punctual în [registrul SL02](p04-installed-start.md). Acest fapt nu este o garanție că toate cerințele întregului plan au fost implementate sau auditate.
- **În review separat:** auditul de completitudine cerut după predarea SL02; până la adjudecarea unui raport complet nu îi atribuim verdict. Actualizarea acestei hărți nu îl închide.
- **Proces de dezvoltare, nu funcție MVP:** skillul de status global este în lucru conform [contractului](project-status-skill.md). Nu schimbă următoarea felie de produs.

## Legendă: trei axe independente

| Axă | Valori și interpretare |
|---|---|
| Cod | IMPLEMENTED = livrabilul rândului există; PARTIAL = numai o parte; NOT_IMPLEMENTED = livrabil nelivrat, chiar dacă are fundații reutilizabile |
| Probe | PASS_LOCAL_RECORDED = dovadă citată cu limite; PARTIAL = numai subset; NOT_RUN = neexecutat; FAIL = eșec măsurat; BLOCKED = prerechizit/constatare care împiedică acceptarea |
| Review | APPROVED_SCOPED = acceptat de părinte în scope și snapshot delimitat; IN_REVIEW = review în curs fără verdict; NOT_REVIEWED = fără review de implementare; CHANGES_REQUESTED = constatări rămase |

Un document specificat/revizuit nu primește review de **implementare** aprobat. Schimbarea codului relevant după o probă/review cere revalidare sau explicație verificabilă a neafectării; un commit, test verde sau notificare de subagent nu promovează singur un gate. Nu calculăm procente din numărul de SL-uri: dimensiunile și dependențele sunt diferite.

## Fundații anterioare registrului SL

| Componentă | Implementat și verificat local | Rest și sursă |
|---|---|---|
| P0.1 | API/DB readiness, pachet instalabil, migrare/schema InstanceControl | Nu launcher/MVP; [P0.1](p01-local-readiness.md) |
| P0.2 | Pairing API, sesiuni, Host/Origin/CSRF, control privat, supervisor inert, lease/fencing/barieră | Nu stop de containere/runtime; [P0.2](p02-local-control.md), [quality](p02-python-quality.md) |
| P0.3 | Shell React real, pairing/logout/status, assets same-origin, OpenAPI/TS, E2E local | Nu UI P1 sau Start assessment; [P0.3](p03-local-bootstrap.md) |
| P0.4 înainte SL02 | Status privat, bundle install, image build/install, UDS/forwarder și probe de topologie | Harnessurile nu sunt comenzi; [status](p04-cli-status.md), [bundle](p04-bundle-install.md), [image](p04-image-install.md), [topologie](p04-host-uds.md) |
| G-DESIGN | VISUAL_ACCEPTED pentru prototipul df17a29, acord de implementare P0 | Nu nouă aprobare vizuală și nu G00; [README / excepția AGENTS](../../README.md) |

## MVP — registrul complet al subfeliilor

Ordinea de mai jos păstrează ID-urile canonice; **nu este o coadă strict liniară**. Dependențele de închidere și ramurile paralele rămân cele din plan §4. Pentru rândurile viitoare, probele și review-ul **implementării** sunt NOT_RUN/NOT_REVIEWED; revizuirea specificației nu schimbă aceste valori.

| ID | Fază / ticket canonic | Rezultat urmărit | Cod | Probe | Review | Rest / dependență / limită | Sursă |
|---|---|---|---|---|---|---|---|
| SL01 | P0.4a / prerechizit B01c | Fixture PostgreSQL privat și runner comun | IMPLEMENTED | PASS_LOCAL_RECORDED | APPROVED_SCOPED | Date păstrate; nu închide G00 | [DB](p04-test-db-integration.md) |
| SL02 | P0.4b / B01f start | Start headless instalat, readiness/status, reuse și cleanup propriu | IMPLEMENTED | PASS_LOCAL_RECORDED | APPROVED_SCOPED | Pair/open și stop durabil lipsesc; negativele și limitele sunt în registru | [SL02](p04-installed-start.md) |
| SL03 | P0.4c / B01f pair/open | Pairing TTY-only și deschiderea browserului verificat | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | CLI pair/open lipsesc; reutilizează pairingul API/web P0.2–P0.3 | [Plan §4.2/§19.2](../Omnis_Implementation_Plan.md) |
| SL04 | P0.4d / B01f stop/recovery | Stop/recovery operațional, concurență și persistență | PARTIAL | PARTIAL | NOT_REVIEWED | Există bariera/lease/fencing și status; comenzile și gate-ul lifecycle complet lipsesc | [Plan §4.2/§19.2](../Omnis_Implementation_Plan.md) |
| SL05 | P1-data / B02 | Engagement draft/revizie/scope persistent | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G00; migrare și API B02 | [Plan §6](../Omnis_Implementation_Plan.md) |
| SL06 | P1-web / B03–B04 | Dashboard/setup pe date reale | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B02; bootstrapul nu este experiența P1 | [Plan §6](../Omnis_Implementation_Plan.md) |
| SL07 | P2-inert / B05 | Runtime-host Hermes nativ inert | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B02/G00; handshake, pin, home izolat | [Plan §7](../Omnis_Implementation_Plan.md) |
| SL08 | P2-inert / B06a | Catalog seed și rezolvarea pachetelor | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B05; STATIC/PURE și G-MODULE-core | [Plan §7](../Omnis_Implementation_Plan.md) |
| SL09 | P2-inert / B06b | Task/Attempt și binding copil nativ | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B06a; inbox/receipts/lineage durabile | [Plan §7](../Omnis_Implementation_Plan.md) |
| SL10 | P2-inert / B06c | Proiecții de date către modele | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Înaintea oricărui model; G-DATA-EARLY | [Plan §7](../Omnis_Implementation_Plan.md) |
| SL11 | P2-inert / B06m | Admission și buget înainte de model dispatch | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Seam real pre-send și G-MODEL; fără contabilizare doar declarativă | [Plan §7](../Omnis_Implementation_Plan.md) |
| SL12 | P4a-minim | Settings minim pentru primul provider/run | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După P2-inert; readback și selecție explicită | [Plan §8](../Omnis_Implementation_Plan.md) |
| SL13 | P2-live | Probă Hermes/model real fără ținte | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După data/model gates și acord cont/model/buget; G02-live/G04a | [Plan §7–8](../Omnis_Implementation_Plan.md) |
| SL14 | B01e-build | Build proxy remediat, numai pentru laborator | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Pinul publicat respins nu devine sigur dintr-un build; înainte P3a | [Plan §5](../Omnis_Implementation_Plan.md) |
| SL15 | P3a / B07 | Broker HTTP, policy, evidence și primul request permis | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După build admis și G02-live; G03a/G-NET | [Plan §9](../Omnis_Implementation_Plan.md) |
| SL16 | P3a / B08 | Run/stream/SSE și observație inspectabilă | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B07; evenimente și proiecții persistente, nu date DEMO | [Plan §9](../Omnis_Implementation_Plan.md) |
| SL17 | P3-auth / B09h | Identități HTTP, seif și refresh | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G03a; G-AUTH-HTTP și G-EFFECT HTTP | [Plan §10](../Omnis_Implementation_Plan.md) |
| SL18 | P3b / B09a–B09b | Browser/SPA și auth asistat | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B09h; poate avansa paralel cu prima BOLA, G03b | [Plan §10](../Omnis_Implementation_Plan.md) |
| SL19 | P5a / B10a | Inventar de suprafețe din discovery/import | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După P3-auth; capturi/provenance/Katana | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL20 | P5a / B10b | Normalizare, threat model și coverage | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B10a; observed/inferred/gaps distincte | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL21 | P5a / B11 | Primul pachet executabil BOLA | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După inventar; eval/publicare cu B12, nu simplul import SKILL.md | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL22 | P6a / B12 | Validator independent și calificarea probelor | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Cu B11, după broker/auth; vulnerable/fixed/benign și replay nou | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL23 | P6a / B13a apoi B13b | Findings, deduplicare și review operator | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După B12; confirmarea tehnică este separată de Accept/Hold | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL24 | P6a / B13c apoi B13d | Raport imutabil și retest real | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După findings; închide prima BOLA cap-coadă G05a/G06a | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL25 | P-LOOP / B18a apoi B18a.r | Continuări, STEER și review/rework metodologic | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G06a; G-LOOP/G-METHOD, fără dublu consum | [Plan §14](../Omnis_Implementation_Plan.md) |
| SL26 | P-FOCUS / B10f→B12f→B13f | Mod focused cu același motor și buget | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G-LOOP; G-FOCUS și raport/trace distinct | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL27 | P-WORDLIST / B10d | Wordlist din capturi și baselines | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După prima BOLA; CORE înainte B15, gate integrat după consumator | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL28 | P-RESEARCH / B10c | Research bounded și retur în frontieră | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G-LOOP; early data/egress, nu prerequisite BOLA | [Plan §11](../Omnis_Implementation_Plan.md) |
| SL29 | P5b / B15j.1/B15d/B15n | Recon extins, JS, discovery și Nuclei | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După browser/wordlist/primul finding; G05b/G-JS/G-WORDLIST | [Plan §13](../Omnis_Implementation_Plan.md) |
| SL30 | P6b / B16 și B17 | XSS reflectat și traversal-canary | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După browser/recon; oracole și controale proprii G06b | [Plan §13](../Omnis_Implementation_Plan.md) |
| SL31 | P-PATH / B18c | Attack paths probate fără dublarea findings | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După G-LOOP/G06b; G-PATH și vizual separat | [Plan §14](../Omnis_Implementation_Plan.md) |
| SL32 | P-JEV / B06j→B14j | Jev OFF/SHADOW/ADVISORY, fără autoritate de verdict | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Inert din P2, închidere după G-LOOP; acord separat pentru live | [Plan §7/§12](../Omnis_Implementation_Plan.md) |
| SL33 | P4b / B14a→B14b | Settings complet, editor și publicare versionată | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După P4a, paralel; ambii provideri, G04b/MODULE/REVISION | [Plan §12](../Omnis_Implementation_Plan.md) |
| SL34 | P-MAINT / B14c.1→B14c.2 | Maintenance și improvement pentru run-uri viitoare | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După P4b/G-LOOP; core safe înainte worker, publisher separat | [Plan §12](../Omnis_Implementation_Plan.md) |
| SL35 | P7 / B18b și B19 | Fault injection/recovery integrat cu mai mulți copii | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După ramurile MVP; G07/G-HERMES-BOUND, fără amânarea nucleelor safety | [Plan §14](../Omnis_Implementation_Plan.md) |
| SL36 | P8 / B20→B21→B22 | Evaluare held-out, backup/restore și release MVP | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | După P7/P4b; G08/G-DATA/G-OPS și toate promisiunile probate | [Plan §15](../Omnis_Implementation_Plan.md) |

## Milestone-uri și gates globale

| Milestone / gate | Stare de închidere | De ce / ce lipsește |
|---|---|---|
| M0 / G00 | DESCHIS | SL03/SL04 și probele complete L01–L05-control/L08-core, inclusiv limitele de rețea; start headless nu le înlocuiește |
| Integrare nativă / G02-inert → P4a → G-MODEL/G-DATA-EARLY/G02-live/G04a | NOT-RUN | Runtime-host, binding, dispatch și acord explicit cont/model/buget |
| G01 / experiența web reală | NOT-RUN | B02/B03/B04; nu bootstrapul P0.3 |
| M1 / prima BOLA / G-AUTH-HTTP + G05a/G06a | NOT-RUN | Discovery, investigator, validator, review, raport și retest reale; un provider este suficient |
| M2 / MVP coerent | NOT-RUN | M1 plus browser/G03b/G-EFFECT, recon/G05b/G06b, G-LOOP/FOCUS/PATH/JEV/SKILL/METHOD/JS și G04b |
| Ramuri promise ale MVP | NOT-RUN | G-MODULE/REVISION/TOOLS/RESEARCH, G-WORDLIST-CORE apoi integrat, G-IMPROVE/HERMES-BOUND-CORE apoi complet; opționale într-un run, nu opționale în certificarea promisiunii |
| Release / G07/G08/G-DATA/G-OPS | NOT-RUN | Recovery integrat, evaluare preregistrată, backup/restore/retention și demonstrație din release |
| CI remote | NOT-RUN | Nicio rulare remote nouă pretinsă și niciun push implicit |

**Firul critic:** P0 complet/G00 → B02/P1-data → P1-web și P2-inert → P4a-minim → P2-live → HTTP/broker/auth → prima BOLA cu raport/retest. Browserul și ramurile MVP se dezvoltă conform DAG-ului, fără a cere editor/Jev/research înainte de primul finding. Nucleele safety intră înaintea primului consumator, nu sunt amânate până la P7.

## Post-MVP / extensii explicite

Aceste valuri nu sunt deja implementate și nu înseamnă paritate Strix. Plan §15 este autoritatea subfamiliilor, oracolelor și gates; E3 este profil de informație, nu o familie suplimentară.

| ID | Val canonic | Rezultat urmărit | Cod | Probe | Review | Rest / dependență / limită | Sursă |
|---|---|---|---|---|---|---|---|
| E1 | Breadth inițial | Disclosure/config, auth/session/JWT, BFLA/mass assignment, SQLi | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Oracle/vulnerable/fixed/benign per subfamilie; nu import executabil automat | [Plan §15](../Omnis_Implementation_Plan.md) |
| E2 | Browser/business și analiză extinsă | CSRF, DOM/stored XSS, SSRF/XXE, business/race; history și JS debugger | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | G-HISTORY/G-JS-DEBUG și protocol/replay/cleanup distincte; blind XSS ține de E4 | [Plan §15](../Omnis_Implementation_Plan.md) |
| E3 | Source-aware | Snapshot revizuit, source-to-sink, remediere/retest | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | G-SOURCE, zero exec la import; source-supported nu este runtime-confirmed | [Plan §15](../Omnis_Implementation_Plan.md) |
| E4 | Extensii de protocol/familie/deployment | Workers, GraphQL/WS/gRPC/OAST, upload/deserializare/RCE, echipe | NOT_IMPLEMENTED | NOT_RUN | NOT_REVIEWED | Gate nou și autorizare explicită; nu drepturi din import sau acces host implicit | [Plan §15](../Omnis_Implementation_Plan.md) |

**B21m / research periodic și cron:** ulterior/opțional, neimplementat; nu blochează MVP-ul manual. Activarea lui cere contractul/gate-ul propriu și acord, nu instalare implicită de cron prin acest skill.

**METHODOLOGY_ONLY / EXECUTION_UNSCHEDULED:** `agentic_system_security`, `argument_injection`, `browser_security`, `header_injection`, `http_request_smuggling`, `llm_prompt_injection`, `nosql_injection`, `open_redirect`, `prototype_pollution`, `semantic_confusion`, `ssti`, `subdomain_takeover`, `weak_password_detection`. Sunt surse metodologice cu execuție neprogramată, nu funcții pierdute din hartă și nici E1 implicit. În baseline, cele 75 ghiduri sunt source-reviewed/not-imported și execution_certified=false; [inventarul](omnis-upgrade-review.inventory.json) și planul §15 păstrează dispoziția exactă.

**Trasabilitate transversală:** RF descrie fluxul operațional, SK01–SK10 patternul de authoring/livrare, iar HF01–HF10/NS01–NS19 amendamentele canonice. Nu le numărăm ca implementări sau faze suplimentare: consumatorii lor sunt SL/B în [plan §2.1/§4.4/§17](../Omnis_Implementation_Plan.md). Skill-urile din `.hermes/skills/` sunt pentru dezvoltare, nu catalogul executabil de pentest.

## Întreținere și review

La predare, verifică Git real și dovezile relevante; actualizează numai rândurile afectate, rezumatul global și următoarea felie. Păstrează eșecurile în registrul probei. Pentru fiecare modificare de verdict înregistrează în registru/commit: ID, revizie, scope, comandă/exit, review și adjudecare, limite și resurse/cleanup. Un reviewer/subagent nu își aprobă singur integrarea.

O lectură de orientare nu cere scrieri sau commit gol. Dacă planul adaugă/remapează SL/E, testele de documentare cer reconcilierea hărții; dacă se schimbă numai codul sau dovada, agentul trebuie să compare scope-ul — testele textuale nu pot atesta adevărul unui PASS. Nu actualiza automat un verdict din mesajul unui commit sau dintr-o notificare întârziată. O constatare nouă reproductibilă rămâne nouă chiar dacă raportul folosește un ID vechi; comparația se face pe snapshot și scenariu.
