# Omnis + Hermes — arhitectură propusă și plan MVP

> **Revizie local-first pentru discuție:** [MVP local și contracte de integrare](Omnis_Hermes_Local_MVP_Integration_Proposal.md). Include alegerile utilizatorului privind laboratorul, autentificarea și approvals, plus auditul REST/JSON-RPC/Settings. Documentul de mai jos rămâne istoricul propunerii inițiale, nu backlogul aprobat.

- **Statut:** propunere pentru discuție, **neaprobată**; nu autorizează implementarea sau testarea vreunei ținte.
- **Data:** 2026-09-24
- **Domeniu:** evaluări Web/API autorizate, inițial pe laborator și aplicații controlate; acces pentru echipa autentificată, cu posibilă mutare ulterioară pe VPS.
- **Bază:** conversația despre Omnis/Hermes; `Omnis_Reference_Architecture_v7.md` este o sursă de idei, nu un set de decizii obligatorii. Nota de la începutul acelui document trimite la fișiere V0 care nu se află momentan în acest workspace. În această propunere nu presupunem că v7 este backlogul curent.

## 1. Decizia de produs, în două fraze

**Omnis** este aplicația de lucru a echipei: configurează engagementuri, RoE, scope, identități de test, modele permise, bugete, aprobări, graf, execuție, dovezi, findings și rapoarte. **Hermes** este motorul cognitiv și de tool-calling: furnizori de modele, skill-uri, sesiuni, specialiști condiționali și raționament adaptiv. Omnis nu rescrie aceste capabilități, dar păstrează controlul asupra efectelor externe și adevărului din raport.

Nu construim un „chat cu un scanner”, dar nici un swarm permanent sau un framework nou de agenți. Valoarea AI este să interpreteze aplicația, să formeze și să testeze ipoteze, să urmărească semnale neașteptate și să reprioritizeze investigația. Codul determinist se ocupă de permisiuni, persistență, limite, identități, dovada obiectivă și oprire.

### Înăuntrul / în afara primei versiuni

| MVP inclus | Amânat până la dovezi de utilitate și siguranță |
|---|---|
| Web/API autorizat, un singur grup intern de utilizatori; laborator și aplicații deținute/controlate; pre-auth și un flux post-auth de test | Înscriere publică pentru scanarea oricărui URL, multi-tenant pentru clienți ostili, infrastructură/AD/cloud, DoS, atacuri asupra parolelor |
| O sesiune coordonator per engagement, workeri focalizați la cerere, graf per engagement, un flux complet candidat→verificare→raport | Zeci/sute de agenți permanenți, fine-tuning, auto-promovarea skill-urilor, memorie externă care absoarbe tot traficul |
| Configurare engagement, model/rol, conturi de test prin referințe securizate, dashboard live, pauză/stop, dovezi | Expunerea dashboardului/API-ului Hermes direct către utilizatori sau acces shell nerestricționat pentru agenții de pentest |

## 2. Ce am verificat din exterior — fără a confunda reclama cu dovada

Materialele furnizorilor descriu **produsele lor**, nu dau acces la prompturi, contracte de sesiune, rate reale de recall sau toate controalele interne. Le folosim ca semnale de design, nu ca specificație sau evaluare independentă.

| Sursă publică | Semnal relevant | Decizia Omnis | Ce NU copiem automat |
|---|---|---|---|
| XBOW: hartă vie, coordonator, workeri scurți și validatori independenți.[41] | Separarea explorării de dovadă și actualizarea hărții după observații | **Adaptăm:** graf, coordonator și verificator separat | Numărul mare de agenți, „zero false positives” sau orice presupunere despre implementarea internă a sesiunilor |
| Aikido: agenți care reverifică findinguri, dovezi, testare de aplicații/API și retest.[42] | Testarea realității unei observații înainte de raport | **Adoptăm principiul:** verificare prin controale și replay; **amânăm** retest continuu până la prima raportare sigură | Promisiuni de zero false pozitive sau echivalarea unui PoC generat cu adevăr demonstrat |
| Ethiack: suprafață actualizată și dovadă de exploatabilitate.[43] | Descoperirea și verificarea trebuie legate în aceeași stare de campanie | **Adaptăm:** noi noduri/suprafețe redeschid prioritizarea | Testare permanentă pe orice țintă fără autorizație/revizie de scope |
| Cantina: registru comun al mediului, politici pentru agenți, dovezi, remediere și retest; triere umană a rapoartelor bounty.[44][45][46] | Context comun + proveniență + om acolo unde verdictul este ambiguu | **Adoptăm:** case graph per engagement, verificare și review; **amânăm** autofix și ecosistemul SecOps | „Un creier” fără granițe între clienți ori un agent care devine autoritate asupra findingului |
| BugBunny: reutilizarea scope-ului/excluderilor și escaladare către un manager.[47] | RoE și istoricul trebuie să fie vizibile în engagement | **Adoptăm:** scope revisionat și aprobări explicite | Memorie globală care amestecă dovezi între engagementuri |

PentestGPT separă analiza, generarea și parsarea și folosește contexte noi pentru subtaskuri; benchmarkul său nu include ținte benigne pentru măsurarea falselor pozitive.[26] AutoPenBench raportează 21% succes autonom față de 64% asistat în setul propriu de 33 de sarcini; „real-world” include reproduceri CVE în containere, nu un eșantion de aplicații necunoscute.[27] CAI oferă semnale despre handoff și human-in-the-loop, dar rezultatele sale pe provocări nu dovedesc acoperirea aplicațiilor Web/API reale sau că topologia sa ar fi optimă pentru Omnis.[28]

**Concluzie de cercetare:** comparăm empiric trei regimuri de context pe aceleași laboratoare și același buget: (A) o sesiune lungă, (B) sesiuni proaspete per task cu context din graf, (C) coordonator continuu + workeri proaspeți. Varianta C este ipoteza inițială, nu decizie ireversibilă.

CyberSecEval 3 e util ca exemplu de evaluare a riscurilor și capabilităților modelelor, **nu** drept scor al calității unui produs de pentest. Pentru Omnis contează evaluarea fluxului complet pe ținte autorizate, inclusiv controale negative.[29]

## 3. Reutilizare Hermes versus lucru specific Omnis

Inventarul documentației Hermes folosit la cercetare este catalogul oficial, completat prin paginile relevante de mai jos; un contract observat în documentație rămâne de confirmat pe instalarea locală.[1]

Documentația Hermes descrie `POST /api/sessions` pentru crearea unei sesiuni și API-ul `/v1/runs` pentru turn-uri cu stare, evenimente SSE, stop și approval.[2] **Numai un `session_id` al unei sesiuni existente** reîncarcă transcriptul activ când nu se furnizează explicit alt istoric; un ID arbitrar în payload servește la corelare, nu garantează continuitate.[2][48]

Hermes oferă skill-uri încărcate la cerere și pluginuri cu tool-uri proprii.[7][8]

Are și subagenți pentru delegare și un board Kanban pentru profiluri.[9][10] Profilurile separă configurația și memoria, dar **nu** sunt sandboxuri OS/rețea.[4]

| Cerință | Refolosim | Construim/decidem în Omnis | Verificare înainte de cod final |
|---|---|---|---|
| Modele/providere, aliases, rotație/fallback | Configurație și rutare Hermes.[36][37][38] | Policy per rol/engagement: modele admise, cost, regiune și nivel de confidențialitate | Precedența `/model` din sesiune > rută/alias > model/provider cerut; statusul consemnează modelul efectiv după fallback.[2] |
| Sesiunea coordonatorului | Sesiune creată prin API, apoi transcript continuat prin `session_id` la `/v1/runs`.[2] | Registru `engagement → sesiune existentă/activă`, cu succesor/checkpoint la rotație; context pack din DB | Reconnect, turn-uri simultane, restart, compresie, schimbări de scope |
| Workeri AI | Subagenți Hermes pentru sarcini scurte; rulări separate pentru task-uri gestionate de Omnis.[9] | Task-uri, dependențe, bugete, identități, lease și handoff-uri structurate | Oprirea unui copil nu lasă acțiuni neînregistrate; nu presupunem că se reia după crash |
| Skill-uri/tehnici | `SKILL.md` Hermes, încărcare la cerere.[7] | Catalogul Omnis de aplicabilitate, dovezi/controale, ceiling de risc, versiuni și evaluări | Skill-ul nu poate lărgi scope-ul sau instala capabilități neaprobate |
| Tool-uri HTTP/browser/scannere | Pluginuri Hermes pentru scheme și handlers.[8] | Adaptoare tipizate + policy/action gateway + execuție controlată; niciun efect direct prin terminal/browser brut | Redirect, DNS, cereri copil, rate, identități și stop chiar la o pagină ostilă |
| Graph și memorie | Sesiuni și eventual căutare ca instrumente auxiliare | Graph canonic per engagement și context pack versionat | Fără scurgeri între engagementuri ori conversii de ipoteze în „fapte” |
| Interfață administrativă Hermes | Dashboardul are configurare și API de management al profilurilor/config/cheilor/skill-urilor.[11] | Fațadă Owner-only în Omnis; datele/cheile de administrare nu ajung la operatorii obișnuiți | Contractele management API și fluxurile OAuth/API-key testate live; dashboardul Hermes rămâne privat |

`delegate_task` este util pentru fan-out rapid, dar un copil în execuție nu este reluat după pierderea procesului.[9] Kanban este o coadă durabilă, nu baza de date de vulnerabilități sau o graniță multi-tenant: `tenant` este un filtru soft, iar un board separat tot nu este izolare OS.[10]

Un `/goal` sau `/loop` într-o sesiune este util la investigații limitate, dar nu înlocuiește schedulerul și reconcilierea engagementului.[12][13] Pentru MVP alegem **task-uri Omnis persistente + apeluri Hermes**, evaluând Kanban într-un spike numai dacă reduce real codul fără să dubleze starea.

Cron Hermes poate programa turn-uri proaspete, dar nu garantează persistența unui proces fără configurarea potrivită a user scope-ului și nici execuția exact-o-dată a unui efect extern.[49] A2A și lifecycle API pentru copii sunt alternative de extindere, nu necesare primului flux.[14][40]

## 4. Arhitectura logică și granițele de încredere

```text
Browserul echipei (HTTPS)
   │  login, RoE, aprobări, live SSE, graf, findings
   ▼
Omnis Web/API (auth/RBAC + engagement service + event stream)
   │
   ├── DB PostgreSQL: engagement, revisions, tasks, graph, acțiuni,
   │                 evenimente, observații, candidați, findings
   ├── Evidence store: bytes/hash/proveniență, acces/redactare/retention
   ├── Scheduler simplu: tranziții, lease, cost/rate, pause/stop/recovery
   ├── Hermes bridge (server-to-server; cheia nu ajunge în browser)
   │      ├── coordonator: sesiune per engagement, turn-uri scurte
   │      └── worker/validator/reporter: rulări cu contexte focalizate
   └── Action Gateway: ROE/scope/risk/identity/budget → allow/deny/approval
           └── executor izolat + egress controlat → ținta AUTORIZATĂ
```

**Regula de autoritate:** modelul poate interpreta, propune, adapta în interiorul unui task și invoca tool-ul admis; codul Omnis autorizează acțiunea exactă, o execută, o înregistrează și controlează statutul findingului. Nu folosim promptul, skill-ul sau un hook Hermes ca singurul firewall de scope. API-ul Hermes poate da acces la terminal și alte tool-uri dacă sunt activate; pentru profilurile de pentest admitem numai toolset-urile controlate și adăugăm izolare de proces/rețea.[2][8]

**MVP = monolit modular, nu microservicii:** UI, API, scheduler și politică în aplicația Omnis; Hermes rulează separat pe loopback; executorul efectiv separat/izolat. Postgres este unica sursă de adevăr pentru engagement. Evenimentele Hermes sunt telemetrie/progres și sunt corelate cu evenimentele de domeniu Omnis, nu le substituie.

Dashboardul Hermes poate fi extins cu taburi UI și rute FastAPI, dar în MVP **nu îl transformăm în portalul echipei**: e o suprafață de administrare a mașinii, cu autorizare diferită de cea pe engagement.[11][39]

Un `approval.request` sau un stop Hermes nu înlocuiește aprobarea Omnis a **acțiunii exacte** și nici revocarea egressului: stop este o cerere de întrerupere și workerul poate fi încă în curs de ieșire.[2][54]

### Contract între Omnis și Hermes

- Omnis creează mai întâi sesiunea Hermes și persistă `engagement_id`, `revision`, `task_id`, `hermes_session_id` existent, `run_id`, `context_snapshot`, `model_requested`, `model_effective`, `skill_versions` și `event_cursor` Omnis. Nu folosim un UUID Omnis necunoscut lui Hermes ca substitut de sesiune.
- La fiecare tură, coordonatorul primește **delta + rezumat canonic**: obiectiv, reguli efective, graf relevant, datorie de acoperire, dovezi/candidați noi, contradicții, buget. Nu dump-ul integral al DB și nici credentiale.
- Tool-uri propuse pentru pluginul Omnis: `get_case_context`, `get_evidence_metadata`, `propose_task`, `request_target_action`, `submit_observation`, `submit_candidate`, `request_review`. Sunt interfețe contractuale propuse, **nu** capabilități deja implementate.
- Handoff-ul workerului conține `task_id`, versiunea/snapshotul grafului, concluzie, referințe de dovezi, controale negative, direcții noi și ce nu a putut verifica. Omnis validează schema și scrie starea; coordinatorul nu acceptă textul workerului ca finding.
- Clientul web urmărește SSE Omnis. Backendul consumă SSE Hermes (`run/tool/message/approval`) și emite evenimente de domeniu: `phase_changed`, `task_started`, `proposal_denied`, `evidence_recorded`, `candidate_created`, `validation_completed`, `finding_verified`. Bufferul Hermes al evenimentelor neconsumate expiră după cinci minute: pentru reconectare și audit, Omnis folosește propriul `events` durabil și `GET /v1/runs/{run_id}` pentru status, fără a pretinde că poate recrea tokenii pierduți.[2]
- Hook-urile observator Hermes pot ajuta la corelarea telemetriei, dar **nu** constituie verificarea policy a unei acțiuni externe; auditul efectului vine din brokerul Omnis.[52]
- `Idempotency-Key` deduplică **crearea run-ului** (cheia este reținută 24 de ore după ultima actualizare de status); nu face idempotent efectul extern. Un request către țintă cu rezultat ambiguu după crash **nu** este retrimis automat. La restart, un run Hermes activ devine `interrupted`, iar Omnis reconciliază task-ul/acțiunile înainte să continue.[2]

## 5. Modelul de cunoaștere: graf, matrice, sesiuni și agenți

Hermes are un „learning journey / memory graph” pentru istoria skill-urilor și a memoriei sale, **nu** pentru topologia țintei. Memoria built-in este injectată ca snapshot înghețat la începutul sesiunii; nu este un feed live al constatărilor.[5]

Providerii externi de memorie pot injecta context și sincroniza conversații; numai unul este activ per profil, alături de memoria built-in.[6] Hindsight sau un `MemoryProvider` propriu merită evaluate ulterior pentru recall/checkpoint, dar trebuie verificate izolarea, proveniența și retenția.[51]

Pentru MVP **nu activăm** un provider extern asupra datelor clienților și nu folosim `MEMORY.md` global pentru ținte. Un context engine cu DAG este posibil prin extensie, dar rezolvă gestionarea conversației, nu înlocuiește graful canonic al engagementului.[15]

**Graful Omnis**: `Asset`, `Surface` (rută/metodă), `Parameter`, `Persona`, `WorkflowState`, `Observation`, `Hypothesis`, `Task`, `Candidate`, `Finding`, `EvidenceRef`. Legături tipizate: `contains`, `uses_identity`, `observed_on`, `supports`, `contradicts`, `derived_from`, `tested_by`, `verified_by`, `duplicates`, `depends_on`. O muchie are `status` (observat/inferat/infirmat/confirmat), sursă, timp, engagement/revision și dovezi. Ipotezele AI nu devin fapte doar fiindcă apar în graf.

**Matricea vizuală** este o proiecție a acelorași înregistrări: `surface × persona/rol × familie de teste × stare (netestat / testat sigur / candidat / confirmat / limitat)`. UI permite trecerea graf → acțiune → observație → dovadă → validator. Workerii citesc un subgraf relevant prin API, nu modifică direct noduri/muchii canonice. Mesajele între agenți sunt handoff-uri structurate și comentarii pe task, nu un chat permanent care amplifică aceeași presupunere.

**Sesiuni și prompting:** o sesiune Hermes per engagement pentru coordonator; fiecare tură este limitată și declanșată de eveniment. Workeri/validatori au context proaspăt; un validator nu primește concluzia altui model ca premisă de adevăr. Promptul stabil descrie rolul și formatul deciziilor; scope-ul/revizia/bugetul vin din contextul curent și sunt revalidate de Omnis. La compresie sau rotație, un checkpoint al grafului + cursorul evenimentelor Omnis reconstruiește contextul. Memoria Hermes înghețată în prompt nu se modifică magic în sesiunea deja pornită: datele noi intră prin tool/context pack la turn-ul următor sau printr-un succesor explicit al sesiunii. Metadatele și istoricul conversației Hermes ajută, dar nu sunt stare canonică.

**„Jev” rămâne neclar** din conversație: poate fi model, agent sau serviciu. Nu îl integrăm imaginar. Dacă este un critic al deciziilor, poate evalua contradicții și priorități în mod consultativ; nu aprobă scope sau findings.

## 6. Etape, roluri și bucle

| Etapă | AI conduce | Execuție / rezultat canonic Omnis | Ieșire sau reîntoarcere |
|---|---|---|---|
| 0. Preflight | Interpretează contextul aplicației, semnalează lipsuri | Autorizație/RoE, scope revision, identități, modele, bugete, health; fără efect pe țintă | `READY` sau `BLOCKED` |
| 1. Recon | Alege zone interesante; interpretează JS, OpenAPI, DOM/API, auth flows | Crawl/HTTP/browser bounded, parse, dedup pe rută+metodă+parametru+identitate/stare; graph nodes | Suprafețe noi → mapping; anomalii → ipoteze |
| 2. Mapping & ipoteze | Corelează graful, descoperă relații și prioritizează | Persistă ipoteză cu semnal vulnerabil prezis + control sigur + acoperire | Task-uri de test sau revenire la recon |
| 3. Testare | Workerul alege/aplică variante admise și interpretează observații; poate propune altă direcție | Fiecare efect trece prin policy/executor/evidence; rate și lease per țintă/persona | Observație, ipoteză infirmată, candidat sau nouă suprafață |
| 4. Validare | Agent independent caută explicații alternative și solicită replay permis | Oracle specific familiei, control negativ, dovadă, stare `VERIFIED/REJECTED/INCONCLUSIVE` | Invalid → replanificare; ambiguu → review/limitare |
| 5. Raport & retest | Redactează explicație și remediere din dovezi, propune retest | Filtru de fapte, dedup la cauză, aprobare umană la livrare | Raport/retest sau `LIMITED` cu gaps |

Bucle finite: **acțiune** (predicție→test→observație→interpretare), **fir de investigație** (mai multe teste pentru o ipoteză), **campanie** (reprioritizare când apar dovezi/suprafețe/candidați). Coordonatorul poate cere noi task-uri, modele și skill-uri admise; Omnis le limitează după scop, cost, rată și condițiile de oprire. Nu impunem o ordine liniară recon→test care ignoră semnalele noi.

Pentru MVP: **un coordonator**, un worker de recon/analiză, un worker de testare și un validator creat numai când există candidat. Parserul OpenAPI, comparația de răspunsuri și deduplicarea pot fi fast-path determinist; AI decide semnificația și experimentul următor. Dacă bugetul sau fereastra de autorizare expiră, rezultatul este `LIMITED`, nu „test complet”.

## 7. Tool-uri și skill-uri: adaptare fără bypass

Primele capabilități propuse: `http.request` tipizat, `browser.navigate/observe` numai după verificarea medierii, `response.compare`, `evidence.read_redacted`, `graph.query`, `candidate.submit`. Playwright are suport oficial pentru automatizare browser Python; ZAP Automation Framework și Nuclei oferă integrări posibile pentru mai târziu.[30][31][32] Ieșirea scannerelor este o observație/candidat, **niciodată automat un finding**. Hermes suportă MCP, dar un server MCP neaprobat sau un tool nativ cu egress direct ar putea ocoli policy Omnis.[50] Nu oferim în profilul pentest `terminal`, `browser` generic sau code execution; dacă un CLI este integrat ulterior, trece prin adaptor cu versiune pin-uită, parametri/schema/timeout/evidence și același policy gateway.

Un skill Hermes rămâne metodologie contextuală (`SKILL.md`). Pentru fiecare tehnică folosită de Omnis atașăm un **manifest minim**: aplicabilitate, precondiții, tool-uri permise, buget, semnal vulnerabil, control sigur, dovadă necesară, criteriu de stop și teste pe cazuri pozitive/negative. Nu construim inițial un nou limbaj de workflow sau compilator de skill-uri. Promovarea unui skill nou între engagementuri cere revizuire și evaluare; conținutul unei ținte este date neîncredere, nu instrucțiune pentru agent. WSTG și NIST SP 800-115 furnizează metodologie/trasabilitate, nu verdict automat.[21][23]

## 8. Candidate → finding: reducerea falselor pozitive

Stări distincte: `HYPOTHESIS → CANDIDATE → VALIDATING → VERIFIED | REJECTED | INCONCLUSIVE`. Un HTTP 200, un match de template sau acordul dintre două modele nu demonstrează singur impact. Înaintea testului se declară semnalul vulnerabil și controlul sigur; după test se stochează identitatea/starea, inputul, observația brută, hashul și reproducibilitatea. Validatorul lucrează cu context independent și un oracle potrivit clasei, reexecutând doar când efectul este sigur și starea poate fi refăcută. Diferențele de autentificare, rate-limit, conținut dinamic și variație de mediu pot produce `INCONCLUSIVE`.

Raportul obișnuit conține findings verificate, plus secțiune distinctă pentru acoperire, candidați neconcludenți și limite. Păstrăm respingerile și controalele negative pentru a măsura și falsele negative. Nu promitem „zero false positives”; evaluăm precizia, recall-ul pe ținte cu adevăr cunoscut, rata de replay și timpul până la o dovadă utilă.

## 9. Web/API, tehnologiile propuse și simplificările

| Componentă | Propunere MVP | Motiv/trade-off |
|---|---|---|
| Frontend | React + TypeScript + Vite; pagini Engagement, Live, Graph/Matrix, Approvals, Findings, Report, Admin.[16][17] | Un SPA autentificat, fără strat SSR/Node obligatoriu pe VPS; interfața se alimentează din API Omnis, nu din dashboard Hermes |
| Vizualizare | Cytoscape.js pentru graf, tabele/heatmap pentru matrice.[20] | Graful e o proiecție; click deschide dovezi și evenimente. Dacă performanța/UX nu corespund, schimbăm librăria fără migrarea datelor |
| Backend | Python FastAPI (OpenAPI, endpointuri, streaming), monolit modular.[18] | Se integrează natural cu adaptoarele Python/Hermes; separăm module în cod, nu în microservicii |
| DB/coadă/graf | PostgreSQL: relații tipizate, `events`, `tasks` cu lease/claim, tranzacții și query-uri recursive limitate.[19][33] | Fără Neo4j și Redis la început; `LISTEN/NOTIFY` poate trezi streamul, dar replay-ul vine numai din `events`, nu din notificarea efemeră.[34][35] |
| Evidence | Fișiere/blobs cu hash și manifest în DB; criptare, retenție și preview sigur | Nu stocăm secrete sau HTML activ neizolat în pagina Omnis; adaptor S3 compatibil poate veni mai târziu |
| Auth echipă | OIDC prin provider existent + cookie HttpOnly, sesiuni și RBAC în Omnis; TLS prin reverse proxy (ex. Caddy).[24][25] | Nu inventăm autentificare/parole noi; platforma publică nu expune direct Hermes |
| Hermes | Gateway/API pe loopback, profil runtime separat de profilul de dezvoltare, toolset minim + plugin Omnis; model/provider selectat per rol/run.[2][4][8] | Configurația/modelul rămân Hermes; profilul nu garantează izolare OS/network. Fără doi writeri independenți pe același home |
| Execuție | Executor izolat cu acces la rețea doar printr-un punct care aplică scope-ul; întâi HTTP de laborator, browser cu efecte doar după gate de fezabilitate | Aici este munca specifică de securitate a Omnis; în special redirecturi, DNS și cereri secundare ale browserului sunt dificil de garantat |

### UI și fluxuri API propuse

- `POST /engagements`, `POST /engagements/{id}/revisions`, `POST /.../preflight|start|pause|stop`; `GET /.../state|graph|matrix|tasks|events|findings`.
- Ownerul introduce RoE și chei prin UI; modelul/providerul/skill-urile sunt selectate din catalogul Hermes expus **doar prin backendul Omnis**. Pentru selecția bogată folosim `/api/model/options`; `/v1/models` nu este catalogul complet al combinațiilor model/provider.[2][53] Cheile sunt write-only/redactate la citire; OAuth și managementul credentialelor trebuie validate într-un spike, fără a expune API-ul de admin Hermes membrilor echipei.
- SSE Omnis cu `Last-Event-ID`/cursor: faze, task-uri, apeluri de tool redacted, policy decisions, dovezi, validator, cost, pauză. Nu afișăm chain-of-thought privat; afișăm **decision cards** cu obiectiv, ipoteză, evidență, incertitudine și motivul operațional.
- Roluri inițiale: Owner/Admin, Lead, Operator, Reviewer, Viewer. Aprobare exactă pentru acțiuni cu impact și audit pentru cine a schimbat scope/ROE.

## 10. Siguranță și operare pe VPS: condiții de intrare, nu „mai târziu”

- **Acces:** HTTPS, OIDC/MFA, sesiuni HttpOnly/SameSite, CSRF/CORS/Host strict, RBAC pe fiecare engagement. URL public ≠ permisiune publică de scanare. Hermes API/dashboard rămân private, fără token în JavaScript.
- **Permisiune:** dovada autorizației, RoE, scope pe host/port/path, ferestre, identități de test, excluziuni, profil de risc, rate/concurrency/cost. Separăm explicit `testabil`, `numai acces/citire` și `exclus`: descoperirea unui domeniu accesibil nu îl face atacabil. Revizia de scope invalidează task-uri vechi înainte de noi efecte.
- **Egress:** fiecare cerere, redirect și copil browser/scanner trece prin controlul destinației și bugetului; blocare private/link-local/metadata/out-of-scope, revalidare DNS și stop efectiv. OWASP documentează riscurile de SSRF și DNS rebinding; un simplu allowlist în prompt nu este protecție.[22]
- **Secrete și date ostile:** vault/referințe opace, injecție numai la execuție; pagini, JS, HTTP responses, documente, skill-uri importate și outputuri de tool sunt date neîncredere. Redactare înainte de model/log/export; viewer separat pentru artefacte active.
- **Oprire și recovery:** pause oprește sarcini noi; kill revocă permisiuni și oprește executorii; o cerere cu rezultat necunoscut după crash rămâne `UNKNOWN`, nu se repetă orbește. Backup/restore și ștergerea derivatelor sunt teste de lansare.
- **Izolare:** MVP pe ținte de laborator poate demonstra designul; deschiderea către ținte terțe ori utilizatori din organizații diferite cere teste de confinare/tenant isolation pe host și rețea, nu doar un alt profil Hermes.

## 11. Plan propus: vertical slices și criterii de acceptare

| Etapă | Livrabil verificabil | Condiția de trecere |
|---|---|---|
| S0 — spike Hermes, fără țintă reală | Gateway local, sesiune coordonator, model picker, `/v1/runs`+SSE+stop/approval, plugin tool fără efect extern, eveniment în Omnis; verificare restart | Contractele API documentate funcționează în versiunea instalată; lipsurile/permisiunile devin ADR-uri; nu declarăm nimic sigur doar din docs |
| S1 — schelet de produs | Auth echipă, engagement/ROE/scope revision în DB, task/events, UI live, graph cu date de laborator, Hermes bridge | Un operator poate crea și opri un engagement-lab; reconectarea UI reconstruiește evenimentele; accesul altui rol este refuzat |
| S2 — o investigație cap-coadă | Recon HTTP/API tipizat, graph/matrix, coordonator, un worker, candidat, validator cu controale pozitive/negative, raport din dovezi | Ținta vulnerabilă este confirmată și ținta sigură nu produce finding; out-of-scope redirect este blocat; pauza/stopul sunt vizibile și eficiente |
| S3 — Web post-auth/browser și team alpha | Identități de test, flux Playwright cu egress demonstrat, aprobări, izolare dovezi, review, backup/recovery; legarea findingului de remedierea făcută de om și retestul dovezii; acces VPS numai pentru echipa autentificată | Fiecare cerere efectivă, inclusiv copil browser, este observabilă sau refuzată; restartul nu repetă mutații; review de securitate înainte de ținte externe |
| Mai târziu | Nuclei/ZAP allowlist, OAST, JS aprofundat, retest continuu, bug bounty ROE, mai multe familii/model routing, eventual multi-tenant | Intră doar după măsurare și ADR; niciun marketing de „acoperire totală” |

Evaluare minimă pe laboratoare izolate, cu ținte **vulnerabile și sigure**, versiuni pin-uite: precision/false positives, recall/miss rate pe adevăr cunoscut, reproducerea dovezilor, încălcări de scope (ținta = zero), acțiuni repetate, cost/timp, intervenții umane și limitări. Confruntăm hibridul coordonator+workeri cu variantele sesiune unică și sesiuni proaspete la model/buget egale. O rată bună pe CTF nu este o rată de descoperire garantată în producție.[26][27]

**Stare locală verificată la redactare:** în workspace există `README.md` minim și arhitectura v7 de referință, fără cod MVP sau fișierele V0 invocate de v7. Hermes instalat este `v0.21.5 (2026.9.24)`, profilul activ este `default`, gatewayul era oprit. Niciun endpoint live, tool plugin, scan sau deployment Omnis nu a fost exercitat prin acest document; S0 este proba necesară.

## 12. Decizii pentru discuție (nu presupuneri mascate)

1. **Produs inițial:** laborator + aplicații Web/API controlate pentru echipa internă (recomandat) sau bug bounty din prima versiune? Ultima variantă extinde mult RoE și verificarea autorizării.
2. **Acces:** team-only pe VPS cu un singur operator juridic/organizație, sau viitor SaaS multi-tenant? Proiectăm contracte extensibile, dar nu pretindem izolare multi-tenant la S1.
3. **Auth:** ce OIDC/SSO există deja? Dacă niciunul, alegem un furnizor de identitate pentru alpha fără a construi parole proprii.
4. **Jev:** ce înseamnă exact? Model, serviciu sau rol de critic/evaluator? Îl integrăm doar după clarificarea interfeței și autorității.
5. **Provideri și date:** ce modele/regiuni sunt acceptate pentru datele clienților? Cheile sunt ale organizației sau BYOK? Ce date pot fi trimise la AI extern?
6. **MVP proof:** ce aplicație-laborator și ce familie de vulnerabilități alegem pentru primul traseu? Recomand autorizare între două identități de test, deoarece include un control sigur clar.
7. **UI:** graful și matricea sunt ambele utile; validăm cu utilizatorii dacă graful trebuie să permită adnotare manuală sau numai vizualizare în MVP.
8. **Integrare Hermes:** `API /v1/runs` este preferința inițială; S0 decide dacă sunt necesare JSON-RPC ori embedding pentru aprobare/subagent/streaming/management.[3] Nu facem fork de Hermes înainte de acest experiment.

**Prag de aprobare:** stabilim răspunsurile de mai sus și acceptăm explicit domeniul S0–S2, controalele de scope și criteriile de validare. Abia apoi începe implementarea. Acest document poate fi amendat; nici el, nici v7 nu sunt „bătute în cuie”.

## Sources

[1] https://hermes-agent.nousresearch.com/docs/llms.txt
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[4] https://hermes-agent.nousresearch.com/docs/user-guide/profiles
[5] https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
[6] https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
[7] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[8] https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
[9] https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
[10] https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
[11] https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
[12] https://hermes-agent.nousresearch.com/docs/user-guide/features/goals
[13] https://hermes-agent.nousresearch.com/docs/user-guide/features/loops
[14] https://hermes-agent.nousresearch.com/docs/user-guide/messaging/a2a
[15] https://hermes-agent.nousresearch.com/docs/developer-guide/context-engine-plugin
[16] https://vite.dev/guide
[17] https://react.dev
[18] https://fastapi.tiangolo.com
[19] https://www.postgresql.org/docs/current/queries-with.html
[20] https://js.cytoscape.org
[21] https://owasp.org/projects/web-security-testing-guide
[22] https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
[23] https://csrc.nist.gov/pubs/sp/800/115/final
[24] https://www.keycloak.org/documentation
[25] https://caddyserver.com/docs/quick-starts/reverse-proxy
[26] https://arxiv.org/html/2308.06782v2
[27] https://arxiv.org/html/2410.03225v2
[28] https://arxiv.org/html/2504.06017v2
[29] https://arxiv.org/html/2408.01605v2
[30] https://playwright.dev/python/docs/intro
[31] https://www.zaproxy.org/docs/desktop/addons/automation-framework
[32] https://docs.projectdiscovery.io/opensource/nuclei/overview
[33] https://www.postgresql.org/docs/current/sql-select.html
[34] https://www.postgresql.org/docs/current/sql-listen.html
[35] https://www.postgresql.org/docs/current/sql-notify.html
[36] https://hermes-agent.nousresearch.com/docs/integrations/providers
[37] https://hermes-agent.nousresearch.com/docs/user-guide/features/credential-pools
[38] https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers
[39] https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard
[40] https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api
[41] https://xbow.com/platform
[42] https://www.aikido.dev/attack/aipentest
[43] https://ethiack.com
[44] https://www.cantina.security/platform
[45] https://www.cantina.security/apex
[46] https://www.cantina.security/bounties
[47] https://bugbunny.ai
[48] https://hermes-agent.nousresearch.com/docs/user-guide/sessions
[49] https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
[50] https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
[51] https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin
[52] https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks
[53] https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
[54] https://hermes-agent.nousresearch.com/docs/user-guide/security
