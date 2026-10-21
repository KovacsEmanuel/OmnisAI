**1. Verdict și design recomandat**

Migrarea este justificată, dar nu este o înlocuire de client HTTP. La baza exactă `39ab04f13d66fcba9a4cadb02338fb9fae9fa3e8`, Settings, testul modelului, ownerul operației, contractul dispatchului și distribuția instalată depind de traseul Hermes/Codex. Schimbarea dropdownului sau folosirea `hermes=False` nu elimină aceste dependențe.

Recomand **OpenAI Agents SDK ca unică bibliotecă pentru bucla agent/model/tool**, executată sub supervisorul Omnis existent. Pachetul este `openai-agents`, importat prin `agents`; pachetul `openai` furnizează clientul API și nu înlocuiește biblioteca de agenți. Omnis păstrează engagementul, identitățile operațiilor, politica, autorizarea efectelor, ledgerul, evidence și Stop.

Separarea recomandată:

- **Supervisorul Omnis** admite și urmărește operația, deține lease/epoch/generation, taskul activ și închiderea.
- **Agents SDK** conduce strategia: interpretează obiectivul, solicită tooluri și continuă pe baza rezultatelor.
- **Dispatchul Omnis** aprobă fiecare apel de model, verifică DATA, rezervă bugetul și persistă trimiterea.
- **Transportul Omnis** aplică veto-ul final, credentialul conexiunii, endpointul, deadline-ul și anularea.
- **Toolurile Omnis** validează argumentele și autorizația înaintea oricărui efect; modelul nu primește terminal, socket sau acces DB.

Nu recomand un al doilea framework, importarea orchestratorului Strix sau menținerea Hermes drept motor alternativ pentru runurile noi. Documentația SDK permite modele concrete per agent și provider per run, suficiente pentru mixul cerut. Aceasta justifică fezabilitatea selecției per rol, nu compatibilitatea fiecărui model. [Modele și provideri](https://openai.github.io/openai-agents-python/models/)

Baseline-ul trebuie amendat în aceleași documente: arhitectură A04/A14, §3–5 și contractele model/DATA, planul P4a/P2-live și ordinea brokerului, stackul și UI Settings. Auditul din 20 octombrie este un indiciu util, dar recomandarea sa de SDK simplu trebuie actualizată la decizia actuală: bibliotecă de agenți, fără runtime Hermes și fără subscription/OAuth în produs.

Analiza de mai jos este statică. Nu certifică funcționarea SDK, providerilor sau distribuției.

**2. Matricea frontierelor și ordinea schimbărilor**

În tabel, `A` înseamnă `api/src/omnis/`, `C` înseamnă `cli/src/omnis_cli/`, `W` înseamnă `web/src/`, iar `H` înseamnă `integrations/hermes/`. Aceste abrevieri identifică exact rădăcinile; **toate căile marcate NEW_PROPOSED sunt propuneri, inexistente la baza analizată**. Ordinea O1–O6 reprezintă dependențe de migrare, nu un plan concurent.

| Ordine | Path / simbol / consumer real | Dispoziție și motiv | Schimbări inseparabile |
|---|---|---|---|
| O1 | `W/features/engagement/ProviderSettings.tsx`, `W/shared/api/providers.ts::requestedSelection/decodeProvider` | **REPLACE** fluxul Codex/device-login cu conexiuni API-key, încărcare modele, default și override per rol. | `ProviderSettings.test.tsx`, clientul HTTP, DTO/OpenAPI; păstrarea focusului, recovery și absenței retry-ului automat. |
| O1 | `A/modules/settings/provider_models.py::ProviderSelection/ProviderCommand/ProviderView/OAuthChallenge` | **REPLACE** contractele limitate la `openai-codex/gpt-6.1-sol/xhigh`. OAuthChallenge este **RETIRE** pentru produsul nou. | Identitate/revizie conexiune, credential prezent fără valoare publică, stare discovery/test distinctă, referințe per rol. |
| O1 | `A/modules/settings/provider_routes.py::configure/operation/settings_exchange` → `LocalControl.settings` | **MODIFY**; păstrează autentificarea și transportul local tipizat, înlocuiește delegarea către managementul Hermes. | Dimensiuni cadre, erori sanitizate, CSRF/origin, operation IDs și citire după răspuns pierdut. |
| O1 | **Propuse:** `A/modules/settings/provider_connections.py`, `A/security/secret_store.py` | **NEW_PROPOSED** pentru configurație versionată și credentiale separate per conexiune. Nu există un secret store generic implementat în sursa examinată. | Persistență DB non-secretă, stocaj privat explicit, scriere atomică/readback, înlocuire/revocare cu Stop. |
| O1 | **Propusă:** `A/migrations/versions/0014_provider_connections.py`; existente `core/db.py::SCHEMA_REVISION`, `core/managed_schema.py`, `core/schema.py` | **NEW_PROPOSED / MODIFY** aditiv; fără rescrierea migrațiilor 0001–0013. | Readiness, schema exactă, teste migrare și toate pinurile de schemă din CLI/bundle. |
| O2 | `A/supervisor/__main__.py::run` | **MODIFY**. Astăzi montează `NativeTaskOwner` numai cu catalog și runtime, iar Settings numai cu runtime. | Montarea noului executor fără aceste condiții; ordinea quiesce/start, heartbeat, drain și shutdown. |
| O2 | `A/supervisor/native_tasks.py::NativeTaskOwner.model_test/close_model_test` | **REPLACE** responsabilitatea pentru operațiile noi, păstrând controlul în același supervisor. Restul execuției native devine **RETIRE** după substituție. | **Propus:** `A/supervisor/agent_execution.py`; un singur owner și registru de taskuri active, fără controller paralel. |
| O2 | `A/modules/instance/service.py::native_preparation_commit/runtime_authority`, `transport/local_control.py`, `instance/schemas.py` | **MODIFY** frontiera de admitere. `runtime_authority` autentifică inclusiv contexte v5/v6 native; nu este deja grant SDK. | Comenzi tipizate pentru operații noi, aceleași bariere owner/lease/Stop, callback de drain, teste supervisor/Stop. |
| O2 | `A/modules/runs/model_test_routes.py::start_model_test/read_model_test`, `model_test_models.py` | **MODIFY** pentru conexiunea/modelul fixat și rezultat fidel; **RETIRE** `provision/selection_ref` din conectivitatea nouă. | OpenAPI, decoderul web, consent, limits, operații repetabile explicit cu identități noi. |
| O2 | `A/modules/runs/model_test_operation.py::handle/run/view/projection` | **REPLACE** traseul `NativeTaskCommand`/catalog/runtime cu operație de sistem finită. Păstrează idempotency și readback. | Corectarea pierderii statusului providerului; teste `test_model_test_operation.py`, routes și web. |
| O2 | `A/modules/runs/model_test.py::ModelTest.reserve_execution/execution_packet/execution_receipt` | **KEEP** readerul calificat al testelor native istorice; **REPLACE** producerul pentru apelurile noi. | Nu schimba sensul înregistrărilor v6 și nu transforma output existent în succes nou. |
| O2 | `A/policy/model_dispatch_contract.py::scope_ref/validate_request`, `budgets.py::create_budget/reserve/reduce_history/mark_sent/settle` | **MODIFY** pentru scope de operație de sistem și execuție SDK. Acum scope-ul admis este numai `managed-run`; selection este obligatorie. | Producerul scope-ului, rezolvarea referințelor în `_resolved/_budget`, versiunea dispatchului și replay-ul istoric trebuie schimbate împreună. |
| O2 | `A/modules/runs/model_dispatch.py::ModelDispatch`, `model_protocol.py` | **KEEP** contractele istorice NO_MODEL; **MODIFY** frontiera comună de dispatch. `model_protocol.reserve(...hermes=False)` rămâne probă sintetică, dependentă de `FrozenPreflight`. | Noul sender nu poate adopta descriptorul NO_MODEL ca autoritate live. |
| O2–O3 | `A/policy/model_context.py::derive_model_context`, `model_configuration.py`, `ready_model_configuration.py` | **KEEP** validarea veche; **REPLACE** derivarea contextului nou. Contextul actual impune CONTRACT_PROBE/SUPPORT/NO_MODEL și identificatori nativi. | Snapshot conexiune/model/rol, capabilități și parametri acceptați, fără inventarea unei inițializări native. |
| O2–O3 | `A/modules/runs/model_projection.py::ModelProjections`, `A/policy/model_projection.py::SyntheticApproval/projection_input` | **KEEP** politica sintetică istorică; **MODIFY** prin contract nou pentru inputul SDK. Producerul actual cere manifest/binding/composition și catalog. | Clasificare DATA pentru instrucțiuni, tool schemas și rezultate; digest pe inputul efectiv, nu doar pe prompt. |
| O2–O3 | **Propuse:** `A/modules/runs/agent_models.py`, `agent_runner.py`, `provider_transport.py` | **NEW_PROPOSED**: DTO/records pentru noul traseu, adaptor unic Agents SDK și transport controlat. | Fiecare apel intern al Runnerului trece prin dispatch; rezultate și erori persistate cu proveniență SDK explicită. |
| O3 | **Propus:** `A/modules/tasks/agent_tools.py`; existent `tasks/module_registry.py` | **NEW_PROPOSED / KEEP**. Registru îngust de tooluri tipizate, fără adoptarea automată a handlerelor CONTRACT ca tools live. | Validare argumente, grant per invocare, limite, receipt și persistență înainte de retur către agent. |
| O3 | `A/modules/tasks/managed_store.py`, `managed_contract.py`, `managed_admission.py::_verify_graph/readback` | **KEEP / MODIFY** numai pentru acces explicit versionat. Store-ul de înregistrări poate fi reutilizat; lifecycle-ul nativ nu este universal. | Nu trimite noul graf SDK prin validatorul care cere runtime-binding/native-final; păstrează verificarea vechilor grafuri. |
| O3–O4 | `tasks/method_checks.py::check_execution`, `method_checker_identity.py::descriptor/verify`, `result_qualification.py`, `criterion_checks.py`, `mission_revisions.py` | **KEEP** pentru istoricul calificat. **MODIFY** numai cu un producer nou și semantică explicită. | Closure-ul checkerului este hash-uit; editarea fișierelor din `SOURCES` afectează identitatea, nu doar importurile. Teste istorice obligatorii. |
| O4 | `A/supervisor/runtime_client.py::RuntimeClient/FrozenPreflight`, `case_slot.py::CaseSlot`, `runs/native_preparation.py` | **RETIRE** din noua execuție; **KEEP** codul necesar interpretării/jurnalelor istorice până la probarea independenței. | SDK nu folosește boot/ticket/session Hermes; arhivele native nu sunt mutate sau adoptate automat. |
| O4 | `A/modules/runs/model_test_source.py::provision/verify_shipped`, `C/model_test_source.py::SOURCE_FILES` | **RETIRE** din conectivitatea nouă. Acum cer package/profile/Publish/preparation/restart. | `profiles/records-mapping-contract.yaml`, pachetul din `skills/records-mapping-contract/` și fixtures rămân citibile ca date istorice. |
| O4 | `H/src/omnis_hermes/runtime_host.py`, `runtime_protocol.py`, `management_server.py`, `management_http.py`, `management_auth.py`, `management_oauth.py` | **RETIRE** ca execuție/dependență a noului produs. | Eliminarea management REST, device flow, stării Codex și proceselor auxiliare numai din artefactul nou. |
| O4 | `H/src/omnis_hermes/{managed_admission_contract,native_preparation_contract,prompt_bundle,contract_method,model_context,model_configuration,model_projection,model_admission,model_request,model_terminal}.py` | **RETIRE** producerii/runtime; **KEEP** subsetul pur necesar readerilor sau fixture-urilor istorice, cu proveniență. | Închide dependențele tranzitive înainte de scoaterea wheelului; nu șterge întreg directorul după nume. |
| O4 | `H/upstream/managed-source/agent/` și `run_agent.py` | **RETIRE** patchurile de constructor, turn, RPC, loop, auxiliary, request și subagent lifecycle din buildul nou. | Call-site-urile `omnis_hermes` sunt reale aici; API-ul comunică în principal prin protocol, nu prin import direct. |
| O5 | `C/start.py`, `start_runtime.py::ControlRuntime/settings_overlay`, `compose.py::ImageReceipt/install_control_image`, `release.py::_manifest` | **MODIFY** pentru artefact explicit fără runtime Hermes. | Roluri servicii, mounturi, env, attestations, receipts, instalare/restart/Stop și compatibilitate cu manifestele vechi. |
| O5 | `C/forwarder.py::start_forwarder/start_auth_forwarder` | **KEEP** forwarderul browser→API; **RETIRE** traseul OAuth/Codex din noul profil. | Egress provider nou, finit și legat de Stop; relay-ul TLS actual nu devine broker de target. |
| O5 | `C/native_artifacts.py::closure/stage_context`, `ops/prepare_hermes_runtime.py`, `ops/Dockerfile.hermes` | **RETIRE** din producerea releaseului nou; **KEEP** verificarea metadatelor necesară citirii pachetelor istorice. | `pin.json`, manifestele patch/source/build, licenses și notices nu dispar din arhivele deja produse. |
| O5 | `ops/build_control_bundle.py::build_bundle`, `Dockerfile.control`, `Dockerfile.control-model-test`, `compose.control.yaml` | **MODIFY / RETIRE** profilul control-model-test nativ; pachet nou fără sursa CONTRACT obligatorie. | Rețeaua control este internă; noul egress trebuie proiectat și probat, nu presupus disponibil. |
| O5 | `api/pyproject.toml`, `api/uv.lock`, `cli/pyproject.toml`, `cli/uv.lock`, `H/{pyproject.toml,runtime-override/pyproject.toml,upstream/pyproject.toml}` și lockurile asociate | **MODIFY / RETIRE** dependențele distribuției. `openai==2.24.0` este acum numai dev în API. | Pin verificat `openai-agents` și closure runtime; fără LiteLLM implicit, fără wheel/source Hermes în noul artefact. |
| O5–O6 | `contracts/omnis.openapi.json`, `W/shared/api/generated.ts`, `client.ts`, `modelTest.ts`, componentele Settings/ModelTest | **MODIFY** simultan cu API-ul. | Decoderele actuale verifică valori și număr exact de câmpuri; regenerarea tipurilor singură nu repară runtime decoderul. |
| O6 | `Makefile`, `ops/run_test_db_gate.py`, `api/tests`, `cli/tests`, `integrations/hermes/tests`, fixtures | **MODIFY** selecția verificărilor noului produs; **KEEP** regresiile istorice relevante. | Separă probele SDK de native-build/OAuth AST; nu elimina testele ledger/Stop/history odată cu transportul. |
| O1–O6 | `.hermes/skills/`, `scripts/hermes_dev.py`, `tools/development/` | **KEEP** ca instrumente de dezvoltare distincte. | Nu sunt catalog executabil de pentest și nu intră în contextul investigatorului sau evaluării. |

**3. Primul traseu complet, de la Settings la rezultat persistent**

Primul rezultat trebuie livrat prin consumatorii produsului, în două operații distincte: testul providerului și execuția agentului. Un răspuns la test nu certifică agentul.

**Conexiunea.** Operatorul adaugă în Settings o conexiune OpenRouter sau OrcaRouter. Backendul validează endpointul acceptat și păstrează separat configurația non-secretă și credentialul. Browserul primește numai identificator, revizie și starea credentialului. Încărcarea listei de modele este o operație explicită, bounded și anulabilă sub același owner. O listă returnată nu dovedește suportul pentru tools, reasoning sau output structurat.

Defaultul și maparea rol→conexiune/model se persistă. Identitatea selecției include conexiunea: două modele cu același nume, dar endpointuri sau chei diferite, nu sunt aceeași configurație. La admiterea operației se fixează reviziile; schimbarea defaultului nu modifică un run activ. Lipsa override-ului poate rezolva defaultul la admitere; eșecul unui provider nu autorizează fallback.

**Testul.** `start_model_test` admite o operație SETTINGS_TEST fără engagement, Mission, catalog CONTRACT, Publish sau restart. Producerii obligatorii sunt: operația idempotentă, snapshotul configurației, decizia DATA pentru textele sintetice, proiecția, descriptorul ownerului, bugetul numeric, rezervarea și dispatchul. `native_turn_ref` rămâne absent; nu se fabrică identificatori Hermes pentru satisfacerea validatorului.

După commitul `SENT`, transportul verifică din nou autoritatea înainte de bytes. Receiptul persistă providerul/routerul solicitat, modelul cerut și observat când este disponibil, statusul terminal, outputul și usage-ul cunoscut. GET/reload citește operația existentă fără resend. Defectul actual din `view/projection`, care promovează orice observație cu output la `COMPLETE`, trebuie eliminat: completed, incomplete, failed și UNKNOWN rămân distincte.

**Agentul.** După test, o operație separată pornește un agent SDK cu un singur tool tipizat. Pentru prima substituție a motorului recomand un tool determinist asupra unui artefact sintetic deținut de operație: primește o referință, citește datele aprobate și persistă un rezultat derivat. Nu cere catalog CONTRACT și nu execută trafic target.

Agentul solicită efectiv toolul; executorul Omnis validează argumentele și autoritatea, persistă receiptul/rezultatul și abia apoi îl întoarce SDK-ului. Continuarea modelului trece din nou prin DATA și dispatch. Rezultatul final și starea operației se persistă, iar reload/restart oferă readback fără reluarea efectelor. Acceptance-ul cere tool-call și folosirea rezultatului, nu doar un răspuns textual.

Pentru tool→răspuns final sunt necesare, în mod normal, mai multe apeluri de model; limita de un apel aparține testului providerului, nu întregului agent. `max_turns` nu înlocuiește ledgerul apelurilor.

Acest traseu certifică integrarea agent/tool/persistență. Primul request Web/API autorizat cere ulterior brokerul HTTP/evidence și gate-ul său. Biblioteca nu produce acea frontieră prin simpla înregistrare a unui tool.

**4. Safety care trebuie păstrat și ce nu oferă biblioteca**

Credentialele rămân per conexiune, accesibile numai transportului autorizat. Nu intră în prompt, SDK session, records publice, logs sau tracing. Stocajul propus trebuie să definească explicit permisiuni, scriere atomică, readback și recuperarea unei scrieri parțiale. Credentialul poate exista fără ca providerul să fi fost verificat. Revocarea sau înlocuirea în timpul execuției oprește mai întâi utilizările active.

DATA se aplică inputului efectiv după transformările adaptorului: instrucțiuni, istoric, descrieri și argumente de tools, rezultate și parametri suplimentari. `SyntheticApproval` actual clasifică texte exacte; nu este DLP general și nu poate aproba automat date target sau output arbitrar.

Bugetele rămân numerice pentru apeluri, input/context, output și deadline. Se păstrează rezerva validatorului și limitele agregate peste roluri și provideri. Excepția `MONITOR_SUBSCRIPTION` nu se transferă la API-key. Lipsa usage-ului nu înseamnă consum zero, iar capurile tehnice nu garantează un plafon financiar.

Ordinea durabilă rămâne **reserve → commit SENT → veto final → send → receipt/settlement**. Rezervarea neexpediată poate fi eliberată când dovada permite; după SENT, timeoutul, moartea ownerului sau anularea păstrează UNKNOWN fără refund ori retry implicit. Reducerul ledgerului trebuie să citească atât versiunea veche, cât și versiunea nouă, fără reinterpretarea istoricului.

Veto-ul trebuie să existe la transportul real, inclusiv pe conexiuni reutilizate. Senderul actual din `H/upstream/managed-source/agent/turn_api_request.py::run_model_test_request` verifică lifeline/deadline, requestul final și tentativa fizică, plus abort și close. Aceste garanții nu sunt înlocuite de un hook SDK anterior apelului.

Retry-urile trebuie dezactivate la toate nivelurile locale: client `openai`, transport HTTP, politicile Runnerului și orice recovery propriu. Fallbackul este o decizie nouă admisă și bugetată, niciodată continuare ascunsă.

Un **apel API Omnis către router** este diferit de tentativele upstream făcute de router. Omnis poate măsura și limita propriile trimiteri; nu poate deduce câte backenduri a încercat routerul. Configurația routing/fallback acceptată trebuie fixată, iar tentativele necunoscute rămân necunoscute. Nici modelul observat nu dovedește întreaga rută upstream.

Stop revocă admiterea și autoritatea, anulează Runnerul și toolurile active, închide streamurile și clienții, apoi verifică drainul bounded. Cancel/join fără închiderea transportului este insuficient. Închiderea conexiunii locale nu garantează oprirea calculului remote deja admis.

Tracingul extern trebuie oprit înaintea primei execuții, inclusiv prin configurația procesului; dezactivarea tardivă nu șterge date deja bufferizate. [Tracing SDK](https://openai.github.io/openai-agents-python/tracing/)

Agents SDK furnizează bucla și reprezentarea agent/tool. Nu furnizează autorizația engagementului, policy enforcement la sink, seiful Omnis, evidence autentică, exactly-once pe rețea sau Stop-ul distribuit. Guardrails și instrucțiunile modelului nu înlocuiesc aceste mecanisme. [Agenți](https://openai.github.io/openai-agents-python/agents/), [orchestrare](https://openai.github.io/openai-agents-python/multi_agent/)

**5. Compatibilitate, date și retragerea Hermes**

Distribuția nouă trebuie să aibă identitate și manifest proprii, instalate explicit. Nu se șterg, adoptă sau migrează automat `.omnis`, profiluri, volume, arhive ori granturi OAuth existente. OAuth nu este convertit în API-key. O instalație veche nu primește noul motor printr-un Start implicit.

Schema 0011 leagă `managed_run` de binding/runtime_boot/ticket/native_root, iar `managed_task` are identități native și constrângeri finite. Prin urmare, nu recomand umplerea acestor câmpuri cu UUID-uri SDK inventate. Noile operații folosesc records și stare explicită, aditive, cu propriul discriminator de executor; primitivele de integritate și ledger se reutilizează după adaptarea scope-ului.

Schimbarea schemei afectează și `C/start.py::EXPECTED_SCHEMA`, `C/release.py::_SCHEMA`, validarea din `C/instance.py` și manifestul produs de `ops/build_control_bundle.py`. Compatibilitatea DB nu se rezolvă numai prin adăugarea unui fișier Alembic. Upgradeul unui profil existent cere separat backup/restaurare și compatibilitate probate.

Citirea istorică păstrează envelopes, schemas, composer/checker identities, provenance, command receipts și UNKNOWN. `method_checker_identity.py` hash-uiește o closure de surse: mutarea sau simplificarea validatorilor poate modifica identitatea acceptată. Datele istorice trebuie probate prin readerul instalat, fără Host Hermes și fără reexecuție, nu numai prin fixtures regenerate cu producer nou.

**Condiția exactă pentru scoaterea finală a pachetelor runtime Hermes** este îndeplinită numai când:

1. Niciun caller de execuție nou — Settings, discovery, test, agent, tool, startup sau Stop — nu mai cere runtime-ul, protocolul sau credentialele Hermes/Codex.
2. Artefactul nou se construiește și funcționează fără `omnis-hermes`, source Hermes, runtime-override, patchuri native și imaginea Hermes.
3. Readerii datelor și metadatelor istorice funcționează fără importarea/instalarea runtime-ului; orice subset pur necesar este inclus explicit în closure-ul readerului, cu proveniență.
4. Testele relevante de readback istoric, Stop/restart, UNKNOWN/no-resend și parcursul instalat al noului executor au dovezi pe bytes curenți.
5. Reviewul independent confirmă substituția în acest perimetru.

Fișierele istorice pot rămâne în Git sau arhive fără să fie dependențe runtime. `.hermes/skills/` rămâne pentru dezvoltare.

**6. Riscuri, decizii și gates — maximum opt**

1. **Compatibilitate SDK/router/model.** Alege pinurile prin probe Chat Completions/tool-calling/output/usage pentru fiecare conexiune admisă. Versiunile Strix furnizate de părinte — `openai-agents 0.19.0`, `openai 2.53.0`, `litellm 1.101.0` — sunt comparație, nu recomandare de pin. Reconsultarea mea a surselor Strix la SHA-ul indicat a eșuat cu „Cache miss”; nu pretind verificare independentă.

2. **Bypass la apelurile interne.** Gate-ul trebuie să dovedească faptul că fiecare apel Runner, continuare și rol traversează dispatchul Omnis. Un test de transport izolat nu certifică întregul agent.

3. **Stop și autoritate stale.** Sunt necesare controale negative la send, pierdere lease/DB, moarte owner, conexiune reutilizată și deadline, plus drain. Două reviewuri complementare sunt cerute de regulile proiectului pentru aceste frontiere.

4. **Secrete și DATA.** Gate-ul trebuie să acopere izolarea cheilor între conexiuni, non-expunerea în răspunsuri/loguri/context și oprirea tracingului. Seiful generic este muncă nouă, nu funcție păstrată deja implementată.

5. **Persistență și adevărul rezultatului.** Probe pentru completed/incomplete/failed/UNKNOWN, pierdere reply, restart și citire fără resend. Statusul testului providerului și verdictul unei investigații rămân separate.

6. **Compatibilitate istorică.** Gate de reader instalat asupra datelor vechi, cu schema și checkerul relevante; fără reexecutarea producerului și fără ștergerea validatoarelor pentru a simplifica buildul.

7. **Distribuție și egress.** Gate instalat din cwd extern: manifest, closure de wheels, schema, mounturi, servicii, egress finit și Stop/restart cu date păstrate. Rețeaua internă actuală și relay-ul OAuth nu asigură automat conectivitatea nouă.

8. **Limita primului rezultat.** Provider→agent→tool sintetic→persistență nu este pentest. G-MODEL/G-DATA și probele noului owner preced revendicarea integrării; G03/G-NET și gate-urile evidence/auth/validator preced traficul și findings. Canonicalul relevant se actualizează pentru noul produs, fără transfer de PASS din Hermes.

Comenzile Git de început și final au terminat cu exit `0`: branchul este `checkpoint/p2-batch2-pause-20261015`, HEAD este neschimbat, diffurile tracked/staged sunt goale. Singurul untracked rămâne `documents/Omnis_Notite_Originale.html`, necitit și nemodificat. Nu am editat sau comis nimic, nu am pornit agenți și nu am executat teste, DB, Docker, browser, servicii ori requesturi provider/target. Citirile statice nu sunt PASS runtime.

| Perimetru | Implementare | Dovezi | Review / pas următor |
|---|---|---|---|
| **AICI — analiza migrării** | Fără modificări | Sursă și Git verificate static | Părintele adjudecă raportul |
| Fundații P0/P1 | Existente | Acceptări istorice scoped | Se păstrează; fără recertificare |
| P2 inert și readeri | Existente, contracte native | Dovezi istorice distincte | Regresii pe frontierele schimbate |
| Noul Settings/API-key/SDK | Neimplementat | Runtime NOT_RUN | Amendarea baseline-ului, apoi felie verticală |
| HTTP/evidence/validator | Nelivrate în noul traseu | NOT_RUN | Gate-uri proprii înainte de efecte |
| Rest MVP/post-MVP | Neschimbat de audit | Fără promovare | Resequencing explicit în planul canonic |