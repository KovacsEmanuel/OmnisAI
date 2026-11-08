# Strix 7574 — referință funcțională, UI și adaptări propuse pentru Omnis

**ANALYSIS_COMPLETE / CANONICAL_AMENDMENT_ACCEPTED_DOCUMENTARY_SCOPED / NOT_IMPLEMENTED.** Studiul inițial și suplimentul18inspectori rămân la probele lor. §14 aplică decizia operatorului: nucleu complet până S7, IDOR/BOLA inițial și pairing manual/A amânat. [Plan§7.2](../Omnis_Implementation_Plan.md) este autoritatea; dosarul și fișele SR sunt proveniență. §14.6 leagă reviewurile/corecțiile/91teste docs de snapshotul exact, nu QA runtime/paritate sau mandat de implementare. S1 inert rămâne scoped, UI VISUAL_CHANGES_REQUESTED și T2 NOT_CLOSED.

## 1. Decizia de produs și rezultatul studiului

**Păstrăm backendul/ownerul Omnis și livrăm mecanismul observat, nu încă un runtime Strix în spate.** Valoarea referinței este fluxul observabil: obiectiv scurt → recon propriu → observații/model comun → specializări cu metodologie/context → acțiuni și rezultate → contraexemple/indicii → continuare justificată → validare → rezultat inspectabil. Nu sunt suficiente un prompt mai lung, o colecție de skills sau un graf cu multe noduri.[2][4]

Ce merită adaptat: metodologia și rubricile relevante, observațiile atribuite și corectabile, citirea progresivă index→punct→probe, handoffurile cu gaps/next clues și inspectorul contextual tipizat. Ce păstrăm nativ: identitățile run/task/attempt, PG, inbox/consum, seiful, admission/fence/Stop, senderul provider, catalogul calificat și proiecțiile. Ce nu copiem: moștenirea integrală a istoricului, Shell/Filesystem pentru orice rol, completion numai cu warning, noul coordinator/SQLite/viewer, dependențele integrale Strix sau auto-retry/wake peste UNKNOWN/HOLD/Stop.

**Pairing — decizie explicită ulterioară:** **A = DEFERRED_BY_OPERATOR**, mecanismul manual existent este suficient pentru T2/S7. Dispoziția este acum transpusă în plan/arhitectură/UI; nu auto-pair livrat sau permisiune pentru bearer în URL/argv. Nu continuăm investigația automatizării și nu păstrăm un blocker S7 latent; redeschidere numai la cerere nouă, cu propriile probe de frontieră.

**Criteriul util pentru Omnis:** prima demonstrație trebuie să folosească propriul recon/context/tool/validator și să producă un rezultat verificabil. Nu promitem aceleași36 rapoarte, același traseu, cost sau durată; runul de referință nu este ground truth și aplicația a fost modificată prin testare.

## 2. Surse fixate și frontiera dovezii

| Sursă | Identitate și limită |
|---|---|
| Omnis | `177266f82b65eabdd4273b2f91fa605753763ebf`, branch `checkpoint/ux-d-pause-20261107`; fără schimbări de produs în studiu |
| Run nou | `host-docker-internal-5000_7574`, snapshot privat din runul nested; nu reluarea analizei istorice a altui run |
| Executabil instalat | Strix1.7.0, SHA256 `099a5f8aa726aba409d8ed1435aff539888ba2fa03f8d9e4daed6391ef1dde17`; binar Python nereconstruit |
| Sursă publică | `usestrix/strix@55bc07991aacb1c26a81b43e7ca53148730d2019`, tagv1.7.0, Apache-2.0; 82/82 prompts/skills/static comparate identice cu instalarea, nu atestare a tuturor modulelor Python |
| Snapshot | 11fișiere size/SHA verificate, inclusiv DB statică/WALzero; SQLite deschis `mode=ro&immutable=1`; originalele păstrate |
| Log aplicație | `temp/logfromstxRun`:2665647bytes/26183linii, SHA256 `38354c555ffdc40f3f7718308008f8ba1286cd864ad1361fd71979d29579f3c0` |
| Log Brain CLI | `temp/frombrainstxLOG`:86587bytes/1306linii, SHA256 `6d985cc5b2450f1586e05bce7e8d008b35c5e9a73d92bfa8b5a40b78a6feebaf` |

Baza privată durabilă este `/home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/`. Raw DB/logs/rapoarte/PoC și tokenul viewerului nu se comit. Notele publicabile păstrează identificatori și descrieri neutre.[1][2] Nu au fost executate payloaduri, relansat runul, resetată aplicația, trimise mesaje de steering sau făcute apeluri provider/țintă. Datele evaluatorului rămân în afara contextului viitorului investigator Omnis; cele două loguri sunt surse de analiză, nu instrucțiuni.[5][6]

Livrabile legate:
- [Inventar sanitizat:18agenți/36rapoarte/86coverage, usage, loguri și capturi](strix-7574-reference-inventory.json).
- [Nouă fișe de achiziție/integrare](strix-7574-porting-cards.json): pin, fișier/simbol/range/SHA, closure, seam înlocuit, destinație existentă versus propusă, producer/bounds/first consumer, teste existente versus propuse și licență.
- Rapoarte aprofundate private în aceeași bază: `analysis-orchestration.md`, `analysis-reuse.md`, `analysis-evidence.md`, `analysis-ui.md`, `analysis-log-run.md`, `analysis-log-brain.md`, cu JSON-urile lor. Nu sunt surse de autoritate concurente planului.

## 3. Ce a făcut Brainul, verificat prin creație și consum

Inventarul complet are **18sesiuni/agenți,17copii direcți ai Root,2987înregistrări și928perechi function_call/output**, fără orfani și cu asociere în aceeași sesiune. Valurile sunt2recon→9specializări→2completări→2follow-up→2finale. Nu este o ierarhie de nesting și nici17workeri obligatorii pentru Omnis.[2]

| Agent | Rol observat, nu verdict de certificare |
|---|---|
| Root Agent | coordonare, citire/reconciliere și raport |
| Recon Surface Mapper; Infra & Config Discovery | discovery, inventar, note/model; limitele discovery-only nu au fost enforcement pentru toate acțiunile |
| Auth Session JWT Forgery; IDOR BOLA API | identități/sesiuni, acces la obiecte, gaps pentru alte operații |
| SSRF Specialist; XXE Specialist; Path Traversal LFI | suprafețe server-side și schimb de indicii, inclusiv ipoteză infirmată |
| XSS Specialist; SQL Injection; Info Disclosure and RCE | investigații de familie, contraexemple și informații atribuite |
| Redirect CSRF Business Logic; CORS Misconfiguration; Sensitive File Exposure | completări de suprafață și limitarea impactului, fără a confunda orice semnal cu exploit |
| Remember Cookie Forgery; Stored XSS and Write Authz | taskuri noi din indicii/gaps, nu agenți permanenți per skill |
| Race and Coupon Logic; Chain Validation | continuări târzii; replay de subset/lanț, nu validare universală |

### Trei exemple care trebuie să existe ca comportament, nu ca rețete copiate

1. **Recon→hartă→delegare:** nota`a8160b` este produsă de Recon, primită/citită de Brain, urmată de modelul comun și nouă briefuri. Locatoare DB210→248→261/262→265/266→299–316; CLI127–505. Acesta este producer→read→decizie, nu doar ordinea unor carduri.[2][6]
2. **Indiciu de fișier→ipoteză XXE→infirmare:** Root transmite informația către XXE; workerul o primește după o primă finalizare, face probe distincte și corectează presupunerea de HTTP-XXE. Callbackul unui alt tool nu este atribuit XML-ului; negativul este înregistrat și acceptat. DB850/852→1448→1517/1578→1673/1674→1692–1695→1712→1715. Omnis păstrează contradicția și calificarea, fără a transforma indiciul în autoritate.[2]
3. **Negativ CORS→pistă diferită→task nou:** limitarea impactului CORS produce o notă și indiciul pentru cookie persistent; Root creează specialistul, acesta citește nota și efectuează propria investigație. DB1945/1946→2069→2077/2079→2088/2091→2138/2139→2336/2337. Nu importăm endpointul, credentialele ori soluția în prima calibrare Omnis.[2][6]

Există10notes, un model cu trei amendamente și32todos în cinci namespace-uri. Patru mesaje explicite Brain au fost urmărite până la livrarea în context și acțiuni ulterioare. `delivered` nu este încă `consumed`; mesajele root ulterioare cu roluser sunt wrappers/recovery/timeout, nu25clarificări umane. Cele22wait_for_agents nu sunt22teste sau22intervale complete de600s.[2][6]

### Promptingul/contextul — ce păstrăm și ce nu

Runul selectează21skills explicite distincte din75disponibile; sursa adaugă un baseline comun, dar DB nu păstrează întreg system promptul efectiv. Încărcarea completă în wire rămâne inferată din sursă, nu captură SDK. Zero apeluri`load_skill` sau`think` native apar între cele27tooluri distincte folosite. În viewer, mesajele assistant normale sunt etichetate **Thinking**; nu este raționament ascuns expus.[2][3][4]

Toate17delegările cer`inherit_context=true`. Intrarea inițială a ultimului copil are316511bytes, separat de system prompt/wire. Nu încape prin simplă copiere în compoziția/requestul Omnis. **Clarificarea necesară U03:** eliminarea parent-history este adaptare Omnis, nu comportament upstream; un singur mesaj poate conține întreg istoricul serializat. Păstrăm brief critic + index/punct/refs, mandatory context și contradicțiile materiale, măsurate în requestul SDK complet. Nu rezolvăm context flooding prin trunchierea instrucțiunilor obligatorii sau prin încărcarea tuturor ghidurilor.[2][4][6]

## 4. UI: ce face referința mai ușor de citit

**Separarea suprafețelor este cheia:** pagina normală identifică runul și rezultatul, iar click pe agent deschide inspectorul, în loc să amestece toate argumentele/uneltele/receipturile în streamul comun.[3]

Source abreviat`V:`=`strix/interface/viewer/frontend/src/` la pinul nou:
- `components/live/AgentDetailModal.tsx:17–31,75–112,125–160`: header fix, scroll propriu, modal contextual, urmărire live numai aproape de final; shell randat înaintea transcriptului greu.
- `AgentTranscript.tsx:241–305` și `tool-renderers/index.ts:79–174`: icon+etichetă și renderer per familie; notă, model, delegare, mesaj, rezultat HTTP, terminal, raport au forme diferite.
- `AgentCommsRenderer.tsx:6–63`: misiunea delegată, predare și mesaj adresat; `ToolCard.tsx:8–61`: preview/Showmore, fără a pretinde că previewul este raw evidence.
- `ChatBubble.tsx:12–21`: **Thinking înseamnă eticheta unui mesaj assistant**. `AgentTranscript.tsx:99–122,209–215` ascunde intrarea inițială și livrările inter-agent; nu afișează întreg promptul de sistem.
- `AgentGraph.tsx:27–71,161–175` leagă nodurile după parentID. Graful nu demonstrează cine a consumat o notă sau un chain de atac.[3][4]

În Omnis păstrăm`RunPanel`, arborele compact/stările textuale și query-urile read-only; rafinăm un singur inspector etalon înainte de propagare. Instrucțiunile/contextul permis trebuie să rămână inspectabile explicit, chiar dacă viewerul Strix le ascunde inițial. Filtrele utile sunt cerință Omnis; nu au fost observate în modalurile Strix examinate. Filtrarea întregului run cere query/cursor/bounds server-side; filtrul local pe pagină trebuie etichetat onest.

Pictogramele semantice nu cer o bibliotecă ori canvas nou. Direcția vizuală pentru un graf panoramic rămâne de decis față de baselineul care admite arbore compact; nu facem din graf prerequisite pentru eficacitate. Nu importăm automat Tailwind/ReactFlow/Dagre/highlighter sau Guide the agent. Inspectorul rămâne read-only în mandatul curent; steeringul viitor cere propria comandă/admitere/readback. Stop, focus, contrast, keyboard/reduced-motion și recuperarea UNKNOWN nu se ascund pentru estetică.

Capturi private, cu SHA în inventar:
- `captures/strix-completed-dashboard.png`: final,1440×1000.
- `captures/strix-completed-agent-graph.png`: graf final,viewport1440×900; nu toate nodurile sunt lizibil încadrate.
- `captures/strix-recon-inspector.png`: inspector real din etapa live, nu screenshot final.

**Frontiera inițială, la828445d2:** au fost examinate interacțiunile Root/Recon/Infra și modaluri Auth/IDOR, nu toate18transcripturi în browser; restul inventarului provenea din DB/surse. **Suplimentul explicit cerut ulterior acoperă acum18/18inspectori**, cu DOM extins și captură per agent (§10). Limita inițială nu este rescrisă drept succes retrospectiv. Lectura suplimentară privește proiecția randată, nu datele omise de renderer, fiecare payload adjudecat sau hidden reasoning. Capturile nu reprezintă acceptare estetică Omnis.

## 5. Ce adaugă logurile, fără false concluzii

`logfromstxRun` este consolă Flask/access-log/traceback, nu jurnalul SDK. Censul are22644înregistrări de acces,16933răspunsuri404 și153răspunsuri500. Cele153tracebackuri conțin128lockuri SQLite,22TypeError și3OverflowError. Părintele a reprodus direct numărul acceselor/statusurilor,tracebackurilor și lockurilor; numărul nu demonstrează cine ținea lockul ori că încărcarea a cauzat toate erorile.[5]

Fereastra access-log19:28:07–19:52:35 nu declară fusul. Este compatibilă cuUTC+02 față de runul17:27:29–18:03:08UTC, deci temporar parțială sub această ipoteză. Lipsesc body, principal, traceID și efectul persistent/cleanupul final. Corelarea metodă+target+oră±2s dă56referințe de exchange cu candidat temporal unic/status compatibil în20rapoarte; **nu este join autoritativ sau replay independent**. Status200 ori exit0 după cereri eșuate nu înseamnă finding confirmat.[1][5]

Consecințe de produs:
- S2 capturează destinația/hopurile, auth efectiv, body/completeness bounded și semnalul de degradare; nu doar statuscode.
- S3 nu transformă avalanșa404/soft404 sau simpla repetare într-o hartă/coverage mai completă; discovery-ul rămâne bounded și health-aware.
- S4 face controale cu precondiții valide și propriul replay; un500/lock poate invalida proba, nu deveni automat vulnerability sau secure negative.
- S5 păstrează timeouturile/efectele UNKNOWN și settlementul proceselor; poll/input pe proces existent nu este autoritate pentru retryul efectului.
- S6–S7 păstrează starea target post-Strix, fereastra logului, diferența primit/capturat și cleanupul necunoscut. Nu resetăm aplicația ori importăm soluția în investigator.

## 6. Rezultatul final: ce înseamnă și ce nu

Cele36rapoarte au distribuția7critical/17high/10medium/2low. Toate86coverage entries au dispoziție individuală:63reported,5no_issue_found,14ruled_out,4N/A. Șase reported nu au findingID explicit în evidence narativă. Coverage export rămâne`complete=false`, iar SARIF`executionSuccessful=false`, deși runul final și graphul suntcompleted. Ordinea producerilor explică Rootrunning în exportul anterior ultimei tranziții; nu declarăm crash doar din acea nepotrivire.[1][2][4]

`create_vulnerability_report` verifică rubrici/IDs/dedupe, nu execută universal PoC ori oracle de familie. ChainValidation are acțiuni proprii pentru două lanțuri și actualizează rapoarte existente, dar moștenește contextul colegilor. Nu este D14 independent pentru toate36. Numărul cauzelor-rădăcină rămâne necunoscut; raport, instanță, chain și root cause nu sunt aceeași unitate. Omnis nu trebuie să câștige aparent la scor prin duplicarea pașilor unui chain.[2][4]

Închiderea Strix păstrează opttodos Root neînchise și warningbrowser_security. Cele15actualizări coverage făcute de Brain sunt reconciliere, nu15replayuri. Adoptăm replanul și contraexemplele utile, dar nu completion numai prin absența rândurilor needs_follow_up.[2][6]

Contabilizarea este reconciliată: **18sesiuni+actoruldedupe=19actori usage**,621+40=661cereri LLM, nu661requesturi target. Costul persistat1.8153400036USD este afișat1.82USD; per-agent cost este alocare proporțională, nu factură individuală. Inputul cached și outputul reasoning sunt componente ale totalului, nu se adună încă o dată. Nu extrapolăm cost/durată Omnis din acest run ori din egalitatea aritmetică a unui ledger.[1][4]

## 7. Reutilizare concretă: KEEP / ADAPT / NEW

Fișele SR01–SR09 sunt selectări de sursă, **nu patchuri copy-ready sau compatibilitate importată**. Originalele/cazurile de test se păstrează cu licență/notice și digest; testele numite există, dar nu au fost executate ca suite upstream/produs. Codul specific backendului/autoritate se adaptează, nu se redenumește.[4]

| Card | Unitate și acțiune | Native first consumer / plasare |
|---|---|---|
| SR01 | KEEP catalog/composer→SDKstep→owner; nu mai portăm dedupe/factory a doua oară | `agent_composition.compose_publication`, `AgentStep`, `AgentRunOwner`; extindere multi-pachet calificată înS3/S4 |
| SR02 | ADAPT parcursul recon→model și PORT atribuirea/indexul notes + rubricile modelului | `skills/web-recon/`, mapmodels/service propuse; refs reale dinS2→Brain/briefS3 |
| SR03 | COPY/ADAPT metodologia IDOR aplicabilă, counterevidence și severity-calibration | pachetulIDOR/triage/validatorS4, nu numai un vulnerability-prompt sau un payload dump |
| SR04 | PORT previewUTF8/paginare; capul include notice/envelope | primul evidence readerS2; tiny-cap upstream10→43bytes cere corecție, nu enforcement copiat orbește |
| SR05 | KEEP HTTPX disponibil; NEW numai glueul de captură/read/modify/replay autorizat | policy/target_actions, executorHTTP, identities/evidence propuseS2; Caido nu este clientHTTP autonom extras |
| SR06 | KEEP owner/inbox/consum; ADAPT handoff summary/openitems/refs | new_attempt/complete, run_store.add_inbox/consume;S3/S4 apoiS5concurență |
| SR07 | PORT istoricul revizuirii/contradicției coverage, nu verdictul agent-reported | mapS3,qualificationS4; fără lowercasing al identității operației sau evidenceopțională pentru secure negative |
| SR08 | KEEP proiecțiile/call pairing; ADAPT tipizarea prezentării UI | events/store/RunPanel existente, cu produceriiS2–S4 și restart/readbackS7 |
| SR09 | KEEP checkerele compatibile; NEW doar bindingul SECURITY/D14/oracle/writer absent | validation/findings propuseS4→S6/S7; nu report-tool transformat în validator |

**Clarificări pentru U02/U03/U06/U07 existente:**
- U03 numește lipsa parent-history adaptare Omnis; sursa poate moșteni istoricul. Nu atribuim upstream un control pe care îl adăugăm noi.
- U06 păstrează observația pinului vechi la revizia sa. La noul1.7.0, IDs HTTP neverificate sunt eliminate cu warning dacă proxyul nu poate fi interogat; asta tot nu confirmă findingul.
- U02 se extinde cu pachetul și consumerul real; core-only/compoziția8KiB nu sunt dovadă că întreaga metodologie nouă încape. Calificare→compoziție→request complet măsurat, nu scaffolding/editor general.
- U07 păstrează UI/proiecțiile existente; actualizările în source DTO/API/decoder/filtrare/readback vin împreună. Dintr-un viewer nu se copiază autoritatea execuției.

## 8. Modificările punctuale propuse în plan, în ordinea consumerilor

Acesta este **delta candidat** pentru plan§7/arhitectură/UI și U01–U09, nu o nouă secvență concurentă. Majoritatea obligațiilor există deja; analiza le face observabile și localizează adaptările, fără a declara funcțiile viitoare buguri ale S1.

| Loc | Ce se păstrează / concretizează | Ieșire pozitivă / refuz care schimbă admiterea |
|---|---|---|
| Înainte de efecte S2 | Remediu finit al stagnării: un receipt/result ID nou nu este singur progres. Defectul contorului S1 a fost reprodus pe `AgentRunOwner.complete`, cu storage/DATA/worker mockuite; nu run PG/model. Păstrăm MONITOR fără plafon total. | Repetarea aceleiași sarcini pe aceleași inputuri/revizii fără informație nouă produce diagnostic/limitare; reproducerile legitime au scop/precondiții explicite; Stop/HOLD nu sunt slăbite. |
| S2 / U04, arh. §7–10 | HTTP/auth/evidence la același sink, inclusiv OPERATOR_CHECK; read/preview separat de replay ca efect nou; health/auth recheck după degradare. | Allow → acțiune/identitate/hopuri/evidence persistente; off-scope/redirect/identitate străină/Stop → zero efect; missing/corrupt/overflow/UNKNOWN nu confirmă și nu retrimit. |
| S3 / U02,U05 | Recon propriu produce refs + observații atribuite; Brain citește index/punct/probe și creează brief selectat; corecția păstrează istoria și contradicția. | Lanțul recon → notă/model → citire Brain → brief este demonstrat; CAS409/foreign ref/mandatory overflow refuzate; soft404/repetiție nu umflă coverage. |
| S4 / U03,U06 | Metodologie calificată IDOR, D13 pe direct-final/finish/errors, candidat/gaps separat, triage apoi D14 cu context/attempt/auth/probe/control proprii. | DENY + efect privat + control/replay susțin confirmarea; owner/shared/fixed/benign/login200/auth-invalid/probe lipsă nu confirmă; lipsurile rămân explicite. |
| S5 / U03,U08 | Același owner/inbox, maximum doi workeri incluzând draining/validator, prioritate next-slot; livrat/context consumat/decizie sunt distincte. | Late/duplicate consumate o dată; stale/post-Stop nu produc wake; terminal → successor nou; reconectare/timeout/UNKNOWN fără resend sau auto-Resume. |
| S6 | Prima tentativă autonomă păstrată, baseline post-Strix/snapshot/ROE/identități/efecte/date/cost aprobate; comparație pe producerul lacunei. | Discovery proprie → finding confirmat independent pentru D03; negativul/blocajul diagnostic nu devine PASS funcțional sau secure; truth/logurile acestui dosar sunt excluse din contextul investigatorului. |
| S7 | Snapshot final coerent, QA installed/readback/restart fără rerun; reconcilierea obligațiilor, candidaților, inboxului, UNKNOWN și cleanup. | Nu COMPLETED din ledger gol; limite/gaps persistente, efect UNKNOWN cere reconciliere; canonical pe bytes integrați și dispoziție A explicită. |
| UX/SL16 cu producerii | O singură vedere etalon agent → inspector, activitate compactă și detalii tehnice secundare; diagnostic privat pe ownerii/stocarea existente. | Operatorul poate explica misiune/acțiune/rezultat fără UUID dump; keyboard/focus/Stop/reload și refuzurile de secret sunt probate separat de estetica umană. |

Pentru schema/API/migrarea exactă, ownerul produsului rămâne cel existent. Date noi map/evidence/identity/findings cer migrare aditivă și citiri istorice; layoutul singur nu justifică migrare. Nu inventăm tabele/endpoints/helpers acum. Fișele JSON separă destinațiile existente de cele propuse și cazurile de test existente de cele care vor apărea cu producerul.

### Ce nu mutăm obligatoriu în primul finding

Mai multe familii și tooluri nu devin prerequisite pentru IDOR. Browserul necesar cazului se admite înaintea folosirii, dar nu este prerequisite universal al HTTPX. Shell/scripturi sunt numai prin sandboxul admis, nu consola hostului. RCE/deserializare/scannere/protocoale, stored/DOM XSS/CSRF/SSRF/XXE/business/race și familiile E urmează propriile transporturi/oracles/evaluări; nu activăm 26 skills deoarece un run le selectează. Replanul generalizat G-LOOP/path G-PATH și raport/export/retest T5 își păstrează gates; pistele noi S3/S4 rămân legate de primul circuit, nu extind automat exitul său.

## 9. Verificare proporțională și concluzie de readiness

Nu repetăm canonicalul pentru acest dosar. Istoricul indică un canonical S1 de 73.35 minute, dintre care 56.32 minute API (76.79%); verificarea UI restrânsă a avut 7.83 minute, dar scope diferit și nu îl înlocuiește. Refolosim dovezile neschimbate; affected checks și re-review delta în loop, consumer real după review, full gate la frontiera integrată. Profilarea setup/call/teardown se adaugă la următoarea execuție deja necesară, nu ca benchmark separat. Nu justificăm slăbirea Stop/izolării sau un nou harness printr-un timp mare.

**Readiness inițial:** există surse, inventar reconciliat și unități de adaptare pentru un amendament punctual. Suplimentul de mai jos răspunde întrebării noi despre fiecare inspector și mecanismul de cod, inclusiv unei probe autorizate pe cod copiat. Nu există implementare S2 nouă, parity Strix sau autorizare de a o începe. Probele de produs/țintă rămân NOT_RUN; spike-ul nu este integrare.

## 10. Supliment: fiecare agent deschis în browser

**18/18 inspectori deschiși și încărcați, 1401 blocuri UI, 928 apeluri native reconciliate, 96 expandări Show more și câte o captură principală reală pentru fiecare agent.** Cele trei grupuri au salvat textul extins/HTML și metadatele după fiecare agent. Părintele a verificat ID-urile fără duplicate sau omisiuni, toate hashurile DOM principale, existența/formatul celor18PNG și egalitatea numărului de apeluri cu inventarul nativ. Nu însumăm calls, mesaje și capturi ca unități echivalente.

Baza suplimentară privată este `agent-deep-dive/` sub rădăcina din §2. `reconciled-inspectors.json` leagă toate ID-urile de DOM/captură/SHA și întinderea lecturii; `group-1/report.md`, `group-2/report.md`, `group-3/report.md` păstrează deciziile operaționale, locatoarele per agent și traseele de cod. Inventarul versionat leagă acest supliment de baza Omnis `828445d25257e3a9c39d826e1641fb4429bc9a47`.

| Agent / ID | Blocuri UI | Ce aduce comparației și ce rămâne limitat |
|---|---:|---|
| Root / `7254ce7b` | 114 | Recon → citire notă → model → specialiști → follow-up → reconciliere. Decizia Brain nu este aceeași operație cu mesajul livrat. |
| Recon / `dd49cb2a` | 78 | Formulare/JS/operații/roluri → notă comună →15coverage. Discovery-only în brief nu a împiedicat efecte privilegiate. |
| Infra / `d6c9b933` | 76 | Stack/headers/fișiere → notă/model. Save tardiv poate înlocui modelul Root; nu există CAS upstream pe acel save. |
| Auth / `957b23a9` | 100 | Controale pe canale/identități și follow-up; create/update refuzate apar tot ca report cards. |
| IDOR / `b14d6b8d` | 34 | Citire mapă/model → probe/controale → rapoarte/notă/amendament. Write-authz rămâne gap, nu este închis de completed. |
| SSRF / `ea103836` | 91 | Ipoteză → control → indiciu Root → revizuire impact; eroarea după fetch nu dovedește zero efect. |
| XXE / `9aec127c` | 80 | Separă callbackul altui fetcher de XML; infirmă capabilitatea de rețea presupusă din configurație. |
| LFI / `61d382cb` | 28 | Baseline/probă/control și conținut distinct, nu simplu200; testul local al fixului nu este retestul aplicației. |
| XSS / `3abe48b4` | 78 | Source→sink→execuție browser, refacere secvențială după contaminarea contextului; nu detector XSS nativ ascuns. |
| SQLi / `7d0571cd` | 113 | Matrice/oracles/scanner și confirmare manuală; cart fără auth și register cu lock nu sunt negative secure. Declară11coverage, ledgerul are9. |
| Info/RCE / `c7a54d0d` | 72 | Separă disclosure/debug de execuție; validitatea credentialului la destinația downstream nu a fost probată. |
| Redirect/CSRF/logic / `744ac73f` | 170 | Hopuri/efect business/cookie age și controale browser. Password-change blocat de lock nu probează takeoverul afirmat mai larg. |
| CORS / `a8533d83` | 60 | Counterevidence reduce impactul; nota produce pista Remember și task nou, nu severitate umflată. |
| Sensitive Files / `cf62de63` | 31 | Expunere observată, impact downstream separat; consolidare în rapoarte existente, fără duplicarea tuturor pașilor. |
| Remember / `59380b0f` | 50 | Citește nota CORS și face propriile controale de identitate; privileged write rămâne neprobat din cauza lockului. |
| Stored XSS/write authz / `2c83431f` | 145 | Task multi-part și controale; unele concluzii din sursă nu au propriul e2e. Restartul țintei din run este efect istoric, nu cleanup dovedit. |
| Race/Coupon / `582d97ac` | 46 | Checklist vizibil,5create attempts/3acceptate; două refuzuri arată tot ca report cards. Done nu șterge condițiile/gaps. |
| Chain Validation / `962fa89c` | 35 | Probe proprii pe două lanțuri,2updates pe același report,0rapoarte noi; nu D14 independent pentru36findinguri. |

**Întinderea exactă:** au fost parcurse textele/proza operațională randate, inclusiv finalurile și expandările; grupul2 a citit și blocurile distincte de cod vizibil. Raw/executable literals sunt private, nu readjudecate universal. Mesajele inițiale, livrările ascunse, outputs omise și reasoning nativ nu sunt pretinse citite în UI. Modalurile nu au paginare proprie; toate blocurile din array-ul încărcat sunt în DOM, dar unele previewuri sunt tăiate înainte de DOM. Inspecția vizuală este reprezentativă pe familii, nu audit WCAG/toate viewporturile sau comparație pixel-perfect a tuturor capturilor.

### 10.1 Defecte concrete ale referinței pe care nu le portăm

| Referință / locator la pinul §2 | Efect observat | Cerința Omnis |
|---|---|---|
| `AgentTranscript.tsx:45–63` + `TerminalRenderer.tsx:103–125` | Textul shell devine `{__raw:...}`, dar rendererul caută `content/error/exit_code`; în grupul1 sunt129outputs native care nu apar. | Rezultat tipizat sau explicit unsupported, niciodată dispariție tăcută; preview/completeness distincte de raw evidence. |
| `proxy/tools.py:215–260` + `ProxyRenderer.tsx:37–67` | Producerul emite `entries/page_info`, rendererul caută `requests`; lista, erorile și continuarea pot lipsi. | DTO/decoder/renderer testate împreună pentru success/empty/error/has_more, read-only fără replay. |
| `proxy/tools.py:351–373` + `ProxyRenderer.tsx:72–115` | Producerul emite `hits/total_hits`, rendererul caută `matches`; patternul este vizibil fără hits. | Un rezultat neînțeles nu devine „no match”. |
| `AgentCommsRenderer.tsx:21–40` | Finish ascunde `open_items/final_recommendations/filed_report_ids` și rezultatul operației. | Gaps, recomandări, referințe și consum explicite; completed al taskului nu confirmă metoda sau findingul. |
| `VulnReportRenderer.tsx:19–114` | Randează argumentele, cu severity fallback, fără a trata corect refuzul/dedupe/update failure; Race are două exemple refuzate. | Starea operației și starea findingului sunt separate; tentative/rejected/persisted/confirmed nu se confundă. |

Parentul a recitit direct ramurile coerce/terminal/proxy/handoff/report și producerul listei HTTP; constatările sunt despre referința Strix, nu defecte inventate în Omnis. Modalul gol din tab ascuns a fost explicat prin deferarea `requestAnimationFrame`: `Page.bringToFront` a permis încărcarea. Nu atribuim acea situație unei erori de rețea și nu pornim un alt harness.

## 11. Direcția concretă pentru UI Omnis, după S1

Aceasta este specificarea cererii actuale pentru amendamentul punctual, **nu UI implementată sau nouă acceptare estetică**. Păstrăm Overview și baselineul Omnis; nu copiem brandingul, sidebarul cloud, promoțiile, ReactFlow/Dagre/Tailwind sau toastul suprapus Strix.

### 11.1 Overview: consum lizibil, nu consolă

Card compact **Run details / Usage**, cu axe stabile etichetă→valoare și detalii secundare la cerere. Stare/Needs you/rezultate păstrează ordinea actuală; nu mutăm transcriptul în Overview. `RunDetails.tsx:42–47,127–211` este referința de compoziție, nu contractul datelor Omnis.

| Metrică cerută | De unde vine / ce lipsește în Omnis | Decizia minimă |
|---|---|---|
| Run time | `RunView`/`RunSummary` nu expun start/final. Evenimentele au timestamp persistent. | Extensie read-only cu start/final/as_of și wall elapsed, inclusiv pauzele, explicit. Nu cronometru pornit la mount și nu final din click Stop. Lipsa datelor rămâne UNKNOWN. |
| LLM requests | `usage.totals.dispatches` numără alocări, nu paid calls; `DispatchUsage` are stări/timestamps și receipt. | Proiecție cu definiție explicită a requests observate și a submissions pending/unknown; nu simpla redenumire a dispatches. SENT nu dovedește singur facturarea. |
| Input tokens, din care cached | `UsageTotals.input_tokens/cached_tokens`, OBSERVED/PARTIAL/UNKNOWN | Folosim agregatul existent al întregului run, nu suma paginii. Componenta cached nu se adaugă iar la total. |
| Output tokens, din care reasoning | `UsageTotals.output_tokens/reasoning_tokens` | Același contract; reasoning este contor, nu conținut de raționament afișat. |
| Total tokens | `UsageTotals.total_tokens` și reconcilierea decoderului | Păstrăm totalurile exacte și starea de observație, fără Number pe șiruri mari sau date inventate. |
| Cost | `cost_observed` există, fără câmp monedă în DTO actual | Cost observat cu coverage; simbolul monetar numai dacă moneda este stabilită de contractul sursei. Nu estimăm tacit și nu facem pricing call pentru acest card. |
| Agents | Summary-ul este o pagină de attempts, nu total agenți | Agregat server-side de taskuri distincte, Brain inclus explicit; attempts/recovery separat. Nu numărăm actorul contabil dedupe drept worker. |

Cele661requests/$1.82/19actors sunt referința Strix, **nu metrici Omnis**. `RunDetails.tsx:211` folosește usage.agents.length, de aceea diferă de18agenți în sidebar. Nu copiem ambiguitatea. `projections.py:88–157`, `run_contract.py:381–411`, `web/src/shared/api/runs.ts:54–98,155–183` și `RunPanel.tsx:277–280,335–342` au deja baza contabilă; nu se construiește alt serviciu de usage.

### 11.2 Activity: două pastile, Feed și Agents

- **Activity** înlocuiește eticheta Brain stream; UI canonic rămâne în engleză. URL-ul `/stream` și linkurile run/attempt/source/cursor existente rămân compatibile; noua selecție de subview trebuie validată, fără identificatori sensibili sau autoritate în URL.
- **Feed:** evenimente scurte ale întregului run — actor, verb semantic, rezultat/stare, timp și link către agent/probă. Spawn, tool call/result, decizie, întrebare, notă/model, validare și control se tipizează numai când există producerul real. Nu un monolog lung și nu toate argumentele/receipturile deschise implicit.
- **Agents:** listă ierarhică compactă sau dropdown expandabil, cu Brain și copiii lansați efectiv, nume/scop scurt, status text+dot și indicator de activitate. Agent configurat nu este spawned; taskul și attempturile nu se multiplică arbitrar.
- Actualizarea folosește mai întâi pollingul existent la5sec (`runs.ts:5`), cu snapshot/stale și fără resetarea tabului, selecției, focusului sau scrollului. Nu introducem WebSocket/SSE doar pentru eticheta live. Un run final nu demonstrează prin screenshot timingul spawnului; acesta se probează pe consumerul Omnis.
- `RunPanel.tsx:238–260` are deja grupare task/attempt și ancestor context. `projections.summary:254–303` este implicit20attempts, bounded64KiB, fără cursor roster. Cererea de listă completă cere paginare deterministă/read-only și total separat, nu limită mărită sau pagină locală prezentată drept toate datele.

### 11.3 Inspectorul etalon, click pe orice agent

Header stabil cu nume/misiune, rol/model și status textual, apoi cronologie tipizată: delegare, decizie/observație înregistrată, call→pending/result/error, notă/model, coverage, candidat/validare/raport și predare. Iconurile locale și etichetele scurte diferențiază familiile; culorile sunt suport, nu verdict. Body-ul trebuie să fie lizibil și să folosească spațiul viewportului, nu să copieze60vh cu microtext slab contrastat.

Misiunea, rezultatul și gaps rămân în prim-plan. **Prompt/input permis și pinned skills**, usage și proveniența sunt inspectabile explicit, dar nu umplu vederea inițială. Outputul extern se randează inert, redactat și bounded; summary/preview nu pretind că sunt evidence integrală. Deciziile sunt explicații operaționale înregistrate, nu hidden chain-of-thought.

Filtre propuse: familie/tip de eveniment, actor și stare; un filtru local se numește loaded-page. Istoricul complet al agentului cere reader/cursor scoped, nu filtrarea unei pagini globale și nici fetch-all. Auto-follow numai aproape de coadă; când operatorul citește sus, noutățile se semnalizează fără salt forțat. Stop rămâne imediat, legat de runul exact și accesibil cu inspectorul deschis; Escape/Close/focus return, loading/empty/stale/unknown/error și reduced motion rămân.

**Closure nativ:** `Engagement.tsx:48–52`/`copy.ts:2` → `RunPanel.tsx:59–145,232–260,292–347` → `projections.summary/events` → `run_store.event`. DTO/OpenAPI/generated/decoder/teste se modifică împreună cu producerul. Inspectorul actual este înregistrare pe attempt, nu istoric multi-step complet; layoutul singur nu produce calls/results lipsă. Păstrăm `Inspect consuming Brain` și verificarea refs cauzale, nu doar un chat vizual.

## 12. Cum funcționează tehnic și ce cod preluăm exact

La acest pin, **specialistul nu este o clasă Python diferită per vulnerabilitate**. Specializarea este nume/task + rolul din prompt + skills Markdown + context + toolset. LLM propune acțiuni; factory/SDK/coordinator le execută și persistă. O metodologie scrisă nu este automat enforcement.

Prefixele din tabel sunt relative la `upstream-v1.7.0/` din §2. Locatoarele complete, callerii, dependențele și testele selectate se află în rapoartele celor trei grupuri și extind **aceleași SR01–SR09**, nu creează un runtime/backlog paralel.

| Traseu și cod efectiv | COPY / ADAPT / KEEP și first consumer |
|---|---|
| `core/runner.py:run_strix_scan:180–665` → `agents/factory.py:build_strix_agent:657–743` → `make_child_factory:746–777` | **KEEP** `AgentStep`/`AgentRunOwner` Omnis. SDK-ul este deja aceeași familie; nu importăm încă un coordinator, SQLite, SandboxAgent cu Shell/Filesystem sau session owner. |
| `agents/prompt.py:_resolve_skills:24–75`, `render_system_prompt:78–149`; `skills/__init__.py:validate_requested_skills:215–239`, `load_skills:264–300` | **COPY_CONTENT/ADAPT** rubrici din `skills/coordination/root_agent.md:19–40,67–96`, pentru recipe recon S3 și investigator/validator S4. **KEEP** catalogul/composerul calificat; missing-skip, shadow global și încărcarea implicită nu se portă. |
| `tools/agents_graph/tools.py:create_agent:495–607` → runner callback506–518 → `core/execution.py:spawn_child_agent:343–404`, `_start_child_runner:1108–1166`, `_run_cycle:711–889` | **ADAPT** obiectiv/brief/skills/parent și lifecycle pe `run_runtime.new_attempt`/`work`/`AgentStep`; contexte selectate, nu serializerul parent-history din `core/inputs.py:336–371`. S3/S4, concurență S5. |
| `tools/agents_graph/tools.py:send_message_to_agent:170–270`, `agent_finish:611–752`, `_render_completion_report:63–114`; coordinator send/consume | **ADAPT** predare cu summary/findings/reports/open items/recommendations; **KEEP** PG inbox+consume în tranzacțiile native. Formatterul pur `_render_filed_report:52–60`/completion este candidat mic, nu mailbox best-effort/auto-wake. S3→S5. |
| `tools/notes/tools.py:_mark_authorship:140–152`, `_to_note_listing_entry:155–177`, create/get/list; `tools/threat_model/tools.py:_save_impl:327–389`, `_amend_impl:418–459` | **COPY/ADAPT** atribuirea, indexul și rubricile `_REQUIRED_SECTIONS:53–58`; **KEEP** PG/CAS/ExactRefs. S3 producer→Brain read→brief; nu store global/RLock/mirror JSON sau save care șterge amendamente stale. Nu există un crawler autonom upstream de extras din aceste funcții. |
| `agents.factory:_BASE_TOOLS:568–612`; SDK function schema/tool execution; `runtime/session_manager.py:258–370` și `runtime/docker_client.py` | Registrarea este SDK, toolurile rulează în host callback sau sandbox partajat. În run, `curl`/scripturi/`agent-browser`/scanere sunt lansate din shell. **NOT_PORT** întregul runtime; **KEEP** transport/owner/Stop Omnis, extensii sandbox numai când admise. |
| `tools/output_store.py:47–166`; `tools/proxy/tools.py:list_requests:135–266`, `view_request:269–373`, `repeat_request:390–453`; `caido_api.py:build_raw_request:173–214` | **COPY/ADAPT** preview UTF8 și regula framing în reader/executor HTTPX S2, nu un serviciu Caido nou sau parser/retry generic. Capture-read este read-only; replay are admitere nouă. Preview nu este cap incremental al socketului, DLP sau evidence durable. |
| `tools/reporting/tool.py:create_vulnerability_report:982–1460`, `_do_create:780–963`, `_verify_http_exchange_ids:231–265`; `report/dedupe.py:check_duplicate:328–416` | **ADAPT** rubrici/counterevidence/severity-conditions în candidatul S4; **NOT_PORT** ca D14. Toolul validează formă/IDs, nu execută universal PoC. Proxy outage poate elimina IDs cu warning; dedupe folosește LLM și eșecul poate lăsa notduplicate. Omnis păstrează propriul sender/DATA și oracle/writer. |
| `report/state.py:add_vulnerability_report:330–437`, `update_vulnerability_report:457–553`; `report/writer.py:render_vulnerability_md:223–361`; coverage tools/update și `finish/tool.py:139–353` | **ADAPT** supersedes/istoric și rubrici; **KEEP** stocarea/proiecțiile PG native, **NEW** glue-ul finding writer absent, legat de oracle-ul S4. ReportState global absent poate întoarce success/notpersisted; completed poate păstra warning/gaps. `csv_safe:35–53`/`safe_fence:56–66` sunt helpers mici COPY la primul export T5, nu prerequisite ascuns pentru IDOR sau S7. |

**Validarea referinței:** Chain Validation folosește același spawn generic și context moștenit; numele nu îi acordă independență. Recomandarea discovery→validation→reporting din `root_agent.md:84–89` este prompt/metodologie, nu o ramură obligatorie a codului create-report. Actorul dedupe compară identitatea raportului; nu face replay/oracle. În Omnis, D13, candidat/triage și D14 cu attempt/auth/probe/control proprii rămân mecanisme distincte. Nu trebuie rescris ceea ce există; trebuie legat glue-ul SECURITY absent de checkerele compatibile și de first consumer.

### 12.1 Dependențe: ce este comun, ce este numai upstream

Omnis are deja `openai-agents==0.19.0`, `openai==2.45.0`, Pydantic și HTTPX. Sursa Strix declară SDK `[litellm]>=0.19.0,<0.20` și alte intervale; lockul său nu este inventarul binarului instalat sau ordin de înlocuire a pinurilor Omnis. Nu importăm LiteLLM/OAuth/subscription/MCP/cloud/PDF/scanere doar fiindcă sunt în manifest. SDK public0.19.0 a fost descărcat separat ca wheel de analiză cu hash/licență MIT; nu este executabilul Strix atestat.

**Clarificare cryptography:** Omnis are50.0.1, Strix cere48.x, dar comentariul `pyproject.toml:51–53` motivează plafonul prin wheel macOS Intel/universal2, nu incompatibilitate API demonstrată. Nu este blocker general de reuse și nu cere upgrade/downgrade preventiv. Un upgrade justificat rămâne opțiune dacă unitatea aleasă îl cere efectiv; nu reinventăm codul pentru a evita orice schimbare de dependență. Nu importăm manifestul integral și nu atingem seiful fără proba consumerului afectat.

### 12.2 Cod copiat și executat: un singur spike, nu numai analiză

Sub mandatul suplimentar explicit, developerul a pregătit `agent-deep-dive/group-2/reuse-spike/`: nouă copii byte-exact de sursă/licență, testul `test_compat.py`, adapterul finit `adapted.py`, README, diff și manifest înghețat. Părintele a verificat cele15hashuri și egalitatea celor9copii cu sursele. Licența Apache-2.0 și proveniența sunt păstrate; source native deja versionat nu a fost modificat.

**Întrebarea executată:** se poate copia `_coerce_arguments` din factory Strix înainte de `finish`/`WorkerFinal` Omnis fără schimbarea refuzurilor native? Proba compilează funcțiile pure reale din copii AST, inclusiv decoderul JSON nativ/DTO, nu simulează răspunsul țintei sau un finding.

**Rezultat autor:** RED6teste/2eșecuri așteptate/exit1 → GREEN6PASS/exit0. Coercion upstream poate șterge un membru JSON duplicat și poate repara stringul `gaps` într-o listă; inputul brut este refuzat, cel reparat ajunge acceptat. Controlul pozitiv al sursei originale rămâne în suite; nu s-a relaxat aserțiunea. Adapterul finit doar deleagă decoderului/DTO native și întoarce bytes nemodificați.

**Decizie:** **NOT_PORT generic coercion / KEEP strict native boundary**. Cel mai mic patch de produs este să nu adăugăm acel wrapper. Adapterul este numai probă, nu helper de instalat. Proba autorului folosește Python3.13.12/Pydantic2.12.5; reviewul independent **APPROVED_SOURCE_SCOPED** a fost urmat de o singură reexecuție neschimbată cu `/home/kali/OmnisAI/api/.venv/bin/python -I -B <spike>/test_compat.py`: **6/6PASS, exit0,0.132s unittest**, Python3.13.15/Pydantic2.13.5. Diferența de pin este închisă numai pentru aceste șase cazuri de contract extras. Niciun rezultat aici nu este PG/SDK/dispatch/D13/D14/target QA. Produsul rămâne neschimbat.

Raportul privat `agent-deep-dive/spike-independent-review.json` include argv/output/exit/mediu și hashurile before/after; SHA256 `0021fb8487ce0834760c7df0a6894db8fc670a46a5475ec807c84b949311cf67`. Manifestul spikeului este `d7ab92e76377556f1a69895b3dfd5a416afb2af3edbc5afb5ac9d290afb57b0f`; niciun fișier al spikeului nu s-a schimbat la review/QA. Nu se rerulează proba neschimbată doar pentru alt raport.

## 13. Delta inițială — proveniență înlocuită de amendamentul §14

Tabelul următor păstrează **propunerea inițială**, înaintea alegerii explicite a nucleului complet. Limitarea la HTTP/IDOR, exportul lăsat T5 și ordinea strict liniară au fost înlocuite în plan§7.2/§14 de mai jos. Nu sunt instrucțiuni concurente sau autorizație de lansare S2; rezultatele istorice de sursă/UI/spike nu sunt rescrise drept integrare.

| Loc în planul existent | Ce se modifică precis | Consumer și ieșire verificabilă |
|---|---|---|
| **S1-UX înainte S2 / SL16 / U07** | Etichetă Activity, Feed+Agents, roster compact și inspector etalon; Overview cu toate componentele usage existente. Proiecții aditive numai pentru runtime/requests/agent-total și cursorii necesari; diagnostic privat separat. | `Engagement`/`RunPanel` + API DTO/projections/decoder/tests. Un run normal actualizează lista fără reset focus/scroll; click arată decizii/call/result/gaps, nu UUID dump. Totalurile întregului run nu se deduc din pagina20; reload/read-only nu execută nimic. Metricile fără sursă rămân UNKNOWN. |
| **S1 core, înainte de efecte S2** | Remediul finit al stagnării deja reprodus, nu receipt nou = progres. Păstrăm strict JSON/DTO, nu generic coercion demonstrat incompatibil. | Același owner/completion și testele afectate; inputuri/revizii identice fără informație nouă nu produc progres fals; reproducerea legitimă are scop și precondiții explicite. Fără total LLM cap nou. |
| **S2 / SL15+SL17 / U04** | HTTP/auth/captură/health la sinkul comun; output/error/completeness/pagination tipizate până în inspector. Separă read/search de replay. | Allow→receipts/hopuri/identitate/probe recitibile; deny offscope/foreign identity/redirect/Stop înainte de efect. Mismatch/string/empty/error/has_more vizibile, nu „no results”. Lock500/auth-invalid nu devin negative secure. |
| **S3 / SL19–SL20 / U02+U05** | Pachet recon calificat, observații/mapă/model revizionate și atribuite; Brain citește index→punct→probe înainte de brief. Checklist = proiecție de obligații/gaps, nu autoritate. | Recon refs→citire Brain→decizie→brief se probează end-to-end. CAS409, foreign ref, shadow/unqualified skill și mandatory overflow refuzate; amendamentul păstrează contradicția/autorul, nu save-later-wins. |
| **S4 / SL21–SL23 / U03+U06** | Metodologie IDOR+triage+D13+D14; carduri candidate/rejected/persisted/confirmed distincte, controale efective și gaps la toate finalizările. | Validator cu attempt/context/auth/probe/control proprii→oracle/writer→finding inspectabil. Report rubrici/ID existent/confidence/200 nu confirmă; owner/shared/fixed/benign/login200/auth-invalid/missing evidence nu confirmă și nu certifică secure. |
| **S5 / nucleul SL35 / U03+U08** | Maximum2workeri incluzând draining/validator, același owner/inbox; izolare context/process/auth și livrat/persistat/consumat/decizie distincte. Follow-up terminal = successor readmis. | Duplicate/late/persist-failure/owner-loss/UNKNOWN și post-Stop receive-only fără wake/resend/auto-Resume. Browserul partajat upstream nu este izolare task/attempt; validatorul așteaptă slotul eligibil. |
| **S6 / calibrarea existentă** | Prima tentativă autonomă proprie, baseline post-Strix și condiții health/auth/oracle/cleanup cunoscute. Se compară lanțul recon→decizie→control→finding, nu numărul de agenți/carduri. | D03 minimum finding confirmat independent; negativ util/degradare nu închide. Datele evaluatorului și soluțiile din loguri nu intră în investigator; hints asistate separat. |
| **S7 / acceptarea existentă** | Coerență UI/DB pe snapshot/cursor/revizii, coverage/checklist/gaps/inbox/UNKNOWN/cleanup și istoric fără rerun; dispoziție A explicită. | QA installed/reload/restart și gate aplicabil pe bytes integrați. Completed nu ascunde obligații;18agenți reali nu devin19din accounting,9coverage nu devin11din summary, refuzul nu devine report persistat. Fără extinderea tacită la T5export sau G-PATH. |

Familiile browser/XSS/CSRF, OAST/XXE/SSRF, traversal, SQLi/scannere, RCE/deserializare/business/race și attack paths folosesc rubricile comune, dar își păstrează transporturile/oracles/sandbox/eval proprii înainte de activare. Nu sunt șterse din plan și nu devin toate prerequisite ale IDOR. Primul circuit util și evoluția către amploarea Strix rămân două niveluri diferite.

**Prima schimbare recomandată:** închiderea scope-ului S1-UX pe o singură vedere etalon Activity→Agents→inspector, cu proiecțiile necesare și metricile deja disponibile, apoi propagare după feedback uman; remediul de stagnare se tratează separat înainte de efectele S2. Nu alt audit general sau alt runtime. Source-kit-ul/spike-ul rămâne candidat privat neintegrat; integrarea reală cere developer, review și QA pe consumerul afectat, nu promisiunea „va merge din prima”.

## 14. Amendamentul nucleului complet și verificarea suplimentară

### 14.1 Decizia, sursele și ce schimbă față de studiul lui Sol

Operatorul a ales explicit: **S7 = nucleu HTTP/browser/scripturi sandboxate/recon/notițe/hartă/threat model/delegare adaptivă/validare independentă/raport și UI**, inițial evaluat pe IDOR/BOLA; A amânat, pairing manual suficient. Nu este clonă a runtime-ului Strix, promisiune de36findinguri sau mandat de implementare. Criteriile și dependențele au fost mutate în plan§7.2 și reconciliate cu arhitectură/UI/stack; propunerile anterioare §8/§13 și M11 nu guvernează noul exit.

Baza Omnis este `1843c7bf89afe6014cc1101ae69d301a5fc6167b`; sursa Strix rămâne `55bc07991aacb1c26a81b43e7ca53148730d2019`. Cele35intrări de sursă din SR01–SR09,21căi distincte, au fost recalculate de părinte: SHA și intervale valide, fără drift. Doi analiști read-only au confruntat sursa originală cu DB/logurile, nu doar rezumatul anterior. Rapoartele originale sanitizate sunt păstrate privat sub `t2-amendment/` în baza§2, cu hashes `8d04921107b1078a01b31df203c4b78eb496470e0fc573815da54fcfcd79ba9a` (orchestrare) și `2755f155aa9ee22119a820aed91a00331fb0b5a7e8bcff77517a408c2a53d75f` (transporturi). Concluziile aplicabile sunt aici și în aceleași [fișe SR](strix-7574-porting-cards.json), nu într-un backlog nou.

Originalul corect este runul **nested7574** sub directorul exterior d7f4 furnizat de operator; cele două runuri nu se însumează. Snapshotul11fișiere este identic cu originalele nested; WAL original0bytes, copie statică deschisă immutable/read-only. Inventarul sursă a reconciliat18sesiuni/17copii direcți,2987records,928perechi call/output fără orfani,27tooluri și21skills explicit selectate. Inspecția browser suplimentară a redeschis Overview/Agents/Issues și Root/IDOR/Race/Chain, cu114/34/46/35blocuri și expandările11/1/8/1; **nu revendică o a doua lectură integrală18/18**. Suplimentul anterior§10 rămâne dovada acelei lecturi. Un selector de diagnostic a eșuat pe un nod SVG fără innerText și a fost corectat la selectorul nodurilor; nu defect al produsului și nu QA Omnis.

### 14.2 Legăturile care trebuie portate, nu numai lista toolurilor

| Lanț original la pin | Ce dovedește / ce primește Omnis |
|---|---|
| `core/runner.py:462–535` → `agents/factory.py:657–777` → `agents/prompt.py:24–149` → `core/execution.py:711–889` | Factory comună; specializare prin misiune/skills/context/tools, nu clase per vulnerabilitate. SDK execută; coordinatorul gestionează lifecycle. `load_skill` adaugă referințe în context, nu permisiuni; în run nu a fost apelat. KEEP SDK/owner/composer nativ, EXTEND rolurile/pachetele/toolurile reale. |
| `tools/agents_graph/tools.py:495–607` → callback runner506–518 → `execution.spawn_child_agent:343–404` → `inputs.child_initial_input:336–371` |17copii direcți, toate cer inherit_context. Ultimul input316511bytes nu este compatibil cu request32KiB; context selectat+mandatory facts+refs este adaptare Omnis explicită. Omnis păstrează modelul pinned per rol, nu același model global presupus pentru orice copil. |
| Recon DB210/211→nota a8160b→Root261/262read→265/266model→299–316nouă delegări | Toate nouă briefuri citează nota. Producer→read→decizie este proba necesară S3, nu doar „delivered”. CLI127–505 confirmă traseul public fără a importa credentialele/rețetele în investigator. |
| CORS DB1945–1948→nota623860→Root2069/2072→Remember2077/2079→read2088/2091 | Rezultat limitat/negativ cu indiciu util → specializare nouă și investigație proprie. Nu este nesting și nu transformă negativul în finding; S5 păstrează concluzia și admite successorul pe noul basis. |
| Gaps coupon IDOR934/935 și Root1080; BusinessLogic handoff2493/2543→Root2750–2751→Race2757/2759 și Chain2758/2760 | Ipoteza utilizatorului este corectă pentru acest run: Root creează taskul special din informația deja obținută, nu are un agent permanent de cupon. Race face5create attempts,3acceptate și2refuzate; completed/open_items nu certifică toate probele. CLI831–933 și1029–1098. |
| `agent_finish:611–752` → `_render_completion_report:63–114` → `core/agents.py:417–516` | Păstrăm summary/observații/gaps/recomandări/refs. NOT_PORT mailbox clear-before-persist, notice-before-send ori revival interactive terminal; Omnis folosește cele două tranzacții native și successor readmis. Nudge-ul `_run_until_lifecycle:491–606` nu este D13. |

**Frontiera Omnis care lipsește realmente:** `agent_runner.py:44–89` are numai BRAIN/RECON, read_context/finish, arguments `{}` și history max1; `projection:128–194` reconstruiește read_context. `agent_composition.py:69–86` acceptă doar omnis-agent-core. `run_runtime.py:new_attempt:255–312` selectează brain/recon, iar `complete:1128–1130` resetează stagnarea pe consumed_refs nevid. Planul cere extensia **împreună** a DTO/registry/compoziție/history/owner/receipt/DATA/Stop/proiecții/decoder/UI și remediul finit al progresului fals; nu simpla adăugare a unui skill și nu refactorizarea fundației. Paths vechi `agent_run_owner.py`/`agent_run_service.py` nu sunt fișiere existente: ownerul real este `run_runtime.py:AgentRunOwner`.

### 14.3 Conținut pregătit deja: nu îl rescriem

Branch-ul `content/strix-s234-catalog@1885d3f9dd9d498008a84d005ad6197f4807db2f` conține79originale și6adaptări `skills/strix-catalog/prepared/`. Părintele a verificat bytes/SHA și comparația:70originale identice/9diferite față de v1.7.0; IDOR/standard/deep/severity/python sunt identice. Coordination/handoff/HTTP/recon/IDOR/validation se refolosesc; browser/python methodology se completează în același kit. Fișele indică fiecare cale/range/hash, delta relevantă, manifest/procedură/schema/binding și primul consumer. Nimic nu a fost cherry-pick-uit/publicat aici.

Cele6adaptări au **48390bytes**; IDOR singur9993bytes față de composer8192. Păstrăm corpul metodologiei, nu îl reducem la un prompt generic: variantă aplicabilă+obligații mandatory și referințe opționale calificate la cerere, cu măsurarea requestului SDK complet. Lipsesc handlerii reali, calificarea SECURITY și consumerii, nu textul în sine. Eval înainte Publish, fără soluții ShopShfere în datele investigatorului și fără allowance de prompt dedus din API64KiB.

### 14.4 Browser, scripturi și raport: reuse la granița corectă

- **Browser:** Strix execută agent-browser0.26.0 din shell (`containers/Dockerfile:111–135`), nu furnizează un driver Python ascuns. Păstrăm biblioteca **Playwright Python1.63.0** canonică; adaptăm metoda snapshot→act→resnapshot/sesiuni, nu adăugăm CLI/daemon/Node/runtime Strix. Sesiune denumită în prompt nu este binding de attempt. Browser hardened+transport/CA+G-NET/G03b/G-EFFECT preced fiecare efect.
- **Scripturi:** factory435–499 adaptează SDK Shell exec/poll; Python este shell, nu kernel separat. SDK Shell0.19.0 a fost comparat: cere BaseSandboxSession/authority/result adaptation și are semantică timeout/fallback/output incompatibilă pentru import direct. Minimum ales: interpretoare fixate + adaptor batch tipizat în executorul privat, artifact/workspace/process/outputs și poll/cancel/readback; fără alt coordinator sau REPL permanent. Modelul poate pregăti/edita scriptul ca date, dar nu instalează tools și nu acordă egress. Fiecare request din threads/subprocese este admis/contorizat la sink.
- **HTTP/evidence:** KEEP HTTPX; captura→read/search→modify/replay și testele framing sunt utile. Caido nu este clientHTTP autonom de extras; parserul dict pierde duplicate, timeoutul replay nu autorizează retry. Preview UTF8 nu este cap incremental sau evidence durabil.
- **Raport:** portăm ansamblul rubricilor finding+istoric din `report/writer.py:223–396`, nu doar safe_fence. Writerul upstream148–220 produce Markdown/CSV/JSON și temp+rename, **nu HTML Omnis sau snapshot PG/fsync**. S4b introduce glueul necesar HTML/JSON inert/eligibil/imutabil; report-tool/LLM dedupe rămân distincte de D14. B13d retest și PDF/CSV/SARIF nu devin prerequisite primului core.

**Blocker tehnic real înainte S2b:** mitmproxy12.2.3 rămâne respins. Admiterea unei versiuni/remedieri și closure-ului fixate precede QA; B01e-build LAB_TEST_ONLY apoi integrated/confinement preced traficul. Nu am făcut lookup de latest, install, downgrade crypto sau test de proxy în această analiză; planul nu îl declară rezolvat. HTTPX trusted distinct nu este blocat retroactiv.

### 14.5 Performanța observată și măsurarea Omnis

| Axă | Observat în referință | Interpretare corectă pentru S6 |
|---|---|---|
| Durată run |2139.176149s = **35.65minute** | Wall start→end, nu timp CPU/LLM/target separat și nu deadline Omnis promis. |
| LLM |661requests;18agenți+dedupe=19actori,40cereri dedupe | Tool calls și target requests se contorizează separat; dedupe nu este validator tehnic. |
| Tokens |84364528input, din care78364433cached (**92.89%**);763181output, din care425614reasoning;85127709total | Cache/reasoning sunt componente. Costul mic nu permite extrapolare fără aceeași rutare/cache/model; nu pretindem atâtea tokenuri unice sau gândire internă inspectată. |
| Cost |1.8153400036USD persistat, UI1.82USD | Cost per-agent repartizat proporțional upstream, nu factură individuală. Omnis nu inventează moneda dintr-un DTO fără contract monetar. |
| Exec/poll |372exec_command+56write_stdin;356outputs exit0,12nenule,60running |428outputs nu sunt428procese; poll running nu este terminare. Mediană wall a apelului/poll0.63845s, maxim30.1256s, nu latență E2E a jobului. |
| Trafic logat |22644access records în **24.47minute**, inclusiv30malformate;16933status404,153status500 | Fereastră parțială fără fus explicit; matching temporal nu este join autorizant. HTTP200/exit0 nu confirmă findingul. |
| Burst/degradare |10678records în minutul19:31, vârf266într-o secundă;128lockuri SQLite din153tracebacks | Nu in-flight concurrency măsurată și nu cauzalitate dovedită a lockurilor. Nu portăm avalanșa de requesturi ca obiectiv de viteză. |

S6 măsoară pe consumerul normal deja necesar: timp până la prima observație/task util/candidat/confirmare, queue/admission/execute/capture/check/readback, calluri LLM/target/tool distincte, tokens/cache/cost cu observație, procese/bytes/cancel, replay/intervenții/gaps/cleanup. Numitorul eficacității este setul adjudecat suportat, nu36rapoarte. Lipsesc ground-truth sigilat/FN census/CPU-RSS/request ledger complet și condiții egale; **nu paritate sau superioritate demonstrată**. Protecția target minimă (rate/health/429) rămâne înaintea efectelor; algoritmi avansați de rate-limit pot veni ulterior, nu suspendă protecția de bază. MONITOR fără plafon total LLM rămâne.

### 14.6 Frontiera amendamentului și verificare

Schimbări admise: plan/arhitectură/UI/stack, fișele SR, proiecțiile de status și regresii documentare. Fără modificări în api/web/cli de produs, source-kit, manifest/lock, servicii/DB/date/seif/operator/Strix. Originalele din temp și fișierele protejate rămân neatinse. Revertul commiturilor documentare inversează numai specificația, nu date sau efecte externe.

RED documentar real: cele două noi teste de nucleu eșuează pentru lipsa contractului§7.2, nu pentru import/harness. Controalele ulterioare cer toate incrementele și detectează eliminarea browserului obligatoriu, exportului sau dispoziției A. Reviewurile independente și GREEN final se consemnează pe snapshotul exact; proba veche6/6strict-decoder nu se rerulează și nu certifică noul nucleu.

**Adjudecare finală a părintelui — ACCEPTED_DOCUMENTARY_SCOPED:** candidat `20ba948a9138f1a987c8576d2cc393fd0a30639d`; reviewul de livrare a cerut două corecții MEDIUM, iar reviewul complementar de sursă/autoritate a dat `APPROVED_SCOPED_DOCUMENTARY_BOUNDARIES`. T2-DELIVERY-01 (rezumate/milestone-uri vechi din hartă) a fost reprodus și corectat în `74ae856a2d72b195023ec527da422fc0ae3b1542`; T2-DELIVERY-02 (două clauze M-LAB care amânau exportul) în `f2d2801173bc920d60d549419b8d096de3517b90`. Ambele au RED→GREEN propriu și re-review **APPROVED_SCOPED_DOCUMENTARY_DELIVERY** pe f2d28011, cu dispoziții explicite CLOSED_DOCUMENTARY_SCOPED și zero findings noi. Acoperirea originală și aprobarea complementară sunt păstrate numai pe bytes/secțiuni neschimbate; actualizarea de status de după review nu schimbă contractul tehnic.

Originalele byte-exact sunt `t2-amendment/review-delivery.json`, `review-boundaries.json`, `review-delivery-followup.json` în baza privată§2. Dovezile: `20ba948a-evidence.json`, `20ba948a-docs-browser.json`, `74ae856a-docs-tests.log`, `f2d28011-docs-tests.log` și RED păstrat. `python -B scripts/render_docs.py --check`, `python -B -m unittest discover -s tests/documentation -v` și `git diff --check` au exit0 pe snapshotul corectat: **91teste PASS** (89inițial, apoi două regresii aditive; nu însumare de suite). Chromium real a verificat cele4cititoare schimbate la1440/390, celule/tabele/scroll local și zero HTTP(S) subresources; clauzele M-LAB corectate au readback DOM separat. Nu este QA UI de produs sau aprobare estetică. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Noii consumeri runtime, proxyul și sizingul complet rămân NOT_RUN/prerechizite, nu blocate ca analiză sau declarate rezolvate. Nicio relansare implicită după această închidere documentară.

## Sources

[1] file:///home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/private-source-snapshot/run.json
[2] file:///home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/private-source-snapshot/.state/agents.db
[3] file:///home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/installed-static/interface/viewer/static/assets/index-B1JzV4Vu.js
[4] https://github.com/usestrix/strix/tree/55bc07991aacb1c26a81b43e7ca53148730d2019
[5] file:///home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/supplemental-logs/logfromstxRun
[6] file:///home/kali/.local/share/omnis-reference-artifacts/strix-20261108-7574/supplemental-logs/frombrainstxLOG
