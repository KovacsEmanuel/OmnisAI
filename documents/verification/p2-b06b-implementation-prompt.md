# Prompt de execuție — SL09/B06b inert

Livrabil de pregătire, **neexecutat**. Textul de mai jos devine mandat numai când operatorul îl transmite explicit pentru implementare. Nu autorizează inferență sau trafic către ținte.

## Prompt copy-ready

Continuă OmnisAI în `/home/kali/OmnisAI` și implementează numai **SL09/B06b inert**, după contractul `documents/verification/p2-b06b-next-contract.md`. Nu porni un plan concurent și nu reimplementa feliile acceptate.

### Intrare și autoritate

- Verifică Git real: status/branch/HEAD/diff/index și worktree-uri. Reconciliază orice diferență fără reset, stash, adopție WIP sau transfer automat de PASS. Worktree-uri noi exclusiv din HEAD local verificat.
- Citește AGENTS.md, README, CONTRIBUTING, `implementation-status.md`, contractul B06b și `p2-b06b-preparation-analysis.json`; acesta din urmă este checkpointul analizei, nu verdictul final. Dacă există `p2-b06b-preparation-close.json`, verifică bindings/limite și Git curent, nu numai cuvântul PASS.
- Autoritate: plan §4.2/SL09, §7 și §19.2; arhitectură §5, §6.3, §9.3–9.5 și §9.7–9.10. Folosește skill-urile de delivery/API/runtime/review/status la cerere și workflowul de echipă din CONTRIBUTING.
- B06a este CLOSED_SCOPED_STATIC_PURE în `f057d4cfea23f0169f0f909f2262fccee73e7e4f`. P0/G00, P1/G01, B04 hydration și B05-inert au acceptări distincte. Păstrează toate FAIL/UNCERTAIN/incidentele și limitele lor; nu relansa journeys/gate-uri neschimbate fără motiv nou concret.
- `documents/Omnis_Notite_Originale.html` este protejat: NU îl citi, copia, modifica, hash-ui sau stage. `.hermes/skills/` sunt skill-uri de dezvoltare, nu catalog de produs.

### Rezultatul și perimetrul

Livrează Publish explicit/CAS/idempotent al exact seed-ului calificat în catalogul existent, după confirmarea operatorului și review/eval independente, apoi RunSnapshot CONTRACT_PROBE, Task/Attempt, ExecutionSelection NO_MODEL, PromptBundle/Brief/Result, BoundProcedure/MethodPlan/Check, root–child binding și inbox/receipts durabile. Urmărește toate C01–C12 și tabelul core/deferred H03–H08 din contract; golden/AST/peer simulat nu sunt integrare nativă sau verdict SECURITY.

Extinde bounded ownerii settings/catalog/store, tasks/runs și adaptorul/composerul Hermes; păstrează supervisorul, runtime-host-ul, transportul și metodele native. Inventariază fișierele reale și schema înainte de editare. Introdu fiecare modul/migrare numai cu primul consumator, plus pins API/CLI/bundle/upgrade și testele sale. Fără motor generic workflow, editor Settings, registry sau serviciu per agent.

Ai acord numai pentru fixture-uri **noi, proprii și sintetice**: PostgreSQL disposable UDS/no-network, instalare/build din locks și runtime-home separat, fără credențiale personale. Declarează identitatea/ownershipul, limitele, before/after și inversul efectelor; cleanup exact al resurselor proprii, date/loguri păstrate. Nu adopta vechea DB/fixture/instalare r1 și nu modifica P0/P1/operator data.

### Ordinea practică și probele

1. Fă discovery finit al seamului nativ la pinul Hermes `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. B05 blochează session.create/prompt.submit în modul inert, iar lifecycle launch pornește conversația copilului; nu presupune un NO_MODEL end-to-end existent. Preferă plugin/middleware; numai dacă este necesar, patch minimal auditat separat pe același SHA de bază, cu manifest/provenance și regresii. Nu dezactiva inert flagul ori deschide administrarea stock.
2. Livrează felii verticale mici, începând cu Publish/readback/replay/restart. Cele nouă surse BEHAVIOR_FILES includ consumerul/storage-ul: editarea lor schimbă fingerprinturile. Califică fixture-ul pe artefactul final înainte de Publish și promovează exact acel snapshot; nu forța revisions, micșora closure sau rescrie receipts vechi. Preferă seamul separat când este suficient.
3. Respectă DAG-ul recordurilor fără refs inverse: snapshot/selection/bundle și BoundProcedure/MethodPlan înainte de brief/launch; mapping trusted comis înainte de primul read/tool; TaskResult persistat înainte de MethodCheck. Header/criteria/bound predicates aparțin assignmentului exact. Succesul metodologic nu confirmă o vulnerabilitate.
4. Probează M1 exact după M2 aditiv, separat de auth/input invalid; late post-Stop/Pause prin receive-only/HELD_FOR_RECONCILIATION, fără citiri/tools/wake/model/dispatch noi. Duplicatul identic este idempotent; payload conflict/emitent străin sunt refuzate. Distinge delivered/admitted/turn_completed/domain_result_consumed și ownerul unic al continuării; restart/lost reply nu retrimit orbește promptul. UNKNOWN nu este zero sau refund.
5. Pentru fiecare comportament: RED real → implementare minimă → GREEN/regresii pe același consumer, cu overlap observat unde ceri concurrency. Rulează gates reale ale fișierelor schimbate, migrare/PG, consumator installed și gate canonic `make check` pe snapshotul final când prerechizitele sunt admise. Două reviewuri complementare exacte, fix/re-review focalizat pentru blocante și QA independentă installed; UI/browser doar dacă produsul UI este efectiv afectat. Nu repeta auditul general pentru un fix punctual.

### Limite și ieșire

Fără inferență de produs, cont/provider/model/buget, target traffic, proxy/broker/auth, rollout peste P0/P1, restart/adopție r1, schimbări globale sau push. Nu porni B06c/B06m/P4a/P2-live, editorul B14b ori REVIEWER/MethodResolution/rework B18a.r; seed-ul rămâne CHECK_ONLY. Etapele model/data/live și aprobările lor sunt distincte.

Dacă un scenariu cere model, păstrează NOT_RUN până la etapa live. Dacă bindingul core nativ nu poate fi probat inert, raportează **BLOCKED** cu seamul exact: poți livra separat Publish/contractele deterministe efectiv probate, dar nu declara întreaga B06b PASS dintr-un copil/emitter simulat. Nu lăsa un blocker să devină un motor/harness nou sau o cerere prematură de credențiale.

Commit după fiecare schimbare coerentă, cu motiv/probe/limite/revert; stage numai căile intenționate și verifică SHA/status. Nu termina cu modificări intenționate necomise. Predă scurt în română: ce funcționează real, comenzile/exit codes și bindings, verdictul scoped și toate NOT_RUN/BLOCKED, cleanup/date păstrate, commituri și matricea globală implementare/probe/review. Următorul DAG rămâne B06c → B06m → Settings minim → P2-live cu acord separat.
