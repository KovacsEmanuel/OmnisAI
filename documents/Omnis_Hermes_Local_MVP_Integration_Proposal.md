# Omnis × Hermes — MVP local și contracte de integrare

**Revizie pentru discuție · 25 septembrie 2026**

Aceasta este propunerea de lucru actualizată după clarificarea MVP-ului local. Nu este o implementare, o aprobare a tuturor alegerilor tehnice sau o autorizație de scanare. Păstrează propunerile precedente ca istoric, dar înlocuiește presupunerea unui MVP redus la o singură scanare demonstrativă.

**Bază verificată:** documentația oficială Hermes, pornind de la indexul public,[1] și inspecția statică a checkoutului `0.21.5`, commit `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, din `/home/kali/.hermes/hermes-agent`. Nu au fost pornite gatewayuri, schimbate credențiale, apelate modele sau testate ținte în acest audit. „Confirmat în cod” nu înseamnă „validat end-to-end”.

## 1. Verdict și limite confirmate de utilizator

**Da: Omnis poate folosi Hermes ca motor de agenți în backend și poate reutiliza inclusiv orchestrarea subagenților.** Nu este necesar să copiem autentificarea providerilor sau să facem un fork masiv. Integrarea recomandată are trei suprafețe: API-ul de execuție Hermes (preferabil JSON-RPC pentru acest MVP), API-ul administrativ al Dashboardului și un plugin Omnis pentru unelte și telemetrie.[2][3][7]

Dar **Hermes nu furnizează prin aceste contracte modelul de engagement, harta de țintă, metrica de coverage sau verdictul probatoriu al unui finding**. Acestea sunt produsul Omnis, nu o temă nouă pentru dashboard.

### Confirmat în această discuție

- Aplicație web **locală** în prima fază.
- Validare pe **laboratoare și aplicații proprii/de test, cu autorizare explicită**.
- Identități opționale: fără login, cookie/token/Basic Auth; login în browser asistat de utilizator pentru fluxuri complicate.
- Teste cu impact limitat automat; **aprobare înaintea modificărilor și acțiunilor mai intruzive**.
- Settings inițial pentru **OpenRouter** și **ChatGPT/Codex OAuth**.
- Engagement dashboard live, recon, hartă navigabilă, ipoteze, workeri scurți, verificator separat, findings și raport.
- Chains avansate pot rămâne post-MVP.

### Recomandări, nu decizii impuse

Un operator local inițial; un engagement activ simultan; workeri concurenți limitați în interiorul lui. Un provider/model explicit per engagement la început; schimbarea modelelor per rol poate urma după testarea rutării și contabilizării. Un singur cont AI nu este totuna cu o singură identitate pe țintă: putem avea identități de test separate în același engagement.

**Local nu înseamnă offline.** OpenRouter și Codex presupun acces la servicii externe; fragmentele trimise modelelor trebuie filtrate și aprobate prin politica de date. Nu încărcăm automat întregul trafic al aplicației în prompturi.[8]

## 2. Cine deține ce

| Strat | Responsabilitate | Reutilizare / construcție |
|---|---|---|
| Omnis Web | Settings, engagement wizard, scope, identități, hartă, progres, approvals, findings, raport | Construim UI propriu; nu clonăm întregul Hermes Dashboard |
| Omnis API și DB | Starea engagementului, snapshoturi, taskuri, evenimente durabile, dovezi, autorizare | Construim; sursa canonică a produsului |
| Adaptor Hermes | Client JSON-RPC pentru agenți, client REST pentru administrare, corelare și reconciliere | Construim clienți restrânși peste interfețele existente |
| Hermes runtime | Provideri, autentificare AI, conversații, compresie, tool-calling, copii AI | Reutilizăm |
| Plugin Omnis în Hermes | Unelte de domeniu, acces restrâns la context, legătura task–subagent, telemetrie | Construim pe API-urile de extensie existente |
| Broker/executori Omnis | HTTP, browser și unelte de recon controlate; scope, identități, rate, timeout, captură de dovezi | Construim adaptoare; putem reutiliza unelte existente fără să le expunem ca shell nelimitat |

```text
Browserul operatorului
  └─ Omnis Web + API
       ├─ DB engagement + taskuri + evenimente + evidence store
       ├─ Settings adapter ── Hermes Dashboard API privat
       ├─ Runtime adapter ── Hermes JSON-RPC privat
       │                      └─ Brain Hermes
       │                           └─ delegate_task → subagenți Hermes
       └─ Broker de acțiuni → executori izolați → ținte autorizate
                 ↑
        pluginul cere acțiuni; brokerul decide și execută
```

Aceasta este o separare de responsabilități, nu cerința de a crea microservicii. Recomand un **monolit modular Omnis**, Hermes într-un proces/mediu separat și executori separați. Postgres poate păstra taskurile și evenimentele; nu avem nevoie inițial de Redis, Neo4j sau Kubernetes. Frontendul poate fi React/TypeScript, iar backendul Python/FastAPI; acestea sunt alegeri propuse, nu rezultate ale auditului.

Hermes Dashboard și API Server sunt suprafețe distincte. Browserul Omnis nu primește cheile lor de administrare. Backendul face apelurile și expune numai operațiile necesare engagementurilor.

## 3. API-uri de execuție: REST și JSON-RPC

### Alegerea pentru MVP: JSON-RPC pentru control fin

**JSON-RPC este tot un API**, nu automatizarea ecranului TUI. Omnis trimite obiecte JSON și primește răspunsuri/evenimente structurate. Protocolul este disponibil pe stdio sau WebSocket; este interfața folosită de hosturile Hermes pentru sesiuni, approvals și subagenți.[3]

Pentru local-first recomand un host Omnis care deține procesul RPC și transportul stdio. Entrypointul verificat este `python -m tui_gateway.entry`, rulat cu interpreterul instalării Hermes și mediul Omnis controlat; nu există un flag `hermes --mode rpc` de inventat. Alternativa WebSocket `/api/ws` există în `hermes_cli/web_routers/chat_ws.py:583–601`, dar cere gate-urile și credentialul transportului său; nu presupunem că un token REST funcționează identic. Stdio evită să expunem încă un transport privilegiat browserului.

| Operație a hostului Omnis | Metodă JSON-RPC existentă | Parametri principali |
|---|---|---|
| Negociere întrebări/approvals | `client.capabilities` | `server_requests: true`, după `gateway.ready` |
| Creare Brain | `session.create` | `provider`, `model`, `title`, `cwd` controlat, `close_on_disconnect: false` |
| Pornește/continuă lucru | `prompt.submit` | `session_id`, `text`; alte câmpuri nu se transmit implicit |
| Stare / istoric | `session.status`, `session.history` | `session_id` |
| Reatașare / evenimente recente | `session.resume`, `session.events.since` | Pentru events: `session_id`, `last_seen`; nu înlocuiește jurnalul Omnis |
| Intervenție Brain | `session.steer` | `session_id`, `text` |
| Copii activi | `subagent.list` | `session_id` al părintelui |
| Intervenție copil | `subagent.steer` | `session_id`, `subagent_id`, `text` |
| Oprire copil | `subagent.interrupt` | `session_id`, `subagent_id`; verificăm ulterior terminarea |
| Stop sesiune | `session.interrupt` | `session_id`; Omnis revocă și acțiunile/executorii |

Schemele au fost verificate în `apps/shared/src/gateway-contract.openrpc.json`, iar controlul copiilor în `tui_gateway/methods_subagents.py:53–113`. `session_id` RPC și `stored_session_id` sunt valori distincte returnate la creare; păstrăm ambele, fără a presupune identitate cu ID-uri HTTP. `subagent.list` nu oferă automat un istoric durabil al tuturor copiilor.

Exemple JSON-RPC **de schemă, neexecutate**, cu substituenți expliciți:

```json
{"jsonrpc":"2.0","id":"omnis-cap-1","method":"client.capabilities","params":{"server_requests":true}}
```

```json
{"jsonrpc":"2.0","id":"omnis-create-1","method":"session.create","params":{"provider":"openrouter","model":"<MODEL_DIN_CATALOG>","title":"Omnis · ENG_DEMO · Brain","cwd":"<WORKSPACE_OMNIS_CONTROLAT>","close_on_disconnect":false}}
```

```json
{"jsonrpc":"2.0","id":"omnis-turn-1","method":"prompt.submit","params":{"session_id":"<RPC_SESSION_ID>","text":"Începe engagementul ENG_DEMO folosind uneltele Omnis și snapshotul autorizat."}}
```

Hostul trebuie să răspundă și la requesturi **server → client**, nu doar să consume evenimente. Pentru `approval` răspunde cu același `id` și `result:{choice:...}`; pentru metode neimplementate returnează eroare JSON-RPC, nu lasă agentul blocat. `request.cancel` retrage numai întrebarea corespunzătoare. Nu implementăm sudo/shell general pentru un workflow de pentest limitat.[3]

Diferența față de REST: RPC expune și progres `subagent.tool`, dar oglindirea UI nu este sursa probatorie. Evidence și verdictul vin din broker; observer hooks completează telemetria.[6] În plus, admission-ul unui prompt RPC nu moștenește garanția `Idempotency-Key` a HTTP Runs: după un răspuns pierdut, hostul verifică status/istoric/attempt înainte să retrimită.

### Alternativa HTTP: contracte existente și utile

Tabelul următor documentează ce putem apela prin REST, chiar dacă pentru controlul nativ fin al copiilor recomand RPC. **Nu conducem aceeași sesiune simultan prin doi proprietari RPC/HTTP.**

Contractele de mai jos sunt Hermes, nu endpointuri Omnis inventate. API Server folosește `Authorization: Bearer <API_SERVER_KEY>`; portul implicit documentat este `8642`, cu bind pe loopback. Configurația reală trebuie descoperită, nu presupusă.[2]

| Operație necesară Omnis | Contract Hermes existent | Ce completează Omnis |
|---|---|---|
| Descoperirea funcțiilor versiunii active | `GET /v1/capabilities` | Preflight și verificarea compatibilității; nu presupunem că toate versiunile au aceleași rute |
| Verificare runtime | `GET /health`, `GET /health/detailed` | Interpretarea stării din JSON; readiness degradat poate răspunde tot HTTP 200 |
| Catalog modele/provideri | `GET /api/model/options`, opțional `?refresh=1` | UI filtrat la cei doi provideri admiși; `/v1/models` nu este catalogul complet |
| Crearea conversației Brain | `POST /api/sessions` | Asociere durabilă engagement–session; sistemul de scope rămâne în Omnis |
| Începerea unui tur de lucru | `POST /v1/runs` | `session_id`, `input`, provider/model și cheie de idempotency; o rulare nu este întreg engagementul |
| Stare și rezultat | `GET /v1/runs/{run_id}` | Persistență proprie; modelul solicitat se distinge de `runtime` efectiv |
| Progres live | `GET /v1/runs/{run_id}/events` | Un consumator backend; stocare și retransmitere către UI, fără a trata SSE drept audit durabil |
| Istoric și rezultate întârziate | `GET /api/sessions/{session_id}/messages` | Reconciliere și continuarea Brainului, fără istorice client stale |
| Intervenție în timpul lucrului | `POST /v1/runs/{run_id}/steer` | Mesaj de operator; nu este un mecanism de schimbare a scope-ului |
| Approval Hermes | `POST /v1/runs/{run_id}/approval` | Asociere cu approval ID; separat de aprobările de risc Omnis |
| Stop | `POST /v1/runs/{run_id}/stop` | Revocarea acțiunilor, oprirea executorilor și verificarea stării terminale |
| Descoperire skills/toolsets | `GET /v1/skills`, `GET /v1/toolsets` | Catalogul permis și verificarea inventarului efectiv, inclusiv pentru copii |

Rutele de bază și semantica sunt documentate.[2] `steer` și schema precisă de approval au fost verificate și în `gateway/platforms/api_server_runs.py:1072–1178`. API-ul oferă și session chat/fork și API-uri OpenAI-compatible, iar **Sessions + Runs** este alternativa HTTP potrivită, nu parsarea CLI-ului sau a textului ANSI.[2][3]

### Secvență de pornire HTTP — alternativă, neexecutată

1. Omnis verifică autorizarea, scope-ul, identitățile necesare, bugetele și disponibilitatea providerului.
2. Creează sesiunea Hermes și păstrează ID-ul returnat.
3. Îngheață revizia inițială de engagement și configurația relevantă. Secretele nu intră în mesaj.
4. Creează turul de lucru cu o cheie de idempotency persistentă pentru acel tur.
5. Consumă SSE în backend și afișează evenimentele Omnis persistente în browser.

```http
POST /api/sessions
Content-Type: application/json
Authorization: Bearer <API_SERVER_KEY_DOAR_IN_BACKEND>

{"title":"Omnis · ENG_DEMO · Brain"}
```

```http
POST /v1/runs
Content-Type: application/json
Authorization: Bearer <API_SERVER_KEY_DOAR_IN_BACKEND>
Idempotency-Key: omnis-ENG_DEMO-brain-turn-0001

{
  "session_id": "<ID_RETURNAT_DE_HERMES>",
  "provider": "openrouter",
  "model": "<MODEL_VALID_ALES_DIN_CATALOG>",
  "input": "Începe engagementul ENG_DEMO. Încarcă snapshotul și taskurile prin uneltele Omnis."
}
```

Acestea sunt exemple cu substituenți expliciți, **nu payloaduri gata de rulat**. Pentru al doilea provider, slugul este `openai-codex`, cu un model disponibil contului. Nu trimitem parola de pe țintă, cheia OpenRouter sau grantul OAuth în prompt.[8]

```json
{"input":"Prioritizează suprafețele nou descoperite după autentificare."}
```

Ultimul payload se poate trimite la `/v1/runs/{run_id}/steer` numai când runul acceptă intervenții. Pentru approval folosim forma `{"request_id":"<ID_EXACT>","choice":"once"}` sau `"deny"`; nu expunem opțiuni globale de tip `always` în fluxul obișnuit Omnis. O aprobare Hermes nu autorizează implicit o acțiune în afara engagementului.

### Limite care schimbă implementarea

- **Toolseturile nu sunt câmpuri arbitrare per run.** `_create_agent`, `gateway/platforms/api_server.py:2195–2279`, le încarcă din configurația profilului/platformei pe traseul obișnuit. Putem pregăti un runtime Omnis restrâns și folosi capabilități de task în broker; nu presupunem că JSON cu `allowed_tools` modifică agentul.
- **Instrucțiunile suplimentare nu înlocuiesc întregul system prompt Hermes.** Comportamentul trebuie adaptat prin toolset, plugin și configurație, nu doar printr-un mesaj care spune „ești pentester”.[2]
- **SSE nu este un event log durabil cu replay garantat.** Codul folosește o coadă consumată, iar handlerul șterge transportul la închidere: `api_server_runs.py:481–482, 1016–1057`. Nu există aici un contract verificat de replay prin `Last-Event-ID`. Reconectarea browserului trebuie făcută la jurnalul Omnis; pierderea legăturii backend–Hermes cere reconciliere din status/istoric și din sursele de domeniu.
- **Progresul copiilor este incomplet pe SSE.** Sunt transmise `subagent.start` și `subagent.complete`, dar `subagent.tool`/progress ticks sunt omise; preview-ul rezultatului de tool este limitat la 500 de caractere. Nu extragem evidence sau endpointuri prin parsarea acestui preview.[2]
- **Idempotency nu înseamnă exact-once pe țintă.** Runs deduplică pornirea pentru 24 h după ultima actualizare a stării. O cerere HTTP cu efect incert după crash trebuie reconciliată separat, nu retrimisă automat.[2]
- **Stop nu înseamnă pauză/reluare a stivei de execuție.** Runul intră în `stopping`, apoi ajunge într-o stare terminală. Pauza de engagement și reluarea de la checkpoint sunt funcții Omnis.[2]

## 4. Settings: contractele existente, fără clonarea dashboardului

**Putem construi Settings aproape integral peste backendul existent al Hermes Dashboard.** Aceste rute REST detaliate sunt contracte interne dashboard/desktop observate la commitul auditat, nu un SDK public promis stabil. Le încapsulăm într-un adaptor mic, pin-uim versiunea și le acoperim cu contract tests. Capabilitățile administrative și autentificarea providerilor sunt documentate oficial.[7][8]

### Bootstrap local și autentificare administrativă

Există `hermes serve`, un backend headless cu REST-ul Dashboardului, fără build SPA. Recomand un `HERMES_HOME` dedicat Omnis, mediu controlat și `--isolated`, ca să nu ne atașăm sau să modificăm backendul personal existent. Exemple schematice, **neexecutate**:

```text
Mediu injectat de supervisor:
  HERMES_HOME=<DIRECTOR_OMNIS_SEPARAT>
  HERMES_DASHBOARD_SESSION_TOKEN=<SECRET_ALEATOR_PER_PORNIRE>

Argumente proces management:
  hermes serve --isolated --host 127.0.0.1 --port 0

Semnal readiness de verificat:
  HERMES_BACKEND_READY port=<PORT_ALOCAT>
```

În modul loopback fără gate extern, backendul Omnis folosește headerul `X-Hermes-Session-Token: <TOKEN_ADMIN>`. Acesta este alt secret decât `API_SERVER_KEY` și altul decât cheia OpenRouter. Verificăm `/api/health`, apoi un GET autentificat. Tokenul rămâne în backend. Dacă activăm un gate extern, contractul de autentificare se schimbă; tokenul local nu îl substituie.

Dovezi: `hermes_cli/main_dashboard.py:810–901`, `hermes_cli/web_server.py:317–445`, `hermes_cli/subcommands/dashboard.py:15–59`. Loopback/tokenul nu izolează backendul de alte procese locale ale aceluiași utilizator. Omnis trebuie să adauge propriile controale de acces local, Origin/CSRF și protecția secretelor.

### OpenRouter

Toate exemplele folosesc `<PROFILE_ID>` ca substituent. Într-un `HERMES_HOME` separat se poate folosi profilul `default` al acelui runtime, nu profilul personal al utilizatorului. Adaptorul fixează profilul server-side; nu primește căi de filesystem arbitrare din browser.

| Operație | Contract Dashboard | Semantica importantă |
|---|---|---|
| Stare cheie | `GET /api/env?profile=<PROFILE_ID>` | Pentru `OPENROUTER_API_KEY`: `is_set`, `redacted_value`; existența în fișier nu dovedește validitatea sau creditul |
| Test cheie | `POST /api/providers/validate` | Body `key`, `value`, `profile`; rezultat `ok`, `reachable`, `message`; nu salvează cheia |
| Salvare/actualizare | `PUT /api/env` | Același body; rezultat `ok`, `key`, `config_updates` |
| Ștergere cheie | `DELETE /api/env` | Body `key`, `profile`; elimină și oglinzile/env pool asociate; poate păstra alte credențiale independente |

```json
{"key":"OPENROUTER_API_KEY","value":"<CHEIE_INTRODUSA_SECURIZAT>","profile":"<PROFILE_ID>"}
```

Acesta este un exemplu de schemă, nu o cheie și nu un request executat. Testul face o cerere externă de verificare a cheii. Codul acceptă și HTTP 429 ca `ok:true, reachable:true`: **nu etichetăm asta drept inferență disponibilă**. O inferență de probă este altă operație, explicită și potențial facturabilă. Dovezi: `web_routers/config_env.py:232–316,887–972`, `web_models.py:15–25`, relative la `hermes_cli/`.

### ChatGPT/Codex — provider nativ, nu plugin nou

Slugul este **`openai-codex`**. Device-code OAuth nativ nu cere instalarea Codex CLI. Nu extragem sau copiem refresh tokens în Omnis și nu avem nevoie de subscription proxy între Omnis și agentul Hermes.[8]

| Operație | Contract Dashboard | Ce folosește Omnis |
|---|---|---|
| Status provider | `GET /api/providers/oauth?profile=<PROFILE_ID>` | Rândul `id=openai-codex`, starea loginului și sursa credentialului |
| Început login | `POST /api/providers/oauth/openai-codex/start?profile=<PROFILE_ID>` | Fără body; întoarce `session_id`, `flow`, `user_code`, `verification_url`, `expires_in`, `poll_interval` |
| Urmărire | `GET /api/providers/oauth/openai-codex/poll/{session_id}?profile=<PROFILE_ID>` | `pending`, `approved`, `expired`, `error`; schema generică include și `denied` |
| Anulare login pending | `DELETE /api/providers/oauth/sessions/{session_id}?profile=<PROFILE_ID>` | După anulare, poll poate întoarce 404; nu există rezultat durabil `cancelled` |
| Deconectare profil | `DELETE /api/providers/oauth/openai-codex?profile=<PROFILE_ID>` | Eliminare locală, nu revocare upstream și nu anulare implicită a loginurilor pending |

UI-ul arată URL-ul și codul în fluxul securizat de autentificare; utilizatorul aprobă la provider. Omnis doar urmărește starea. `approved` înseamnă că Hermes a salvat grantul în propriul store, nu că a fost deja verificată o inferență sau selectat defaultul modelului.

**Capcane care trebuie tratate:**

- Toate rutele, inclusiv poll, necesită autentificarea dashboardului. Comentariul local „no auth” al pollului nu descrie middleware-ul efectiv.
- Folosim același profil la start, poll și cancel; nepotrivirea este refuzată.
- `/submit` nu implementează introducerea unui cod pentru Codex: răspunde 400. CLI-ul oferă și PKCE browser, dar această rută REST `start` este device-code; nu promitem un fallback PKCE REST inexistent.
- Start poate da 504 înainte ca workerul de login să termine. Evităm retry automat nelimitat, fiindcă o sesiune pending poate exista deja fără ID primit de client.
- Pending sessions sunt în RAM și se pierd la restart. Logout anulează întâi loginurile pending cunoscute, apoi șterge și recitește statusul. Fallbackul către credențiale externe/root trebuie exclus prin izolarea mediului și testat; altfel contul poate reapărea conectat.
- Câmpurile de status despre refresh/expirare nu reflectă complet store-ul Codex în această versiune; nu deducem absența refresh tokenului din `has_refresh_token:false`.

Dovezi: `hermes_cli/web_routers/oauth.py:264–305,619–795`, `hermes_cli/auth_codex.py:153–193`. Contractul tehnic nu garantează eligibilitatea fiecărui abonament, cota sau drepturile de redistribuire; documentația Hermes lasă detalii ale cotelor/planurilor neprecizate.[8]

### Catalog și selecție de modele

- `GET /api/model/options?profile=<PROFILE_ID>&refresh=false&include_unconfigured=false&explicit_only=true` — filtrăm în Omnis la OpenRouter/Codex. Discovery/pricing pot accesa rețeaua.
- `POST /api/model/set` — alegerea defaultului pentru sesiuni noi, nu hot-swap garantat pentru agenții existenți.

```json
{
  "scope":"main",
  "provider":"openai-codex",
  "model":"<MODEL_ALES_DIN_CATALOG>",
  "profile":"<PROFILE_ID>",
  "confirm_expensive_model":false
}
```

Nu trimitem cheia prin această operație. HTTP 200 poate conține `ok:false, confirm_required:true`: Omnis cere acord, nu anunță succes. `stale_aux` semnalează configurații auxiliare rămase separat. Configurația Brain, delegare, auxiliare și fallback trebuie verificată împreună, nu doar dropdownul principal. Dovezi: `hermes_cli/web_routers/models.py:101–131,275–318`.

### Ce administrare restrângem

Există `GET/POST /api/profiles`, `GET/PUT /api/config`, `GET /api/tools/toolsets`, `PUT /api/tools/toolsets/{name}`, `GET /api/skills`, `PUT /api/skills/toggle`. Nu le expunem ca proxy generic în Omnis. Crearea de profil nu clonează implicit `.env` personal; configurarea tools/skills se face dintr-un manifest aprobat, la sesiuni noi. Nu expunem `/api/env/reveal` și nu retransmitem întregul config: configurațiile legacy pot conține secrete.

Hermes rămâne proprietarul `.env`, `auth.json` și `config.yaml` din mediul său; Omnis păstrează referințe și stare de interfață. Setările se salvează prin API, se recitesc pentru verificare și se aplică la o limită sigură, nu schimbând mediul unui agent activ.

**Identitățile țintei sunt separate de credențialele AI.** Omnis are seif/referințe pentru cookie, token sau Basic Auth, injectate numai de executor în originea autorizată. Loginul asistat se face în browserul izolat al engagementului, fără a preda agenților întregul browser personal.

## 5. Orchestrarea: delegare nativă, cu host JSON-RPC

**Recomandarea finală a auditului este `delegate_task` nativ + host Omnis pe JSON-RPC**, cu plugin pentru instrumentele de pentest și evenimentele de domeniu. Nu recomand actualul `ctx.subagent_lifecycle` ca bază principală a MVP-ului. Interfața este publică, dar nu oferă paritate cu delegarea standard.[3][4][5]

### Comparația mecanismelor reale

| Mecanism | Ce oferă | Limită decisivă / alegere |
|---|---|---|
| `delegate_task` + JSON-RPC | Contexte noi, loturi de copii, rezultate, output schema, list/steer/stop; hostul poate controla copiii și primi progres | **Preferat.** Provider/model din configurația delegării/moștenire, nu arbitrar în fiecare task; Omnis aplică autoritatea pe efecte |
| `ctx.subagent_lifecycle` | launch/status/wait/cancel/result/reconnect, model per launch, `allowed_toolsets` | Fără steer, provider per launch, skills sau output_schema; operațiile verifică parentul activ; rezultate în proces |
| `/v1/runs` independente | HTTP, provider/model explicit, status/SSE/stop/steer pentru fiecare worker | Alternativă dacă prioritatea devine HTTP-only și workeri rădăcină independenți; Omnis preia mai multă coordonare |
| Kanban | Taskuri/attempturi și dependențe durabile, workeri pe profiluri | Posibil ulterior; nu este necesar pentru primul arbore de specialiști scurți și nu înlocuiește DB de pentest |

Nu confundăm API-ul de integrare al hostului cu unealta expusă modelului. Brainul apelează **`delegate_task`**; backendul Omnis vorbește **JSON-RPC** cu sesiunea Brain și cu managementul copiilor. Sunt două niveluri ale aceluiași mecanism, nu două frameworkuri de agenți.

### De ce nu alegem lifecycle API ca fundație

Am verificat `agent/subagent_lifecycle.py:245–280,335–389`, nu doar descrierea din documentație:

- inclusiv managementul handle-ului depinde de parentul activ; un handle serializat nu devine automat controlabil dintr-un request HTTP exterior;
- lipsesc `steer`, provider, output_schema și subscribe/callback public; `structured_payload` există în dataclass, dar nu este populat pe traseul citit;
- launch folosește `DEFAULT_MAX_ITERATIONS`, nu rezolvarea standard a configurației `delegation`; nu presupunem aceleași pinuri provider/model și aceleași controale de admission;
- timeout per launch, working directory și per-tool blocking sunt respinse; `allowed_toolsets` poate restrânge, nu lărgi;
- rezultatul `SUCCEEDED` nu garantează finalizarea investigației sau validitatea findingului; starea se pierde la restart, iar retenția terminală este de o oră.[5]

În plus, la acest commit parametrul legacy `role` este ignorat de constructorul copilului: dreptul de a delega este calculat din adâncime și configurație (`tools/delegate_tool.py:187–191`). Pentru un arbore plat dezactivăm delegarea imbricată prin configurația reală și verificăm uneltele rezolvate; `role="leaf"` în prompt sau request nu este o graniță de securitate.

### Ce păstrăm din Hermes

Brainul folosește `delegate_task` pentru investigații și lansează un copil nou pentru validare. Schema model-facing acceptă `tasks[].goal`, `context`, `output_schema`, `images`, `group` și acțiunile `spawn/list/steer/stop`. Nu acceptă selecții arbitrare de provider/tools/skills per copil; modelul comun și toolseturile restrânse ale runtime-ului sunt suficiente pentru prima versiune (`tools/delegate_tool.py:634–726`).[4]

Pluginul Omnis înregistrează unelte prin `ctx.register_tool`, fără să rescrie tool loop, provideri, auth sau compresie.[10] Nume **propuse**, nu funcții existente: `omnis_context`, `omnis_surfaces`, `omnis_prepare_task`, `omnis_report_signal`, `omnis_submit_result`.

Un task este pregătit în Omnis înainte de delegare. Brainul primește un briefing restrâns și o referință de task; pluginul corelează delegarea și copilul cu acel task. **Asocierea trebuie legată de sesiunea reală/capabilitatea emisă de backend, nu autorizată printr-un task_id scris liber de LLM.** Copilul neasociat poate raționa, dar brokerul refuză orice acces la țintă. Această legătură este un criteriu critic pentru I0; nu pretindem că API-ul nativ are deja un câmp generic de task Omnis.

Observer hooks oferă sesiune părinte/copil, turn, task și tool-call IDs, cu diferențe între evenimente. Omnis stochează mapping-ul propriu; nu presupune un `run_id` comun peste REST, RPC și copii. `subagent_stop` poate fi corelat prin `child_session_id`; evenimentele pot sosi înaintea răspunsului de spawn.[6]

### Cine trezește Brainul — diferență importantă între transporturi

**HTTP Runs:** completarea detached se persistă în istoricul serverului, dar nu pornește automat un tur de model; clientul deține continuarea.[2]

**TUI gateway / JSON-RPC:** codul `tui_gateway/session_notifications.py:148–168,459–544,690–737` are poller nativ, claim al turului și `_notif_submit` pentru completările delegării. Poate relansa agentul când sesiunea este disponibilă. Așadar, **nu rescriem în Omnis acest wake pentru fiecare copil și nu generalizăm limita HTTP la tot Hermes**. Documentația descrie inclusiv tururile pornite de completări async și starea lor la reconnect.[3]

Pentru evenimentele specifice pentestului — identitate nouă, hartă modificată, semnal intermediar, aprobare — construim un inbox durabil Omnis și un dispatcher serializat:

```text
Copilul observă o anomalie
  → omnis_report_signal: tip, observație, evidence refs
  → broker validează autoritatea și persistă evenimentul
  → harta și dashboardul se actualizează
  → dacă Brainul rulează: session.steer / citire de delte
    dacă este idle și continuarea este permisă: prompt.submit
  → fără duplicarea completării native de delegare
```

Nu invocăm reentrant modelul dintr-un observer callback. Grupăm deltele, verificăm bugetul și starea engagementului și deduplicăm după eveniment/attempt. Dacă se folosește alternativa HTTP, dispatcherul trebuie să preia explicit și continuarea rezultatelor copiilor.

### Bugete și stări

Delegarea nativă are limite de lot/iterații și mecanisme de stagnare, dar acestea nu constituie automat un buget comun de campanie. Copiii primesc bugete noi; timeoutul configurat pentru inactivitate nu este un deadline total. Omnis controlează separat durată, trafic, concurență și rezervă pentru validare. Rezultatele `completed` cu `schema_valid:false` se păstrează pentru triere, nu se promovează la findings.[4]

O sesiune Brain poate avea multe tururi. `message.complete`, `run.completed`, `subagent.complete` și `SUCCEEDED` sunt stări de runtime, nu `engagement.completed`. Închiderea engagementului se decide din starea Omnis și din precondițiile de raportare. Nu lăsăm wake-ul nativ să ocolească pause/stop/bugete: brokerul revocă efectele imediat, iar hostul trebuie să oprească/dreneze runtime-ul dacă nu poate garanta suspendarea continuărilor; acest caz este test obligatoriu în I0.

## 6. Fluxul MVP: etape cu bucle, nu o conductă rigidă

### A. Preflight

Autorizație și reguli de engagement, ținte și excluderi, identități, fereastră, bugete, verificarea providerului, verificarea politicii de rețea și readiness. Absența loginului este validă; nu blochează reconul neautentificat.

### B. Recon inițial și incrementări

- Crawl HTTP și crawl/browser pentru suprafețe dinamice autorizate.
- Linkuri, formulare, metode, parametri observați în query/path/body/header/cookie, JSON și cereri browser.
- `robots.txt`, sitemap și specificații API disponibile legitim.
- Headere, cookies, indicii de tehnologie/versiune și metadate de răspuns.
- JS: inventar fișiere, legături între surse, extragere de rute și parametri, comentarii relevante.
- Descoperire bounded de directoare/fișiere și parametri, în limita ratei și a scope-ului.
- Proveniență și de-duplicare; semnale de soft-404, redirect, pagină de login și rate limiting tratate explicit.

**Corecție:** fuzzingul de directoare este activ, nu „pasiv” doar fiindcă este în recon. O rută găsită într-un JS este mai întâi **inferred**, nu endpoint live confirmat. Un banner de versiune sau un header absent nu dovedește automat o vulnerabilitate.

Reconul are un buget și un punct de livrare inițial, dar continuă pe delta: noi identități, noi rute, inputuri sau răspunsuri neobișnuite. Putem testa o suprafață suficient documentată înainte de a epuiza tot crawlul.

### C. Analiză și generare de ipoteze

Brainul citește rezumatul hărții, matricea de acoperire și vecinătățile relevante. Creează taskuri cu suprafață, identitate, clasă de problemă, observație suport, semnal așteptat, control sigur, buget și motiv de prioritate.

Nu cerem „găsește vulnerabilități peste tot” fiecărui copil. Un task bun delimitează o ipoteză verificabilă și drepturile necesare.

### D. Workeri de investigație

Fiecare copil lucrează într-un context proaspăt și pe un task îngust. Poate raporta:

- candidat susținut de observații;
- comportament negativ/control sigur;
- rezultat neconcludent sau blocaj;
- suprafață nouă;
- ipoteză alternativă apărută în investigație.

Un comportament neașteptat devine un eveniment de replanificare, nu o permisiune pentru copil de a lărgi singur scope-ul sau de a testa altă identitate. Același broker verifică fiecare acțiune nouă.

### E. Validare independentă și raport

Un candidat pozitiv trimis de investigator este dat unui **copil nou**, cu o sesiune de execuție proaspătă, aceleași identități/precondiții autorizate necesare reproducerii și context minim. Același provider/model poate fi folosit în MVP; separarea de context nu garantează independența erorilor. Diferența decisivă o fac replay-ul, controlul negativ și dovada observabilă.

După verdict, actualizăm harta, matricea și taskurile dependente. La final generăm raportul numai din findinguri confirmate și adăugăm explicit limitele și suprafețele netestate.

## 7. Harta tip Burp: mai mult decât un arbore de URL-uri

UI-ul poate arăta `host → path → metodă → parametri`, dar baza de date trebuie să păstreze observațiile care nu încap într-un arbore.

| Entitate Omnis propusă | Ce trebuie să păstreze |
|---|---|
| Engagement / ScopeRevision | Autorizație, originuri/ținte, excluderi, reguli, interval, bugete, revizie |
| Identity / AuthContext | Anonim sau cont/rol; principal/ownership, referință secret, cookie jar/browser context separat, expirare, `auth_epoch` și dovadă pozitivă de login |
| Surface / Operation | Origin, metodă, cale brută și rută normalizată numai când este justificată, content-type, sursă |
| Parameter / Observation | Nume, locație, tip observat, identitate/stare, exemplare redactate, `inferred`/`observed` și evidence refs |
| Relationship | JS referă rută; formular trimite request; identitate accesează operație; evidence susține candidat |
| Task / Attempt | Ipoteză, rol, snapshot, dependențe, lease, limită, model efectiv, stare și rezultate |
| Evidence / Validation | Request/response, diferențe/control, screenshot dacă este necesar, timestamp, hash, identitate și încercare |
| Finding / Report | Verdict demonstrat, impact și limitări, referințe verificabile, versiune și retest |

Normalizarea nu trebuie să unească din greșeală resurse cu politici diferite. Păstrăm URL-ul/cererea originală ca evidence, iar ruta normalizată este o vedere separată. Identitățile nu se amestecă în aceleași sesiuni de browser sau cookies.

Pentru agent, harta nu este un screenshot: expunem unelte de interogare cu filtre, paginare și snapshot. Exemple de nume **propuse**: `omnis_context`, `omnis_surfaces`, `omnis_evidence`, `omnis_tasks`, `omnis_submit_result`, `omnis_report_signal`. Nu expunem direct SQL și nu punem tot graful în fiecare prompt.

### Autentificare, browser și schimbarea contextului

Un browser autentificat și un client HTTP cu cookie copiat nu au obligatoriu aceeași stare: tokenuri JS, CSRF, refresh și workflow pot diferi. Fiecare identitate are context propriu, verificare pozitivă a principalului/rolului și `auth_epoch`. Nu deducem succesul loginului numai din lipsa unui 401.

La expirare sau drift blocăm taskurile dependente și marcăm intervalul incert `AUTH_BLOCKED/INCONCLUSIVE`; nu îl contabilizăm ca test negativ. Loginul asistat redeschide descoperirea post-auth într-o revizie nouă. Accesul necesar către IdP/CDN se poate aproba separat ca dependență funcțională, **nu ca autorizație de pentest asupra acelui terț**.

Analiza statică JS, execuția browser și testarea DOM XSS sunt capabilități diferite. Faptul că avem browser nu înseamnă că am implementat toate verificările JavaScript.

## 8. Findings confirmate: verificatorul nu votează adevărul

Flux propus:

```text
CANDIDATE → INVESTIGATING → VALIDATING
                              ├─ CONFIRMED
                              ├─ REJECTED
                              └─ INCONCLUSIVE
```

Un finding poate deveni `CONFIRMED` numai dacă validatorul produce dovezi suficiente pentru clasa respectivă și serviciul de validare verifică precondițiile și integritatea lor. Simplul „am confirmat” din textul LLM nu satisface condiția.

- **Control de acces:** relația rol/ownership trebuie cunoscută și autorizată. Diferența dintre două răspunsuri sau simplul status 200 nu demonstrează acces nepermis.
- **XSS:** un marker reflectat nu este același lucru cu execuție în browser. Validarea trebuie să distingă textul inert de contextul executabil, într-un browser izolat.
- **SQLi:** o eroare generică sau o întârziere singulară nu ajunge. Oracle-ul și controalele trebuie definite înainte; fără acces distructiv sau extragere de date sensibile pentru a „face dovada mai convingătoare”.
- **Expunere de informații:** relevanța și sensibilitatea trebuie demonstrate; headerele și fingerprintul rămân observații când impactul nu este stabilit.

**Pachetul inițial recomandat pentru aprobare:** control de acces la obiecte între identități autorizate (IDOR/BOLA), XSS reflectat și path traversal read-only limitat la un fișier-canary autorizat. Pentru ultima familie nu folosim citirea secretelor reale drept probă. Acoperim astfel identitate/ownership, browser și o clasă server-side cu oracle de laborator explicit.

SQLi general, stored/DOM XSS, SSRF/OAST, race conditions, upload executabil și chains rămân în afara adâncimii inițiale, chiar dacă reconul descoperă suprafețe unde ar putea fi relevante. Explicația SQLi de mai sus arată ce ar cere o validare serioasă, nu promite suport MVP. **Catalogul rămâne de aprobat**, iar semnalele nesuportate apar ca ipoteze/zone neevaluate, nu findings certificate.

`INCONCLUSIVE` nu este `REJECTED`. Expirarea sesiunii, WAF/rate limit, target schimbat, lipsa unei identități sau epuizarea bugetului nu demonstrează false positive. Păstrăm motivele și permitem retest când precondițiile se schimbă. Măsurăm și false negatives pe laborator; un sistem care respinge orice candidat nu este unul bun doar pentru că nu raportează FP.

## 9. Dashboard live și coverage fără procente înșelătoare

### Ecrane MVP

1. **Engagement setup:** ținte, scope/excluderi, autorizație, identități, profil de risc, bugete, provider/model.
2. **Overview live:** faze active, taskuri, workeri, approval queue, trafic/rate, buget, blocaje, progres și status real.
3. **Target map:** tree și tabel, filtre după metodă/identitate/stare/sursă; inspector de parametri, comentarii, request/response și provenance.
4. **Investigații:** candidat → investigator → validator, rezultate negative, neconcludente și taskuri blocate.
5. **Findings:** numai confirmate în vederea principală, cu replay/evidence și revizii; candidații rămân separat.
6. **Raport:** constatări demonstrate, metodologie, identități testate, acoperire și limite, export HTML/JSON; PDF printr-un flux de print/export ulterior validat.
7. **Settings:** cei doi provideri AI și statusul runtime-ului, fără întregul panou administrativ Hermes.

### Sursele de date live

REST SSE și evenimentele JSON-RPC Hermes oferă telemetrie de execuție. Observer hooks pot furniza corelare pentru sesiuni, requesturi LLM, tooluri și copii, însă sunt contracte de observabilitate, nu un jurnal probatoriu obligatoriu.[6]

**Brokerul și parserii Omnis emit evenimentele de domeniu direct:** suprafață observată, identitate validată, probă înregistrată, task schimbat, candidat nou și verdict. Nu lăsăm un LLM să estimeze câte endpointuri există din povestea conversației. Scrierea stării și a evenimentului se face atomic, cu ID și ordine de evenimente per engagement. Browserul poate relua de la cursorul Omnis.

### Ce înseamnă coverage

Nu putem cunoaște procentul dintr-o aplicație necunoscută care a fost descoperit doar din crawling. Afișăm separat:

- **Discovery:** suprafețe observate, deduplicate; rute doar inferate separat; frontieră vizitată/rămasă și zone blocate.
- **Exercise coverage:** operații cunoscute pentru care există interacțiune în contextul unei anumite identități.
- **Test coverage:** matrice `operație × parametru relevant × identitate/stare × familie de verificare aplicabilă`.
- **Validation coverage:** candidați cu verdict versus candidați încă nevalidați.

Stările includ `not_tested`, `queued`, `running`, `tested_no_issue`, `candidate`, `confirmed`, `inconclusive`, `blocked`, `not_applicable`. Un rezultat „fără problemă observată” este legat de test și snapshot; nu certifică endpointul ca sigur pentru orice vulnerabilitate.

Orice procent derivat trebuie să aibă un numitor explicit, versiunea snapshotului și excluderile vizibile. Aplicabilitatea necunoscută și taskurile blocate nu se elimină pentru a îmbunătăți artificial scorul; numai `not_applicable` justificat poate fi exclus. Numitorul gol se afișează `N/A`, nu „100%”. Dacă loginul descoperă suprafețe noi, numitorul crește; coverage poate scădea fără ca sistemul să fi pierdut progres. Nu promitem „100% din aplicație”.

## 10. Autonomie controlată, pauză și recuperare

**Scope-ul este cod, nu prompt.** Include originuri, porturi, căi și excluderi, identități, tipuri de acțiune, rate și limite. Fiecare request, redirect, cerere de browser și acțiune copil trebuie să treacă prin aceeași verificare. Un firewall pe IP singur nu distinge căile sau aplicațiile găzduite pe aceeași infrastructură.

Mediul de execuție nu are voie să ocolească brokerul prin shell, browser stock, MCP arbitrar sau trafic direct. Informațiile despre țintă sunt input neîncrezător; o pagină care „cere” extinderea scope-ului nu este o aprobare. Containerele și mecanismele de securitate Hermes ajută, dar nu constituie singure dovada confinării cerute de Omnis.[9]

### Acțiuni ale operatorului

- **Pause:** oprește admiterea taskurilor noi, lasă numai acțiunile deja admise să se încheie în limitele lor; UI arată `PAUSING` până când condiția este îndeplinită.
- **Stop:** revocă permisiunea de noi efecte, trimite stop/cancel, oprește procesele executorilor și verifică lipsa activității. `STOPPING` nu se afișează ca `STOPPED` prematur.
- **Resume:** revalidează scope/identități/provider, reconciliază taskurile și pornește tururi noi din checkpoint; nu pretinde că reia un thread Python mort.
- **Aprobări:** legate de acțiunea exactă, argumente, target, identitate, revizie și expirare. Nu folosim „aprobare permanentă pentru orice”.

Recon, task, worker, fază și engagement primesc bugete și criterii de oprire. Retestul se justifică prin dovezi noi, identitate nouă, schimbare de stare ori un motiv înregistrat; detectăm repetarea fără informație nouă. Când limita oprește munca, rezultatul este **LIMITED**, nu „pentest complet”.

Bugetele de cereri/timeouts/concurență se pot impune în broker. Costul AI necesită contabilizarea cererilor părintelui, copiilor, retry-urilor și operațiilor auxiliare, fără dublarea agregatelor. Un cost calculat după răspuns este un **prag estimativ de oprire**, nu un plafon financiar exact; hard cap cere un mecanism înaintea apelului sau o limită impusă de provider. Cotele abonamentului nu se inventează în UI.[6][8]

Dacă Hermes cade, Omnis păstrează taskurile și dovezile. Operațiile cu rezultat extern necunoscut devin `UNKNOWN/NEEDS_RECONCILIATION`, nu „failed, retry imediat”. Metodele HTTP nu garantează singure lipsa efectelor secundare. Dacă aceeași acțiune poate modifica date, repetarea ei cere reconciliere sau aprobare.

## 11. Ce este fezabil, ce necesită lucru și ce nu promitem

| Funcție solicitată | Verdict pentru MVP local | Condiție / muncă reală |
|---|---|---|
| UI propriu care conduce Hermes | Fezabil pe contracte existente | Host JSON-RPC, adaptor REST pentru Settings, procese private; contract tests |
| OpenRouter și Codex în Settings | Fezabil tehnic | Integrare management/OAuth și verificare live cu acord; drepturile/cotele contului rămân externe |
| Recon HTTP + JS + browser + fuzzing bounded | Fezabil de construit | Tool adapters, captură, parseri, state/auth, politici; nu vine gata din Hermes |
| Sitemap tree cu parametri și provenance | Fezabil de construit | Model de date și UI Omnis; dedup fără pierderea identității/contextului |
| Brain cu workeri scurți și validator | Fezabil pe mecanisme Hermes | Delegare nativă, plugin și task ledger; corelare și delte event-driven |
| Live pentru fiecare acțiune relevantă | Parțial nativ | RPC pentru progresul copiilor; evenimente de domeniu și telemetrie plugin pentru datele canonice |
| Bucle post-auth și descoperiri neașteptate | Fezabil de construit | Snapshoturi/delta, prioritate, dedup și condiții de retest |
| Findings confirmate cu evidence | Fezabil pentru catalog explicit | Oracle-uri per clasă, replay și control; nu simplă încredere în verdictul LLM |
| Pause/stop/recovery de engagement | Nu este livrat integral de API | Omnis state machine + revocare/oprire/reconciliere verificată |
| Coverage completă a oricărei aplicații | Nu este o promisiune defensabilă | Raportăm ce știm și ce am testat, cu limite |
| Zero false positives / zero false negatives | Nu garantăm | Evaluare pe exemple vulnerabile și controale sigure, cu inconclusive separat |
| Children care supraviețuiesc restartului | Nu prin lifecycle API actual | Restart/replay controlat la nivel de task, nu învierea contextului de execuție |
| Chains multi-etapă, SSO/MFA autonom, SaaS multi-client | Post-MVP | Cerințe și model de risc distincte |

**Nu alegem încă un fork.** Dacă testele arată o lipsă punctuală imposibil de rezolvat prin plugin/adaptor, documentăm exact hookul necesar și evaluăm un patch upstream/fork minimal. Nu copiem auth/provider runtime doar pentru a evita două endpointuri de management.

## 12. MVP mai ambițios, livrat incremental

Experimentul tehnic este **poarta de intrare**, nu plafonul produsului. MVP-ul final trebuie să conțină fluxul complet descris de utilizator.

| Increment | Ce trebuie să existe | Probă de acceptare |
|---|---|---|
| I0 — contracte și limite | Host RPC, Settings pentru cei doi provideri, un copil și legătura de task, cancel; REST ca alternativă documentată | Contraste între versiune/docs verificate; login/reautentificare reală; comportament la crash și ieșire din scope |
| I1 — engagement și hartă live | Setup, identități opționale, recon HTTP/browser/JS, tree și evidence | Descoperiri live deduplicate, toate cererile atribuibile, login expirat semnalat, excluderi respectate |
| I2 — investigații și verificator | Brain, taskuri scurte, catalogul agreat, validator nou | Caz vulnerabil și control sigur pentru fiecare clasă; inconclusive nu devine FP; dovezile se pot reproduce |
| I3 — bucle și închidere | Post-auth incremental, reprioritizare, bugete, pause/stop/recovery, raport | Suprafața nouă redeschide taskuri relevante; refresh UI nu pierde progres; restart nu repetă mutații; raportul nu inventează rezultate |

### Teste obligatorii înainte de a-l numi MVP

- Schimbarea providerului nu expune chei în browser, mesaje sau loguri; fallbackul nu trece neobservat către un provider nepermis.
- Grant expirat/revocat și rate limit apar corect; „configurat” nu este afișat drept „testat”.
- Brain și copil corelează fiecare acțiune cu taskul și cu evidence, fără acces la identitatea altui task.
- Streamul browserului poate fi reconectat din jurnalul Omnis; căderea fluxului Hermes nu șterge harta/dovezile.
- Finalizarea detached folosește wake-ul nativ o singură dată; dispatcherul Omnis nu îl dublează. Pause/stop/bugetele împiedică efecte noi și continuări nepermise.
- Redirect, DNS schimbat, IPv6, subresurse browser și tool alternativ nu pot depăși scope-ul. Accesul la metadata, host și control plane este blocat dacă nu face parte din laboratorul autorizat.
- O pagină ostilă nu poate transforma instrucțiuni din target în autoritate, nu poate confirma singură un finding și nu execută scripturi când evidence este afișat în dashboard.
- Două identități de test și controlul negativ rămân distincte; sesiunea expirată nu produce verdict de vulnerabilitate.
- Pentru fiecare familie aprobată există fixture vulnerabil și fixture remediat, resetabile și separate de exemplele de dezvoltare. Dovezile trebuie să reproducă problema pe primul și să nu promoveze controlul sigur; orice abatere blochează publicarea acelei capabilități ca verificată.
- Stop verifică executori și copii, iar resume după crash reconciliază rezultatele incerte.
- Raportul final referă numai evidence existente și include explicit identități, teste neefectuate și limitări.

Nu atribui durate exacte sau procente de cod reutilizat fără aceste probe. Partea costisitoare nu este conectarea butonului Start la Hermes; este calitatea hărții, execuția observabilă, autenticitatea dovezilor și comportamentul sigur al buclelor.

## 13. Diferențe față de propunerea precedentă

1. Local-first și setul de autentificări clarificate înlocuiesc planificarea inițială orientată și spre o echipă/VPS.
2. Providers restrânși la OpenRouter și Codex; Settings este fațadă peste managementul existent, nu rescriere auth.
3. Delegarea nativă Hermes, controlată prin host JSON-RPC, este preferată unui wrapper peste actualul lifecycle API; limitările acestuia sunt documentate.
4. Separăm wake-ul nativ al delegării în runtime-ul RPC de continuările specifice pentestului și de limita HTTP, unde clientul deține următorul tur.
5. Browser recon, recon post-auth, hartă cu proveniență, feedback loops și validator sunt ținte MVP, nu toate împinse după el.
6. Snapshot/coverage/verdict/evidence devin entități de produs, nu text derivat din chat.
7. S0/I0 rămâne un experiment tehnic obligatoriu, dar MVP-ul nu se reduce la el.

**Decizii încă deschise:** catalogul exact de verificări pentru prima versiune, aplicațiile de laborator și fixture-urile pentru controale, limita inițială de concurență și alegerea definitivă a stackului. Acestea nu anulează fezabilitatea integrării, dar trebuie închise înainte de estimare și implementare.

## 14. Dovezi din cod și nivelul de verificare

Căile de mai jos sunt relative la checkoutul Hermes menționat la început. Liniile sunt ancore pentru commitul auditat, nu un contract de stabilitate după upgrade.

| Sursă | Constatare |
|---|---|
| `gateway/platforms/api_server.py:2195–2279` — `_create_agent` | Config/platform toolsets; construcție agent și rutare |
| `gateway/platforms/api_server.py:2334–2349` — `_handle_model_options` | Catalog îmbogățit diferit de `/v1/models` |
| `gateway/platforms/api_server.py:2944–3009` — `_handle_create_session` | Creare atomică a unei sesiuni reale |
| `gateway/platforms/api_server_runs.py:567–703` — `_handle_runs` | Body input/session/provider/model, idempotency, continuare istoric |
| `gateway/platforms/api_server_runs.py:267–301` — `_make_run_event_callback` | Evenimente copii selective; omiterea progresului per tool copil |
| `gateway/platforms/api_server_runs.py:481–482, 1016–1057` | Coadă SSE consumată și curățarea transportului; fără replay durabil verificat |
| `gateway/platforms/api_server_runs.py:1072–1178` | Schema approval, steer și stop |
| `agent/subagent_lifecycle.py:24–75, 148–161` | Contracte publice, limite, retenție în proces și thread pool |
| `agent/subagent_lifecycle.py:245–280,335–389` | Lipsa parității cu delegarea standard; parent activ și rezultate limitate |
| `tools/delegate_tool.py:187–191,634–726` | Rol derivat din configurație/adâncime; schema delegării native |
| `apps/shared/src/gateway-contract.openrpc.json` | Parametrii și rezultatele metodelor RPC folosite în exemple |
| `tui_gateway/methods_subagents.py:53–113` | List/interrupt/tail cu ownership de sesiune/transport |
| `tui_gateway/session_notifications.py:148–168,459–544,690–737` | Completări async care pot porni nativ următorul tur în runtime-ul RPC |
| `hermes_cli/web_server.py:317–445` | Tokenul local pentru management |
| `hermes_cli/web_routers/config_env.py:232–316,887–972` | Stare/salvare/validare/ștergere OpenRouter |
| `hermes_cli/web_routers/oauth.py:264–305,619–795` | OAuth Codex start/poll/cancel/logout |
| `hermes_cli/web_routers/models.py:101–131,275–318` | Catalogul management și model assignment |

**Verificat aici:** documentație oficială, source inspection și corelarea traseelor importante. **De verificat în I0:** apeluri reale, OAuth, izolarea și oprirea, durata/rata/costul, evenimentele plugin sub sarcină și recuperarea. Nu sunt prezentate numere de benchmark sau rezultate de scanare fabricate.

## Sources

[1] https://hermes-agent.nousresearch.com/docs/llms.txt
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[4] https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
[5] https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api
[6] https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks
[7] https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
[8] https://hermes-agent.nousresearch.com/docs/integrations/providers
[9] https://hermes-agent.nousresearch.com/docs/user-guide/security
[10] https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
