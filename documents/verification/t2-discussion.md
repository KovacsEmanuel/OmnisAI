# T2 — registru provizoriu de discuție și decizii

**DISCUSSION_ONLY / MINI-PLAN NOT_FINALIZED / IMPLEMENTATION NOT_STARTED.**

Acesta este fișierul de lucru cerut de operator: păstrează ce s-a discutat, ce s-a hotărât ca direcție și ce mai trebuie precizat. „Provizoriu” descrie maturitatea deciziilor, nu o locație care expiră. Se actualizează în loc, în Git, pentru continuitate între sesiuni.

Nu este un al doilea plan, amendament aplicat, mandat de implementare, autorizație de scanare ori acceptare de produs. [Unicul CURRENT](../../README.md), [arhitectura](../Omnis_MVP_Architecture.md) și [planul canonic](../Omnis_Implementation_Plan.md) rămân autoritatea. Canonul încă descrie T2 inert; extinderea cerută mai jos trebuie reconciliată explicit înainte de implementare. Nu se reia integrarea istorică Hermes/Codex/P2.

Baza Git la deschiderea registrului: `0003ef0b040022714a4dfb0d2c9351deba9057c4`. T1 este CLOSED_SCOPED la dovezile sale; acest registru nu schimbă starea T2 și nu revendică o observație live nouă a instalației.

## 1. Cum folosim registrul

- **DECIS — direcție:** operatorul a ales comportamentul/rezultatul; nu înseamnă că toate detaliile tehnice sunt aprobate.
- **CERUT — de detaliat:** funcționalitate cerută, cu limitele și contractul încă deschise.
- **PROPUS:** recomandare a agentului sau concluzie de cercetare; nu se transformă implicit în decizie a operatorului.
- **DESCHIS:** întrebare care poate schimba produsul, riscul, efectele sau criteriul de închidere.
- **BLOCKED / NOT_RUN:** lipsă reală de acces/dovadă sau execuție neefectuată; nu este PASS.

Pentru fiecare punct discutăm: scopul operatorului → comportamentul concret → ce reutilizăm → intrări/ieșiri și limite → rezultat observabil → controale/eșecuri → decizia rămasă. Detaliile interne se aleg din codul și callerii reali; operatorul nu trebuie să decidă mecanica SQL sau fiecare câmp tehnic.

O recomandare aprobată avansează discuția. Aplicarea amendamentului și lansarea implementării/efectelor rămân acțiuni separate. Nu pornim un agent developer pentru acest registru.

## 2. Ce este stabilit până acum

| ID | Stare | Direcția stabilită | Ce nu trebuie dedus |
|---|---|---|---|
| D01 | DECIS — direcție | Omnis este produs independent, **fără wrapper Strix**. Copiem/adaptăm cât este util din cod, prompturi, skills și componente, cu proveniență/licențe; nu pornim Strix în spate. | Nu este aprobat importul întregului runtime, al dependențelor sau al tuturor toolurilor Strix. |
| D02 | DECIS — direcție | Prima probă funcțională end-to-end folosește aplicația operatorului pe care a rulat Strix, nu un demo sintetic prezentat ca rezultat al produsului. | Nu elimină testele locale/controalele negative pentru binding, Stop, duplicate, limite și erori. Nu autorizează un atac nou în sesiunea de discuție. |
| D03 | DECIS — direcție | T2 urmărit include **cel puțin o vulnerabilitate confirmată independent**, pentru a verifica întregul flux util. | Familia, cazul exact, oracle-ul, identitățile, controalele și efectele/resetul nu sunt încă stabilite. Un finding nu certifică întregul produs. |
| D04 | DECIS — direcție | Operatorul completează engagementul: obiectiv/prompt inițial, context, ROE, ce este în/în afara scope-ului și ce acțiuni sunt permise/interzise; identități când sunt necesare. | Promptul nu extinde ROE/scope-ul și nu ține locul secretelor introduse prin fluxul dedicat. Detaliile formularului și clarificărilor rămân de discutat. |
| D05 | DECIS — direcție | **Brainul coordonează, workerii execută acțiunile asupra țintei.** Recon/mapping/threat model cresc incremental, fără a aștepta o hartă perfectă. | Nu un agent nou pentru fiecare request; nici swarm obligatoriu la startup. |
| D06 | DECIS — direcție | Delegarea este adaptivă și are intenție și goal clare. Rezultatul păstrează observații, probe, limite și indicii; un negativ cu un indiciu relevant poate provoca altă investigație decisă de Brain. | Un mesaj nou nu cere automat spawn/retest. Workerul propune continuarea; nestingul, concurența și regulile exacte de reluare nu sunt aprobate prin această direcție. |
| D07 | DECIS — direcție | În engagement, **Brain stream** arată activitatea comună și o ierarhie compactă de agenți. Click pe agent permite inspectarea delegării, promptului/contextului permis, metodologiei, acțiunilor, rezultatelor, deciziilor scurte și predării. | Nu graph canvas nou, deliberări interne ascunse ori credentiale în transcript. Detaliile navigării/controlului și relația cu Coverage rămân deschise. |
| D08 | DECIS — direcție | **Pairing automat în browser:** operatorul pornește Omnis și ajunge autentificat fără să copieze codul din terminal. Sensul a fost clarificat explicit: bootstrap browser, nu binding Brain–worker. | Mecanismul sigur, prima asociere, expirarea/logout, headless și fallback nu sunt încă decise. Autentificarea/Host/Origin/CSRF nu se elimină. |
| D09 | CERUT — de detaliat | **Engagement Map comună:** Brainul și agenții să consulte/contribuie la inventar, observații, ipoteze, lucru efectuat și rămas; delegările să refere puncte/subpuncte, reducând repetarea contextului. | Accesul la toate datele brute, editarea liberă a autorității/verdictelor și mecanismul de scriere/concurență nu sunt aprobate. Cercetarea suplimentară și propunerea din §5 nu sunt încă o alegere finală. |
| D10 | CERUT — de detaliat | Pregătim înainte de cod scenariile importante și gestionarea eșecurilor, pentru a evita ore de reparat probe fără progres de produs. Lucrăm puțin, dar complet pe primul traseu util. | Nu promitem anticiparea tuturor eșecurilor sau remedii inventate; matricea exactă nu este încă stabilită. |

**Firul urmărit, la nivel de direcție:** setup/ROE/prompt → Brain → recon propriu → hartă/context/ipoteză → delegare → investigație reală → rezultat/indicii → decizie/continuare → validare independentă → finding inspectabil în engagement.

## 3. Ce rămâne de discutat, în ordine de produs

Aceasta este o agendă de discuție, **nu ordinea de implementare și nu o listă de felii autorizate**. Fiecare rând se închide separat; nu cerem operatorului să aleagă totul dintr-o dată.

| Punct | Ce trebuie hotărât concret | Propunere actuală / limită |
|---|---|---|
| M01 — rezultatul T2 | Prima familie/caz, ce demonstrează findingul, intrări permise agentului, oracle/controale, precondiții și criteriul de închidere. | IDOR/BOLA este prima familie din canon și recomandarea inițială, **nu încă alegerea explicită din această discuție**. Inventarul/PoC-urile evaluatorului nu sunt date agentului drept soluție. |
| M02 — setup și autonomie | Cum se separă obiectivul, autorizația, scope-ul și efectele; ce ambiguități cer Needs you; ce acțiuni se execută autonom. | Refolosim engagementul/wizardul existent. Autonomie pentru acțiuni deja permise, fără confirmare la fiecare request; efectele neadmise nu sunt aprobate de textul modelului. Detaliile nu sunt încă decise. |
| **M03 — Engagement Map / AICI** | Obiectele/punctele hărții, ce poate citi și modifica fiecare rol, referințele din delegare, corecții/contradicții, simultaneitate, freshness, coverage și întrebări pentru operator. | Recomandarea și cercetarea sunt în §5. Trebuie agreat comportamentul înainte de schemă/API. Nu confundăm RAG/notes cu starea canonică a probelor. |
| M04 — delegare și context | Rolurile inițiale, granularitatea taskului, ce primește obligatoriu workerul, retrieval din hartă, ce predă, când mesaj către agent existent vs task nou, dedup și independența validatorului. | Goal/intentie/non-goals/context critic/refs/metodă/limite/încheiere/predare; fără inheritance automat al întregului istoric. Forma și regulile exacte sunt PROPUS, nu complete. |
| M05 — skills, modele și reuse | Subsetul de conținut/cod importat, maparea toolurilor, proveniență/licențe, bibliotecă/pin, compatibilitate, default/override, pachete fixate și context mandatory. | Păstrăm direcția API-key-only. `openai-agents` este candidat, nu pin admis; nu adoptăm întregul manifest Strix. Nu importăm toate skills înaintea primului consumer. |
| M06 — execuție și validare | Primul transport real, policy/Stop la sink, capture/evidence/DATA, auth necesară cazului, investigator/triage/validator, ce produce CONFIRMED și ce produce INCONCLUSIVE. | Aducem explicit doar subsetul necesar T3/T4 în traseul T2 extins. HTTP trusted poate preceda browser/shell/scannere; nu le presupunem necesare și nu ocolim confinarea. |
| M07 — experiența operatorului | Ce apare în stream/hartă/inspector/finding, legătura părinte vs cauză, prompt redactat, reload/reconectare, clarificări/intervenții și controale active. | Reutilizăm baseline-ul UI; o singură sursă coerentă, nu hărți/contoare contradictorii. Nu se aprobă estetică nouă sau ecrane demo din registru. |
| M08 — lifecycle și resurse | Stop/Pause/HOLD/Resume, restart/checkpoint, pierdere de owner/răspuns, rezultate tardive/duplicate, stagnare, priorități și plafon de workeri. | Nucleele de siguranță preced efectele. MONITOR fără plafon total artificial LLM și Resume manual rămân canon; limitele tehnice/target rămân. Canonul are prima probă cu un copil, apoi maximum doi: o altă alegere cere decizie, nu copierea fan-out-ului Strix. |
| M09 — probe și comparație | Matrice finită de pozitiv/negativ/fault, efect așteptat, dovadă capturată, diagnostic owner și limita de reluare; baseline/reset/date lăsate de Strix, cleanup și comparație echitabilă. | Separăm defect de produs, harness, prerequisite lipsă și refuz legitim. Rezultate tipizate/efecte, nu fraze exacte LLM; probe afectate după editări, poarta completă la integrare. Regula existentă de două cicluri harness-only nu se resetează. |
| M10 — auto-pair | Handoff launcher→browser sigur, asociere inițială, browser existent/absent, expirare/logout, headless și recuperare. | Extindem traseul existent; nu auth Strix, URL cu secret, CDP ori scriere arbitrară în profilul browserului ca scurtătură implicită. Metoda rămâne de ales. |
| M11 — mini-plan final | Ordinea/dependențele subfeliilor, producătorul și primul consumer real, fișiere/calleri, verificarea și limitele, rollback și momentul acceptării. | Se completează după acordul punctelor de mai sus; reconciliere cu canonul, fără plan concurent și fără pornire automată a implementării. |

## 4. Ce reutilizăm și ce știm din referința Strix

Sursă publică inspectată: `usestrix/strix` la `6b7ae2ebe4d47037a927aade23265ff4e4f27e84`. Binarul instalat nu este demonstrat byte-identic acestei surse. Licența și dependențele se reverifică pentru fiecare import efectiv.

| Componentă de referință | Utilitate pentru discuție | Limită |
|---|---|---|
| Root coordination și prompt composition | Obiective clare, inventar comun, delegare dinamică, prefix comun + metodologie relevantă. | Adaptare la context/autoritate Omnis; nu preluăm declarații de autorizație sau policy din prompt. |
| Create/finish/mailbox și sesiuni distincte | Briefing, rezultat/open-items, comunicare către un worker existent, cauzalitate și predare. | Nu alt owner, DB SQLite concurentă sau wake/retry implicit în produs. |
| Notes/threat model/coverage | Metadata-first retrieval, amendamente atribuite, corectarea aceleiași observații în loc de duplicare, lucru rămas. | Nici proza, nici prezența unui rând nu certifică test/coverage/verdict. |
| Per-agent event projection și inspector | Legarea apelului de rezultat, selecție după identitate și timeline util. | Integrare în UI Omnis, nu viewer/server/graph engine separat. |
| Rubrici de probe/counterevidence și renderere | Metodologie și afișare fără a rescrie fiecare piesă. | Copierea conținutului nu admite automat executabile, dependențe sau validatori. |

Analiza de orchestrare a numărat prin cod 13 agenți, 12 delegări, 14 finish-uri și 13 episoade cauzale. Inventarul reuse a numărat 32 unități candidate și 75 ghiduri/skills; acestea nu sunt capabilități integrate/certificate.

Concluzii păstrate: recon → inventar/model comun → specialiști → gapuri/continuări; informația LFI a produs lucru suplimentar la SSRF, dar mesajul către SQLi a sosit după rezultate deja obținute. Nu este demonstrat cazul exact negativ+clue→task nou în această rulare. Notificarea, consumul și efectul ulterior sunt fapte distincte. `completed` în export nu echivalează automat cu completitudinea coverage-ului.

Rularea de referință este păstrată local la `/home/kali/strix_runs/host-docker-internal-5000_d7f4`. Nu copiem în Git transcripturi, credentiale recuperate sau PoC-uri raw. Analizele redacționate sunt temporar în `/home/kali/.hermes/cache/scratch/t2-deep-analysis-20261102/`; concluziile din acest registru și sursele fixate nu depind exclusiv de supraviețuirea scratchului.

**BLOCKED:** analiza detaliată și reconcilierea probelor celor 27 findinguri/60 intrări coverage au fost oprite de provider cu `content_policy_blocked` și cerințe de securitate ale contului. Nu au fost încheiate și nu sunt preluate prin reformulare/alt model. Scriptul și matricea parțiale nu sunt rezultate acceptate. Această limită nu împiedică discuția generică a hărții, dar nu permite folosirea întregii liste Strix ca ground truth validat.

## 5. Engagement Map — cercetare și propunere, încă de decis

### 5.1. Comportamentul cerut și forma minimă propusă

Operatorul a cerut o hartă comună, consultabilă și actualizabilă de agenți, cu puncte/subpuncte folosite în delegare: ce s-a identificat, testat, pe ce parametri, ce a rămas și unde este nevoie de operator.

**PROPUS pentru Omnis:** o vedere coerentă a datelor existente de inventory/observations/tasks/evidence/coverage, în PostgreSQL, nu încă o sursă de adevăr. Delegarea păstrează goal-ul, intenția, non-goals și contextul critic; referințele stabile către hartă înlocuiesc repetarea întregului istoric, nu sarcina. Agenții pot cere detalii relevante la nevoie.

De agreat explicit:

- Ce poate modifica orice worker: observații/ipoteze/contradicții/continuări versus stări rezervate ownerului și validatorului.
- Corecții atribuite și versionate; păstrarea probelor și a concluziei istorice, fără overwrite pierdut la actualizări simultane.
- `observed/inferred/contradicted` separat de `unknown/untested/assigned/blocked/inconclusive/tested`; detalierea coverage pe operație, parametru, metodă și identitate/context.
- Noutățile din hartă nu modifică pe ascuns obiectivul ori autorizația unui task admis; când se revalidează o precondiție schimbată.
- Acces engagement-scoped și după policy; fără secrete sau acces global la toate datele brute.
- Când Brainul cere alt task, context operator sau închidere; progres pe universul cunoscut/declarat, nu procent inventat din întreaga aplicație.
- Relația UI: Coverage/Endpoints ca vedere de hartă și Brain stream pentru schimbări/decizii cu linkuri, nu două copii contradictorii. Nu presupunem un canvas vizual nou.

### 5.2. Strix — mecanisme inspectate în cod

1. **Notes metadata-first:** `list_notes(include_content=False)` întoarce index/previews; `get_note(note_id)` citește detaliul, cu autor și filtre. Este un model simplu de retrieval reutilizabil, fără vector DB obligatoriu.[22]
2. **Model comun și amendamente:** `get/save/amend_threat_model` separă baza de corecțiile atribuite; append-ul și persistarea sunt serializate. `save` înlocuiește întregul document și golește amendamentele, deci nu se copiază drept operație sigură de editare concurentă Omnis.[23]
3. **Coverage comun corectabil:** rândurile au identitate și istoric, iar `update_coverage` corectează aceeași suprafață/risk area și poate redeschide o concluzie. Unicitatea este verificată sub lock. Totuși, schema upstream este text-centrică, iar `no_issue_found` nu cere evidence în validatorul acestei revizii; nu este oracle de coverage Omnis.[24]

Notes și threat model au mirroring/hydration JSON în această sursă, chiar dacă unele docstrings încă spun „in-memory only”. Păstrăm comportamentul verificat în cod, nu acele formulări. Aceste componente formează un exemplu util de stare comună, nu o Engagement Map unificată cu toate garanțiile propuse.

### 5.3. Alte proiecte open-source

**STATIC_NOT_TESTED:** comparație limitată la PentAGI și NeuroSploit, pe snapshoturi publice parțiale fixate, nu checkouturi complete sau execuții ale produselor. Au fost inspectate câte opt fișiere-sursă principale și suportul necesar. Cercetarea privește mecanismele de cunoaștere comună, nu reia analiza findingurilor blocată. Nu este un clasament universal al celor mai bune implementări.

| Proiect / pin | Mecanism verificat | Adaptare utilă pentru Omnis | Ce nu preluăm implicit |
|---|---|---|---|
| PentAGI `cffed9485aa1cca70762cd08a57ac62a80406258` | `storeToolResult` leagă fragmentele de user/flow/task/subtask/tool; `memory.Handle/getGlobalFilters` face retrieval bounded și poate relaxa task/subtask păstrând filtrul flow.[25][26] | Proveniență explicită și citire întâi îngustă, apoi mai largă numai în același engagement/run. Patternul poate fi aplicat pe PostgreSQL existent; embeddings nu sunt o condiție a lui. | RAG-ul nu este inventar/tested-coverage autoritativ; fragmentele pot fi derivate/sumarizate. Nici UUID-ul, nici notificarea CRUD nu demonstrează CAS, outbox sau invalidare a probelor. |
| PentAGI / Graphiti opțional, același pin | Integrarea de graf adaugă Graphiti/Neo4j și configurare separată a clienților LLM/embeddings.[27] | REFERENCE pentru relații și timp; justificăm separat infrastructura numai dacă apare o nevoie pe care SQL/proiecțiile nu o rezolvă. | DEFER Graphiti/Neo4j, serviciile și dependențele suplimentare pentru T2. Nu sunt necesare doar pentru a avea o hartă comună. |
| NeuroSploit `92e8959f4ea17bddaa0436505edcddf98f7d6b16` | `GraphBatch`/`graph_checkpoint` proiectează recon, findings, relații și istoric într-o vedere comună; există sumar de context limitat. `project_history` păstrează istoricul ca `needs_review/hypothesis`, nu confirmare curentă.[28][29] | Vedere comună derivată, referințe și provenance; recuperare selectivă a contextului. Preluăm regula semantică „istoric ≠ dovadă proaspătă”, nu harnessul sau un graph DB nou. | JSON/checkpoint nu sunt automat store tranzacțional comun cu coverage, revizii sau retractare. Statusurile care doar se întăresc nu acoperă invalidarea după schimbarea precondițiilor. |
| NeuroSploit / `write_coverage`, același pin | Exportul numește agenții selectați drept „tested” și deduce clasele din numele lor.[29] | REFERENCE ca avertisment: păstrăm distinct agent selectat, lucru executat și cerință probată. | Nu calculăm coverage din numele/numărul agenților, confidence sau prezența unui finding; cerem context și probe ale metodei executate. |

Locatoare utile: PentAGI `backend/pkg/tools/executor.go:597–644`, `memory.go:74–179,261–266`; NeuroSploit `neurosploit-rs/crates/harness/src/graph_memory.rs:226–304,940–1025,2250–2287`, `pipeline.rs:1954–2030,3742–3787`. Sursele fixate de mai jos permit recuperarea fără cache. Notele publice de cercetare sunt temporar în `/home/kali/.hermes/cache/scratch/t2-map-research-20261102/other-oss/`.

### 5.4. Recomandarea rezultată — PROPUS, nu încă decis

1. **O singură hartă canonică în PostgreSQL existent**, cu proiecții pentru agenți și UI. Notes/RAG/sumare rămân derivate și nu dublează autoritatea probelor.
2. **Index/metadata întâi, detaliu la cerere:** citiri bounded pe puncte și referințe relevante, fără dump al întregii hărți în fiecare prompt și fără relaxarea accesului către alt engagement.
3. **Fapte și relații adresabile, cu proveniență:** cine/ce task a observat, sursa și dovada, revizia și contextul; observed/inferred/contradicted nu se reduc la confidence.
4. **Corecții atribuite și control al reviziei:** actualizări înguste, istoric păstrat și refuzul suprascrierii stale; contradicția se păstrează până la adjudecare, nu „ultima propoziție câștigă”. Nu acordăm agenților acces SQL direct.
5. **Freshness și invalidare în ambele sensuri:** o schimbare de auth/precondiții poate cere reverificare. Un rezultat istoric rămâne în istoric, dar nu certifică automat starea curentă; concluziile nu pot doar să se întărească.
6. **Coverage bazat pe execuție/probe**, distinct de inventar, task alocat sau agent selectat. Un request ori un sumar nu închide toate metodele/identitățile/parametrii acelui punct.
7. **Schimbări ale hărții legate de evenimentele Omnis și aceeași revizie**, pentru stream, retrieval și reload coerente. Nu adăugăm alt scheduler, publisher autoritativ, graph canvas sau serviciu de memorie pentru această funcție.

Această recomandare combină mecanisme concrete din cele trei surse; importurile efective, schema, API-urile, politicile de scriere/citire și alegerea operatorului rămân M03/M04/M06/M07. Codul public inspectat nu certifică eficacitatea, izolarea ori compatibilitatea integrării Omnis.

## 6. Reguli rămase din canon și implicațiile schimbării T2

- Direcția runtime rămâne API-key-only OpenRouter/OrcaRouter, cu Hermes/Codex numai tooling de dezvoltare. Nu se redeschide alegerea runtime-ului prin cercetarea hărții.
- Persistența canonică, autorizația, DATA, contabilizarea, Stop și finalizarea rămân Omnis; biblioteca de agenți oferă mecanică.
- MONITOR fără plafon total artificial LLM; HOLD/Resume manual, fără retry/fallback implicit. Limitele per operație și limitele target nu dispar.
- Canonul curent: plan §7 T2 inert; §9 HTTP/evidence și B08; §11 prima metodologie/validare; §14 replan extins. Direcția cerută în D02/D03/D06/D07 impune un amendament de ordine/scope pentru subsetul necesar, nu declararea lor retroactiv implementate.
- Prima observație reală are nevoie de transport autorizat și captură; confirmarea unei vulnerabilități are nevoie suplimentar de metoda, precondițiile, controalele și replay-ul adecvate. Nu cerem toată infrastructura BOLA pentru un simplu recon anonim și nu declarăm reconul finding confirmat.
- Probele viitoare trebuie să păstreze baseline-ul aplicației și să țină cont de mutațiile lăsate de Strix. Reset/copie izolată, credentiale, date către model, cost și efecte cer dispoziția explicită necesară; nu sunt autorizate de această notă.

## 7. Recuperare și următorul pas

**AICI: M03 — Engagement Map.** Comparația statică din §5.2–5.3 este consemnată; discutăm acum comportamentul concret al hărții și limitele colaborării, pornind de la recomandarea încă neaprobată din §5.4. Celelalte puncte rămân agenda din §3. Nu revenim la un tur general de audit Strix și nu relansăm acceptări T1 neschimbate.

După fiecare decizie, actualizăm rândul și detaliile sale în acest fișier; o întrebare rămasă nu devine „decisă” printr-un rezumat. Când toate punctele necesare sunt suficient de clare, consolidăm mini-planul cu subfelii, reutilizare, dependențe, consumer/exit real, verificări și limite, apoi cerem separat aplicarea amendamentului și mandatul de implementare.

**Neexecutat:** cod de produs, instalări/upgrade, schimbări DB/operator/servicii, model/provider/țintă, browser QA și push. Nota nu este o acceptare tehnică a funcționalităților discutate.

## Sources

[22] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/notes/tools.py
[23] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/threat_model/tools.py
[24] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/coverage/tools.py
[25] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/tools/executor.go
[26] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/tools/memory.go
[27] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/docker-compose-graphiti.yml
[28] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/graph_memory.rs
[29] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/pipeline.rs
