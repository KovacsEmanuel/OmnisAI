# Omnis — amendamentul skill-uri, specializare și review metodologic

**Bază analizată:** `90b90c51a0a64a1c2b8f04ffaf7e6d47de0ca7eb`. Analiză/adjudecare înaintea editării canonului, nu plan alternativ și nu implementare runtime. Cererea operatorului autorizează integrarea patternului din notițe în arhitectură și plan; nu autorizează trafic, DB, instalări sau granturile din capturi.

## Sursă și conservare

Sursa primită este `documents/Omnis_Notite_Originale.html`, SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`. Era **untracked** la început; rămâne nemodificată și nestaged, alături de cele șase fișiere DB/WIP protejate. Canonul de mai jos nu depinde de prezența acestui fișier în checkoutul altui implementator: deciziile sunt migrate în documentele versionate. Numele din notițe sunt exemple, nu identificatori/API-uri admise automat.

Textul original integral și toate **8 imagini** au fost citite separat de părinte și reviewer. Textul rerandat și Skills.md din details sunt aceeași sursă, nu două confirmări. Observațiile vechi ale asistentului din HTML nu sunt decizii. Imaginea 3 este parțială; imaginea 6 repetă Phase 1; imaginea 7 separă producătorul de wordlist de consumator, dar stringurile JS nu probează utilizare live. Imaginea 8 este demonstrație externă: nu importăm ținta, calea locală, numerele sau afirmația Confirmed Tech Stack ca date/evidence Omnis.

Analize înainte de editare: `parent-analysis.md` și `independent-analysis.md` în `/home/kali/.hermes/cache/scratch/omnis-skill-pattern-review/`. Reviewerul a salvat analiza proprie înainte de confruntare. Concluziile durabile sunt păstrate aici; rapoartele scratch nu sunt prerechizit pentru implementare.

## Verdict și adjudecare

**Păstrăm mecanismele existente:** un singur runtime Hermes, catalog unic SKILL.md + omnis.yaml, Technique/Procedure/TaskBrief/Result, grants backend, publication/evaluation, Artifact/Observation, inbox/replan, validator și ReportReview. Nu declarăm aceste mecanisme absente. **Completăm contractele** pentru toate tipurile de muncă, rețeta de specializare și reviewul metodologic; particularizăm JS/discovery ca exemple, nu ca două excepții hardcodate.

| ID | Sursă din notițe | Decizie canonică / owner și livrare |
|---|---|---|
| NS01 | Agent skill; întrebările goal/steps/tools/output | Pattern comun de authoring și work_kind; settings/catalog + tasks, B06/B11/B14b, arhitectură §9.9 și plan §4.4 |
| NS02 | Skill design [vuln category], exemplul XSS | Specializări ≠ patru procese obligatorii; AgentRecipe și selecție după ipoteză/context. B16 reflected, restul gate-uri de extensie; pool comun neschimbat |
| NS03 | Framework, imaginea 2 | Skill ≠ agent ≠ tool ≠ procedură; Brain creează task și backendul admite copilul nativ; fără agents.yaml sau framework nou |
| NS04 | Arguments ca string | Input schema + ProcedureBinding rămân adevărul; argumente numite tipizate, fără shell interpolation/string paralel; B06a/b, UI14/15 |
| NS05 | Model/Effort, imaginea 3 | Preferință/cerință versus rezoluție efectivă în recipe/config/receipt; `xhig` invalid, nu corectat tacit; H04/H08/G-MODEL, UI09/14/15/20 |
| NS06 | Context/supporting files | Încărcare progresivă din subsetul fixat, refs/digests și proiecții; scripts/binare inerte la editare, fără auto-install; B06/H03/G-DATA-EARLY |
| NS07 | Permissions in subagent | Cereri de capabilități, nu grants; intersecție rol/binding/scope/focus/policy/readiness/buget. Nu copiem Bash/MCP wildcard; H04/H08/G-TOOLS |
| NS08 | How to build a skill, mindmap | Authoring din surse și metodă cu obligații verificabile. CONTRACT/PURE nu pretinde corpus vulnerable/fixed; SECURITY păstrează oracol/triplet și negative controls; B06/B11/B12 |
| NS09 | Context Engineering: senior reviewer după copil | MethodCheck determinist înaintea succesului; critic REVIEWER independent și rework bounded la B18a **după G06a**, nu al doilea validator sau publisher |
| NS10 | Goals/loops/cron | Brain urmărește obiectivul și primește delte; supervisorul decide completion/limite. Reviewerul nu reînnoiește bugetul; cron rămâne maintenance ulterior |
| NS11 | Handoff și compunere | Refolosim StepOutputRef local și artifacts între taskuri; done_when/requirements calificate per BoundProcedure; un handoff nu declanșează automat consumerul |
| NS12 | JS: inline/files/lazy/history/sourcemaps | Sursă/prospețime/context/digest și gaps; achiziție separată de analiză offline. B10 minim, B15j pentru breadth; history online/debugging numai cu subgate explicit ulterior |
| NS13 | Swagger/API din JS, versiuni | Inventar API și eventual OpenAPI INFERRED/PARTIAL, fără metode/auth/params inventate; import/export nu acordă scope sau execuție; B15j/G-JS |
| NS14 | Functions/params/flags/comments/libs/secrets | Semnale și leads citate, nu vulnerabilități confirmate. Secrete private, fără folosire activă automată; B10b/B10c/B15j și oracol de familie separat |
| NS15 | ContentDiscovery versus content-discovery-wordlist | Producer pasiv, opțional planner MODEL separat, builder PURE determinist pentru input fix, consumer TARGET_IO. G-WORDLIST-CORE înainte B15, poarta integrată după |
| NS16 | Liste standard/specifice, quick hits, ffuf | Variantă generică/contextuală și subset quick-hits cu provenance/buget, comparație la buget egal. Tooluri/liste din capturi sunt candidate neadmise; reuse fixat rămâne baza |
| NS17 | Human in the loop la raport | Validator tehnic → Accept/Hold editorial; contestarea cere probe/retest, nu CONFIRMED manual. B12/B13, UI05/07 |
| NS18 | Human in the loop în run, auth/CAPTCHA | Needs you pentru efect/clarificare/auth/date/cost/gaps; comandă și readback, nu bypass sau solver implicit; B07/B09/B18a, UI08/12/15 |
| NS19 | Tool table/recon/password mutation/RAG | Adaptoare înguste și context contextual; shell/code runner numai după adaptor/gates, fără host implicit. Credential attacks/social engineering/post-exploitation nu intră în MVP; RAG nu impune vector DB nou |

## Limite native verificate înainte de proiectarea contractului

Hermes are încărcare progresivă a skillurilor și referințelor; Omnis o folosește pe releaseul RO selectat, nu pe biblioteca personală mutabilă.[2] Public lifecycle cere un parent activ; handleurile nu fac un worker durabil după restart.[3]

La pinul `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, `SubagentLaunchRequest` are `model` și `allowed_toolsets`, iar launch le transmite constructorului nativ. Nu are provider/effort per launch; blocked_tools/workdir/per-launch timeout sunt respinse explicit. **Lista goală de toolsets ajunge inheritance, nu deny-all.** Nu inventăm aceste câmpuri în `delegate_task` model-facing; plugin-first folosește seamul real, cu H04/H08/G-MODEL și inventarul efectiv înainte de efect.[5]

Sursele au fost citite, nu executate. Fetch raw GitHub a primit 429; API-ul oficial a recuperat fișierele exact la pin. Extracția web inițială a paginii skills a fost prea scurtă; browserul a recuperat textul complet. Aceste fallbackuri nu sunt teste ale runtime-ului Omnis și nu schimbă pinul.

## Limită de schimbare și verificare

Modificările se limitează la arhitectură/plan/UI/stack/readiness/README/verification, cititoarele generate și regresiile documentare. Fără schemă DB nouă, directoare/module produs, implementare de skill executabil, tool install sau schimbare de P0. Nu schimbăm prima probă BOLA, G00, WIP ori aprobarea vizuală.

Baseline înainte de editare: `make check-docs` **46 teste PASS**, 5 cititoare sincronizate; `git diff --check` PASS. `make check/test` rămâne BLOCKED de integrarea DB/WIP explicată în plan §19.2; nu se începe alt harness. Verificarea finală și readbackul commiturilor se completează după amendament, distinct de probele runtime NOT-RUN.

## Re-review și remedii

Review-ul independent al contractelor la `02f1f41` a găsit F1/F2 medii și F3 mic; nu sunt defecte runtime reproduse. Raportul complet este `core-rereview.md` în scratchul acestei felii. Adjudecare: acceptate, remediate documentar și în regresiile relevante, fără extindere P0.

| Constatare | Remediu și commit | Verificare / limită |
|---|---|---|
| F1 — LOCAL ambiguu în recipe multi-pachet | ProfileTemplateRef CANDIDATE cu package_key explicit sau RELEASE; source_draft_refs fixate la freeze, LOCAL rămâne intern pachetului; `7b29c47` | Regresie RED→GREEN, exemplu alpha/beta inspect, bare LOCAL/namespace lipsă refuzate; nu implementare de resolver |
| F2 — lipsă relație de închidere după rework | MethodResolution append-only origine→cerință/rezultat succesor + check/review/qualification/rule; proiecția închide obligația curentă, nu rescrie R0; `2a81400` | Regresie RED→GREEN; fără StepOutputRef cross-attempt, numai subprocedură publicată cu artifact calificat ori prerechizite reexecutate bounded |
| F3 — smoke guards treceau fără definiții | Rânduri normative unice, câmpuri indispensabile, REQUIRED→BLOCK și mutații negative in-memory; `f033b50` | Ștergere MethodPlan/MethodCheck și relaxare REQUIRED reproduse ca false-green, apoi refuzate; nu parser semantic universal sau harness de produs |

**Review exemple/livrare: PASS bounded pe 0905f87**, raport `delivery-rereview.md` în scratch. Reviewerul a confruntat textul și cele 8 imagini, a parcurs SK/RF/SL/UI/gates, proveniența/API inferat, producer/consumer și extensiile E2, fără constatări funcționale noi. A executat 47 teste documentare (3 CLI cu scrieri temporare NOT-RUN în subsesiunea read-only), cele două teste ale deltei și 4 controale negative în memorie; nu îi atribuim suita completă a părintelui. Părintele a verificat că secțiunile revizuite §11.1/§4.4/stack §10.4 sunt identice după remedierile core. **Re-review F1–F3: PASS documentar pe 2a81400**, raport `core-fixes-rereview.md`. Reviewerul a verificat 6 teste focalizate, a detectat 8 mutații in-memory, a comparat 3 perechi MD/HTML prin randare în memorie și a confirmat cele 7 fișiere protejate. Părintele a citit raportul și a verificat că cele 7 fișiere canon/test revizuite sunt byte-identice cu acel snapshot. F1/F2/F3 sunt închise documentar; nu este certificare runtime.

## Verificare finală și predare

**Verdict:** cele 19 decizii NS sunt incorporate în același baseline, iar constatările re-review-urilor sunt rezolvate în aria verificată. Arhitectura §9.9–9.10 definește patternul comun și reviewul metodologic; §11.1 arată JS/discovery; plan §4.4 și RF/SL/ticketurile precizează livrarea. Acest verdict permite continuarea incrementală conform prerechizitelor, nu promite zero buguri, skills implementate sau eficacitate demonstrată.

| Stare | Comandă/probă și rezultat real | Limită |
|---|---|---|
| PASS | `python scripts/render_docs.py` și `python scripts/render_docs.py --check`: 5 HTML-uri generate/sincronizate, exit 0 | Canon/readers, nu frontend/backend integrat |
| PASS | `python -m unittest discover -s tests/documentation -v`: 54 teste, exit 0, după ultima schimbare de cod/test | Regresii documentare, inclusiv negative pentru definiții/ref/model/rework; nu oracles runtime |
| PASS | `git diff --check`: exit 0 | Whitespace, nu corectitudine semantică |
| PASS | `python tests/documentation/browser_check.py --include-documents --output "$TMPDIR/omnis-skill-pattern-review/browser-check.json"`: 116 checks, zero failures/JS errors/unexpected network, exit 0 după fixuri | Prototip/readers offline, nu G00 sau aprobare vizuală nouă |
| PASS | Inspecție reală desktop 1440 și mobil 390: §4.4 și §9.10/§11.1, 10 SK cu 5 celule; scroll local tabel și fără overflow global | Capturi în scratchul feliei; un timeout de captură a fost recuperat prin captură viewport explicită, nu output inventat |
| PASS | Review independent de analiză, review core cu F1–F3 remediate și re-review PASS, delivery PASS bounded; sursele revizuite recitite/verificate | Nu pretindem că reviewerii au executat întreaga suită a părintelui |
| PASS | DAG 22 noduri/35 muchii, aciclic și aceleași dependențe ca baza; 36 SL, 10 SK, 19 NS; 145 linkuri locale fără țintă lipsă | Dependency checks nu dovedesc singure implementabilitatea semantică, analizată separat |
| FAIL intermediar, remediat | Testele contractelor noi au fost întâi RED; F3 a reprodus false-green și apoi a detectat mutanții. Script de editare cu syntax error înainte de scrieri și un header match ratat, corectate | Niciun eșec de produs nu a fost mascat ca PASS |
| BLOCKED | Preflight read-only pentru gate-ul complet, exit 2: OMNIS_TEST_DATABASE_URL/OMNIS_TEST_PROJECT lipsă și UDS–TCP incompatibil | `make check/test` nu a fost lansat; nu se ocolesc gărzi și nu se adoptă WIP/DB fără acord |
| NOT-RUN | API/DB/launcher/assessments/LLM de produs/Jev/eficacitate comparativă/CI remote | G00 și gates runtime rămân deschise; testele documentare nu le închid |

**Conservare:** cele 7 fișiere dirty inițiale (6 DB/WIP + HTML-ul original) sunt byte-identice. AGENTS/DESIGN/prototip/tokenuri/pinuri/manifestele de surse și handofful anterior sunt neschimbate. Nu există modificări de cod de produs, migrări, tools instalate sau trafic de țintă. HTML-ul primit rămâne untracked/nestaged; acest registru îi păstrează proveniența și deciziile, fără a publica implicit materialul original. Procedurile reutilizabile învățate sunt păstrate în skillul de proiectare al profilului activ, nu în memoria globală de progres.

**Următoarea felie:** plan §19.2 neschimbat: integrarea explicit autorizată a fixture-ului DB/WIP, apoi launcherul instalat; noile contracte se implementează numai cu consumatorii B06/B10/B15/B18a.r/B14b. History online/debugger, alte subfamilii și tooluri candidate așteaptă gate-urile/pinurile/permisiunile lor. Comiturile sunt locale, fără push/reset/stash sau rescriere de istorie.

## Commituri ale amendamentului

| Commit | Schimbare |
|---|---|
| `98ca9a5` | docs(review): adjudicate the original skill and child-agent patterns |
| `635499c` | docs(skills): define shared specialization and execution selection contracts |
| `02f1f41` | docs(method): separate task completeness review from vulnerability validation |
| `0905f87` | docs(delivery): apply the shared skill pattern to JS and discovery |
| `f033b50` | test(docs): reject missing method contracts and weakened model requirements |
| `7b29c47` | docs(catalog): qualify candidate references in multi-package recipes |
| `2a81400` | docs(method): link rework evidence to the original obligation explicitly |
| `07ff073` | docs(readiness): point implementers to the shared skill delivery pattern |

Commitul final al registrului se identifică din Git, fără hash autoreferențial. Reverturile documentare nu sunt prezentate ca rollback de date/servicii.

## Sources

[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api
[5] https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/subagent_lifecycle.py?ref=ee5ee84a345204a3b1d6ef6ba1ab747e602867b9
