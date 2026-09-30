# Omnis — specificație UI/UX v2 · baseline vizual acceptat

**VISUAL_ACCEPTED · Prototip df17a29 · Surface: Operate / Monitor, cu inspector contextual · Bootstrap P0.3 implementat local; experiența P1 rămâne NEÎNCEPUTĂ**

[DESIGN.md](../DESIGN.md) este sursa tokenurilor; [prototipul offline](Omnis_UI_Prototype.html) este o demonstrație navigabilă, nu frontendul implementat. Conținutul sintetic este etichetat DEMO și nu poate executa requesturi, autentificări sau scanări. Limbajul UI MVP: engleză pentru etichete tehnice consecvente, documentație română; excepția explicit cerută este setupul de misiune cu etichetele românești de mai jos. Nu implementăm i18n complet, dar textele rămân centralizate.

**Portarea P0.3:** numai shellul/capsulele/tokenurile/fonturile și formularul local, sesiunea/logoutul și starea reală a instanței sunt conectate la API. Nu se copiază fixture-ul DEMO sau metricile în produs; funcțiile viitoare sunt UNAVAILABLE/NOT_RUN cu motiv. Capturile și probele de tastatură/contrast/stări sunt în [dovezile P0.3](verification/p03-local-bootstrap.md), separate de acceptarea vizuală a prototipului și de viitoarea experiență P1. API/DB/control indisponibile, sesiunea expirată și datele stale nu sunt succese.

## 0. Referința primită și felia de design

**Aprobarea vizuală este explicită:** după livrarea prototipului `df17a29`, utilizatorul a răspuns „arata bine. bravo” și a cerut auditul final înaintea implementării într-o sesiune nouă. Acceptarea acoperă direcția/layoutul și interacțiunile ilustrate, nu datele sintetice, integrarea backend sau rezultatele de securitate. Referință furnizată de utilizator: `/home/kali/OTPen/omnis/brand/omnis-cockpit-v5.html`, SHA-256 `d0545bda58284f5eacd595de395e161efe0d5ba083ffa94dd2423d8a084ed2e7`. Fișierul extern rămâne nemodificat; nu importăm scripturile, conținutul de securitate sau configurațiile sale. Referința este un template vizual, nu contractul de domeniu Omnis.

**Surface primar: Operate / Monitor; secundar: Inspect.** Referința definește acum și compoziția, nu numai paleta: antetul amplu al Dashboardului, pastilele de navigare și metrici, now-bar/stadiu, Needs you, Top findings, Severity și Budget. Statisticile vin dintr-un fixture DEMO coerent în prototip și din agregate backend în produs; nu eliminăm informația cerută pentru a evita datele demo. Nu copiem confidence/precision fără definiție, council/graph, scripturi sau resurse remote. Contrastul și țintele de 44px au prioritate față de microtextul din template.

### Lessons learned din iterațiile respinse

- Prima adaptare a păstrat culorile, dar a înlocuit limbajul vizual: butoane/pastile, proporții, densitate, tipografie și gruparea panourilor nu mai semănau suficient cu referința. **Regulă:** compară componentele și compoziția ecran-cu-ecran, nu declara fidelitate pe baza paletei.
- A doua adaptare a separat corect Dashboard/Engagement/Settings, dar a rămas o consolă prea rară, cu copy tehnic și fără stadiu, metrici, Severity și Budget. **Regulă:** separarea informațională nu înlocuiește fidelitatea vizuală și nu justifică eliminarea componentelor cerute.
- Restricția anterioară „fără hero/statistici” a fost aplicată prea larg. Cererea actuală cere explicit antet și metrici similare referinței. **Regulă:** folosește date sintetice etichetate și calculate dintr-o singură sursă, nu lipsa datelor ca motiv pentru un layout gol.
- Verificările tehnice au prins regresii reale, dar nu au validat gustul sau apropierea de referință. **Regulă:** după clickuri reale, compară Dashboard, Overview, stream și finding deschis la același viewport cu referința; aprobarea finală rămâne a utilizatorului.
- Review-ul manual nu trebuie confundat cu verdictul tehnic. **Regulă:** acceptarea operatorului pentru raport poate urma unei validări, dar nu promovează un candidat în CONFIRMED și nu înlocuiește evidence/oracle.

**Contractul iterației curente:** Dashboard general fidel structurii Home; engagement cu Overview → Brain stream → Findings → Coverage → Reports. Overview arată stadiu, aprobări, metrici confirmed/critical/high/coverage/endpoints, severity distribution, buget și findings. Streamul este compact și diferențiază tool called/result, decizie, endpoint și validare. Findingul se expandează cu sumar, risc, PoC, pași, dovezi, validator și review operator când este cerut. Coverage are numărător/numitor și acces la endpoints; Nu există tab Chains sau graph; amendamentul G-PATH adaugă numai timeline bounded în inspector, după prima BOLA și G-LOOP, cu aprobare vizuală distinctă a extensiei. Raportul conține numai CONFIRMED și, când policy cere review manual, numai cele acceptate pentru raport. Câmpurile se mapează la contracte backend propuse, nu la API-uri pretins implementate.

Adaptări obligatorii:

- Trei suprafețe distincte: **Home / Dashboard central**, **Engagement** și **Settings**. Overview urmează compoziția now-bar → Needs you → metrici → Top findings/Severity → Budget/context. **Brain stream complet are propriul tab**, cu stadiu și evenimente compacte. Fără sidebar permanent; drawer pe mobil păstrează scope-ul și Stop echivalent.
- Fără brain graph, canvas de noduri sau panouri plutitoare draggable. Brain stream: evenimente și decizii scurte, actor/task, motiv rezumat, rezultat și link către obiect/dovadă. Nu expune chain-of-thought și nu deduce starea runului din conversație.
- Fără council, jurori sau voturi. Investigator → validator separat → verdict persistent admis de serviciul probatoriu, pe oracle/controale/evidence. Review-ul operatorului este separat: **Accept for report / Hold**, numai după confirmarea tehnică. Candidatul rămâne neconfirmat indiferent de un click; validatorul nu este nici el un vot LLM suficient pentru CONFIRMED.
- Findings confirmate separate de candidates/inconclusive. Detaliu deschis din listă: impact, severitate motivată, precondiții, reproducere, evidence redactate, controale, decizia validatorului, limite, remediere și retest. Lipsa actuală a dovezilor nu rescrie verdictul istoric.

**Limita feliei de design acceptate (istoric):** prototipul existent, asseturi locale și fixture-ul lui, testele, DESIGN/tokenuri, specificația și probele aferente. S-au păstrat separarea Dashboard/Engagement/Settings și contractele Stop/focus, înlocuind compoziția prea simplificată, fără frontend/backend de produs, conturi sau trafic target în acea felie. Review-ul pentru raport este cerință UI/backend propusă, nu serviciu deja implementat. Portarea ulterioară P0.3 de mai sus nu schimbă baseline-ul vizual sau ordinea livrării celorlalte funcții.

**Acceptare tehnică:** Dashboard/Engagement/Settings au scope și selecție de navigare distincte; Skills/Runtime nu sunt taburi ale engagementului; new setup este separat de setupul contextului selectat. Navigare și detaliu utilizabile; DEMO permanent; stări fără succes optimist; regresiile Stop/modal/drawer/focus păstrate; fără overflow la 320/390/1024/1280/1440; screenshoturi inspectate și zero requesturi externe. Verificare: `python tests/documentation/browser_check.py --include-documents --output <scratch>/browser-check.json`, `python scripts/render_docs.py --check`, `python -m unittest discover -s tests/documentation -v`. Iterația acceptată are 116 checks browser trecute, zero erori JS/requesturi externe; probele și limitele sunt în `verification/README.md` și `verification/browser-check.json`. Testele tehnice nu sunt sursa aprobării vizuale.

Rollbackul prototipului folosește commiturile acelei felii, fără schimbări de DB/runtime; referința externă rămâne neatinsă. Starea de atunci **START_PENDING_NEW_SESSION** a fost urmată de autorizări explicite P0.1/P0.2/P0.3. Structura și contractul `omnis` rămân în arhitectură/plan; launcherul este încă P0.4. Testele de portare nu constituie o nouă aprobare vizuală automată.

### Proveniența elementelor, nu funcții aprobate implicit

| Element | Sursă | Tratament în această propunere |
|---|---|---|
| Dashboard central separat de engagement și Settings | Home/cockpit/settings din referință + corecția explicită a utilizatorului | Intrare globală, navigație contextuală numai în suprafața potrivită |
| Brain stream fără graph; validator fără council | Cererea explicită a utilizatorului | Tab propriu în engagement; verdict și dovezi în finding detail |
| Providers/Skills/Runtime, approvals, scope/auth, retest | Contractele existente din baseline, nu funcții inventate în această reordonare | Settings sau detaliul obiectului; nu scurtături tehnice în nav engagement |
| Skills/Runtime în taburile engagementului; stream complet în Overview | Alegeri ale adaptării precedente, neacceptate vizual | Eliminate din aceste poziții |
| Invoice lab, Alice/Bob, ruta facturii, evenimentele și findingul exemplu | Copy/fixture creat pentru machetă | Date sintetice, nu cerințe noi aprobate și nu rezultate reale |
| Butoane/selectoare „Preview”, simularea ACK și evidence-state | Instrumente pentru verificarea prototipului | Selectorul global și previewurile evidence/replay/retest sunt în panouri pliante „Prototype controls” / „Finding demo controls”, închise implicit; ACK-ul simulat apare numai după comanda demo relevantă |
| Council, graf, chains, multiple runuri active, procente/precision/costuri din template | Conținut al referinței care nu definește Omnis | Nu este importat ca funcționalitate sau telemetrie |

## 1. Anatomia consolei

```text
Global: Omnis | Home (Dashboard) · Engagement · Settings

Dashboard
  antet + target/creare nouă
  Needs your review → metrici globale → pulse → engagement bento

Engagement / Invoice lab
  țintă + run / Pause · Stop
  Overview · Brain stream · Findings · Coverage · Reports
  Overview: stadiu → Needs you → metrici → findings/severity → buget/context
  Brain stream: log compact tipizat, cu stadiu și linkuri la obiecte
  Coverage: matrice/checks și subvedere Endpoints
  Setup și Candidates: acțiuni secundare în context

Settings
  Providers · Skills · Runtime & data
  configurare, fără taburile sau rezultatele engagementului

În afara engagementului: control compact și explicit al runului activ.
Container centrat · maximum 1180px · Stop accesibil în orice scope.
```

Navigarea globală selectează **Dashboard / Engagement / Settings**. Dashboard este landing-ul, cu creare și selecție de engagement; nu afișează taburile unei ținte. Engagement are breadcrumb înapoi, țintă/run și taburi proprii. Settings are numai Providers/Skills/Runtime & data; Skills și Runtime nu apar în nav engagement. Selecția globală rămâne Engagement pe toate paginile lui și Settings pe toate subpaginile de configurare. Pe mobil, drawerul afișează grupul contextual corect, nu lista tuturor paginilor la același nivel.

Topbar menține numele engagementului, run state și sync state. Stop rămâne accesibil în toate paginile și pe mobil când un run este activ. Selecția contextului nu mută accidental controlul pe alt run: butonul indică exact runul activ dacă pagina consultă un snapshot vechi.

În Dashboard și Settings, acest control este o bandă compactă cu **numele/ID-ul runului pe care îl controlează**, nu antetul complet și taburile engagementului. Este control de siguranță, nu o amestecare a rezultatelor celor două contexte. Deschiderea unui engagement nu schimbă sau pornește runul. Crearea nouă (`#new-engagement` în demo) folosește cadrul global; Setup din engagement păstrează cadrul lui.

**Intrare în produsul instalat:** comanda `omnis` pornește serviciile în fundal și deschide dashboardul după readiness; pairingul este cerut dacă nu există sesiune UI validă. „Dashboard ready” nu înseamnă provider gata sau assessment pornit. Settings/Overview explică gates lipsă; nu apare un run RUNNING după simpla deschidere. Închiderea tabului nu oprește serviciile. Stop din UI oprește runul; `omnis stop` oprește și instanța, păstrând datele. Contractul complet și probele încă neîncepute sunt în arhitectură §4.1–4.5; acest bootstrap nu este simulat ca autentificare reală în prototip.

## 2. Route map și placement

| Rută planificată | Conținut primar | Inspector / acțiune |
|---|---|---|
| `/pair` | Pairing local la prima deschidere sau sesiune expirată | Cod din terminal, unic/expirabil; fără secret în URL, fără acces la date înaintea autentificării |
| `/engagements` — Dashboard / home | Overview global: creare engagement, listă/carduri și atenție legată de cazul sursă | Deschide engagementul; fără findings/detail/stream complet sau taburi de țintă globale |
| `/engagements/new` | Wizard cu pași verticali și form central | Rezumat sticky desktop; Save draft permanent, Next/Back; nimic nu pornește |
| `/engagements/:id/setup` | Revizie/draft, scope și context | Edit numai oprit; active → motiv + link Stop, fără editare mascată |
| `/engagements/:id/overview` | Now-bar/stadiu, aprobări, metrici, Top findings, Severity, Budget și context | Review finding/operator sau acțiune exactă; streamul rămâne separat |
| `/engagements/:id/stream` | Stadiu + evenimente compacte tipizate, timestamp/actor/sumar/link; filtre de tip și actor | Tool called/result, decizie, endpoint, validare; fără graph/council/deliberări interne |
| `/engagements/:id/coverage` | Matrice suprafață × identitate × familie, filtre | Click celulă → procedură, test, control și evidence; numitor/snapshot vizibile |
| `/engagements/:id/coverage?tab=endpoints` | Tree host/path, tabel metodă/path/auth/sursă/stare | Operație selectată: params, observations, request/response, related |
| `/engagements/:id/investigations` | Tabel/queue taskuri cu ipoteză, rol, skill, attempt, blocaj/verdict | Timeline investigator→validator; reason, budget, results și stop task dacă suportat |
| `/engagements/:id/findings` | Confirmate implicit, filtre clasă/severitate/status remediere | Dovadă, impact, limite, remediere, retest; candidates nu sunt amestecați |
| `/engagements/:id/reports` | Snapshoturi/version history și limite | Generate snapshot, HTML/JSON download, print; nu rescrie raport vechi |
| `/settings/providers` | OpenRouter și Codex: stări și model/config | Save/test/delete ori device OAuth; consum AI explicit |
| `/settings/skills` | Catalog, search, lifecycle și readiness independente | Files/diff/review/publish; pachet/revizie/digest/evaluare vizibile |
| `/settings/runtime` | Pin Hermes, tool inventory, executori, compatibilitate | Diagnostic sanitizat; fără shell, env reveal, auto-upgrade |
| `/settings/data` | Storage/retention, export/delete/backups, data policy | Operații distructive confirmate cu impact; restore nu autorulează |

Rutele Investigations/Candidates și Setup sunt secundare; nu adaugă taburi primare. URL păstrează engagement/run, filtre și ID de selecție, **niciodată secrete, request bodies sau tokenuri**. Hashurile DEMO (`#map` etc.) nu sunt rute de produs și nu impun compatibilitate API. Datele reale vin prin API și Query cache; refresh reîncarcă snapshotul. Preference neconfidențiale de densitate pot fi locale; nu persistăm dovezi/credentiale în browser.

## 3. Setup în cinci pași

1. **Target & permission:** nume, selector explicit **Evaluare generală / Test focalizat**, textarea multiline **„Obiectiv / instrucțiuni pentru Brain”**, owner/autorizație, fereastră; origins ATTACKABLE/VISIT_ONLY/BLOCKED, căi și excluderi. Text original 1–8192 code points / maximum 32768 bytes UTF-8, limită și counter vizibile; focused gol/whitespace este refuzat. General materializează defaultul explicit din arhitectură §9.3, niciodată aplicat automat focused. Exemplu: „Testează numai dacă un utilizator poate accesa facturile altuia. Nu modifica datele.” Hint: credențialele se introduc la Identities/seif, nu în obiectiv. Preview local al regulilor, fără requests țintă sau LLM la tastare/Save/Next/Back.
2. **Application context:** seed URLs, workflowuri prioritare, obiecte test, reguli `(rol/tenant × obiect × operație → ALLOW/DENY/UNKNOWN)`, proveniență/revizie, import OpenAPI revizionat. Cerințele BOLA nu se ascund într-un free-text opțional.
3. **Identities (optional):** anonymous valid; persona/rol/tenant, tip auth și secret handle; Verify login cu efecte/scope/buget explicite, fără Brain sau assessment pornit; status și Cancel check în același pas până la receipt terminal. GET check/identity confirmă principal/rol/epoch, nu simplul 202. Assisted browser deschis numai după aprobarea scopeului dependențelor, fără browser personal.
4. **Rules & budgets:** efecte, praguri, request/time/storage, rezervă validare, data policy/provider/model și catalog admis. `report_review_policy`: OPERATOR_REQUIRED preselectat și afișat explicit sau VALIDATOR_ONLY ales de operator; se fixează în run, nu se schimbă în timpul lui. „Cost necunoscut” separat de limita tehnică; nu afișăm quota Codex inventată.
5. **Review & preflight:** erori/blocaje grupate cu link înapoi la câmp; mod, obiectivul exact salvat, constraints/non-goals, revizie/model/identități/riscuri/cost posibil, capabilități disponibile și necunoscute. Save draft nu face inferență; nu afișăm interpretare AI fictivă. Start cere preflight actual și confirmare explicită. Brain interpretează după admission în PREPARE; preview AI pre-Start nu este inclus în MVP.

În P1, lipsa catalogului permite Save draft cu workflow_profile_ref=null și CATALOG_UNAVAILABLE/NOT_SELECTED; nu împiedică G01 și nu activează Start. B06/P4a livrează profilul publicat, selectat explicit înainte de Start. Formularul secret HTTP se livrează cu B09h/G-AUTH-HTTP, assisted browser login numai cu P3b.

Preflightul formularului este inert și citește receipturi existente. Check target health este acțiune online separată, cu limite și Cancel check; receipt stale cere repetare explicită, nu trafic ascuns la Save/Start. OPERATOR_CHECK și rutele de readback/anulare sunt în arhitectură §9.7/UI08. Un check activ se anulează/drenează înainte de Start; închidere tab nu înseamnă anulare. Stop-ul instanței închide și aceste operații.

Backendul este autoritatea finală. Un wizard bifat nu garantează că între timp auth/lease/model/policy nu s-au schimbat. La 409 păstrăm editările locale și arătăm conflictul; nu suprascriem automat.

### 3.1. Misiunea în run și readback

Save/reload/restart păstrează exact textul și selecția; 409 nu pierde editările. Arhitectură §9.3 este unica definiție a MissionSpec/FocusEnvelope. Scope = plafon autorizat, full/focused = ce testăm, depth/buget = cât; deep nu lărgește focusul. Ambiguitatea cere clarificare în Needs you; obiectiv nesuportat arată BLOCKED/gap, nu pornește full. STEER clarifică/prioritizează prin comandă durabilă cu readback ADMITTED/CONSUMED, disponibilă pentru G-FOCUS după B18a. Schimbarea materială a obiectivului cere Stop + run nou. Bugetul/deadline-ul bootstrapului focused sunt cumulative peste revizii/re-entry; Needs you nu oferă refill ascuns. Rezultatele tardive pot apărea în History fără a reactiva faza sau runul.

Overview și Brain stream afișează mode/objective badge, mission revision și motivul taskului, fără transcript intern. Coverage numește CoveragePromiseRevision, universul misiunii și denominator_revision, separat de acțiunile enabled; disable lasă gap în promisiunea existentă. ResultQualification explică dovada istorică păstrată versus eligibilitatea curentă, inclusiv după replan/Stop; în afara misiunii = neinclus/netestat, nu sigur/N/A. CriterionOutcome funcțional apare separat de finding/coverage securitate. Raportul focalizat declară criterii/outcomes, suport, excluderi și limite; COMPLETED înseamnă evaluarea efectuată, nu toate criteriile PASS sau aplicația sigură. Retestul preia explicit modul/limitele într-un run nou. Matricea de livrare/readback este în plan §16, UI11–UI13.

## 4. Fluxurile critice

### Start / approvals / Stop

- Start: buton disabled cu explicație dacă gate incomplet; la click se cere preflight real, apoi dialog de rezumat. Comanda primește ID; UI arată PENDING până la readback.
- Approval: panou persistent în Overview și badge număr real în nav; detaliu cu acțiune/efect/target/body redactat/persona/epoch/revizie/expirare. Confirmarea este exactă și o singură utilizare. Expirarea/invalidate se vede chiar dacă dialogul era deschis.
- Stop: click imediat, fără modală care întârzie oprirea; 202 afișează STOPPING, nu STOPPED. Orice dialog/drawer care face topbarul inert conține o acțiune Stop echivalentă pentru runul activ; aceasta închide overlay-ul și trimite aceeași comandă idempotentă. Dacă rețeaua cade, mesaj persistent „Stop not acknowledged” și calea locală de oprire din runbook; nu toast verde.
- Pause: PAUSING până la drenarea efectelor, apoi PAUSED; explică diferența față de Stop. Resume face preflight și poate intra în NEEDS_RECONCILIATION.
- Lucrul deja expediat nu este prezentat ca anulat. Efectele UNKNOWN au detaliu și acțiune de review; nu există retry automat dintr-un buton generic „repară”.

### Coverage / Endpoints → investigație → dovadă

Coverage este tabul principal; Endpoints este subvederea inventarului. Treeul selectează contextul, tabelul selectează operația, inspectorul nu pierde identity/snapshot. Parametri grupați query/path/header/cookie/body; valorile redactate. Sursa JS/OpenAPI este INFERRED până există observație. Un header/banner nu apare la Findings.

Click pe coverage cell arată: denominator key, procedură/revizie, precondiții, acțiunile executate, controlul și evidence. `tested_no_issue` este descris „No issue demonstrated by this procedure”, nu „Safe”. Un filtru nu schimbă numitorul global fără etichetă.

Investigația arată ipoteză, motiv de prioritizare, worker/attempt, skill digest și dependențe. Inspectorul arată TaskBriefV1/TaskResultV1 redactate, procedura/overlay/input digests și misiunea, consumate o singură dată; reason/gaps/next clues nu sunt transcript intern. Readback și migrarea se livrează cu taskurile conform UI15 din plan. Timeline separă investigator, validator și serviciul de verdict. Nu afișăm deliberări interne/chain-of-thought; afișăm decizii scurte și rezultate observabile.

### Findings → report → retest

Listă implicită numai CONFIRMED. Candidates/REJECTED/INCONCLUSIVE rămân în Investigations și pot fi deschise explicit. Finding detail: impact demonstrat, severitate motivată, precondiții, pași, evidence, limite, remediere. Confidence nu este severity.

**Compoziția de review:** listă comună în double-bezel, filtre-pill și rânduri cu severity pill, titlu/metodă/rută, investigator → validator, verdict/review și chevron. Dropdown inline: context și ID, Summary/Risk în două coloane, PoC, pași numerotați, evidence baseline/replay/control, cardul validatorului, apoi Accept for report/Hold când este necesar și remediere/limite. Sub 760px coloanele se stivuiesc. Linkul din stream deschide findingul exact; nu există vot/council sau confirmare manuală a candidatului.

Disponibilitatea **actuală** a evidence este separată de completitudinea **la momentul verdictului**. În prototip, selectorul DEMO AVAILABLE/MISSING/TRUNCATED/CORRUPT/DELETED din panoul pliant **Finding demo controls** ascunde transcripturile indisponibile și dezactivează preview-ul cerințelor de replay, dar nu rescrie verdictul istoric. Statusul de disponibilitate rămâne vizibil în detaliu, în afara panoului de simulare. Textele/transcripturile sunt sintetice, nu output al unui executor. Produsul nu va avea acest selector de scenarii: starea vine din API.

Retest cere run/autorizație/buget proaspăt și afișează FIXED doar după precondiții valide/control. Auth expirat produce RETEST_INCONCLUSIVE. Raportul nou citează probe noi; cel vechi rămâne neschimbat. Dedup conservator cu occurrences expandabile, nu dispariția „duplicatelor” fără audit.

### Providers și Skills

Settings minim poate fi catalog read-only. Settings complet adaugă editor/diff/review/publish fără a schimba layoutul. Readiness provider are patru axe: configured/authenticated/reachable/inference_ready. Test inference este separat și potențial facturabil, admis prin B06m/G-MODEL înaintea oricărui call. Settings și bugetul runului disting usage/cost observat, estimat și UNKNOWN; plafon monetar strict indisponibil blochează acea opțiune, nu afișează enforcement fictiv. Caps tehnice calls/output/deadline sunt vizibile; retry/fallback/auxiliare nu sunt gratuite. Cancel login și logout sunt operații distincte, cu readback.

Editorul de skill este form text/file tree controlat, nu filesystem browser. Arbore: SKILL.md + unicul omnis.yaml + references/technologies + templates/procedures/schemas/requests + assets; TechniqueRevision (metodă) și ProcedureRevision (variantă bounded) sunt separate în detaliu, fără al doilea catalog. Afișează precondiții, baseline/probe/control, false positives, oracle/evidence, limite/cleanup și compatibilitate. Draft → Review → Eval → Publish: afișează digestul acceptat și receiptul; editarea ulterioară invalidează review/eval. Eval îngheață candidatul într-un CandidateSnapshot și arată digestul/closure, statusul jobului și Stop evaluation; candidatul nu devine selectabil pentru assessment. Testarea activă este comandă distinctă, cu laborator/buget/permisiuni, nu efect al editării. STATIC/PURE/FIXTURE/BENCHMARK sunt calificări separate. Operatorul unic poate confirma propriul edit după review/eval tehnic pe același material; autorul AI nu poate autoaproba sau publica. Publicarea arată exact digest/revizie și spune „Applies to new runs”; toate taskurile aceluiași run păstrează catalogul fixat. Disable blochează selecția în runuri noi; revocarea de urgență a unui release activ trece prin Stop/fencing. Erorile de path/reference/dependency sunt lângă fișierul relevant.

### Plan adaptiv, Jev și auxiliare

Păstrăm Dashboard → Engagement → Settings și cele cinci taburi. Rosterul în Brain stream/Investigations arată rol/task/attempt/stare/slot, nu council. Threat model în Coverage/inspector arată observed/inferred, basis/contradicții/revizie; planul efectiv afișează phase_key/subphase_key/instance_id și motivul revenirii, nu un canvas editabil. Un path în Related/finding inspector are pași și tranziții cu evidence, etichete INFERRED/PROVEN/INCOMPLETE; nu dublează findings și nu devine brain graph.

În Settings Runtime, Decision support are OFF/SHADOW/ADVISORY, model/head/question/projection/threshold revisions, data policy/buget și test separat facturabil. Invalid/timeout/fallback și cost UNKNOWN se văd; niciun badge Jev nu confirmă finding. Overview/stream arată numai receiptul/minimul util, condiționat de obiectiv.

Skills extinde aceeași listă/detail/files cu Workflow profiles, Techniques/Procedures, Wordlist recipes și Improvements; clone/edit/reorder/validate/review/eval/publish sunt forms/diff, nu DSL/IDE. Runtime are Research sources și maintenance status/pause/stop. Primul job manual este indisponibil până la G-HERMES-BOUND-CORE și data gate-ul propriu; nu așteaptă cronul, care rămâne opțional ulterior. Butonul de research online cere G-DATA-EARLY-RESEARCH și surse admise; gate-ul final de retention P8 nu este prima verificare a datelor. Research activity și wordlist artifact/provenance se inspectează în task/evidence; preview nu rulează fuzzer. Artifactele wordlist trebuie să treacă G-WORDLIST-CORE înainte de consum; randamentul și G-WORDLIST complet se verifică numai după integrarea discovery B15. Improvements separă author/reviewer/evaluator și stale material; publicarea se aplică numai runurilor noi. WAITING_FOR_RUNTIME_SLOT este diferit de RUNNING, pause schedule diferit de worker stopped. API/owner/migrare/probe/readback per control: plan UI17–UI23, inclusiv source import E3 inert.

Acestea sunt extensii funcționale aprobate **în specificație**, nu layouturi noi aprobate vizual. Dacă prototipul este extins, rămâne DEMO și cere inspecție keyboard/mobile/Stop plus acceptare vizuală separată; nu pretindem integrare backend. Nu expunem admin Hermes, filesystem ori shell.

### Runtime și tooluri

Settings Runtime separă instalat / compatibil / evaluat / permis pentru runul selectat, cu binary/config/template/parser revisions și motivul blocajului. UI nu oferă shell, install arbitrar sau grant global. În Investigations, o ToolInvocation se deschide către toate Action/evidence atribuite; output raw privat este separat de proiecția redactată. Zero matches, unealtă neexecutată, crash/timeout și efect UNKNOWN au stări diferite. Brain cere capabilitatea, backendul acordă subsetul, copilul invocă adaptorul; operatorul vede cererea și motivul, nu chei copiate între agenți. Contractul de livrare este UI16 în plan.

## 5. Stări și copy obligatorii

| Stare | UI corect | UI interzis |
|---|---|---|
| Nu există date | Empty + următoarea acțiune | Numere demo în baza reală |
| Încărcare | Skeleton bounded și aria-busy | „0 findings” înainte de răspuns |
| Readiness insuficient | Motiv și gate lipsă | Start funcțional cu backend absent |
| SSE deconectat | Stale, ultimul cursor/timp, reconnect | Indicator live verde |
| Model cost necunoscut | Unknown + motiv | 0.00 inventat |
| Scope/protocol nesuportat | Unsupported/not tested | No issue / passed |
| Auth expirat | AUTH_BLOCKED, identitatea afectată | Negative test / fixed |
| Evidence lipsă | MISSING/TRUNCATED și ce nu se poate verifica | Replay disponibil fictiv |
| Stop trimis | STOPPING + verificări | STOPPED pe răspuns 202 |
| Limită atinsă | LIMITED, teste rămase și motiv | „Assessment complete” fără limite |

## 6. Accesibilitate și responsive

Țintă WCAG 2.2 AA pentru fluxurile implementate: semantică, keyboard, focus vizibil/neobscurat, contrast, reflow și mesaje de status; verificarea automată nu certifică singură conformitatea.[9]

- Toate controalele au label/accessible name; tab order natural și skip link. Nu shortcut global cu o singură literă pentru Stop sau alte efecte.
- Dialoguri/drawers cu focus containment, Esc și restore; erori form cu summary focus. Live region polite agregat, nu spam la fiecare eveniment.
- Touch targets minimum 44px; niciun text esențial sub 14px desktop/16px form mobil; nu tabele gigantice înghesuite pe mobil.
- Container maximum 1180px fără sidebar permanent. Dashboard și Overview în două coloane la ≥1024, stack sub 1024; Brain stream este separat. Map: ≥1440 inspector lateral; 1024–1439 inspector sub tabel; <1024 nav drawer contextual și detaliu full-width. La 320/390 controalele rămân accesibile, cu scroll local etichetat pentru tabele.
- Zoom 200%, prefers-reduced-motion și high contrast/forced colors verificate pe fluxurile de bază. Statusurile au text, nu doar nuanță.
- Raport print A4, text minimum 12pt, referințe la evidence lizibile, fără sidebar/acțiuni de aplicație.

## 7. Contract frontend și acceptance checklist

Componente comune propuse: AppShell, RunControls, PhaseBanner, MetricPill, SeverityDistribution, BudgetPanel, AttentionQueue, FindingDisclosure, ReportReview, StatusLabel, EmptyState, ErrorPanel, DataTable, ScopeEditor, IdentitySelector, PreflightChecklist, ApprovalDetail, EvidenceViewer, CoverageMatrix și SkillReleasePanel. Radix acoperă dialog/tabs/menu; nu înlocuim elementele native utile. Nu adăugăm bibliotecă mare de charts sau IDE editor înaintea unei nevoi.

Frontendul nu cunoaște tokenul admin Hermes, secretul proxy, credentialul AI sau cheia seifului. Target evidence este text escapate, nu `dangerouslySetInnerHTML`. Schema API generată, erorile tipizate și entity revision alimentează UI; nu inferăm starea runului din streamul conversației.

**U01** Create/edit/reload/restart, field errors, dirty-state și conflict între două taburi.

**U02** Start blocked/preflight/pending/live; Stop pending/disconnected/stopped, fără succes optimist.

**U03** Approval expirat sau policy revizuit în timp ce panoul era deschis este refuzat și explicat.

**U04** Tree/tabel/coverage/inspector folosesc același snapshot/identity și permit trecerea la evidence.

**U05** Candidate nu apare ca finding; negative fără dovadă nu crește coverage; report+retest păstrează istoricul.

**U06** Provider/Skills readiness independent, cancel/logout/readback și release immutable.

**U07** Keyboard complet, focus/dialog, contrast, mobile 320/390 și desktop 1280/1440, zoom/reduced motion.

**U08** Payload HTML/JS/SVG ostil, linkuri externe și screenshot invalid nu execută/încarcă resurse în browserul operatorului.

**U09** SSE replay/resync/stale și refresh nu dublează counters; numerator/denominator și N/A se păstrează.

**U10** DEMO-ul este separat vizibil și tehnic: fără API real, secrets, fetch către țintă, metrici salvate în datele produsului sau confuzie cu teste de integrare.

## 8. Date necesare și legătura UI–backend

**Contracte propuse, nu endpointuri deja implementate.** `assets/prototype-model.js` este un fixture sintetic local, nu adaptor API și nu sursă de autoritate. Un singur model alimentează toate contoarele și eligibilitatea raportului; valorile nu sunt copiate manual între carduri.

| Suprafață | Date/proiecție necesară | Sursa planificată și interacțiuni |
|---|---|---|
| Dashboard | Engagement ID/nume/origin, run activ, phase, summary per snapshot, atenție și findings confirmate | `GET /api/v1/dashboard` pentru sumar/pagină; `/api/v1/engagements` pentru CRUD; click păstrează engagement/run/snapshot; creare separată |
| Overview | `run.status`, `phase`, activitate curentă, elapsed, bugete used/limit, `confirmed_by_severity`, endpoints observed/inferred, coverage covered/total, approvals și report reviews pending | Proiecție server-side a runului din aceleași revizii ca findings/coverage; propunere `/runs/{run}/summary`; Stop/Pause rămân comenzi cu readback |
| Brain stream | Event ID/cursor, UTC, kind (`tool_called`, `tool_result`, `decision`, `endpoint`, `validation`, `approval`), actor, sumar redactat, referință la obiect/attempt | SSE `/runs/{run}/events?after=cursor`; replay/resync nu dublează contoare; fără deliberări interne, raw payloaduri sau credentiale |
| Findings | ID, claim_revision, review_revision, clasă/severitate, operation/identity/snapshot, summary/risk, PoC, pași, evidence manifest/stare, validator, limite/remediere și report_review_policy | `/api/v1/runs/{run}/findings`; expand/filter/select; `POST /api/v1/findings/{id}/report-review` pentru APPROVED/HELD, expected revisions și command ID; contract în arhitectură §9.2 |
| Coverage / Endpoints | Celule cu denominator key, operație/parametru/identitate/epoch/familie/procedură/snapshot; state și evidence; observed/inferred separat | `/runs/{run}/coverage` și `/surfaces`; inspectarea unei celule păstrează contextul exact, nu declară endpointul sigur |
| Reports | Run/snapshot/revision, policy de includere, copii finding/evidence/review, coverage/limite, istoric și artifact refs | Generare server-side dintr-un snapshot coerent; export HTML/JSON inert, raport vechi imuabil; preview-ul din prototip este marcat DEMO |

### Reguli de agregare și review

Contractul normativ este `ProjectionEnvelope` din arhitectură §9.1: scope revision este diferită de versiunea/cursorul datelor, iar proiecția completă a paginii furnizează și counts de navigare. Starea/faza sunt ale serverului; `phase_active=false` nu poate fi suprascris prin rerandare sau din textul Brainului. Erorile `CURSOR_CONTEXT_MISMATCH`/RESYNC_REQUIRED, paginarea și pollingul Home păstrează ultima proiecție etichetată stale până la resync. Coverage afișează `denominator_revision`, numerator/denominator și contextul; filtrarea nu schimbă tacit totalul.

- Confirmed/critical/high și distribuția Severity numără **numai verdictul tehnic CONFIRMED**. Un candidat cu severitate potențială Critical nu mărește aceste valori.
- Coverage = celule eligibile cu procedură/precondiții/control/evidence complete împărțite la numitorul declarat. N/A se exclude numai cu motiv de aplicabilitate; blocked/unknown/unsupported nu sunt succese. Numitor gol → N/A. Endpoints și requests sunt metrici diferite.
- Faza (`VALIDATE` etc.) este proiecție de progres a runului, nu înlocuiește RUNNING/PAUSING/STOPPING și nu se ghicește dintr-un mesaj Brain. Barele de buget arată used/limit, nu procent de „pentest complet”. Cost indisponibil rămâne Unknown, nu zero.
- `report_review.required/status/actor/claim_revision/review_revision` este o axă separată de `validation_status` și `remediation_status`. Accept for report cere CONFIRMED și evidence disponibile; Hold poate exclude și cu evidence lipsă, fără a șterge verdictul. Un candidat/inconclusive nu poate fi promovat. Policy OPERATOR_REQUIRED versus VALIDATOR_ONLY și modificările materiale sunt explicate conform arhitectură §9.2; flagurile mixte ale fixture-ului sunt exemple de stări, nu motorul policy de copiat.
- Backendul trebuie să verifice ownership, If-Match/revision, policy, integritatea și legătura probelor în tranzacție, să păstreze auditul și să refuze cererea stale. Schimbarea materială a claimului/evidence version invalidează review-ul anterior. O simplă schimbare de disponibilitate actuală nu rescrie istoricul.
- La generare, **finding eligibil = CONFIRMED și (review necerut sau APPROVED)**. Candidate/REJECTED/INCONCLUSIVE și review-required PENDING/HELD nu intră ca vulnerabilități. Un raport existent nu se schimbă după review ulterior; raportul nou indică separat disponibilitatea actuală a evidence și limitele.
- În demo, review-ul și snapshoturile trăiesc numai în memorie și exportul se numește explicit DEMO. În produs, aceste reguli sunt aplicate de backend; butonul, promptul sau JavaScriptul nu sunt enforcement.

Review-ul pentru raport nu împiedică oprirea/finalizarea tehnică și nu reia runul. La 409 păstrăm contextul, arătăm schimbarea materialului și cerem un nou review; nu retrimitem automat decizia. Generate arată pending până când artifactul este AVAILABLE; lista și downloadurile provin din snapshotul salvat. Raportul parțial declară excluderile/limitele; pagina nu schimbă raportul vechi după Hold, retest sau retention.

## Sources

[9] https://www.w3.org/WAI/WCAG22/quickref — How to Meet WCAG (Quickref Reference)
