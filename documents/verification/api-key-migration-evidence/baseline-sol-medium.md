## 1. Design recomandat și limitele autorității

**Recomand amendarea aceluiași baseline pentru un runtime controlat de Omnis, API-key-only, cu OpenRouter și OrcaRouter.** OpenAI Agents SDK rămâne candidat pentru bucla agent–model–tool, condiționat de verificarea frontierelor necesare. Fundația FastAPI/PostgreSQL/React/CLI, contractele de domeniu și istoricul acceptărilor se păstrează.

Verificarea Git la început și final a indicat același HEAD:

`39ab04f13d66fcba9a4cadb02338fb9fae9fa3e8`

Branch: `checkpoint/p2-batch2-pause-20261015`. Diff-urile tracked și staged sunt goale. Singura intrare este `?? documents/Omnis_Notite_Originale.html`; **nu am citit sau modificat acest fișier**. Nu am scris fișiere, creat commituri, pornit agenți, executat teste/builduri, servicii, browser, modele sau trafic target.

Am confruntat documentele cerute cu surse reprezentative. Confirmări statice relevante:

- `provider_models.py:9` restrânge configurația la `openai-codex/gpt-6.1-sol/xhigh`.
- `runs/model_test_source.py` cere încă Publish, pregătire nativă, context, input CONTRACT, assignment și restart pentru testul sintetic.
- `runs/model_test_operation.py:109` omite statusul providerului; `:144` transformă orice observație nenulă în `COMPLETE`. Confirm mecanismul static descris de audit, fără a pretinde reproducere executată.
- `turn_api_request.py:287` utilizează deja clientul `OpenAI`, cu `max_retries=0`, pe traseul Codex Responses.
- `api.py:132` păstrează `assessment_ready=False`; Start este dezactivat în interfața engagementului.
- Manifestele inspectate nu admit încă OpenAI Agents SDK sau OrcaRouter ca dependențe/configurații ale produsului.

Două citiri au vizat inițial căi greșite pentru modulele ModelTest; comenzile au raportat exit 2, apoi am identificat și citit căile reale din `modules/runs`. Acestea sunt erori de localizare, fără efecte.

**Direcție aprobată:** eliminarea Hermes runtime și Codex subscription/OAuth din produs; API keys; ambii routeri; orchestrator AI, roluri/skills și configurație web, cu default comun sau model per rol.

**Analiză propusă aici:** contractele înlocuitoare, repartizarea responsabilităților, simplificarea testului providerului și ordinea până la pentestul minor.

**Autoritate viitoare:** părintele adjudecă raportul și amendamentul canonic; implementarea, pinurile, migrațiile, accesul la conturi, cheltuielile și laboratorul cer mandatele lor. Decizia de direcție nu certifică SDK-ul sau compatibilitatea providerilor.

Designul propus:

1. Supervisorul Omnis păstrează lease, scheduling, taskuri, persistență, bugete, Stop și reconciliere.
2. Brainul propune misiuni și taskuri; backendul validează și admite.
3. Un adaptor de runtime izolat execută bucla agent/tool. SDK-ul nu primește autoritate implicită asupra DB, rețelei sau proceselor host.
4. Adaptoarele providerilor rezolvă configurații imutabile și chei prin handles. Browserul nu apelează providerii direct.
5. Brokerul și executoriile rămân singura cale către laborator.
6. Prima execuție folosește Brain plus un singur slot de copil; investigatorul eliberează slotul înaintea validatorului independent.

SDK-ul documentează integrarea modelelor externe, inclusiv configurarea unui endpoint OpenRouter; aceasta justifică evaluarea candidatului, fără să demonstreze compatibilitatea tuturor modelelor sau garanțiile Omnis. [Documentație oficială SDK](https://openai.github.io/openai-agents-python/models/)

Tracingul SDK poate exporta date către infrastructură externă. Propun dezactivarea exportului implicit și admiterea separată a oricărei telemetrii. [Tracing SDK](https://openai.github.io/openai-agents-python/tracing/)

OpenRouter documentează utilizarea API, iar OrcaRouter publică un endpoint compatibil și rutare automată. Pentru Omnis, modelele exacte, fallbackul și furnizorul efectiv trebuie controlate sau raportate explicit; declarațiile comerciale nu reprezintă probe de compatibilitate, retenție ori cost. [OpenRouter](https://openrouter.ai/docs/quickstart), [OrcaRouter](https://www.orcarouter.ai/)

## 2. Amendamente normative exacte

Locatoarele următoare se referă la SHA-ul verificat. **REMOVE** elimină obligația activă; istoricul și proveniența rămân.

| Document + locator | Obligație veche | Dispoziție | Contract propus; motiv și consumer |
|---|---|---|---|
| Arhitectură §1, r.7–18 | Contracte Hermes; copii nativi; OpenRouter/Codex | MODIFY | Runtime Omnis, API keys OpenRouter/OrcaRouter; default sau selecție per rol. Consumer: scope și preflight. |
| Arhitectură A04, r.33 | Delegare Hermes, stdio, management REST, plugin | MODIFY | Adaptor Omnis pentru bucla agent/tool; SDK candidat, fără embedding în request FastAPI. Consumer: supervisor. |
| Arhitectură A05, r.34 | Broker/L7 și executori fără egress alternativ | KEEP | Aceeași frontieră target; provider egress separat, explicit autorizat. Consumer: toate efectele. |
| Arhitectură A06, r.35 | Runtime separat, catalog RO, pin integral | MODIFY | Mediu de produs separat de toolingul personal; SDK/adaptoare/lockuri fixate; fără încărcare ambientală. Consumer: distribuție. |
| Arhitectură A14, r.43 | Host părinte al Hermes stdio | MODIFY | Owner de execuție cu lifecycle bounded și IPC privat dacă separarea proceselor o cere; protocol Hermes retras. Consumer: Stop/recovery. |
| Arhitectură A16, r.45 | Research/maintenance prin Hermes nativ | MODIFY | Joburi Omnis cu snapshot, date, buget și slot proprii; mecanismul nativ nu mai este obligatoriu. |
| Arhitectură §3, r.48–91 | Topologie, TCB și state DB Hermes | MODIFY | Înlocuire noduri Hermes cu adaptor/loop Omnis; inventar nou de stare și TCB. Păstrare izolări, proxy și probe negative. |
| Arhitectură §4, r.103–105 | Settings prin management Hermes; OAuth approved | MODIFY | Settings deținute de Omnis, operații API-key tipizate și readback; configurat ≠ autentificare verificată ≠ inferență reușită. |
| Arhitectură §4.2, r.128–145 | Profil P2, startup nativ și buget specific 10s | MODIFY | Control plane inert păstrat; pregătirea noului adaptor explicită. Timeout nou măsurat înainte de adoptare; fără login/discovery/inferență la boot. |
| Arhitectură §4.3, r.149–170 | RPC allowlist, management exclusiv, process group Hermes | MODIFY | Contract bounded de execuție/cancel/status/rezultate; revocare înainte de drain. Păstrare InstanceControl, fence, ownership și incertitudine. |
| Arhitectură §4.4, r.180–188 | Slot Hermes/provider store și arhive de caz | MODIFY | Store de secrete Omnis separat de starea conversațiilor/cazurilor; fără copiere/adoptare grants. Inventarul nou decide arhivarea. |
| Arhitectură §4.5/L06–L08 | Acceptare launcher cu adaptor nativ | MODIFY | Readiness, ownership, zero IO implicit și Stop probate pe artefactul nou; P0/P1 rămân istorice scoped. |
| Arhitectură §5, r.219–235 | Pin Hermes, refresh owner, callback/patch nativ obligatoriu | REMOVE/MODIFY | Retragere pin și strategie „plugin apoi patch”; păstrare binding pre-access, identitate trusted și refuz fără mapping. |
| Arhitectură §5, r.243–289 | Metode RPC, dashboard token, rute Hermes/Codex OAuth | REMOVE | Înlocuire cu porturi Omnis pentru execuție și provider API. Fără proxy admin generic sau rute OAuth în produsul nou. |
| Arhitectură §5.2, r.303–313 | ModelDispatch legat obligatoriu de turn Hermes | MODIFY | Referință autentică de execuție/call emisă de adaptor; SETTINGS_TEST are owner sistem. Ledger, DATA, caps și pre-send rămân. |
| Arhitectură §5.2, r.315 | Excepție subscription fără cap output garantat | REMOVE | Excepția Codex devine istorică. API-urile cer caps verificate; costul necunoscut rămâne UNKNOWN. |
| Arhitectură §6, r.319–350 | Wake nativ prioritar; ACK Hermes; interrupt Hermes | MODIFY | Un singur owner al continuării în Omnis; delivered/admitted/completed/consumed distincte; no-resend și Stop păstrate. |
| Arhitectură §6.1–6.3 | Copii nativi, pool, replan și calificare rezultate | MODIFY/KEEP | Instanțe temporare Omnis; același pool și handoff. Păstrare M1/M2, istoric versus eligibilitate, fără extindere din prompt. |
| Arhitectură §6.2, r.399–405 | G-HERMES-BOUND și HM03–HM06 | MODIFY | Gate neutru de runtime/maintenance cu aceleași obligații; curator/review nativ retrase, cron ulterior opțional. |
| Arhitectură §9/§9.5, r.476, 634 | RuntimeBinding/LaunchManifest și lineage Hermes | MODIFY | Domain IDs rămân canonice; IDs SDK/provider sunt referințe externe, mapate și versionate. Niciun task ID din text nu acordă drepturi. |
| Arhitectură §9.4, r.574, 599 | Încărcare nativă; `Compatibility.hermes_revision` | MODIFY | Loader/composer Omnis; compatibilitate cu revizia adaptorului/runtime-ului și schemele fixate. Versiune nouă pentru forma incompatibilă. |
| Arhitectură §9.5, r.618–636 | Composer în `integrations/hermes`; limitări native | MODIFY | Ownership Omnis; compoziție și refs păstrate. Rol/context/schema/capabilități validate înainte de tool, fără moștenire ambientală. |
| Arhitectură §9.7 | Root/child/sistem și Start după receipts | KEEP/MODIFY | Păstrare separare emitent și CheckReceipt; schimbare numai transport/adaptor. Test provider fără Mission/copil fictiv. |
| Arhitectură §9.8, r.692–706 | Eval/publicare și bootstrap prin traseul nativ | KEEP/MODIFY | CandidateSnapshot și digest exact păstrate; SETTINGS_TEST decuplat de catalog. Proba agentului și eval SECURITY rămân distincte. |
| Arhitectură §9.9, r.719–735 | AgentRecipe/ExecutionSelection și seam lifecycle Hermes | MODIFY | Default comun sau override per rol, inclusiv cross-provider; selecție backend fixată. Eliminate obligațiile `SubagentLaunchRequest`/toolsets Hermes. |
| Arhitectură §9.10 | MethodPlan/Result/Check/Review | KEEP/DEFER | Checkerul minim și gaps există înaintea primei BOLA; criticul LLM/rework avansat ulterior. COMPLETE nu produce CONFIRMED. |
| Arhitectură §10, r.784 | Inventar sessions/compaction/logs Hermes | MODIFY | Inventar SDK, conversații, cache, tracing și erori provider; aceeași retenție și izolare cross-case. |
| Arhitectură §12, r.900, 928–931, 991–1012 | Arbore/adaptoare/lockuri și upgrade Hermes | MODIFY | Port runtime neutru și pachet adaptor ales; domeniul independent de SDK. Nu redenumire masivă preventivă; toolingul dev rămâne. |
| Plan §1–3; RF02/RF04/RF07/RF12 | Stack Hermes și doi provideri vechi | MODIFY | Aceeași experiență de produs, noul owner runtime/provider și API keys; reutilizare fără orchestratoare OSS importate integral. |
| Plan §4–4.4, §7–7.1 | Închidere P2 nativ, apoi P4a/live; H01–H08 | MODIFY | Păstrare ID-uri și dependențe safety; acceptări native istorice, probe noi numai pentru consumerii înlocuiți. Fără replay al întregului CONTRACT. |
| Plan §8, r.295–297; §12/B14a | Mandat Codex, conectare OAuth și output exception | REMOVE/MODIFY | SETTINGS_TEST API finit, explicit; configure/save/delete/test/default/per-role din web. Mandatul OAuth este istoric. |
| Plan §12–15 | Maintenance/recovery Hermes și completare nativă | MODIFY | Runtime neutru; nuclee Stop/DATA/admission înaintea efectelor; extinderi și release ulterior, fără micșorarea promisiunilor tacită. |
| Plan §16/UI09, UI15, UI22; §17/HF05 | OAuth, consumer Hermes, G-HERMES-BOUND | MODIFY | UI și trasabilitate către noile contracte; HF păstrate cu dispoziție de supersedare, fără rescrierea deciziilor istorice. |
| Plan §19/§19.2 | Mai multe CURRENT și următor pas Codex | MODIFY | Un CURRENT: direcție aprobată, canon încă neamendat, implementare nouă NOT_RUN; checkpointurile precedente în istorie. |
| UI §2, r.98–100; §3, r.110–113 | Providers Codex/OAuth și pin Hermes | MODIFY | OpenRouter/OrcaRouter API keys, default/per-role, status adaptor și test separat; aceeași navigare. |
| UI §4, r.157–169; §7, r.205 | Cancel login/logout, maintenance Hermes, token admin | MODIFY | Save/delete/test/cancel operație; rezultat provider complet/incomplet/eșuat/necunoscut. Secretele și privilegiile backend rămân inaccesibile frontendului. |
| Stack §1–2/§7/§9–10 | Hermes obligatoriu, lockuri, GO nativ | MODIFY | SDK candidat neadmis până la pin/probe; medii separate și același NO-GO target. Retragere obligații native active. |
| Stack §10.2 HM01–HM08; S01/S05/S06/S09 | Native delegation/lifecycle/review/curator/staging/cron/plugin/recovery | REMOVE/MODIFY | HM-urile devin surse istorice retrase din execuție; obligațiile utile reatribuite ownerilor Omnis. Destinațiile reuse se actualizează explicit. |
| `versions.json:runtimes.hermes`, `remaining_gates` | Runtime selectat și gates native | MODIFY | Hermes marcat istoric; candidat SDK separat, fără pin/probe inventate. Gates actuale neutre, probele vechi imuabile. |

## 3. Dispoziția tuturor rândurilor SL și E

Dispoziția privește **contractul viitor**, nu verdictul probelor istorice. DEFER înseamnă după prima probă, fără eliminarea obligației din MVP.

| ID | Dispoziție | Delta și limita |
|---|---|---|
| SL01 | KEEP | Fixture/ownership PostgreSQL păstrate; fără reluare generală. |
| SL02 | KEEP | Startup instalat inert păstrat; regresii numai dacă distribuția îl afectează. |
| SL03 | KEEP | Pair/open și pairing local păstrate. |
| SL04 | KEEP | Stop/fence/date păstrate; noile efecte primesc probe proprii. |
| SL05 | KEEP | Drafturi/revizii/CAS păstrate. |
| SL06 | KEEP | Dashboard/Setup reale; Start rămâne blocat până la gates. |
| SL07 | MODIFY | Host/protocol Hermes retras; adaptor Omnis nou. Acceptarea B05 rămâne istorică. |
| SL08 | MODIFY | Catalog/resolver reutilizabile; compatibilitate nouă, fără seed CONTRACT prerequisite pentru test provider. |
| SL09 | MODIFY | Brief/binding/metodă/inbox păstrate; identitatea și rezultatele provin din noul loop. |
| SL10 | MODIFY | Aceleași obligații DATA, probate pe serializarea și erorile noului adaptor. |
| SL11 | MODIFY | Ledger/pre-send/Stop/caps păstrate, nou consumer provider. |
| SL12 | MODIFY | Settings API-key și default/per-role; testul nu cere restart/catalog. |
| SL13 | MODIFY | Probă reală model→tool→rezultat, fără target; răspunsul sintetic singur este insuficient. |
| SL14 | KEEP | Proxy admis prin gate; respingerea actuală rămâne. |
| SL15 | KEEP | Broker/policy/evidence/deny la sink înaintea traficului. |
| SL16 | KEEP | Stream/proiecții reale; schimbare adaptor fără date DEMO. |
| SL17 | KEEP | Identități HTTP, seif, principal/epoch și validator izolat. |
| SL18 | DEFER | Browser/SPA după prima BOLA API; rămâne MVP. |
| SL19 | KEEP | Discovery real din URL, fără soluție furnizată. |
| SL20 | KEEP | Hartă minimă, provenance și gaps; fără framework nou de coverage. |
| SL21 | KEEP | Pachet BOLA bounded, reviewed/evaluat/publicat exact. |
| SL22 | KEEP | Validator independent și vulnerable/fixed/benign înainte de acceptare. |
| SL23 | KEEP | Finding/review și CAS, fără confirmare din UI. |
| SL24 | KEEP | Raport și retest incluse în prima probă de produs. |
| SL25 | DEFER | Replan/review/rework avansate ulterior; inboxul/no-double-consume rămân de bază. |
| SL26 | DEFER | Focus adaptiv complet ulterior; scope/focus declarat este obligatoriu imediat. |
| SL27 | DEFER | Wordlist extins după primul finding; fără obligație universală. |
| SL28 | MODIFY | Research ulterior prin worker Omnis; early-data/egress înainte de query. |
| SL29 | DEFER | Recon/JS/Nuclei extinse ulterior, fiecare request atribuit. |
| SL30 | DEFER | XSS/traversal ulterior, cu oracole și controale proprii. |
| SL31 | DEFER | Paths și tranziții probate după familiile necesare. |
| SL32 | DEFER | Jev rămâne integrare/evaluare MVP ulterioară, fără autoritate de verdict. |
| SL33 | MODIFY | Ambii routeri/default/per-role înaintea închiderii Settings; editorul complet ulterior. |
| SL34 | MODIFY | Maintenance Omnis înlocuiește curatorul nativ; gate înainte de primul worker. |
| SL35 | MODIFY | Recovery pe runtime nou; extinderea ulterioară nu amână Stop de bază. |
| SL36 | KEEP | Held-out/release/restore și rezultate raportate; fără transfer de certificare. |
| E1 | KEEP | Subfamilii ulterioare, oracle/eval separat. |
| E2 | KEEP | Browser/business/history/debugger ulterior, gates specifice. |
| E3 | KEEP | Source-aware explicit revizuit; fără execuție la import. |
| E4 | KEEP | Protocoale/workeri/deployment prin decizii și autorizări distincte. |

Niciun rând întreg nu necesită RETIRE: se retrag mecanismele Hermes/OAuth din interiorul rândurilor modificate. Rândurile istorice P2-inert acceptate nu se retrogradează arbitrar și nu certifică runtime-ul nou. Schema CONTRACT, rezultatele PURE și QA129 rămân probe ale consumerilor originali.

Recuperările carantinate rămân separate. Nu devin prerequisite ascuns pentru dezvoltarea pe fixture nou și nu sunt adoptate, pornite sau reconciliate prin amendamentul documentar.

## 4. README, status, development rules și skills

**README:** înlocuirea primului CURRENT este necesară. Acesta descrie încă blocajul startup, în timp ce CURRENT din `p4a-minim.md:9` și harta descriu pregătire/restart ulterioare. Noul CURRENT trebuie să spună că direcția runtime este aprobată, analiza este în adjudecare, iar integrarea nouă nu există. Prezentarea „Brain/copii nativi Hermes” se schimbă; instrucțiunile P0/P1 păstrează limitele instalărilor existente.

**Harta de implementare:** un singur CURRENT și rânduri actualizate în loc. SL12 descrie încă UI9/nepublicat, contradictoriu cu checkpointul ulterior. Istoria trebuie etichetată și separată; nu se lansează recertificări pentru a uniformiza retrospectiv paragrafele.

**Verification index:** `documents/verification/README.md:82` trebuie să distingă probe native/OAuth istorice de gates active pentru noul adaptor. Auditul din 20 octombrie rămâne diagnostic la snapshotul său, fără promovare automată la normă.

**CONTRIBUTING:** secțiunea de configurare Hermes de dezvoltare, trust, `scripts/hermes_dev.py`, worktrees și setările developerului se păstrează. Rândul `:86`, care prescrie `omnis-hermes-runtime` pentru runtime-ul produsului, trebuie înlocuit cu procedura neutră adjudecată. Se păstrează TDD, review independent, commituri mici și probe la consumer.

**Skill-ul runtime:** `.hermes/skills/omnis-hermes-runtime/SKILL.md:16` interzice înlocuirea Hermes. Această obligație trebuie supersedată explicit. Procedura poate rămâne pentru mentenanța integrării istorice; regulile generale utile se mută într-o procedură actuală, fără duplicarea întregului jurnal de pitfalls.

**Alte skills:** `omnis-api-data`, `omnis-release-ops`, `omnis-delivery`, `omnis-review-qa`, `omnis-safety-evaluation` și `omnis-project-status` necesită actualizări focalizate ale consumerilor, mediilor și gate-urilor. Metadata `hermes`, autorul și folosirea loaderului de dezvoltare nu sunt dependențe runtime și nu trebuie eliminate mecanic.

**AGENTS este protejat.** Textul actual afirmă încă așteptarea aprobării implementării/structurii, deși planul consemnează autorizări istorice. Corectarea lui necesită editare explicită prin mecanismul de protecție, cu acordul aplicabil; nu mutarea regulilor într-un fișier alternativ pentru bypass. Mandatul prezent nu autorizează acea editare.

## 5. Matricea verificărilor și exporturilor viitoare

Nicio comandă din tabel nu a fost executată în această analiză.

| Suprafață | Înlocuire/regenerare necesară | Ce trebuie păstrat |
|---|---|---|
| `test_amendment_contracts.py` | Înlocuire marker obligatoriu `G-HERMES-BOUND`, destinații Hermes și obligații HM active cu dispoziții noi verificabile. | Compoziție, refs, Stop, gates, numitor, reuse/licențe și UI01–UI23. |
| Manifest reuse versus stack | Actualizare sincronizată a destinațiilor și statutelor HM; arhivare proveniență. | Unicitatea ID-urilor, hashes și faptul că source-reviewed nu înseamnă importat. |
| `test_b06b_preparation.py` | Contractele istorice rămân; activele H03–H08 se adaptează la noul consumer. | Pozitiv/negativ, ordering, history receive-only și lipsa grantului din NO_MODEL. |
| `test_project_status.py` | Verificare structurată a unui singur CURRENT și a dispozițiilor curente, cu controale negative. | Toate ID-urile, fazele și axele cod/probe/review. |
| `test_resume_status.py` | Înlocuire simplă de markeri insuficientă; detectare checkpoint activ contradictoriu/stale. | P0/P1 nu sunt redeschise; istoria rămâne explicită. |
| `test_baseline_contracts.py` | Actualizare doar a contractelor active schimbate. | Aserțiunea asupra `stack-probe.json` istoric, inclusiv Hermes netestat atunci, rămâne adevărată. |
| Teste API/provider/runtime | Înlocuire OAuth/native cu API-key/adaptor; test separat pentru provider și loop. | Ledger, DATA, cross-task, Stop, timeout, UNKNOWN, no-retry și outcome complet/incomplet/eșuat. |
| `render_docs.py` și suite documentare | Regenerare HTML pentru Markdown normativ schimbat; apoi `--check` și unittest documentation. | Linkuri, headings, escaping și probe negative; fără ștergeri pentru green. |
| `versions.json` | Editare explicită a selecțiilor/gates, păstrare metadate istorice. | Fără actualizare inventată a probelor/advisories. |
| OpenAPI și TypeScript | Regenerare numai când DTO/rutele efective se schimbă, prin exportatorii repo-ului. | Nu generare de endpointuri viitoare drept implementate. |
| Prototip/UI | Browser check și inspecție vizuală când se schimbă UI; acceptare vizuală separată. | Stop, focus, stări, keyboard/mobile și lipsa secretelor. |
| Locks/OCI/SBOM | Actualizare în felia de admitere/implementare a adaptorului. | Pinii existenți neafectați; istoricul distribuției vechi. |

## 6. Ordine finită până la primul pentest minor

Aceasta este amendarea ordinii planului existent, cu aceleași milestones și tickets.

1. **Adjudecare și amendament canonic coerent.** Arhitectura fixează ownershipul runtime/provider, IDs și safety; planul fixează succesiunea; stack/UI/status sunt sincronizate. Verificări documentare, exporturi afectate și review pe bytes exacți. Nu implementare ascunsă în commitul documentar.

2. **Admiterea adaptorului candidat.** Alegere de pin SDK/client, lock, inventar, tracing și provider endpoints. Pozitiv: loop bounded cu tool tipizat. Negative: tool neadmis, model/config străin, retry/fallback ascuns, Stop/control-loss, secret în payload/log. Dacă seamul pre-send nu poate aplica ledgerul, se blochează alegerea, fără promisiune de remediere automată.

3. **Settings și sistem/model funcțional.** API keys, default și selecții per rol, readback după save/delete/reload. SETTINGS_TEST folosește input sintetic explicit și owner sistem; nu cere catalog, copil sau restart. Pozitiv: răspuns și outcome real persistat. Negative: key absent/invalid, 429, timeout, incomplete/failed, Stop, răspuns pierdut fără resend. Primul provider poate închide proba inițială; al doilea se verifică separat înaintea acceptării ambilor.

4. **Model→roluri→taskuri.** Brain și un copil execută un task cu skill minim fixat, tool real inert, rezultat persistent și readback. Defaultul și override-ul per rol se materializează în ExecutionSelection. Wrong-child, stale epoch, prompt override și inventar ambiental sunt refuzate. Acesta este criteriul agent/tool, distinct de conectivitate.

5. **Transport și auth înaintea laboratorului.** Build proxy admis, broker, captură durabilă, scope/efecte, caps, identități A/B/validator și principal pozitiv. Allow și deny măsurate la sink; addon absent, direct egress, redirect interzis și Stop între admitere/send refuzate. Datele target către model trec DATA înaintea primului payload.

6. **Primul pentest minor complet.** URL și context autorizat → recon descoperă operația → Brain formulează ipoteza BOLA → investigator produce probe → validator independent face replay/controale → finding și raport HTML/JSON → retest nou pe remediere. Fixture vulnerable/fixed/benign, fără endpoint vulnerabil furnizat ca soluție. UNKNOWN/auth drift/probe lipsă rămân inconclusive; controlul sigur nu este confirmat. Include Stop și cleanup verificabile. **Un smoke de provider sau un request HTTP reușit nu închide acest rezultat.**

7. **Extinderea distinctă a harnessului.** După feedbackul primei probe: replan/STEER, critic metodologic, editor/profiles/commands/skills aprofundate, browser, alte familii, research, wordlists, Jev și maintenance. Nucleele de autorizare, validare, date și Stop există deja; această etapă le extinde.

Rămân neacoperite: versiunea SDK admisă, compatibilitatea concretă tool/structured-output/effort pentru modelele alese, controlul rutării interne a routerilor, costul strict aplicabil, stocarea cheilor, migrarea stării istorice și gates release pe noua distribuție. Nu este necesară rezolvarea tuturor extensiilor înaintea BOLA, dar fiecare limită relevantă primei probe trebuie decisă și verificată înainte de efect.

| Perimetru | Cod | Probe | Review / pas următor |
|---|---|---|---|
| P0/P1 | Păstrat | Acceptări istorice scoped | Fără recertificare generală |
| P2-inert existent | Păstrat istoric | Scoped, fără transfer | Separare de runtime nou |
| **AICI: amendamente** | Nicio modificare | Analiză statică | Adjudecarea părintelui |
| Runtime/provider nou | Neimplementat | NOT_RUN | Canon, pin, adaptor |
| Primul pentest minor | Neimplementat | NOT_RUN | Succesiunea finită de mai sus |
| Harness aprofundat/MVP/extensii | Ulterior | NOT_RUN | Fără capabilități declarate livrate |

**Predare:** raport read-only, fără commituri; HEAD/status neschimbate. Implementarea și acceptarea noului traseu rămân deschise.