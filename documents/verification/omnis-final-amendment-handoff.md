# Omnis — predare finală pentru amendarea baseline-ului

**Stare: dosar de predare și contracte propuse; baseline-ul canonic NU este modificat prin acest fișier.** Bază reverificată: `0e536941e8adf5b8312ea5eeb515c84123fa3ba9`, ramura `p04-control-topology-wip`. Sesiunea următoare aplică amendamentele când operatorul trimite promptul de autorizare. Nu este ordin de a porni un assessment sau de a implementa tot MVP-ul într-o singură sesiune.

## 1. Ordinea de lectură și autoritatea

1. [README](../../README.md), [AGENTS](../../AGENTS.md), [CONTRIBUTING](../../CONTRIBUTING.md); apoi `git status`, HEAD și diff-ul real. Remote-ul poate rămâne în urmă.
2. [Arhitectura](../Omnis_MVP_Architecture.md), [planul](../Omnis_Implementation_Plan.md), [UI/UX](../Omnis_UI_UX_Spec.md), [stackul](../Omnis_Stack_Baseline.md) și [DESIGN](../../DESIGN.md): acestea sunt baseline-ul până la amendarea explicită.
3. [Review Sol/OSS](omnis-upgrade-review.md): §3 adjudecă Sol, §4 reuse, §5–7 flow/Jev/MVP, §8 amendamente, §9 P0.4, §12 biblioteca Strix.
4. [Supliment modular](omnis-modularity-research-supplement.md): §2–6 module/research/maintenance, §7 codul, §9 amendamente; **§12 este walkthrough-ul principal al runului**.
5. [Manifestul exact de reutilizare](omnis-modularity-research-supplement.reuse.json), [inventarul Strix](omnis-upgrade-review.inventory.json), [dosarul original Sol](omnis-pentest-review-proposal.md) pentru sursele/rațiunile care nu au fost înlocuite.
6. [Adjudecarea P0.4](p04-loop-adjudication.md), plus README-urile [API](../../api/README.md), [CLI](../../cli/README.md), [web](../../web/README.md), numai pentru impactul asupra implementării existente.

**Delta nouă din cererea operatorului:** setup web are un câmp de prompt pentru Brain și suportă test focalizat, nu numai pentest general. §3 de aici este propunerea completă pentru această cerință și trebuie migrată în documentele canonice. Celelalte completări sunt contractul de skill/technique, TaskBrief, unelte reale și criteriul comparativ. Handofful nu înlocuiește corectitudinea surselor: la conflict, adjudecă explicit și consemnează amendamentul, nu copia orbește o propoziție din review.

## 2. Decizii care trebuie păstrate

- Omnis este produs independent local-first Web/API autorizat, cu **runtime Hermes nativ**, PostgreSQL și web Omnis; nu wrapper Strix și nu colecție de runtime-uri alternative.
- Fluxul principal rămâne **obiectiv → recon/mapping → threat model/ipoteze → investigatori → validator → delte/replan/chaining → raport/retest**. Research este auxiliar la nevoie; improvement nu blochează raportul și nu modifică runul activ.
- Brainul este strategul; supervisorul deține authority/dispatch/budget/Stop/completion. Copiii primesc taskuri înguste. Prima probă are un copil; MVP-ul propus permite maximum doi copii activi, incluzând validatorul/researcherul, pe lângă Brain.
- Jev este inclus în direcție, nu o întrebare redeschisă. Relevanță/triage și stagnare sunt primele heads; shadow înainte de advisory calibrat. Nu oracle, scope grant sau publisher.
- Se reutilizează **cod, teste, prompturi și metodologie reale**, la SHA și linii din manifest. Păstrează provenance/notices; nu transforma următoarea sesiune într-o nouă dezbatere de licențiere în locul amendamentelor tehnice.
- Fazele/subfazele/acțiunile sunt compozabile și versionate; instanțele/taskurile/artifactele pot crește adaptiv sub definiția fixată. Nu workflow DSL arbitrar, nu shell generic și nu handler importat din textul unui draft.
- Trei familii sunt nucleul demonstrabil, **nu paritate cu breadthul Strix**. Prima vulnerabilitate BOLA rămâne milestone separat; G-LOOP/G-PATH și extensiile sunt dependente, nu introduse retroactiv în G05a/G06a.
- Direcția vizuală acceptată se păstrează. Nu brain graph/council. Roster, prompt setup, scope/mode badges și path timeline sunt extensii delimitate; o probă tehnică nu este aprobare vizuală.

## 3. Promptul din setup și runurile focalizate

### 3.1. Contract de produs și UI

UI/UX §3 L107 menționează deja „obiectiv”, dar nu definește un prompt operațional propagat și nici un mod focused. **Concretizăm acel obiectiv, nu creăm două câmpuri concurente.** În pasul Target & permission din `/engagements/new` și `/engagements/:id/setup`:

- selector explicit **Evaluare generală / Test focalizat**;
- textarea cu label **„Obiectiv / instrucțiuni pentru Brain”**, multiline, limită bounded declarată în DTO și afișată în UI;
- exemple scurte, nu un prompt prestabilit de „testează tot” aplicat și modului focused;
- Save draft/Next/Back/reload păstrează exact textul și selecția; 409 nu suprascrie draftul;
- instrucțiune vizibilă să se folosească formularul de identități/seiful pentru credențiale, nu textarea;
- în Review & preflight: modul, obiectivul, limitele, capabilitățile disponibile și ce rămâne neclar;
- în run: obiectiv/mode badge, progres și motivul taskului, nu transcript/chain-of-thought.

Exemplu de prompt focalizat: „Testează numai dacă un utilizator poate accesa facturile altuia. Nu modifica datele.” Un alt obiectiv poate numi un workflow și comportamentul așteptat. O verificare funcțională poate produce observații/pass-fail pe un criteriu, dar nu devine automat vulnerabilitate cu severitate. Dacă obiectivul nu este susținut de capabilitățile produsului, Omnis explică blocajul; nu îl convertește tacit într-un pentest complet.

**Save draft și tastarea nu apelează LLM-ul sau ținta.** Interpretarea Brainului are loc după Start și admission pentru model, în faza de pregătire, înaintea investigațiilor/fuzz. Dacă se adaugă preview AI înainte de Start, este acțiune explicită separată, cu provider/data-policy/buget și cost posibil vizibile. Validarea de sintaxă a draftului rămâne locală/server-side inertă.

Înainte de Start, rezumatul arată întotdeauna textul, modul și limitele salvate; o interpretare AI apare numai dacă operatorul a cerut acel preview explicit. Nu promitem preview semantic gratuit și nu introducem LLM obligatoriu la salvare/preflight. Scope/permisiuni, misiune full/focused și depth/buget sunt trei axe distincte: „deep” nu lărgește o misiune focalizată și nu crește permisiunile.

### 3.2. Contract de date propus

În `EngagementRevision` și `RunSnapshot`, nu într-un store de chat separat:

- `assessment_mode = FULL_ASSESSMENT | FOCUSED_TEST`;
- `objective_text` original, privat, cu revizie; general poate folosi un obiectiv default **explicit materializat**, focused cere text nevid;
- `objective_constraints` declarate de operator, de exemplu read-only sau funcționalități excluse; ele nu pot lărgi autorizația;
- referință la profilul/pachetele selectate și la regulile business existente;
- `MissionSpec` rezultat al interpretării: obiectiv rezumat, funcționalități/criterii, ce nu se testează, operații necesare, gaps și `done_when` verificabil;
- `FocusEnvelope`: anvelopa de execuție focalizată validată de backend, cu operații/path-uri cunoscute, acțiuni funcționale de suport, discovery bootstrap bounded și stare de rezoluție;
- mission/focus revision și digest în taskuri, outputuri, coverage și raport.

`MissionSpec` este o propunere model-generated, nu autorizație. Compilerul verifică că folosește referințe reale și capabilități admise. `FocusEnvelope` nu poate depăși scope/policy/budget/identități; contextul de identitate și permiturile sunt atașate de backend, nu din JSON revendicat de model.

**Snapshot vs plan derivat:** `RunSnapshot` îngheață modul cerut, obiectivul/constraints, profilul și versiunile selectate. `MissionSpec`/`FocusEnvelope` sunt rezultate derivate și revizii append-only ale planului, legate de acel snapshot; fiecare task citează revizia consumată. Nu rescriem snapshotul când Brainul termină interpretarea sau descoperă altă operație relevantă. O reinterpretare care schimbă material obiectivul nu este replan obișnuit: cere revizie/run nou. Conflictul dintre modul ales și promptul interpretat cere clarificare înaintea investigațiilor largi, nu ignorarea instrucțiunii restrictive.

**Focusul semantic nu se obține dintr-un regex pe prompt.** Discovery-ul minim poate identifica operațiile relevante, apoi ele sunt legate explicit de misiune. Dacă nu putem delimita ce înseamnă „testează această funcționalitate”, rezultatul este clarificare/gap, nu dreptul de a investiga toate suprafețele. Nu pretindem un sandbox semantic perfect al limbajului natural; verificăm respectarea obiectivului prin task/action traces și fixtures full/focused.

Textul original rămâne recuperabil în contextul privat autorizat; logurile/proiecțiile sunt minimizate și redactate. Modelul primește numai varianta permisă de data policy. Detectarea unor markeri de secret nu este DLP universal. Promptul nu intră în URL, browser storage nesecurizat ori export public implicit.

### 3.3. Flux focused vs general

| Element | FULL_ASSESSMENT | FOCUSED_TEST |
|---|---|---|
| Recon | Inventar al suprafeței promise în scope/catalog | Numai discovery necesar obiectivului și prerechizitelor sale |
| Plan | Ipoteze/familii aplicabile suprafeței cunoscute | Taskuri care susțin criteriile misiunii; nu hunting global |
| Login/health | Funcționale, declarate și bugetate | Pot fi necesare chiar dacă „nu testa autentificarea”; auth-maintenance ≠ auth attack |
| Clue nou | Poate deschide alt fir admis | Deschide task numai dacă servește obiectivului; altfel observație/deferred-outside-objective, nu investigație automată |
| Jev | Relevanță/prioritate în campanie | Aceleași heads, condiționate de obiectiv/non-goals; rankingul nu poate lărgi focusul |
| Coverage | Universul cunoscut/promis al assessmentului | Regula de includere este fixată prin misiune; numitorul se materializează/revizuiește în acel univers, etichetat clar; nu procent global al aplicației |
| COMPLETED | Obligațiile runului reconciliate | Testarea obiectivului îndeplinită cu evidence și fără lucru obligatoriu restant; nu „aplicație sigură” |
| Raport | Assessment cu domeniu și lacune | **Raport de test focalizat**, prompt/rezumat autorizat, criterii testate, prerechizite, excluderi și limite |
| Retest | Run nou, probe proaspete | Run nou cu obiectiv/limite preluate explicit și revalidate; nu devine full implicit |

Promptul poate restrânge lucrul, nu autoriza destinații/efecte noi. Domeniul autorizat este plafonul; focusul selectează ce urmărim în interiorul lui. O operație legitimă de suport este declarată în anvelopă, nu ascunsă ca excepție. Un rezultat incidental poate fi păstrat, dar nu justifică un pivot în afara obiectivului.

Suprafața din afara misiunii este „neinclusă/netestată”, nu N/A de aplicabilitate sau „sigură”. O obligație promisă dar blocked/unsupported/disabled/skipped rămâne gol în numitor; filtrul sau skipul nu cosmetizează procentul. Observațiile relevante pot extinde numitorul într-o revizie nouă. Criterion outcomes pentru verificări pur funcționale sunt separate de findinguri și de `tested_no_issue` de securitate; o aserțiune funcțională nu umflă coverage-ul de vulnerabilități.

Schimbarea materială a obiectivului/modului într-un run activ cere Stop și run/revizie nouă. STEER clarifică sau prioritizează în cadrul misiunii existente; nu hot-swap al scopului. UI trebuie să distingă „clarifică taskul” de „schimbă obiectivul”. `COMPLETED` spune că evaluarea cerută a fost efectuată, nu că toate criteriile business au trecut; outcome-ul fiecărui criteriu și findingurile sunt proprietăți separate.

## 4. Structura standard a skills și tehnicilor

### 4.1. Un pachet nativ clar, un singur manifest Omnis

Layout **propus**, nu fișiere create/activate acum:

```text
skills/object-authorization/
  SKILL.md
  omnis.yaml
  references/
    methodology.md
    false-positives.md
    technologies/<overlay>.md
  templates/
    procedures/read-object.yaml
    schemas/task-result.schema.json
    requests/<reviewed-template>.json
  assets/
    wordlists/<reviewed-seed>.txt
```

Testele upstream/adaptate, fixtures, scorerul și canary truth sunt în workspace-urile de dezvoltare/evaluare, **nu montate în catalogul accesibil investigatorului**. Scripturile sunt opționale și nu se execută la import/încărcare/editare; un helper executabil este consumat numai prin adaptorul trusted și capabilitatea sa, nu prin shell liber oferit skillului.

`skills/` conține sursele metodologiei produsului; `.hermes/skills/` din repo conține proceduri de **dezvoltare** și nu se încarcă în investigatori/evaluator. Runtime-ul primește numai release-ul publicat, nu checkoutul, profilul personal sau toate pachetele draft.

`SKILL.md` păstrează frontmatter nativ valid (`name`, descriere scurtă, versiune, provenance) și o structură metodologică stabilă:

1. **When to use / do not use:** familie, scop, limite și moduri suportate.
2. **Inputs și precondiții:** tehnologie/versiune observată, transport, identități, reguli business și evidence necesare.
3. **Ipoteză și invariant:** ce susține sau infirmă testul.
4. **Metodă:** pași tipizați, baseline/probe/control, variantes și condiții de revenire.
5. **Dovezi și oracle:** observația necesară, controale sigure și cine decide verdictul.
6. **False positives / proof gaps:** auth drift, public/shared objects, reflection fără execuție, indisponibilitate etc.
7. **Impact/effect/cleanup/Stop:** în limitele acordate de backend, nu auto-permisiuni.
8. **Output/handoff:** schema structurată, evidence refs, candidați, contradicții și next clues.
9. **Surse, compatibilitate și verificare:** origine/revizie și evaluările legate de acest pachet.

Nu încărcăm toate tehnologiile și payloadurile în SKILL.md. Overlay-ul se selectează după facts/procedura curentă, iar materialul voluminos rămâne în fișiere suport incluse în digest. Un `xss.md` upstream care tratează reflected/stored/DOM devine subproceduri cu capabilități/oracles distincte; prezența ghidului nu certifică toate variantele.

### 4.2. Contract minim `omnis.yaml`

Unicul manifest executabil de pachet declară:

- schema version, package ID și versiune; corelarea cu numele nativ SKILL;
- intrări/ieșiri și referințe de schemă; procedure/technique IDs;
- familie/CWE/standard versionat și aplicabilitate declarativă, fără `eval`;
- tehnologii/versiuni/transporturi suportate și limite explicite;
- capabilități/tool/template **cerute**, nu granturi;
- efecte declarate și limite de procedură, precondiții, stop/cleanup;
- oracle/control/replay refs și referințe la evaluarea deținută de backend;
- fișiere suport/provenance și compatibilitatea adaptorului.

Statusurile knowledge-reviewed/dependency-ready/fixture-evaluated/benchmark-evaluated/permitted-for-run sunt calculate din receipts și policy, **nu obținute prin editarea unui `validated: true` în YAML**. Digestul release-ului este calculat de backend pe conținutul complet după o regulă canonică documentată; valoarea derivată se stochează astfel încât să nu existe hash autoreferențial.

Schema normativă de introdus la amendare precizează tipul/obligativitatea/nullability pentru fiecare câmp și impune: IDs unice, versiune de schemă suportată, referințe de conținut/schema/procedură rezolvabile, fișiere incluse în digest, paths confined fără symlink și compatibilitate de adaptor. Metadata neexecutable nu acordă autoritate. Un tool cunoscut dar neinstalat produce dependency-unavailable; un pachet executabil nu se publică cu handler/tool ID necunoscut. Materialul methodology-only poate fi păstrat fără a pretinde acea execuție.

### 4.3. Tehnica și procedura nu sunt sinonime

`TechniqueRevision` descrie metoda generală: clasa problemei, ipoteza, principiul de testare, domeniul de aplicabilitate și limitele. O tehnică poate avea mai multe `ProcedureRevision` pentru transporturi, tehnologii sau contexte diferite. Procedura este varianta concretă, bounded, care citează tehnica-părinte și poate fi executată prin capabilități existente. Relația poate fi în același pachet, nu cere alt catalog/serviciu/tabel.

O `ProcedureRevision` are ID/revizie și parent technique ref, objective/applicability, input/identity/business preconditions, effect ceiling cerut, predicted vulnerable signal, secure control, pași cu action/tool IDs și params tipizate, output/evidence contract, oracle ID, invalidation rules, max attempts/stop reasons, cleanup și rezultate posibile inclusiv BLOCKED/INCONCLUSIVE. TaskBrief și coverage citează procedura exactă, nu doar numele larg al tehnicii. Un path sau payload brut se păstrează exact; normalizarea hărții nu îi rescrie bytes.

Metodologia poate evolua fără schimbarea schedulerului. Un nou protocol/oracle/handler poate cere adaptor și schemă/gate propriu; nu promitem că orice capabilitate viitoare se obține doar din text. Versionarea și compatibility tests previn ruperea core-ului: noile câmpuri/semantici incompatibile cer versiune explicită, iar un manifest necunoscut este refuzat, nu ignorat parțial.

## 5. Prompting Brain → copil: contract complet

Nu folosim un prompt generic „ești expert, testează tot” pentru fiecare copil și nu copiem automat tot istoricul Brainului. Composerul produce din surse trusted un **TaskBriefV1**:

Headerul comun este `schema_version`, `run_id`, `task_id`, `attempt_id`, `snapshot_ref`, `mission_revision`, `through_cursor`, `brief_revision` și `result_schema_ref`. Sunt referințe/control de consistență, nu secrete sau granturi; `RuntimeBinding` rămâne separat.

| Grup | Conținut |
|---|---|
| Misiune | Run/mission revision, mod general/focused, rezumatul obiectivului, non-goals și focus envelope ref |
| Assignment | Rol, ipoteza exactă, suprafața/operația, motivul priorității, `done_when` și `return_when` |
| Context | Observațiile citate, vecinătatea relevantă a hărții, observed vs inferred, contradicții, ce s-a încercat deja |
| Metodă | Skill/procedure/technology overlay revisions și input artifacts fixate, inclusiv wordlist digest |
| Identitate | Persona/context labels și refs permise, auth epoch; fără secret/token în prompt |
| Execuție | Capabilitățile permise pentru assignment, limite/rezervă/deadline și condiții de oprire; **descriere**, nu token de autoritate |
| Rezultat | Output schema, evidence/receipts obligatorii, candidați, controls, proof gaps, effects/cleanup și next clues |

Autoritatea reală este legată de runtime child/attempt prin mappingul backend înaintea primului tool. `task_id`, rolul sau un buget scris de model în JSON nu acordă acces. Native `delegate_task` nu primește parametri inventați `tools/provider/skills per child`; adaptorul/pluginul folosește suprafața reală verificată la pin și backendul verifică fiecare acces.

Compoziția recomandată: **base invariants + role instructions + TaskBrief + skill/metodă + overlay necesar**. PromptBundleRevision, modelul și package digests sunt fixate per run. În conversațiile existente, noi clues/refs vin prin tool results/handoff/steer; nu rescriem system prefix sau tool schema pentru a schimba rolul unui copil în mers. Validatorul folosește attempt/context separat.

**TaskResultV1:** schema version și exactele task/attempt/brief refs, status al procedurii, observation/evidence refs, candidate claims, rezultatele controalelor, contradicții, gaps, next clues, consumed input refs, actions/effects/cleanup și usage cunoscut ori UNKNOWN. `SUCCEEDED` nu înseamnă vulnerabilitate confirmată. Copilul raportează sugestii de next task; Brainul replanifică, iar supervisorul admite. Un clue în afara obiectivului focused este returnat ca deferred, nu explorat liber.

Teste: două goaluri identice legate de copii corecți; input/mission stale; ref străin; skill lipsă/wrong digest; mandatory context trunchiat; prompt full moștenit eronat într-un focused task; feedback după Stop; rol schimbat fără nou attempt. Golden composition verifică structura, iar fixtures comportamentale verifică dacă metoda funcționează — nu sunt același gate.

## 6. Unelte reale pentru Brain și copii

Prin „unelte reale” interpretăm în primul rând executabile/scannere, biblioteci și servicii concrete, nu doar metode descrise în prompt: de exemplu Katana, Nuclei, browser/HTTP, generatoare/parsers și ulterior alte tooluri. Dacă se vor cere dispozitive hardware propriu-zise, ele vor avea adaptor, resource lease, policy și fail-safe separate; accesul USB/serial/RF sau la host nu este introdus implicit în MVP Web/API.

**Brainul selectează capabilitatea potrivită și o cere pentru task; backendul acordă subsetul admis; copilul o invocă prin toolul Omnis.** Nu dăm Brainului binare/chei pe care să le copieze liber copiilor.

### 6.1. `ToolDefinition` și `ToolInvocation`

`ToolDefinition` aparține registrului trusted, separat de skill:

- ID/revision, tip adapter, executable/package/image digest și versiune verificată;
- input/output schema și parser version; suport transport/effect/capability;
- dependencies, templates/config bundles fixate și status local readiness;
- metodele permise, resource bounds, cancellation/readback și egress contract;
- mecanismul secret injection, artifact capture și sanitation;
- teste de compatibilitate și positive/negative receipts.

`ToolInvocation` citează run/mission/task/attempt, definition/config/template/wordlist digests, input refs, identitate/epoch, budget reservation, fencing și output/effect receipt. Schema model-facing nu include secrete sau credentialul intern de autoritate. Un tool prezent pe disc nu este automat disponibil oricărui copil.

`ToolResult` păstrează schema/version, invocation ID, status/exit/cancel/effect outcome, parser revision, observații și artifact/evidence refs, truncation și erori tipizate. Proiecția pentru model este separată de captura brută. Chiar și un rezultat cu zero matches trebuie să spună dacă unealta a executat efectiv procedura sau a eșuat înaintea ei.

Nu dublăm `Action`: o ToolInvocation pură produce zero acțiuni target, iar o invocare de scanner poate produce mai multe `Action` legate de ea. Admiterea, contabilizarea și capturarea sunt per request/efect la sink; un permit de invocare nu autorizează trafic nelimitat. Aceste legături și receipts folosesc aceleași module de policy/evidence, nu o autoritate paralelă în adaptor.

Execuție: argv/config tipizate, fără shell interpolation și fără `pip install`/update de templates la runtime; environment allowlist; secrets prin canalul privat suportat de adaptor, nu argv/log/model; filesystem/network/resource limits; request attribution la sink inclusiv pentru requesturile copil ale scannerului. Exit code 0 ≠ finding, zero matches ≠ negativ verificat, timeout/crash cu efect incert ≠ retry sigur.

**Scalarea bibliotecii de tooluri nu schimbă core-ul:** un adaptor nou implementează portul comun și este înregistrat într-un release; pachetele cer capability IDs. Compilerul rezolvă compatibilitatea; indisponibilitatea produce UNAVAILABLE/BLOCKED, nu fallback shell. Dezactivarea/revocarea activă urmează Stop/fencing; nu hot-swap de executable sub attempt.

Teste: installed/permitted separat; wrong binary/template digest; missing dependency; opțiune necunoscută; argument injection; direct egress și redirects; stdout oversized; zero-result vs tool failure; Stop între admitere și dispatch; stale child/lease și restart. Pentru resurse partajate, contextul aparține unui attempt și nu se împrumută între investigator și validator.

## 7. Eficacitate: țintă competitivă, nu garanție din document

**Verificarea finală poate confirma coerența contractelor și traseul de implementare. Nu poate confirma că Omnis va egala sau depăși Strix fără execuția produsului.** P0.4 nu are încă recon/agent runtime/findings de produs. Nici biblioteca de 75 ghiduri și nici Jev nu schimbă acest fapt.

Planul P8 are deja vulnerable/fixed held-out, repetări, replay și baseline determinist. Păstrăm acele praguri și adăugăm un protocol comparativ declarat **înainte de rulări**:

1. Pin Strix/Omnis, modele/provider/fallback, prompt/package/tool versions, hardware, bugete și condițiile de execuție; raportăm unde paritatea nu este posibilă.
2. Aceleași variante de aplicație resetate, identități/reguli, informație de intrare și permisiuni. Black-box, grey-box și source-aware sunt piste separate.
3. Full și focused sunt piste separate; aceeași misiune și același focus în pereche. Nu comparăm un test focalizat reușit cu un pentest general și nu numim asta superioritate.
4. Distinct findings/cauze-rădăcină, occurrences și chains separate; adjudecare independentă și replay. Măsurăm FN/misses pe etapă, FP pe controale sigure, coverage calificat, scope/data violations, cleanup, intervenții, cost/latency și cost per finding validat (N/A dacă nu există numitor).
5. Pentru primul MVP comparăm subsetul de familii efectiv suportate, **marcat explicit**. Separat raportăm breadthul total și familiile neimplementate; nu revendicăm paritate generală dintr-un subset convenabil.
6. Corpusul Strix deja citit este caz de dezvoltare, nu held-out. Nu dăm solverului truth/canary/soluții; repetările, ordinea și invalidările sunt prestabilite, fără alegerea celor mai bune runs.
7. „Comparabil” cere marja/metricile preregistrate și incertitudinea raportată. „Mai bun” cere câștig demonstrat pe metrica aleasă, fără regresie acceptată tacit în siguranță/FP; costul mai mic cu mai multe ratări este trade-off, nu victorie generală.
8. Jev se compară on/off/shadow/advisory pe același profil și buget; nu pretindem causalitate dintr-un run.

Scopul produsului final rămâne breadth competitiv și investigație adaptivă. E1 este doar prima extindere: runul Strix discutat include și clase din E2, iar unele capabilități de execuție sunt planificate în E4. Dacă primul release trebuie să aibă breadth apropiat, se declară exact subfamiliile/scenariile din aceste valuri și gates aferente; nu etichetăm E1 sau trei familii drept paritate completă.

## 8. Matrice de amendare și acceptare pentru sesiunea nouă

Locațiile sunt raportate la baseline-ul inspectat; recitește ancorele înainte de editare. ID-urile HF de mai jos sunt doar rânduri de handoff, nu înlocuiesc gates H01–H08/G00–G08.

| ID | Modificare și loc | Owner/API/migrare | Ticket și positive/negative gate |
|---|---|---|---|
| HF01 | Prompt/mode: UI §3 L105–113, §8; arhitectură §9 L345–365; plan B02/B04 și UI01/UI08 | `engagements` draft/revision + `runs` snapshot; câmpuri pe modelul existent, fără chat DB nouă | G01 create/edit/reload/409; focused gol respins; save zero LLM/target; HTML prompt inert; secret handling/data policy |
| HF02 | MissionSpec/FocusEnvelope: arhitectură §5–7 L207–221/L271–320; plan B06/B10/B18 | `tasks/runs/policy`; plan validat, task scope/mission refs, command readback | FULL vs FOCUSED; suport login permis, auth attack exclus; unclear focus nu pornește hunting global; prompt off-scope refuzat |
| HF03 | Completion/coverage/report: arhitectură §6 L284–308, §9.2/§11 L436–446; plan B12/B13/B20, UI Coverage/Reports | `runs/coverage/reports`; mission denominator și criterion outcomes, snapshot coerent | Obiectiv testat→COMPLETED fără promisiune whole-app; unsupported/gap→LIMITED; numitor focused etichetat; retest nou |
| HF04 | SkillPackage/Technique/Procedure: arhitectură §5/§12, plan B06/H03 + P4a-minim, apoi B14b/B16/B17; UI Settings Skills | `settings/skill_catalog`; un manifest `omnis.yaml`, review/eval metadata backend, releases RO | Schema/pachet minim înaintea primei proceduri, editor complet ulterior; wrong digest/reference/shadowing refuzate; edit după eval invalidează acceptarea; active run neschimbat; held-out absent din package |
| HF05 | TaskBrief/TaskResult/PromptBundle: arhitectură §5 L207–245/§11 L434; plan B06/H03–H08 | `tasks` + `integrations/hermes`; context trusted separat de JSON LLM | Două goaluri identice/role context/mission stale; fără tool/provider args native inventate; no double wake după Stop |
| HF06 | ToolDefinition/Invocation: arhitectură §3/§7/§12, plan B07/B09/B15 + matrix runtime | Registry/adaptoare trusted + broker; skill cere capabilitatea, backend o acordă | Instalat≠permis; wrong binary/template; egress/secret/timeout/Stop; parser output≠verdict |
| HF07 | Modularitate și auxiliare: supliment §2–6/§9/§12 → arhitectură A15/A16 și owners | Refolosește supervisor/Task/Inbox; research și maintenance separate | Re-entry bounded; research failure nu blochează fir independent; improvement nu e prerequisite pentru raport |
| HF08 | Jev condiționat de obiectiv: review principal §6 → arhitectură/Settings/RunSnapshot | `DecisionAdvisor`; proiecție goal/focus minimizată, heads/revizii fixate | Shadow fără efect; invalid/missing→fallback; ranking nu lărgește mission; fără CONFIRMED din probabilitate |
| HF09 | Evaluare competitivă: plan §15 L238–257 și arhitectură §11 | Evaluator separat, protocol și rezultate per run | Comparații matched/full/focused; FP/FN/root-cause/replay/cost; fără claim de superioritate nemăsurat |
| HF10 | Cod P0.4 existent: README/adjudecare și plan§19 | Păstrează API/DB/control/bootstrap/CLI; matrice keep/fix-later/extend | Niciun Start fictiv; assessment_ready false; nicio promovare de harness la G00 |

Scope UI nou: selector/textarea/preview/readback în setup; mode/objective în Overview/Brain stream; focus-aware coverage/report; file tree de skill/proceduri/tehnologii și runtime tool readiness. Păstrăm Dashboard → Engagement → Settings și taburile acceptate. Nu expunem admin Hermes, filesystem sau shell în browser. Pentru prototip: numai DEMO și inspecție keyboard/mobile/Stop separată de integrarea backend.

**Legături API de păstrat din arhitectură §9, toate contracte viitoare, nu endpointuri implementate:**

- HF01: `/api/v1/engagements`, `/{id}`, `/{id}/revisions` salvează/citesc textul, modul și constraints sub revision/If-Match; readbackul verifică exact textul și aceeași revizie, inclusiv după restart.
- HF02: `/api/v1/engagements/{id}/preflight`, `/{id}/runs` și `/api/v1/runs/{run}/commands` fixează contextul și admit execuția. Browserul nu postează o `MissionSpec` ca grant; 202 nu este execuție finalizată.
- HF03/HF05: `/api/v1/runs/{run}/summary`, `/tasks`, `/coverage`, `/events?after=cursor` expun mode/mission revision, briefing/debriefing redactat și proiecții coerente; refresh/resync și inspectorul trebuie să arate aceleași refs, nu copii frontend divergente.
- HF03: `POST/GET /api/v1/runs/{run}/reports`, `GET /api/v1/reports/{id}/artifacts/{format}` și `/api/v1/findings/{id}/retests` păstrează misiunea/limitele și separă snapshotul vechi de probele noi. Verificarea include bytes HTML/JSON descărcați, nu doar preview.
- HF04/HF06: familiile `/api/v1/settings/skills/...` și `/api/v1/settings/runtime` poartă catalogul, fișierele/diff-ul și readiness. La B14b se precizează subrutele/DTO-urile de edit/review/publish; nu endpoint shell și nu pass-through Hermes. Migrarea skill release și receipts aparține catalogului; invocation/Action refs aparțin execuției/evidence. Noile relații sunt versionate și validate de backend, nu doar adăugate în UI.

**Ordine de livrare:** B02/B04 pot persista promptul/modul și afișa readiness; B06 propagă TaskBrief; B10/B12/B13 aplică focusul și reportingul cu primul consumator. G05a/G06a rămâne prima probă BOLA, apoi un gate focused separat dependent; editorul complet, cronul și toate toolurile viitoare nu devin prerechizite ale acelei prime dovezi. Ambele moduri trebuie să primească acceptance în MVP-ul amendat, nu focused lăsat ca simplă textarea fără efect.

## 9. Impactul asupra codului P0.4 și limita intervenției

Verificare statică în această sesiune: `api/src/omnis/api.py:118` păstrează `assessment_ready=False`; CLI definește `status/install/install-image`; bootstrapul web are încă butoanele de run indisponibile. Inventarul urmărit al modulelor API este `instance`, nu motorul viitor de engagement. **Nu există un motor pentest de rescris acum.**

Păstrează fundația. Restanțele deja documentate — Compose WIP UDS/no-network versus fixture/CI încă TCP, helper probe-only, timeout/cleanup supervisor și owner exec WIP — se tratează în felii P0.4, fără încă o campanie de harness. Noile concepte de mission/skill/tool apar odată cu modulele care le exercită, nu ca tabele goale în P0.

WIP observat la început, nu atribuit acestei sarcini și nu autorizat implicit pentru modificare/staging:

- `api/src/omnis/core/db.py`
- `api/tests/test_fixture_ownership.py`
- `ops/compose.test.yaml`
- `api/tests/test_database_url.py`
- `ops/run_test_db_gate.py`
- `tests/development/test_test_db_gate.py`

Sesiunea nouă livrează amendamentele și matricea de impact. O corecție de cod mică poate fi tratată separat numai dacă este necesară unui contract **deja implementat**, are test/reproducer sigur și fișiere fără conflict. Dacă depinde de acest WIP, DB/servicii neaprobate sau schimbă faza de implementare, documentează blockerul/ticketul și cere acordul relevant; nu integra silențios munca altui autor. Nu modifica AGENTS protejat pentru a ocoli divergența istorică de status vizual.

## 10. Contractul livrării următoare

Sesiunea următoare trebuie să producă modificări reale în baseline, nu un al patrulea plan alternativ:

1. Status/base/diff și inventar al cerințelor din HF01–HF10; load procedurile proiectului relevante.
2. Amendamente coerente la arhitectură (comportament), plan (ordine/gates), UI/UX (date/interacțiuni) și stack (unități de reuse/dependency), cu planul comun de MVP/extensii. Source pins din manifeste se păstrează.
3. Contractele concrete Mission/SkillPackage/Technique/TaskBrief/ToolDefinition, aliniate între documente; nu snippets care sugerează API-uri deja implementate.
4. Matrice UI→owner/API/migrare/ticket→positive/negative readback, inclusiv prompt/focused și tool delegation.
5. `README`/readiness/verification index actualizate cu starea reală; review-urile rămân dovezi/rațiuni, nu autoritate concurentă după incorporare.
6. Readers HTML regenerate: `python scripts/render_docs.py`; apoi `--check` și `python -m unittest discover -s tests/documentation -v`. Dacă prototipul se schimbă, rulează browser checks și inspectează vizual; nu afirma acceptare estetică nouă.
7. Pentru orice cod schimbat: TDD, review independent, comenzi reale potrivite feliei; `make check` cu prerequisite unsafe/absent rămâne BLOCKED, nu alias fals-green.
8. Commit mic per schimbare coerentă, mesaje cu motiv/verificare/limite; numai fișiere intenționate. Fără amend/squash/rebase/force-push sau push implicit. Verifică SHA/stat/status după commit.
9. Raport final în română: ce este incorporat în documente, ce este implementat, ce rămâne de probat și următoarea felie. Nu declara superioritate față de Strix înainte de protocolul comparativ executat.

**Criteriu de predare:** un implementator nou poate urma un singur baseline și poate adăuga o tehnică, un overlay de tehnologie sau un adaptor fără să ghicească rolurile, contractele, authority ori modul de publicare. Nicio frază din document nu confundă un draft/golden test/sursă inspectată cu o capabilitate executată.
