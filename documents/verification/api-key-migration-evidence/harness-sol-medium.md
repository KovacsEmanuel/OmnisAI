**Da: un singur model poate deservi roluri distincte de orchestrator, investigator și validator pentru primul pentest minor.** Sunt necesare instanțe logice și contexte separate, unelte reale controlate de Omnis și o poartă probatorie deterministă. Nu este necesar un model diferit pentru fiecare rol și nici întregul harness avansat înaintea primei demonstrații.

Aceasta este o concluzie de fezabilitate arhitecturală. La HEAD `39ab04f13d66fcba9a4cadb02338fb9fae9fa3e8`, traseul respectiv **nu este implementat și verificat cap-coadă**. Recomand amendarea baseline-ului existent pentru a-l livra incremental, cu Hermes runtime și Codex subscription/OAuth eliminate complet din noul scope.

**1. Primul pentest minor: BOLA de citire, descoperită și verificată**

Aleg prima familie deja stabilită în [plan §11](/home/kali/OmnisAI/documents/Omnis_Implementation_Plan.md:335): BOLA/IDOR asupra unei aplicații API de laborator cu date sintetice. Este suficient de mică pentru prima probă și suficient de semnificativă pentru a verifica investigația, identitățile, regula business și validarea. O simplă expunere anonimă ar reduce cerințele de auth, dar ar evita tocmai diferența dintre acces legitim și acces nepermis pe care milestone-ul existent urmărește să o probeze.

Intrarea este URL-ul aplicației, autorizația și limitele laboratorului, două identități sintetice, contextul business și obiectivul „verifică accesul la obiecte private ale altui utilizator, fără modificări”. Nu oferim ruta vulnerabilă, parametrul de substituit, requestul exploatabil, seedul bazei sau răspunsul așteptat.

Fixture-ul propus conține:

- Două persoane în contexte distincte, cu obiecte private proprii.
- Un obiect partajat legitim, accesibil conform unei reguli explicite.
- O variantă vulnerabilă și una remediată, cu aceeași suprafață funcțională.
- Controale pentru obiect inexistent și autentificare invalidă/expirată.
- Date cu markeri sintetici care permit verificarea conținutului efectiv returnat.

Obiectele și operațiile trebuie să fie descoperibile prin navigarea/API-ul normal al laboratorului. Identificatorul unui obiect cunoscut legitim prin contextul celeilalte persoane poate deveni inputul unei probe; nu este necesară ghicirea nelimitată a ID-urilor. Evaluatorul păstrează separat adevărul de referință și configurația vulnerable/fixed. Agentul primește regulile de acces autorizate, dar nu localizarea defectului.

Bucla observabilă este:

1. **Orchestratorul** primește snapshotul autorizat și formulează o strategie inițială.
2. Cere unui **rol executant** o cartografiere minimă, apoi investigația unei ipoteze fundamentate în observații.
3. Executantul solicită o unealtă HTTP tipizată. Omnis validează scope, identitate, efect, buget și fencing, apoi execută requestul real.
4. Requestul, răspunsul, proveniența și rezultatul execuției devin evidence durabilă; modelul primește numai proiecția permisă.
5. Rezultatul modifică următoarea decizie: investigație suplimentară, candidat, respingere justificată sau gap. Un rezultat negativ nu este transformat automat în finding.
6. **Validatorul**, într-un attempt și context auth separat, reproduce proaspăt proba și controalele.
7. Serviciul determinist de verdict verifică regula business, identitățile, conținutul relevant și integritatea probelor înainte de `CONFIRMED`.

Demonstrația trebuie să arate cel puțin o alegere ulterioară dependentă de rezultatul unei unelte. Altfel avem un script fix cu text generat în jurul lui, fără dovada strategiei conduse de agent.

Pentru `CONFIRMED`, nu ajunge HTTP 200: răspunsul trebuie să conțină efectiv datele private ale obiectului interzis, în contextul persoanei neautorizate, cu autentificarea validă și regula `DENY` aplicabilă. Ownerul legitim și accesul partajat permis sunt controale distincte. Un răspuns generic, date publice, sesiunea greșită sau o regulă `UNKNOWN` nu satisfac oracolul.

Prima acceptare de produs include finding inspectabil, raport minimal fidel și retest pe varianta remediată. `FIXED` cere probe noi, autentificare validă și controale funcționale; auth expirat produce `RETEST_INCONCLUSIVE`. Raportul inițial rămâne imuabil.

Aceasta demonstrează o capabilitate îngustă de laborator. Nu certifică toate variantele BOLA sau eficacitatea generală Web/API. „Fără finding” poate fi un rezultat corect pe fixed/benign, însă numai cu precondițiile, testele și controalele executate.

**2. Nucleul necesar înaintea probei și harnessul de după**

Înaintea primei probe sunt obligatorii trei responsabilități logice: orchestrare AI, execuție specializată și validare independentă. Pot folosi același model configurat explicit și pot rula serial, cu un singur executant activ. Specialistul eliberează slotul înaintea validatorului.

Separarea este între:

- **Skill:** cunoaștere și metodologie versionată.
- **Rol:** instrucțiuni, responsabilitate, context disponibil și capabilități admise.
- **Task:** obiectiv concret, ipoteză, inputuri, limite și criterii de predare.
- **Tool:** implementare trusted care execută o operație tipizată.
- **Procedură/oracol:** pașii și condițiile probatorii aplicabile cazului.

Un investigator poate folosi mai multe skills, iar același skill poate servi mai multe taskuri. Parsarea JSON, normalizarea rutelor, calculul digesturilor, verificarea bugetelor și serializarea raportului rămân cod determinist. Nu propun agent pentru fiecare etapă și nici proces permanent pentru fiecare skill.

OpenAI Agents SDK este candidat pentru bucla de agent, distinct de clientul HTTP `openai`. Patternul manager `agents-as-tools` păstrează coordonarea conversațională la orchestrator și permite specialiști temporari. Această facilitate nu atribuie autoritate asupra efectelor. [Documentația Agents](https://openai.github.io/openai-agents-python/agents/) și [orchestrarea](https://openai.github.io/openai-agents-python/multi_agent/) susțin patternul, nu acceptarea Omnis.

În Omnis, apelul unui specialist trebuie încapsulat astfel: propunere AI → task validat → attempt atribuit de backend → execuție admisă. Contextul trusted al callbackului fixează run/task/attempt/rol; aceste identități nu sunt luate ca adevăr din argumentele modelului. Specialistul nu primește dreptul de a crea recursiv alți specialiști.

Nucleul anterior probei mai cere:

- Un owner unic, legat de controlul și Stop-ul existente.
- Admission înaintea fiecărui apel model și request target.
- Un adaptor HTTP real, secret injection și contexte auth izolate.
- Store local pentru snapshoturi, taskuri, observations, evidence și rezultate.
- Proiecții model-facing limitate, cu proveniență și gaps explicite.
- Bugete cumulative și rezervă pentru validare.
- Deadline, limită de pași și stagnare; fără refill prin restart sau task nou.
- Readback după reload/restart, fără retrimitere implicită.

PostgreSQL și artefactele locale sunt suficiente pentru început. Nu este necesară o bază vectorială. Contextul modelului poate fi construit din indexul runului, observațiile relevante și referințe către probe; conversația nu devine sursa autoritativă a stării.

Validatorul primește claimul înghețat, rețeta de reproducere, precondițiile și regulile necesare, fără transcriptul persuasiv al investigatorului. Are context auth separat și produce evidence nouă. Separarea aceasta este posibilă cu același model, dar nu garantează independență statistică.

**Verdictul determinist și a doua opinie LLM sunt mecanisme diferite.** Checkerul verifică probele și regulile; un critic LLM poate identifica omisiuni sau propune rework, dar nu poate vota peste evidence lipsă. Pentru prima BOLA nu este necesar un reviewer metodologic suplimentar.

După prima acceptare se dezvoltă harnessul avansat: concurență bounded, replanificare cu mai multe ramuri, compresie probată, selecție multi-model, review/rework, corpus held-out și fault injection extins. Nucleele Stop, buget și izolare trebuie să existe înaintea efectelor; generalizarea lor completă poate urma consumatorii reali.

**3. Ce există efectiv și ce trebuie amendat**

Auditul din 20 octombrie este util ca indiciu. Verificarea statică actuală confirmă principalele delimitări:

- [API-ul](/home/kali/OmnisAI/api/src/omnis/api.py:132) întoarce explicit `assessment_ready=False`.
- [Engagement.tsx](/home/kali/OmnisAI/web/src/features/engagement/Engagement.tsx:41) păstrează Start disabled; stream/findings/coverage/reports sunt indisponibile.
- [ExecutionSelection](/home/kali/OmnisAI/api/src/omnis/modules/tasks/execution_selection.py:1) acceptă felia finită `CONTRACT/NO_MODEL`, nu selecția live generală pe roluri.
- [Plan snapshot](/home/kali/OmnisAI/api/src/omnis/modules/runs/plan_snapshot.py:1) produce `CONTRACT_PROBE`, `effective=None`, `assessment_selectable=False`.
- `coverage/denominator.py` construiește universul declarat al inputului sintetic. `result_qualification.py` califică material CONTRACT și păstrează `REVALIDATION_REQUIRED`; nu reprezintă coverage de pentest.
- `module_registry.py` implementează trei transformări PURE: parse, normalize, build-map.
- Directoarele `labs/` și `executors/` nu există în checkoutul inspectat.

Inventarul de reutilizare trebuie tratat pe producer și consumer, nu numai după numele fișierului:

| Căi existente | Producer → consumer actual | Reutilizare și limită |
|---|---|---|
| `modules/engagements/{schemas,service,routes}.py` | Draft/revizie → Dashboard/Wizard/Engagement | Păstrăm autorizația declarată, CAS, istoric și Save inert; adăugăm consumatorul runului |
| `modules/instance/{domain,service,schemas}.py`, `supervisor/__main__.py` | Lease/generație/barieră → control local și owneri | Extindem montarea/drain-ul pentru noul runtime |
| `settings/{skill_catalog,candidate_resolution,candidate_store,catalog_publication,publication_store}.py` | Material verificat → candidat/publicare/readback | Refolosim digesturi, confinare și proveniență; compilerul actual este restrâns și legat de Hermes |
| `tasks/{managed_contract,managed_store,managed_composition,method_checks}.py` | Brief/binding/receipts → rezultat/check/inbox | Refolosim primitivele potrivite; protocoalele native și checkerul CONTRACT nu devin direct SECURITY |
| `policy/{budgets,model_dispatch_contract,model_projection}.py` | Cerere/proiecție → rezervă și contabilizare | Păstrăm mecanismele; scope-ul implementat cere încă `managed-run` și selection |
| `runs/{model_dispatch,model_test,model_test_operation,model_test_source}.py` | Config/admitere/probă fixă → owner nativ și UI | Separăm testul providerului de catalog/preparation/runtime nativ |
| `provider_models.py`, `provider_routes.py` | Comandă Settings → supervisor privat | Contractul actual este Codex-only; necesită înlocuire explicită pentru API keys |
| `web/src/shared/api/`, `contracts/omnis.openapi.json` | DTO/OpenAPI → client și componente | Schimbări sincronizate cu backendul; fără SDK în browser |

Există două pachete CONTRACT în `skills/` și profilele omonime în `profiles/`: `recon-mapping-contract` și `records-mapping-contract`. Ele declară chiar că nu execută scanning și nu produc findings. Nu există aici pachetul executabil `object-authorization` promis de plan.

`skills/bug-bounty-triage/SKILL.md` este material importat, fără manifestul executabil Omnis al celorlalte pachete. Conține instrucțiuni de păstrare a secretelor în raport și utilizare de unelte externe; acestea sunt incompatibile cu politica Omnis fără adaptare. L-am citit ca sursă de produs, nu l-am activat. `.hermes/skills/` nu a fost folosit drept catalog de pentest.

Căi **noi propuse**, create numai cu primul consumator: `integrations/agents_sdk/` pentru adaptorul SDK; `settings/provider_connections.py` și `model_catalog.py`; `tasks/agent_execution.py`; `executors/http/`; `modules/identities/`, `modules/evidence/`, `modules/surfaces/`, `modules/validation/`, `modules/findings/`, `modules/reports/`; `skills/object-authorization/`, `profiles/api-bola-lab.yaml` și `labs/dev/fixtures/object-authorization/`. Migrațiile se adaugă incremental; nu rescriem 0001–0013.

Pentru noua execuție trebuie eliminate dependențele Hermes din owner, distribuție, launcher și Settings. `hermes=False` într-un validator nu realizează această înlocuire. Datele și readerii istorici rămân citibili fără a porni Hermes sau a adopta grants vechi. Nu menținem două controllere active pentru același run.

Amendamentele apar în **același baseline**:

- Arhitectură §5: runtime Omnis cu adaptor SDK candidat, fără Hermes/OAuth în noul scope.
- §5.2 și §6: admission, ownership, continuări și Stop independente de identități native Hermes.
- §7–8: scope/effects/auth păstrate; transport HTTP și seif livrate cu primul consumer.
- §9: contracte versionate noi unde semantica incompatibilă o cere; fără native IDs fabricate.
- §10–11: evidence și prima evaluare SECURITY distincte de artefactele CONTRACT.
- Plan §2/4/8–16: înlocuirea providerilor și resequențierea către prima BOLA, apoi extinderea harnessului.

Înghețăm extinderea generică CONTRACT, editorul complet, metodele de review general și noile forme de predicate până când un consumer de produs le justifică. Nu anulăm acceptările istorice și nu le transferăm noului runtime.

Comenzi **existente în sursa CLI**: `omnis start --no-open`, `status`, `pair`, `open`, `stop`, `install`, `install-image`. Nu am verificat instalația locală. `omnis run stop`, `doctor` și comenzile generale de assessment sunt încă propuse. Operațiile viitoare Start/Stop run pot fi inițial comenzi API/web durabile; nu inventăm un CLI instalat.

`python scripts/render_docs.py --check`, testele documentare și browser checkerul sunt comenzi existente, **neexecutate aici**. Pentru amendarea ulterioară a Markdownului normativ se regenerează HTML. Nici testele tehnice, nici titlurile vechi despre design nu substituie aprobarea vizuală cerută de instrucțiunile curente.

**4. Settings: conexiune → catalog → model → rol**

Fluxul nou trebuie să permită două conexiuni independente, OpenRouter și OrcaRouter: introducere cheie → salvare locală → verificare explicită a conexiunii/catalogului → alegere default → eventual override per rol. Același run poate fixa orchestrator pe OpenRouter și validator pe OrcaRouter, după verificarea combinației.

Ambii provideri documentează integrare prin clientul OpenAI-compatible. Aceasta justifică investigarea transportului; nu dovedește compatibilitatea tuturor modelelor sau a loopului SDK. [OpenRouter SDK](https://openrouter.ai/docs/guides/community/openai-sdk), [OrcaRouter SDK](https://docs.orcarouter.ai/compatibility/openai-sdk).

Cheia este write-only din perspectiva readbackului web: backendul întoarce prezență, identificator de conexiune, revizie și eventual fingerprint limitat. Stocarea folosește protecție locală și cheie separată; fără secret în URL, prompt, evenimente, export sau browser storage. Nu se citesc implicit credentiale personale și nu se migrează OAuth în API keys.

**Save nu face inferență și nu validează cheia online.** Butoanele „Verifică conexiunea/actualizează catalogul” și „Testează modelul” sunt operații explicite separate. Catalogul păstrează sursa, momentul și staleness. O intrare în catalog nu dovedește entitlement pentru cheia curentă, disponibilitate, tool calling funcțional sau suportul parametrilor solicitați.

Testul modelului este finit, cu mesaj sintetic vizibil, plafon de apeluri/output/deadline, fără target și fără fallback. Testul capabilității tool calling este o probă distinctă, eventual cu o funcție locală inertă; nu devine pentest. OpenRouter descrie explicit că aplicația execută funcția și transmite rezultatul înapoi modelului. [Tool calling](https://openrouter.ai/docs/guides/features/tool-calling).

Selecția se rezolvă înainte de Start:

`override explicit de rol/profil → preferință compatibilă a metodologiei → default explicit al runului`.

Conflictele, cerințele REQUIRED nesatisfăcute și lipsa defaultului blochează. Fallbackul plătit este dezactivat implicit; unul permis ulterior trebuie numit, aprobat, bugetat și înregistrat. Politica trebuie să acopere și routingul providerului, nu doar schimbarea modelului în codul Omnis.

Snapshotul runului fixează conexiunile și reviziile, modelele exacte, transportul, parametrii, capabilitățile verificate, politica de routing, data policy și plafoanele. Rotirea/revocarea cheii blochează utilizări noi conform politicii; nu mută silențios runul pe alt cont.

Usage se agregă per dispatch, rol și provider, apoi pe run. Input/output/reasoning/cache raportate nu se adună dublu; costul observat, estimarea și necunoscutul rămân distincte. Subbugetele nu multiplică plafonul global. Codul actual respinge plafonul monetar în contractul finit inspectat, deci nu putem revendica enforcement financiar existent.

SDK-ul permite modele și provideri diferiți per agent, dar avertizează asupra diferențelor dintre interfețe și features. Propun instanțe client explicite per conexiune, fără mutarea unui default global în timpul runului. [Modele SDK](https://openai.github.io/openai-agents-python/models/).

Tracingul extern trebuie dezactivat înaintea primei probe: documentația îl declară activ implicit, inclusiv captură sensibilă implicită. Observabilitatea Omnis rămâne locală și redactată; un exporter ulterior cere decizie și probe separate. [Tracing](https://openai.github.io/openai-agents-python/tracing/).

Defectul de proiecție indicat de audit este vizibil și în cod: `model_test_operation.projection()` omite statusul providerului, iar `view()` produce `COMPLETE` pentru observația prezentă. Noul contract trebuie să păstreze separat completed/incomplete/failed, verificarea modelului și usage. Nu am reprodus dinamic defectul în acest mandat.

**5. Roadmap ulterior, cu rezultate de produs**

Ordinea propusă modifică dependențele existente, fără să creeze un plan concurent:

1. **Tranziție runtime și nucleu inert:** noul owner/adaptor, Settings API-key, contabilizare și Stop; probe fără cont pentru refuzuri, proiecții și persistență.
2. **HTTP/evidence/auth:** request real autorizat, captură durabilă, inspector și identități izolate. Poate fi dezvoltat fără model live. Dacă alegem HTTP trusted fără MITM, trebuie amendată explicit obligația actuală de proxy și probate DNS/IP/redirect/egress la sink.
3. **Prima BOLA:** URL → mapping minim → ipoteză → specialist → validator → finding/raport/retest. Acesta este primul rezultat util, fără editor general sau provider secundar obligatoriu.
4. **Harness aprofundat:** clues și contradicții → replan bounded; handoff, dedup, inbox/readback, stagnare, recovery și critic metodologic cu rework limitat.
5. **Roluri multi-model verificate:** gate separat pentru mixul OpenRouter/OrcaRouter, requested/effective, tool results, izolare, usage total, Stop și indisponibilitate. Un dropdown sau flag nu închide milestone-ul.
6. **Recon și Web/API extins:** mapping incremental, OpenAPI, JS static/sourcemaps, discovery bounded, browser post-auth; apoi XSS reflectat și traversal-canary cu oracole proprii.
7. **Triage, raportare și retest extinse:** dedup pe cauză, occurrences, impact demonstrat, review editorial, export coerent și retest cu probe noi.
8. **Direcțiile avansate păstrate:** research contextual, Jev, learning/improvement, attack paths și breadthul E1–E4, fiecare cu propriul consumer și gate.

Tool adapters pentru Katana, Nuclei, browser sau Schemathesis se introduc separat, cu versiune/config/template fixate, input tipizat, attribution per request, capture, cancel și readback. Outputul scannerului produce semnale; exit 0 sau zero matches nu sunt verdict.

Browserul rămâne milestone explicit după HTTP/auth, cu sandbox, subrequesturi și efecte probate. JS complet urmează prima BOLA; history online și debuggerul își păstrează gate-urile ulterioare. Research revine în aceeași frontieră de investigație. Jev începe OFF/SHADOW și influențează prioritizarea numai după evaluare comparativă. Learning produce draft → review → eval → publicare pentru runuri viitoare. Attack paths cer dovezi pentru ambii pași și tranziție.

Comenzile de produs viitoare trebuie să acopere Start/preflight, Stop run, task/cancel unde suportat, report generate/download și retest. Ele se livrează cu receipt durabil și GET readback; nu devin comenzi shell model-facing. Skills și profilele versionate aleg metodologii și limite, nu instalează executabile sau schimbă politica.

Din Strix, am inspectat [prompt.py la pinul cerut](https://raw.githubusercontent.com/usestrix/strix/a3c31236bd6305784a501a3102dab0bda83f2317/strix/agents/prompt.py): selecția ordonată/deduplicată, prefixul comun și separarea skills sunt idei reutilizabile. Încărcarea implicită a ghidurilor browser/Python și fallbackul la prompt gol nu trebuie preluate ca politică Omnis. `factory.py`, `core/execution.py` și fișierele skills solicitate nu au putut fi recuperate prin instrumentul web; nu le atribui proprietăți neverificate și nu import un al doilea runtime.

Eficacitatea se măsoară separat de integrare: TP/FP/FN pe vulnerable/fixed/benign, replay independent, ratări atribuite discovery/plan/execuție/validare, requesturi, apeluri model, cost, latență și intervenții. Comparația cu baseline determinist folosește aceleași informații și bugete. Protocolul held-out și pragurile existente din plan §15 rămân pentru promovarea capabilității; prima demonstrație nu le înlocuiește și nu justifică paritate competitivă.

**6. Decizii care pot schimba direcția și acceptance map**

Șapte riscuri/decizii merită adjudecare explicită:

1. **Frontiera SDK:** pinul ales trebuie să permită admiterea fiecărui apel efectiv, inclusiv apelurile specialiștilor. Dacă cere hooks invazive, restrângem integrarea.
2. **Compatibilitatea router/model:** textul generat nu dovedește tool calling, output structurat, effort sau identitate efectivă; combinațiile neverificate rămân indisponibile.
3. **Transportul target:** alegerea HTTP trusted versus proxy schimbă implementarea, fără a reduce obligațiile de scope, egress și Stop.
4. **Oracle și independență:** o regulă business greșită sau contaminarea validatorului poate produce FP; alt model nu garantează eliminarea biasului.
5. **Cost și routing:** usage/preț incomplet ori routing necontrolabil poate împiedica plafonul monetar strict; caps tehnice nu îl substituie.
6. **Migrare și istorie:** retragerea Hermes nu trebuie să execute din nou operații vechi sau să facă datele ilizibile; rollbackul DB cere plan separat.
7. **Generalizare prematură:** dacă prima BOLA ajunge iar dependentă de editor/compiler/maintenance complet, secvențierea trebuie corectată înainte de extindere.

| Acceptare | Pozitiv | Negativ obligatoriu | Readback |
|---|---|---|---|
| Settings | Config/default/rol persistente; test finit explicit | Save fără inferență; key invalid, model incompatibil, fără fallback | Reload/restart arată aceeași revizie și operație |
| Agent loop | Tool result schimbă decizia următoare | Tool inventat, argument invalid, ref străin, text ostil fără autoritate | Task/attempt/decizie/evidence legate |
| HTTP/auth | Request permis, principal verificat, evidence durabilă | Off-scope/redirect/identitate greșită/secret echo refuzate | Inspectorul păstrează contextul și digestul |
| BOLA | Acces privat interzis demonstrat și replay proaspăt | Shared/owner/fixed neconfirmate; auth invalid → inconclusive | Claim, regulă, baseline/probă/control inspectabile |
| Stop/buget | Fără dispatch nou după revocare; validarea are rezervă | Restart/refuz/lost reply fără refill sau resend | Stări terminale ori UNKNOWN explicit |
| Raport/retest | Export fidel; fixed cu probe noi | Evidence lipsă, claim stale, auth expirat fără FIXED fals | Raport vechi imuabil; retest legat |
| Multi-model ulterior | Rolurile rulează efectiv pe combinația fixată | Model ignorat, provider indisponibil, hot-swap refuzat | Requested/effective și usage agregat |

Fără cont se pot verifica inert schemele, compoziția, ownershipul, snapshots, contabilizarea, Stop-ul și serializarea, cu doubles declarate. Nu se pot certifica astfel entitlementul, comportamentul live al modelului, costul real sau eficacitatea pentestului.

Apelurile viitoare de produs cer acord explicit pentru cheia/providerul/modelul, datele transmise și buget. Traficul către laborator cere separat scope, identități, efecte, limite și permisiunea fixture-ului. Mandatul actual autorizează analiza de dezvoltare, nu aceste operații.

Verificarea Git inițială și finală confirmă același HEAD, branch `checkpoint/p2-batch2-pause-20261015`, fără modificări tracked/staged; verificarea finală a avut **exit 0**. Singurul untracked rămâne `documents/Omnis_Notite_Originale.html`, necitit și nemodificat. Nu am scris fișiere, creat commituri, pornit agenți, teste, servicii sau apeluri model/target de produs. Livrabilul este analiza pentru adjudecare; implementarea și toate acceptările live rămân **NOT_RUN**.