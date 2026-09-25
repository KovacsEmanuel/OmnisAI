# Omnis — arhitectura MVP, baseline v1

**25 septembrie 2026 · Specificație pentru implementare · Produs neimplementat**

## 1. Autoritate și domeniu

Acest document închide alegerile de arhitectură pentru MVP-ul local cerut. [Planul revizuit](Omnis_Implementation_Plan.md) stabilește ordinea și porțile; [stackul](Omnis_Stack_Baseline.md) stabilește versiunile și limitele verificării; [UI/UX](Omnis_UI_UX_Spec.md) și [DESIGN.md](../DESIGN.md) stabilesc interfața. Contractele Hermes necesare sunt consolidate în §5; propunerile anterioare se consultă numai în istoricul Git, nu ca specificații concurente. La conflict se aplică acest baseline și planul v2; o abatere se înregistrează printr-un amendament înaintea implementării.

**„Final” înseamnă o bază coerentă, versionată, de pornire, nu integrare deja validată.** P2/P3 au porți explicite de fezabilitate. Nu substituim o probă eșuată cu o promisiune sau cu o reducere tacită a MVP-ului.

### Inclus

- Linux x86_64, un operator local, o singură aplicație Omnis, un engagement activ; prima probă cu un copil, apoi maximum doi copii nativi Hermes.
- Aplicații/laboratoare proprii, izolate și autorizate; HTTP(S), formulare, REST/JSON, SPA, JS static și import OpenAPI local revizionat.
- Recon anonim și autentificat opțional; hartă și matrice de coverage; Brain, investigatori, validator separat, delte, approvals, Stop, pause/resume și reconciliere.
- Trei familii demonstrate: control de acces la obiecte (IDOR/BOLA), XSS reflectat, traversal read-only către canary autorizat. Etichetele IDOR/BOLA nu dublează aceeași verificare.
- Settings OpenRouter și `openai-codex`, catalog/editare/review/publicare Skills; raport HTML/JSON, print și retest țintit.

### Exclus explicit

SaaS, acces public, multi-tenancy, colaborare, SSO/MFA autonom, un nou framework de agenți, marketplace/autoinstall Skills, graph DB, vector DB, Redis/Celery, Kubernetes, execuție shell generică, scanarea LAN-ului, SQLi general, stored/DOM XSS, SSRF/OAST, upload executabil, brute-force, DoS și chains avansate. Observarea unei suprafețe nesuportate nu o transformă în test executat.

## 2. Decizii de arhitectură

| ADR | Decizie | Motiv / alternativă respinsă |
|---|---|---|
| A01 | Monolit modular Python/FastAPI, frontend React/TS/Vite static | Fără nevoie de SSR, Next.js sau backend BFF suplimentar |
| A02 | PostgreSQL canonic; SQLAlchemy 2 async + psycopg 3; Alembic | SQLite nu reproduce concurența/lockingul dorit; nu împărțim adevărul între DB și conversații |
| A03 | API web separat de un singur supervisor Omnis; aceeași bază și același cod de domeniu | Reloadul API nu relansează Brainul; fără scheduler în fiecare worker Uvicorn |
| A04 | Delegare nativă Hermes, JSON-RPC stdio, management REST privat și plugin îngust | Fără scraping TUI, fork masiv, embedding `AIAgent` în requestul FastAPI sau workeri falși |
| A05 | Broker și proxy L7 autorizant pentru fiecare request; executori fără egress alternativ | Un proxy CONNECT opac sau o allowlist IP nu pot controla path/efect/identitate |
| A06 | Runtime Omnis separat de instalarea personală; catalog read-only, pin integral | Profilul este separare de stare, nu sandbox; nu încărcăm `.env` personal/project-local |
| A07 | Auth opțional cu seif local și serializare per context; refresh cu un singur proprietar | Nu dezactivăm rotația tokenurilor pe țintă și nu reutilizăm browserul personal |
| A08 | Dovezi adresate opac, protocol de finalizare înainte de verdict; evenimente tranzacționale | Un hash și un commit SQL nu fac filesystemul atomic |
| A09 | Confirmare și `tested_no_issue` prin verificatoare deterministe de completitudine/oracle | Un al doilea LLM nu votează adevărul; verdictul runtime nu este verdict de securitate |
| A10 | Scope/politică/model/catalog imutabile pe run; Stop + nou run pentru modificări | Evităm migrarea live a permisiunilor; identitatea poate reautentifica numai într-un nou `auth_epoch` controlat |
| A11 | SSE Omnis cu replay; comenzi HTTP versionate și idempotente | Nici SSE Hermes, nici chatul nu sunt event store |
| A12 | UI Operate: tree/tabel/inspector, nu graph canvas în prima versiune | Păstrăm relațiile și proveniența în model; vizualizarea 3D nu aduce valoare primei demonstrații |

## 3. Procese, rețele și granițe de încredere

```text
Browser operator → loopback Omnis web/API → PostgreSQL + artefacte + seif
                                   ↓ comenzi durabile
                         supervisor Omnis (unic)
                           ├─ host RPC → Hermes Brain → delegate_task → copii
                           ├─ Settings → management Hermes privat
                           └─ action broker → HTTP / Chromium executori
                                               ↓ exclusiv proxy autorizant
                                     mitmdump + addon Omnis → fixture autorizat
```

Separăm procesele pentru ciclul de viață și autoritate, nu pentru scalare distribuită. Un singur repo, un singur model de domeniu și o singură DB Omnis. State DB Hermes este istoric de runtime, nu DB alternativă de produs.

**Baza de încredere:** codul supervisorului, brokerului, proxy-addonului, pluginului de identitate și runtime-ul Hermes fixat. Modelul, textele copiilor, skills nepublicate și conținutul țintei sunt neîncrezătoare. Copiii nativi au conversații separate în același runtime, nu sandboxes OS independente. Modelul nu primește execuție arbitrară în acest proces; compromiterea arbitrară a codului din baza de încredere și root/același UID malițios nu sunt izolate de un mapping de task.

### Topologie aleasă

- `control`: API, supervisor și DB; numai web/API publică un port loopback. DB, endpointuri interne, management Hermes și proxy nu publică porturi către LAN.
- `runtime`: Hermes are acces numai la unelte Omnis autentificate și la egressul providerului selectat; fără rută către ținte, host, metadata, DB sau API-ul web/admin. Se folosește un endpoint intern separat, nu se permite întregul Omnis API modelului.
- `executor`: HTTP și Chromium pot ajunge numai la proxy; fără DNS extern/direct, UDP/QUIC, SOCKS, host networking, Docker socket sau volum de proiect/personal. Fiecare context primește o identitate de transport distinctă, necunoscută modelului.
- `target`: numai proxyul poate ajunge la fixture. Fixture-ul nu ajunge la control plane, internet sau rețeaua personală; email/plăți/webhookuri sunt sinks de test. Evaluatorul deține seed/reset/canary, inaccesibile agentului.
- Provider egress și target egress sunt trasee diferite, cu politici diferite. Nu se folosește provider proxy ca relay generic către ținte.

Reutilizăm ideea de rețea internă plus proxy din documentația Hermes, nu presupunem că ea implementează automat politica Omnis.[3] Rețelele bridge Docker au propriile reguli de conectivitate; `internal: true` singur nu certifică toate izolările sau accesul la host.[6] **Poarta G03 cere probe negative din fiecare namespace, inclusiv acces la gatewayul hostului și IPv6.** Configurația exactă nftables/namespace este artefact versionat P0/P3; fără demonstrație fail-closed nu pornim efecte.

### Browser și HTTPS: alegere concretă

Folosim Playwright Python în executor și **un proxy inspectabil bazat pe mitmdump cu addon Omnis**, condiționat de G-DEPENDENCIES. **Buildul publicat `mitmproxy==12.2.3` nu este aprobat pentru trafic target:** rezolvarea verificată include dependențe cu advisories; B01e trebuie să producă un release upstream corectat sau build cu patch minimal, lock separat și teste TLS/HTTP/confinare. Nu forțăm dependențe în afara constrângerilor și nu îl prezentăm ca sigur pe baza instalării. Vezi [stack baseline](Omnis_Stack_Baseline.md). Interceptarea Playwright este utilă pentru context și blocking suplimentar; nu este singura frontieră de autorizare. Service Workers pot ascunde cereri de mecanismele de rutare Playwright.[4]

- Proxy explicit; fiecare CONNECT este verificat la host/port **înaintea conectării upstream**, apoi TLS este interceptat pentru control per request.
- CA efemeră de laborator, instalată numai în containerul/contextul executorului; niciodată în trust store-ul operatorului. Cheia CA nu ajunge la Hermes sau țintă. Validarea certificatului upstream rămâne activă; CA proprie a fixture-ului este admisă explicit. Pinning/mTLS nesuportat produce `UNSUPPORTED`, nu `ignore_https_errors` global.
- Addonul implementează guard de conexiune, `requestheaders` pentru limite/refuz precoce și `request` pentru cererea completă; **request streaming oprit**. Documentația mitmproxy spune că, dacă streamingul este activ, evenimentul `request` poate veni după ce bodyul a fost transmis.[11]
- Configurăm explicit `connection_strategy=lazy`, fără certificate sniffing upstream înaintea autorizării, fără passthrough prin `ignore_hosts`/`tcp_hosts`, raw TCP sau upgrade WebSocket. Numele/opțiunile efective se verifică pe pin; valorile implicite nu sunt contractul Omnis.[10][12]
- HTTP/1.1 este transportul certificat MVP; HTTP/2, HTTP/3/QUIC, WebSocket, gRPC și protocoale raw nu sunt certificate. Nu facem request smuggling sau teste dependente de fidelitate wire-level prin acest proxy. Cererea observată de target este dovada efectului; versiunea originală a cererii și transformările proxyului se păstrează când sunt relevante.
- Guardul verifică URL brut, authority/Host/SNI/port, redirect și adresa rezolvată la conectare. Blocăm userinfo, scheme nepermise, ambiguități de parsare, metadata, loopback/link-local și adrese private din afara fixture-ului explicit. Nu blocăm generic orice RFC1918 și apoi exceptăm tot LAN-ul: laboratorul are adresare precisă.
- Conexiunile reutilizate nu ocolesc verificarea pe fiecare request. Rebinding, host/authority discrepant, redirect cross-origin și URL cu encodări ambigue au teste de refuz. Auth și cookies nu urmează redirecturi către altă origine prin copiere automată.
- Chromium: non-root, sandbox activ, seccomp compatibil, capabilități eliminate, fără `--no-sandbox`, fără `--ipc=host`, cu `/dev/shm` dimensionat privat. Imaginea Playwright documentată nu este declarată de producător drept sandbox suficient pentru site-uri neîncrezătoare; avem nevoie de hardening și probă proprie.[5]
- Service Workers se blochează; downloads/popups se blochează implicit, WebRTC/UDP și extensii sunt dezactivate. Un popup necesar unui login se permite numai într-o fereastră asistată explicită, pe originile de dependență aprobate. CSP a țintei nu este dezactivată pentru a fabrica XSS.

**Guardul real este proxy + rețea + broker.** Eroare addon, indisponibilitate policy/DB, lease expirat sau corelare lipsă înseamnă refuz, nu trafic permis. Cazul „addonul nu s-a încărcat” se verifică prin readiness și izolare: executori neporniți până la self-test negativ; un mitmdump generic fără policy nu este un serviciu acceptat.

**Binding browser→proxy:** un context/generație de browser aparține unui singur attempt pe durata lui, nu este transferat de la investigator la validator. `parent_action` reprezintă un workflow browser bounded (navigare și pași tipizați), nu fiecare click; pașii și requesturile au ID-uri proprii sub același părinte și nu extind permisiunea workflowului. Executorul de încredere deschide un `BrowserActionWindow` cu `(run, attempt, parent_action, auth_epoch, fencing_epoch, context_generation, deadline)` și canal proxy autentificat; metadata nu este pusă în headere ce ajung la țintă sau în argumentele LLM. Proxyul atribuie fiecărui request copil propriul action ID în acea fereastră și îl admite separat. Nu există două ferestre concurente pe același context. După închidere, fetchuri/timere de fundal se refuză; înaintea următoarei acțiuni se drenează și închide generația. Pentru MVP, contextul se reface dintr-un checkpoint de auth permis, nu se atribuie după timestamp o cerere întârziată unei acțiuni noi. Pierderea stării SPA/tokenurilor neregenerabile produce blocaj asistat, nu o excepție de policy. P3b probează cererea întârziată din generația veche exact când începe următoarea acțiune. Identitatea transportului singură nu este suficientă.

## 4. Control plane local și configurare

Loopback nu este autentificare. Omnis pornește numai pe `127.0.0.1`, cu Host allowlist exactă și același origin pentru buildul web și API. Dev Vite are host strict și proxy `/api`; nu CORS `*` sau porturi ascultate public.

**Bootstrap ales:** launcherul generează un cod local de pairing, unic/expirabil, afișat numai operatorului în terminal; formularul local îl schimbă o singură dată pe o sesiune opacă server-side. Codul nu apare în URL, Git sau log de request. Rată limitată, verificare Host/Origin și timeout. Cookie `HttpOnly; SameSite=Strict; Path=/`, fără `Domain`; HTTP loopback este limita asumată, nu pretindem TLS. Mutările cer și token CSRF legat de sesiune; SSE cere aceeași sesiune. Logout invalidează server-side; expirarea sesiunii UI nu anulează automat engagementul, dar nu permite control neautorizat. Refuzăm extinderea bindului; accesul remote ar cere TLS și alt threat model.

Un proces malițios cu același UID/root pe host rămâne în afara garanției. Nu prezentăm seiful, cookieul sau containerele drept protecție față de administratorul hostului.

Paths propuse pentru instalare, nu create acum: `$XDG_STATE_HOME/omnis` (implicit `~/.local/state/omnis`), runtime homes sub acest root, **nu sub `~/.hermes`**, configurație non-secretă sub `$XDG_CONFIG_HOME/omnis`, secrets cu permisiuni restrictive. Nu montăm `/home/kali`, checkoutul personal Hermes sau `.codex`. State/secrets/evidence/backups nu trăiesc în repo.

Settings și management Hermes au un singur writer; mutațiile provider/model/catalogului executabil sunt interzise în timpul unui run, exceptând Stop și revocarea credentialului care declanșează mai întâi oprire. Editarea unui draft Omnis neexecutabil poate continua: nu scrie în catalogul runtime și nu schimbă snapshotul; publicarea/selectarea noii versiuni se aplică numai unui run nou. Nu expunem proxy generic pentru config, filesystem, env reveal, terminal sau admin. Readback obligatoriu după set/delete/logout; `429`, `configured` și `oauth approved` nu înseamnă `inference_ready`.

## 5. Runtime Hermes și autoritatea copilului

Pinul de cod este `0.21.5` / `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Mediu instalat separat, nu copiat cu toate datele din home-ul personal. JSON-RPC stdio este suprafața aleasă pentru sesiuni, întrebări server→client și subagenți; documentația oficială distinge această suprafață de HTTP Runs.[2] Referința de adaptor de mai jos păstrează contractele utile din auditul static, fără dependență de o propunere veche.

**Un singur runtime activ și un singur store de credentiale AI.** Alegem un home de produs dedicat, cu un singur slot activ de engagement, nu copii de OAuth grants în homes concurente. Supervisorul oprește complet writerii înaintea schimbării engagementului și mută starea de caz (state DB, sessions, logs, caches și derivatele inventariate) într-o arhivă per-engagement nemontată runtime-ului următor; în slot rămân numai provider store/config aprobate și catalogul comun read-only. Restaurarea unui caz mută numai starea lui, cu verificarea ID-ului și cu permisiuni noi, înaintea startupului. Nu relocăm fișiere SQLite/WAL sub procese active și nu folosim symlinkuri către grants pe care un atomic replace le-ar putea rupe.

Managementul Hermes pornește exclusiv pentru Settings când writerul de execuție este oprit; apoi se închide înaintea runului. Runtime-ul activ este singurul proprietar al refreshului. UI citește statusul din proiecția Omnis când runul este activ; nu lansează validări sau modificări admin concurente. Inventarul exhaustiv al căilor de stare și proba A→B→A cu markeri sunt H02/G-DATA: dacă un path rămâne partajat sau un credential este adoptat implicit, gate-ul eșuează. Aceasta este gestionare de volume/stare a supervisorului, nu presupunerea unui flag Hermes inexistent. Memorie globală și auto-learning dezactivate; arhivele nu devin accesibile prin tooluri model-facing.

### Contract obligatoriu al bindingului

1. Brainul pregătește în Omnis un task READY: ipoteză, snapshot, rol, identități, skill digest, buget și precondiții. Referința nu este secret/credential.
2. Adaptorul delegării validează toate taskurile din batch față de sesiunea părinte și rezervă attempturi într-un `LaunchManifest` durabil. Identitățile/traseele de execuție nu sunt alese liber în argumentele toolului copilului.
3. **Înaintea primului tool al copilului**, un hook de runtime de încredere leagă `(launch_manifest, batch_index, parent_instance, child_instance)` de attempt; commitul mappingului precede orice acces de domeniu. Nu asociem după goal, FIFO, timestamp aproximativ sau un task ID revendicat de copil.
4. Handlerul pluginului primește identitatea contextuală din runtime, în afara JSON-ului LLM, și folosește mappingul pentru broker. Un copil neasociat nu citește nici evidence ale altui task. Tokenurile interne nu sunt întoarse modelului.
5. Compresia/rotația session ID cere lineage emis de runtime și actualizare atomică; în lipsa lui, apelul este refuzat și attemptul blocat, nu legat după prompt.

**Decizie de implementare P2:** încercăm întâi middleware/plugin cu metadata runtime verificabilă. Suprafața static inspectată nu dovedește că oferă toate câmpurile de la pasul 3. Dacă proba nu poate lega batch_index fără euristici, implementăm un patch minimal la frontiera nativă de creare a copilului: sidecar de launch transmis explicit, callback pre-run fail-closed și eveniment de lineage. Păstrăm `delegate_task`, tool loop, auth și orchestrarea native. Patchul se versionează separat, cu teste și SHA de bază; absența unui mecanism sigur blochează P3. Nu expunem un nou framework de workeri ca „echivalent”.

P2 include: două goaluri identice; batch concurent/retry; falsificarea taskului fratelui; observer întârziat/excepție; compresie; skill shadowing; canaries în store-uri simulate checkout/root/`CODEX_HOME`; inventar efectiv Brain/copil după încărcarea pluginurilor. Hooks de observabilitate nu devin gard de securitate.

### Capabilități model-facing

Brain: context/hartă/delte, pregătire task, delegare nativă, vizualizare rezultate. Copil: context îngust, skill native read-only, acțiuni HTTP/browser tipizate, emitere semnal/rezultat. Validator: numai precondiții, probe de replay și control autorizate. Fără tooluri stock de terminal/browser/network, SQL, `eval`, MCP liber, auto-learning global, auto-install, shell preprocessing sau scriere în skill release.

Uneltele nu includ credentiale în schema lor. Read APIs validează engagement/attempt/identity/snapshot la fel de strict ca write APIs. Nu se copiază chain-of-thought în UI; afișăm ipoteze, decizii scurte, motive, acțiuni și dovezi.

### Referință de adaptor la pinul Hermes

Consolidare din auditul static păstrat în Git la `b12e179`, pentru SHA Hermes indicat mai sus. Nu reprezintă o nouă verificare live și nu schimbă porțile H01–H08. Rutele administrative sunt contracte interne care trebuie încapsulate și acoperite de teste de contract în P2; browserul Omnis nu le apelează direct.

**Execuție:** `python -m tui_gateway.entry`, cu interpreterul și mediul runtime-ului Omnis controlat, pe stdio. Nu automatizăm TUI și nu expunem un al doilea proprietar HTTP al aceleiași sesiuni.

| Operație | Metodă RPC | Câmpuri / condiții |
|---|---|---|
| Handshake reverse requests | `client.capabilities` | `server_requests: true`, după `gateway.ready` |
| Creare Brain | `session.create` | `provider`, `model`, `title`, `cwd` controlat, `close_on_disconnect: false` |
| Tur nou / continuare | `prompt.submit` | `session_id`, `text`; răspuns pierdut → reconciliere, nu retry orb |
| Stare / istoric | `session.status`, `session.history` | `session_id` |
| Reatașare / evenimente recente | `session.resume`, `session.events.since` | Pentru events: `session_id`, `last_seen`; nu înlocuiește jurnalul Omnis |
| Intervenție Brain | `session.steer` | `session_id`, `text` |
| Copii activi | `subagent.list` | `session_id` al părintelui; nu registru istoric durabil |
| Intervenție / oprire copil | `subagent.steer`, `subagent.interrupt` | `session_id`, `subagent_id`; steer adaugă `text`; oprirea se verifică ulterior |
| Oprire sesiune | `session.interrupt` | `session_id`; nu substituie revocarea brokerului |

Păstrăm separat `session_id` RPC și `stored_session_id`. Requesturile server→client primesc răspuns cu același `id`; `approval` folosește `result:{choice:...}`, `request.cancel` retrage întrebarea exactă, iar metodele neimplementate primesc eroare JSON-RPC, nu aprobare implicită. Fără sudo/shell generic. Schema de referință: `apps/shared/src/gateway-contract.openrpc.json`; control copii: `tui_gateway/methods_subagents.py:53–113`.

**Delegare nativă:** `delegate_task` acceptă `tasks[].goal`, `context`, `output_schema`, `images`, `group` și acțiunile `spawn/list/steer/stop` la pinul auditat; nu presupunem selecție arbitrară provider/tools/skills per copil. `role="leaf"` nu este o graniță: adâncimea/configurația decid delegarea imbricată. Pluginul folosește `ctx.register_tool`; numele `omnis_*` din această arhitectură sunt contracte Omnis de implementat, nu tooluri deja existente. Ancoră: `tools/delegate_tool.py:187–191,634–726`.

Pollerul RPC poate porni nativ continuarea unui rezultat detached; Omnis nu o dublează. În alternativa HTTP Runs, clientul deține continuarea. ACK-ul notificării nu dovedește consumul rezultatului: verificăm și admiterea falsă, Stop și crashul după pornirea turului. Ancore: `tui_gateway/session_notifications.py:148–168,459–544,690–737`; `tui_gateway/prompt_turn.py:994–1001`.

**Bootstrap Settings privat:** supervisorul folosește `hermes serve --isolated --host 127.0.0.1 --port 0`, cu `HERMES_HOME` dedicat și `HERMES_DASHBOARD_SESSION_TOKEN` aleator injectat. Descoperă portul din `HERMES_BACKEND_READY port=<PORT_ALOCAT>`, verifică `/api/health` și un GET autentificat. În modul loopback fără gate extern, headerul este `X-Hermes-Session-Token`. Acesta nu este `API_SERVER_KEY` sau cheia AI. Se aplică regula unui singur writer din §5: managementul este oprit înaintea execuției. Ancore: `hermes_cli/main_dashboard.py:810–901`, `hermes_cli/web_server.py:317–445`.

`<PROFILE_ID>` este fixat server-side la profilul runtime-ului Omnis; nu este o cale sau o selecție arbitrară din browser.

| Operație Settings | Contract management | Semantica obligatorie |
|---|---|---|
| OpenRouter status | `GET /api/env?profile=<PROFILE_ID>` | `OPENROUTER_API_KEY`: `is_set`, `redacted_value`; nu inferență validată |
| OpenRouter validate | `POST /api/providers/validate` | Body `key`, `value`, `profile`; nu salvează; un 429 poate fi raportat `ok:true, reachable:true` |
| OpenRouter save | `PUT /api/env` | Body `key`, `value`, `profile`; rezultat `ok`, `key`, `config_updates`, apoi readback |
| OpenRouter delete | `DELETE /api/env` | Body `key`, `profile`; verificăm că nu reapare prin fallback |
| Codex status | `GET /api/providers/oauth?profile=<PROFILE_ID>` | Rândul `id=openai-codex` și sursa credentialului |
| Codex device login | `POST /api/providers/oauth/openai-codex/start?profile=<PROFILE_ID>` | Fără body; `session_id`, `flow`, `user_code`, `verification_url`, `expires_in`, `poll_interval` |
| Codex poll | `GET /api/providers/oauth/openai-codex/poll/{session_id}?profile=<PROFILE_ID>` | `pending`, `approved`, `expired`, `error`; schema generică include `denied` |
| Cancel login pending | `DELETE /api/providers/oauth/sessions/{session_id}?profile=<PROFILE_ID>` | Poll ulterior poate da 404, nu un rezultat durabil `cancelled` |
| Codex logout | `DELETE /api/providers/oauth/openai-codex?profile=<PROFILE_ID>` | Ștergere locală, nu revocare upstream; anulăm întâi loginurile pending cunoscute |
| Catalog modele | `GET /api/model/options?profile=<PROFILE_ID>&refresh=false&include_unconfigured=false&explicit_only=true` | Filtrat la OpenRouter/Codex; discovery/pricing pot accesa rețeaua |
| Selecție model | `POST /api/model/set` | `scope:"main"`, `provider`, `model`, `profile`, `confirm_expensive_model:false`; pentru sesiuni noi |

Toate rutele OAuth, inclusiv poll, cer autentificarea managementului și același profil. `/submit` nu este fallback Codex în acest contract; start poate da 504 înainte să termine loginul, iar pending sessions se pierd la restart. Nu retrimitem start nelimitat și nu interpretăm `has_refresh_token:false` drept absență demonstrată a grantului. `approved` nu înseamnă inferență disponibilă; Codex CLI nu este necesar pentru device OAuth nativ.

La model/set, HTTP 200 poate avea `ok:false, confirm_required:true`; `stale_aux` cere verificarea auxiliarelor/delegării/fallbackului. Cheile/codurile rămân numai în fluxul securizat, nu în prompt/log. Nu expunem `/api/env/reveal`, configul integral, profile management sau REST generic. `GET /api/skills` și `PUT /api/skills/toggle` nu înlocuiesc editorul complet, release digest/review și catalogul per run deținut de Omnis. Ancore Settings: `hermes_cli/web_routers/config_env.py:232–316,887–972`, `oauth.py:264–305,619–795`, `models.py:101–131,275–318`, `hermes_cli/auth_codex.py:153–193`.

**Ancorele probelor de autoritate:** identitate contextuală în `agent/tool_executor.py:1673–1688`, `model_tools.py:822–838`, `tools/registry.py:887–903`; hook pre-run în `tools/delegate_tool.py:285–297,383–415` și `tools/delegate_tool_child_run.py:854–862`; rotație session ID în `agent/conversation_compression.py:3340–3373`; surse dotenv/root în `tui_gateway/server.py:50–51`, `run_agent.py:121–122`, `hermes_cli/env_loader.py:423–447`, `hermes_constants.py:217–234`, `hermes_cli/config_defaults.py:1718–1724`. Aceste ancore sunt pentru SHA fixat, nu contracte garantate după upgrade și nu dovadă că mappingul sigur Omnis există deja.

## 6. Scheduler, taskuri, continuări și bugete

Supervisorul unic deține dispatcherul, runtime-ul și lease-urile. API poate avea mai multe procese în viitor, dar nu pornește schedulerul în lifespan. PostgreSQL oferă advisory locks la nivel de sesiune sau tranzacție; alegerea și eliberarea lor trebuie să fie explicite.[8]

- Lease de supervisor și `fencing_epoch` persistent; un singur engagement activ prin constrângere DB/lock. Workerul care pierde lease-ul nu mai poate admite/expedia acțiuni.
- Joburi/taskuri în PostgreSQL, claim tranzacțional cu `FOR UPDATE SKIP LOCKED`; fencing token la execuție. Nu ținem tranzacția deschisă în timp ce așteptăm rețea, LLM sau operator.
- DB state + domain event în aceeași tranzacție. Cursorul per engagement se alocă prin incrementul unui counter row blocat până la commit; un BIGSERIAL global singur nu ordonează commiturile și nu este suficient pentru SSE. Inbox de delte și marker de consum durabile. Notificarea native child completion are prioritate pentru continuarea ei; Omnis nu emite un al doilea wake în paralel.
- `delivered`, `admitted`, `turn_completed` și `domain_result_consumed` sunt stări distincte. ACK Hermes nu dovedește ultimele două. După crash reconciliem task/result IDs și cursori; rezultat neconsumat se livrează din nou numai după verificarea proprietarului turului. Consum idempotent, nu promisiune de exactly-once pe rețea.
- Un `prompt.submit` cu răspuns pierdut nu se retrimite orb. Attempt de tur în DB, status/istoric RPC, apoi decizie; incertitudinea poate bloca automatizarea până la operator.
- Cozi separate conceptual pentru investigație/validare; rezervă de trafic/timp pentru validare, fără rezervă „de prompt” care poate fi consumată tacit de recon.

### State machines normative

`EngagementRun`: `PREFLIGHT → READY → RUNNING → PAUSING → PAUSED → RUNNING`; din orice stare activă `STOPPING → STOPPED`; finalizare normală `COMPLETED` sau `LIMITED`; crash/efect incert `NEEDS_RECONCILIATION`. READY expiră dacă preflight/model/auth/policy se schimbă. Engagementul editabil este distinct de runul imutabil.

`TaskAttempt`: `QUEUED → BOUND → RUNNING → SUCCEEDED | INCONCLUSIVE | BLOCKED | FAILED | CANCELLED | NEEDS_RECONCILIATION`. `SUCCEEDED` înseamnă procedura încheiată, nu finding confirmat. Retries creează attempturi noi și păstrează istoricul.

`Action`: `PROPOSED → APPROVAL_REQUIRED | DENIED | ADMITTED → DISPATCHING → COMPLETED | FAILED | UNKNOWN`. `DISPATCHING` se persistă înaintea bytes upstream; crashul în acea fereastră rămâne conservator `UNKNOWN`, chiar dacă este posibil să nu fi fost trimis nimic. Comanda operatorului poate fi idempotentă; efectul pe țintă nu este deduplicat magic.

`Finding`: candidat → validare → `CONFIRMED | REJECTED | INCONCLUSIVE`. Starea remedierii este separată: `OPEN | FIXED | REGRESSED | RETEST_INCONCLUSIVE`, cu evidence noi și raport nou, fără rescrierea verdictului istoric.

**Predicat de finalizare:** numai supervisorul poate închide runul. `COMPLETED` cere frontiera de discovery epuizată în subsetul declarat, toate celulele obligatorii aplicabile cu rezultat probatoriu, toți candidații validați, niciun task/inbox/approval/cleanup/efect UNKNOWN restant și runtime/executori quiescenți. Propunerea Brainului de închidere nu este autoritate. Lucru restant din limită, policy/auth/unsupported relevant sau stagnare → `LIMITED` cu lista exactă; efecte externe nereconciliate → `NEEDS_RECONCILIATION`, chiar dacă raportul parțial poate fi exportat. Stagnare implicită: trei tururi consecutive fără observație/dovadă/precondiție nouă, consum de rezultat nou sau schimbare justificată de task; retries identice nu resetează contorul. Pragul este fixat în run manifest. `COMPLETED` certifică obligațiile catalogului și scope-ului declarat, nu siguranța întregii aplicații.

### Stop, pause, sănătate

Stop nu cere confirmare modală: revocă `fencing_epoch`, blochează noi dispatchuri, întrerupe Hermes, închide proxy/context/procese și așteaptă quiescența. UI rămâne `STOPPING` cât verificarea nu e completă. La timeout, supervisorul termină process group/containerul și afișează efectele incerte; nu declară anularea requesturilor deja expediate.

Pause oprește **dispatchuri noi**, nu numai taskuri noi; acțiunile deja expediate se pot drena în timeout. Permituri emise dar nefolosite sunt invalidate. Wake nativ în timpul pauzei nu trebuie să producă inferențe noi; dacă pinul nu poate garanta asta, închidem runtime-ul după drenare și reluăm din checkpoint într-un runtime nou. Resume face preflight și reconciliere, nu reînvie threaduri.

Defaults de fixture, de confirmat prin probe: maximum doi copii; o acțiune target în zbor; maximum o cerere/secundă per origin fără burst; deadline per cerere 15 secunde; lease 5 secunde, heartbeat 1 secundă; Stop fără dispatch nou după commitul revocării, quiescență locală în 10 secunde sau escaladare vizibilă. Ceas monotonic pentru deadline local, UTC pentru audit. Nu sunt performanțe măsurate.

Health: probe incluse în scope/buget, baseline la preflight; 429 respectă `Retry-After` în limite, altfel backoff bounded; 503 sau trei eșecuri consecutive de health blochează noi dispatchuri și cere review. Nu reluăm mutații pe retry automat. Bugetul global include login, redirecturi, subresurse, health, baseline/control și validare. Costul AI estimat/necunoscut este separat de hard caps de timp/request; plafon financiar numai dacă poate fi rezervat/verificat înaintea apelului sau impus la provider.

## 7. Policy și efecte

Scope entry: origin exact, port, reguli de path, `ATTACKABLE | VISIT_ONLY | BLOCKED`, excluderi, dependințe, identități și interval. BLOCKED câștigă; VISIT_ONLY permite numai operații funcționale declarate și nu payloaduri de test. URL-urile din JS/OpenAPI și redirecturile nu lărgesc scope-ul.

Effect class: `READ_ONLY_KNOWN`, `SESSION_CHANGE`, `LIMITED_WRITE`, `DESTRUCTIVE`, `UNKNOWN`. Proveniență: fixture manifest/operator cu revizie; clasificarea modelului este sugestie, nu permisiune. `UNKNOWN` este blocat sub politica read-only. Pentru aplicații proprii mai puțin descrise operatorul poate aproba o operație/workflow limitat după inspecție; nu pretindem recon read-only universal al oricărei aplicații.

Approval = acțiune exactă + hash semantic verificat al argumentelor + origin/operație/identitate/epoch/policy revision + expirare + număr de utilizări. Corpul cu CSRF volatil se leagă de o rețetă versionată și de câmpuri substituibile strict definite; nu hashăm bytes vechi și apoi autorizăm orice body nou. Toate subrequesturile browserului primesc verificare proprie; „am aprobat un click” nu este autorizație nelimitată pentru requests necunoscute.

Verificarea autorității/fencingului, rezervarea bugetului și consumarea unică a approvalului sunt tranzacționale. Aceeași idempotency key cu payload diferit produce conflict. Limita de doi copii include validatorul; validarea nu poate crea pe ascuns al treilea copil. Retryurile de target ale clientului HTTP și proxyului sunt dezactivate; un retry necesar loginului sau unei probe este acțiune nouă cu buget și politică, nu retry de transport invizibil.

Scope parsing este distinct de normalizarea hărții. Pentru primul traversal-canary, ruta HTTP rămâne o operație clar autorizată, iar inputul de traversal este un parametru declarat; nu relaxăm blocarea căilor de rutare ambigue/encodate pentru a obține un finding. Inputul autorizat este păstrat exact, nu „reparat” de normalizator.

Setup/login/workflowuri simple au pași tipizați, precondiții și verificare finală; nu avem DSL general sau shell arbitrar. Operațiile cu modificare țin un jurnal de obiecte create și obligații de cleanup. Cleanupul este tot acțiune autorizată, nu o excepție de ștergere. `cleanup_incomplete` intră în raport.

## 8. Identități, auth și adevărul regulii business

Identitate = label operator, principal/rol/tenant verificabil, auth mode, referință secretă și `auth_epoch`. Anonymous este valid și nu necesită seif. Basic/token/cookie sunt injectate numai în originea permisă, cu redirecționări revalidate; login asistat rulează în browserul engagementului, fără import automat de profil personal.

**Seif target:** criptare AEAD cu bibliotecă consacrată, cheie locală separată de DB și backup, permisiuni 0600, referințe opace în DB; cheia lipsă produce LOCKED. Nu pretindem protecție de același UID. Copiile temporare de cookies/storageState au TTL, sunt private, excluse din Git/export și șterse la închidere conform retenției. Operatorul introduce secrete doar în UI securizat, niciodată în chat/model.

Lease exclusiv per auth context și, unde este necesar, obiect de test. Un singur refresh owner; după refresh, epoch nou și precondiții revalidate. Nu clonăm orbește refresh tokens între doi workeri. A doua identitate poate avea alt context independent, dar limita globală rămâne. UI arată `WAITING_FOR_IDENTITY` în locul unui worker aparent blocat fără explicație.

Refreshul este efect de sesiune: persistăm intenția `(refresh_attempt, old_epoch, owner_generation, fencing)` înaintea cererii. Noul secret se salvează criptat/durabil înaintea publicării noului auth_epoch în tranzacție; numai ownerul încă valid poate publica. Un răspuns de la owner expirat este pus în carantină și contextul se blochează pentru reconciliere, nu redevine valid printr-un CAS asupra epochului vechi. Crash după rotația serverului dar înaintea persistării locale → `AUTH_UNKNOWN`, fără retry cu tokenul vechi; reautentificare asistată ori reconciliere explicit suportată de aplicație. G03b injectează ambele ferestre și refuză rezultate negative/verdict în intervalul incert.

Matrice business versionată: `(principal/rol/tenant, obiect sau clasă de obiect, operație) → ALLOW | DENY | UNKNOWN`, sursă și revizie. Include obiect privat și partajat. `owner != actor` sau status 200 nu sunt oracle. UNKNOWN produce `INCONCLUSIVE` și cerere de context; nu poate fi completat de LLM ca fapt.

Pozitiv login: o observație configurată de principal/rol (nu doar absența 401). Drift/expirare între baseline și probă invalidează intervalul. Browser storage și HTTP cookie jar sunt contexte distincte până când un transfer explicit testat dovedește echivalența. Replay recuperează tokenuri volatile și reface setupul; auth expirat nu devine `tested_no_issue` sau `FIXED`.

## 9. Model de date și contracte

UUID-uri opace, timp UTC, revizii întregi, enums explicite, schema_version pe payloaduri. PostgreSQL JSONB numai pentru metadata/payload versionat; cheile de autoritate, FK-urile și stările sunt coloane/constrângeri, nu documente JSON libere.

| Agregat | Date și constrângeri |
|---|---|
| Engagement / EngagementRevision / Run | Autorizație, scope, policy, data policy, bugete, snapshot model/catalog; runul citează revizia imutabilă |
| Identity / AuthContext / BusinessRuleRevision | Secret refs, principal, epoch, lease și reguli ALLOW/DENY/UNKNOWN |
| Surface / Operation / Parameter / Observation / Relationship | URL brut separat de rută normalizată, metodă, tip, proveniență, observed/inferred, context identitate și evidence |
| Task / Attempt / RuntimeBinding / LaunchManifest | Rol, precondiții, ipoteză, skill digest, limite, lineage de încredere și fencing |
| Action / Approval / EffectRecord | Autoritate, argumente tipizate/redactate, revizii, dispatch, rezultat/UNKNOWN și cleanup |
| Evidence / Artifact | Proveniență executor, digest, size, stare, path intern generat, redactare și retenție |
| Candidate / Validation / Finding / Occurrence / Retest | Oracle, controale, severitate motivată, impact demonstrat, precondiții, remediere și probe noi |
| DomainEvent / Inbox / Command / ReportSnapshot | cursor, revision, causation, idempotency, payload minim/redactat și snapshot reproductibil |

Relațiile sunt engagement-scoped, cu FK compuse/validare de ownership; fără joins între engagementuri pe baza unui ID ghicit. Normalizarea conservatoare păstrează exemplarele și contextul; nu unifică două obiecte cu politici diferite. Indexuri pe engagement/cursor, task/state, operation/identity și claim queue; paginare keyset, nu offset nelimitat.

### API Omnis v1 (contract propus, nu endpointuri deja existente)

- `/api/v1/engagements`, `/{id}`, `/{id}/revisions`: CRUD draft și validare; update cu `If-Match`/revision, 409 la conflict sau run activ.
- `/{id}/preflight`, `/{id}/runs`, `/runs/{run}/commands`: Start/Pause/Resume/Stop; comenzi cu idempotency key și readback; 202 înseamnă acceptată, nu finalizată. Serverul reface condițiile critice la Start, nu se bazează pe un rezultat UI stale.
- `/runs/{run}/events?after=cursor`: SSE cu `id`, replay din DB, heartbeat, last cursor; cursor expirat → `RESYNC_REQUIRED`, fetch snapshot și reabonare fără dublare. Snapshot include `through_cursor` consistent.
- `/runs/{run}/surfaces`, `/coverage`, `/tasks`, `/findings`, `/approvals`, `/evidence/{id}`: query bounded și scope validat. Autorizarea nu vine din filtrul clientului.
- `/settings/providers/{allowed_provider}/...`, `/settings/runtime`, `/settings/skills/...`: operații allowlisted, nu pass-through către Hermes.
- `/reports` și `/findings/{id}/retests`: snapshoturi imutabile și revalidare țintită cu buget/autorizație proaspete.

Errors: `{code, message, correlation_id, field_errors, retryable}`; fără traceback/secrete. Exemple: `SCOPE_DENIED`, `UNSUPPORTED_TRANSPORT`, `AUTH_BLOCKED`, `POLICY_CHANGED`, `EVIDENCE_UNAVAILABLE`, `RUNTIME_INCOMPATIBLE`, `NEEDS_RECONCILIATION`. Semantica retryable se referă la operația API, nu la reexpedierea automată pe țintă.

OpenAPI generat din Pydantic; tipuri TS generate în build. Tipurile generate nu sunt validator runtime și nu acordă drepturi; API validează tot. TanStack Query deține server state, URL deține filtre/selecția, React deține state local al formularului; fără Redux/Zustand inițial. Invalidări SSE pe entity revision și refetch, nu counter++ la orice event repetat.

## 10. Evidence, date și raport

**Protocol artefact:** (1) rezervare STAGING în DB; (2) scriere streaming bounded în fișier temporar exclusiv, fără nume ales de țintă; (3) flush/fsync, digest, rename atomic pe același filesystem, fsync director; (4) tranzacție DB care publică AVAILABLE plus eveniment; (5) reconciler pentru STAGING/orfani/lipsă. Cititorul verifică existența/integritatea înaintea operației probatorii. Hashul detectează modificarea, nu dovedește singur proveniența.

Stări: `STAGING`, `AVAILABLE`, `TRUNCATED`, `MISSING`, `CORRUPT`, `DELETED`; versiunea redactată este derivat cu legătură la raw. Oracle declară ce bytes sunt obligatorii; un fragment suficient poate susține o observație limitată, nu automat un verdict complet. Verdictul este refuzat dacă dovezile obligatorii sunt absente/incomplete.

Limite inițiale de fixture: request body recepționat 1 MiB; response pe wire 5 MiB; response decomprimat 5 MiB; evidence păstrat 5 MiB, ratio maxim decomprimare 20:1; artefact individual 20 MiB, 1 GiB/run. Guardul aplică bytes/time caps incremental înaintea bufferingului/decomprimării, și fără Content-Length/chunked; depășirea întrerupe consumul și închide upstreamul, nu doar trunchiază fișierul final. Pentru MVP răspunsul bounded este verificat înainte să fie predat browserului; streaming către Chromium este oprit. Trace-ul este oprit implicit și bounded când este cerut; upload OpenAPI/JS 5 MiB, depth/time limits și decodare incrementală. Memoria/CPU/PIDs/tmpfs au capuri de container, inclusiv la parser și Chromium; dumpul/trace-ul nu ocolește bugetul. Parametri ajustabili numai în revizie, niciodată nelimitat; depășirea se înregistrează, nu se ascunde. Rezervăm capacitatea înaintea unei acțiuni; disc plin oprește admiterea și păstrează starea efectului. G03a verifică bytes efectiv citiți, memorie bounded și închiderea conexiunii pe fixture chunked/decompression bomb, nu numai absența verdictului.

Inventar de date: DB, raw/derivate, seif, cookie/storageState, Hermes sessions/compaction/live logs/provider error dumps, screenshots, model payloads, exports și backups. Memorie globală/cloud memory/auto-learning/exporteri auxiliari dezactivate în runtime Omnis. Providerul primește minimum necesar, conform data policy; redactarea headerelor nu garantează eliminarea PII din body/screenshot. Markeri sensibili sintetici verifică fiecare traseu în G-DATA.

**ModelProjection v1**, obligatoriu înainte de prima trimitere de date de țintă: tool results/context/delte sunt DTO-uri cu allowlist de câmpuri (ID-uri opace, metodă, cale redactată, nume/tip parametri, status, observații și fragmente bounded aprobate). Raw body, headers, query values, cookies, storageState, stack traces și fișierele de evidence nu intră implicit în context. Executorul produce o proiecție separată; secretele cunoscute se elimină, iar tipurile/câmpurile sensibile neclasificate se refuză ori cer review, nu sunt „redactate” doar prin regex general. Screenshoturile sunt dezactivate model-facing implicit; se permit doar pe fixture sintetic aprobat și după verificarea/crop/maskingului necesar. Scope-ul și proveniența proiecției sunt verificate ca la evidence read. `G-DATA-EARLY` cu markeri sintetici este înainte de G02-live pentru datele probei și înainte de P3 pentru primul output target; G-DATA la P8 extinde aceeași suită la retenție/export/restore. Nu pretindem DLP universal; sintetic-only rămâne condiție a MVP-ului.

Evidence HTML/JS/SVG se afișează ca text escapate; fără iframe raw, script, event handlers, linkuri autoîncărcate sau SVG inline de la țintă. Screenshoturi validate și decodate bounded. Download explicit cu `Content-Disposition: attachment`, `nosniff`, CSP restrictiv și avertisment; exporturile sunt offline, escapate, fără resurse remote. Nu stocăm secrete în localStorage sau URL.

Retenție default propusă: raw/derivate și sesiuni engagement 30 zile, exporturile numai explicit, audit de comenzi/snapshoturi fără payload sensibil 90 zile; secrete de sesiune numai cât sunt necesare. Ștergerea unui engagement cere run oprit, manifest de date/derivate și tombstones; backupurile expiră separat și limita este afișată. Backup consistent: run oprit/quiescent, DB + manifest artefacte + checksums; cheia seifului nu intră în aceeași arhivă. Restore într-un root separat începe locked/stopped, nu repornește taskuri și nu restaurează login AI implicit.

Finding stabil + occurrences deduplicate conservator după clasă/rădăcină/regulă/operație/context; nu unim pe titlu. Severitate argumentată separat de confidence, CWE, impact demonstrat versus potențial, pași reproductibili, evidence refs, limite, remediere și retest. CVSS numeric este opțional; dacă apare, păstrăm vectorul și calculăm determinist, fără număr inventat de LLM. Operatorul poate contesta/adnota, nu rescrie bytes sau confirma fără poarta probatorie.

Verdictul istoric și disponibilitatea actuală a dovezilor sunt proprietăți separate. La MISSING/DELETED/CORRUPT, UI și exporturile noi afișează starea curentă și replay indisponibil; nu rescriu snapshotul sau verdictul de la data lui. Exportul vechi offline nu poate cunoaște o ștergere viitoare: include data/snapshotul și avertismentul că disponibilitatea curentă se verifică în Omnis. O nouă reproducere cere probe noi; un raport vechi nu este reutilizat ca verdict proaspăt.

## 11. Recon, coverage și evaluare

Matrice suport:

| Suprafață | MVP | Limite vizibile |
|---|---|---|
| HTTP(S), forms, REST/JSON | Da, prin broker/proxy | Nu wire-level smuggling, streaming uploads, protocoale raw |
| SPA, JS static, API post-auth | Da, Chromium controlat | SW/WS/QUIC dezactivate; aplicație dependentă de ele = parțial/unsupported |
| OpenAPI local JSON/YAML | Da, upload revizionat | Parser sigur, limite/depth, fără `$ref` externe sau execuție YAML; fără extindere scope |
| Directory/parameter discovery | Da, bounded wordlist fixată | Activ, inclus în buget/efecte; soft-404 și rate limit tratate |
| GraphQL/gRPC/WebSocket | Doar semnal de existență când observabil | Nu capabilitate testată; fără negativ implicit |
| Katana/Nuclei/sqlmap | Nu dependențe ale baseline-ului | Adaptor opțional numai după gate propriu; fără instalare/template-uri automate |

Pachet Brain: snapshot și cursor, vecinătate relevantă, observații/contradicții, frontieră neexplorată, precondiții lipsă, buget și truncation flag. Contextul se paginează; nu transmitem întreaga hartă la fiecare tur. Dedup task după ipoteză + suprafață + identitate/epoch + family revision; retest cere informație nouă sau motiv auditat.

Coverage key: operație × parametru relevant × identitate/epoch × familie aplicabilă × snapshot/procedură. `tested_no_issue` cere precondiții, test și control efectiv executate, evidence și versiune corecte; răspunsul LLM negativ nu crește numărătorul. `not_applicable` cere justificare, iar unknown/blocked rămân vizibile. Numitor gol = N/A. Descoperit/exercitat/testat/validat sunt indicatori diferiți. UI oferă trecere din fiecare celulă la test/dovadă.

Evaluarea separă integrare, capabilitate cu ipoteză furnizată și E2E fără soluție furnizată. Evaluatorul deține adevărul de referință, canary-urile și resetarea; agentul nu vede seed DB, scorer sau source privilegiat. Profilul de informație este declarat: black-box URL sau grey-box cu identități/reguli/OpenAPI, nu revendicăm black-box când dăm reguli business.

Pragurile, corpusul, repetările și baseline-ul sunt fixate în plan înaintea rulărilor. Rezultatele se publică per run, cu ratări atribuite discovery/planificare/investigație/validare și cost necunoscut explicit. Promovarea unei familii ca benchmark-validated este legată de exact skill/tool/model/corpus; nu este precizie universală.

## 12. Implementare și guvernanță

### 12.1. Arborele țintă și proprietatea fișierelor

**Amendament de organizare propus după revizia UI. Nu este scaffold creat sau aprobare de implementare.** Alegem directoare **`api/` și `web/` la rădăcină**, în locul schiței anterioare `src/omnis` + `apps/web`. `api/` conține monolitul modular și supervisorul (același wheel/cod de domeniu, procese diferite); `cli/` este launcherul operatorului, nu un al doilea backend. Rootul păstrează documentele/uneltele existente. Fișierele de mai jos se creează numai în felia care le exercită; nu umplem P0 cu clase goale sau toate tabelele MVP.

```text
OmnisAI/
├── README.md / AGENTS.md / CONTRIBUTING.md / DESIGN.md / Makefile
├── .github/workflows/ci.yml             # gate comun, fără conturi/live LLM
├── api/
│   ├── pyproject.toml / uv.lock         # API + supervisor, nu Hermes/proxy
│   ├── alembic.ini
│   ├── migrations/env.py / versions/   # migrare odată cu felia de date
│   ├── src/omnis/
│   │   ├── __init__.py
│   │   ├── api.py                      # app factory FastAPI, fără scheduler
│   │   ├── bootstrap.py                # wiring explicit al adaptoarelor
│   │   ├── core/
│   │   │   ├── config.py / paths.py    # configurație validată, fără env dump
│   │   │   ├── ids.py / clock.py / errors.py
│   │   │   ├── db.py / uow.py          # pool + unitate de lucru/tranzacție
│   │   │   └── logging.py              # context IDs + redaction
│   │   ├── security/
│   │   │   ├── host_origin.py / csrf.py / sessions.py
│   │   │   ├── pairing.py              # bootstrap local; nu token admin Hermes
│   │   │   └── redaction.py            # proiecție allowlist, nu DLP universal
│   │   ├── modules/                    # modulele din tabelul de mai jos
│   │   │   └── engagements/
│   │   │       ├── domain.py           # invariants/tranziții pure
│   │   │       ├── service.py / ports.py
│   │   │       ├── models.py / repository.py
│   │   │       └── schemas.py / routes.py
│   │   ├── supervisor/
│   │   │   ├── __main__.py / loop.py   # entrypoint separat, singleton
│   │   │   ├── leases.py / inbox.py / reconcile.py
│   │   │   └── shutdown.py             # fencing, Stop, dovadă de quiescență
│   │   ├── transport/
│   │   │   ├── internal_api.py / internal_auth.py
│   │   │   └── events.py               # SSE din evenimente durabile
│   │   └── adapters/
│   │       ├── hermes_client.py        # protocol privat, nu SDK în domain
│   │       └── executor_client.py      # acțiuni tipizate, nu shell generic
│   └── tests/
│       ├── conftest.py
│       ├── unit/ / integration/ / contracts/ / migrations/
├── web/
│   ├── package.json / package-lock.json
│   ├── index.html / vite.config.ts / tsconfig.json / vitest.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/App.tsx / router.tsx / providers.tsx
│   │   ├── shared/
│   │   │   ├── api/client.ts / errors.ts / events.ts / generated.ts
│   │   │   ├── styles/tokens.css / global.css
│   │   │   └── ui/                     # RunControls, StatusLabel, Dialog etc.
│   │   └── features/
│   │       ├── engagements/ / setup/ / overview/
│   │       ├── map/ / investigations/ / findings/ / reports/
│   │       └── settings/providers/ / skills/ / runtime/ / data/
│   └── tests/setup.ts                  # Vitest; teste lângă componente
├── cli/
│   ├── pyproject.toml / uv.lock         # console script `omnis`, mediu mic
│   ├── src/omnis_cli/
│   │   ├── __init__.py / __main__.py / main.py
│   │   ├── paths.py / config.py / instance.py
│   │   ├── compose.py / health.py / browser.py
│   │   └── pairing.py / control.py / exit_codes.py
│   └── tests/                          # lifecycle, concurență, erori, argv
├── integrations/hermes/
│   ├── pyproject.toml / uv.lock / upstream.json
│   ├── src/omnis_hermes/plugin.py / binding.py / projections.py
│   ├── contracts/                      # mesaje de pin + teste de compatibilitate
│   └── patches/                        # numai dacă un gate cere patch auditat
├── executors/
│   ├── http/pyproject.toml / uv.lock / src/omnis_http/ / tests/
│   ├── browser/pyproject.toml / uv.lock / src/omnis_browser/ / tests/
│   └── proxy/pyproject.toml / uv.lock / src/omnis_proxy/ / tests/
├── contracts/
│   ├── omnis.openapi.json              # generat din API-ul Omnis
│   └── internal.schema.json            # wire intern versionat, fără ORM
├── skills/                             # surse metodologie PRODUCT, reviewed
├── labs/dev/manifests/ / fixtures/ / sinks/
├── ops/
│   ├── compose.yaml / compose.dev.yaml / compose.test.yaml
│   ├── images/                         # API, runtime, HTTP, browser, proxy
│   ├── network/                        # policy nftables/namespace verificată
│   └── release/manifest.schema.json    # versiuni, wheel-uri, OCI digests
├── tests/
│   ├── documentation/ / development/  # testele existente, nu aplicația
│   └── e2e/ / safety/ / recovery/ / release/
├── scripts/
│   ├── render_docs.py / hermes_dev.py  # existente, numai dezvoltare
│   └── export_contracts.py / build_release.py
├── documents/                          # același baseline și probele lui
├── tools/development/                  # Reticle/anti-slop etc., numai dev
└── .hermes/skills/                      # skills DEZVOLTARE, niciodată runtime
```

Numele separate prin `/` într-un rând cu fișiere înseamnă frați în directorul indicat, nu un singur path. `dist/`, builduri, caches și medii virtuale sunt generate/ignorate, nu surse versionate. Arborele nu mută acum niciun fișier existent.

### 12.2. Modulul potrivit pentru fiecare comportament

Sub `api/src/omnis/modules/`:

| Modul | Deține | Fișiere speciale, numai când sunt necesare | Prima felie |
|---|---|---|---|
| `engagements/` | Draft, revizie, scope declarat, autorizare și context business | `scope.py`, `business_rules.py` | B02 |
| `runs/` | Preflight, comenzi idempotente, run snapshot și tranziții | `preflight.py`, `commands.py`, `completion.py` | B04/B05/B07 |
| `tasks/` | Task/attempt, bindings, inbox/continuări și priorități | `binding.py`, `continuations.py` | B06 |
| `policy/` | Efecte, scope efectiv, admitere, approval și bugete | `effects.py`, `admission.py`, `budgets.py` | B07 |
| `identities/` | Persona/auth context, refresh/lease, epoch, secret refs | `vault.py`, `refresh.py` | B09 |
| `surfaces/` | Operații/parametri/observații/relații, normalizare conservatoare | `normalization.py`, `imports.py` | B08/B10 |
| `coverage/` | Numitor, aplicabilitate, proceduri și dovada negativului | `denominator.py` | B10/B12 |
| `evidence/` | STAGING/finalizare, manifest, integritate, retenție | `store.py`, `projection.py`, `retention.py` | B07 |
| `validation/` | Reproducere independentă și gate deterministic, nu voturi | `oracles/object_access.py`, `reflected_xss.py`, `traversal_canary.py` | B12 |
| `findings/` | Verdict admis, occurrences, severitate, retest | `deduplication.py`, `retest.py` | B13 |
| `reports/` | Snapshot/export HTML/JSON inert, limite și istoric | `render.py`, `templates/report.html` | B13 |
| `settings/` | Readiness provider, publicare catalog și data policy | `providers.py`, `skill_catalog.py` | B14/P4a |

**Șablon de modul, nu generator obligatoriu:** `domain.py` (stdlib, invariants), `service.py` (use cases), `ports.py` (Protocol pentru I/O), `models.py` (ORM), `repository.py` (SQL), `schemas.py` (DTO Pydantic), `routes.py` (HTTP). Nu creăm cele șapte fișiere dacă felia nu are cele șapte responsabilități. Testele au același nume de modul: `api/tests/unit/engagements/test_domain.py`, `api/tests/integration/engagements/test_repository.py`, `api/tests/contracts/test_engagements_api.py`.

**Exemplu web concret:** `web/src/features/findings/FindingsPage.tsx`, `FindingDetail.tsx`, `EvidenceBundle.tsx`, `ValidatorDecision.tsx`, `api.ts`, `queryKeys.ts`, `FindingsPage.module.css` și teste `*.test.tsx` lângă componente. `overview/BrainStream.tsx` consumă proiecții de evenimente, nu loguri interne Hermes. `shared/ui/RunControls/` deține componenta, CSS Module și testele Stop/Pause/Start reutilizate. Nu copiem HTML-ul DEMO ca aplicație și nu menținem un al doilea set de fixture-uri în datele produsului.

**Executori:** în fiecare pachet, `__main__.py` pornește workerul inert, `runner.py` execută numai acțiuni tipizate admise, `capture.py` păstrează output bounded. Browserul adaugă `contexts.py` și `action_window.py`; proxyul are `addon.py`, `policy_client.py`, `limits.py`, `readiness.py`. Adaptorul nativ Hermes expune numai binding/proiecții/unelte allowlisted. Proxyul rămâne neadmis până la B01e, indiferent că are deja un loc în arbore.

### 12.3. Reguli de import, date, API și UI

- **Direcția dependențelor:** routes/schemas → services/ports → domain. Repositories/ORM, filesystem și Hermes/executor clients implementează ports și sunt conectate în `bootstrap.py`. Domain nu importă FastAPI, SQLAlchemy, Hermes sau Playwright; o probă de import în CI respinge încălcările.
- **Monolit modular, nu microservicii de domeniu:** un modul folosește serviciul/portul public al altuia, nu îi modifică direct modelele. Nu introducem event bus distribuit, DI container general, `BaseService`/`BaseRepository` generic sau `utils.py` fără responsabilitate. Evenimentul durabil și idempotency rămân contracte de date, nu notificări volatile.
- **O tranzacție pentru invariantul comun:** `uow.py` deține commit/rollback; repository-urile nu fac commit pe ascuns. Admiterea autoritate/buget/approval rămâne atomică între module. SQLAlchemy session per unitate de lucru, nu globală și nu ținută deschisă cât răspunde LLM-ul. I/O async; parsing CPU și subprocessuri bounded în afara event loopului.
- **Boundary strict:** input validat cu DTO-uri, erori tipizate și correlation ID; UUID-uri opace, UTC, entity revisions, ownership engagement-scoped, paginare bounded. Nu returnăm ORM, traceback, env sau secrete. Domain errors sunt mapate explicit la contractul HTTP, inclusiv 409 și stări necunoscute.
- **Contracte generate:** API-ul este sursa pentru `contracts/omnis.openapi.json` și apoi `web/src/shared/api/generated.ts`; schema internă pornește din DTO-urile interne ale aceluiași cod. CI detectează drift; nu edităm generated types de mână și nu generăm cod din OpenAPI-ul țintei. Wire schema are versiune și compatibilitate verificată între mediile separate.
- **Frontend:** TypeScript strict, Router pentru navigare/filtre/selecție, Query pentru server state, state local numai pentru draft/interacțiune. CSS Modules + tokenuri generate din DESIGN; Radix pentru interacțiuni complexe și HTML nativ unde ajunge. Fără `any`/ignore global/catch gol pentru a face testele verzi; stările loading/empty/error/stale/unknown rămân distincte.
- **Date și loguri:** ID-uri/cauzalitate în logs structurate, allowlist/redaction înainte de log/model/export; nici evidence raw, tokens, cookies sau codes de pairing în browser storage/URL/log. Bloburile nu se servesc prin director static; numai endpoint cu ownership, integritate și policy. Settings runtime nu este filesystem browser.
- **Config și dependențe:** manifeste/lockuri separate pentru web, API, CLI, Hermes și fiecare executor; nu un venv comun. `api/src/omnis/core/config.py` și `cli/src/omnis_cli/config.py` au subseturi proprii tipizate, nu copiază credentiale. Versiunile sunt cele din stack baseline; formatare/typecheck/dependency audit se fixează explicit în B01a, nu alegem aici versiuni inventate pentru unelte lipsă.

### 12.4. Comenzi și traseul unei felii

Astăzi există numai `make check`/`make test` pentru documente/unelte. **Contracte de comenzi viitoare, nu comenzi deja funcționale:** `make dev`, `make build`, `make test-api`, `make test-web`, `make test-contracts`, `make test-e2e`, `make test-safety`, `make test-release`. Se adaugă când componenta și proba există; un gate indisponibil raportează NOT-RUN/BLOCKED, nu exit 0. CI apelează aceleași comenzi locale. Pachetul instalat folosește `omnis`, nu Vite sau comenzi Make.

Exemplu B02: test domain RED → modul `engagements` + migrare → repository pe PostgreSQL real → route/DTO/OpenAPI → tipuri generate + formular/query web → E2E create/reload/conflict → commit coerent. B07 adaugă policy/evidence cu aceleași frontiere, nu un director generic de „agenți” care ajunge să dețină DB și rețeaua. Corpul held-out/scorer rămâne într-un workspace evaluator separat, niciodată montat runtime-ului.

Migrațiile se execută o singură dată prin comandă dedicată înaintea startupului; schema incompatibilă blochează readiness. Backup înaintea migrațiilor distructive; rollback documentat sau restore, nu promisiune că orice migrație este reversibilă. CI fără secrete/scanări/LLM: format/typecheck/unit/contracts/build, DB reală de test, safety fixtures izolate. Live provider opt-in și buget explicit.

TDD pe felii verticale: test RED relevant → implementare minimă → GREEN → refactor. Commit mic per comportament/decizie, numai fișiere intenționate, mesaje cu motiv și verificări. Upgrade Hermes/dependințe prin branch dedicat, lock/digests, contract+safety suite, fără upgrade sub run activ. Nu încărcăm automat pluginuri/pachete din rețea la startup.

### Porți de decizie care rămân reale, nu ascunse

- **G-RUNTIME:** binding/lineage, credential ownership, wake și Stop native — dacă pică, P3 blocat până la extensie/patch minimal verificat.
- **G-DEPENDENCIES:** proxyul publicat cu dependențe afectate este respins; B01e produce upstream/build remediat și verificat înaintea oricărui target effect.
- **G-NET:** proxy/namespace nu poate împiedica toate traseele certificate — transport blocat; nu activăm fallback direct.
- **G-PROVIDER:** cont, model, entitlement, buget și data policy aprobate — test live blocat până atunci; P0/P1 și testele fără LLM continuă.
- **G-RELEASE:** toate funcțiile MVP promise, inclusiv Settings complet/ambii provideri, au dovezi. Lipsa contului nu devine succes mock.

Acestea sunt condiții de execuție ale planului, nu alegeri de stack lăsate fără proprietar. Raportul de re-review consemnează ce a fost verificat în această livrare și ce trebuie demonstrat de aplicație.

## Sources

[2] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration — https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[3] https://hermes-agent.nousresearch.com/docs/user-guide/egress/network-isolation — https://hermes-agent.nousresearch.com/docs/user-guide/egress/network-isolation
[4] https://playwright.dev/python/docs/network — https://playwright.dev/python/docs/network
[5] https://playwright.dev/python/docs/docker — https://playwright.dev/python/docs/docker
[6] https://docs.docker.com/engine/network/drivers/bridge — Bridge network driver | Docker Docs
[8] https://www.postgresql.org/docs/current/explicit-locking.html — PostgreSQL: Documentation: 18: 13.3. Explicit Locking
[10] https://docs.mitmproxy.org/stable/concepts/how-mitmproxy-works — How mitmproxy works
[11] https://docs.mitmproxy.org/stable/api/events.html — Event Hooks
[12] https://docs.mitmproxy.org/stable/concepts/options — Options
