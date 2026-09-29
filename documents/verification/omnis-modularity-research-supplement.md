# Omnis — supliment: module editabile, research contextual și îmbunătățire continuă

**PROPUNERE PENTRU OK, NU AMENDAMENT APLICAT.** Bază Omnis: `4d13bf009841b5624f6941cfbfde3ccc1ed3a8f2`. Completează [review-ul Sol/OSS](omnis-upgrade-review.md), nu îl înlocuiește și nu creează un plan de implementare concurent. Operatorul cere explicit extensibilitate pentru faze/subfaze/acțiuni, skills/tehnici, cercetare după stack/versiuni, wordlists contextuale și propuneri de îmbunătățire în background prin Hermes. Arhitectura și planul canonic se modifică **numai după OK ulterior**.

Accentul acestui supliment este tehnic: ce cod păstrăm și cum îl adaptăm pentru un produs funcțional. Shortlistul nu este restrâns aici după modelul de licențiere; sursa, SHA-ul și notices rămân parte din trasabilitatea fiecărui import. Nu s-au copiat componente în runtime, instalat frameworkuri, creat cronjobs ori pornit servicii/scanări/inferențe de produs. WIP-ul DB/fixture existent rămâne separat.

## 1. Ce lipsea din review-ul anterior

1. **Un contract al extensibilității**, nu doar liste de roluri și directoare. Trebuie să putem adăuga `recon.fingerprinting` sau `mapping.auth-context` printr-o definiție și un handler/adaptor clar, fără modificarea schedulerului la fiecare tehnică.
2. **Separarea definiției de execuție:** fază/subfază/acțiune editabilă vs TaskAttempt/Action efectiv executat; un draft nou nu schimbă retroactiv un run.
3. **Un worker de research explicit**, care pornește de la identificări de produs/versiune, produce leads citate și propune metode, fără să confunde un advisory cu un finding.
4. **Wordlist ca artifact de primă clasă:** rețetă, intrări/proveniență, limite, digest și versiune, nu un fișier anonim generat de model.
5. **O buclă de îmbunătățire a produsului**, distinctă de bucla de investigație a țintei: lesson → propunere → review → evaluare → publicare.
6. **Topologie și ownership pentru background:** delegarea, review-ul nativ, curatorul și cronul Hermes au scopuri diferite. „Background” nu înseamnă automat izolat, persistent, gratuit sau read-only.
7. **Intervale de cod și teste de port**, nu doar numele repo-ului. §7 și [manifestul de reutilizare](omnis-modularity-research-supplement.reuse.json) fixează fișierul/simbolul/liniile și destinația propusă.

**Recomandarea centrală:** păstrăm supervisorul/PostgreSQL/Hermes, introducem un registru mic de componente și definiții versionate, apoi reutilizăm BBOT pentru rutarea evenimentelor/preseturi, Scrapy pentru compoziție/pipeline, WebTech/CeWL/Kiterunner pentru recon contextual și Strix pentru metodologia și contractele agenților. Nu instalăm încă un orchestrator complet.[17][18]

## 2. Model modular: ce este editabil și ce nu se confundă

### 2.1. Obiectele distincte

| Obiect propus | Rol | Ce poate modifica operatorul |
|---|---|---|
| `WorkflowProfileRevision` | Selectează faze/subfaze/acțiuni, bugete și strategia unui tip de engagement | Clonează profil, selectează module publicate, configurează/reordonează în limitele dependențelor |
| `PhaseDefinition` | Organizare și progres: recon, mapping, investigation etc. | Nume/descriere, subfaze, outputuri așteptate; asociere la enum-ul de progres existent |
| `SubphaseDefinition` | Grup coerent: JS hints, OpenAPI mapping, fingerprinting, research, wordlists | Acțiuni, input bindings, prerequisite IDs, prioritate, activare opțională |
| `ActionDefinition` | Contract executabil: handler, input/output schema, config, capabilități, limite | Parametri validați și alegerea unui handler deja instalat; nu Python/shell sau import path arbitrar |
| `TechniqueRevision` | Metoda: ipoteză, precondiții, probe/controale, dovezi, oracle și cleanup | Conținut/procedură/cazuri revizuite, cu diff și evaluare; fără a acorda singură capabilități |
| `SkillPackageRevision` | Pachetul Hermes nativ cu SKILL.md și fișiere suport | Editare draft, review/publicare; manifestul executabil rămâne `omnis.yaml` |
| `WordlistRecipeRevision` / `WordlistArtifact` | Algoritmul și rezultatul concret al selecției/generării | Surse/subseturi, reguli de tokenizare/mutație, caps și review; artifactele rezultate sunt imuabile |
| `ResearchRequest` / `ResearchResult` | Întrebarea contextuală și răspunsul cu surse | Politica de surse, obiectiv și limite; nu reinterpretarea rezultatului drept permisiune |
| `ImprovementDraft` | Propunerea de schimbare a unei tehnici, rețete sau compoziții | Accept/hold/reject, editare și comparație; publicarea citează exact revizia evaluată |
| `RunPlanSnapshot` | Materializarea versiunilor/configurațiilor selectate pentru run | Read-only în run; o selecție nouă se aplică unui run nou |

Aceste nume descriu contracte, **nu zece servicii, zece baze sau zece tabele obligatorii**. Drafturile și catalogul aparțin `settings`, snapshotul aparține `runs`, instanțele de lucru aparțin `tasks`, faptele aparțin `surfaces/evidence`. O migrare nouă este justificată numai de invariantul feliei. Nu duplicăm catalogul deja planificat în B14b.

**Un modul nu este neapărat un agent.** Parsarea HTML, extragerea versiunilor, construirea unui wordlist și validarea DTO sunt pași deterministi. Hermes este folosit unde ajută interpretarea, ipotezele, selecția și sinteza. Nu plătim un tur LLM pentru fiecare nod din diagramă.

### 2.2. Trei niveluri de modificare

- **Configurare:** schimbarea ordinii, parametrilor și selecției din module existente. Produce draft/revizie; schema și dependențele sunt verificate înainte de publicare.
- **Metodologie:** prompt, skill, rețetă, wordlist seed, tehnică și controale. Produce pachet/revizie și testele necesare, nu un nou drept de rețea sau de efect.
- **Capabilitate nouă:** handler/executor/parser/oracle/plugin nou. Cere cod trusted, teste, dependențe fixate și release; nu se creează dintr-un textarea „run this Python”.

Autorizația, fencingul, limitele de resurse, injectarea credentialelor, capture/provenance, stările UNKNOWN, validarea tehnică și Stop sunt **contracte de produs obligatorii**, nu checkboxuri de dezactivat în editor. Operatorul poate omite o tehnică opțională; omisiunea rămâne vizibilă în coverage și poate produce LIMITED. Editabil nu înseamnă că un modul poate șterge dovezi sau confirma propriul rezultat.

### 2.3. Compoziție fără limbaj de workflow arbitrar

Un `ActionDefinition` are cel puțin: `id/revision`, `handler_id`, schema de config, tipuri input/output, skill/procedure refs, `requires/provides`, predicate IDs, execution class (`PURE`, `RESEARCH_IO`, `TARGET_IO`, `MODEL`), effect/capability ceiling, deadline, limite de attempts și fan-out, retry policy și policy de invalidare a rezultatului. Handlerul și predicatele sunt rezolvate în registrul trusted din build. Nu acceptăm `eval`, `when: <Python/Jinja>`, directoare de module arbitrare ori scripturi instalate la încărcarea draftului.

Definiția unui pas nu este instanța `Action` de efect target din baseline. Un parser pur se poate reexecuta pe aceleași bytes/revizii; o repetare I/O cere readmitere și buget, iar efectul extern UNKNOWN cere reconciliere, nu retry automat. Declarația PURE nu autorizează un handler să facă I/O. Cache/dedup leagă cod/config/input digest și contextul de identitate/policy; numai date publice aprobate pot intra într-un cache de research comun, nu evidence de țintă.

BBOT oferă cod de selectare event-type/module și compoziție de preset, iar Scrapy oferă ordonare și lanțuri de procesare; preluăm subseturile, nu scannerul BBOT sau reactorul/crawlerul Scrapy.[17][18]

**DAG și buclele adaptive sunt compatibile:** prerechizitele unei generații formează un DAG. Un clue nou creează o **instanță nouă** a unei subfaze, cu `iteration`, `causation_id`, input snapshot și limite. Nu introduce un ciclu de așteptare între taskuri existente. Relațiile de cauzalitate persistate trimit spre rezultate anterioare; dedup/stagnarea/max-iterations împiedică feedbackul infinit.

Exemplu de traseu:

```text
Start → preflight → Brain + Recon → hartă/threat model → ipoteze
                                         ↑                │
                                         │        Jev: prioritizare asistată
                                         │                ↓
                                         └── delte ← specialiști → candidați
                                              ↑                    ↓
                                              └──── rezultate ← validator
                                                         │
                                        replan / chain / raport / retest

Ramuri la nevoie, NU porți obligatorii ale fiecărei investigații:
  gol de cunoaștere despre stack → Research Worker → leads → ipoteze
  discovery/fuzz justificat → Wordlist Builder → artifact → specialist

În afara pentestului activ:
  lessons aprobate → Improvement Worker → draft/review/eval → runuri viitoare
```

**Calea principală este investigația și validarea vulnerabilităților.** Research poate să nu fie invocat deloc; un indiciu suficient merge direct la specialist. Wordlist Builder se folosește numai când procedura beneficiază de discovery/fuzzing. Improvement nu trebuie să ruleze sau să termine pentru ca assessmentul să ajungă la raport.

Ordinea logică nu cere „recon complet” înainte de orice investigație. Mappingul este actualizat continuu; un output minim suficient poate permite un task, iar golurile rămân explicit în frontieră.

## 3. Fiecare fază și acțiune, gândită pentru extensie

Toate rândurile sunt **compoziții propuse** peste contractele existente. Statusul de control (`RUNNING/PAUSED/STOPPING/...`) rămâne separat de numele fazei/subfazei. `RunProgress.phase` păstrează enum-ul din baseline; adăugăm `phase_key/subphase_key/instance_id`, label și stare tipizată, nu un nou control state pentru fiecare tehnologie.

| Fază | Subfaze/acțiuni configurabile | Intrare → rezultat | Owner / închidere |
|---|---|---|---|
| Boot și instanță | Profil instalat, assets, diagnostic | Release verificat → dashboard readiness | CLI/control; nu rulează researcher, curator sau target la boot |
| Setup | Scope, identități, contexte business, profil de workflow | Draft → EngagementRevision | `engagements`; revizii/CAS; salvarea nu execută |
| Preflight | Transport, auth pozitiv, health, provider/data readiness | Revizie + capabilități → READY sau motive | `runs/identities/policy`; controalele obligatorii nu se dezactivează |
| Recon discovery | HTTP, browser, JS hints, OpenAPI, known files, crawl bounded | URL/context/evidence → observations/endpoints | `surfaces` + executori; incomplet/unsupported vizibil |
| Fingerprinting | Headers, meta/scripts, paths, versiuni din artefacte | Capturi existente → TechnologyObservation | Pas pasiv; produs/versiune observată vs inferată și contradicții |
| Mapping | Operații/params, roluri/obiecte, relații și provenance | Observații → hartă/versioned neighborhood | `surfaces/coverage`; normalizare conservatoare, raw păstrat |
| Research contextual | Advisory lookup, vendor docs, precondiții, metode relevante | Facts publicabile → ResearchResult/VulnerabilityLead | Copil Hermes nativ + egress research; lead nu este finding |
| Wordlist preparation | Select stack corpus, vocabular, segmentare, mutații, ranking | Sources/facts + recipe → artifact cu digest | Pas determinist + Jev ranking opțional; nicio cerere target prin simpla generare |
| Threat model și plan | Rubrici comune, hypotheses, task groups, specialist selection | Hartă + leads + policy → TaskProposal | Brain + compiler determinist; motive scurte și basis refs |
| Investigation/fuzz | Procedură de familie, candidate set, baseline/probe/control | Task/identitate → evidence/candidate/clue | Action broker + handler; buget/Stop/cleanup și outputs tipizate |
| Validation | Replay independent, safe control, oracle specific | Claim înghețat → verdict și gaps | `validation`; investigatorul/Jev nu pot promova singuri |
| Replan/chaining | Delta relevance, requires/provides, next hypothesis | Rezultate → task nou / path inferred ori probat | `tasks/findings`; generație nouă bounded, fără counts duplicate |
| Report/review | Template, redactare, includere, export | Claim/evidence eligibile → snapshot/export | `reports/findings`; forma este editabilă, adevărul și eligibility sunt server-side |
| Retest | Rețetă/identități/versiuni selectate explicit | Finding istoric + run nou → fixed/regressed/inconclusive | Probe noi; raportul istoric nu se rescrie |
| Cleanup/recovery/Stop | Pași declarați și adaptoare instalate | Effects/leases → quiescent ori reconciliation | Supervisor; nu hook de anulare pe care editorul îl poate scoate |
| Improvement | Lessons, public updates, propuneri și evaluare | Material aprobat → draft/review/eval/release | Settings + maintenance slot Hermes; nu mutație tacită a runului |

**Pipeline pentru rezultate:** decode → validate shape/context → normalize preserving raw → redact/project → persist evidence/domain event → notifică cititorii. Observerul UI poate eșua fără să piardă eventul DB. Un hook de policy/capture nu este un observer opțional care poate da fail-open. Erorile unui modul produc receipt de eșec și păstrează observațiile existente.

**Lifecycle de modul:** instantiate din revizie → validate config → prepare input refs → schedule/claim → admit → execute → capture/validate output → persist → notify → close/reconcile. Nu ținem o tranzacție DB deschisă cât așteptăm modelul/rețeaua. Ordinea teardownului este testată explicit; nu presupunem că un pipeline upstream închide totul secvențial invers.

## 4. Research Worker: stack/versiuni → metode și leads citate

### 4.1. Intrare minimă, nu tot engagementul

`TechnologyObservation` păstrează `product_id/vendor`, `version_raw`, versiune parsată dacă este validă, sursa detectorului și revizia semnăturii, evidence refs, observat/inferat, configurații/precondiții cunoscute și conflicte. Bannerul poate fi greșit sau backportat; nu transformăm automat „pare framework X” într-o versiune exactă.

`ResearchRequest` referă run/task/attempt/snapshot, facts aprobate pentru publicare, obiectiv și bugete. Query-ul trimis online folosește numele public al produsului/pachetului și versiunea validată, **nu URL privat, client, cookie, token, body brut, text ostil sau vocabulary personal**. Când identitatea produsului nu se poate stabili, workerul returnează ambiguitatea și ce dovadă mai trebuie.

### 4.2. Fluxul concret

1. Detectorul pasiv produce fingerprint din capturi deja existente. WebTech are separarea utilă între exchange/parser și matching; constructorul/downloaderul lui nu se folosește ca atare.[11]
2. Resolverul determinist leagă un produs/pachet/ecosistem valid; păstrează identificatorul brut și nu „repară” un token invalid pentru lookup.
3. Adaptoarele de surse caută advisories și documentație primară. OSV are query pe package/version/commit și querybatch; un mic adaptor HTTP typed este glue Omnis, nu motiv să clonăm infrastructura OSV.[5][6]
4. Workerul Hermes sintetizează intervale afectate, precondiții, versiuni fixate, contradicții, proceduri candidate și surse. Search/fetch pot folosi mecanismele native, încapsulate de un tool Omnis care validează query/URL/egress; nu expunem stock web tools nelimitate copilului.[22]
5. `ResearchResult` persistă exact sursele, data/versiunea recuperării, excerpts aprobate, hash doar dacă bytes au fost realmente obținuți, aplicabilitate și lacune. Erorile/429/sursele lipsă sunt distincte de zero advisories.
6. Brain/Jev prioritizează **taskuri deja admisibile**. Aplicabilitatea advisory este lead; findingul cere demonstrația relevantă, iar lipsa unui oracle rămâne unsupported/inconclusive.

Stări distincte: `TECHNOLOGY_OBSERVED`, `VERSION_UNCERTAIN`, `ADVISORY_MATCH_CANDIDATE`, `PRECONDITIONS_UNVERIFIED`, apoi verificarea tehnică normală. Nu numărăm CVE-uri găsite pe internet drept vulnerabilități ale engagementului și nu interpretăm „n-am găsit CVE” ca dovadă de siguranță.

### 4.3. A treia cale de egress

Baseline-ul separă provider egress de target egress; această funcție cere explicit și **research egress**. Politica autorizează serviciile de search/documentație/advisory și eventual download de date în quarantine, cu redirect/DNS/bytes/time caps. Research nu poate deveni relay către țintă, loopback/control/metadata sau destinații arbitrare dintr-un articol. Providerul efectiv/failover al căutării este vizibil și permis de data policy; o eroare de backend nu autorizează automat trimiterea query-ului altui serviciu.

Rezultatul unei pagini și codul unui PoC rămân date. Workerul poate propune o procedură sau un patch, dar nu poate instala sau executa automat codul recuperat. Evaluarea activă este o acțiune separată, în laborator și sub permisiunea ei.

## 5. Wordlists specifice stackului, nu dumpuri generate de LLM

### 5.1. Surse și algoritm

Combinăm:

- căi și parametri **observați**, forms/JS/OpenAPI și nomenclatura tehnică aprobată;
- corpusuri specifice tehnologiei, selectate și fixate, nu întreaga colecție generică;
- frecvență/tokenizare/ngrams din CeWL, pe materialul capturat local;
- mutații prefix/sufix/numerice din BBOT, cu caps și ordine deterministă;
- candidați contextuali în stil Kiterunner: metodă + cale + parametri + body/content type, nu numai un string de path.[12][17][13]

Assetnote oferă un index de liste pe tehnologii. Commitul indexului **nu fixează bytes de pe CDN**: descărcarea autorizată trebuie să producă hash, mărime, proveniență și revizie proprie. Indexul inspectat include și liste goale și corpusuri foarte mari; nu le tratăm toate ca input util sau nelimitat.[14]

`WordlistRecipeRevision` declară sursele/subseturile, tipul (`path`, `parameter`, `extension`, `route_template`, `benign_probe`), transformările, encodingul, caps, seed și criteriul de ranking. `WordlistArtifact` păstrează recipe/input digests, transform/provenance per candidat, counts înainte/după filtre, motive de excludere, truncation și ordinea exactă.

**Separări obligatorii:** wordlist de content discovery ≠ password list ≠ payload pack ≠ tehnică. Research-ul după stack nu implică credential guessing. Parametrii și numele de rută nu cer includerea valorilor query, numelor persoanelor sau tokenurilor. Excludem PII/secrete înainte de export/model; vocabularul privat neaprobat rămâne local.

### 5.2. Generarea poate fi adaptivă fără hot-swap

Într-un run, rețeta și codul generatorului sunt fixate. O observație nouă poate produce **un artifact nou** și un nou task care îi citează digestul; nu modifică wordlistul deja consumat de un attempt. Același principiu permite Brainului să creeze taskuri noi din modulele aprobate fără să schimbe catalogul.

Jev poate ordona candidați sau evalua relevanța unui corpus, dar nu inventează provenance, nu acordă scope și nu înlocuiește feedbackul măsurat al testului. Rankingul se evaluează prin descoperiri unice utile/requesturi, nu prin dimensiunea listei.

### 5.3. Execuție și calibrare

Builderul este pasiv; fuzzerul este un executor separat. Înainte de dispatch: metodă/origin/path/identity/effect/budget aprobate. Controlul soft-404 este pe operație/prefix/metodă/identitate/epoch și se reface la drift. 401/403 pot semnala existența unei suprafețe și nu se șterg global ca „zgomot”. Un rezultat filtrat păstrează motiv/evidence, nu dispare din audit.

Preluăm din Kiterunner schema contextuală și modelul baseline, **nu** întreg preflightul: sursa include și metode cu mutație. Copierea literală ar contrazice un recon read-only; adapterul produce acțiuni individuale admisibile.[13]

## 6. Hermes în background: trei roluri, un singur ownership

### 6.1. Ce reutilizăm nativ

Pinul Omnis/instalat inspectat este `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` / baseline 0.21.5. Paginile live sunt referința curentă, dar nu dovedesc aceeași implementare la acest pin. Intervalele din tabel sunt la SHA-ul fixat. **HM01–HM08 identifică mecanismele acestui supliment; nu sunt subprobele canonice G02/H01–H08 din plan.**

| ID | Mecanism și sursă exactă | Integrare recomandată |
|---|---|---|
| HM01 | `tools/delegate_tool.py:187–205,234–248,263–285` — copil nativ, context/tool resolution | Research per engagement, TaskAttempt/inbox Omnis; cercetătorul intră în plafonul de copii, cu prioritate pentru validator |
| HM02 | `agent/subagent_lifecycle.py:219–229,245–280,303–345,360–387`; `hermes_cli/plugins.py:391–396` | Suprafață nativă opțională pentru plugin cu parent activ; nu runtime nou, nu presupunem worker durable după restart |
| HM03 | `agent/background_review.py:1078–1118,1137–1183` — whitelist și `extra_tools` | În maintenance, tool îngust propus `omnis_propose_improvement`; sesiunea conține doar lessons aprobate, nu transcript brut de țintă |
| HM04 | `agent/curator.py:860–876,894–967,1057–1079` — housekeeping și consolidare opt-in | Refolosim organizarea/review-ul într-o bibliotecă de lucru; curatorul nu publică în release și nu este researcher web implicit |
| HM05 | `tools/skill_manager_tool.py:627–677` — write approval/pending replay | Staging/diff nativ ca intrare editorială, nu certificare/publicare. Release Omnis read-only și publisher separat |
| HM06 | `cron/scheduler.py:2420–2439`; `cron/scheduler_prompt.py:20–34` | Cron nativ pentru cadență periodică. Inițial preferăm `no_agent` pentru enqueue de maintenance; inferența începe numai după admission Omnis |
| HM07 | `hermes_cli/plugins.py:456–498,993–1022` — tools și skill packages | Plugin subțire Omnis, catalog/propuneri și research broker; fără fork core pentru fiecare tehnică |
| HM08 | `tools/async_delegation.py:258–300` — recovery/unknown | Reconciliere rezultate/attempts; notificare acceptată nu înseamnă tur terminat sau rezultat consumat |

HM01/HM02 folosesc suprafețele native, dar contractele de mapping și oprire Omnis rămân de exercitat.[25][26]

HM03–HM05 sunt mecanisme reale de review/mentenanță/staging, nu un pipeline gata certificat de auto-îmbunătățire pentest.[27][28][29]

HM06/HM07 acoperă cadență și extensii, nu autoritatea de run.[30][31][32]

HM08 permite reconcilierea completărilor, nu persistența unei execuții în curs sau reluarea automată a unui copil întrerupt.[33]

### 6.2. Modelul minim recomandat pentru MVP

**Research Worker:** copil al runtime-ului de engagement, cu facts minimizate, tools Omnis și buget propriu în bugetul runului. Rezultatul poate veni în timp ce alți pași continuă; un task obligatoriu pentru validare nu așteaptă nelimitat internetul.

**Improvement Worker:** după un rezultat relevant sau la închiderea runului, se creează o propunere/lesson în DB. Materialul aprobat este procesat într-un **slot de mentenanță serializat după quiescență**, folosind Hermes nativ. Nu copiem OAuth grants, nu activăm un al doilea writer concurent pe același home și nu expunem arhivele altor engagementuri. Aceasta este excepția îngustă propusă la interdicția auto-learning, nu eliminarea ei globală.

**Research periodic:** după integrarea de mai sus, cronul Hermes poate colecta update-uri publice și enqueua o cerere de maintenance. Nu adăugăm APScheduler/Celery. Recomand un job `no_agent` cu wrapper trusted și output/job ID tipizat, apoi admission și execuție prin slotul de produs; nu cron LLM direct pe home-ul activ. Acest adapter este propus și cere probă la pin, nu există deja în Omnis.[3][23]

**Curator:** pentru redundanță/drift/organizarea bibliotecii de lucru. Nu trebuie să caute automat CVE-uri și nu are implicit web access în implementarea inspectată. Îmbunătățirea unei metode este propunere evaluabilă, nu simplă arhivare bazată pe `use_count`.[2][28]

### 6.3. Limite native importante, verificate în sursă

- `skills.write_approval` are o cale **fail-open la import failure** în `skill_manager_tool.py:627–634`. Prin urmare release RO/publisherul Omnis nu pot fi înlocuite cu acel flag.[29]
- `curator --dry-run` elimină tranzițiile deterministe, dar la consolidare adaugă un banner în prompt fără a elimina toolurile mutatoare. Nu este sandbox de preview. Backupul la pin este best-effort și nu certifică rollback tranzacțional.[28]
- Cronul la pin construiește agentul cu **`skip_memory=False`**, deși unele instrucțiuni locale spun altceva. Toolset/config/MCP/memorie trebuie verificate în slotul privat; nu presupunem izolare din eticheta „cron”.[30]
- `_parse_wake_gate` returnează wake pentru output gol, JSON invalid, `{}` sau `"false"` string; numai booleanul exact `false` îl oprește. Părintele a reprodus șase cazuri offline. Wake gate este optimizare, nu frontieră fail-closed de buget/autorizație.[31]
- Background review primește snapshot/digest al conversației. `skip_memory` nu înseamnă că acel snapshot este sanitizat. Îl folosim pe lessons aprobate într-o sesiune dedicată, nu ca export implicit al runului.[27]
- `ctx.subagent_lifecycle` are nevoie de parent activ și limite pe câmpurile suportate. Un handle sau un câmp de dataclass nu dovedește reatașare după restart ori structured result funcțional. Folosim întâi adaptorul stdio/delegarea deja alese.[24][26]

Aceste limite nu sunt motive să rescriem Hermes; sunt punctele exacte unde Omnis trebuie să păstreze controlul de produs și să testeze adaptorul.

### 6.4. Stop separat pe domenii

| Comandă | Oprește | Ce păstrează |
|---|---|---|
| Stop engagement | Taskuri/research legate de caz, noi dispatchuri target/model, wake neadmis | Evidence și propunerile deja persistate; remote in-flight rămâne urmărit/UNKNOWN |
| Stop maintenance | Admitere de jobs research/îmbunătățire și execuțiile de maintenance active | Drafturi/review-uri și release-uri publicate; pause schedule nu este singură dovadă de oprire |
| Stop instance / emergency | Ambele domenii și procesele proprii | Date și receipturi; la restart fără autoresume de efecte |

Programul de mentenanță poate exista după Stop engagement, dar nu moștenește grantul de inferență sau date al cazului oprit. Până la un amendament separat, **nu propun curator continuu simultan cu engagementul**: intră în conflict cu writerul unic actual. Webul arată `WAITING_FOR_RUNTIME_SLOT`, nu „rulează” fictiv.

## 7. Codul exact de preluat și locul adaptării

**Regulă de citire:** intervalul este originea fixată a portului/patchului, nu promisiunea că fișierul se lipește neschimbat. `COPY/ADAPT` păstrează implementarea utilă și înlocuiește seam-ul de runtime/storage; `PORT` păstrează algoritmul în Python; `DATA` păstrează corpus/schema. Manifestul asociat include URL cu `#L…`, SHA de fișier/fragment, destinație și test. Nu executăm hookuri sau exemple la import.

### 7.1. Strix — pin `ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2`

| ID | Fișier / linii / simbol | Ce luăm efectiv → adaptare Omnis |
|---|---|---|
| S01 | `strix/agents/prompt.py:20–71,74–126` — `_resolve_skills`, `render_system_prompt` | Compoziție ordonată/dedup rol–mod–skills → `integrations/hermes/src/omnis_hermes/prompt_bundle.py`; resolver de release Omnis, eroare explicită în loc de prompt gol |
| S02 | `strix/skills/__init__.py:159–175,215–239,264–300` | Parser frontmatter/validare ID și ramurile utile de body load → `settings/skill_catalog.py`; fără global shadowing/silent skip, Hermes rămâne loader |
| S03 | `strix/skills/coordination/root_agent.md:28–40,67–96` | Recon-first, model comun, amendments și handoff → skillul Brain/engagement; taskuri cu evidence refs și caps |
| S04 | `strix/tools/threat_model/tools.py:53–58,269–271,327–389,418–459` | Rubrici/câmpuri/checks → `runs/threat_model.py`; required sections structurate, nu substring ca oracle; Postgres append-only în loc de JSON globals/clear amendments |
| S05 | `strix/tools/agents_graph/tools.py:498–548,614–672` | Contract objective/skills și summary/findings/open_items → `tasks/handoffs.py`; native Hermes binding și refs, nu coordinator Strix |
| S06 | `strix/tools/load_skill/tool.py:11–36` | Format de referință on-demand → proiecție/nativ `skill_view`; încărcarea nu schimbă system prefix și nu acordă tools |
| S07 | `strix/tools/output_store.py:47–73,76–140` | UTF-8 prefix/suffix/head-tail și notice → `evidence/preview.py`; notice inclus în cap, artifact IDs în loc de raw shared workspace |
| S08 | `strix/report/writer.py:35–66,223–361` | `csv_safe`, `safe_fence`, formatter Markdown → `reports/render.py`; numai snapshot eligibil, HTML escaping separat |
| S09 | `strix/agents/factory.py:611–644` | Collision check/registry pattern → `tasks/module_registry.py`; nu global tools pentru toți copiii și nici Shell/Filesystem capability |
| S10 | `strix/skills/analysis/counterevidence.md:16–39,100–126,145–185` | Closure/proof gaps/reopen/counter-case → metodologie validation/evidence; separă source-supported de runtime-confirmed |

Toate aceste ancore au fost confruntate cu clona locală fixată. Core/execution, mailbox și SDK Strix sunt referințe de flux, **nu module noi de runtime în Omnis**. Biblioteca completă și cele 29 de dispoziții rămân în review-ul anterior; aici concretizăm primul lot de cod și contracte.[15]

### 7.2. BBOT și Scrapy — compoziție modulară

BBOT: `a6fb827bb144cdb85b52e142a4d6e14ed5f94b69`. Scrapy: `5d789b24f994bcdfca97c34d976c73739e064849`. Prefixele de destinație sunt `api/src/omnis/`, cu excepția executorului indicat. Funcțiile/testele au fost verificate programmatic prin AST și hash: 43 referințe pentru aceste nouă unități.

| ID | Sursă exactă | Subset și destinație | Probă necesară |
|---|---|---|---|
| M01 | BBOT `core/event/base.py:919–1007,571–593` — event JSON/id/uuid/hash | Envelope/provenance și content identity vs occurrence → `modules/surfaces/events.py` | Redelivery idempotent; două observații distincte păstrate; parent străin refuzat |
| M02 | BBOT `modules/base.py:828–942` — pre/postcheck | Event-type routing și filtre cu motive → `modules/tasks/module_registry.py`, același registru S09 | Doar subscriberii admiși; filtru nu acordă autoritate; replay nu dublează taskul |
| M03 | BBOT `scanner/preset/preset.py:340–533,569–579,961–1003` | Selecție/dependencies/exclusions din merge/bake → `modules/runs/plan_snapshot.py` | Missing/cycle/excluded dependency refuzate; snapshot independent de draft |
| M04 | BBOT `scanner/preset/validate.py:65–93,161–170,195–291`; `core/config/models.py:322–344` | Agregare/classificare erori + config schema → `modules/settings/skill_catalog.py` | Erori per câmp, strict/no secrets; fără exec de Config și fără fallback la dict |
| M05 | BBOT `core/helpers/wordcloud.py:89–147,191–284`; `core/helpers/misc.py:1334–1358` | Frecvență/mutații prefix-sufix/numerice → `modules/surfaces/wordlists.py` | Ordine/digest stabile, caps, provenance; fără DNSMutator/fetch implicit |
| M06 | Scrapy `utils/conf.py:20–63` — `build_component_list` | Ordonare/disabled/collision → `modules/tasks/component_order.py` | Priorități strict int bounded, tie-break stabil, core hooks nedezactivabile |
| M07 | Scrapy `pipelines/__init__.py:57–66,77–80`; `middleware.py:131–153` | Chain sync/async de rezultate → `modules/surfaces/ingestion.py` | Ordine A→B; output invalid nu persistă ca succes; raw/receipt de eșec păstrate |
| M08 | Scrapy `core/downloader/middleware.py:53–64,108–163,200–230` | Request/result/error ordering → `executors/http/src/omnis_http/action_hooks.py` | A/B înainte, B/A după; retry/redirect reautorizate; deny/cancel nu devin succes |
| M09 | Scrapy `utils/signal.py:165–214`; `signalmanager.py:21–49` | Fan-out pentru cititori/telemetrie → `transport/events.py` | Observer defect nu pierde DB event; recuperare din cursor; nu permission/inbox gate |

Preluările BBOT economisesc cod de selecție/config/provenance; nu copiem `bake()` care poate modifica `os.environ` și reuni scope. Validarea Omnis folosește schema unui handler trusted, nu `_exec_config_class` și fallbackul upstream la dict.[17]

Preluările Scrapy economisesc compoziția lanțurilor, nu persistența și autoritatea. Signals nu sunt un event store; lifecycle-ul upstream nu garantează teardown serial invers. Nu adăugăm Twisted doar pentru aceste funcții.[18]

### 7.3. Fingerprinting, wordlists și task grouping

| ID / pin | Sursă exactă | Ce adaptăm → consumator |
|---|---|---|
| R01 WebTech `7141d3542b650df9f984deba6213e2911ee7b9d1` | `webtech/target.py:31–53,195–203,216–274` | Parse pattern și checks pe capturi → `surfaces/fingerprints.py`; grupul de versiune real, eroare pe pattern invalid, timeout regex, fără requests |
| R02 același pin | `webtech/parser.py:8–27` — `WTParser` | Meta/script-src extraction → același modul; inline JS nu este executat |
| R03 CeWL `ca01aeae1c77bb086ef757611dea6377b8d1168b` | `cewl.rb:760–781,1168–1203,1236–1245` | Tokenizare path/frecvență/ngram/sort → `surfaces/wordlists.py`; port Python, păstrează raw/Unicode/short version tokens, fără spider/parole |
| R04 Kiterunner `7d5824cda9a2eef86d8d18b05b713d7e260f34d2` | `pkg/proute/route.go:13–30,66–137` | Route schema și rendering contextual → `surfaces/route_candidates.py`; înlocuiește defaulturi arbitrare cu inputuri tipizate |
| R05 același pin | `pkg/kiterunner/preflight.go:15–38,193–245` | Baseline/wildcard model → `surfaces/response_baselines.py`; metodă/identitate/epoch/variance, nu suita upstream de mutații |
| R06 Assetnote `6dea231f4cbd356a637851b1c13b83de4da00adb` | `data/technologies.json:1–109` | Index corpus per tehnologie → catalog de surse; snapshot/hash propriu al bytes downloadate, nu HTML Download executat |
| R07 Shannon `327c10fd90a6186a9f035b4b6ddb5bbba1839e92` | `apps/worker/src/ai/reconciliation/task-formation-schema.ts:11–23,33–122,181–209` | Schema de grupare și refuzul labelurilor duplicate/străine → `tasks/grouping.py`; port Python, fără Temporal/pi; observațiile negrupate nu dispar |

WebTech/CeWL oferă cod reutilizabil de extracție; în ambele cazuri păstrăm funcțiile pasive, nu transportul sau procesarea de metadate personale.[11][12]

Kiterunner/Assetnote oferă context de rută și corpus tehnologic; nu importăm automat corpusul sau scannerul complet.[13][14]

Shannon este acum inclus în shortlistul **tehnic de port** pentru acest seam, față de rolul reference-only din primul review. Nu înlocuiește Hermes și nu preluăm pipeline-ul lui complet.[16]

### 7.4. Ordinea efectivă a importurilor

1. Strix S01/S02/S03/S05/S10 și subsetul inițial de skills, cu unit tests; primul consumator este copilul Hermes.
2. M02/M03/M04/M06/M07, numai cât cere primul profil recon/mapping; reaplicăm checks de plan deja selectate din PentestGPT în review-ul anterior, nu un compiler concurent.
3. R01/R02 și researcher cu adapters de surse; M05/R03/R06 construiesc wordlisturi offline, apoi fuzzerul deja ales le consumă prin broker.
4. M01/M08/M09 odată cu pipeline/proiecții/effects; S04/S07/S08 odată cu consumatorii de threat model/evidence/report.
5. R04/R05/R07 pentru recon contextual și reducerea taskurilor redundante, după proba pozitivă/negativă a seam-ului. Background maintenance se activează numai după draft/review/publication boundary.

Nu toate unitățile trebuie importate înaintea primului finding. Păstrăm implementarea upstream acolo unde economisește muncă, dar nu împachetăm o platformă întreagă pentru o funcție mică. Lucrul nou inevitabil este glue-ul de DTO, persistență, authority și UI Omnis.

## 8. Îmbunătățirea tehnicilor: pipeline și informații editabile

`ImprovementDraft` conține: target package/profile ID, base digest/revision, motiv și failure category, surse, fișiere complete/diff, efecte/capabilități schimbate, expected benefit, teste propuse, cost estimat ori UNKNOWN. Poate propune și o subfază nouă, un overlay de framework sau altă rețetă de wordlist, nu doar rewording SKILL.md.

```text
lesson aprobat / sursă publică nouă
  → ImprovementDraft
  → review de conținut și schimbare de capabilitate
  → teste statice + fixtures vulnerable/fixed/benign + regresii
  → aprobare pentru digestul evaluat
  → publish immutable
  → selectare numai pentru runuri noi
```

Draft/review/eval sunt stări editoriale. Metodologia, readinessul toolurilor, validarea pe fixtures, benchmarkul și permisiunea per run sunt **axe separate**, nu o scară care acordă automat toate drepturile. O publicare methodology-only este posibilă, dar nu activează execuția unei familii.

- Editarea după review/eval invalidează acele acceptări materiale.
- Un model nu își aprobă singur patchul; Jev poate critica/recomanda evaluarea, nu publica.
- Evaluarea folosește fixtures și buget aprobate. A îmbunătăți un skill nu este autorizație de a rula teste active pe engagementul vechi.
- Cross-run lessons sunt exportate prin data policy: nu requests/responses brute, secrete, hărți de clienți sau soluțiile corpusului held-out.
- Rollback selectează o versiune anterioară pentru runuri noi; revocarea activă face Stop/fencing. Nu rescrie istoricul rapoartelor.
- Măsurăm usefulness per procedură și task: misses/FP, reproducere, requests, timp/cost și intervenții. Numărul de views sau opinia curatorului nu certifică îmbunătățirea.

## 9. Amendamente exacte pentru OK-ul următor

Fișierele/liniile sunt cele ale baseline-ului nemodificat din această sesiune. Textele de mai jos sunt **propuneri de inserat/înlocuit**, nu schimbări deja aplicate. Noul plan rămâne cel canonic după amendare; nu implementăm din două planuri concurente.

### 9.1. Arhitectură

| Locație | Amendament concret |
|---|---|
| `Omnis_MVP_Architecture.md:25–40` (§2) | Adaugă A15: „Definiții tipizate/revizionate pentru faze/subfaze/acțiuni și pachete; execuția folosește registry trusted + RunPlanSnapshot, nu workflow DSL general.” Adaugă A16: „Research per engagement și maintenance editorială sunt domenii de lucru distincte, executate prin Hermes nativ, cu ownership/bugete/date separate.” |
| `:59–85` (§3) | Adaugă research egress separat de target/provider; query projection, origins/fallback, download quarantine și lipsa accesului către control/target. Niciun fetch din articol nu lărgește scope. |
| `:97–99,160–176` (§4) | Separă catalog releases RO, drafts, research artifacts și maintenance workspace fără case mounts; Settings publică/readback revizii, nu editează fișiere active ori profilul personal. |
| `:197–221,243–269` (§5) | Păstrează auto-learning off pe runtime-ul de engagement; permite explicit Research Worker și slot de maintenance după quiescență. Definește native calls/plugin tools și G-HERMES-BOUND; nu „pornește curatorul global”. |
| `:271–308` (§6) | Adaugă registry selection, instanțe de subfază/generație și cauzalitate; input/event dedup, limits și un singur wake owner. Tabel Stop run/maintenance/instance; progresul fazei nu controlează starea runului. |
| `:310–336` (§7–8) | ActionDefinition cere capabilities/effect/identity context; wordlists și research produc date, nu permits. Login funcțional și auth testing rămân operații diferite. |
| `:342–388` (§9) | Extinde contractele existente cu profile/package draft revisions, RunPlanSnapshot refs, TechnologyObservation, ResearchResult, WordlistArtifact și ImprovementDraft. Refolosește Task/Attempt/Inbox/Evidence; nu face tabele pentru orice concept de pe diagramă. |
| `:409–419` (§10) | Extinde ModelProjection și retention inventory la queries, research, lesson export, pending writes, cron outputs și curator reports/backups. Digest/citat doar din bytes disponibili; redactarea este înainte de provider. |
| `:423–446` (§11) | Recon/mapping/fingerprinting/wordlist/research sunt subfaze independente cu provenance; advisory matching separat de finding, coverage promisiune vs module disabled și benchmark per recipe/technique revision. |
| `:557–600` (§12) | Owners: settings=definiții/publicare; runs=snapshot/progress; tasks=registry/scheduling; surfaces=fingerprints/wordlists/relations; evidence=artifacts; integrations/hermes=runtime; integrations/research=adapters. Introduce fișiere doar cu primul consumator. |

**Text normativ central propus pentru A10/§6:** „Definițiile și codul selectate sunt imuabile pe run; instanțele de task, observațiile, research results și artifactele generate pot crește adaptiv sub acea definiție. Orice attempt citează exact inputurile și reviziile consumate. Modificarea unui draft nu schimbă un attempt activ; skip/cancel este comandă auditată, nu ștergerea unei obligații.”

### 9.2. Planul de implementare

| Locație în `Omnis_Implementation_Plan.md` | Delta propusă, fără întârzierea primei dovezi |
|---|---|
| §4 L50–69 și §19 L340–344 | P0.4 rămâne launcher/G00; importurile inerte pot fi pregătite în paralel, dar nu declară G00. Nu condiționăm primul finding de editor general sau cron. |
| §6 L93–99 | B02/B04 primesc selectarea profilului publicat și revizia lui; draftul engagementului nu poate avea handler neinstalat sau schema necunoscută. |
| §7 L103–124 | B06 primește registry/context/debrief minimal și Research task type; subprobele canonice G02/H03, G02/H04, G02/H06, G02/H08 și ModelProjection acoperă și researcherul. |
| §8 L128–130 | Catalog read-only include recipe/profile și readiness; provider/pachet minim rămân obligatorii. Jev păstrează integrarea din review-ul anterior. |
| §9 L134–148 | B07/B08 capturează input/module revision, provenance, subphase progress, receipturi și oprirea tuturor dispatchurilor relevante. |
| §11 L166–190 | Descompune B10 în B10a capture/import, B10b map/fingerprint, B10c research, B10d wordlist/baseline. Pentru G05a se cer doar B10a/b și inputs necesare fixture-ului; c/d intră cu primul consumator justificat, nu toate înainte de BOLA. |
| §12 L196–202 | Extinde B14b cu recipe/profile/technique drafts, validate/diff/publish; subfelie B14c ImprovementDraft/review/eval linkage. Un catalog, nu al doilea package manager. |
| §13 L206–212 | B15 promovează discovery contextual și wordlists specifice; nu numără candidate routes ca endpointuri observate. |
| §14 L216–224 | B18a/G-LOOP include re-entry bounded și research result consumat o dată; B19 verifică Stop/Crash și maintenance slot. |
| §15 L228–263 | B20 compară recipe/technique releases; B21 adaugă maintenance lifecycle, retenție și rollback; cron periodic urmează numai după ownership/egress/draft gates. |
| §16 L280–291 | Adaugă subrânduri UI pentru profile editor, technique/wordlist review, Research activity și Improvements; păstrează navigarea acceptată. |

### 9.3. UI și contracte de readback

Nu adăugăm obligatoriu un workflow canvas. În Settings, extindem Skills/Runtime cu **Workflow profiles**, **Techniques**, **Wordlist recipes**, **Research sources** și **Improvements**; în engagement afișăm planul efectiv și subfazele în stream/coverage. Componentele noi cer inspecție vizuală separată, nu refacerea cockpitului.

| Suprafață / comandă propusă | Owner / date | Probe de acceptare |
|---|---|---|
| `GET /api/v1/settings/action-catalog` | Registry installed + schema/revision/readiness | Metadata exactă, fără căi/credentiale; unknown handler nu apare available |
| Draft/validate/publish `settings/workflow-profiles` | Settings revisions + immutable release | Clone/edit/order/readback; dependency/cycle/core disable/stale revision refuzate |
| Draft technique/wordlist sub `settings/skills` | Unicul pachet `omnis.yaml` + provenance | Diff întreg; edit după eval invalidează acceptarea; run activ neschimbat |
| Research sources/config și activity | Sources policy + ResearchResult/task refs | Query sanitizat și provenance; eroare/fallback/UNKNOWN vizibile; fără target URL scurs |
| `GET /runs/{run}/plan` și summary/events | RunPlanSnapshot + subphase instances/cursor | Aceeași revizie, trigger și motiv; refresh/replay fără counters duplicate |
| Improvement list/diff/review/eval/publish | ImprovementDraft, evaluator receipt, release digest | Autorul nu autoaprobă; material stale/failed eval blochează publish; exact readback |
| Maintenance pause/stop/status | Job admission + native execution ref | Schedule paused ≠ worker stopped; no new dispatch; results deja persistate rămân |

Rutele și payloadurile sunt **propuse**, nu implementate. Toate mutările păstrează session/CSRF/ownership, expected revision, command ID/idempotency și readback al exactei ținte. Publicarea unui handler nou nu se face prin aceste formulare: este release de cod.

### 9.4. Stack și fișiere

`Omnis_Stack_Baseline.md` §5–8 trebuie să declare separat: ce cod se portează fără dependency upstream, ce pachet/executabil rămâne nemodificat și ce surse/corpusuri au pins proprii. Nu adăugăm BBOT+Ansible, Scrapy+Twisted, Ruby/CeWL ori Temporal/pi în runtime doar pentru subseturile din §7. Pydantic/asyncio existente sunt suficiente pentru registrul inițial; transporturile și modelele rămân cele alese.

Layout propus, creat incremental:

```text
api/src/omnis/modules/settings/    # catalog/drafts/review/publish
api/src/omnis/modules/runs/        # compiled profile/snapshot/progress
api/src/omnis/modules/tasks/       # registry/selection/handoff/grouping
api/src/omnis/modules/surfaces/    # ingestion/fingerprint/wordlist/baseline
api/src/omnis/modules/evidence/    # artifacts/projections/availability
integrations/hermes/              # native runtime + proposal/research tools
integrations/research/            # pinned public-source adapters, no target authority
skills/<package>/SKILL.md
skills/<package>/omnis.yaml       # unica definiție executabilă a pachetului
skills/<package>/references/      # metodologie adaptată cu provenance
skills/<package>/templates/recipes/ # date tipizate revizuite, nu cod arbitrar
third_party/<source>/<revision>/  # proveniență/copii selectate, neîncărcate implicit
```

Nu se creează acum aceste directoare sau scaffolduri. Generarea recipe/profile draft de către agent produce date în workspace-ul Omnis, nu `git commit` automat din backend.

## 10. Felii de implementare după aprobare și probe

### Prima felie modulară observabilă

Două subfaze recon/mapping și trei acțiuni **inerte** pe observații sintetice, conectate la Settings/API/PostgreSQL. Operatorul schimbă un parametru/ordinea permisă, publică, citește noua revizie și vede un rezultat diferit pentru runul nou; runul deja fixat produce același rezultat. Aceasta probează extensibilitatea, nu eficacitatea pentest.

### Ordine propusă

Lista următoare descrie incremente care pot avansa în paralel, **nu un lanț în care research/wordlists blochează primul investigator**. Pe calea critică intră numai componentele necesare primei proceduri; B10c/d, editorul și maintenance rămân independente până la consumatorul lor.

1. Amendamentele normative de mai sus, cu readers HTML regenerate și review; un commit coerent per decizie.
2. Import Strix delimitat și registry/profile minimal, fără editor complet; prima felie inertă.
3. Fingerprint pasiv → ResearchResult citat → wordlist artifact pe date sintetice; niciun fuzzer pornit automat.
4. Integrare cu reconul și primul investigator prin broker; aceeași evidență în map/stream și aceeași comandă Stop.
5. Draft→review→eval→publish pentru o îmbunătățire reală, demonstrată cu control sigur; Jev advisory rămâne măsurat.
6. Maintenance slot și abia apoi cron public research; lipsa slotului disponibil produce queued, nu al doilea writer.

### Gate-uri suplimentare, atașate celor existente

| Gate propus | Pozitiv | Negativ obligatoriu |
|---|---|---|
| G-MODULE | Profil valid compilat, acțiune nouă instalată utilizată fără schimbare scheduler | Unknown handler/schema, dependency lipsă/ciclu, core hook disabled, config cu cod/expression |
| G-REVISION | Publicare revizie nouă pentru run nou; input artifact nou în run vechi sub rețetă fixată | Hot-swap code/prompt/catalog, stale review, artifact suprascris |
| G-RESEARCH | Facts publicabile → sursă primară → lead cu precondiții | Versiune ambiguă, query cu secret, redirect off-policy, backend fallback neaprobat, sursă lipsă |
| G-WORDLIST | Rețetă deterministă/caps/provenance; randament comparat pe fixture | PII/token, listă goală, corpus oversized, duplicates, absolute origin injectat, baseline drift |
| G-IMPROVE | Draft evaluat + aprobat la același digest → release exact | Autopublish, import failure approval, symlink/path escape, test artifact din altă revizie, held-out leakage |
| G-HERMES-BOUND | Research/maintenance cu inventar native și slot exclusiv | Cron memory/MCP contaminare, malformed wake, dry-run mutator, cancel fără quiescență |

Aceste gate-uri nu înlocuiesc subprobele canonice G02/H01–H08 sau G03/G-DATA și nici nu transformă importul într-o capabilitate certificată. Primele introduc seam-uri necesare consumatorului; nu devin un mega-gate înainte de BOLA.

## 11. Verificări efectuate și limite

- Review-uri independente pe sursele modulare și pe Hermes; parent a recitit mecanismele decisive și a verificat prin Git/AST/hash cele 43 de referințe BBOT/Scrapy.
- WebTech, funcții pure extrase din sursa inspectată: trei controale pozitive; patternul malformat reproduce `IndexError`, deci parserul adaptat trebuie să-l refuze explicit. Importul runtime-ului/downloadului nu a fost executat.
- CeWL, numai funcția de extracție path executată cu Ruby stdlib: două controale; `/api/v1/orders.json` produce `api/orders` ca tokenuri și pierde `v1` din cauza lungimii minime. Omnis trebuie să păstreze raw și tokenizarea configurabilă. Nu s-a lansat spiderul.
- Shannon, subset pur transpiled local: trei controale pentru grup valid, label duplicat între grupuri și label necunoscut. Prima extracție a omis acolada de la L122 și a eșuat înainte de execuție; intervalul a fost corectat și proba a trecut. Nu este typecheck/suită Shannon sau integrare Omnis.
- Hermes `_parse_wake_gate`: șase controale reproduse de parent pe funcția extrasă din pin, fără importarea runtime-ului; malformed output trezește conform implementării, nu este barieră de autorizare.
- Cele de mai sus sunt probe inerte/extrageri de cod, **nu suite upstream, scanări, rulări Jev ori dovadă de eficacitate**. Testele de integrare din manifest sunt propuse.
- Arhitectura/planul/UI/stackul canonic și cele șase căi WIP DB/fixture sunt neatinse; G00 și CI remote rămân în starea deja documentată. Nu există cron, provider cost sau auto-learning nou activat de acest review.

## 12. Run Omnis de referință — pentestul rămâne fluxul principal

**Walkthrough ilustrativ al produsului propus, NU run executat sau finding real Omnis.** P0.4 este încă fundație/control. Scenariul folosește o aplicație Web/API proprie de laborator, două identități și reguli de acces aprobate, cu pachetele BOLA, reflected-XSS și traversal-canary disponibile. Arată MVP-ul adaptiv din review-ul principal; nu presupune că SQLi/SSRF/RCE sunt deja implementate.

### 12.1. Cine există într-un run

| Componentă | Pornire și responsabilitate |
|---|---|
| Supervisor Omnis | Cod determinist: admission, bugete, ownership, Stop, persistență și finalizare; nu agent LLM |
| Brain Hermes | Strategia campaniei, ipoteze, selecție/delegare, interpretarea rezultatelor și replan; un părinte logic pe durata runului, nu inferență continuă când așteaptă |
| Recon Agent | Copil nativ pentru descoperirea/interpretarea suprafeței; poate primi un task nou, îngust, după un indiciu sau schimbarea contextului auth |
| Investigatori pe familie | Copii creați când există o ipoteză potrivită: Access Control/BOLA, XSS, Traversal etc.; nu toată biblioteca lansată la început |
| Validator | Copil/attempt/context nou pentru replay și controale; verdictul tehnic este aplicat de serviciul/oracle-ul Omnis |
| Research Worker | Copil opțional pentru o lacună concretă de cunoaștere; nu prerechizit pentru orice atac și nu owner al planului |
| Jev | DecisionAdvisor apelat la puncte utile de selecție/triage/stagnare; nu agent pentester și nu înlocuiește Brainul |
| Mapping, fingerprint, wordlist, crawler/scanner | Module/adaptoare; pot executa multă muncă fără un nou agent LLM |
| Reporting | Renderer din snapshot; narațiune LLM numai dacă este utilă, fără reporter obligatoriu per finding |
| Improvement/curator | Nu ocupă un rol în calea critică a pentestului; lessons/drafturi pentru îmbunătățirea runurilor viitoare |

Plafonul propus rămâne **un copil în prima probă, apoi maximum doi copii nativi activi, inclusiv validatorul și eventual researcherul**, pe lângă Brain. Un specialist care predă rezultatul eliberează slotul; validatorul nu apare pe ascuns ca al treilea copil. Research așteaptă un slot când investigația/validarea au prioritate. Concurența agenților nu înseamnă trafic target nelimitat. Extinderea poolului este separată de acest walkthrough.

### 12.2. Firul principal și revenirile, pas cu pas

1. **Setup/Start/preflight:** operatorul oferă URL, scope, identități/reguli, bugete și profil; preflightul verifică funcțional contextul. Nu există încă un swarm și nu rulează improvement. După READY/Start, pașii admiși se execută autonom în limitele stabilite, nu cer confirmare la fiecare citire benignă.
2. **Recon inițial:** Brain deleagă un task de inventar. Crawlerul, browserul și parserele observă căi, operații/params și fluxurile aplicației. În exemplu apar o API de comenzi, căutare și download. Mappingul persistă fapte/identități/proveniență; Recon predă și ce nu a putut vedea. Nu așteptăm un inventar perfect înaintea primei ipoteze utile.
3. **Threat model și ipoteze:** Brain leagă roluri/obiecte/suprafețe și creează ipoteze testabile: acces la obiect străin, execuție reflectată, citire în afara directorului admis. Jev poate ordona ipotezele admisibile și sugera specializarea. Dacă indiciile sunt suficiente, mergem direct la investigatori — fără research obligatoriu și fără wordlist obligatoriu.
4. **Investigație specializată:** un copil Access Control testează ipoteza BOLA; alt slot poate primi XSS sau alt task independent. Fiecare primește pachetul potrivit, context îngust, precondiții și criteriu de închidere. Toolurile/replay-ul sunt brokered. Rezultatul poate fi candidat, control care infirmă ipoteza, clue sau blocaj, nu numai finding.
5. **Validare incrementală:** când primul investigator termină, validatorul primește claimul și rețeta, execută proaspăt controalele relevante. Alt investigator poate continua în celălalt slot. Nu așteptăm sfârșitul tuturor atacurilor pentru a valida. O reflecție XSS fără execuție nu este confirmată; BOLA fără regula business și identitate validă rămâne neconcludentă.
6. **Prima revenire:** un rezultat de validator care infirmă ipoteza sau cere o precondiție produce delta către Brain. Brain poate restrânge/închide ipoteza, cere remapping sau formula alt test justificat. Nu repetă mecanic aceeași probă. Jev poate semnala contradicția/stagnarea, iar decizia și motivul sunt înregistrate.
7. **Indiciu transversal din Traversal:** taskul Traversal poate demonstra citirea canaryului autorizat; în scenariul proiectat, acel artifact de laborator conține și o referință către o operație omisă pentru aceeași clasă de obiecte business. Aceasta este o observație nouă, nu o instrucțiune de executat și nu extinde scope-ul.
8. **A doua revenire — recon/mapping incremental:** Brain cere verificarea acelei operații noi sau folosește pasul determinist suficient. Harta primește noua operație și provenance. Dacă există acum context auth diferit, se remapează numai suprafața relevantă; nu se recrawlează global tot engagementul.
9. **Nou task pe o familie deja folosită:** operația nouă justifică o investigație BOLA suplimentară. Brain creează un nou task/attempt cu basis refs și procedura fixată. Nu este necesară instalarea unui skill sau schimbarea planului publicat. Dacă aceeași cauză a fost deja raportată, păstrăm occurrence/evidence noi, nu umflăm automat finding count.
10. **Chaining:** Brain observă posibilul link dintre citirea canaryului și accesul nepermis la obiect prin noua operație. Generatorul de capabilități/Jev poate ordona ipoteza de path; un task specializat și validatorul probează pașii și tranziția. Doar după aceea path-ul este probat; două findings alăturate pe hartă nu sunt suficiente. Acest gate este după prima vulnerabilitate, nu în locul ei.
11. **Reconciliază golurile:** Brain și proiecțiile de coverage identifică operații/params/identități netestate, candidați nevalidați, contradicții, approvals ori cleanup restant. Dacă mai există lucru util și admis, se întoarce la etapa potrivită. Dacă lipsesc capabilități/timp/context, golul rămâne explicit; nu este inventat un negativ.
12. **Închidere și raport:** supervisorul aplică predicatul de completion și dovada quiescenței; Brain nu închide singur runul. Raportul folosește findingurile eligibile, evidence, paths, coverage și limitele snapshotului. Review-ul editorial poate continua fără runtime pornit. După remediere, retestul este un run nou cu probe noi.

Research și wordlisturile se pot insera între pașii relevanți: de exemplu, fingerprint incert → research pe produs/versiune → metodă candidată; sau lipsă de rute → corpus specific stackului → discovery bounded → mapping nou. **Rezultatul lor se întoarce în aceeași frontieră de investigație, nu creează un pentest paralel.** Un research eșuat nu oprește taskurile independente; o ipoteză care depinde de el rămâne blocată/neconcludentă. Lucrul auxiliar deja pornit este tot oprit/drenat bounded la închiderea runului.

### 12.3. Unde intervine Jev și cine decide adevărul

În modul **SHADOW**, toate aceste recomandări se înregistrează fără să schimbe execuția. În **ADVISORY**, numai heads evaluate/calibrate pot influența alegerile admisibile; **OFF** păstrează același motor de pentest fără advisor. Nu apelăm Jev obligatoriu la fiecare request/tool.

| Punct în run | Rol Jev | Owner rămas |
|---|---|---|
| După recon / între ipoteze | Relevanță/prioritate/specialist | Brain formulează strategia; supervisorul admite doar taskuri permise |
| După rezultat sau clue | Semnal nou/contradicție/redundanță | Observația rămâne în DB; Brain consumă delta și replanifică |
| Într-un fir care nu progresează | Continue/pivot/stop ca sugestie | Limitele/repetițiile și completion sunt deterministe; Brain alege altă ipoteză |
| La candidate selection/wordlists | Ranking bounded, când headul este evaluat | Generatorul fixează candidații; brokerul validează fiecare efect |
| La dedup/impact/path, ca extensie | Critică și ordonare, nu verdict | Finding identity, oracle, evidence și path validation rămân Omnis |

Primele heads recomandate rămân **relevanță/triage și stagnare**. Dedup semantic, critica impactului și chain ranking nu sunt declarate toate obligatorii sau certificate din prima felie. Jev nu acordă scope, nu injectează credentiale, nu produce CONFIRMED și nu înlocuiește validatorul.

### 12.4. Matricea revenirilor și a opririlor

| Semnal | Tranziție |
|---|---|
| Endpoint/parametru/rol nou | Mapping incremental → aplicabilitate/coverage nouă → ipoteză/task |
| Candidat promițător | Validator independent, nu raport final direct |
| Control infirmă ipoteza | Închidere justificată ori ipoteză revizuită; nu încă o probă identică |
| Auth drift/control invalid | Blocaj/reautentificare admisă → precondiții și baseline proaspete; nu tested_no_issue/FIXED |
| Capabilitate nouă probată | Reevaluare precondiții → posibil path → test/replay al tranziției |
| Repetiții fără informație nouă | Pivot sau închidere limitată a firului, cu motiv |
| Research indisponibil | Continuă firele independente; marchează numai dependența afectată |
| Buget/permisiune/capabilitate insuficientă | LIMITED/gol explicit; fără să transforme lipsa probei în „sigur” |
| Stop/Pause | Fără dispatch nou target/model/research; drain/reconcile, fără wake care repornește lucrul |
| Lesson util pentru produs | ImprovementDraft pentru viitor; nu condiție pentru raport și nu hot-patch al tehnicii active |

**Ce se păstrează din exemplul Strix:** recon-first, model comun, specialiști selectați, handoffs transversale, revenire după indiciu și verificare, goluri reconciliate și impact compus. **Ce adaugă ultimele propuneri:** componente editabile/revizionate și auxiliare utile, fără a înlocui această buclă. În extensiile E1/E2, SQLi/auth/CSRF/SSRF etc. intră în același mecanism când pachetele și adaptoarele sunt implementate; existența ghidului în catalog nu lansează un specialist nefuncțional.

## Sources

[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/curator
[3] https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
[5] https://google.github.io/osv.dev/api
[6] https://google.github.io/osv.dev
[11] https://github.com/ShielderSec/webtech/tree/7141d3542b650df9f984deba6213e2911ee7b9d1
[12] https://github.com/digininja/CeWL/tree/ca01aeae1c77bb086ef757611dea6377b8d1168b
[13] https://github.com/assetnote/kiterunner/tree/7d5824cda9a2eef86d8d18b05b713d7e260f34d2
[14] https://github.com/assetnote/wordlists/tree/6dea231f4cbd356a637851b1c13b83de4da00adb
[15] https://github.com/usestrix/strix/tree/ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2
[16] https://github.com/KeygraphHQ/shannon/tree/327c10fd90a6186a9f035b4b6ddb5bbba1839e92
[17] https://github.com/blacklanternsecurity/bbot/tree/a6fb827bb144cdb85b52e142a4d6e14ed5f94b69
[18] https://github.com/scrapy/scrapy/tree/5d789b24f994bcdfca97c34d976c73739e064849
[22] https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search
[23] https://hermes-agent.nousresearch.com/docs/developer-guide/cron-internals
[24] https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api
[25] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/tools/delegate_tool.py
[26] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/agent/subagent_lifecycle.py
[27] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/agent/background_review.py
[28] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/agent/curator.py
[29] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/tools/skill_manager_tool.py
[30] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/cron/scheduler.py
[31] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/cron/scheduler_prompt.py
[32] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/hermes_cli/plugins.py
[33] https://github.com/NousResearch/hermes-agent/blob/ee5ee84a345204a3b1d6ef6ba1ab747e602867b9/tools/async_delegation.py
