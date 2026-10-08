# SL09 / B06b — contractul următoarei felii (pregătit, neautorizat)

## Autoritate și intrare

Acesta este contractul următorului consumator din DAG-ul existent, **nu un plan concurent și nu implementare începută**. Autoritate: plan §4.2/SL09, §7/B06a–B06b și §19; arhitectură §9.3–9.5/§9.8–9.10 și contractul nativ §5. Intrarea cere adjudecarea B06a local STATIC/PURE pe cod/probe/review/QA installed și cleanup exacte. G02 global nu este o condiție circulară înaintea consumatorilor proprii.

Baza viitoare se citește din Git real după acea adjudecare. Worktree-uri noi numai din HEAD local verificat; nicio adoptare a worktree-urilor curente/istorice. P0/G00, P1/G01, B04 hydration și B05-inert rămân acceptări distincte; nu se reiau fără defect nou concret. B06a oferă catalog/rezervări/freeze/closure/eval durabile, nu încă publicare sau Task/Attempt/copil.

## Rezultatul observabil al SL09

Publicarea explicită a **exact seed-ului calificat**, cu refs/revizii/digests și calificarea neschimbate, apoi Task/Attempt durabile și binding root–copil nativ pentru contractul inert permis. TaskBriefV1/TaskResultV1, PromptBundleRevision, LaunchManifest, MethodPlan/Check, predicate calificate, lineage și inbox/ACK/consumed trebuie consumate efectiv; nu DTO-uri fără consumator, goal text ca identitate sau copil simulat ca integrare nativă.

Publicarea este a B06b și necesită mandat nou. Materialele RELEASE sintetice test-only din B06a nu sunt seed publicat și nu pot autoriza selecția unui assessment. Nici contractul de față, nici închiderea B06a nu acordă această autoritate.

## Frontiera minimă de cod și reutilizare

- Extinde numai proprietarii prevăzuți în SL09: `tasks`, `integrations/hermes` binding/composer/prompt bundle și snapshoturile de run necesare consumatorului. Citește definițiile/usages reale înainte de a stabili fișierele permise sau schema.
- Reutilizează resolverul, storage-ul immutable, compiler/evaluator fingerprints, snapshotul calificat, runtime-host nativ și transportul/private ownership B05. Nu un motor generic de workflow, al doilea supervisor, tabel/serviciu per agent, editor Settings sau rescrierea feliilor acceptate.
- Creează migrația numai împreună cu primul consumator persistent; compară schema pins API/CLI/bundle și upgrade-ul real. Nu migra r1/P0/P1 și nu adopta DB-uri vechi ca fixture.
- Păstrează metodele native și prefixul stabil. Composerul citează refs și contextul minim calificat; nu dump de istoric ori instrucțiuni din output neîncrezut.

## Acceptare falsificabilă și gate-ul consumatorului

1. Seed calificat → publicare explicită exactă/readback → Task/Attempt/Brief/LaunchManifest → binding nativ → rezultat structurat cu exactele task/attempt/brief refs → inbox/ACK/consumed durable → restart/readback fără dublă execuție/consum.
2. Două goaluri identice păstrează identități și lineage distincte. Wrong child/task/attempt/ref pin/owner, rezultate duplicate/târzii și compresia contextului sunt probate prin consumatorul nativ admis, cu pozitive pe aceeași cale.
3. Case slots se leagă numai la assignment în BoundProcedure, cu ownership/kind/revision/digest/cardinalitate exacte. STEP_OUTPUT_REF rămâne legat de procedura/pasul/outputul declarat; nicio rezolvare prin text sau nume global. MethodPlan/Check și M1/M2 respectă contractele canonice și feedbackul metodologic separat de verdictul tehnic.
4. Stop/fencing/inbox și retry/UNKNOWN sunt probate pe lucrul efectiv livrat. H03–H08 și G-REVISION-core primesc dovezile propriului consumator; H01 native breadth absentă rămâne explicit NOT_RUN, nu recertificare a întregului B05 ori emitter fals.
5. Două reviewuri complementare pe snapshot exact și QA independentă installed, PostgreSQL disposable propriu UDS/no-network, procese native și cleanup exact/date păstrate. UI numai dacă este efectiv afectată: browser real, persist/readback și capturi inspectate, nu interfață inventată.

Pentru fiecare comportament: RED real → fix minimal → GREEN/regresii; pentru concurrency cerută, overlap observat, nu apeluri secvențiale. Probe neexecutabile sunt BLOCKED/NOT_RUN. Încercările eșuate, incidentele și limitele rămân versionate. Commituri granulare locale, fără push sau history rewrite.

## Non-obiective și continuarea existentă

Fără inferență, cont/provider/model/buget, trafic către ținte, proxy/broker/auth, rollout peste P0/P1, restart/adopție r1 ori schimbări globale. Dacă bindingul nativ nu poate fi probat inert prin consumatorul admis, se raportează acel blocker; nu se simulează un model și nu se cheltuie buget pentru PASS.

După B06b: **B06c** proiecții/G-DATA-EARLY → **B06m** admission și buget înainte de dispatch → **Settings minim/P4a** → **P2-live** numai cu acord separat cont/model/buget. Apoi build proxy admis → broker/HTTP/auth → prima BOLA cu validator, review, raport și retest. Aceste implementări nu sunt autorizate de mandatul B06a și nu sunt începute aici.

Rollbackul codului este granular prin revert; nu anulează publicări/DB/credenciale/servicii. Mandatul viitor trebuie să declare separat before/after, backup/restaurare unde există date de operator și inversul efectelor externe. Contractul pregătit nu acordă drepturi de execuție.
