# Omnis — review Sol și strategie de upgrade prin reutilizare OSS

**Review de produs și integrare, nu baseline amendat.** Bază inspectată: `1e748a0e05517c3e85854aedee5fb758cf8d609d`, ramura `p04-control-topology-wip`. Obiectul review-ului este [dosarul Sol](omnis-pentest-review-proposal.md), nu doar ultimul diff. Direcția clarificată de operator este: **produs independent, cod/metodologie open-source preluate efectiv, Hermes păstrat, Jev integrat, MVP urmat de extindere competitivă**. Includerea Jev nu mai este o întrebare deschisă; contul, bugetul și datele pentru apeluri live sunt aprobări separate.

Acest document înregistrează recomandările și ordinea amendamentelor. Nu schimbă singur arhitectura, scope-ul, porțile sau aprobarea vizuală și nu constituie implementare. Nu s-au pornit assessmenturi, ținte, provideri sau servicii de produs. Cele șase fișiere WIP DB/fixture găsite la început au rămas neatinse.

## 1. Verdictul meu

**Sol are direcția corectă, dar planul trebuie să treacă de la „condiții de integrare” la „produs construit prin reutilizare”.** Nu recomand aruncarea fundației Omnis, copierea completă a Strix sau încă un orchestrator AI. Recomand să preluăm componentele care concentrează munca utilă: metodologie, compoziția prompturilor, recon/parsing, cazuri de test, întrebări Jev, detectarea stagnării, corelarea indiciilor și formatarea rapoartelor.

Cele mai importante ajustări:

1. **Biblioteca Strix devine un import concret, nu o inspirație vagă.** Inventarul are 75 ghiduri plus README, dintre care 29 de vulnerabilități; import/review în loturi, licență și proveniență, conversie la catalogul produsului. Metodologia poate fi largă înainte ca toate familiile să fie executabile.[2]
2. **MVP-ul trebuie să demonstreze modus operandi, nu trei scripturi izolate:** URL/context → recon → hartă/threat model → ipoteză → specialist → validator → indiciu nou/replan → raport/retest. Prima probă BOLA rămâne mică; demonstrația adaptivă urmează imediat, nu abia la P7.
3. **Jev intră în implementarea MVP, în paralel cu runtime/Settings:** integrare reală, întâi shadow, apoi advisory pentru selecții măsurate. Folosim SDK-ul Python oficial și adaptăm întrebările utile din NeuroSploit; nu adăugăm runtime Rust pentru un client HTTP.[23][30]
4. **Reutilizăm crawlerul și scannerul, nu le reconstruim:** Katana pentru discovery, Nuclei pentru un subset revizuit de semnale, Schemathesis pentru extensia API/schema. Adaptoarele și legătura cu evidence Omnis sunt codul nostru.[25][26][27]
5. **Harta internă, taskurile și findingurile sunt obiecte diferite.** Relațiile și precondițiile trebuie să conducă investigația, nu să decoreze dashboardul. Attack paths sunt relații probate, nu încă un finding numărat peste cele componente.
6. **Trei familii nu înseamnă paritate cu Strix.** Le păstrăm drept nucleu demonstrabil, dar programăm extensiile de breadth în §7. Dacă obiectivul lansării este breadth apropiat de run-ul Strix, extensia E1 trebuie inclusă explicit în release; nu declarăm că MVP-ul restrâns o are deja.

## 2. Ce am verificat în run-ul Strix

### 2.1. Inventar și limite

Viewerul local furnizat de operator a fost accesat read-only: Overview, Issues, Agent graph și drawerul verificatorului. Datele au fost citite și prin endpointurile pe care viewerul însuși le folosește: run, vulnerabilities, report, transcript, capabilities. **Tokenul URL, secretele, PII, payloadurile și transcripturile brute nu sunt în Git.** [Inventarul derivat](omnis-upgrade-review.inventory.json) este separat de dovezile sensibile și păstrează pinurile surselor, contoarele și hashurile snapshoturilor locale, fără conținutul lor brut.

| Observație din run | Rezultat citit/calculat |
|---|---|
| Run | `host-docker-internal-5000_d7f4`, completed, deep; fără instrucțiune suplimentară configurată |
| Durată din start/end | 1.666,414716 secunde; UI afișează 27m 46s |
| Model afișat | `openrouter/deepseek/deepseek-v4.1-flash` |
| Cost raportat de run | `$1.2585033071`, rotunjit `$1.26` în UI; nu factură verificată independent |
| Usage | 331 apeluri în `llm_usage.requests`, **nu 331 requesturi target** |
| Context | 31.450.264 input tokens, dintre care 29.033.344 cached; aproximativ 92,3% cache |
| Agenți | 13 în transcript: root + 12 copii; toate relațiile parent sunt către root |
| De ce UI mai arată 14 | Usage include și componenta `dedupe`; nu este un al 14-lea investigator cu transcript în graf |
| Evenimente | 733: 470 tool și 263 chat; indexate integral pentru actor/tool/ordine |
| Issues salvate | 27: 6 critical, 13 high, 8 medium; unul este raportul de lanț `vuln-0027` |
| Acțiuni relevante | 208 `exec_command`, 12 `create_agent`, 3 mesaje explicite între agenți, 3 amendamente threat model, 14 `agent_finish` |

Acesta este un exemplu util de eficacitate pe ținta locală, nu un benchmark al Omnis și nu o măsură a fals-negativelor. Nu am reexecutat PoC-urile. Am citit taskurile, debriefurile, mesajele, indexul tuturor acțiunilor și rezultate selectate decisive; nu pretind replay independent pentru fiecare issue sau audit bytecode complet. Binarul local are SHA-256 `5299f33114fa586733b74a4f97757a12782888a2caa149bcba5c93c4c70c6379`; clona inspectată este Strix `v1.6.2`, `ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2`. Identitatea sursei nu dovedește singură echivalența întregului binar.[2]

### 2.2. Cum a ajuns de la URL la raport

Indicii de eveniment de mai jos sunt **zero-based în snapshotul transcriptului**, nu ID-uri universale. Timestampurile sunt UTC; `created_at` din roster nu a fost folosit pentru cronologia execuției.

| Pas observat | Dovezi din transcript | Ce preluăm în Omnis |
|---|---|---|
| Root verifică starea, apoi deleagă recon | `create_agent` #11, 15:45:26; recon #16–#79 | Un rol Recon cu contract de inventar, nu specialist pentru fiecare clasă înainte de a cunoaște aplicația |
| Recon combină unelte și interpretare | curl, Katana, ffuf, nuclei, JS/forms/API; notă partajată; zero hituri nuclei raportate ca limită, nu „target sigur” | Crawl/parser matur + observații structurate; modelul interpretează ce merită investigat |
| Root construiește threat model | `save_threat_model` #84, 15:48:59 | O revizie comună de actori, limite de încredere, suprafețe și ipoteze, cu observed/inferred distinct |
| Dispecerizează un lot de specialiști | #87–#94, 15:49:26: disclosure, auth, access, SSRF/XXE, traversal, SQLi, XSS/redirect, business | Selecție după suprafață; nu copiem automat concurența de opt copii în Omnis |
| Traversal produce un indiciu transversal | note/source recuperate; root trimite #376 către SSRF și #377 către SQLi | Handoff cu evidence refs, precondiții și destinatari; sursa nouă actualizează planul |
| Rezultatul unui handoff nu este mereu încă un task | SSRF revine și întărește proba; SQLi răspunde #481–#482 că sinkurile sunt deja acoperite | Replan inclusiv no-op justificat; nu duplicăm investigația doar pentru că a venit mesaj |
| Root adaugă verificare și caută goluri | #546 Independent Critical Verifier; #547 Staff-Portal Token & CSRF | Buget rezervat verificării și dispatch pe goluri, nu doar pe findings deja spectaculoase |
| CSRF corectează prima impresie | browser, control steady-state și fereastră post-login; amendament #666 | Oracle de browser și contraexemplu real; lipsa unui flag cookie nu este singură PoC |
| Un nou indiciu creează alt specialist | CSRF/source relevă binding de rol; #675 Mass Assignment, apoi #721 amendament | Frontieră adaptivă: un rezultat poate deschide altă familie după prima rundă |
| Root reconciliază și compune impactul | updates coverage #684–#692; chain report #729; `finish_scan` #732 | Închidere după reconciliere și raport de path separat de numărătorul defectelor |

Nu este „un singur prompt care știe tot”. Cererea scurtă beneficiază de **system prompt + mod deep + skilluri comune + skilluri de specialitate + task concret + context moștenit + note/threat model + tool loop**. `_resolve_skills` adaugă mod, tooling și counterevidence/severity, iar root primește coordonare; rendererul Jinja compune pachetul. Acesta este mecanismul reutilizabil.[8][9][31]

### 2.3. Toți agenții, cu contribuția efectivă

| Agent / ID | Issues salvate de el | Contribuție și lecție |
|---|---|---|
| Root `8e6a5d6a` | 0027 | Orchestrare, handoffs, goluri și lanț final; nu testare target directă în acel unic shell call, care inventariază workspace-ul |
| Recon `9ec66744` | — | Inventar tehnic, endpoints/params/JS/forms, note și ipoteze; scanner fără hit nu încheie analiza |
| Disclosure `a4b7e981` | 0001–0003, 0005 | Grupează expuneri pe cauză; impactul ulterior se actualizează, nu se refiliază |
| Auth `afcf8263` | 0017–0020 | Sesiuni/cookies/JWT, acces privilegiat și sinkul command-execution; secretele trebuie handles, nu text comun în Omnis |
| Access `434b1e3e` | 0006, 0008 | Compară identități/obiecte și testează limite; public profile nu devine automat BOLA |
| SSRF/XXE `84ac298b` | 0007, 0009 | Handofful de source produce dovadă mai puternică: acces indirect vs refuz direct |
| Traversal `92f56160` | 0004 | Descoperire plus source clues care alimentează alte familii; nu doar finding izolat |
| SQLi `f7b35566` | 0010–0012, 0014 | Diferențiale + sqlmap, controale negative și acoperire pe parametru |
| XSS/redirect `f7a7352e` | 0021–0023 | Demonstrație browser, nu simplă reflecție; diferențiază sink activ de cod nefolosit |
| Business `545288c5` | 0013, 0015, 0016 | Reguli/invariante și obiecte persistente; impact financiar posibil separat de ce a fost demonstrat |
| Verifier `85365818` | — | Replay proaspăt/control pentru șase claims nominale, nu toate cele 27 |
| Staff/CSRF `52180885` | 0024, 0025 | Închide golul staff-token, limitează corect concluzia CSRF, semnalează mass assignment și efecte rămase |
| Mass assignment `2b5c916a` | 0026 | Investigă indiciul nou, arată două sinkuri ale aceleiași cauze și controale |

**Ce îmbunătățim, fără a nega rezultatele utile ale Strix:**

- `vuln-0027` compune defecte deja raportate. Sunt 27 înregistrări, nu o dovadă că există 27 cauze-rădăcină distincte. Nici simpla scădere a lanțului nu adjudecă toate celelalte deduplicări.
- În graf toate cele 12 instanțe copil sunt sub root; promptul cere arbori imbricați și un validator per vulnerabilitate, dar run-ul nu urmează literalmente acea structură. Copiem comportamentul eficient observat, nu o diagramă promisă în prompt.[31]
- `create_vulnerability_report` validează câmpuri/calcul CVSS/dedup, nu execută automat un oracle independent pentru fiecare finding. `finish_scan` are un control real pentru copii activi, însă golurile de coverage sunt avertismente; nu trebuie descris nici ca „totul este doar prompt”, nici ca dovadă completă de finalizare.[32][33][34]
- Handoffurile păstrează probe lipsă și efecte de test (conturi/date modificate); „no unresolved surface” în sumar nu certifică cleanup sau eliminarea tuturor incertitudinilor. Omnis trebuie să propage aceste obligații în raport.
- Taskurile SSRF au inclus destinații/porturi secundare și metadata; un singur origin în URL-ul cererii trimise nu limitează automat efectul server-side. Omnis are nevoie de target-lab izolat și de autorizarea tranziției, nu doar de un proxy pentru client.
- Conținutul moștenit și notele conțineau material sensibil. Omnis păstrează informația utilă pentru chaining prin referințe la credențiale/capabilități, nu prin copierea secretelor între prompturi.

## 3. Review pe toate secțiunile Sol

| § Sol | Verdict | Ajustare necesară |
|---|---|---|
| 1 — stare și scop | **Păstrează** | Descrie corect P0.4: nu există încă motorul pentest de refactorizat. Refolosim fundația API/DB/CLI/web. |
| 2 — referințe | **Completează** | Run-ul este demonstrația practică; adaugă accountingul 13 vs 14 și traseele din §2. Competitorii închiși dau cerințe UX/evaluare, nu cod accesibil. |
| 3 — bucle | **Adoptă și mută mai devreme demonstrația** | B06 are deja inbox/consum; G-LOOP demonstrează replan după primul finding. Nu construim nouă schedulere pentru nouă tipuri de buclă. |
| 4 — breadth | **Adaptează** | Nu lăsa toate ghidurile suplimentare fără traseu de promovare. Import larg în paralel; execuție în valuri și stări transparente. `omnis.yaml` rămâne unicul manifest, nu al doilea catalog concurent. |
| 5 — reutilizare | **Extinde substanțial** | Introdu lista exactă source→funcție/pachet→destinație→adaptare→test din §4. Nu limităm reutilizarea la două helpers de raport. |
| 6 — Jev | **Integrare decisă** | Înlocuiește „dacă îl vrem” cu ticket/owner/livrare. SDK Python oficial + întrebări NeuroSploit. Shadow/advisory sunt moduri de operare, nu amânare nedefinită a implementării. |
| 7 — web/UX | **Adoptă, cu delte mici** | Roster în Brain stream/Investigations, threat model inspectabil, Jev Settings și path drawer; fără refacerea cockpitului sau importarea UI Strix. |
| 8 — amendamente | **Corectează înainte de aplicare** | P4a-minim nu este opțional; HTTP-auth se separă de Chromium pentru primul BOLA; nuclei/crawl și Jev primesc integrare explicită în stack. |
| 9 — ordine | **Simplifică** | „Offline-first” se aplică feliei active, nu obligă să construim toate extensiile înainte de primul live. Prima vulnerabilitate nu așteaptă source import/general editor/graph. |
| 10 — decizii | **Parțial depășit de instrucțiunea operatorului** | Build-by-reuse și includerea Jev sunt stabilite. Rămân de adjudecat setul precis al releaseului, importul AGPL dacă va fi dorit și extensiile vizuale, nu direcția generală. |

### Corecții exacte, nu o rescriere a întregului dosar

- **Sol L130:** „P4a Settings-minimal opțional” contrazice planul L58–59/L69/L128–130. Un provider explicit configurat/readback și un skill published sunt obligatorii pentru prima inferență. Editorul, al doilea provider și Jev nu blochează **prima** probă BOLA.
- **Sol L114:** „command/inbox/ack/consumed migrations numai la B18a” întârzie prematur un invariant deja necesar la B06/H06–H07. B18a adaugă STEER și proba de replan, nu inventează atunci inboxul.
- **Sol L141:** lista offline amestecă prerequisites reale cu source snapshot și converter general. O spargem pe tickets independente; niciun nou mega-gate.
- **Sol L128 vs L87:** Stop înseamnă niciun dispatch nou și quiescență locală verificată; nu putem promite oprirea calculului deja trimis providerului.
- **Sol L53/L97:** metodologia largă și source-aware au nevoie de ordine concretă, nu doar „METHODOLOGY_ONLY/după MVP”. §7 stabilește valurile; activarea executabilă rămâne probată per familie.

## 4. Inventar de reutilizare efectivă

### 4.1. Regula de integrare

**C = copiere/adaptare de sursă și teste; P = pachet upstream păstrat, adaptor Omnis; R = referință fără copiere în produs.** Un port Python al unei funcții Go/Rust adaptate este tot reutilizare cu atribuire, nu implementare pretins originală. Nu adăugăm Go/Rust/Temporal în control plane pentru a evita un port de câteva funcții. Pentru engines mari în Go, folosim binarul separat, nu portăm engine-ul în Python.

Pinurile sunt snapshoturi **de cercetare**, nu versiuni deja admise în buildul Omnis. Auditorul de import fixează și tranzitivele, fișierele de licență/NOTICE, testele și update policy; un README care spune „secure” nu este verificare.

| ID / formă | Sursă și unitatea concretă | Destinație propusă Omnis | Ce adaptăm / acceptare |
|---|---|---|---|
| U01 **C** | Strix `strix/skills/`: root coordination, analysis, recon, familii și referințe framework/protocol | `skills/` produs + manifest B11/B14b; nu `.hermes/skills/` de dezvoltare | Copiem metodologia revizuită cu Apache-2.0/attribution; mapăm toolurile și scope-ul. Test import: ID unic, frontmatter/referințe/digest, separarea knowledge de activare. |
| U02 **C** | Strix `agents/prompt.py::_resolve_skills` și blocurile utile din `system_prompt.jinja` | `integrations/hermes/.../prompts/` și composer de rol la B06/B11 | Păstrăm compoziție/dedup și selectarea contextuală; înlocuim terminal/browser generic și mandatul „test ALL/2000 steps” cu capabilities reale. Missing skill este eroare explicită, nu skip tăcut. |
| U03 **C** | Strix `tools/output_store.py`: `_take_prefix`, `_take_suffix`, `_head_tail`, `bound_text` + teste | proiecția bounded spre model/evidence viewer | Truncation explicit și paginare cu ID opac; nu spill raw în workspace comun. Proba offline a găsit notice mai mare decât capul de 10 bytes: minim valid sau notice bounded înainte de adoptare. |
| U04 **C** | Strix `tools/threat_model/tools.py` — rubrici/validare de secțiuni; formatele notes și `agent_finish(findings, open_items)` | `runs`/`surfaces`/`tasks`, persistate în PostgreSQL | Extragem schema/rubricile, nu global JSON store. Amendamente append-only cu basis refs; sumarizarea nu șterge istoricul. Test clue nou→revizie→task care îl consumă. |
| U05 **C** | Strix `report/writer.py`: `safe_fence`, `parse_fenced_code`, `render_vulnerability_md`; `csv_safe` doar când livrăm CSV | `reports/` la B13 | Refolosim formatter și testele, alimentat exclusiv din snapshot Omnis. Nu copiem selecția eligibilității/state. HTML rămâne escaped; Markdown fence nu este sanitizer HTML. |
| U06 **C** | PentestGPT activ `pentestgpt_agent/.../plan.py::compile_plan`, DTO-uri și testele de basis/dependency/revision; `execution.py::_exact_receipt_slice` | `tasks`/`validation`/`evidence` | Adaptăm validarea planului la Task/Attempt Omnis și pool bounded. Copiem verificarea referințelor/fragmentului, nu SQLite MemoryKernel, wrapperul obsolete, lexical effect classifier ori limita globală de un singur task. Un excerpt autentic nu confirmă singur vulnerabilitatea. |
| U07 **C** | NeuroSploit `.../typesafe.rs`: întrebări `same_finding`, `progress_checkpoint`, `response_origin`; `pipeline.rs::typesafe_prune_agents` | întrebări versionate `integrations/jev/` | Reutilizăm rubricile pentru dedup sugestiv, stagnare și relevanță, nu clientul cu `jev-latest`, retry ascuns, raw headers/body și defaults optimiste. Pruning devine prioritate, nu eliminare definitivă de coverage. |
| U08 **C** | NeuroSploit `.../chain.rs`: `Capability`, `provides`, `requires`, `derive_links`, `path_for`; `pipeline.rs::attack_chain/chain_from_seed`; `agents_md/chains/` | `findings/attack_paths`, frontieră în `tasks` și Brain handoff | Portăm matchingul și bucla frontieră→expandare→dedup→validare→frontieră nouă, nu Rust/ModelPool. CWE/keyword/same-host generează **ipoteze**; nu dovedesc chainul. Înlocuim validatorul și filtrăm explicit următoarea frontieră; identity/epoch/state/evidence per edge. |
| U09 **C** | PentAGI `backend/pkg/providers/helpers.go::repeatingDetector`, `executionMonitor`; `task_assignment_wrapper.tmpl`, debrief/task reporter | stagnare/context în `tasks` + prompturi | Portăm comparația normalizată și testele relevante, nu Go backend/GraphQL/Graphiti/Langfuse stack. Cheia include task/identitate/procedură/stare; nu eliminăm câmpuri material diferite doar pentru a găsi repetiții. |
| U10 **P** | Katana `pkg/engine/parser/`, `pkg/navigation`, `pkg/output/result.go` și format JSONL | executor de recon B10/B15 | Reutilizăm crawlerul/parsingul, nu un crawler Omnis nou. Run bounded, versiune/config fixate, auto-update/off-origin/form submission neaprobat dezactivate/refuzate. Fiecare request atribuit și contorizat la sink, inclusiv redirect. |
| U11 **P** | Nuclei engine `pkg/templates`, `pkg/operators`, `pkg/output.ResultEvent` + corpus templates **auditat separat** | adaptor semnale / discovery-exposure | Subset HTTP revizuit, template digest, JSONL→Candidate/Observation. Fără autoinstall/update, code/JS/headless/network/OAST neaprobate. Un matcher hit nu devine direct CONFIRMED. Test secret/PII redaction și template refuzat. |
| U12 **P** | Schemathesis `specs/openapi`, generare de cazuri, stateful links și checks | extensie API OpenAPI/body/business workflows | Reutilizăm loader/generator/checks prin API Python, nu un fuzz loop paralel fără broker. Import local fără remote refs, caz generat→acțiune Omnis, seed/shrinking/cleanup contabilizate. Contract failure ≠ automat vulnerabilitate. |
| U13 **P** | `typesafe-sdk` 0.7.2, client async, typed questions/responses, retry policy și tests MockTransport | adaptor privat Jev | Transport explicit, `jev-1.13.0`, retries=0, deadline, config fără fallback ambiental, payload/log sentinel. SDK are `httpx2`, nu presupunem compatibilitate cu HTTPX existent; lock separat auditat. |
| U14 **R** | Shannon: `queue-schemas.ts`, `task-formation-schema.ts`, prompt partials, reconciliation/report references | referință pentru source-aware și schema relațiilor | Sursa curentă este **AGPL-3.0**, nu MIT. Nu copiem în produsul cu licențiere încă neadjudecată. Dacă se dorește cod Shannon, decizie de licență sau licență separată înainte de import; un proces separat nu șterge automat obligațiile. |

Pentru U01/U02, ancorele sunt corpusul și compoziția promptului Strix.[2][9][31]

Pentru U03/U05, sursele sunt output bounding și formatterul de raport Strix.[35][36]

U06–U09 sunt localizate în snapshoturile PentestGPT, NeuroSploit și PentAGI.[24][23][22]

U10–U12 folosesc snapshoturile Katana, Nuclei și Schemathesis.[25][26][27]

U13/U14 au sursele SDK TypeSafe și Shannon separate.[30][21]

Copierea exactă a fișierelor/testelor se face în felia de import, cu provenance și diff; **niciunul nu este deja integrat în Omnis prin acest review**.

### 4.2. Ce NU merită copiat

- Strix `AgentCoordinator`/OpenAI Agents SDK, Shannon Temporal/pi, PentAGI Go runtime și NeuroSploit Rust harness: ar dubla runtime-ul Hermes și ownership-ul Omnis. Preluăm unități autonome, nu patru orchestre.
- Loaderul Strix cu override/shadowing global și skill lipsă ignorat: Hermes are deja skills, iar Omnis are catalog pin-uit per run.[9]
- Stocarea findings/coverage ca text global, LLM dedup drept identitate și completion din narațiune. Refolosim formate/teste, nu autoritatea upstream.[32][33][34]
- `typesafe_agent.rs` ca validator automat: rubrici de reflecție XSS sau tentativă fetch SSRF nu sunt echivalente cu execuție/impact probat. În sursa inspectată, `pipeline.rs:2374–2392` poate seta `validated=true` după confirmation-loop Jev, deși comentariile din jur descriu rolul drept aditiv. Putem reutiliza selecția de candidates și întrebările, nu acea promovare a verdictului.[23]
- UI-urile complete ale competitorilor: păstrăm shellul Omnis acceptat și portăm doar interacțiunea roster/handoff/evidence relevantă, pe proiecțiile Omnis.

### 4.3. De ce aceste proiecte și nu o listă nesfârșită

Selecția acoperă goluri diferite: Strix pentru metodologie/flow, NeuroSploit pentru Jev/chaining, PentestGPT pentru propuneri tipizate și legătura cu receipts, PentAGI pentru repetări/context, Katana/Nuclei pentru motoare mature, Schemathesis pentru API/schema, SDK oficial pentru client. Shannon adaugă valoare de studiu source-aware, cu cost legal/tehnic mai mare la copiere. Lista comunitară a fost folosită numai pentru discovery, apoi au fost inspectate sursele efective; nu am preluat scorurile sau descrierile ei ca dovadă.[20]

Snapshoturile curente diferă de unele review-uri publice: PentestGPT are modulul activ Supervisor/Executor, iar Shannon folosește pi/TypeBox în sursa inspectată. Nu proiectăm după un articol despre vechea implementare Claude/Zod.[21][24]

### 4.4. Testele de păstrat și prima felie de import

La copiere păstrăm cazurile upstream relevante, nu doar implementarea: Strix `tests/test_runner_root_prompt.py`, `test_skill_dir_extension.py`, `test_threat_model_tool.py`, `test_output_store.py`, `test_fenced_code.py` și `test_report_writer.py`; unele teste verifică behavior upstream pe care îl schimbăm deliberat, deci rezultatul dorit Omnis se consemnează separat.[2]

PentestGPT furnizează `pentestgpt_agent/tests/test_plan.py` și `test_execution.py`; PentAGI are cazurile `TestRepeatingDetector`/`TestExecutionMonitorDetector_*` în `backend/pkg/providers/helpers_test.go`; NeuroSploit păstrează teste în `chain.rs`/`typesafe_agent.rs`.[24][22][23]

Primul import propus livrează **fișiere reale utilizabile offline**: provenance manifest, licențe/NOTICE, root/recon/counterevidence și pachetul BOLA adaptat, composer minim cu fixtures/golden tests, plus lista exhaustivă a ghidurilor rămase. Nu construiește înainte un editor web complet, nu instalează toate toolurile și nu activează automat pachetele importate. Următoarea felie îl consumă prin copilul Hermes, astfel încât importul să nu rămână un depozit nefolosit.

Pentru frontieră, testul Omnis esențial este `needs-review` exclus din seed-urile de execuție, nu doar listă nevidă. În NeuroSploit, `pipeline.rs:1477–1504` folosește rezultatul `validate()` ca frontieră, dar `:1841–1844` păstrează și needs-review/no-evidence. Preluăm algoritmul adaptiv cu filtrul tehnic Omnis, nu presupunerea sugerată de numele variabilei `validated`.[23]

## 5. Arhitectura țintă: ce adăugăm peste fundația existentă

```text
Web Omnis: setup / control / hartă / agenți / findings / reports / Settings
                        │ proiecții + comenzi
PostgreSQL: RunSnapshot, Observations/Relations, Tasks/Attempts, Evidence
                        │
Supervisor Omnis ── Brain Hermes (strategie + ipoteze + replan)
        │               ├── Recon / Investigator (roluri + skilluri Strix adaptate)
        │               └── Validator (attempt/context independent)
        ├── Jev DecisionAdvisor: selecții bounded, critică, stagnare
        ├── action broker ── HTTP / browser / Katana / Nuclei / API generator
        │                       │ policy + capture per request
        │                 target autorizat / sinks de laborator
        └── verdict + report snapshot + renderer reutilizat
```

**Nu înlocuim mecanismul nativ de conversații, tool loop și delegare Hermes.** Îl folosim prin adaptorul deja ales; DB Omnis ține faptele de engagement, nu conversația ca unica memorie. Suprafața curentă Hermes documentează control de sesiuni/delegare; compatibilitatea exactă la pinul produsului rămâne probă H01–H08, nu upgrade automat.[3][4]

### 5.1. Pachetul de prompturi și context

Un prompt comun scurt + un rol + procedura skillului + task contract; nu întregul corpus în fiecare copil. Din Strix păstrăm recon-first, precondiții, ipoteze falsificabile, diferențiale, counterevidence, severity justification și handoff.[8][9][31]

- **Brain:** snapshot/cursor, obiectiv, hartă relevantă, frontieră, rezultate noi, bugete și pool; produce ipoteze/task proposals și motivul scurt al alegerii.
- **Recon:** returnează operații/metode/params/forms/JS hints, auth observations și surse; fără să marcheze o suprafață testată doar pentru că a găsit-o.
- **Investigator:** ipoteză, control prezis, identity/business context și capabilități disponibile; returnează observations/candidates/open_items/next clues/effects.
- **Validator:** claim și rețetă reproductibilă cu precondiții; evidence proaspete și oracle specific. Nu primește instrucțiunea „confirmă findingul colegului”.
- **Reporter:** inițial formatter determinist; narațiune LLM numai dacă adaugă valoare, legată de claims/snapshot. Nu cerem agent separat pentru fiecare vulnerabilitate.

`PromptBundleRevision` se fixează cu model/skill/procedură în run. Teste golden pentru compoziție și output schema; teste de comportament pe corpus separat pentru eficacitate. Golden prompt green nu dovedește că investigatorul găsește vulnerabilități.

### 5.2. Harta internă și chaining

Păstrăm PostgreSQL și relațiile deja planificate, nu introducem graph DB. Noduri utile: operation/parameter, persona/role/tenant, artifact, hypothesis, candidate/finding, capability și business object. Relații: observed-on, requires, yields, contradicts, tested-by, enables; fiecare cu provenance, evidence refs, identity/epoch și revizie. O proiecție `ThreatModelRevision` grupează aceste fapte; nu devine al doilea adevăr copiat în JSON.

Un handoff minim conține: `source_task/attempt`, `basis_evidence`, `new_fact`, `hypothesis_delta`, `suggested_family`, `required_context`, `open_items`, `effect/cleanup_refs`. Secretul nu este `new_fact`; un credential handle poate fi doar o capabilitate propusă, injectată de backend dacă pasul este admis.

Generatorul de chain îmbină **ce produce A** cu **ce cere B**. Jev poate ordona candidații; Brain poate propune un test. Un edge inferred rămâne ipoteză până la replay compatibil al ambilor pași și al tranziției. Aceeași gazdă sau două CWE compatibile nu sunt suficiente; schimbarea de identitate se probează, nu se interzice universal. O legătură lipsă produce path incomplet, fără a șterge findingurile componente.[23]

Prima demonstrație de path poate rămâne în laborator în interiorul familiilor existente: o citire canary permisă descoperă o referință necesară unei verificări BOLA; ambele defecte și legătura sunt probate, fără secret real sau pivot pe alt origin. Este un scenariu propus, nu un rezultat executat. UI: timeline compact în inspector; excepție explicită la A12/„fără Chains”, cu aprobare vizuală separată.

## 6. Jev: integrare concretă, nu promisiune de precizie

**Alegere recomandată:** `DecisionAdvisor` deținut de Omnis, cu clientul async TypeSafe oficial. Sursa SDK inspectată declară versiunea 0.7.2/MIT; candidatul de model este `jev-1.13.0`. `Choice`, `Score` și `Noul` sunt decizii tipizate, nu un al doilea Brain generativ.[5][7][30]

| Punct de integrare | Întrebare reutilizată/adaptată | Efect permis în MVP |
|---|---|---|
| Alegerea specialistului | Este relevantă familia pentru observațiile/precondițiile curente? | Ordine între taskuri admisibile, fără eliminarea obligațiilor obligatorii |
| Triage de clue | Confirmă/contrazice/aduce direcție nouă/irelevant? | Propune wake sau replan; evenimentul rămâne durabil indiferent de scor |
| Stagnare | Continue / pivot / stop pe firul curent | Semnal către Brain, combinat cu detectorul determinist de repetiții/buget |
| Dedup | Aceeași cauză/fix sau doar același endpoint? | Sugestie de merge cu evidence; IDs/occurrences nu dispar printr-un verdict Jev |
| Critica findingului | Ce impact/precondiție rămâne neprobată? | Cere evidence/review, nu emite CONFIRMED sau CVSS factual |
| Chain ranking | Ce legătură are precondiții compatibile și câștig probatoriu? | Ordine de investigație; permisiunea și validarea edge-ului rămân separate |

Primele două utilizări sunt **relevanță/triage și stagnare**: ușor de comparat, reversibile, fără verdict de securitate. Întrebările NeuroSploit sunt sursă reală de cod/conținut; portăm doar subsetul potrivit. Nu copiem praguri generice, răspunsuri lipsă mapate la „application/continue”, `jev-latest`, retryul automat sau payloaduri brute.[23]

Contract minim: `(run, snapshot, candidate IDs, question revision, projection digest)` → răspuns validat cu `model_id`, distribuție/scor, usage/latency/cost cunoscut ori UNKNOWN și fallback. SDK-ul permite transport propriu și `RetryPolicy(max_retries=0)`; logarea DEBUG poate include body, deci avem test sentinel și logging controlat, nu numai redaction de Authorization.[29][30]

Adaptorul nu expune `extra_body`/`extra_headers` arbitrare: în `client/aio/client.py:161–164`, `extra_body` poate suprascrie state/model/questions după compoziție. Verificăm payloadul final serializat și digestul lui. La răspuns cerem exact întrebările așteptate, tip/choice/range/model corecte: `response_types.py:79–109` poate ignora tipuri viitoare și permite answers gol, deci „SDK parse a trecut” nu înseamnă o decizie completă. Lipsă/necunoscut → fallback explicit, nu implicit allow/continue.[30]

Ordine: contract + fixture/sentinel → integrare live shadow aprobată → comparație paired fără/cu Jev → advisory numai dacă nu crește misses/FP și produce câștig util. Baseline suplimentar: heuristică deterministă și, dacă e util, model generativ ieftin. Studiul pentest are o singură rulare per condiție pe o țintă; REFLEX arată beneficii contextuale, dar și cazuri unde un cascade ieftin este competitiv. Nu justifică o promisiune de „decizii automat mai bune” pe Omnis.[18][19]

Jev este inclus în produs chiar când modul unui run este OFF. Settings arată configurarea, versiunea, data policy și costul; runul arată modul fixat. Nu facem hot-swap sau apeluri la boot. Provider egress este separat de target; revocarea oprește dispatchuri noi, iar apelurile trimise pot rămâne remote in-flight. TypeSafe declară că nu antrenează pe cereri; ZDR este ofertă enterprise, nu presupunere pentru orice cont.[5][6]

## 7. MVP și extinderea spre produs competitor

### 7.1. Propunerea de scope

**Prima felie ≠ MVP final ≠ paritate Strix.** Păstrăm prima vulnerabilitate BOLA ca demonstrație mică. Pentru închiderea MVP recomand să existe trei familii probate **într-o campanie adaptivă**, Jev integrat/evaluat și cel puțin un path bounded după G-LOOP. Path-ul este o extindere explicită a baseline-ului actual, nu cerință introdusă retroactiv în G05a/G06a.

MVP include:

- Web/API local autorizat, black-box/grey-box declarat, HTTP/browser/JS și OpenAPI local; setup și toate acțiunile normale în web.
- Recon reutilizat și hartă internă inspectabilă; threat model parțial util înainte de hunters, apoi actualizat.
- Biblioteca de knowledge importată/revizuită în loturi; catalogul nu ascunde familiile neexecutabile și nu le prezintă drept testate.
- BOLA, reflected XSS și traversal-canary demonstrate; validator, coverage probatoriu, report/retest reale.
- Replan din clue nou, debriefuri durabile, stagnare și buget rezervat validării; inițial un copil, apoi doi inclusiv validatorul.
- Jev real în shadow și advisory numai pe heads care trec comparația; nu condiționează primul finding.
- Un path scurt probat, separat de root-cause counts; UI compactă, după amendament/aprobare vizuală.

**Trade-off explicit:** acest MVP demonstrează modul de operare și infrastructura extensibilă, nu breadthul celor 27 issues din Strix. Pentru un prim release care pretinde breadth apropiat, includem și E1 de mai jos și acceptăm livrarea mai mare. Nu recomand să etichetăm trei familii drept competitor complet.

### 7.2. Valuri cu valoare observabilă

| Val | Livrare | Reutilizare dominantă | Condiție de închidere |
|---|---|---|---|
| **M0 — fundație** | Termină launcherul P0.4/G00, apoi engagement și copil Hermes autentic | Codul Omnis deja existent, nu rewrite | Artifact instalat, stare persistentă, control real; nu doar harness |
| **M1 — primul rezultat** | Recon minim util → BOLA → validator → report/retest | Strix BOLA/recon/counterevidence + parser/crawler; PentestGPT checks adaptate | URL/context fără soluție → finding; safe/shared control neconfirmat |
| **M2 — MVP adaptiv** | G-LOOP, browser + XSS/traversal, Jev, path bounded, Settings și gates finale | Strix knowledge, NeuroSploit Jev/chain, TypeSafe SDK, PentAGI stagnare | Clue schimbă următorul task; path are evidence; Jev măsurat, export/retest fidel |
| **E1 — breadth Web/API** | Disclosure/config exposure; auth/session/JWT; BFLA/mass assignment; SQLi | Strix ghiduri + Nuclei subset exposure, adaptoare diferențiale/SQLi mature | Fiecare subfamilie are oracle și fixture vulnerable/fixed; auth-maintenance distinct de auth-testing |
| **E2 — workflow/browser/server-side** | CSRF, DOM/stored XSS, SSRF/XXE, business workflows și race bounded | Strix + Schemathesis stateful + sink/canary dedicat | Browser/session timing și relații business probate; cleanup și destinații secundare controlate |
| **E3 — source-aware** | Snapshot explicit de cod, hints/source-to-sink + verificare runtime, remediere/retest | Pipeline/parsers OSS revizuite; Shannon ca referință sau import după decizie legală | Source-light fără execuție la import; profil de informație evaluat separat; source proof nu devine implicit runtime proof |
| **E4 — scalare/extensii** | Mai mulți workers, GraphQL/WS/gRPC, OAST, upload/deserializare/RCE și integrări echipă unde sunt cerute | Pachete dedicate și componente existente evaluate atunci | Gate de transport/familie/deployment; nu activare prin simplu import de skill |

E1/E2 se împart pe pachete, nu într-un mega-commit. Ordinea internă se poate reprioritiza după țintele proprii și rezultatele Omnis; nu inventăm estimări calendaristice înainte de probe.

## 8. Amendamente precise la Omnis

Numele noi de API/fișiere sunt **contracte propuse**, nu endpointuri deja implementate. Păstrăm [matricea UI existentă](../Omnis_Implementation_Plan.md) §16 și o extindem, nu pornim un plan concurent.

| Loc actual | Schimbare propusă | Owner și probă |
|---|---|---|
| Arhitectură §1–2, L13–21/L30–40 | Separă certificarea inițială de catalogul/familiile viitoare; excepție bounded AttackPath la A12; Hermes rămâne runtime | Product decision + G-PATH și aprobare vizuală; fără graph DB |
| Arhitectură §5, L207–245 | Prompt bundle, task/debrief contract și mapping al metodologiei Strix la tools native/Omnis | `integrations/hermes`, `tasks`; H03/H04/H06, pachet lipsă și copil greșit refuzate |
| Arhitectură §6/§11, L271–308/L434–442 | Scenariu adaptiv explicit, clue-driven frontier și progress/stagnation; nu alt scheduler | `tasks/runs/surfaces`; consum idempotent și next-task diferit după clue |
| Arhitectură §9/§12, L342–353/L559–579 | Threat model projection/revision, evidence-backed relations și AttackPath; Jev receipt | Reutilizează Observation/Relationship/Task/Inbox; migrare separată numai pentru invariant lipsă |
| Arhitectură §3/§10, L61–85/L409–417 | Scanner action window/attribution și ModelProjection pentru Jev; provider transport separat | `policy/evidence/executors`, `integrations/jev`; sink deny și payload sentinel |
| Plan §4/§10, L58–64/L97/L154–158 | P4a-minim obligatoriu; extrage HTTP-auth din browser pentru BOLA API-only | `identities/vault`; principal/role pozitiv, epoch/replay și drift→inconclusive; G03b rămâne pentru MVP complet |
| Plan §7/§14, L118–119/L216–222 | Inbox minimal la B06, B18a/G-LOOP imediat după G06a; B18b păstrează concurența extinsă | `tasks`; crash/replay/Stop fără dublu wake |
| Plan §11/§13, L166/L206 | JS/OpenAPI/body minim care poate descoperi prima operație intră cu B10; Katana/parsers în loc de crawler nou | `surfaces/executors`; endpoint nelinkuit descoperit fără a oferi soluția |
| Plan §8/§12 și stack §5–8 | U13/Jev în paralel P2/P4a, pins candidate, import backlog U01–U14 și licențe | Manifest/lock dedicat; client inert→shadow→advisory; fără chei în repo |
| Plan §11–15/§16 | G-PATH dependent după G-LOOP, valuri E1–E4 și matrice UI extinsă | Nu schimbă prima probă BOLA; breadthul livrat este acela testat |
| UI/UX §0/§3/§8 | Roster, threat model, handoff/path inspector și Decision support fără schimbarea navigării principale | Brain stream/Investigations/Settings; keyboard/Stop/context/stale și readback |
| README/status | După amendamente aprobate, leagă deciziile și starea reală | Nu declară upgrade implementat din existența acestui review |

### 8.1. Delta UI → contract → owner → test

| Suprafață | Contract propus / existent | Persistență și moment | Positive / negative readback |
|---|---|---|---|
| Threat model în Coverage/Overview | GET threat-model + surfaces/events | `runs` projection, `surfaces` facts la B10 | Revizie/cursor coerente; inferred nu devine observed/tested |
| Roster și handoff în Brain stream | GET tasks/events existent; STEER propus pe commands | Task/Attempt/Inbox la B06; STEER la B18a | Exact copil/attempt; queued≠consumed; stale/Stop refuzate |
| Path în finding inspector | GET attack-paths propus | Findings/path steps + evidence refs la G-PATH | Pași și tranziție probate; edge străin/lipsă/epoch incompatibil refuzate; counts neschimbate |
| Jev Settings și evenimente | GET/PUT decision-support propus; config readback | Settings revision + RunSnapshot + DecisionReceipt | Modul/versiunea exactă; no secret echo/hot-swap; timeout/fallback vizibil |
| Skills import/review | Draft import/publicare sub Settings, export de surse separat | `omnis.yaml`, provenance/release digest la B14b | Un release exact; referință lipsă/shadowing/tool lipsă nu activează skillul |
| Recon/scannere | Capability/preflight + action events | Package/version/template/config în RunSnapshot | Request atribuit la sink și evidence; scanner fără hit nu califică toate familiile ca testate |
| Source-light ulterior | POST/GET engagement sources propus | Manifest/digest/review la G-SOURCE | Import revizuit + restart; symlink/remote ref/secret/ref extern refuzate; zero execuție la upload |

Nu creăm în avans toate aceste rute/migrări. Fiecare felie livrează consumatorul, contractul, testul și readbackul împreună.

## 9. P0.4: ce păstrăm și ce ajustăm acum

Păstrăm API/pairing/sesiuni, PostgreSQL/migrări, control privat/lease/barieră, bootstrap React real, CLI status și instalarea bundle/imagine. API are `assessment_ready=False`; CLI expune `status/install/install-image`, nu launcher complet. Aceasta este fundație reutilizabilă pentru produs, nu motor de pentest existent.

Review-ul implementării a identificat următoarele, fără a modifica WIP:

| Prioritate locală | Constatare | Remediere limitată |
|---|---|---|
| Înainte de gate DB | `ops/compose.test.yaml` WIP trece la no-network/UDS, dar `api/tests/conftest.py:48–67` cere în continuare TCP loopback/port; helperul nou este probe-only | Închide **un singur** contract fixture + helper + Make/CI/docs; nu reveni la port publicat pentru green |
| Înainte de `omnis stop` acceptat | `supervisor/__main__.py:38–51`: Stop event nu întrerupe un heartbeat/quiesce/release suspendat; timeoutul este numai pe wait | Deadline/anulare/rezultat reconciliat la acele I/O; nu alt framework de proces |
| Înainte de CI reproductibil | `.github/workflows/ci.yml:21–44` păstrează vechiul port lookup și nu pregătește mediul CLI necesar gate-ului | Actualizare împreună cu fixture-ul; CI remote rămâne NOT-RUN |
| Nu promova WIP | `owner.py:76–97,159–195` lasă anumite OSError waitpid/gate-write fără kill/reap controlat | Deja cunoscut în adjudecarea P0.4; păstrează entrypointul instalat `omnis.serve` până la remediere/probă separată |
| Înainte de commitul WIP al autorului | Runnerul nou are drift Ruff format | Corecție separată a autorului, nu modificare de arhitectură |

Părintele a reprodus inert refuzul UDS și cele trei căi OSError; a verificat control-flowul Stop cu heartbeat suspendat și revenirea după eliberare. **Mock/control-flow, nu fault live DB/OS.** `make check`/`make test` nu au fost rulate pe fixture-ul neacceptat; acest blocaj nu împiedică cercetarea/importurile inerte, dar împiedică declararea G00.

Calea critică rămâne scurtă: fixture coerent → `omnis start --no-open` instalat → pair/open → stop durabil/persistență → G00 → engagement/copie Hermes. Nu mai extindem harnessul fără să avansăm o comandă de produs. Restul review-ului nu trebuie ținut ostatic de detaliile acestui harness.

## 10. Ordinea schimbărilor și măsurarea rezultatului

1. **Amendamente de decizie:** corecțiile Sol P4a/inbox/offline; direcția build-by-reuse/Jev; scope MVP/path; plan/architecture/UI/stack sincronizate. Commituri mici, fără schimbarea produsului sub un run.
2. **Provenance/import offline în paralel cu P0.4:** upstream manifest, licențe/NOTICE, corpus curat de metodologie și testele copierii; drafturile nu activează trafic.
3. **Runtime+context:** Hermes adapter, PromptBundle, TaskProposal/debrief și proiecții; adaptăm U02/U04/U06 în felia care le consumă.
4. **Recon/investigator/validator:** Katana/parsing și primul skill BOLA; evităm un engine de scanare propriu. Raport/retest și helpers U03/U05 odată cu consumatorii.
5. **Bucla adaptivă și Jev:** U07/U09/U13, apoi U08/G-PATH. Nu trecem direct la un swarm mare; măsurăm utilitatea unui handoff și a unei alegeri mai bune.
6. **Promovare pe familii E1–E4:** conținutul este deja disponibil; adăugăm adaptor/oracle/fixtures, nu repetăm construcția platformei la fiecare clasă.

Măsurăm separat: operații/params/identități descoperite; ipoteze valide și ratări pe etapă; distinct findings/occurrences/paths; independent replay; false positives pe controale sigure; efecte/cleanup; target requests și LLM/decision calls; cache/cost/latency; intervenții umane. Pentru Jev: aceeași țintă resetată, model generativ, tools, identități și buget, cu/fără advisor, plus fallback/disagreement/calibration.

Run-ul actual Strix poate deveni **caz de dezvoltare**, nu held-out: l-am văzut deja, inclusiv soluțiile. Pentru comparație onestă folosim variante noi/fixed și aceleași condiții de acces. Nu alegem un threshold retroactiv ca să câștige Omnis. Cantina/Aikido/XBOW sunt referințe de produs, nu un motor open-source pe care îl avem disponibil pentru integrare.

XBOW documentează preflight/auth-concurrency, auth-only și clasificarea tipului de validator.[10][11][12]

Aikido oferă coverage pe endpointuri descoperite și threat model vizibil condiționat de repository-linked, utile ca referințe UX, nu oracole Omnis.[14][37]

Field reportul Cantina și comparația Doyensec sunt surse atribuite, nu praguri de eficacitate certificate pentru produsul nostru.[16][17]

## 11. Dovezi, verificare și limite

- Documentele și codul P0.4 au primit review-uri independente read-only; constatările importante de fixture/owner/Stop au fost reproduse de părinte prin probe inerte.
- Sursele OSS sunt fixate prin SHA și licență în inventarul asociat. Auditul este al componentelor candidate, **nu audit complet de securitate al fiecărui repo și al tuturor dependențelor**.
- Proba de reutilizare a executat funcții pure inspectate, extrase din Strix/PentestGPT: 19 verificări au trecut; cazul `bound_text(max_bytes=10)` a produs 45 bytes și este înregistrat ca adaptare necesară. Nu este suită upstream completă sau integrare Omnis.
- `python scripts/render_docs.py --check`: exit 0, cinci cititoare sincronizate. `python -m unittest discover -s tests/documentation -v`: exit 0, 28 teste. Acestea verifică documentația/prototipul, nu pentest runtime.
- Viewerul Strix a avut și o captură timeout/o reîncărcare fără token refuzată; accesul autentificat a fost recuperat. Datele/screenshotul ulterior au confirmat Issues și drawerul agentului. Nu am trimis raportul prin email/cloud.
- Extracția web a unor pagini a fost parțială; lucrările Jev au fost citite și din HTML direct. Pagina Aikido despre threat model a fost recuperată în browser după 403; prerechizitul repository-linked a fost confirmat acolo. Nu presupunem acces la implementarea internă a produselor închise.
- Nicio copie de cod/metodologie upstream nu este încă activată în produs, niciun model Jev nu a fost apelat, niciun cost Omnis măsurat. Review-ul livrează sursele și planul de adaptare, nu pretinde că a livrat upgrade-ul.

## Sources

[2] https://github.com/usestrix/strix/tree/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[4] https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
[5] https://docs.typesafe.ai/models
[6] https://docs.typesafe.ai/legal
[7] https://docs.typesafe.ai/api
[8] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/skills/coordination/root_agent.md
[9] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/agents/prompt.py
[10] https://docs.xbow.com/console/guidance/checking-configuration
[11] https://docs.xbow.com/console/reference/protected-urls
[12] https://docs.xbow.com/console/reference/vulnerability-classification
[14] https://help.aikido.dev/pentests/coverage-and-findings/understanding-pentest-coverage.md
[16] https://www.cantina.security/resources/apex-field-report/apex-field-report.pdf
[17] https://doyensec.com/resources/ComparingAIApplicationSecurityTestingPlatforms_Doyensec.pdf
[18] https://arxiv.org/html/2609.28940v1
[19] https://arxiv.org/html/2609.26532
[20] https://github.com/insidetrust/awesome-ai-pentest
[21] https://github.com/KeygraphHQ/shannon/tree/327c10fd90a6186a9f035b4b6ddb5bbba1839e92
[22] https://github.com/vxcontrol/pentagi/tree/ea665308baaff015b226f308438a68d929d0f29b
[23] https://github.com/CyberSecurityUP/NeuroSploit/tree/5d4e7e0347219ceae22735ec6af3d8cdd0561ded
[24] https://github.com/GreyDGL/PentestGPT/tree/e8b1bb77d1ac00329675cec3b060aba971ec1ac8
[25] https://github.com/projectdiscovery/katana/tree/29f4d1cbaffc634f79f389c59f34be6f85fcde5d
[26] https://github.com/projectdiscovery/nuclei/tree/47f74706a54261ecbbbac617a75c1ec5ef9bddd7
[27] https://github.com/schemathesis/schemathesis/tree/be1b46696dc7eb8aa472054d1b46c95e8f069382
[29] https://docs.typesafe.ai/sdk/python/api/retries
[30] https://github.com/typesafe-ai/typesafe-sdk-python/tree/f078f1e208a0d885154dc758344ae4fce77ac168
[31] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/agents/prompts/system_prompt.jinja
[32] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/tools/finish/tool.py
[33] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/tools/reporting/tool.py
[34] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/tools/coverage/tools.py
[35] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/tools/output_store.py
[36] https://github.com/usestrix/strix/blob/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2/strix/report/writer.py
[37] https://help.aikido.dev/pentests/coverage-and-findings/threat-model
