**Recomand adoptarea modului de lucru proporțional deja descris în team-slice, cu clarificările de mai jos. Echipa fixă „1 orchestrator + 2 devs + 2 reviews + 1 live QA” nu este justificată ca default.** Nu lipsește încă un rol sau manual; lipsesc alinierea autorității și aplicarea consecventă a regulilor existente.

Direcția API-key-only este consemnată deja în analiza migrării de la HEAD: fără Hermes runtime/Codex subscription în produs, cu OpenRouter/OrcaRouter și SDK candidat; Hermes/Codex rămân unelte de dezvoltare. Analiza pregătește amendarea canonului, fără să autorizeze singură implementarea.

**1. Acoperire exactă**

Am citit integral **59/59 de căi distincte** din inventarul înghețat: 53 assets de proiect și șase instrucțiuni suplimentare. Toate cele 59 de SHA-256 corespund inventarului. Ieșirile inițial trunchiate au fost completate prin citiri separate.

```text
.hermes/skills/omnis-accessibility/SKILL.md
.hermes/skills/omnis-accessibility/references/LICENSE.txt
.hermes/skills/omnis-accessibility/references/upstream.json
.hermes/skills/omnis-accessibility/references/upstream.md
.hermes/skills/omnis-anti-slop/SKILL.md
.hermes/skills/omnis-api-data/SKILL.md
.hermes/skills/omnis-chisel/SKILL.md
.hermes/skills/omnis-delivery/SKILL.md
.hermes/skills/omnis-delivery/templates/task.md
.hermes/skills/omnis-delivery/templates/team-slice.md
.hermes/skills/omnis-frontend-performance/SKILL.md
.hermes/skills/omnis-frontend-performance/references/LICENSE.txt
.hermes/skills/omnis-frontend-performance/references/upstream.json
.hermes/skills/omnis-frontend-performance/references/upstream.md
.hermes/skills/omnis-frontend/SKILL.md
.hermes/skills/omnis-frontend/references/LICENSE.txt
.hermes/skills/omnis-frontend/references/upstream.json
.hermes/skills/omnis-frontend/references/upstream.md
.hermes/skills/omnis-hermes-runtime/SKILL.md
.hermes/skills/omnis-project-status/SKILL.md
.hermes/skills/omnis-project-status/templates/handoff.md
.hermes/skills/omnis-release-ops/SKILL.md
.hermes/skills/omnis-release-ops/references/startup-failure-boundaries.md
.hermes/skills/omnis-reticle/SKILL.md
.hermes/skills/omnis-review-qa/SKILL.md
.hermes/skills/omnis-review-qa/references/private-nss-audit.md
.hermes/skills/omnis-safety-evaluation/SKILL.md
profiles/recon-mapping-contract.yaml
profiles/records-mapping-contract.yaml
skills/bug-bounty-triage/LICENSE
skills/bug-bounty-triage/NOTICE.md
skills/bug-bounty-triage/README.upstream.md
skills/bug-bounty-triage/SKILL.md
skills/bug-bounty-triage/provenance.json
skills/recon-mapping-contract/NOTICE.md
skills/recon-mapping-contract/SKILL.md
skills/recon-mapping-contract/omnis.yaml
skills/recon-mapping-contract/references/methodology.md
skills/recon-mapping-contract/templates/procedures/map-capture.yaml
skills/recon-mapping-contract/templates/schemas/capture.schema.json
skills/recon-mapping-contract/templates/schemas/empty.schema.json
skills/recon-mapping-contract/templates/schemas/operations.schema.json
skills/recon-mapping-contract/templates/schemas/records.schema.json
skills/recon-mapping-contract/templates/schemas/surface_map.schema.json
skills/records-mapping-contract/NOTICE.md
skills/records-mapping-contract/SKILL.md
skills/records-mapping-contract/omnis.yaml
skills/records-mapping-contract/references/methodology.md
skills/records-mapping-contract/templates/procedures/map-records.yaml
skills/records-mapping-contract/templates/schemas/empty.schema.json
skills/records-mapping-contract/templates/schemas/operations.schema.json
skills/records-mapping-contract/templates/schemas/records.schema.json
skills/records-mapping-contract/templates/schemas/surface_map.schema.json
/home/kali/OmnisAI/AGENTS.md
/home/kali/OmnisAI/CONTRIBUTING.md
/home/kali/.hermes/SOUL.md
/home/kali/.hermes/skills/software-development/development-toolchain-integration/SKILL.md
/home/kali/.hermes/skills/software-development/agentic-security-platform-design/SKILL.md
/home/kali/.hermes/skills/autonomous-ai-agents/hermes-agent/SKILL.md
```

Suplimentar, am citit integral `README.md` și `documents/verification/api-key-runtime-migration-analysis.md`; numai secțiunile relevante din arhitectură, plan, stack, UI/UX și implementation-status. Nu revendic lectura integrală a acestor cinci documente normative și nici a referințelor globale neincluse în inventar.

Scope-ul global este limitat justificat la cele trei skills indicate: integrarea uneltelor, arhitectura platformei și utilizarea Hermes. Inventarierea email/media sau a altor profiluri nu ar schimba decizia. Nu am citit originalul HTML untracked, credentiale, `.env`, auth ori loguri private.

**2. Dispoziția fișierelor**

În tabel, `D/` înseamnă `.hermes/skills/`; fiecare locator de skill indică `SKILL.md`. EDIT reprezintă recomandare, nu modificare aplicată.

| Fișier / locator | Dispoziție | Motiv și edit exact recomandat | Riscul unei tăieri greșite |
|---|---|---|---|
| `D/omnis-accessibility`, Procedure 3/7 și ultimul bullet | **EDIT** | Păstrează semantica, focus, Stop și verificarea parcursului. Mută rețeta particulară sticky-header/back-link în referință. Adaugă: „Selectează scenariile după widgetul/calea afectată; nu executa întreaga listă pentru fiecare editare.” | Pierderea regresiilor reale de focus sau ascunderea Stop. |
| `D/omnis-anti-slop`, Procedure 1–3 | **EDIT** | Păstrează politica executabilă. Înlocuiește instalarea implicită cu „Instalează numai dacă mediul fixat lipsește; pentru produs verifică fișierele TS afectate; smoke-ul uneltei se repetă când se schimbă unealta/configurația.” | Lint neexecutat sau presupunerea că lintul dovedește siguranța runtime. |
| `D/omnis-api-data`, Prerequisites și Pitfalls | **EDIT / MOVE_TO_REFERENCE** | Înlocuiește separarea permanentă API/Hermes cu API/runtime/executor. Păstrează tranzacții, validare, migrații, idempotency și readback în corp; mută rețetele incidentelor, inclusiv native/composer și clock-wrapper, în referințe tematice. | Ruperea readerilor istorici, fingerprints sau protecțiilor DB dacă lecțiile sunt șterse fără înlocuire. |
| `D/omnis-chisel`, Current prerequisite | **QUARANTINE** | Păstrează NO-GO și procedura exclusiv pentru reevaluare cerută explicit. Text propus: „Nu se încarcă în dezvoltarea obișnuită; indisponibilitatea Chisel nu blochează uneltele native.” | Activarea accidentală a adaptorului ale cărui controale au eșuat. |
| `D/omnis-delivery`, Procedure 2/6/9 și Pitfalls | **EDIT** | Trimite politica de echipă la team-slice și admiterea muncii la CONTRIBUTING. Înlocuiește „available Hermes tools” cu „uneltele disponibile sesiunii”. Mută incidentele P0/pair/transfer în referințe. | Eliminarea TDD, Git granular sau a limitei de două cicluri. |
| `D/omnis-frontend-performance`, When to Use | **KEEP** | Este deja condiționat de măsurare și nevoie reală. Păstrează „Do not preemptively optimize an unimplemented UI”; fără extindere. | Optimizări speculative sau eliminarea cleanupului pentru performanță. |
| `D/omnis-frontend`, Procedure 2 și Pitfalls | **EDIT / MOVE_TO_REFERENCE** | Înlocuiește aprobarea vizuală universală înaintea implementării cu „Reutilizează baseline-ul acceptat; cere aprobare pentru direcție vizuală schimbată.” Mută cazurile hydration, capturi stitched și receipt recovery în referințe tematice. | Redeschiderea repetată a designului sau pierderea regresiilor funcționale. |
| `D/omnis-hermes-runtime`, When to Use, linia 16 | **RETIRE din rutarea produsului / MOVE_TO_REFERENCE** | Elimină obligația activă „Do not replace Hermes with another agent framework”. Marchează întregul skill „LEGACY: numai diagnostic/readback al executorului istoric; nu cerință pentru runtime-ul API-key-only”. | Ștergerea prematură a contractelor necesare interpretării datelor vechi. |
| `D/omnis-project-status`, Procedure 1–8 | **EDIT** | ORIENT minim: Git, CURRENT și rândurile afectate. Log/worktrees/refs numai pentru conflict concret. Verificările documentare se aplică după editări documentare, nu după orientare read-only. | Status optimist fără dovezi dacă se elimină separarea cod/probe/review. |
| `D/omnis-release-ops`, Procedure și Pitfalls | **EDIT / MOVE_TO_REFERENCE** | Generalizează runtime-ul și păstrează locks, artefact instalat, restore și cleanup. Mută incidentele Docker/uv/pidfd/startup în rețete încărcate după frontieră. | Confundarea buildului cu livrarea sau pierderea protecției datelor. |
| `D/omnis-reticle`, When to Use | **EDIT** | Înlocuiește „or rerun the synthetic acceptance smoke” cu „smoke numai la schimbarea integrării/uneltei ori defect demonstrat”. Păstrează TOOLING_ONLY și NOT_INTEGRATED. | Transformarea unui smoke sintetic în acceptare de produs. |
| `D/omnis-review-qa`, Procedure 3/8 și Pitfalls | **EDIT / MOVE_TO_REFERENCE** | Politica echipei vine din team-slice. Clarifică „commit candidat verificat înainte de review; acceptare după review/QA”. Mută incidentele CDP, NSS, PG, IPC și packaging în referințe indexate. | Slăbirea independenței, închiderea findings printr-o listă nouă goală sau pierderea cleanupului. |
| `D/omnis-safety-evaluation`, Procedure 1–8 | **KEEP** | Frontierele sunt utile și runtime-neutre. Păstrează scope, sink, auth, DATA, controale și replay; nu activa întregul protocol înaintea consumatorului corespunzător. | Reducerea siguranței pentru a accelera prima demonstrație. |
| `skills/bug-bounty-triage/SKILL.md`, liniile 47–57, 314/317 | **QUARANTINE** | Păstrează originalul byte-exact, neactiv. Viitoarea adaptare trebuie să înlocuiască autoritatea sursei și „never redact” cu politica Omnis de date/proveniență și să elimine instalările/conturile implicite. | Expunerea secretelor, acceptarea raportului ca adevăr sau execuție externă neadmisă. |
| `skills/recon-mapping-contract/SKILL.md`, ultima secțiune | **KEEP istoric / EDIT numai versiune nouă** | Nu este recon activ: transformă metadata sintetică. În versiunea viitoare: „Starea publicării este citită din catalogul persistent; sursa nu certifică publicarea.” | Rescrierea bytes/pinurilor istorice sau promovarea CONTRACT în SECURITY. |
| `skills/records-mapping-contract/SKILL.md`, Sources | **KEEP istoric / EDIT numai versiune nouă** | Păstrează PURE și inputul Ref. Pentru noul executor, compatibilitate runtime/adaptor versionată, fără `hermes_revision` obligatoriu. | Acceptarea fără requalificare a pachetului modificat. |
| `AGENTS.md`, Autoritate și Implementare/review | **EDIT** | Corectează starea vizuală/implementare depășită; separă explicit dev tooling de produs; atribuie remedierea dezvoltatorului desemnat, reproducerea/adjudecarea părintelui. | Ocolirea protecției sau interpretarea direcției aprobate ca autorizație live. |
| `CONTRIBUTING.md`, echipă/product-first/status | **EDIT** | Păstrează admiterea muncii drept sursă unică. Înlocuiește politica echipei duplicată cu pointer la team-slice; elimină matricea globală obligatorie la orice răspuns în favoarea deltei relevante. | Tăierea regulilor utile împreună cu repetițiile. |
| `/home/kali/.hermes/SOUL.md`, liniile 3–11 | **EDIT propus, protejat** | Păstrează vocea și respectarea mandatului; mută procedura detaliată în workflow, iar paragraful Omnis de la linia 11 în autoritatea repo-ului. Nu aplica aici. | Contaminarea altor proiecte sau pierderea regulii Git dacă nu există întâi în AGENTS. |
| Global `development-toolchain-integration`, §3–9 | **EDIT / MOVE_TO_REFERENCE** | Păstrează workflow generic. Mută pasajele „this user”, Omnis runner, Codex/subscription și incidentele concrete în proiect/referințe; păstrează numai pointere tematice. | Pierderea distincției între autoritate de dezvoltare și efecte de produs. |
| Global `agentic-security-platform-design`, Procedure 2/4, Pitfalls | **EDIT** | „Load hermes-agent” devine „Încarcă documentația runtime-ului ales; Hermes numai dacă face parte din scope”. Păstrează separarea model/autoritate și evaluarea reală. | Impunerea din nou a Hermes sau înlocuirea nejustificată a altui runtime ales. |
| Global `hermes-agent` | **KEEP pentru dezvoltare** | Nu este autoritate asupra produsului Omnis. Nu îi activa instalarea, `-w`, cron sau proxy prin simpla citire; prioritate contractului repo-ului. | Ștergerea dev toolingului util sau folosirea OAuth/proxy drept soluție de produs. |

Dispozițiile suportului citit:

- **KEEP pasiv:** cele trei seturi `references/LICENSE.txt`, `upstream.json`, `upstream.md`. Licențele și provenance se păstrează; regulile Tailwind/Motion/AlertDialog din upstream nu devin instrucțiuni active. Adaptarea locală are deja excepții corecte pentru Stop și stack.
- **KEEP ca referințe condiționale:** `startup-failure-boundaries.md` și `private-nss-audit.md`. Nu sunt preflight universal și nu sunt autorizații de execuție.
- **EDIT:** `templates/task.md`, `team-slice.md`, `templates/handoff.md`, conform propunerilor de mai jos.
- **KEEP:** NOTICE/provenance/licența triage. Formulările despre worktree/no-commit sunt istoricul importului, nu interdicții perpetue asupra repo-ului; NOTICE poate delimita explicit acest lucru fără rescrierea provenienței.
- **KEEP:** ambele profile de proiect, manifests, proceduri, methodology și toate schemele CONTRACT. Sunt date/contracte versionate, nu profiluri personale și nu instrucțiuni globale. Compatibilitatea Hermes se adaptează într-o versiune nouă, cu consumer; nu prin editarea releases istorice.

**3. Opt constatări de proces**

1. **Canonul încă poate readmite produsul respins.** Arhitectura A04/§5 impune Hermes nativ și patch minimal; planul §7–8/§12 păstrează Hermes/Codex OAuth; skillul runtime interzice înlocuirea. Analiza migrării §6 identifică deja amendamentele. Următorul pas este T0 din propunerea existentă, fără încă o analiză generală sau implementare anticipată.

2. **AGENTS are stare veche cu efect operațional.** Spune că designul și structura așteaptă aprobarea; README/UI consemnează aprobările. Agentul poate cere repetat aceeași permisiune sau reveni la prototip. Corecția trebuie făcută explicit în fișierul protejat, fără sursă alternativă.

3. **Product-first este deja prezent.** CONTRIBUTING liniile 50–71, delivery și team-slice cer consumer real, admiterea verificării, reutilizarea dovezii și limita de două cicluri. Controlul util este ca orchestratorul să refuze următoarea comandă fără decizie identificabilă în taskul existent; adăugarea aceleiași reguli în SOUL și încă trei skills nu o aplică automat.

4. **Ownerul remedierii este ambiguu.** AGENTS spune „părintele … remediază”; team-slice și SOUL atribuie fixes dezvoltatorului. Părintele trebuie să reproducă/adjudice, apoi să trimită fixul ownerului. Dacă preia autoratul, schimbarea se declară, nu apare un al doilea autor ascuns.

5. **Commitul și acceptarea sunt confundate în formulări.** Team-slice Closure cere commit înainte de review; CONTRIBUTING enumeră review înainte de commit, iar review-qa vorbește despre commitul feliei acceptate. Soluția: commit candidat verificat, review/QA pe identitate exactă, acceptare ulterioară; fără commit gol de aprobare.

6. **Regula CURRENT este bună, documentele o contrazic.** Status skill cere CURRENT și rândurile afectate, istoric numai pentru fapt lipsă/conflict. README/status/plan păstrează multe CURRENT/AICI și continuări diferite. README mai cere și audit/handoff suplimentare la reluare. Un singur CURRENT trebuie să indice mandatul curent; checkpointurile rămân istorice, fără coadă executabilă.

7. **Corpurile active au devenit colecții de incidente.** API-data, review-qa, release-ops și workflow global amestecă principii cu rețete foarte specifice. Nu toate sunt încărcate la fiecare task: repo-ul cere selecție la nevoie, iar upstream-urile sunt pasive. Totuși, selectarea unui skill mare aduce toate incidentele lui. Reducerea se justifică prin relevanță și decizii, nu printr-o economie de timp dedusă din bytes.

8. **Importul triage necesită carantină, nu curățare cosmetică.** „Evidence authoritative” contrazice chiar cerința lui de reproducere independentă; „never redact” contrazice politica Omnis. NOTICE constată corect problema. Metadata descriptivă NOT_ACTIVATED nu dovedește enforcement; auditul acesta nu a verificat loaderul executabil.

**4. Graph/loop recomandat**

Este un traseu în taskul și registrul existente, fără GraphEngineer, LoopEngineer, serviciu nou sau framework de orchestration.

```text
ORIENT → ADMIT → DEVELOP → FREEZE → REVIEW → REAL_QA → CLOSE
                    ↑                │          │
                    └──── FIX ←──────┴──────────┘
                         │
                   BLOCKED / HOLD
```

| Stare / owner | Intrare și ieșire observabilă |
|---|---|
| **ORIENT — orchestrator** | Git + CURRENT + contract afectat → mandat, diferențe și primul consumer. Istoric numai pentru conflict/fapt lipsă. |
| **ADMIT — orchestrator** | O cerință finită → rezultat, producer/consumer, owner de fișiere, controale, buget și limite. Decizie arhitecturală numai dacă este nerezolvată. |
| **DEVELOP — un dev** | Contract și inputuri reale → RED, schimbare minimă, GREEN și verificări afectate. Helpers rămân prerequisite. |
| **FREEZE — orchestrator** | Livrare dev → integrare exactă, identitate commit/blobs și commit coerent verificat. Nu declară acceptare. |
| **REVIEW — independent** | Același snapshot și criterii → findings concrete și verdict scoped. Două reviews complementare numai pentru frontierele sensibile enumerate. |
| **REAL_QA — nonautor** | Blocante de cod închise + artefact final + preflight fără efecte → parcurs real, control negativ, readback și cleanup. Reviewerul poate face etapa QA separat. |
| **CLOSE — orchestrator** | Dovezi pe bytes curenți → adjudecare, canonical la frontiera integrării/fazei și numai delta factuală de status. |

Bucla de fix este limitată prin **aceeași acceptance row**, nu numărul de sesiuni:

- Finding reprodus → dev desemnat → fix minim → affected checks → commit separat → re-review focalizat → QA afectată.
- O tentativă nouă trebuie să răspundă unei întrebări schimbate prin fix sau diagnostic concret.
- După **două cicluri numai harness fără progres pe cerință**, oprește acea frontieră: WIP/BLOCKED, reproducer restrâns și următoarea acțiune exactă. Nu reseta contorul prin alt nume/sesiune și nu adăuga al treilea verifier.
- Un defect nou de siguranță rămâne blocant. Limita nu îl aprobă și nu permite trecerea pe o felie dependentă.

Configurația implicită este **un orchestrator, un dev, un reviewer independent**, cu QA într-o etapă separată. Dev2 apare numai pentru fișiere/interfețe și criterii independente. Reviewer2 este obligatoriu pentru authority, epoch, concurrency, model dispatch, Stop, efecte/secrete și contracte cross-runtime. „Live QA” înseamnă artefact real afectat; nu implică automat provider/target și nici browser pentru CLI.

**5. Drafturi minime, cu sursă unică**

Text propus pentru AGENTS — **neaplicat**:

> Direcția aprobată a produsului exclude Hermes runtime și Codex subscription/OAuth; Hermes/Codex rămân unelte de dezvoltare. OpenRouter/OrcaRouter folosesc API keys; biblioteca de agenți rămâne candidat până la admiterea sa. Amendarea canonului urmează analiza migrării existentă; aprobarea direcției nu autorizează implementare, chei, buget sau trafic.
>
> Baseline-ul vizual acceptat și structura aplicației sunt cele consemnate în UI/UX §0 și arhitectură. Reaprobarea privește schimbări de direcție, nu fiecare felie funcțională.
>
> Politica de echipă și succesiunea commit/review/QA sunt definite numai în team-slice. Părintele reproduce și adjudecă blocantele; dezvoltatorul desemnat le remediază. Orice transfer de autorat se declară.
>
> Admiterea muncii și limita ciclurilor sunt definite în CONTRIBUTING, „Execuție orientată spre produs”. Skills de dezvoltare specializează aceste reguli, fără să le dubleze sau să impună runtime-ul produsului.

Modificări punctuale:

- **team-slice, Closure:** „Commitul candidat verificat precede reviewul; acceptarea urmează reviewului și QA necesare. Snapshotul poate fi identificat prin commit/blobs; schimbările relevante cer re-review. Modificările exclusiv documentare din afara closure-ului consumat nu invalidează automat aprobarea.”
- **team-slice, Development/QA:** ownerul dev rămâne și owner de fix; părintele reproduce/adjudice/integră. QA are nonautor, etapă și contract propriu, fără agent suplimentar obligatoriu.
- **task.md:** păstrează câmpurile actuale; grupează preflight/QA/cleanup, fără rubrici duplicate. Adaugă în aceeași acceptance row: „ultimul progres de produs; cicluri harness-only 0/1/2; următoarea decizie”. Nu genera raport separat pentru completare.
- **CLOSE/handoff:** înlocuiește obligația matricei globale de 6–8 rânduri pentru orice task cu „rezultat, snapshot, dovezi/review, blocker și pas următor; matrice globală la milestone, schimbare globală sau cerere”. Read-only nu declanșează docs tests ori editări.
- **README/status/plan §19:** înlocuiește CURRENT în loc și citează registrul; istoricul nu mai păstrează blocuri copy-ready active. Nu construi validator semantic al statusurilor.
- **Skills:** corpurile păstrează procedura domeniului; principii de echipă → team-slice, admiterea muncii → CONTRIBUTING, Git/autoritate → AGENTS, status → project-status. Referințele păstrează rețetele incidentelor.
- **SOUL:** păstrează identitatea și tonul; eliminarea detaliilor Omnis este numai propusă. Nu am modificat fișierul protejat.

Aceste edituri se integrează în amendamentul T0 deja propus; nu creează un plan concurent.

**6. Ce se retrage și ce se păstrează**

Se retrag din **instrucțiunile active** obligațiile Hermes-native/Codex-subscription, mandatele vechi de reluare, recertificarea neschimbată și smoke-urile ceremoniale. Se mută în referințe incidentele rezolvate și rețetele de platformă.

Se păstrează Git, licențele, notices/provenance, findings și FAIL/UNCERTAIN, readerii și contractele istorice necesare, dev toolingul și siguranța. Schemele/manifests nu se șterg în această curățare: versiuni noi cu primul consumer; retragerea codului/distribuției numai după înlocuire și dovadă de readback. Datele personale și instalările existente nu sunt material de curățat.

**Verificare și verdict:** Git început/final identic, HEAD `59253358147a427b66471b5b6f13c5e5690c58ea`; diff tracked și staged goale, exit 0. Singurul untracked rămâne `documents/Omnis_Notite_Originale.html`, necitit. Zero scrieri/commituri/agenți; teste, builduri, servicii, provider și target **NOT_RUN**. O încercare de citire prin heredoc a fost refuzată de filesystemul read-only; lectura a continuat cu `python -c`.

**ADOPTĂ modul proporțional și bucla de mai sus; retrage echipa fixă de șase roluri ca default.** Acesta este verdict asupra modului de lucru propus, fără acceptare de produs sau certificare a migrării.