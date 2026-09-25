# Omnis — arhitectura MVP, baseline v1

**25 septembrie 2026 · Specificație pentru implementare · Produs neimplementat**

## 1. Autoritate și domeniu

Acest document închide alegerile de arhitectură pentru MVP-ul local cerut. [Planul revizuit](Omnis_Implementation_Plan.md) stabilește ordinea și porțile; [stackul](Omnis_Stack_Baseline.md) stabilește versiunile și limitele verificării; [UI/UX](Omnis_UI_UX_Spec.md) și [DESIGN.md](../DESIGN.md) stabilesc interfața. Propunerile Hermes precedente rămân audituri istorice ale contractelor, nu surse concurente de scope. La conflict se aplică acest baseline și planul v2; o abatere se înregistrează printr-un amendament înaintea implementării.

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

Pinul de cod este `0.21.5` / `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Mediu instalat separat, nu copiat cu toate datele din home-ul personal. JSON-RPC stdio este suprafața aleasă pentru sesiuni, întrebări server→client și subagenți; documentația oficială distinge această suprafață de HTTP Runs.[2] Contractele exacte la pin rămân în [auditul de integrare](Omnis_Hermes_Local_MVP_Integration_Proposal.md).

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

Structură țintă, de creat în P0:

```text
apps/web/                  React, CSS Modules, generated API types
src/omnis/                 config, API, modules/domain, adapters, supervisor
integrations/hermes/       plugin, contract fixtures, patch manifest dacă necesar
executors/                 HTTP/browser runner, proxy addon, manifests
skills/                    surse reviewed; releases materializate read-only
labs/                      fixture-uri dev fără secrete reale
# corpusul held-out/scorer: workspace evaluator separat, nemontat agentului
migrations/                Alembic
tests/                     unit, contract, integration, UI, safety, recovery
ops/                       Compose, profiles, egress policy, launcher
scripts/                   test/build/doc/release helpers
documents/                 baseline, ADR/amendamente, verificări
```

Domeniul nu importă Hermes/Playwright/FastAPI. Adaptoare la margine; DTO-uri API distincte de ORM. Nu ținem SQLAlchemy sessions globale sau pe durata apelului LLM. I/O async; parsare/CPU și subprocessuri izolate, fără blocarea event loopului. Nu introducem abstraction framework/DI container general înaintea nevoii.

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
