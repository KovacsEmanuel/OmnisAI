# Omnis — analiza migrării API-key-only și primul pentest de laborator

## 0. Decizie, mandat și limită

**Bază analizată:** `39ab04f13d66fcba9a4cadb02338fb9fae9fa3e8`, branch `checkpoint/p2-batch2-pause-20261015`. Direcția aprobată în conversație: **fără Hermes runtime și fără Codex subscription/OAuth în noul produs; OpenRouter/OrcaRouter prin API keys; orchestrator AI, roluri și skills Omnis; un model implicit sau model-per-rol.** Folosirea Hermes/Codex pentru dezvoltare este separată și nu se elimină.

**Livrabilul autorizat acum este analiza exactă**, realizată cu analiști Sol 6.1 și review al propunerii. Documentul nu modifică singur arhitectura/planul, nu autorizează migrarea codului, instalarea unui SDK, folosirea cheilor sau primul pentest. Înlocuiește pentru discuția direcției alternativele încă deschise din [auditul anterior](p2-architecture-reset-audit-20261020.md), fără să rescrie constatările/probele acelui snapshot.

**Verdict:** păstrăm aplicația și domeniul utile, înlocuim integrarea runtime, nu construim un framework general de agenți. OpenAI Agents SDK este candidatul bibliotecii; `openai` este clientul, nu aceeași componentă. Retragerea executabilă a Hermes se încheie printr-un artefact nou care funcționează fără el, nu prin ștergerea preventivă a fișierelor.

**Două etape de produs:** (A) model→rol/task→unealtă→evidence→validator într-un pentest minor de laborator; (B) dezvoltarea aprofundată a harnessului, comenzilor, rolurilor, skills și eficacității. Etapa A are deja safety și adevăr probatoriu; etapa B le extinde, nu le introduce retroactiv.

## 1. Analize independente și adjudecare

Trei procese Codex CLI `0.163.0`, fiecare configurat explicit `gpt-6.1-sol`, effort `medium`, provider CLI `openai`, sandbox `read-only`, approval `never`, `--ignore-user-config`, `--ephemeral`, fără config global schimbat. Autentificarea CLI de dezvoltare a raportat `Logged in using ChatGPT`; aceasta nu este utilizare a subscripției în produsul Omnis. Catalogul bundled a declarat modelul și ambele eforturi medium/xhigh; bannerele reale și citirile de cod au fost observate. Toate trei au ieșit cu cod 0; părintele a citit rapoartele complete și a recontrolat sursele decisive.

| Analist | Sesiune / proces | Raport original | SHA256 |
|---|---|---|---|
| Migrare cod/distribuție | `01a15fe0-edca-71f3-9052-cdb2ae0d1369` / `proc_77c54a34a97c` | [Sol medium — migrare](api-key-migration-evidence/migration-sol-medium.md) | `4ffe9fae18468244539d87b8aae8e554782ad03244c40269bacb714df464165a` |
| Amendamente canonice | `01a15fe0-edf8-7190-84c0-92ba9b64f04f` / `proc_aa012681c404` | [Sol medium — baseline](api-key-migration-evidence/baseline-sol-medium.md) | `eef74154543b2192cf45f1c489242caa6bb75797481c1bca320960a308ad3c51` |
| Primul pentest/harness | `01a15fe0-efca-7c11-8f12-d34873227ab7` / `proc_12376fc6f040` | [Sol medium — harness](api-key-migration-evidence/harness-sol-medium.md) | `ab5ab10566ef28768f7d13407be88b14b169e4fefdf4c3ac55907e7749c7cb82` |

Rapoartele sunt constatări independente, nu autoritate de implementare. Diferențele importante sunt adjudecate astfel:

1. **Bibliotecă, nu client simplu și nu alt runtime complet.** Candidatul este `openai-agents` cu `openai`, utilizând API-uri publice. Nu importăm orchestratorul Strix. Nu adăugăm LiteLLM până când un consumer concret îl cere.
2. **Locul adaptorului:** alegem module înguste în codul API/supervisor deja distribuit, încărcate de procesul de execuție, nu un nou serviciu `integrations/agents_sdk` și nu în requestul FastAPI. Numele propuse sunt în §5. Separarea rețelelor/efectelor rămâne obligatorie; această alegere nu dă acces target procesului modelului.
3. **HTTP inițial:** analistul baseline propune păstrarea proxyului universal; ceilalți admit alternativa unui sender HTTP trusted. Recomandăm amendarea explicită A05 pentru primul executor API HTTPX unic, care vede L7 înainte de TLS și aplică policy. Nu este extinderea relay-ului TLS Codex și nu autorizează egress alternativ. Browser/scannere/shell nu moștenesc excepția; primesc transport și probe separate.
4. **Primul pentest minor este un milestone intermediar `M-LAB` PROPUS**, nu redenumirea M1/G05a/G06a. Analiștii au inclus întregul raport/retest M1 în prima probă. Restrângem M-LAB la investigația BOLA finită, replay/controale, rezultat structurat inspectabil și readback/Stop. Report review general, exporturile finale și retestul de produs rămân necesare pentru M1, imediat după proba utilă, nu înainte de primul experiment.
5. **Nu construim iar un motor metodologic înainte de efect.** Înghețăm breadth-ul CONTRACT; păstrăm identitatea, digesturile și cititorii. Metoda de laborator este un candidat first-party fixat/revizuit, evaluat în `PACKAGE_EVAL` pe laborator, nu obligatoriu o publicație de producție înaintea propriei evaluări. Editorul/compilerul general nu este prerequisite M-LAB.
6. **Model-per-rol este configurație aprobată, nu promisiune că toate combinațiile sunt testate.** Structura permite de la început conexiuni multiple; prima probă poate folosi un singur model și roluri/context distincte. Acceptarea ambilor routeri și a unui run mixt are probe separate, fără a condiționa primul rezultat de toate combinațiile posibile.
7. **Nu construim un verifier semantic al statusurilor.** Corectăm un singur CURRENT și păstrăm câteva verificări structurale relevante. Recomandările din rapoarte de verificare automată a adevărului tuturor checkpointurilor nu devin alt proiect de harness.

## 2. Arhitectura propusă, cu responsabilități clare

```text
Web Omnis → API / comenzi durabile → supervisor Omnis (unic)
                                      ├─ operații Settings/test provider
                                      ├─ Agent/Runner SDK → model adapter → provider egress
                                      └─ tools Omnis → broker / executor HTTP → laborator
                                                            └─ evidence / validator / rezultat
PostgreSQL + artefacte + seif local: starea canonică, nu conversația modelului
```

AI orchestratorul interpretează obiectivul, propune taskuri, cere specialiști, citește rezultate și decide următorul pas. Codul Omnis deține autorizația, scope, identități, bugete, persistență, verdictul tehnic și Stop. Nu există un proces permanent per skill sau un agent pentru parsare/deduplicare/calcul de counters.

Prima configurație are orchestrator + un slot executant; rolul de investigator se încheie înainte de validatorul cu context/attempt/auth separat. Patternul manager/agents-as-tools este potrivit, dar invocarea specialistului trebuie să creeze un task/attempt legitim prin Omnis înainte de efect. IDs, rol și capabilități vin din contextul trusted al executorului, nu din JSON-ul modelului. Delegarea recursivă este indisponibilă inițial.

### Ce am verificat la biblioteca candidată

Părintele a inspectat sursa `openai/openai-agents-python` tag `v0.19.0`, commit `a2d82707d94bfcf2ffbcc62ea9746c5fb183804f`:

- `src/agents/models/interface.py`: interfețe publice `Model.get_response`, `stream_response`, `ModelProvider.get_model` și închidere;
- `src/agents/agent.py:550–579`: `Agent.as_tool` acceptă configurație/limită/hooks și întoarce rezultatul către manager, fără handoff implicit al întregii conversații;
- `src/agents/run_config.py:310–316,349–361,390–398`: provider/config pe run, tracing și filtru de input. Configurația globală a runului poate suprascrie setări de agent: trebuie probată precedența, nu presupusă;
- `src/agents/retry.py:162–172`: politici de retry ale Runnerului distincte de clientul HTTP.

Strix inspectat anterior la `a3c31236bd6305784a501a3102dab0bda83f2317` folosește în lock `openai-agents 0.19.0`, `openai 2.53.0`, `litellm 1.101.0`. **Acestea sunt ancore de analiză, nu dependențe admise Omnis.** O parte din fetchurile Strix ale analiștilor a eșuat; rapoartele nu pretind verificări care nu au avut loc. Pinul final necesită compatibilitate, licență, audit și probe pe ruta aleasă. API-ul actual Omnis declară `openai==2.24.0` numai în dev.

Un port `Model` poate lega dispatchul Omnis de fiecare apel al Runnerului; nu este singur dovada veto-ului fizic. Datele finale, retry-urile, clientul, conexiunile reutilizate și anularea se verifică și la transport. Dacă soluția cere din nou patchuri în constructor/loop sau falsificarea unor identități, se respinge acel adaptor înainte de extindere.

## 3. Contracte de produs care trebuie stabilite în canon

Aceste denumiri sunt **PROPUSE**, nu simboluri sau endpointuri deja existente. Structura rămâne minimă și este introdusă cu primul consumer.

| Contract propus | Producer / date necesare | Primul consumer și regula |
|---|---|---|
| ProviderConnectionRevision | Settings: ID/revizie, provider enum OpenRouter/OrcaRouter, endpoint fix allowlisted, credential ref/revizie, capabilities/routing și statusuri distincte | Catalog/test/agent; nici credential în DB publică/prompt/log, nici base URL arbitrar din tool args |
| ModelSelectionSnapshot | Backend: default explicit și role overrides, connection revision, model ID exact, parametri solicitați/admiși, capabilități verificate, data policy, bugete | Admiterea jobului/runului; fără default global SDK mutat în timpul execuției |
| AI operation / scope de sistem | Ownerul existent: ID, purpose, command/idempotency, payload digest, config snapshot, instance/generation/epoch, deadline și stare durabilă | SETTINGS_TEST fără engagement/Mission/catalog; `run_or_job_ref` rezolvă această autoritate reală, nu un managed-run fictiv |
| Runtime-neutral task attempt | Supervisor: run/task/attempt/rol, input/skill refs, capability set, budget, owner/fencing și versiune executor | Runner/tool callbacks/rezultat; IDs provider/SDK sunt metadata, nu autoritate nativă inventată |
| Model dispatch v2 | Ownerul: scope autentic, purpose, config/projection, rezervare, call ID, caps și fencing | Transport SDK; V1 istoric nu este reinterpretat, NO_MODEL nu devine grant |
| Model outcome | Senderul și persistența: requested/observed, completed/incomplete/failed/unknown, output bounded, usage/estimare/cost distincte | UI/readback/ledger; statusul operației nu șterge statusul providerului |
| Tool invocation / evidence | Broker: caller trusted, request semantic, persona/auth_epoch, scope/effect/caps, sent/terminal/unknown și artefacte | Investigator și validator; result text sau exit0 nu înlocuiesc dovada |

### Settings și model-per-rol

- **Save** este local și fără inferență; nu pretinde că cheia a fost verificată online.
- **Conectează / actualizează catalog** este o acțiune explicită bounded, cu readback și Cancel când suportat; nu testează toate modelele contra cost. Catalogul public nu certifică entitlementul cheii, tool calling sau parametrii.
- **Test model** este explicit, finit, input sintetic afișat, fără target/catalog/task de pentest. Rezultatul se păstrează după reload; click repetat cu aceeași comandă nu retrimite. O nouă încercare explicită este permisă numai după reconcilierea operației precedente și cu ID/buget nou legitim, nu „o singură încercare pe toată viața instanței”.
- Selecția inițială: **override de rol ales de operator, altfel default explicit fixat la admitere**. Preferințele REQUIRED ale metodologiei sunt verificări de compatibilitate; nu aleg singure un model/cont plătit neaprobat. Nu introducem acum un router AI care selectează modele din catalog.
- Modelul este identificat împreună cu conexiunea sa. Un același slug prin două chei/routere nu este aceeași configurație. Defaultul schimbat afectează numai runuri noi.
- O conexiune poate servi mai multe roluri; usage-ul și caps sunt cumulative. Retry/fallback local implicit dezactivate. O rută alternativă este acțiune nouă admisă; schimbarea către alt provider nu se ascunde ca recovery.
- Revocarea/înlocuirea credentialului blochează utilizările noi și drenează cele relevante; activele nu primesc tacit alt cont. Câmpurile publice sunt prezență/stare/ref, nu secretul.
- Seiful providerului este stocaj local separat de datele publice, cu credential ref opac, scrieri atomice, permisiuni restrictive și secret-at-rest protejat conform contractului de seif. Cheia de criptare nu intră în DB/backup/export; LOCKED este explicit. Refolosim această implementare pentru seiful target când apare consumerul B09h; nu pretindem că există deja.

### Bugete, DATA și Stop

Reutilizăm semantica reserve→SENT→receipt/UNKNOWN, nu automat toate presupunerile `managed-run`. Costul strict nu este deja implementat: `validate_limits` refuză un `cost_limit` non-null. Pentru primul live se aprobă limite finite de calls/input/output/timp/requests și cost estimat sau cap provider verificabil, fără badge financiar fals.

Fiecare apel de model, inclusiv copil/validator/continuare, și fiecare request target este admis sub același owner și buget agregat. `max_turns` nu este echivalent cu numărul apelurilor sau cheltuiala. În prima versiune nu există compresie/research/auxiliare LLM ascunse; context prea mare produce limită explicită.

DATA acoperă instrucțiuni, tool schemas, argumente, observații, rezultate și erori. `SyntheticApproval` actual aprobă numai texte sintetice; outputul target cere o proiecție nouă, cu sursă și limite. Tracingul extern este dezactivat înainte de primul Runner, inclusiv pentru copii; un exporter ulterior este altă decizie.

Veto-ul final verifică endpoint/credential/config/authority/deadline la send și pe conexiuni reutilizate. Stop revocă admiterea înainte de cancel/join/close/drain; efectele deja expediate pot rămâne remote in-flight/UNKNOWN. Nu pretindem anulare upstream sau exactly-once. La pierdere de răspuns nu se eliberează fictiv rezervă și nu se retrimite la reload/restart.

Omnis măsoară trimiterile sale către router, nu poate deduce tentativele interne ale acestuia. Routing/fallback acceptate se fixează și se raportează; dacă nu pot fi controlate sau observate la nivelul cerut de politică, combinația este indisponibilă ori cere o limită explicit acceptată, nu o garanție inventată.

## 4. Ordinea finită de livrare propusă

Nu sunt lansări autorizate acum și nu reprezintă un al doilea backlog. Etichetele T0–T6 sunt ordinea amendamentului care trebuie transpusă în planul canonic, cu tickets/SL existente.

| Felie propusă | Rezultat observabil / primul consumer | Pozitiv și negativ decisiv | Nu certifică |
|---|---|---|---|
| T0 — canon | Arhitectură/plan/UI/stack/status aliniate la decizia API-only, cu contracts/owners și fără gates native active contradictorii | Matrice completă, docs render/test și review exact al amendamentului | SDK admis, runtime funcțional sau live |
| T1 — conexiune și apel model | Web Settings→store/config→test finit prin owner și transport→outcome/readback; fără catalog/Publish/restart | Config locală, test explicit și rezultat; key greșită, config străină, Stop, error/incomplete/lost reply fără resend | Agent care folosește tools sau target |
| T2 — bibliotecă și rol/task | Același model în orchestrator și specialist cu skill minim fixat→tool tipizat inert→receipt→următoarea decizie→rezultat durabil | Tool cerut realmente, input valid și rezultat folosit; tool/ref/rol străin refuzat, caps agregate, trace/retries/Stop la consumer | Pentest, eficacitate, provider secundar |
| T3 — transport/evidence/auth | Executor HTTP trusted→laborator sintetic, scope/identități/capture/inspector, independent de model live | Allow la sink și evidence după restart; redirect/off-scope/IP/Host-SNI/identity/secret/Stop denied; pozitiv principal A/B | Browser, scanere externe, orice GET sigur |
| T4 — M-LAB | Orchestrator→discovery minim→ipoteză BOLA→investigator→validator/replay→rezultat inspectabil și readback | Vulnerabil confirmat cu date private canary; owner/shared/fixed/benign neconfirmate; auth invalid→inconclusive; Stop și fără resend | M1 complet, raport final, generalitate BOLA, benchmark |
| T5 — M1 și harness de bază utilizabil | Findings/report review/export HTML/JSON/retest din B13; completarea primei familii și UI utile | Download real/snapshot coerent, retest cu probe noi, claim/evidence indisponibile/ref stale refuzate | M2/breadth competitiv |
| T6 — harness aprofundat | Replan/STEER, skills/roles/comenzi mai bogate, provider mix, browser, recon/JS și extensiile promise | Fiecare funcție la consumerul real și evaluări separate | Paritate cu concurenții din număr de skills/agenți |

T1 și T2 sunt felii verticale ale aceluiași runtime, nu infrastructură de smoke abandonată. T3 determinist poate fi dezvoltat/probat fără model, după amendarea A05 și autorizarea laboratorului. Nu cerem să fie închisă inferența pentru a construi un broker determinist. T4 consumă T1/T2/T3.

La T1/T2, SDK/client/transport/lockurile runtime sunt admise cu consumatorul lor, nu după zeci de probe de constructor. După verificarea minimă SOURCE și reviewurile necesare, prima probă reală bounded precede extinderea breadth-ului. Nu este permisă trecerea peste un blocker de secrete/autorizație/Stop; nici transformarea fiecărei necunoscute istorice într-un prerequisite nou.

### Definiția M-LAB

Aplicație API deținută, resetabilă, cu date sintetice, două persoane, obiecte private și un obiect legitim partajat; variante vulnerable/fixed/benign și control auth-invalid. Intrarea agentului: URL, obiectiv, scope/permisiuni, identități și regulile business. Nu primește endpointul vulnerabil, requestul exploatabil sau seedul/adevărul evaluatorului.

Reconul produsului descoperă operația; obiectele/ID-urile pot fi cunoscute legitim prin persoanele autorizate, fără ghicire nelimitată. Cel puțin o alegere ulterioară depinde de un rezultat de tool. Investigatorul colectează baseline/probă/control. Validatorul are attempt și context auth proaspăt; aceeași familie de model este admisă, dar nu pretindem independență statistică.

Oracolul BOLA cere datele private canary ale obiectului interzis, principal valid, regulă DENY cu revizie și probele corespunzătoare. HTTP200, owner!=actor, schema JSON validă sau acordul a două modele nu confirmă. UI arată candidat/CONFIRMED/REJECTED/INCONCLUSIVE și probele, fără export final ori review editorial fictiv. Sunt obligatorii persistența, citirea după reload/restart fără rerun și un Stop verificat.

Această demonstrație este o evaluare de laborator a unui subset, nu assessment de producție sau certificat general. Raportarea/retestul M1 rămân deschise dacă nu sunt executate. Un rezultat fixed fără finding este corect numai cu precondiții/controale valide.

## 5. Matricea exactă de cod, distribuție și teste

Prefixe: `A=api/src/omnis/`, `C=cli/src/omnis_cli/`, `W=web/src/`, `H=integrations/hermes/`. **NEW** înseamnă cale propusă, nu fișier existent. Matricea originală detaliată este în raportul migrare; mai jos este delta adjudecată. Nu se creează preventiv toate modulele într-un singur commit.

| Căi / simboluri existente sau propuse | Dispoziție și consumer | Schimbări inseparabile / verificare |
|---|---|---|
| `A/modules/settings/provider_models.py`, `provider_routes.py`; `W/features/engagement/ProviderSettings.tsx`, `W/shared/api/providers.ts` | REPLACE Codex-only cu conexiuni API-key, model catalog/default/rol | DTO/route/decoder/UI/teste provider/source/web; CSRF/Host/Origin și key-no-echo păstrate |
| NEW `A/modules/settings/provider_connections.py`, `model_catalog.py`, `A/security/secret_store.py` | T1 store/config/catalog și credential ownership | Secret/DB consistency, LOCKED, atomicitate, revizii și readback; lipsa unui generic secret store este muncă nouă |
| Migrații noi secvențiale după `0013_mission_revisions`; `core/db.py`, `core/managed_schema.py`, `core/schema.py` | ADD aditiv pentru conexiuni/operații și ulterior run/task/evidence | Numărul exact se fixează la implementare; 0001–0013 nu se rescriu. Schema/readiness/CLI/bundle se schimbă împreună |
| `A/supervisor/__main__.py:111–156`, `instance/service.py`, `instance/schemas.py`, `transport/local_control.py` | MODIFY montare Settings/execuție fără catalog/runtime nativ; un singur owner | Quiesce istoric separat, grant valid, heartbeat, drain/Stop, input și operation IDs; nu doar schimbarea `handle/run` |
| `A/supervisor/native_tasks.py` și NEW `A/supervisor/agent_execution.py` | REPLACE execuție nouă sub supervisor; runtime-specific paths RETIRE | Atomic admission, task registry, cancel/close/join; nu al doilea scheduler |
| `A/modules/runs/model_test_routes.py`, `model_test_models.py`, `model_test_operation.py` | MODIFY operație de sistem, no provision/catalog; outcome fidel | Fixează pierderea statusului providerului; `test_model_test_*`, `ModelTest.test.tsx` și decoderul manual |
| `A/modules/runs/model_test.py`, `model_test_source.py`, `C/model_test_source.py` | KEEP read-only semantică istorică necesară; RETIRE producția specială și provisioning din T1 | Nu rerun al testelor vechi; citire fără client/provider, output/UNKNOWN păstrate |
| `A/policy/model_dispatch_contract.py`, `budgets.py`; `A/modules/runs/model_dispatch.py`, `model_protocol.py` | MODIFY versionat pentru scope de sistem/SDK; reuse reducer/invariants, nu native preconditions | `SCOPE_KINDS` doar managed-run astăzi; noul scope trebuie produs și rezolvat autentic. `_resolved/_budget`, usage/replay și vechiul reducer se verifică împreună |
| `A/policy/model_context.py`, `model_configuration.py`, `ready_model_configuration.py`; `A/modules/runs/model_projection.py`, `A/policy/model_projection.py` | KEEP V1/CONTRACT la istoricul său; ADD context/projection SDK și target după consumer | Fără native-turn fals sau approved DATA general din SyntheticApproval. Payload final și erori/loguri controlate |
| NEW `A/modules/runs/agent_models.py`, `agent_runner.py`, `provider_transport.py`; NEW `A/modules/tasks/agent_tools.py` | T2: contracte/runtime library/transport și tool registry îngust | API-uri publice SDK, clients expliciți, fără global hot-swap; trimitere reală/retry/trace/cancel și tool result persistence |
| `A/modules/tasks/execution_selection.py`, `managed_contract.py`, `managed_store.py`, `managed_composition.py`; separat `A/modules/runs/managed_admission.py` | KEEP istoric, MODIFY numai consumerii generici / ADD versiunea SDK | `managed_run` cere native fields după binding, `managed_task` are stări finite. Nu completăm cu IDs false și nu relaxăm V1 pentru V2 |
| `A/modules/tasks/{method_checks,method_checker_identity,criterion_checks,mission_revisions,result_qualification}.py`; `A/modules/coverage/denominator.py` | KEEP readeri/semantici CONTRACT; FREEZE breadth; EXTEND SECURITY cu B11/B12 | `method_checker_identity.SOURCES` hash-uiește closure-ul: nu mutări/ștergeri oarbe; proof de reader vechi, fără recompunere/executare |
| `A/modules/settings/{skill_catalog,candidate_catalog,candidate_resolution,candidate_store,catalog_publication,publication_store}.py` | KEEP parsare/digest/provenance/istoric; MODIFY compatibilitate/composer către runtime nou | Input read-only, fără import/shell; candidate eval permis înainte de Publish; nu prerequisite T1 |
| `A/supervisor/runtime_client.py`, `case_slot.py`; `runs/native_preparation.py` și modelele aferente | RETIRE din noua execuție după înlocuirea callerilor; KEEP metadata readback necesar | Nu mai există boot/ticket/session Hermes pentru SDK; arhive vechi nedescărcate/neadoptate |
| `H/src/omnis_hermes/`, `H/upstream/*patch`, source mirrors, `pin.json`, runtime override și locks | RETIRE din distribuția nouă; pure helpers necesari se păstrează/adaptează explicit cu proveniență | Artifactul nou trebuie să ruleze fără wheel/surse/imagine Hermes. Istoria Git/notices și arhivele nu sunt șterse |
| `C/start.py`, `start_runtime.py`, `compose.py`, `release.py`, `instance.py`, `restart.py`, `status.py`, `stop.py` | MODIFY profile/manifest/services/schema pentru runtime nou | Installed start/status/Stop/restart/date, nu doar build; identități/receipts versionate și fără adopție de profil vechi |
| `C/forwarder.py` | KEEP browser→API; RETIRE auth/Codex-only forwarding în noul profil | Egress provider API nou, finit și revocabil; TLS relay nu este broker target |
| `C/native_artifacts.py`, `ops/prepare_hermes_runtime.py`, `ops/Dockerfile.hermes`, `ops/Dockerfile.control-model-test` | RETIRE producție nativă; KEEP citirea manifestelor istorice unde necesară | Nu alterăm releaseuri deja instalate; profile/fingerprint/reader compatibile |
| `ops/build_control_bundle.py`, `ops/Dockerfile.control`, `ops/compose.control.yaml` | MODIFY closure runtime nouă și egress | Rețeaua control internă actuală nu are automat acces provider. Fără Docker socket, grant general network sau startup effectful |
| `api/pyproject.toml`, `api/uv.lock`, manifests CLI și exports de release | MODIFY dependențe runtime admise | SDK/client nu rămân dev-only; pinned closure/audit/copy-install real; no latest și no LiteLLM implicit |
| `contracts/omnis.openapi.json`, `W/shared/api/{generated,client,modelTest,providers}.ts` | REGENERATE/MODIFY numai după endpointuri reale | OpenAPI→TS nu repară decoderii manuali; format/outcome/source/error + callers în aceeași felie |
| `Makefile`, `ops/run_test_db_gate.py`, teste API/CLI/web, `H/tests` | MODIFY gates active; KEEP regresii utile/istorice | Noul gate nu trebuie să depindă de native/OAuth build. Fără skip global, reduceri de safety sau canonical fals-verde |
| `skills/{recon-mapping-contract,records-mapping-contract}`, `profiles/` | KEEP istoric/knowledge; nu redenumite automat SECURITY | CONTRACT probe≠pentest; materialul first-party LAB nou se fixează/revizuiește și se evaluează |
| NEW `skills/object-authorization/`, `profiles/api-bola-lab.yaml`, `labs/dev/fixtures/object-authorization/` | T4 candidat de metodă și laborator | Fixture private/shared/vulnerable/fixed/auth controls; evaluatorul ține adevărul separat |
| `skills/bug-bounty-triage/SKILL.md` | REVIEW/ADAPT înainte de utilizare, nu activare automată | Instrucțiunile importate de păstrare secrete/tooluri externe nu sunt policy Omnis; license/provenance păstrate |
| NEW `executors/http/`; `A/modules/{identities,evidence,surfaces,validation,findings,reports}/` | CREATE cu T3/T4/T5, nu tot arborele preventiv | Tool boundary→sink→artifact→UI; snapshots și acces pe context. `reports` complet vine la T5 |
| `.hermes/skills/`, `scripts/hermes_dev.py`, toolingul developer | KEEP | Actualizare numai a instrucțiunilor despre produs; nu ștergere globală după cuvântul Hermes |

### Istoric și distribuție

`0011_managed_tasks` are `runtime_boot/ticket/native_root_id` corelate cu binding și taskuri native; nu este un model universal de job deja disponibil. Extinderea lui ori adăugarea unei tabele de operații se decide prin contractul v2 înainte de autor, cu o migrare aditivă și primul consumer. Nu acceptăm JSON liber care ține loc de chei de autoritate/FK/stări.

`method_checker_identity.SOURCES` include checker, managed composition/contracts și catalog; schimbările acolo afectează fingerprints. Primul release nou nu șterge datele vechi, nu le recompune și nu execută metodele pentru a le citi. Cititorii păstrați trebuie să funcționeze fără import/launch Hermes; dacă un reader nu poate fi păstrat încă, datele rămân arhivate și limita este explicită, nu compatibility PASS.

Un release nou are identitate și manifest proprii. Profilurile/PGDATA/granturile existente nu sunt migrate sau șterse automat. Upgradeul în loc și rollbackul DB necesită backup/restaurare probate separat; Git nu revine asupra datelor. Metadata veche rămâne legată de vechiul executor, fără authoritate de execuție nouă.

**Final de retragere Hermes:** toate noile calleri și installed start/status/Stop nu cer proces/wheel/source/imagine native; istoricul declarat suportat este citibil receive-only; noul artefact trece probele de model/tool/Stop fără acea dependență. Numai atunci se scot producerii morți din arborele activ, păstrând Git/licențe/arhive. Nu menținem două motoare active pentru același run.

## 6. Amendamente exacte ale documentelor canonice

Locatoarele sunt ale bazei analizate. **Nu este suficient un find/replace Hermes→OpenAI**: vechile obligații de identitate/control trebuie reatribuite sau retrase explicit.

| Document / secțiune | Schimbare necesară |
|---|---|
| Arhitectură §1 și §2 A04/A06/A14/A16 | Runtime/agent library Omnis și API keys; retrage delegare nativă, management REST și curator Hermes obligatorii. Păstrează separat developer tooling |
| Arhitectură **A05** și §3/topologie/TCB | Amendament HTTP trusted pentru prima felie API-only; provider și target egress distincte; zero rută model→target. Browser/scannere cer gates ulterioare, nu excepție implicită |
| Arhitectură §4, §4.1–4.5, L06–L08 | Profile/release/runtime ownership și startup fără provider IO; Settings fără management Hermes, Stop pe executor nou; starea instalărilor vechi rămâne istorică |
| Arhitectură §5, inclusiv tabelele RPC/Settings | Înlocuiește cu contractele §2–3 de aici. Retire pin/mapping obligatoriu la session.create/prompt.submit/SubagentLaunchRequest și strategia «patch minimal cu orice preț» |
| Arhitectură §5.2 | SETTINGS_TEST sistem; model dispatch versionat fără native_turn fictiv; caps numerice API, șterge excepția activă MONITOR_SUBSCRIPTION, păstrează istoria |
| Arhitectură §6/§6.1–6.3 | Omnis deține continuarea/inbox; rol/context/attempt separate; simpla buclă adaptivă M-LAB precede replan/rework general; Stop/snapshot/no-refill rămân |
| Arhitectură §7–8 | Păstrează scope/effect/business-rule/auth/AEAD; adaptează proprietatea seifului/providerului. Nu presupune GET safe sau provider-key=target identity |
| Arhitectură §9/§9.3–9.6 | Schema/versioning și ref ownership; compatibility.runtime/adaptor în loc de hermes_revision pentru noile pachete; composer/ToolDefinition/provenance deținute de Omnis |
| Arhitectură §9.7–9.8 | Emitent sistem pentru test, task trusted pentru copil, PACKAGE_EVAL pentru candidata LAB; test provider fără Publish și fără Mission |
| Arhitectură §9.9–9.10 | AgentRecipe/ExecutionSelection model-per-rol; metodologie/rol/task distincte; păstrează checkerul necesar fără critic/rework universal înainte M-LAB |
| Arhitectură §10–11 | Inventar sessions/cache/traces SDK și date provider; marker/test data policy; definește M-LAB BOLA și separă integration vs efficacy |
| Arhitectură §12/arbore/importuri/upgrade | Pachetul SDK în runtime-ul distribuit ales; paths noi numai cu consumer. Retragerea artifactelor Hermes, păstrarea notices și dev skills |
| Plan §1–3 și RF02/RF04/RF07/RF12 | Stack/owners noi, API-key-only, funcționalități finale păstrate; fără al doilea provider ca prerequisite universal al primei probe |
| Plan §4/§4.2/§4.3/§4.4 | Integrează T0–T6 și M-LAB ca intermediar; SL07–13 își schimbă consumerul, nu șterg istoricul. Păstrează M1 complet după M-LAB și M2 separat |
| Plan §7/§7.1/§8 | P2-inert istoric; retire active Hermes/OAuth mandates și înlocuiește cu biblioteca+provider+tool gates. No catalogue/setup cycle pentru test |
| Plan §9–11 | HTTP determinist poate precede model live; prima BOLA API fără browser/editor universal. M-LAB consumă doar minimul B07/B09h/B10/B11/B12 și rezultat inspectabil |
| Plan §12–15 | T5 raport/retest; apoi harness aprofundat, browser/breadth, Jev/research/improvement/path. G-HERMES-BOUND se înlocuiește prin obligații runtime-neutre, nu se șterge safety |
| Plan §16 UI09/UI15/UI22 și §17 HF05/HM | Mapări UI→backend→DTO→migrare→consumer→probe actualizate. HF/reuse IDs au dispoziție, nu ștergere retrospectivă |
| Plan §19/§19.2 | Un CURRENT despre direcția aprobată și următorul consumer real; vechile mandates de Codex/recovery nu mai sunt coada activă |
| UI §2–4/§7–8 | Provider/key/catalog/default/rol și statuses truthful, Test model independent de wizard; UI run/evidence/validator minim pentru M-LAB; layoutul acceptat și accesibilitatea se păstrează |
| Stack §1–2/§7/§9–10, `Omnis_Stack_Baseline.versions.json` | Hermes runtime→istoric, SDK candidat→admis numai după pin/probe; client/runtime deps reale, provider APIs. S01/S05/S06/S09 destinații noi; HM01–HM08 retired/adapted cu surse păstrate |
| README, implementation-status, verification index | Un CURRENT/pointer și rânduri actuale, linked analiza deciziei; nereexecutate nu devin PASS. Auditul anterior rămâne diagnostic istoric |
| CONTRIBUTING și skills de dezvoltare relevante | Rutare neutră pentru noul runtime; vechiul omnis-hermes-runtime poate rămâne explicit legacy. Nu eliminăm trust/hermes_dev ori skills developer |
| AGENTS.md protejat | Corecție explicită a contractului/stării depășite când se autorizează amendarea; fără fișier alternativ sau ocolirea protecției |

### H01–H08: ce se retrage și ce se păstrează

H01 retrage framingul/gateway RPC ca prerequisite nou; păstrează timeout/backpressure/unknown operation la transportul folosit. H02 păstrează no ambient credentials/cross-case contamination, fără CODEX_HOME/OAuth ca consumer activ. H03 păstrează skill digest/loader read-only. H04 păstrează task/attempt/capability mapping pre-access, fără native batch index obligatoriu în SDK. H05 păstrează lineage/context integrity dacă există compresie; compresia indisponibilă inițial nu produce o probă nativă fictivă. H06/H07 păstrează Stop/late results/inbox/no-resend/restart, cu Omnis ca unic owner al continuării. H08 păstrează inventarul efectiv al tools și fiecare dispatch model/aux; lipsa auxiliariilor inițiale este funcțională, nu un inventar fabricat. Probe native vechi rămân la snapshoturile lor.

## 7. Dispoziția SL01–SL36 și E1–E4

Un ID apare o singură dată în tabel. Dispoziția privește contractul nou, nu șterge acceptările istorice. M-LAB este intermediar; nu marchează M1 sau fazele rămase închise.

| ID | Dispoziție | Consumer / poziție propusă |
|---|---|---|
| SL01 | KEEP | Fixture PG/ownership, numai probele necesare noilor consumeri |
| SL02 | KEEP + affected | Start/control păstrate; distribuția nouă cere regresii reale |
| SL03 | KEEP | Pair/open/sesiuni, fără nouă identitate de pentest |
| SL04 | KEEP + extend | Stop/fence/date; noile efecte primesc propriile controale |
| SL05 | KEEP | Draft/revizii/CAS, sursă pentru M-LAB |
| SL06 | KEEP + extend | UI actuală, fără redesign; butoane activate numai cu consumer |
| SL07 | REPLACE | Host/RPC nativ retired; owner/SDK execution T1/T2 |
| SL08 | MODIFY/FREEZE breadth | Catalog/pins utile; compatibilitate nouă, fără test-provider prerequisite |
| SL09 | MODIFY | Task/attempt/brief/result/inbox runtime-neutre, minim T2/T4 |
| SL10 | MODIFY | DATA pe SDK și output target real, fără transfer de NO-IO PASS |
| SL11 | MODIFY | Scope sistem/run, ledger și veto send/Stop la noul consumer |
| SL12 | REPLACE | API keys/default/per-role/model test din web |
| SL13 | REPLACE | Loop real model→tool→rezultat; nu doar connectivity |
| SL14 | DEFER/REBASE | Proxy universal nu blochează HTTP trusted; browser/scanner transport admit înaintea folosirii |
| SL15 | MODIFY | HTTP/evidence/core policy T3, după amendamentul A05 |
| SL16 | KEEP + slice | Stream/inspector minim T3/T4, rest proiecții la consumer |
| SL17 | KEEP + slice | Auth HTTP A/B/validator necesar T4; refresh breadth ulterior |
| SL18 | DEFER | Browser/SPA după M-LAB, rămâne capabilitate MVP |
| SL19 | KEEP + slice | Discovery minim din URL la T4, extindere ulterior |
| SL20 | KEEP + slice | Hartă/provenance/gaps minime; coverage complet ulterior |
| SL21 | KEEP + slice | Candidat BOLA pentru PACKAGE_EVAL M-LAB, publish SECURITY înaintea utilizării de producție |
| SL22 | KEEP + slice | Replay/controale/oracol BOLA deja la M-LAB; extensii după |
| SL23 | KEEP + slice | Rezultat/finding inspectabil T4; editorial/review complet T5 |
| SL24 | DEFER după M-LAB | Raport export/retest de produs la T5, necesare M1 complet |
| SL25 | DEFER advanced | Adaptare tool-result minimă T2/T4; STEER/replan durabil/rework la T6 |
| SL26 | DEFER advanced | Obiectiv/scope fixe înainte de efect; focused complet ulterior |
| SL27 | DEFER | Wordlist recipe/artifacts cu primul consumer util |
| SL28 | MODIFY/DEFER | Research Omnis ulterior cu egress/DATA proprii |
| SL29 | DEFER | Recon/JS/Katana/Nuclei extinse după M-LAB |
| SL30 | DEFER | XSS/traversal și oracole separate după transportul necesar |
| SL31 | DEFER | Attack paths: ambele findings și tranziția probate |
| SL32 | DEFER | Jev OFF/SHADOW/evaluare ulterior, direcție păstrată |
| SL33 | MODIFY | Ambii routeri/config roles, fiecare probat; editor complet ulterior |
| SL34 | MODIFY/DEFER | Maintenance/improvement Omnis, nu curator Hermes; no auto-publish |
| SL35 | MODIFY/DEFER breadth | Recovery nou; nucleele Stop/UNKNOWN înainte de live |
| SL36 | KEEP | Held-out, operare/release, backup/restore și limite reale |
| E1 | KEEP ulterior | Exposure/auth/JWT/BFLA/mass assignment/SQLi, oracole proprii |
| E2 | KEEP ulterior | CSRF/DOM-stored-XSS/SSRF/XXE/business/race/history/debugger |
| E3 | KEEP ulterior | Source snapshot revizuit, zero exec la import |
| E4 | KEEP ulterior | Protocoale/workers/familii riscante/deployment separat autorizate |

## 8. Harnessul aprofundat după M-LAB

Nu promitem „toate skills” printr-o bibliotecă. Dezvoltăm următoarele prin rezultate observabile:

| Zonă | După proba mică | Criteriu real |
|---|---|---|
| Strategie/roluri | Recon/mapping, investigator Web/API, triage, validator și coordonare specializate numai unde au valoare | Clue/contradicție schimbă taskul; fără taskuri duplicate sau buget reumplut |
| Skills/metodologii | Pachete cu input/aplicabilitate/probe/control/fallback/rezultat; adaptarea source/notices | Evaluare vulnerable/fixed/benign; metodologie disponibilă≠execuție certificată |
| Comenzi/unelte | Registru îngust, argumente/schemă/limite/timeout/capture/cancel pentru fiecare adaptor | Acțiune atribuită→sink→evidence; unknown tool/argument/efect refuzate |
| Model-per-rol | Mix real OpenRouter/OrcaRouter, modele distincte și context separat | Requested/effective, caps/usage agregat, indisponibilitate și no silent fallback probate |
| Memorie/context | Harta și facts/evidence refs locale, compresie doar când consumerul o cere | Fără contaminare cross-run sau pierderea contradicțiilor/provenienței |
| UI/operare | Start/Stop/steer/aprobări/tasks/findings/reports/retest din web | Readback real, reload fără efect, Stop persistent și stări oneste |
| Recon/browser/JS | Adaptoare concrete și parsere, auth post-login, subrequesturi controlate | Descoperire proprie, proveniență și refuz la sink; nu rezultate externe injectate ca discovery |
| Triage/validation | Critic separat pentru omisiuni, replay/oracole pentru adevărul claimului | Scădere FP/misses măsurată; acordul modelelor nu devine verdict |
| Learning/Jev/research/path | Propunere→eval→review→publish viitor; shadow/advisory; research citat; chaining probat | Nu autoritate din scor/prompt, auto-publish sau path fără tranziție |
| Eficacitate | Corpus de dezvoltare + held-out, baseline determinist și comparații egale | TP/FP/FN, coverage gaps pe cauză, replay, intervenții, cost/latency, scope violations |

Comenzile **existente** din CLI rămân `start --no-open`, `status`, `pair`, `open`, `stop`, `install`, `install-image` la scope-ul lor actual. `omnis run stop`, doctor și operațiile generale de assessment nu sunt pretinse disponibile. Noile Start/run Stop/test-provider/catalog-refresh/report/retest sunt contracte de produs ce trebuie implementate cu API/readback și UI; nu instrucțiuni shell date modelului. Catalogul larg și E1–E4 nu dispar, dar nu sunt pregătite preventiv înaintea primei investigații.

## 9. Verificări, criterii de acceptare și autorizații viitoare

Pentru fiecare felie: prerequisite/producer/caller/bytes → SOURCE pozitiv/negativ → review independent (două reviewuri complementare pentru authority/effect/Stop) → consumerul real afectat → integrare/commit. Un test poate descoperi o problemă, nu poate garanta absența tuturor defectelor.

- Testele documentare se adaptează semantic la contractul aprobat; nu ștergem aserțiunile de safety sau probele istorice ca să fie green. `test_amendment_contracts`, `test_b06b_preparation`, `test_project_status`, `test_resume_status`, `test_baseline_contracts`, `test_flow_contracts`, `test_skill_patterns` și manifestele reuse se verifică pe delta reală.
- Markdown normativ schimbat → `python scripts/render_docs.py`, apoi `--check` și `python -m unittest discover -s tests/documentation -v`. UI/document render schimbat cere verificarea browser relevantă; estetica nu este aprobată de test.
- OpenAPI/TS se generează numai după endpointurile/DTO-urile implementate. Decoderii manuali și fixturile se actualizează împreună.
- Runtime: auth/metadata/capability real, loop/tool result, headers/body/date/caps/Stop la sender, outcome și restart fără resend. Mock-only/SDK no-IO nu sunt inferență.
- Installed: noul bundle, wheel/runtime closure, schema, start/status/Stop, date și readeri istorici. `make check` și runnerul PG au efecte; nu sunt dry-run și nu sunt relansate pentru această analiză.
- M-LAB: același produs face discovery/probe/validator/readback. Controale fixed/benign/auth-invalid și refuz off-scope sunt obligatorii. Benchmark-ul și full release rămân distincte.
- Fără cont/țintă se pot face scheme, serializare, pozitivi/negativi SOURCE și integrare locală controlată autorizată. Pentru live: cheie/provider/model exact, date permise și buget finit; pentru laborator: URL/scope/identități/efecte/request limits/sinks/cleanup separate. Mandatul Sol autorizează numai analiza de dezvoltare.

### Riscuri deschise și limite ale concluziei

1. Pinul SDK/client și closure-ul compatibil nu sunt încă admise; sursa inspectată nu este instalare/test de integrare.
2. Seam-ul public poate fi suficient pentru integrare, dar veto-ul fizic și Stop trebuie demonstrate înainte de live; fără patchuri intrusive tacit acceptate.
3. Cheile/model catalog și outputurile providerilor au semantică diferită; model vizibil nu înseamnă tool-ready.
4. Contractul v2 al scope-ului sistem/ledger/DB trebuie înghețat înainte de autor; nu există deja doar prin `hermes=False`.
5. Rutarea upstream, costul/quota și parametrii pot fi neobservabili. Nu se transformă în garanții.
6. Persistența istorică și checker fingerprints pot păstra dependențe pure; eliminarea runtime-ului nu permite distrugerea datelor.
7. API keys și identitățile target sunt secrete distincte; seiful generic nu este deja implementat.
8. M-LAB trebuie să rămână mic; dacă devine dependent de editor, replan general sau nou harness de certificare, ordinea a deviat. Safety minimă nu se taie pentru a-l micșora.

## 10. Review și rezultat al acestei felii

**Review încheiat: APPROVED_SCOPED pentru analiza care pregătește T0**, nu pentru pin, implementare sau runtime. [Raportul original Sol 6.1 xhigh](api-key-migration-evidence/review-sol-xhigh.md), SHA256 `54eb92cef92f388839cc0976425348bf6e352babed7fd46e4095d360306a3ec1`, a fost citit integral și păstrat byte-exact. Sesiune `01a15fed-7518-77a3-87c9-b495758d64b4`, proces `proc_3cd264ee6a66`, exit0; banner observat `gpt-6.1-sol`, effort `xhigh`, sandbox read-only, approval never. Candidatul analizat avea SHA256 `4c4176ac6eac8bdf23d8f21463f9593072f48c6af97e988e9ccedc73f753ac1e`, produsul HEAD39ab04f neschimbat.

**F01 LOW, neblocant, corectat editorial de părinte:** rândul matricei grupa greșit `managed_admission.py` sub tasks. Calea reală este `api/src/omnis/modules/runs/managed_admission.py`; rândul o separă acum explicit. Nu este un modul nou/refactor. Verificarea căii existente și a absenței variantei greșite este independentă de verdictul semantic; această corecție și nota de adjudecare sunt post-review, nu pretindem identitate byte-exactă cu vechiul candidat.

Reviewerul a confirmat separarea M-LAB/M1, reatribuirea H01–H08, schema/readerii istorici și amendamentul A05. A păstrat legitime limitele SDK pin/transport/live neexecutate și a indicat **amendarea canonului ca următorul pas**, nu o nouă analiză generală. Accesul lui la sursa SDK exact-pin a eșuat; documentația curentă consultată nu înlocuiește citirea source-pin făcută de părinte și nu constituie probă runtime. Nicio constatare blocantă nu a fost raportată în acest scope.

Schimbarea indexului `documents/verification/README.md`, observată la final de reviewer, aparține părintelui și este doar pointerul analizei/etichetarea registrelor anterioare; a fost exclusă corect din verdictul lui. Nu s-a modificat sursa produsului sau canonul înghețat. Verificările documentare au trecut: `python -B scripts/render_docs.py --check` exit0 și `python -B -m unittest discover -s tests/documentation -v` 75 PASS/exit0. Verificarea structurală a părintelui a găsit toate cele40 ID-uri SL/E unice și linkurile locale existente. Aceste rezultate verifică artefactele, nu succesul migrării.

Preflightul CLI a avut o eroare de gramatică: `codex sandbox linux --help` a încercat executabilul `linux` și a ieșit 101, înaintea oricărei inferențe. Helpul real a arătat gramatica corectă; `codex -c sandbox_mode=\"read-only\" sandbox -- /usr/bin/true` a trecut exit0. Nu s-a dezactivat sandboxul și nu s-au modificat setări globale. Cele trei procese de analiză au fost urmărite și încheiate exact; doar launcherul a salvat rapoartele. Nu au fost executate teste/builduri/servicii/DB/Docker/provider calls de produs/target și nu au fost citite credentiale.

## Surse primare pentru biblioteca și providerii propuși

- [OpenAI Agents SDK — Models](https://openai.github.io/openai-agents-python/models/)
- [Agent/Runner](https://openai.github.io/openai-agents-python/agents/), [manager/agents-as-tools](https://openai.github.io/openai-agents-python/multi_agent/), [tracing](https://openai.github.io/openai-agents-python/tracing/)
- [SDK Model interface la pinul inspectat](https://github.com/openai/openai-agents-python/blob/a2d82707d94bfcf2ffbcc62ea9746c5fb183804f/src/agents/models/interface.py), [Agent](https://github.com/openai/openai-agents-python/blob/a2d82707d94bfcf2ffbcc62ea9746c5fb183804f/src/agents/agent.py), [RunConfig](https://github.com/openai/openai-agents-python/blob/a2d82707d94bfcf2ffbcc62ea9746c5fb183804f/src/agents/run_config.py), [retry](https://github.com/openai/openai-agents-python/blob/a2d82707d94bfcf2ffbcc62ea9746c5fb183804f/src/agents/retry.py)
- [Strix manifest](https://github.com/usestrix/strix/blob/a3c31236bd6305784a501a3102dab0bda83f2317/pyproject.toml), [lock](https://github.com/usestrix/strix/blob/a3c31236bd6305784a501a3102dab0bda83f2317/uv.lock), [routing](https://github.com/usestrix/strix/blob/a3c31236bd6305784a501a3102dab0bda83f2317/strix/config/models.py), [runner](https://github.com/usestrix/strix/blob/a3c31236bd6305784a501a3102dab0bda83f2317/strix/core/execution.py)
- [OpenRouter SDK](https://openrouter.ai/docs/guides/community/openai-sdk), [tool calling](https://openrouter.ai/docs/guides/features/tool-calling), [catalog](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
- [OrcaRouter SDK](https://docs.orcarouter.ai/compatibility/openai-sdk), [catalog documentat](https://docs.orcarouter.ai/routing/free-models)

Sursele documentează interfețe/capabilități declarate; nu certifică versiunea aleasă, eficacitatea, modelul efectiv, retenția sau garanțiile serviciilor. Codex subscription și SIWC nu intră în soluția nouă, chiar dacă au fost cercetate în discuția precedentă.
