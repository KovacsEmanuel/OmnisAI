# Audit critic P2 — diagnostic și propunere de simplificare

**Data:** 20 octombrie 2026. **Snapshot de produs auditat:** `10cb5b96d358d67dbf2e430888173c75e6454f0b`, branch `checkpoint/p2-batch2-pause-20261015`.

**Statut:** analiză și recomandare, **NEAPROBATE pentru implementare**. Nu înlocuiește arhitectura/planul, nu închide P2 și nu autorizează conturi, instalări, trafic sau migrarea datelor. Singura modificare propusă de această felie este acest document. Originalul neversionat `documents/Omnis_Notite_Originale.html` rămâne neatins.

## Verdict

**Nu recomand continuarea neschimbată a integrării actuale. Nu recomand nici rescrierea întregului Omnis. Recomand păstrarea fundației și simplificarea controlată a runtime-ului, cu direcție API-key-first.**

Ideea de a reutiliza Hermes nu a fost absurdă: upstreamul oferă explicit integrare programatică și un runtime multi-provider. Dar reutilizarea este benefică numai dacă reduce munca totală. Omnis a ajuns să modifice internalele acelui runtime, să întrețină mecanisme proprii de control și să demonstreze întâi un executor CONTRACT/PURE, în loc să exercite devreme bucla model → unealtă → dovadă → validare.[2][3]

Nu există dovadă că subscripția Codex este cauza blocajelor recente demonstrate. Nu există nici dovadă că schimbarea cu un SDK ar rezolva automat produsul. **SDK-ul OpenAI este deja folosit la ultimul hop actual.** Decizia reală este cine deține bucla de agent și câtă integrare nativă trebuie menținută, nu dacă folosim sau nu biblioteca `openai`.

### Ce există efectiv

- Control plane local instalabil, FastAPI/PostgreSQL/React/CLI, pairing/sesiuni, drafturi persistente, catalog și probe CONTRACT/PURE, binding/inbox/ledger, Settings Codex finit.
- P2-inert are acceptare istorică scoped în registrul actual. Nu o anulez pentru că înlocuirea runtime-ului este luată în considerare și nu o transfer la HEAD sau la inferență.
- Ultimul registru descrie pregătire/restart reușite ale candidatului corectat; primul model start autentic pe acel fix rămâne NOT_RUN. Nu am verificat live instalația operatorului.
- **Nu există încă traseul de produs scan → finding → raport/retest.** `api/src/omnis/api.py:132` fixează `assessment_ready=False`; `web/src/features/engagement/Engagement.tsx:41–52` are Start disabled și suprafețe indisponibile. Acestea sunt lipsuri de implementare, nu opțiuni de configurare greșite.

## 1. Metodă, verificări și limite

Trei audituri independente, read-only, pe același SHA: arhitectură/plan, runtime/provideri, istorie/livrare. Părintele a citit rapoartele complete și sursele decisive, a refăcut numărătorile Git/patch și a reprodus constatarea de proiecție. Rolurile nu au modificat produsul sau instalațiile.

Surse locale principale: arhitectură §2–9, plan §2/4/7/8/9/11–15, stack §10, README, harta de implementare, `p4a-minim.md`, consumerii API/web/supervisor/native și episoade Git. Inventarul și statistica sunt exhaustive numai pentru căile/intervalul declarat; corectitudinea codului și probele istorice au fost inspectate focalizat, **nu fiecare linie, receipt sau scenariu posibil**.

Probe executate în auditul părintelui:

- `api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_test_operation.py api/tests/test_provider_settings_source.py -q --tb=no`, mediu curățat/HOME și TMPDIR scratch: collect 16/exit0; **16 PASS în 5,71s/exit0**. UDS local real, DB/native/provider doubles declarate; nu integrare live. Output: `/home/kali/.hermes/cache/scratch/audit-tests-5aafj7al/`.
- `python3 -I -B -m unittest discover -s tests/documentation -p test_resume_status.py -v`: **3 PASS/exit0**. Auditorul livrării a executat separat `test_project_status.py`: **11 PASS/exit0**. Aceste teste trec deși statusurile se contrazic; verifică structuri/markeri, nu adevărul produsului.
- Reproducer in-memory al **funcțiilor reale `projection` și `view`, plus `ModelTestView`**, cu numai store/accounting/native-command parsing substituite: `completed → COMPLETE`, `incomplete → COMPLETE`, `failed → COMPLETE`, lipsă receipt → `UNKNOWN`. Aserțiunea că `failed` nu trebuie ascuns ca `COMPLETE` eșuează intenționat, **exit1/defect reprodus**. Nu s-au fabricat rezultate de provider: acestea sunt intrări sintetice explicite ale unui test SOURCE.
- Git/status/diff și inventar patchuri: comenzi read-only reale. Nu au fost rulate canonical, Docker/PG, browser, instalări sau provider/target calls.

Rapoartele independente integrale sunt suport temporar, nu autoritate normativă: `/home/kali/.hermes/cache/scratch/omnis-audit-10cb5b9-20261020/{architecture,runtime,delivery}.md`. Concluziile adjudecate sunt păstrate aici; scratch poate expira.

## 2. Ce a mers greșit

Severitățile de aici sunt de livrare/corectitudine, nu scoruri CVSS.

### F1 — HIGH: milestone-ul tehnic a înlocuit milestone-ul de produs

Prima inferență utilă și primul request target au fost precedate de un catalog/compilator, recipes, closure, publicare, binding, predicate, M1/M2, denominator și qualification. Consumerul reprezentativ `integrations/hermes/upstream/managed-source/agent/contract_execution.py` execută pași CONTRACT/PURE determinist, fără bucla conversațională obișnuită. Este cod real; nu este încă un investigator.

`api/src/omnis/modules/coverage/denominator.py` și `tasks/result_qualification.py` au domeniu finit CONTRACT, nu coverage de pentest. Construirea lor nu dovedește descoperire sau validare Web/API. **Ordinea a pus o generalizare mare înaintea feedbackului de la problema reală.**

Nu fiecare test este inutil. Greșeala este că volumul de acceptări de componente a fost folosit prea mult ca semnal de apropiere de produs. Planul însuși arată că HTTP/auth/discovery/validator/findings/reports sunt încă după P2 (`Omnis_Implementation_Plan.md:301–360`).

**Dispoziție:** înghețarea breadth-ului CONTRACT, păstrarea istoriei și a primitivelor utile; următorul criteriu de produs trebuie să fie o acțiune reală și un rezultat vizibil, nu un alt format sintetic.

### F2 — HIGH: testul de conectivitate este supracuplat

`model_test_source.py:90–184` cere Publish/revalidare → launch inert → preparation → context → records sintetice → assignment → `PREPARED_RESTART_REQUIRED`. `model_test_operation.py:172–198` consumă sursa și starea nativă. Mesajele efective sunt două texte fixe, fără tools.

UI nu mai cere completarea ROE pentru test (`Engagement.tsx:14–15`); această circularitate veche a fost corectată. **Cuplarea backend la catalog/metodă/restart a rămas.** Nu este un ciclu logic infinit, ci un lanț inutil de lung pentru funcția cerută.

**Dispoziție:** SETTINGS_TEST ca operație de sistem, fără skill publicat, Mission, copil sau restart. Păstrează consent/config fixată, secret separat, proiecția aprobată, ownerul unic, reserve→SENT, deadline/Stop, readback și no-resend. Proba de agent/tool este alt criteriu; nu trebuie fals acreditată printr-un smoke de provider.

### F3 — HIGH: integrarea nu mai este un adaptor subțire, iar consumerul este Codex-only

Măsurare din patchurile urmărite de Git: trei patchuri, **23 destinații native unice**, **1.939 linii adăugate/68 eliminate**; separat **20 module adaptor/7.975 linii fizice**, inclusiv comentarii și whitespace. Nu număr întregul upstream copiat drept cod scris pentru Omnis.

Schimbările traversează constructor, loop, turn context, request, recovery/auxiliary, lifecycle, auth și gateway. Arhitectura §5/§5.2 cere păstrarea Hermes și patch atunci când lipsește un seam, fără un criteriu de abandon economic. Acest angajament trebuie reevaluat, nu tratat ca obiectiv de produs.

`provider_models.py:9–13`, `management_contract.py:16–21`, `model_test.py`, `model_request.py` și `cli/src/omnis_cli/forwarder.py:301–302` restrâng traseul la `openai-codex/gpt-6.1-sol/xhigh` și egressul aferent. Este o felie implementată îngust, nu dovada că Hermes nu suportă OpenRouter. Upstream documentează API keys și endpointuri compatibile.[3]

**Dispoziție:** alegerea runtime-ului se bazează pe costul consumerului complet și pe probe, nu pe fidelitatea față de o tehnologie. API-key-first nu înseamnă doar schimbarea dropdownului.

### F4 — HIGH: proba specială AIAgent nu certifică agentul cerut de produs

`run_agent.py:315–324` intră într-un constructor special; `agent_init.py:2331–2374` setează tools/toolsets goale, fallback/auxiliary/fast oprite și client deferred. `turn_context.py:996–1017` leagă turul, îl parchează și execută `run_model_test_request`; nu trece prin bucla obișnuită a agentului.

`turn_api_request.py:287–299` folosește deja `OpenAI(...max_retries=0)` și `client.responses.create`. Acest traseu poate dovedi un call real, nu Brain adaptiv/delegare/tools/compresie. Nu este o simulare totală, dar nici un motor de pentest aproape închis printr-un singur răspuns.

**Dispoziție:** separarea explicită a testului providerului de testul buclei agent/tool. Nu adăuga încă un constructor special pentru următorul provider.

### F5 — MEDIUM: pierdere actuală a statusului providerului în proiecția publică

`model_test.py:900–905` distinge intern `inference_status=VERIFIED` numai pentru model/effort exact și `status=completed`. `model_test_operation.py:109–114` elimină acele câmpuri; `:144–146` publică `COMPLETE` pentru orice observație truthy. UI (`ModelTest.tsx:45`) spune „Răspuns primit”, nu literal „PASS”, însă nu mai poate arăta diferența între răspuns complet, incomplet și failed.

Reproducerul părintelui de mai sus confirmă aceeași proiecție prin consumerii reali, cu doubles de storage declarate. **Nu există aici dovadă că un failed live a fost observat sau prezentat anterior ca succes.**

**Dispoziție:** remediu minimal ulterior în producer/proiecție/DTO/UI/teste: păstrează outcome-ul providerului și cel de verificare, fără raw errors/secrete. Nu modifica ledgerul sau politica de retry ca să repari o proiecție. Defect deschis, nemodificat de audit.

### F6 — MEDIUM: un jurnal contradictoriu este folosit drept stare curentă

README:3 încă spune „blocată la pornirea nativă”; harta:13 și `p4a-minim.md:9` au candidatul corectat pregătit/repornit; rândul SL12 al hărții:121 încă descrie UI9 înainte de Publish. Paragrafe CURRENT/AICI mai vechi descriu faze deja închise. Avertismentele „istoric” nu repară primul headline și rândul activ stale.

Acest lucru contrazice chiar `CONTRIBUTING.md:70`. Poate trimite următoarea sesiune în aceeași investigație deja încheiată. Testele documentare nu verifică semantic această contradicție.

**Dispoziție:** un CURRENT scurt, rânduri curente actualizate în loc și referințe către istorie; nu încă un raport de status sau un verifier semantic. Corecția editorială este separată de aprobarea pivotului.

### F7 — MEDIUM: testarea a devenit o suprafață majoră de mentenanță

`api/tests/test_contract_method_pg.py` are **12.935 linii fizice**. Numărul nu dovedește singur risipă. Episoadele Git arată însă că observatorul și așteptările lui au consumat cicluri fără schimbarea aplicației:

- `146749d`: audit fanout produs de observer, remediat cu `sys.monitoring`; schimbare test-only.
- `cddb3ba` → `c1348ce` → `4efc56e`/`7a2ac5a`: SEND diagnostic, reason public/intern, închiderea canalului înainte de readeri offline și clasificare SDK; schimbări test-only, urmate de probe nativ/HTTP controlat, nu provider live.
- `3de38bc`, `66dec1b`, `09816ce`, `771ae3a`: defecte de produs reale, distincte de overheadul QA.

Canonicalul include componentele API/web/CLI/runtime, dar consumerii nativi și installed Start/Stop au opt-in/ținte separate (`Makefile:19–24,90–106,159–164,286,302–315`). Un canonical istoric nu acoperă automat HEAD și nici parcursul instalat complet. Nu recomand slăbirea lui sau refactorizarea acum a întregului harness.

**Dispoziție:** o cerință observabilă, un consumer, un reproducer; teste afectate și review pe snapshot, apoi parcursul real. După două cicluri numai QA fără avans, decizie asupra frontierei, nu un observer nou. Regula există deja; încă un skill care o repetă nu rezolvă problema.

## 3. Ce s-a întâmplat concret cu blocajele recente

| Problemă | Mecanism/evidență | Stare la snapshot |
|---|---|---|
| Idle channel | Hostul trata repausul ownerului ca timeout de frame și emitea refuz nesolicitat; mecanism separat demonstrat | Fix `3de38bc` prezent. Nu explică toate vechile exituri |
| Startup | Proba istorică `handshake-second-test.json` observă timeout la 4,502s și READY la 7,564s, înainte de RPC/model | Startup10/lease11 implementate; provision instalat înregistrat. Nu propun repetarea fixului |
| Restart owner | Quiesce-ul istoric închidea ireversibil ownerul nou; GET AVAILABLE nu observa latch-ul, click refuza | Fix `771ae3a` prezent, review/SOURCE și instalare/restart înregistrate. Primul model start pe fix NOT_RUN |
| Outcome public | failed/incomplete/completed sunt proiectate identic ca COMPLETE | Defect actual reprodus SOURCE, deschis |

Surse: `p4a-minim.md:9–29`, `supervisor/__main__.py:122–131,169–175`, `model_test_operation.py:160–161`. Stările instalațiilor sunt observații istorice, nu verificate live în acest audit.

**Concluzie cauzală:** a schimba doar credentialul/providerul în același traseu nu ar fi reparat idle timeoutul, startupul sau latch-ul. A continua să reparăm doar aceste incidente nu repară, la rândul său, secvențierea și cuplarea arhitecturală.

## 4. Volum verificat, fără procente inventate

Interval first-parent exact `37a56d82a544d0b2d223e433400fc489fc1f8c72..10cb5b96d358d67dbf2e430888173c75e6454f0b`, 7–20 octombrie: **666 commituri**. Partiție exclusivă, precedență produs propriu → native → documente-only → test/QA → rest:

| Categorie | Commituri |
|---|---:|
| Ating produsul propriu | 175 |
| Native/pin/patch fără produs propriu | 19 |
| Exclusiv documente/evidence/proceduri | 326 |
| Teste/QA fără cele două categorii de produs | 135 |
| Packaging/tooling/rest | 11 |

Classifier după căi: scripturile din documents sunt QA; apoi `documents`, `.hermes` și Markdown sunt documente; test files/fixtures/runneri sunt clasificate înaintea produsului. Produsul rămas: `api/src`, `cli/src`, `web/src`, `integrations/hermes/src`, `skills/profiles/contracts`; native: `integrations/hermes/upstream` și `integrations/hermes/runtime-override`. Numărat programatic și refăcut de părinte. Inventarul separat de la snapshotul auditat are **1.002 fișiere urmărite în `documents/verification`**, înaintea acestui raport. Datele nu măsoară timp, bani, productivitate sau inutilitatea fiecărui commit. Istoria P2 măsurată începe pe 7 octombrie; durata totală resimțită de operator include și lucrul anterior.

## 5. Alternative și alegerea recomandată

| Opțiune | Ce rezolvă | Ce rămâne / verdict |
|---|---|---|
| Continuăm exact ruta Codex actuală | Poate fi cea mai mică muncă pentru primul răspuns, dacă fixul recent funcționează | Cere auth/acord și probă reală; păstrează cuplarea. Nu demonstrez că este inutilizabilă, dar nu o recomand drept strategie neschimbată |
| Hermes subțire + API key | Reutilizează un loop matur, skills și provider routing | Necesită probarea frontierelor normale fără modurile speciale; nu este un simplu switch. Alternativă legitimă, costul comparativ nu a fost măsurat |
| **Runtime Omnis simplu + SDK OpenAI-compatible** | Ownerul existent deține bucla bounded și trimiterile; elimină dependența de gateway/constructori nativi pentru noul traseu | **Direcția recomandată**, condiționată de acceptarea consumerului complet, nu un rewrite total. Tool loop/context/recovery nu vin gratis cu SDK-ul |
| Rescriem DB/UI/CLI sau integrăm simultan alt framework complet | Rupe multe dependențe prin înlocuire masivă | **Respins:** abandonează fundația utilă, introduce migrare/risc și reîncepe ciclul |

OpenRouter documentează utilizarea SDK-ului OpenAI cu base URL propriu; OrcaRouter documentează același model de integrare, inclusiv async/tool calling. Acestea justifică fezabilitatea interfeței, nu certifică funcționarea modelului ales sau securitatea/retention/fiabilitatea providerului.[5][14]

**Început concret propus:** `model_test_operation.handle/run` devine o operație finită sub ownerul existent, fără AIAgent/catalog. Păstrăm contractul durabil corect, corectăm proiecția, introducem un singur provider API-key explicit. API-ul are acum `openai==2.24.0` numai în dev dependencies (`api/pyproject.toml:25–38`), deci distribuția senderului trebuie modificată explicit. Nu presupunem că un import disponibil în teste este instalat în produs.

**Cost concret care nu trebuie ascuns:** nu este suficientă editarea `handle/run`. `supervisor/__main__.py:111–141` montează ownerul numai cu catalog/runtime; `policy/model_dispatch_contract.py:23,114–126` acceptă numai `managed-run` și cere selection. Sunt necesare identitatea legitimă a operației de sistem, montarea și drain-ul ownerului fără acea dependență, plus păstrarea veto-ului înainte de send, lifeline/deadline/abort din senderul retras (`turn_api_request.py:221–259,284–299`). `hermes=False`, SENT sau cancel/join singure nu furnizează aceste garanții. API-key păstrează caps numerice; excepția de output monitorizat a subscripției nu se transferă. Limite tehnice nu sunt plafon financiar garantat.

**Această primă felie nu este destinația.** După transport, aceeași direcție trebuie să livreze bucla model/tool și assessmentul de mai jos. Nu încheiem proiectul cu un smoke SDK și nu menținem două motoare care controlează același run. Retragerea runtime-ului Hermes din noua distribuție urmează numai după înlocuirea callerilor și a probelor relevante. Datele și readerii istorici rămân; nu convertim un UNKNOWN vechi în retry.

### Ce păstrăm, ce amânăm

- **Păstrăm:** FastAPI, React/designul acceptat, PostgreSQL/migrațiile/datele, pairing, owner unic, task/attempt IDs utile, control/Stop, bugete și UNKNOWN, code de parser/skills utilizabil și metodologie cu provenance. Nu reutilizăm orice abstracție doar fiindcă există.
- **Scoatem din calea critică:** obligativitatea Hermes, catalog/PURE pentru connectivity, noi variante CONTRACT, batch/multiagent general și compatibilități care nu sunt consumate de prima investigație.
- **Simplificăm prima execuție:** un investigator, apoi validator/context separat, serial; tools tipizate, registru static, istoric/context bounded. Fără general-purpose plugin bus sau orchestrator nou. Context prea mare devine limită explicită până există compresie probată.
- **Amânăm, nu negăm viziunea:** editor avansat, maintenance/auto-improvement, research, Jev, attack paths, provider secundar și concurrency sofisticată. Browserul și breadth Web/API rămân milestone următor, nu sunt scoase tacit din produs.
- **Skills nu cer procesul Hermes:** metodologia versionată poate fi încărcată de Omnis. Learning înseamnă propunere → eval pe cazuri vulnerabile și sigure → review/publicare pentru runuri viitoare, nu rescriere autonomă a toolurilor/politicii în timpul engagementului.

## 6. Traseul minim către un produs util

Acestea sunt **rezultate propuse pentru amendarea ordinii canonice**, nu autorizație să începem P3 în sesiunea de audit.

1. **Model funcțional în Omnis:** config/secret de produs → test explicit → răspuns sau eroare corect clasificată → reload fără resend. Un provider/model, fără catalog/target. Buget/Stop/date aprobate rămân. Acesta verifică numai providerul.
2. **HTTP/evidence prin produs, independent de model:** un request către laborator autorizat, cu captură durabilă și inspector; request off-scope/redirect interzis refuzate la sink; Stop și restart fără efect nou. HTTPX trusted poate fi singurul sender al feliei API-first dacă DNS/IP/redirect/secret injection/caps sunt enforced, inclusiv adresa efectiv conectată, Host/SNI și fencing la fiecare request pe conexiuni reutilizate; nu necesită automat MITM pentru propriul client. Modelul nu primește socket/terminal direct. Provider egress rămâne separat; forwarderul TLS actual nu devine broker target prin adăugarea unor domenii. MITM și izolarea pentru browser/scannere se probează separat înaintea acelor consumatori.
3. **Buclă utilă de investigare:** URL și contexte autorizate → descoperire prin uneltele produsului → ipoteză → probe bounded → candidat/evidence/gap. Endpointul vulnerabil nu este oferit agentului ca soluție. Modelul primește tool results, își adaptează următorul pas și are limite de cost/pași/stagnare; nu doar un script fix botezat agent.[6]
4. **Primul finding BOLA/IDOR:** două identități/regula business, replay într-un context separat, owner legitim/shared/fixed/benign controale. CONFIRMED numai din probe; 200/LLM confidence/MethodCheck COMPLETE nu sunt verdict. Auth invalid → INCONCLUSIVE, nu „securizat”.
5. **Raport și retest utilizabile:** findings/evidence reale în web, HTML/JSON descărcat din snapshot coerent; retest cu probe noi produce FIXED/REGRESSED/INCONCLUSIVE, raportul vechi rămâne. Aceasta este prima versiune API utilă, nu paritate competitivă.

Punctul2 poate avansa fără live model după aprobarea amendamentului: un broker determinist nu are nevoie de constructor AIAgent. Primul E2E trebuie să folosească aceeași cale de produs, nu un script extern ale cărui rezultate sunt injectate ca descoperiri. Un corpus held-out și o aplicație sigură/remediată sunt necesare pentru eficacitate; repetarea unui singur laborator dovedește integrarea, nu performanță generală.

## 7. Relația cu Xbow, BugBunny, Cantina, ARMADA și Strix

Aceste nume sunt referințe funcționale, nu dovezi că trebuie copiată arhitectura lor internă. Sursele oficiale sunt materiale ale vendorilor, nu benchmark independent:

- XBOW descrie setup/scope/auth, requests/responses inspectabile și findings cu proof of concept reproductibil.[8]
- BugBunny prezintă scope/exclusions/context reutilizate și lucru de securitate cu intervenție umană pentru decizii importante.[9]
- Cantina pune accent pe trecerea de la discovery la validare/remediere/verificare, cu memorie și autonomie controlată.[10]
- ARMADA de la Arcanum descrie recon → mine → test → triage → **operator care re-testează**; nu doar agenți care votează între ei. Identificarea ARMADA este o presupunere explicită pe baza referinței utilizatorului.[13]
- Strix are sursă inspectabilă: la `a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c`, manifestul declară OpenAI Agents SDK + OpenAI + LiteLLM; `factory.py` creează SandboxAgent, iar `execution.py` folosește Runner și coordonare de produs. Nu este doar `client.create()`.[16][18][20]

Ce merită urmărit: descoperire, context partajat relevant, metodologie, probe, verificare independentă și feedback asupra următoarei acțiuni. **Nu câți agenți pornesc, câte skills sunt listate sau câte receipturi sunt produse.**

Reuse fără orbire: păstrăm studiile/importurile Omnis existente; pentru completări, Strix prompt/skill selection (`strix/agents/prompt.py`) și componentele de raport/evidence deja inventariate în stack §10 sunt candidați, nu un nou import de orchestrator complet. Sursa consultată este Apache-2.0; orice preluare cere pin/notices/modificări atribuite și teste proprii. Nu se importă prompturi de „full authorization” ca autoritate sau tooluri shell/libertăți care ocolesc brokerul.[19][21]

## 8. Amendamente exacte și condiții de tranziție

Dacă direcția este aprobată, se schimbă **același baseline**, nu se creează plan paralel:

- Arhitectură §2 A04/A14 și §5: Hermes din obligație tehnologică în adaptor opțional/legacy; un singur owner de run/efecte, contracte independente de native session IDs. Metadata nativă rămâne specifică adaptorului, nu falsificată pentru SDK.
- Arhitectură §5.2/§9.7 și plan §8: SETTINGS_TEST de sistem, fără catalog/child/Mission. Budget/DATA/Stop/persistență rămân.
- Plan §4/§7–9: conservă P2-inert la scope-ul său; introduce HTTP/evidence determinist înainte de dependența de live agent; agent tracerul vine după ambele.
- Arhitectură §2 **A05** și §3, stack §6 și plan B01e/B07: permite adaptor HTTP trusted fără MITM numai cu frontieră unică/probe la sink; browserul/scannerele păstrează cerințele lor înainte de activare. A05 cere astăzi proxy L7 pentru fiecare request, deci excepția trebuie amendată explicit, nu aplicată ca bypass.
- Plan §2/§4.3/§12–15: definește release-ul API util distinct de platforma competitivă extinsă; Jev și celelalte direcții aprobate anterior sunt resequențiate explicit, nu șterse tacit.
- UI §3/§4/§8: config reală provider/model, rezultate/erori truthful, Setup mic dar complet pentru autorizație/scope/identități/buget; păstrează designul și accesibilitatea.

Propagare de implementare ulterioară: Settings/models/routes + `model_test_operation` + ledger/supervisor; sender/egress/config/distribuție; OpenAPI/generated TS/client/ProviderSettings/ModelTest; teste SOURCE/unit și consumer instalat. `native_tasks`, `runtime_client`, `case_slot`, CLI/start/runtime și images sunt atinse numai unde noul consumer elimină o dependență. Nu șterge preventiv migrațiile/catalogul/readerii.

**Tranziție sigură:** release și resurse noi explicit deținute; instalațiile existente rămân intacte. Nu există migrare automată a tokenurilor OAuth în API keys. Citirea datelor istorice nu execută din nou requesturi. Dezafectarea codului nativ vine după dovada substituției, fără două controllere active pe același run. Orice rollback cu schimbare DB cere compatibilitate/backup-restaurare explicită; Git singur nu restaurează datele.

**Criteriul care schimbă decizia:** aceeași cale produs model→tool→evidence→validator și Stop trebuie să funcționeze cu mai puține dependențe, fără încă o familie de hooks/oracole. Dacă înlocuirea cere un nou framework de orchestration înainte de acel rezultat, propunerea a deviat și trebuie restrânsă. Nu declar din analiza statică un cost sau un termen de migrare garantat.

## 9. Ce nu schimbă auditul

Nu elimină validarea inputului, autorizația/scope, izolarea efectelor, protecția secretelor, evidența, bugetele, Stop, reviewul independent sau probele pe consumerul real. Nu promite zero false positives, exact-once pe rețea sau anularea calculului remote după send. Nu este aprobare de implementare, primul provider call sau primul assessment.

**Livrabil:** diagnostic verificabil și alegere recomandată. **Risc rămas:** recomandarea SDK-first este justificată arhitectural, dar integrarea alternativă și eficacitatea pentestului nu au fost executate; datele de status ale instalațiilor sunt istorice.

### Review adversarial și adjudecare

Un al patrulea reviewer a examinat argumentul la SHA256 `eb5d3b85ff551c34dcf09430d1042eb3193aa1a62d2662c639fa65c83578958d`: **APPROVED_SCOPED pentru argumentul condiționat**, nu runtime sau migrare. Raport original: `/home/kali/.hermes/cache/scratch/omnis-audit-10cb5b9-20261020/challenge.md`, SHA256 `d6c393aacf37e620216921aa15e8f66f85e1b94f04048c13979c323f4d5a2424`, citit integral de părinte.

- C1 economic: păstrat deschis ca limită; nu există măsurare că SDK minimizează întregul efort. Contraopțiunea puternică este un investigator Hermes normal cu tools Omnis înguste, nu încă un mod special. Nici aceasta nu este un switch deja integrat.
- C2 migrare: call-site-urile owner/managed-run și barierele fizice au fost verificate de părinte și explicitate mai sus; nu sunt ascunse în `handle/run`.
- C3 A05: omisiunea editorială din lista amendamentelor a fost corectată; baseline-ul nu a fost modificat.
- C4 istorie/proiecție: confirmate; defectul actual rămâne deschis, remedierile istorice nu se relansează automat.
- C5 viziune: păstrată distincția între release-ul API util și produsul competitiv; nicio renunțare tacită la browser/Jev/breadth.

Clarificările editoriale de mai sus sunt adjudecarea părintelui după review, nu o revendicare de review byte-exact asupra unei implementări noi. Nu cer un al cincilea audit pentru a recertifica această notă. Pe baseline-ul normativ nemodificat: `python -B scripts/render_docs.py --check` **exit0**, `python -B -m unittest discover -s tests/documentation -v` **75 PASS/exit0**. Citările externe au trecut verificarea de mapping; modul strict a refuzat numai sursele cercetate dar necitate, păstrate în ledger (nu URL-uri inexistente în text). Aceste verificări nu validează semantic arhitectura sau produsul.

## Sources

[2] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime
[5] https://openrouter.ai/docs/guides/community/openai-sdk
[6] https://openrouter.ai/docs/guides/features/tool-calling
[8] https://xbow.com/videos/xbow-run-autonomous-penetration-test
[9] https://bugbunny.ai
[10] https://www.cantina.security
[13] https://arcanum-sec.com/armada
[14] https://docs.orcarouter.ai/compatibility/openai-sdk
[16] https://raw.githubusercontent.com/usestrix/strix/a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c/strix/agents/factory.py
[18] https://raw.githubusercontent.com/usestrix/strix/a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c/pyproject.toml
[19] https://raw.githubusercontent.com/usestrix/strix/a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c/LICENSE
[20] https://raw.githubusercontent.com/usestrix/strix/a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c/strix/core/execution.py
[21] https://raw.githubusercontent.com/usestrix/strix/a0f8ea2cd379c4bf56e665d3db2ba8a4f7c0683c/strix/agents/prompt.py
