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
| D03 | DECIS — direcție | T2 urmărit include **cel puțin o vulnerabilitate confirmată independent**, pentru a verifica întregul flux util. Operatorul a ales explicit **IDOR/BOLA** ca prima familie. | Cazul exact, oracle-ul, identitățile, controalele și efectele/resetul nu sunt încă stabilite. Alegerea familiei nu dovedește că un caz potrivit există în starea curentă a aplicației și nu autorizează testarea. Un finding nu certifică întregul produs. |
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
| M01 — rezultatul T2 | Familia **IDOR/BOLA**, primul subset limitat și calibrarea adaptivă pe circuitul complet sunt acceptate (§3.1/§4.1). Rămân cazul exact, oracle/controale, precondiții, efecte și criteriul detaliat de închidere. | M01 nu este închis prin trecerea discuției la M02; detaliile rămase se consolidează cu execuția/validarea M06 și probele M09. Inventarul/PoC-urile evaluatorului nu sunt date agentului drept soluție. |
| M02 — setup și autonomie | Cum se separă obiectivul, autorizația, scope-ul și efectele; ce ambiguități cer Needs you; ce acțiuni se execută autonom. | Comparația și recomandarea sunt în §3.2; mapa KEEP/EXTEND/NEW și direcția confirmată de reuse inclusiv backbone sunt în §3.3. Păstrăm engagementul și contractul canonic; avansarea discuției nu aprobă automat detaliile încă PROPUS sau închide M02. |
| **M03 — Engagement Map / AICI** | Colaborarea este decisă: un document logic comun per engagement, contribuții/corecții atribuite cu istoric și stări bazate pe probe. Rămân conținutul punctelor, referințele din delegare, simultaneitatea, freshness și prezentarea. | Acordul exact este în §5.1; cercetarea și restul propunerii în §5.2–§5.4. Document comun nu fixează un fișier fizic ori schema/API și nu aprobă toate detaliile tehnice. |
| M04 — delegare și context | Rolurile inițiale, granularitatea taskului, ce primește obligatoriu workerul, retrieval din hartă, ce predă, când mesaj către agent existent vs task nou, dedup și independența validatorului. | Goal/intentie/non-goals/context critic/refs/metodă/limite/încheiere/predare; fără inheritance automat al întregului istoric. Forma și regulile exacte sunt PROPUS, nu complete. |
| M05 — skills, modele și reuse | Subsetul de conținut/cod importat pentru întregul prim flux recon→mapping→threat model→investigație→validare, maparea toolurilor/formatele, proveniență/licențe, bibliotecă/pin, compatibilitate, default/override, pachete fixate și context mandatory. | Reutilizarea cerută și formatele verificate sunt în §4.1. Păstrăm direcția API-key-only. `openai-agents` este candidat, nu pin admis; nu adoptăm întregul manifest Strix. Nu importăm toate skills înaintea primului consumer. |
| M06 — execuție și validare | Primul transport real, policy/Stop la sink, capture/evidence/DATA, auth necesară cazului, investigator/triage/validator, ce produce CONFIRMED și ce produce INCONCLUSIVE. | Aducem explicit doar subsetul necesar T3/T4 în traseul T2 extins. HTTP trusted poate preceda browser/shell/scannere; nu le presupunem necesare și nu ocolim confinarea. |
| M07 — experiența operatorului | Ce apare în stream/hartă/inspector/finding, legătura părinte vs cauză, prompt redactat, reload/reconectare, clarificări/intervenții și controale active. | Reutilizăm baseline-ul UI; o singură sursă coerentă, nu hărți/contoare contradictorii. Nu se aprobă estetică nouă sau ecrane demo din registru. |
| M08 — lifecycle și resurse | Stop/Pause/HOLD/Resume, restart/checkpoint, pierdere de owner/răspuns, rezultate tardive/duplicate, stagnare, priorități și plafon de workeri. | Nucleele de siguranță preced efectele. MONITOR fără plafon total artificial LLM și Resume manual rămân canon; limitele tehnice/target rămân. Canonul are prima probă cu un copil, apoi maximum doi: o altă alegere cere decizie, nu copierea fan-out-ului Strix. |
| M09 — probe și comparație | Matrice finită de pozitiv/negativ/fault, efect așteptat, dovadă capturată, diagnostic owner și limita de reluare; baseline/reset/date lăsate de Strix, cleanup și comparație echitabilă. | Separăm defect de produs, harness, prerequisite lipsă și refuz legitim. Rezultate tipizate/efecte, nu fraze exacte LLM; probe afectate după editări, poarta completă la integrare. Regula existentă de două cicluri harness-only nu se resetează. |
| M10 — auto-pair | Handoff launcher→browser sigur, asociere inițială, browser existent/absent, expirare/logout, headless și recuperare. | Extindem traseul existent; nu auth Strix, URL cu secret, CDP ori scriere arbitrară în profilul browserului ca scurtătură implicită. Metoda rămâne de ales. |
| M11 — mini-plan final | Ordinea/dependențele subfeliilor, producătorul și primul consumer real, fișiere/calleri, verificarea și limitele, rollback și momentul acceptării. | Se completează după acordul punctelor de mai sus; reconciliere cu canonul, fără plan concurent și fără pornire automată a implementării. |

### 3.1. M01 — amplitudinea metodologiei IDOR/BOLA, înaintea cazului de acceptare

Operatorul a cerut verificarea metodologiei și a referinței Strix înainte de restrângerea cazului T2: skillul/agentul nu trebuie proiectat definitiv numai pentru exemplul cu doi utilizatori și citirea unui obiect. **IDOR/BOLA este ales; operatorul propune acum o primă variantă restrânsă pentru calibrare, cu extindere ulterioară. Cazul exact și efectele admise rămân de stabilit.** Metodologia, capabilitatea efectiv implementată și primul caz de acceptare sunt trei lucruri distincte.

**DECIS — direcție și principii metodologice:** operatorul a acceptat dimensiunile și adaptările descrise mai jos: folosim metodologia Strix ca bază, o adaptăm și o îmbunătățim pentru Omnis, fără wrapper și fără limitarea skillului la primul exemplu. Acest acord nu aprobă automat cazul concret, schema/API, toate transporturile în T2, amendamentul canonic, implementarea sau efectele live.

**DECIS — stabilirea drepturilor de acces:** operatorul declară regulile cunoscute (roluri, organizații, caracter privat/partajat și excepții), fără obligația unei specificații exhaustive. Omnis completează contextul prin discovery și îl consemnează în Engagement Map, distingând regulile declarate de comportamentul observat. Faptul că aplicația permite o operație nu dovedește că accesul este intenționat. Când regula rămâne ambiguă, păstrăm candidatul neconfirmat și cerem clarificarea necesară; nu inventăm nici vulnerabilitatea, nici un verdict sigur. Acest acord privește proveniența și interpretarea regulilor, nu schema hărții sau extinderea autorizației ROE.

**Direcție cerută — prima variantă și calibrare:** pornim cu skillul limitat și adaptat din Strix, păstrând posibilitatea completării sale, și întregul traseu de prompting/context către agentul cu modelul selectat. Prima execuție de dezvoltare pe aplicația operatorului trebuie să permită observarea acțiunilor, rezultatelor și deciziilor explicite, apoi compararea cu traseul Strix, pentru ajustări concrete. Nu cerem un endpoint, o succesiune fixă de acțiuni, un text ori un finding prestabilit și nu introducem soluția Strix în promptul investigatorului. Comparația privește fapte observabile și justificări explicite, nu raționament privat. Această cerere de discutare a abordării nu lansează implementarea sau execuția.

**Distincție de evaluare propusă:** testele nu sunt instrucțiuni de atac și nu trebuie să ajungă ca răspunsuri așteptate în contextul agentului. Păstrăm verificări determinate pentru scope, identitate, Stop și integritatea probelor; evaluăm concluziile prin regula business și datele/efectele observate, nu prin HTTP200 sau o formulare LLM. Un 200 poate conține login, eroare ori redirect în conținut; redirecturile HTTP și destinația finală trebuie interpretate în context, cu fiecare hop autorizat. Comparația cu Strix trebuie să țină cont de starea aplicației, identități și informația disponibilă; raportul upstream nu este singur dovadă de adevăr.

**Calibrare ≠ închidere T2:** o execuție exploratorie poate produce un candidat, un rezultat negativ limitat, o incertitudine sau un blocaj fără a forța o vulnerabilitate. Observarea utilă nu demonstrează automat eficacitatea pentesterului. Cerința D03 de cel puțin un finding confirmat independent la închiderea T2 nu a fost retrasă explicit; alegerea unui protocol adaptiv nu o închide și nu o înlocuiește în tăcere. Efectele/costul/datele cer aprobările lor înaintea oricărei execuții reale.

**Analizat public, STATIC_NOT_TESTED:** Strix `skills/vulnerabilities/idor.md` și `broken_function_level_authorization.md`, la pinul §4.[30][31] Comparație cu OWASP API Security 2023 API1/API3 și WSTG v4.2 WSTG-ATHZ-04.[32][33][34] Nu s-au reluat analiza findingurilor blocată, testele ori ținta.

| Axă metodologică de păstrat în proiectare | Variante/context relevante, nu activare implicită |
|---|---|
| Actor și permisiune | Anonymous, owner/non-owner, roluri diferite, relații de partajare; o identitate privilegiată nu demonstrează accesul nepermis al uneia obișnuite. |
| Obiect și relație | Obiecte private/publice/partajate, parent–child, organizație/proiect/tenant și identificatori simpli, opaci sau compuși. |
| Acțiune și efect | Citire, creare/modificare/ștergere, export, partajare ori acțiuni de workflow — numai când ROE și adaptorul le permit, cu probă/cleanup adecvate. |
| Localizarea referinței | Path/query/body/form/header și formele relevante ale identificatorului; metodologia nu se limitează la un integer într-un URL. |
| Suprafață și transport | List/search/detail/bulk, fișiere și joburi; variante API/GraphQL/WS/gRPC doar dacă există și sunt admise. O variantă nesuportată rămâne gap/UNSUPPORTED, nu este testată fictiv. |
| Clasificarea rezultatului | BOLA privește accesul la obiect; BFLA privește funcția/acțiunea nepermisă, iar API3 accesul nepermis la proprietăți. Indiciile vecine cer clasificare/handoff, nu același verdict sau raport duplicat. |
| Context schimbător | Auth expirat/invalid, rol/tenant/context schimbat, cache/flow și dovezi stale; un test fără precondiții valide nu este negativ sigur. |
| Dovadă și controale | Identitate verificată, regulă business de acces, obiect și operație exacte, rezultat/impact observat, control legitim și replay independent; semnalele slabe rămân candidați. |

Strix descrie explicit o matrice Subject × Object × Action, acces orizontal/vertical/cross-tenant, forme și locații variate ale referințelor, operații bulk/job/file și verificări pe transporturi; nu este doar o rețetă A→obiectB.[30] WSTG recomandă identificarea locațiilor referințelor și identități/obiecte de test care economisesc ghicitul, păstrând regula business.[34]

**Adaptări acceptate ca principii, nu copiere oarbă și nu implementare autorizată:**
- `owner != actor` sau HTTP200 nu sunt suficiente: accesul poate fi legitim prin partajare ori rol. OWASP cere permisiunea asupra acțiunii și obiectului; proprietățile și funcțiile au frontiere distincte.[32][33]
- Strix cere în secțiunile sale Validation demonstrații pe cel puțin două transporturi/encodings. Nu transformăm asta într-un prerequisite artificial al confirmării când aplicația are un singur transport aplicabil; trasabilitatea și controalele sunt obligatorii, iar breadth-ul aplicabil se evaluează separat.[30][31]
- Semnale de existență, dimensiune/timing, o identitate greșită sau un răspuns gol nu sunt automat expunere confirmată. Păstrăm public/shared/owner și auth-invalid între controale, cu rezultate distincte.
- Cunoașterea unei variante nu acordă tools, permisiuni ori auto-fallback. T2 primește subsetul necesar cazului ales; restul rămâne documentat și se introduce cu consumerul său real.

**Limită a probelor, nu condiție pentru discuție:** apelul anterior de analiză a findingurilor a fost refuzat de provider invocând cerințele de securitate ale contului; acea încercare rămâne BLOCKED și nu a fost reluată sau rerutată. Nu transformăm acest refuz într-o cerință a Omnis ori într-o condiție pentru discutarea și alegerea metodologiei. Studiul public nu înlocuiește analiza detaliată a probelor reale și nu validează findingurile aplicației. Eventuala reluare a apelului refuzat se tratează separat de acordul de proiectare, fără ocolirea refuzului.

### 3.2. M02 — setup, scope și autonomie: comparație OSS și recomandare

**RESEARCH_COMPLETED_SCOPED / STATIC_NOT_TESTED / M02_PROPOSED_NOT_APPROVED.** La cererea operatorului au fost analizate Strix și două proiecte OSS, fără rulări, conturi, servicii ori trafic de țintă. Comparația folosește surse fixate, nu presupune identitate cu binarele instalate și nu certifică siguranța globală a produselor. Cele trei artefacte au fost agregate prin cod: 3 proiecte distincte, 23 constatări statice (7/8/8). Părintele a recitit contractele și callerii decisivi, nu a acceptat doar rezumatele copiilor.

| Proiect / pin | Comportament observat și limită | Transfer util Omnis |
|---|---|---|
| Strix `6b7ae2ebe4d47037a927aade23265ff4e4f27e84` | Configurația separă targets și instrucțiuni; `build_scope_context` adaugă base URLs ale unui API spec ca ținte autorizate.[40] `scope_rules` gestionează filtre Caido pentru traficul văzut de tools, nu dovedește blocarea egress-ului tuturor toolurilor.[42] `wait_for_user` parchează agentul interactiv și refuză parcare pentru user într-un run autonom.[43] | **ADAPT:** setup simplu și mecanica de întrebare/parcare/reluare. **NU:** autorizare implicită din spec/text sau filtru de vizualizare prezentat drept policy universală. |
| PentAGI `cffed9485aa1cca70762cd08a57ac62a80406258` | `CreateFlow` citit are input liber, provider, functions și resources, nu ROE structurat în acel payload.[45] `AskUser` este înregistrat ca barrier când este activat; performerul setează stop la barrier, dar iese după batch, astfel apelurile rămase pot continua dacă nu apare eroare.[46][47] | **ADAPT:** input→plan→execuție→rezultat→replan și intervenție explicită. **NU:** input unic drept autoritate sau presupunerea că o cerere de ajutor oprește imediat orice dispatch din același batch. |
| NeuroSploit `92e8959f4ea17bddaa0436505edcddf98f7d6b16` | Harnessul Rust are scope structurat, excluderi prioritare și `observe_only`; clasificarea requestului folosește însă verbul HTTP, iar matchingul nu este echivalent cu origin exact+port+path.[49] Pe ruta web REPL citită, `scopePath` este produs, dar nu este transmis de `authArgs`/`buildReplScript`.[48] Clientul HTTP citit urmărește redirecturi către alte hosturi publice fără revalidare ScopePolicy per hop.[50] | **ADAPT:** separarea obiectivului/contextului de ROE și explicarea refuzului. **NU:** parserul/matchingul copiat orbește, GET=read-only, pierderea ROE între UI și consumer ori auditul post-factum ca substitut pentru admitere înainte de trafic. |

**Recomandare pentru Omnis — păstrăm și facem utilizabil contractul existent, nu un al patrulea framework:** arhitectura §7/§8 definește deja origin/port/path, `ATTACKABLE/VISIT_ONLY/BLOCKED`, efecte și identități. Nu atribuim aceste trei categorii Strix și nu afirmăm că sunt deja impuse de codul produsului. Cercetarea informează alegerea comportamentului/formularului și reutilizarea, nu schimbă singură canonul.

1. **Misiune/context în prompt; scope/ROE în câmpuri structurate.** Secretele rămân referințe controlate prin fluxul dedicat, nu instrucțiuni sau fișiere de context. Un API spec, link, redirect sau host înrudit este informație de discovery, nu grant nou.
2. **Trei utilizări explicite:** testabil; numai utilizare funcțională; interzis. VISIT_ONLY permite numai workflowurile declarate, de exemplu login/refresh/SSO, nu orice GET, crawling ori test asupra aceluiași serviciu. BLOCKED câștigă; lista goală/necunoscută nu înseamnă allow-all.
3. **Efectul operației separat de verbul HTTP.** Identitatea și regula business rămân explicite; `UNKNOWN` nu devine read-only. Nu adăugăm acum scor de risc sau motor de approval upstream.
4. **Un singur ROE versionat și citit înapoi:** Save→reload→Start trebuie să păstreze și să consume aceeași configurație admisă, nu două interpretări în formular și runner. Un sumar lizibil înainte de Start explică permisiunile, fără confirmări repetate pentru fiecare request deja permis.
5. **Autonomie în grant, intervenție numai pentru o nevoie reală:** context/identitate/regulă lipsă, efect neadmis sau extindere de scope. Needs you cere o informație/decizie concretă; răspunsul liber nu modifică implicit politica. Cererea de context și aprobarea unei acțiuni rămân lucruri distincte.
6. **Admitere înainte de efect:** fiecare request, redirect și subrequest trece prin autoritatea Omnis. Stop/refuzul/pauza relevantă trebuie să blocheze următorul dispatch, inclusiv într-un batch; efectele deja trimise rămân in-flight/UNKNOWN până la reconciliere. Un filtru de trafic, un flag Confirm sau un răspuns API reușit nu probează asta.

**Limite și lucru evitat:** inspecție statică pe trasee selectate; PentAGI și NeuroSploit sunt snapshoturi parțiale, nu checkouturi complete. Nu au fost probate upstream rețeaua/sandboxul, toate căile browser/MCP ori comportamentul instalat. Constatarea despre batch/propagarea scope/redirecturi este de sursă, nu replay. Nu au fost copiate runtime-uri, servicii, limite totale LLM ori scheme de autentificare subscription; API-key-only și MONITOR Omnis rămân direcțiile stabilite. Importurile efective cer verificarea licenței/notices și a compatibilității. Recomandarea este suficientă pentru a discuta alegerea M02, nu pentru un PASS de execuție.

### 3.3. M02 — mapa de integrare în codul Omnis, cerută de operator

**INTEGRATION_PROPOSAL / SOURCE_INSPECTED / IMPLEMENTATION_NOT_STARTED.** Bază inspectată `ddb2841bc4b5d6c59c84ea0ee4e32c4a28df5941`. Aceasta detaliază producători, consumatori și limite pentru mini-plan, nu introduce o ordine de implementare concurentă. Cererea „cum le integrezi” este analiză de integrare, nu mandat de scriere a codului sau execuție.

**Constatare importantă:** cele trei categorii nu trebuie importate din Rust/Go: `ScopeAccess` și `ScopeEntry` există în `api/src/omnis/modules/engagements/schemas.py:53`, iar selectul lor este deja în `web/src/features/engagement/Wizard.tsx:260`. Acestea validează/salvează date declarative; nu demonstrează enforcement la trafic.

**Direcție confirmată — backbone prin reuse înainte de cod nou:** operatorul cere aceeași prioritate și pentru lipsurile de infrastructură, nu numai pentru skills/prompturi. Pentru fiecare seam verificăm întâi implementarea Strix și biblioteca folosită: folosim biblioteca compatibilă sau copiem/portăm unitatea utilă, păstrăm componentele Omnis deja funcționale și scriem numai adaptarea/invariantul care nu poate fi preluat corect. **NEW în tabel înseamnă destinație/legătură nouă în Omnis, nu obligația de a rescrie implementarea de la zero.** În mini-plan, fiecare unitate va avea sursa/pinul, modul de reuse, modificările, primul consumer și verificarea relevantă; o reimplementare cere motiv concret. Nu copiem runtime-ul Strix ca aplicație și nu înlocuim autoritatea/persistența Omnis.

Inventarul existent a fost recitit selectiv și agregat prin cod: 32 unități distincte, încă propuneri, nu importuri admise. Pentru backbone folosim în special R06 (biblioteca Agent/Runner și `factory.py`/`core/runner.py`/`core/execution.py`), R08–R13 (tools, spawn, completion, mailbox/wait, context și checkpoint/session), R19/R20/R23 (output bounded, usage și evenimente). Clasificarea/ordinea veche din acel inventar este proveniență; subsetul necesar primului flux real se reconciliază în mini-plan, nu se transferă automat ca alt plan.

**Compatibilitate de verificat, nu motiv de rescriere:** manifestul Strix inspectat cere `openai-agents[litellm]>=0.19.0,<0.20` și `openai>=2.45.0,<3`.[51] Omnis declară acum `openai==2.24.0` (`api/pyproject.toml:20`). Aceasta arată diferența dintre manifestele produselor, nu dovedește singură că SDK-ul nu se poate integra. Evaluăm pinul/subsetul necesar fără a importa automat extras, clienți cloud sau întregul manifest și fără upgrade implicit al fundației T1; rezolvarea/compatibilitatea efectivă rămân NOT_RUN.

| Legătură | Păstrăm din Omnis / stare observată | Integrarea propusă și primul consumator |
|---|---|---|
| Formular → draft | `Wizard.tsx:17` are cinci pași; `WizardSections.tsx:59` reguli de efect/date/bugete, `ReviewStep:98` citește ultima revizie salvată. | **KEEP/EXTEND:** același wizard și baseline vizual; completăm numai câmpurile și stările necesare execuției, fără încă un formular sau un wizard copiat. Contextul alimentează promptul; scope/ROE alimentează admiterea deterministă. |
| Draft → API → PostgreSQL | `web/src/shared/api/client.ts:217` folosește GET/POST/PUT existente; `engagements/routes.py:59`/`:117` și `EngagementService.create/edit` păstrează digest, istoric, CAS și command ID. `service.py:79` face readback după commit. | **KEEP:** nu alt config store ori fișier JSON autoritativ. Extinderile de payload se fac strict/versionat, păstrând vechile revizii. Nu presupunem migrare DB până când un câmp/constraint nou o cere. |
| Draft salvat → Start → run fixat | `api.py:68` montează routerele de draft/Settings/model-test; `Wizard.tsx:303` are Start assessment dezactivat. Formularul nu produce încă o evaluare T2. | **NEW, propus:** admitere de assessment în ownerul existent și namespace-ul `modules/runs/`; locator propus `assessment_admission.py`. Primește referința exactă a reviziei/digestului și configurația calificată; verifică autorizația, ROE, DATA, model/pachet/identități și precondiții; produce snapshotul și identitățile trusted run/task/attempt pentru noul consumer T2. Nu există acest consumer prin simpla redenumire a unui run istoric. |
| Snapshot/context → prompt și delegare | `modules/tasks/managed_composition.py:1` păstrează compoziție/ref/provenance; materialele `:67` sunt explicit CONTRACT/NO_MODEL. `execution_selection.py:1` este selecție NO_MODEL, nu model implicit/override agentic. | **ADAPT/VERSION:** reutilizăm parsarea/digesturile și ordinea base→rol→assignment→metodă→skills din conținutul Strix, dar cu producător/contract T2 distinct. Nu scoatem interdicțiile din probele istorice. Contextul modelului este o proiecție redactată; ROE și capabilitățile efective rămân verificate în afara prozei. |
| Acțiune agent → policy → transport țintă | `api/src/omnis/policy/` conține politici de model/configurație/buget; pe traseul activ inspectat nu este demonstrat un broker de trafic target M02/T2. Host/Origin local protejează API-ul, nu ținta engagementului. | **NEW, propus:** admitere de acțiuni target în același namespace policy; locator propus `target_actions.py`, consumat obligatoriu de primul transport HTTP/evidence admis. Leagă origin/port/path, excluderi, acces, identitate/epoch, efect, Stop și limite înainte de send; fiecare redirect/subrequest se verifică separat. Nu un serviciu nou sau un parser de scope copiat din NeuroSploit. |
| Model selectat → inferență agentică | T1 are seif/sender/relay/Stop proprii. `supervisor/model_sender.py:313` folosește `Projection` de model-test și `:373` verifică ACK exact. `api/pyproject.toml:20` declară clientul `openai`; `openai-agents` nu este dependență declarată în manifestul inspectat. | **KEEP/ADAPT:** păstrăm ownerul, protecția secretelor, admiterea egress și contabilizarea; introducem contractul T2 pentru conversație/tool calls și rezultate fără slăbirea verificării T1. SDK-ul agentic/pinul și closure-ul se admit separat înainte de a atribui implementarea loopului; Test model nu devine endpointul de pentest. |
| Identitate → verificare → permisiune | `Wizard.tsx:271` declară target secrets/Verify login indisponibile. `EffectRule`/`BusinessMatrixEntry` sunt date declarative; `operation_refs` acceptă numai lista goală, `workflow_profile_ref` și `business_rules_ref` sunt încă null. | **EXTEND cu primul caz real:** reutilizăm mecanismul de seif T1 în namespace target și producem identități/receipts prin fluxul operatorului, înainte de Brain; fără worker fictiv pentru Verify login. Legăm numai operații/workflowuri/refs existente și verificate, nu strings de endpoint interpretate ca grant. Anonymous rămâne valid pentru reconul care nu cere auth. |
| Agent → Needs you → răspuns → reluare | Modelele AskUser/wait din comparația §3.2 sunt surse de semantică, nu handlers existenți în API-ul Omnis inspectat. | **NEW T2, în run/task/inbox și proiecția engagementului existente/proiectate:** păstrăm motivul, întrebarea și referințele cauzei; blocăm următorul dispatch dependent inclusiv în același batch. Un răspuns se corelează și revalidează; schimbarea ROE este comandă explicită. Nu portăm procesele Go/Rust sau REPL-ul upstream și nu creăm un scheduler separat. |

**Ce copiem/portăm efectiv:** conținutul metodologic și rubricile utile Strix intră în pachete de produs sub `skills/<pachet-nou>/`, cu `SKILL.md`, `omnis.yaml`, references/schemas și notices, ca draft/candidate; activarea așteaptă admiterea consumerului. Nu în `.hermes/skills/` și nu în locul pachetelor istorice. `skills/recon-mapping-contract/SKILL.md:11` și manifestul său `:14` sunt explicit sintetice/PURE, fără efecte; nu le promovăm prin redenumire la recon real. Din PentAGI preluăm/portăm semantica de plan/result/replan și cerere de input; din NeuroSploit separarea ROE/context și motivul refuzului; nu copiem literal implementările Go/Rust când DTO-urile și persistența Omnis există deja. Sursele, pinurile și limitele sunt §3.2/§4.1.

**Prerequisite și compatibilitate care nu pot fi ascunse:** draftul inspectat limitează obiectivul la 8192 code points/32768 UTF-8 bytes, scope-ul la 64 intrări și payloadul canonic la 1_000_000 bytes. Compoziția finală T2 are nevoie de propriul contract complet de dimensiuni/model/tool output; nu presupunem că aceste limite ale formularului sunt buget de context. `DraftBudgets.max_model_calls` și UI „Maximum model calls (declarative only)” păstrează încă forma veche; trebuie un delta versionat pentru MONITOR versus FINITE_TEST, nu `0=unlimited` inventat. Se păstrează citirea vechilor înregistrări fără rescriere sau reinterpretare tacită. Admiterea SDK-ului, producerii T2 și reconcilierea T2 inert→primul flux real în canon rămân necesare; mapa nu le declară realizate.

**Prima demonstrație după implementare/review:** operatorul folosește wizardul real → salvare/readback → Start pe exact configurația admisă → Brain/worker primește contextul și skillul fixate → acțiune reală admisă și probă capturată → rezultat consumat și vizibil. Refuzurile se verifică la aceeași graniță (revizie stale, scope/efect nepermis, input/identitate lipsă, Stop), fără predeterminarea endpointului sau răspunsului LLM. Testele existente de draft (`api/tests/test_engagements.py`, `web/src/app/Wizard.test.tsx`) rămân baza și se extind numai unde se schimbă comportamentul; noile controale de admitere/transport/Needs you se probează pe consumatorii lor, apoi prima calibrare funcțională rămâne pe aplicația operatorului. Nu este un nou demo sintetic și nu este o listă de teste deja executate.

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

### 4.1. Reutilizarea întregului prim circuit, nu doar a skillului IDOR

**Direcție confirmată de operator:** reutilizăm substanțial din Strix conținutul și componentele utile recon/mapping/threat model, promptingului, specializărilor și legăturilor dintre agenți. Le adaptăm la Omnis, observăm primul flux complet pe aplicație și comparăm rezultatele/traseele pentru a localiza lipsa reală: recon, mapping, context, delegare, investigație, tools sau validare. Nu compensăm o hartă incompletă numai prin schimbarea promptului ultimului agent. Nu este wrapper, copiere a întregului produs ori mandat de implementare/execuție în sesiunea de discuție.

**Formate verificate în sursa fixată, STATIC_NOT_TESTED:** skillurile sunt fișiere Markdown cu frontmatter YAML, parsate separat de corp; numai cele cu `template: jinja` sunt randate ca template.[35] Compoziția promptului este Python/Jinja, cu componente comune, specializări și contextul runului; nu este un singur JSON/YAML copiat pentru toate rolurile.[10][36] Toolurile de delegare/finalizare și threat model sunt funcții Python tipizate expuse prin SDK, cu rezultate JSON; modelul partajat conține metodologie/text Markdown și amendamente, nu un pachet de skill executabil.[11][23]

| Piesă reutilizată pentru primul circuit | Ce păstrăm/adaptăm în Omnis |
|---|---|
| Root coordination și compoziția prompturilor | Brain coordonator, obiectiv/intenție, metodologie comună și selecția contextului relevant, nu toate skills în fiecare worker.[10][17] |
| Recon și mapping | Discovery-ul aplicației în scope, suprafețe/operații/parametri/auth/roluri și proveniența lor. `asset_discovery.md` este pentru descoperire largă și cere explicit scope adecvat; nu îl facem prerequisite pentru un singur URL de aplicație.[36][37] |
| Threat model comun | Actori, trust boundaries, suprafețe, reguli/assumptions și corecții atribuite, legate de Engagement Map; adaptare la starea/reviziile Omnis, nu o a doua persistență JSON autoritativă.[17][23] |
| Investigație și verificare | Skill IDOR/BOLA restrâns inițial, conținut metodologic și controale relevante, apoi validator independent. Nu importăm automat tooluri/efecte doar fiindcă sunt pomenite în text.[30] |
| Delegare, mesaje și predare | Reutilizăm ideile și codul compatibil pentru task/skills, sumar, observații, open items și recomandări. Adaptăm la brief/result refs și lifecycle Omnis; nu inheritance implicit al întregului istoric și nu prose `findings` tratată ca înregistrare confirmată.[11] |
| Observabilitate | Același fir de intrări/ieșiri adresabile pentru Brain stream și inspector: prompt/context redactat, skill/model/revizie, acțiuni, rezultate și predare. Diagnosticul se face la etapa care a produs gapul, nu din verdictul final singur. |

**Maparea formatelor, fără framework nou:** contractul Omnis existent în arhitectură §9.4 definește `SKILL.md`, `omnis.yaml`, referințe și scheme JSON. Păstrăm conținutul upstream util și îl legăm de aceste contracte, tooluri și scheme de input/output; nu inventăm un al doilea loader ori o variantă paralelă de manifest. Fișierele de stare ale runului Strix sunt referință de semantică/proveniență, nu înlocuitor pentru persistența Omnis. Proveniența, pinul, licența și modificările se păstrează pentru fiecare import; sursa fixată are Apache-2.0.[38]

**Adaptări necesare, nu numai redenumiri:** promptul general și compoziția Strix includ presupuneri despre autorizație deja acordată și capabilități shell/browser, iar reconul larg presupune tooluri și expansiune de assets.[10][36][37] Le înlocuim cu autoritatea/ROE, capabilitățile efectiv admise și sandboxul Omnis. Nu încărcăm toată infrastructura/scannerele pentru prima probă și nu tratăm instrucțiunea dintr-un skill ca enforcement. Nu copiem fallbackul la prompt gol sau omiterea silențioasă a unui skill necesar din compoziția/loaderul upstream.[10][35]

**Extindere ulterioară:** aceeași infrastructură trebuie reutilizată pentru familii care au capabilități compatibile. O clasă nouă poate cere doar metodologie/configurație și reguli de validare noi, dar un protocol, un efect, o identitate ori un oracle nesuportat poate cere adaptor/cod și verificări suplimentare. Mai multe fișiere nu înseamnă automat mai multă acoperire executată. Primul subset trebuie să fie complet pe traseu; inventarul celor 75 skills rămâne sursă/candidat, nu catalog executabil admis integral.

## 5. Engagement Map — cercetare, decizii și propuneri

### 5.1. Colaborarea acceptată și forma minimă propusă

Operatorul a cerut o hartă comună, consultabilă și actualizabilă de agenți, cu puncte/subpuncte folosite în delegare: ce s-a identificat, testat, pe ce parametri, ce a rămas și unde este nevoie de operator.

**DECIS — un document logic comun per engagement:** operatorul a confirmat explicit această unitate, nu un document per agent și nu o hartă globală între engagementuri. Agenții pot consulta informațiile relevante și adăuga observații, ipoteze, probe, indicii și corecții inclusiv la contribuțiile altora, cu autor, motiv și istoric, fără ștergere sau suprascriere tăcută. Brain folosește harta pentru prioritizare și delegare; „testat” rezultă din execuție documentată, iar „confirmat” necesită validarea corespunzătoare, nu eticheta unilaterală a investigatorului. Accesul rămâne în limitele engagementului/DATA. „Document” descrie obiectul comun de lucru; formatul fizic, schema și mecanismul de actualizare nu sunt alese prin acest acord.

**PROPUS pentru Omnis:** o vedere coerentă a datelor existente de inventory/observations/tasks/evidence/coverage, în PostgreSQL, nu încă o sursă de adevăr. Delegarea păstrează goal-ul, intenția, non-goals și contextul critic; referințele stabile către hartă înlocuiesc repetarea întregului istoric, nu sarcina. Agenții pot cere detalii relevante la nevoie.

De detaliat/agreat în continuare, fără redeschiderea regulii de colaborare:

- Conținutul unui punct și maparea exactă a contribuțiilor/stărilor la roluri: observații/ipoteze/contradicții/continuări versus stări derivate din execuție sau rezervate validării.
- Mecanismul tehnic al corecțiilor și concurenței: istoricul/atribuirea sunt acceptate, dar versionarea, rezolvarea conflictelor și refuzul suprascrierilor stale trebuie concretizate.
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

### 5.4. Recomandarea rezultată — principii parțial acceptate, detalii propuse

1. **Un singur document logic/hartă per engagement — DECIS.** Persistența în PostgreSQL existent și proiecțiile pentru agenți/UI rămân recomandarea tehnică PROPUSĂ; notes/RAG/sumare sunt derivate, nu altă autoritate a probelor.
2. **Index/metadata întâi, detaliu la cerere:** citiri bounded pe puncte și referințe relevante, fără dump al întregii hărți în fiecare prompt și fără relaxarea accesului către alt engagement.
3. **Fapte și relații adresabile, cu proveniență:** cine/ce task a observat, sursa și dovada, revizia și contextul; observed/inferred/contradicted nu se reduc la confidence.
4. **Corecții atribuite și istoric — DECIS; controlul reviziei — PROPUS:** actualizări înguste și refuzul suprascrierii stale; contradicția se păstrează până la adjudecare, nu „ultima propoziție câștigă”. Nu acordăm agenților acces SQL direct.
5. **Freshness și invalidare în ambele sensuri:** o schimbare de auth/precondiții poate cere reverificare. Un rezultat istoric rămâne în istoric, dar nu certifică automat starea curentă; concluziile nu pot doar să se întărească.
6. **Coverage bazat pe execuție/probe — principiu DECIS**, distinct de inventar, task alocat sau agent selectat. Granularitatea exactă rămâne de stabilit; un request ori un sumar nu închide toate metodele/identitățile/parametrii acelui punct.
7. **Schimbări ale hărții legate de evenimentele Omnis și aceeași revizie**, pentru stream, retrieval și reload coerente. Nu adăugăm alt scheduler, publisher autoritativ, graph canvas sau serviciu de memorie pentru această funcție.

Această recomandare combină mecanisme concrete din cele trei surse. Acordul §5.1 nu aprobă automat toate punctele: importurile efective, schema, API-urile, mecanismele de scriere/citire și restul alegerilor rămân M03/M04/M06/M07. Codul public inspectat nu certifică eficacitatea, izolarea ori compatibilitatea integrării Omnis.

### 5.5. Îmbunătățiri și format/livrare — comparație documentară și variantă recomandată

**DOCS_REVIEWED / PROPUS / NOT_IMPLEMENTED.** Operatorul consideră potrivită organizarea în suprafețe, context de acces, investigații și progres, dar cere îmbunătățiri și compararea formatului/livrării înaintea alegerii finale. Nu tratăm această apreciere ca aprobare a schemei sau a tuturor detaliilor. Reutilizăm analiza de cod Strix/PentAGI/NeuroSploit din §5.2–§5.3; completarea de aici este documentație oficială de produs/standard, nu audit de cod sau rulare a unor proiecte noi.

| Referință complementară | Ce este documentat | Adaptare propusă / limită |
|---|---|---|
| Dradis **Pro**, documentație oficială | API JSON cu entități distincte pentru Nodes, Issues, Evidence și Methodologies; Node properties consolidează informația adusă de mai multe pluginuri în locul unor notes fragmentate.[54][55] | Un punct comun cu proprietăți/legături și probe adresabile; prezentare lizibilă derivată. Nu atribuim API-ul Pro ediției OSS și nu importăm cod comercial. |
| DefectDojo, documentație oficială | Deduplicare, aceeași pagină/context pentru original și istoric de import/reimport.[52][53] | Identitate stabilă pentru același punct și istoric al contribuțiilor, fără pierderea probelor distincte. **Nu copiem** închiderea pe absență din raport sau eliminarea potrivirilor: lipsa într-o investigație adaptivă nu demonstrează FIXED ori tested_no_issue. |
| Agent Skills, specificație publică | Progressive disclosure: metadata → instrucțiuni → resurse la nevoie.[56] | Adaptăm principiul la indexul hărții → punctul relevant → probe la cerere. Nu este un standard de Engagement Map și nu adăugăm alt loader/runtime sau permisiuni din metadata. |

CAI a fost verificat ca posibilă referință suplimentară, dar pagina primară îl declară arhivat/read-only; nu este selectat ca nou backbone sau sursă necesară acestui punct.[57] Nu urmărim încă un catalog de platforme: exemplele de mai sus completează exact identitatea/istoricul și livrarea contextului, iar backbone-ul rămâne cel discutat în §3.3/§4.1.

**Varianta recomandată pentru Omnis, încă de ales:**

1. **Un document logic, nu un singur text rescris.** Date canonice structurate în PostgreSQL existent, accesate prin DTO-uri JSON versionate; textul explicativ poate fi Markdown. UI-ul/documentul lizibil și sumarul pentru agent sunt proiecții ale aceleiași revizii, nu copii autoritative. YAML rămâne pentru configurația/pachetele declarative, nu formatul de editare concurentă a stării live. Nici JSON, nici Markdown nu acordă singure autoritate.
2. **Puncte legate, nu doar un arbore de titluri.** Operație ↔ parametru/obiect ↔ identitate/rol ↔ observație/ipoteză ↔ încercare/probă ↔ task/finding. Deduplicăm punctul/operația numai după identitate verificată; nu amestecăm rezultate ale altor identități, tenants, obiecte sau revizii. Fiecare observație își păstrează proveniența, inclusiv cea negativă sau contradictorie.
3. **Context și valabilitate explicite.** Păstrăm ce știm versus ce presupunem, când și în ce condiții s-a observat, auth/rol/tenant și versiunea țintei când este disponibilă. O schimbare relevantă marchează necesitatea reverificării, nu șterge istoricul și nu relansează automat efecte. Relația cu scope-ul se citește din autoritatea fixată: descoperit nu înseamnă autorizat.
4. **Livrare progresivă, aceeași bază.** Brain primește index/sumar și stări relevante; workerul primește goal/intention, contextul critic și refs către puncte, apoi poate cere detaliul și probele necesare. Scope/auth/limitele obligatorii nu sunt omise din brief în numele economiei. Schimbările pot folosi cursorul/evenimentele Omnis; dacă delta nu este disponibilă, recitim punctul calificat, nu inventăm context și nu construim un transport nou doar pentru hartă.
5. **Lucru rămas și responsabilitate vizibile.** Gapuri, blocaje, întrebări operator, indicii și următorul pas propus; alocarea/ownerul vin din taskurile existente, nu dintr-un al doilea scheduler sau din declarația liberă a agentului. Starea de lucru este distinctă de verdict și de coverage. Nu afișăm un procent de testare a întregii aplicații din universul doar descoperit.

**Pentru primul T2:** prioritate pentru puncte stabile, contribuții cu istoric/probe/context, index + detaliu la cerere și legarea la taskurile/streamul reale. Deltas avansate, căutare semantică, embeddings, graph DB, canvas de attack graph și memorie comună între engagementuri sunt DEFER până când un consumer sau un gap măsurat le justifică; nu sunt prerequisite ascunse. Formatul propus trebuie probat în calibrare prin contextul efectiv primit și acțiunile modelului, fără a impune o traiectorie ori o formulare fixă.

**Decizia cerută:** păstrăm baza deja agreată și alegem modelul structurat cu vedere de document + consultare progresivă, păstrând probele/valabilitatea/lucrul rămas explicit. Recomandarea nu pretinde „cea mai bună variantă universală” și nu aprobă schema/API sau modificarea canonului. Documentația publică nu demonstrează CAS, confinare ori integrare Omnis; importurile de cod rămân de admis separat.

## 6. Reguli rămase din canon și implicațiile schimbării T2

- Direcția runtime rămâne API-key-only OpenRouter/OrcaRouter, cu Hermes/Codex numai tooling de dezvoltare. Nu se redeschide alegerea runtime-ului prin cercetarea hărții.
- Persistența canonică, autorizația, DATA, contabilizarea, Stop și finalizarea rămân Omnis; biblioteca de agenți oferă mecanică.
- MONITOR fără plafon total artificial LLM; HOLD/Resume manual, fără retry/fallback implicit. Limitele per operație și limitele target nu dispar.
- Canonul curent: plan §7 T2 inert; §9 HTTP/evidence și B08; §11 prima metodologie/validare; §14 replan extins. Direcția cerută în D02/D03/D06/D07 impune un amendament de ordine/scope pentru subsetul necesar, nu declararea lor retroactiv implementate.
- Prima observație reală are nevoie de transport autorizat și captură; confirmarea unei vulnerabilități are nevoie suplimentar de metoda, precondițiile, controalele și replay-ul adecvate. Nu cerem toată infrastructura BOLA pentru un simplu recon anonim și nu declarăm reconul finding confirmat.
- Probele viitoare trebuie să păstreze baseline-ul aplicației și să țină cont de mutațiile lăsate de Strix. Reset/copie izolată, credentiale, date către model, cost și efecte cer dispoziția explicită necesară; nu sunt autorizate de această notă.

## 7. Recuperare și următorul pas

**AICI: M03 — alegerea formatului și livrării după îmbunătățiri.** Colaborarea per engagement din §5.1 este decisă. Operatorul consideră bună baza de conținut, dar cere alegerea celei mai potrivite variante după comparație; completarea documentară și recomandarea sunt în §5.5. Propunem date structurate cu vedere de document, puncte legate/proveniență/context/valabilitate și index→detaliu→probe la cerere, pe fundația Omnis, fără infrastructură nouă implicită. Alegerea finală și schema/API rămân deschise; nu repetăm un audit general. M01/M02 nu sunt închise automat: cazul/precondițiile/efectele/controalele/exitul se consolidează cu M06/M09, iar SDK/pinul, modelul de execuție, integrarea și delta MONITOR se detaliază cu M05/M08. Nu relansăm dovezi T1 neschimbate. Nu este mandat de amendament canonic, implementare, apeluri provider/țintă ori push.

După fiecare decizie, actualizăm rândul și detaliile sale în acest fișier; o întrebare rămasă nu devine „decisă” printr-un rezumat. Când toate punctele necesare sunt suficient de clare, consolidăm mini-planul cu subfelii, reutilizare, dependențe, consumer/exit real, verificări și limite, apoi cerem separat aplicarea amendamentului și mandatul de implementare.

**Neexecutat:** cod de produs, instalări/upgrade, schimbări DB/operator/servicii, model/provider/țintă, browser QA și push. Nota nu este o acceptare tehnică a funcționalităților discutate.

## Sources

[10] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/agents/prompt.py
[11] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/agents_graph/tools.py
[17] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/skills/coordination/root_agent.md
[22] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/notes/tools.py
[23] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/threat_model/tools.py
[24] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/coverage/tools.py
[25] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/tools/executor.go
[26] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/tools/memory.go
[27] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/docker-compose-graphiti.yml
[28] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/graph_memory.rs
[29] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/pipeline.rs
[30] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/skills/vulnerabilities/idor.md
[31] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/skills/vulnerabilities/broken_function_level_authorization.md
[32] https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization
[33] https://api-security.owasp.org/editions/2023/en/0xa3-broken-object-property-level-authorization
[34] https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References
[35] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/skills/__init__.py
[36] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/agents/prompts/system_prompt.jinja
[37] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/skills/reconnaissance/asset_discovery.md
[38] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/LICENSE
[40] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/core/inputs.py
[42] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/proxy/tools.py
[43] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/strix/tools/wait_for_user/tool.py
[45] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/server/models/flows.go
[46] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/tools/tools.go
[47] https://github.com/vxcontrol/pentagi/blob/cffed9485aa1cca70762cd08a57ac62a80406258/backend/pkg/providers/performer.go
[48] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/web/server.js
[49] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/scope.rs
[50] https://github.com/CyberSecurityUP/NeuroSploit/blob/92e8959f4ea17bddaa0436505edcddf98f7d6b16/neurosploit-rs/crates/harness/src/probe.rs
[51] https://github.com/usestrix/strix/blob/6b7ae2ebe4d47037a927aade23265ff4e4f27e84/pyproject.toml
[52] https://docs.defectdojo.com/import_data/import_intro/reimport
[53] https://docs.defectdojo.com/triage_findings/finding_deduplication/about_deduplication
[54] https://dradis.com/support/guides/rest_api
[55] https://dradis.com/support/guides/projects/node_properties.html
[56] https://agentskills.io/specification
[57] https://github.com/aliasrobotics/CAI
