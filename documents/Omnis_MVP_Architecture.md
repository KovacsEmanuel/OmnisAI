# Omnis — arhitectura MVP, baseline v1

**Baseline amendat HF01–HF10 · API/control/web P0.1–P0.3 implementate local; P0.4 în curs, G00 deschis; motor pentest neimplementat**

## 1. Autoritate și domeniu

Acest document închide alegerile de arhitectură pentru MVP-ul local cerut. [Planul revizuit](Omnis_Implementation_Plan.md) stabilește ordinea și porțile; [stackul](Omnis_Stack_Baseline.md) stabilește versiunile și limitele verificării; [UI/UX](Omnis_UI_UX_Spec.md) și [DESIGN.md](../DESIGN.md) stabilesc interfața. Contractele Hermes necesare sunt consolidate în §5; contractele modulare și de date sunt în §6/§9. Review-urile din verification păstrează sursele/rațiunile istorice, nu specificații concurente după acest amendament autorizat. La conflict se aplică acest baseline și planul v2; o abatere se înregistrează printr-un amendament înaintea implementării.

**„Final” înseamnă o bază coerentă, versionată, de pornire, nu integrare deja validată.** P2/P3 au porți explicite de fezabilitate. Nu substituim o probă eșuată cu o promisiune sau cu o reducere tacită a MVP-ului.

### Inclus

- Linux x86_64, un operator local, o singură aplicație Omnis, un engagement activ; prima probă cu un copil, apoi maximum doi copii nativi Hermes.
- Aplicații/laboratoare proprii, izolate și autorizate; HTTP(S), formulare, REST/JSON, SPA, JS static și import OpenAPI local revizionat.
- Recon anonim și autentificat opțional; hartă și matrice de coverage; Brain, investigatori, validator separat, delte, approvals, Stop, pause/resume și reconciliere.
- Trei familii demonstrate: control de acces la obiecte (IDOR/BOLA), XSS reflectat, traversal read-only către canary autorizat. Etichetele IDOR/BOLA nu dublează aceeași verificare.
- Settings OpenRouter și `openai-codex`, catalog/editare/review/eval/publicare Skills; raport HTML/JSON, print și retest țintit.
- Ambele moduri general/focalizat, campanie adaptivă G-LOOP, path bounded G-PATH și Jev integrat/evaluat în shadow; advisory numai calibrat. Research contextual și improvement editorial sunt auxiliare, nu înlocuitori ai pentestului.

**Prima felie:** un copil, recon minim → BOLA → validator independent → raport/retest (G05a/G06a). **MVP coerent:** trei familii într-o buclă adaptivă, browser, ambele moduri, Jev, path bounded, Settings și gates P0–P8. **Produs competitiv:** extinderi E1–E4 din plan; trei familii sau E1 nu înseamnă paritate Strix. Omnis este construit prin reutilizare efectivă de cod/teste/prompturi/metodologie OSS (stack §10), nu wrapper Strix sau rescriere a fundației.

### Exclus din MVP, nu plafon permanent al produsului

SaaS, acces public, multi-tenancy, colaborare, SSO/MFA autonom, un nou framework de agenți, marketplace/autoinstall Skills, graph DB, vector DB, Redis/Celery, Kubernetes, execuție shell generică, scanarea LAN-ului, SQLi general, stored/DOM XSS, SSRF/OAST, upload executabil, brute-force, DoS și chains avansate (pathul bounded G-PATH este excepția adoptată). E1–E4 precizează promovarea subfamiliilor; SaaS/multi-tenancy și alt deployment cer decizie separată. Observarea unei suprafețe nesuportate nu o transformă în test executat.

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
| A10 | Scope/politică/mod/obiectiv/model/catalog imutabile pe run; Stop + nou run pentru modificări | Evităm migrarea live a permisiunilor; identitatea poate reautentifica numai într-un nou `auth_epoch` controlat |
| A11 | SSE Omnis cu replay; comenzi HTTP versionate și idempotente | Nici SSE Hermes, nici chatul nu sunt event store |
| A12 | UI Operate/Monitor: cockpit acceptat, stream și finding disclosure; Coverage/Endpoints cu tree/tabel/inspector | Păstrăm relațiile/proveniența; fără brain graph/council sau tab Chains. Excepție: path timeline bounded în inspector după G-PATH și review vizual separat, fără reinventarea cockpitului |
| A13 | Executabil host `omnis` → Compose detached + build web static same-origin | O comandă pentru operator, fără Vite/terminale multiple; pornirea aplicației nu pornește un assessment |
| A14 | `runtime-host` fix, părinte al Hermes stdio; canal Unix privat către supervisor | Stdio nu traversează singur containerele; nu montăm Docker socket și nu facem proxy admin generic |
| A15 | Definiții tipizate/revizionate, registry trusted și RunPlanSnapshot; instanțe adaptive sub definiție fixată | Nu DSL arbitrar, handler importat din editor sau alt scheduler |
| A16 | Research per engagement și maintenance editorial după quiescență, prin Hermes nativ | Ownership/date/bugete distincte; auto-learning global rămâne oprit |
| A17 | Jev DecisionAdvisor OFF/SHADOW/ADVISORY, evaluat pe heads bounded | Nu validator, publisher sau scope grant; lipsa lui nu blochează prima BOLA |

## 3. Procese, rețele și granițe de încredere

```text
Browser operator → loopback Omnis web/API → PostgreSQL + artefacte + seif
                                   ↓ comenzi durabile
                         supervisor Omnis (unic)
                           ├─ IPC privat → runtime-host → RPC stdio Hermes → copii
                           ├─ Settings → management Hermes privat
                           └─ action broker → HTTP / Chromium executori
                                               ↓ exclusiv proxy autorizant
                                     mitmdump + addon Omnis → fixture autorizat
```

Separăm procesele pentru ciclul de viață și autoritate, nu pentru scalare distribuită. Un singur repo, un singur model de domeniu și o singură DB Omnis. State DB Hermes este istoric de runtime, nu DB alternativă de produs.

**Baza de încredere:** launcherul host, supervisorul, runtime-host, brokerul, proxy-addonul, pluginul de identitate și runtime-ul Hermes fixat. Modelul, textele copiilor, skills nepublicate și conținutul țintei sunt neîncrezătoare. Copiii nativi au conversații separate în același runtime, nu sandboxes OS independente. Modelul nu primește execuție arbitrară în acest proces; compromiterea arbitrară a codului din baza de încredere și root/același UID malițios nu sunt izolate de un mapping de task.

### Topologie aleasă

- `control`: API, supervisor și DB; API instalat folosește UDS privat, forwarderul host servește numai loopback. Fără port Docker publicat. DB, endpointuri interne, management Hermes și proxy nu au porturi către LAN. Aceasta păstrează calea P0.4 deja probată în harness, nu declară launcherul implementat.
- `runtime`: Hermes are acces numai la unelte Omnis autentificate și la egressul providerului selectat; fără rută către ținte, host, metadata, DB sau API-ul web/admin. Se folosește un endpoint intern separat, nu se permite întregul Omnis API modelului.
- `executor`: HTTP și Chromium pot ajunge numai la proxy; fără DNS extern/direct, UDP/QUIC, SOCKS, host networking, Docker socket sau volum de proiect/personal. Fiecare context primește o identitate de transport distinctă, necunoscută modelului.
- `target`: numai proxyul poate ajunge la fixture. Fixture-ul nu ajunge la control plane, internet sau rețeaua personală; email/plăți/webhookuri sunt sinks de test. Evaluatorul deține seed/reset/canary, inaccesibile agentului.
- Provider egress (inclusiv Jev), target egress și **research egress** sunt trasee distincte. Research folosește adaptor/proxy de surse publice allowlisted, query minimizat, DNS/redirect/bytes/time caps și failover explicit; fără relay către țintă/control/host/metadata. Downloads sunt quarantine și nu execută PoC. Rețeaua refuză bypassul, nu doar un test pe hostname.

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

`127.0.0.1` este bindul **forwarderului host**, nu un port publicat de Docker. Amendamentul P0.4 păstrează API UDS privat/peer UID și forwarder host; înlocuiește schița veche cu publicare Compose loopback. DB/IPC/runtime nu capătă port public. Health-ul intern folosește Host-ul configurat, fără a lărgi allowlistul sau a accepta X-Forwarded-Host arbitrar. Probele complete LAN/launcher rămân G00 deschis; Uvicorn TCP direct este numai exemplu de dezvoltare.

**Bootstrap ales:** launcherul generează un cod local de pairing, unic/expirabil, afișat numai operatorului în terminal; formularul local îl schimbă o singură dată pe o sesiune opacă server-side. Codul nu apare în URL, Git sau log de request. Rată limitată, verificare Host/Origin și timeout. Cookie `HttpOnly; SameSite=Strict; Path=/`, fără `Domain`; HTTP loopback este limita asumată, nu pretindem TLS. Mutările cer și token CSRF legat de sesiune; SSE cere aceeași sesiune. Logout invalidează server-side; expirarea sesiunii UI nu anulează automat engagementul, dar nu permite control neautorizat. Refuzăm extinderea bindului; accesul remote ar cere TLS și alt threat model.

Un proces malițios cu același UID/root pe host rămâne în afara garanției. Nu prezentăm seiful, cookieul sau containerele drept protecție față de administratorul hostului.

Paths propuse pentru instalare, nu create acum: `$XDG_STATE_HOME/omnis` (implicit `~/.local/state/omnis`), runtime homes sub acest root, **nu sub `~/.hermes`**, configurație non-secretă sub `$XDG_CONFIG_HOME/omnis`, secrets cu permisiuni restrictive. Nu montăm `/home/kali`, checkoutul personal Hermes sau `.codex`. State/secrets/evidence/backups nu trăiesc în repo.

Settings și management Hermes au un singur writer; mutațiile provider/model/catalogului executabil sunt interzise în timpul unui run, exceptând Stop și revocarea credentialului care declanșează mai întâi oprire. Editarea unui draft Omnis neexecutabil poate continua: nu scrie în catalogul runtime și nu schimbă snapshotul; publicarea/selectarea noii versiuni se aplică numai unui run nou. Nu expunem proxy generic pentru config, filesystem, env reveal, terminal sau admin. Readback obligatoriu după set/delete/logout; `429`, `configured` și `oauth approved` nu înseamnă `inference_ready`.

### 4.1. Experiența instalată: `omnis`

**Contract propus pentru MVP, încă NEIMPLEMENTAT.** După instalarea explicită a releaseului local, operatorul execută **`omnis`** din orice director: serviciile pornesc în fundal, iar browserul implicit deschide Omnis când dashboardul este ready. La prima utilizare, pagina cere pairingul local de mai sus; nu intră neautentificat în datele engagementului. Cu sesiune validă, ajunge direct la dashboard. Nu pornește TUI-ul sau dashboardul administrativ Hermes.

`cli/` livrează un console script executabil `omnis` dintr-un wheel Python, cu mediu mic separat. Nu impunem un binar monolitic PyInstaller/Electron și nu pretindem că PostgreSQL/Chromium/Hermes sunt încorporate în acel fișier. Releaseul conține launcher, manifest/checksums, configurațiile Compose și imagini OCI fixate; buildul web este inclus în imaginea API, nu servit de Vite în utilizarea normală. Instalarea/pullul inițial și upgradeul sunt operații explicite, nu efecte ascunse ale startupului.

| Comandă propusă | Contract pentru operator |
|---|---|
| `omnis` | Start idempotent + așteptare readiness + deschidere browser |
| `omnis start --no-open` | Același startup, fără GUI; pentru headless/CI |
| `omnis open` | Deschide numai o instanță verificată deja pornită; nu pornește un run |
| `omnis status` / `omnis status --json` | Stare servicii, instance/release/schema, readiness separat; output sanitizat |
| `omnis pair` | Emite un nou cod local one-use/expirabil numai într-un terminal interactiv; nimic secret în JSON/argv/URL |
| `omnis run stop` | Oprește runul activ identificat explicit în comandă/output, fără confirmare; dashboardul rămâne pornit |
| `omnis stop` | Cere Stop/revocare/drenare, apoi oprește instanța și serviciile proprii; păstrează volumele/datele |
| `omnis doctor` | Diagnostic local sanitizat; nu face inferență, login, target probe sau reparare distructivă automată |

La rezolvarea runului activ, clientul de control leagă comanda de ID/revizie; dacă între timp contextul s-a schimbat, raportează conflict, nu oprește un alt run printr-o selecție implicită stale. Closing browser/terminal nu oprește serviciile detached. Nu instalăm implicit serviciu de boot al OS-ului; după reboot pornirea rămâne explicită și fără autoresume de assessment.

### 4.2. Startup determinist, independent de cwd

**Profile de livrare, nu stări simulate:** P0-control pornește numai PostgreSQL, API, supervisor inert și build web real de bootstrap/pairing în shellul acceptat. Nu are nevoie de runtime-host/P2 sau de SSE/P3 pentru dashboard_ready; aceste capabilități sunt UNAVAILABLE și assessment_ready=false. P1 adaugă engagementul persistent și interfața completă; P2 adaugă profilul runtime cu adaptorul real. Protocolul SSE este certificat în B08, nu dedus din pairingul P0. Manifestul/wheelul/buildul minim necesare startupului se produc în P0, iar B21/P8 închid releaseul complet.

**Inert înseamnă zero apeluri provider**, nu numai zero inferențe: fără validate, model discovery/pricing, refresh OAuth, login sau verificare online implicită la boot/status/health/open. Configurația/statusul local pot fi citite numai prin DTO-uri fără secrete; probele online Settings cer o acțiune/acord separate. Instalarea/pullul explicit sunt în afara startupului și nu îi dau dreptul să contacteze providerul sau ținta.

Owner: `cli/src/omnis_cli/instance.py` și `compose.py` pentru instanță; supervisorul este singurul owner al runului. Launcherul folosește căi absolute din manifestul releaseului, argv ca listă și environment allowlisted; nu citește `.env`, Compose overrides sau scripturi din cwd. Nu schimbă profilul Hermes personal.

1. Validează OS/distribuția, release/checksums, Docker/Compose disponibile, configurația non-secretă și permisiunile directoarelor. Regulile de host care cer privilegii se pregătesc prin instalare explicită; launcherul verifică precondițiile, fără sudo sau modificare globală de firewall pe ascuns. Nicio instalare, descărcare sau migrare de upgrade implicită. Release lipsă/incompatibil → eroare acționabilă.
2. Ia lock exclusiv local per instanță și verifică identitatea Compose/manifestului. Dublu launch reutilizează aceeași instanță; un PID sau un port care răspunde nu dovedește ownership. Numele proiectului/etichetele nu se deduc din cwd.
3. Port propus implicit **`127.0.0.1:8765`**, configurabil explicit numai cu serviciile oprite. Host/Origin allowlist urmează exact originul configurat. Port ocupat de alt proces → conflict, fără kill, auto-port sau deschidere a paginii străine. Pentru o instanță existentă verifică identitatea/readiness prin canalul local autentificat și originul HTTP asociat; dacă este sănătoasă, trece la deschiderea UI fără migrare/restart sau schimbarea writerilor. Pentru o instanță nouă continuă cu pasul 4; readiness HTTP se verifică după startup. Alt release/instance ID → refuz.
4. Pornește DB și așteaptă health bounded. Rulează jobul de migrare **o singură dată**, cu lock DB și verificarea schemei; la instalare nouă creează schema din release. La date existente, versiune incompatibilă/upgrade necesar → oprește startupul și cere procedura explicită de update/backup, nu migrează distructiv pe ascuns.
5. Pornește API-ul și supervisorul unic; adaptorul runtime inert se pornește numai dacă profilul P2 instalat/admis îl include. Absența lui în P0-control este UNAVAILABLE, nu healthy și nu blocaj al bootstrapului web. API servește numai assets trusted ale buildului și `/api` same-origin. Supervisorul dobândește ownership/lease DB, verifică inboxul și intenția durabilă de shutdown a instanței, marchează runurile întrerupte pentru reconciliere și nu reia prompturi/efecte. Admiterea rămâne închisă cât un shutdown este incomplet; operatorul finalizează `omnis stop`, apoi cere o nouă pornire. După oprire completă/instalare nouă, startupul explicit poate redeschide admiterea într-o generație nouă, numai după verificarea stării. Restart/reload API nu redeschide admiterea și nu creează al doilea supervisor.
6. Provisionarea normală a serviciilor de execuție rămâne ordonată: numai B01e-build plus B01e-integrated/G-NET pentru transportul cerut, reguli de rețea aplicate și self-test negativ al addonului permit containerele worker HTTP/browser. Certificarea se construiește înainte într-un harness separat, izolat și autorizat; nu prin activarea prematură a assessmentului. Niciun browser context, sesiune Brain sau request target nu se creează la boot. Proxyul refuză tot fără run/lease. Dacă aceste gates nu sunt disponibile, pornește **numai control plane-ul**, cu Start blocat și motiv vizibil; nu rulează proxyul respins pentru a obține un dashboard „verde”.
7. `DASHBOARD_READY` cere DB/schemă/assets/API/control sănătoase. `ASSESSMENT_READY` este separat și cere runtime/provider/policy/confinare/buget la preflight. Lipsa contului sau proxyului certificat nu împiedică folosirea drafturilor/Settings. Health nu apelează modelul sau ținta. Frontendul afișează gate-ul lipsă, nu cost zero sau zero findings înaintea răspunsului.
8. Launcherul generează codul de pairing local și înregistrează digestul/expirarea prin canalul local autentificat; valoarea se afișează numai pe TTY, nu în logs sau output JSON/redirecționat. Consumul atomic este al serviciului de sesiuni, nu al UI. În headless, pairingul este o acțiune ulterioară explicită. Deschide originul configurat (implicit `http://127.0.0.1:8765/`) numai după readiness; fără cod în query/fragment. Browser indisponibil → serviciile rămân ready, URL și instrucțiune de deschidere manuală, fără succes GUI inventat.

Bugetele startup/shutdown sunt finite și configurate, nu bucle infinite. Cod de ieșire propus: `0` pentru operația de lifecycle verificată (dashboard ready nu înseamnă assessment ready), `2` config/precondiție/port incompatibil, `3` startup/readiness eșuat, `4` stop/efecte nereconciliate. JSON include explicit `dashboard_ready`, `assessment_ready`, `browser_opened` și motivul degradării, niciodată coduri/secrete.

Eșec parțial: consemnează serviciile proprii pornite în această încercare și oprește numai acele resurse când nu există instanță preexistentă sănătoasă. Nu șterge volume sau date, nu oprește alte proiecte Docker și nu resetează DB. Un crash al launcherului lasă cel mult servicii fără lucru autorizat; următoarea pornire reconciliază identitatea/starea, nu lansează încă o copie.

### 4.3. Runtime-host, canale private și oprire

**A14 concretizează transportul peste izolarea deja cerută, nu înlocuiește Hermes nativ.** Supervisorul din `control` nu poate controla stdio-ul unui proces din alt container fără adaptor. `integrations/hermes/src/omnis_hermes/runtime_host.py` este părintele fix al procesului Hermes, în namespace-ul runtime; deține stdin/stdout, stderr separat, process group, semnale și reap. Supervisorul păstrează task binding, autoritate, scheduling și DB; adaptorul nu are DB de produs, queue durabilă proprie sau libertatea de a genera taskuri. Hermes JSON-RPC stdio rămâne protocolul nativ documentat; framingul și metodele exacte se verifică pe pin în H01, nu se presupun din documentația curentă.[2]

- **IPC supervisor ↔ runtime-host:** socket Unix într-un volum privat montat numai acestor servicii; director/owner/mode verificate, identitate peer și capability locală per boot, corelată cu generația/fencing epoch. Nu se publică un port sau Docker socket. Capability nu intră în prompt, schema toolului sau log. Nu montăm IPC în HTTP/browser/proxy, web sau evaluator; runtime model-facing nu primește unelte de citire a filesystemului arbitrar.
- `runtime_protocol.py` definește numai operațiile necesare launch/stop/status și schimbul allowlisted de mesaje RPC; fără shell, argv/cwd/path arbitrar, `cli.exec` sau forwarding nelimitat de metode. Dimensiune/frame, coadă, backpressure, timeout, request ID și reverse requests sunt bounded. EOF/submit cu răspuns pierdut → reconciliere, nu retry orb; approval fără operator nu este aprobare implicită.
- Managementul Hermes rămâne loopback în container, accesat de adaptor numai prin operații Settings tipizate. Writerul management și writerul de execuție sunt mutual exclusive. Nu există un proxy admin generic disponibil API-ului/browserului/modelului.
- Watchdog/lease pe adaptor și executori: pierderea supervisorului, a canalului sau a autorității DB blochează efectele și oprește bounded întregul process group Hermes, inclusiv lucrul detached. Refuzul toolurilor singur nu este dovadă că inferența s-a oprit. Mesajele/generațiile vechi sunt refuzate la reconnect. A→B→A și refresh ownership din §5 rămân obligatorii.
- **IPC operator ↔ control plane:** socket local separat `control.sock`, disponibil launcherului host și componentei de control, nu runtime-ului. `api/src/omnis/transport/local_control.py` autentifică owner/peer și capability locală; permite doar status/pairing/stop și tranziția tipizată de admitere a instanței după startup/reconciliere. Acest canal nu ocolește autoritatea DB, nu devine HTTP admin fără sesiune și nu împrumută tokenul administrativ Hermes. UID mapping și permisiunile socketurilor sunt probe P0/P2, nu presupuneri bazate numai pe un volum.
- **Un singur client de container lifecycle:** launcherul host are accesul operatorului la Compose. Nici API, supervisor, runtime, executori, proxy sau tool model-facing nu primesc Docker socket, privileged mode sau generic exec. Serviciile fixe sunt provisionate de launcher în ordinea §4.2; supervisorul activează doar procese/contexte tipizate din containere deja admise. Dacă lipsește serviciul, Start este blocat, nu provisionat printr-un escape hatch.

`omnis run stop` și butonul Stop folosesc aceeași comandă durabilă/idempotentă: revoke/fence → închidere admitere pentru run → întrerupere/drenare runtime/executori → readback. `STOPPING` rămâne până la dovada quiescenței; bytes deja trimiși pot rămâne UNKNOWN.

**Oprirea instanței are o barieră suplimentară, înainte de Stop run.** Toate comenzile CLI care schimbă lifecycle-ul instanței folosesc același lock local. `omnis stop` persistă tranzacțional în `InstanceControl` intenția de shutdown, `admission_open=false`, un `shutdown_command_id` idempotent și o generație monotonă. Start/Resume, launch/continuare model, writer Settings și fiecare admitere de task/acțiune verifică această barieră sub același lock DB/tranzacție; nu este o bifă în UI. Astfel, un Start concurent fie este admis înaintea închiderii și inclus în oprire, fie este refuzat cu `INSTANCE_SHUTTING_DOWN` — niciodată admis între quiescență și oprirea containerelor. Stop și citirile de diagnostic rămân permise.

Cu admiterea instanței închisă, supervisorul oprește runul și writerii prin adaptoarele tipizate, persistă dovada de quiescență/generație, apoi launcherul oprește numai containerele proprii, cu deadline și fără `down -v`/ștergere de date. API și DB rămân disponibile până la persistarea rezultatului. Crashul launcherului nu șterge intenția din DB și nu redeschide admiterea; noul proces continuă shutdownul idempotent. Receiptul local de containere oprite nu rescrie singur stările de run/effect din DB. O nouă pornire explicită verifică finalizarea și generația înainte de redeschidere; un run nereconciliat rămâne blocat separat de disponibilitatea dashboardului.

Dacă API/supervisor nu mai răspund, launcherul poate opri numai containerele identificate din manifest/etichete/ID-uri proprii, inclusiv runtime, executori și proxy, pentru a elimina căile de efect. Raportează **oprire de urgență / stare nereconciliată**, nu inventează `STOPPED` în DB. La restart, runul intră în NEEDS_RECONCILIATION; nu autoresume și nu retry al acțiunilor UNKNOWN. Nu folosim `pkill`, kill după port sau curățare globală Docker.

### 4.4. Instalare, stare și artefacte în afara repo-ului

| Root propus | Conținut și owner |
|---|---|
| `$XDG_CONFIG_HOME/omnis/config.toml` | Configurație non-secretă a operatorului; niciun grant/token |
| `$XDG_DATA_HOME/omnis/releases/<version>/` | Manifest/launcher/artefacte trusted ale releaseului; nu modificate de run |
| `$XDG_STATE_HOME/omnis/instance.json` | Instance/release/Compose identity, schema și origin; fără secrete |
| `$XDG_STATE_HOME/omnis/postgres/` | Numai DB; mount/PGDATA exact pentru imaginea 18 verificat în P0 |
| `$XDG_STATE_HOME/omnis/evidence/` | Bloburi/derivate și staging ale serviciului evidence; fără mount runtime |
| `$XDG_STATE_HOME/omnis/runtime/active/` | Slotul Hermes dedicat; provider store unic, nu profilul personal |
| `$XDG_STATE_HOME/omnis/runtime/archives/` | Starea per-engagement arhivată numai cu writerii opriți; nemontată altui caz |
| `$XDG_STATE_HOME/omnis/catalog/releases/` | Pachete publicate/digesturi, montate read-only pentru run |
| `$XDG_STATE_HOME/omnis/vault/` | Chei/handles target cu owner/mode restrictiv; cheia în afara backupului comun |
| `$XDG_STATE_HOME/omnis/logs/`, `exports/`, `backups/` | Date inventariate și retenție separată conform §10 |
| `$XDG_RUNTIME_DIR/omnis/` | Lock/control IPC/capabilities efemere; mod 0700, fișiere secrete 0600 |

Defaults XDG sunt cele ale utilizatorului (`~/.config`, `~/.local/share`, `~/.local/state`). Dacă XDG_RUNTIME_DIR lipsește, se folosește un subdirector privat verificat `runtime-ipc/` sub state, nu un director partajat temporar. IPC runtime privat are mountul lui, separat de `control.sock`. Căile sunt canonice, owner/mode verificate, symlinkuri nesigure refuzate; startupul nu adoptă date din home-ul personal Hermes. Nu se copiază `documents/Omnis_UI_Prototype.html`, `.hermes/skills` sau toolurile de dezvoltare în catalogul executabil ori buildul produsului.

### 4.5. Acceptarea launcherului — G00 rămâne deschis

| Probă | Rezultatul cerut, cu output real | Poartă |
|---|---|---|
| L01 Instalare și cwd | `omnis` instalat pornește din alt director, servește assets din release și deschide numai originul verificat | G00/G-OPS |
| L02 Concurență | Două launchuri, lock/PID stale și port străin nu creează două instanțe/supervisoare și nu ating alt serviciu | G00 |
| L03 Startup inert | Boot/status/health/API reload/open: zero inferențe, validate/discovery/pricing/OAuth refresh și target effects; doar servicii locale declarate | G00/G01/G02 |
| L04 Migrare/partial failure | DB indisponibilă, job concurent, schemă incompatibilă sau asset lipsă blochează readiness fără ștergeri | G00/G-OPS |
| L05 Pairing/control | P0: one-use atomic, expiry, Host/Origin/CSRF, peer/capability greșit, zero codes în URL/argv/log/JSON. B08 completează autentificarea/expirarea SSE real. | G00-control / G03a-SSE |
| L06 Runtime bridge | Fragmentare, reverse requests, stderr flood, backpressure, EOF, submit incert și generație veche sunt tratate fail-closed | H01/G02 |
| L07 Provisionare izolată | Proxy neadmis/addon absent → niciun executor; namespace/host/metadata/IPv6/Docker/IPC neautorizat refuzate | G-DEPENDENCIES/G-NET |
| L08 Stop și crash | G00: barieră/admitere atomică reală cu lucru inert, crash launcher și restart închis. P2/P3/P7: integrarea Start/Resume/Settings/raport și runtime/execuție, fără efect nou/auto-wake, cu dovadă reală de quiescență. | G00-core/G02/G03/G07 |
| L09 Persistență/restart | Browser/terminal închis nu oprește serviciul; stop/start păstrează datele, fără assessment autoresume | G01/G-OPS |
| L10 Release/headless/recovery | Fără GUI → URL fără secret; update cu backup; restore separat/cheie lipsă → LOCKED și lease-uri vechi refuzate | G-OPS/G08 |

Nicio probă a prototipului HTML sau a launcherului **de dezvoltare** `scripts/hermes_dev.py` nu închide aceste criterii. `omnis` este livrat numai după exercitarea artifactului instalat și a proceselor reale.

**Stare locală P0.1–P0.3:** API/pairing/control/supervisor și bariera inertă sunt păstrate; [P0.2](verification/p02-local-control.md) și [bootstrapul web P0.3](verification/p03-local-bootstrap.md) au dovezi separate. Buildul React este servit same-origin, cu pairing/session/logout și status real, fără DEMO. `GET /health/ready` păstrează HTTP 200 pentru API-ready; `dashboard_ready` și `dashboard_reason` verifică separat assets și controlul privat. Statusul IPC validează lease-ul fără reînnoire; timpul de citire a asseturilor și numărul de workeri sunt bounded. `assessment_ready=false`. G00/L01–L05-control/L08-core complete așteaptă P0.4: launcherul `omnis`, manifestul și certificarea topologiei/UID. FINALIZE persistat certifică numai quiescența controlului inert; redeschiderea cere epoch nou și comandă explicită. Launcherul trebuie să verifice resursele/receiptul opririi, iar P2/P3 extind predicatul cu adaptoarele reale.

## 5. Runtime Hermes și autoritatea copilului

Pinul de cod este `0.21.5` / `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Mediu instalat separat, nu copiat cu toate datele din home-ul personal. JSON-RPC stdio este suprafața aleasă pentru sesiuni, întrebări server→client și subagenți; documentația oficială distinge această suprafață de HTTP Runs.[2] Referința de adaptor de mai jos păstrează contractele utile din auditul static, fără dependență de o propunere veche.

**Un singur runtime activ și un singur store de credentiale AI.** Alegem un home de produs dedicat, cu un singur slot activ de engagement, nu copii de OAuth grants în homes concurente. Supervisorul oprește complet writerii înaintea schimbării engagementului și mută starea de caz (state DB, sessions, logs, caches și derivatele inventariate) într-o arhivă per-engagement nemontată runtime-ului următor; în slot rămân numai provider store/config aprobate și catalogul comun read-only. Restaurarea unui caz mută numai starea lui, cu verificarea ID-ului și cu permisiuni noi, înaintea startupului. Nu relocăm fișiere SQLite/WAL sub procese active și nu folosim symlinkuri către grants pe care un atomic replace le-ar putea rupe.

Managementul Hermes pornește exclusiv pentru Settings când writerul de execuție este oprit; apoi se închide înaintea runului. Runtime-ul activ este singurul proprietar al refreshului. UI citește statusul din proiecția Omnis când runul este activ; nu lansează validări sau modificări admin concurente. Inventarul exhaustiv al căilor de stare și proba A→B→A cu markeri sunt H02/G-DATA: dacă un path rămâne partajat sau un credential este adoptat implicit, gate-ul eșuează. Aceasta este gestionare de volume/stare a supervisorului, nu presupunerea unui flag Hermes inexistent. Memorie globală și auto-learning dezactivate în engagement; excepția editorială strictă din §6.2 folosește slotul de maintenance după quiescență, nu curator continuu. Arhivele nu devin accesibile prin tooluri model-facing.

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

Uneltele nu includ credentiale în schema lor. Read APIs validează ownership/contextul emitentului (§9.7): run și root binding pentru Brain, assignment/attempt/identity pentru copil; aceeași rigoare ca write APIs, fără a inventa un child înainte de delegare. Nu se copiază chain-of-thought în UI; afișăm ipoteze, decizii scurte, motive, acțiuni și dovezi.

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

**Bootstrap Settings privat:** supervisorul cere operația tipizată prin runtime-host; adaptorul din container folosește `hermes serve --isolated --host 127.0.0.1 --port 0`, cu `HERMES_HOME` dedicat și `HERMES_DASHBOARD_SESSION_TOKEN` aleator injectat. Adaptorul descoperă portul din `HERMES_BACKEND_READY port=<PORT_ALOCAT>`, verifică `/api/health` și un GET autentificat pe loopbackul acelui container; supervisorul nu accesează direct loopbackul altui namespace. În modul loopback fără gate extern, headerul este `X-Hermes-Session-Token`. Acesta nu este `API_SERVER_KEY` sau cheia AI. Se aplică regula unui singur writer din §5: managementul este oprit înaintea execuției. Ancore: `hermes_cli/main_dashboard.py:810–901`, `hermes_cli/web_server.py:317–445`.

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

### 5.1. Jev DecisionAdvisor

**HF08, integrare decisă, nu prerechizit al primului finding.** Adaptorul `integrations/jev` folosește SDK-ul async TypeSafe 0.7.2/model candidat `jev-1.13.0` și întrebările NeuroSploit adaptate (stack §10 U07/U13). Acesta nu este un Brain suplimentar. Primele heads: **relevanță/triage** după recon/clue și **stagnare** după rezultat fără progres; dedup/critica impactului/wordlist/path ranking sunt extensii evaluate separat. OFF păstrează același pentest, SHADOW înregistrează fără influență, ADVISORY poate ordona numai candidați deja admisibili după evaluare/calibrare. Niciodată scope grant, CONFIRMED, CVSS factual, ștergere de obligație sau Publish.

`DecisionSupportRevision` (schema_version=1, id/revision/digest tip §9.3) conține `mode: OFF/SHADOW/ADVISORY`, `model_id: Text exact`, `head_refs: Ref[]`, `question_refs: Ref[]`, `projection_schema_ref: SchemaRef`, `threshold_refs: Ref[]`, `data_policy_ref: Ref`, `deadline_seconds: integer 1..30`, `max_calls: integer 0..100`, `fallback: BRAIN_WITHOUT_ADVISOR/DETERMINISTIC_ORDER`, `budget_ref: Ref`, `provider_config_ref: Ref`. RunSnapshot fixează totul; secretul stă separat, fără fallback la profilul personal. `DecisionReceipt` leagă run/task/attempt, mission/focus/snapshot, candidate IDs opace și reviziile de întrebare/proiecție, digestul cererii finale, modelul efectiv, distribuție/scor tipizat, usage/latency/cost cunoscut sau UNKNOWN și motivul fallbackului. Receiptul este evidence despre advisor, nu despre vulnerabilitate.

Brainul construiește setul finit de candidați; backendul îl filtrează prin mission/policy înainte de ranking. Proiecția include obiectiv/non-goals **redactate și aprobate**, facts/refs relevante, niciodată raw headers/body/secrete ori transcript. Întregul payload serializat (state, questions, criteria, option labels), erorile și logurile sunt allowlisted și sentinel-tested. Nu acceptăm `extra_body`/`extra_headers` arbitrare; răspunsul trebuie să aibă exact headurile/choices/ranges/modelul așteptate, nu doar parse SDK reușit. Missing/invalid/timeout → fallback explicit, nu allow/continue optimist. RetryPolicy(max_retries=0); orice reluare este dispatch readmis și bugetat.

Provider egress Jev se probează separat la sink de target/research. După commit Stop/Pause nu se admit noi dispatchuri Jev și nici wake implicit; apelurile deja trimise rămân remote in-flight/UNKNOWN până la readback posibil, nu pretindem că am oprit inferența pe serverul extern. G-JEV: fixtures tipizate/sentinel → live shadow cu cont/date/buget aprobate → paired OFF/SHADOW/ADVISORY versus heuristică deterministă, aceleași misiuni/bugete; calibrăm pe set separat de held-out. Advisory se activează pe head numai dacă beneficiul și pragurile prestabilite trec fără creștere acceptată tacit a misses/FP. În lipsă rămâne shadow/OFF și raportăm rezultatul; integrarea Jev nu este redeschisă ca decizie de produs.

### 5.2. Model admission înainte de inferență

**F04 / B06m / G-MODEL:** primul consumator este P2-live, nu HTTP-ul din B07. `policy/admission.py` și `policy/budgets.py` introduc la B06m numai nucleul de admitere/rezervare pentru model; supervisorul și adaptorul Hermes îl folosesc înaintea primei inferențe, inclusiv testul Settings. B07 extinde **același ledger/owner** cu requesturi target, bytes și approvals, fără contabil paralel. În P0 nu se creează aceste module. Acordul operatorului și un număr scris în TaskBrief nu sunt enforcement.

`ModelDispatch` este înregistrare backend versionată (§9.3), cu `run_or_job_ref: Ref`, `turn_attempt_id: Id`, `runtime_binding_ref: Ref`, `purpose: PREPARE/RECON/INVESTIGATE/VALIDATION/RESEARCH/DECISION/MAINTENANCE/SETTINGS_TEST`, `provider_config_ref: Ref`, `model_id: Text`, `projection_digest: Digest`, `reservation_ref: Ref`, `fencing_epoch: integer ≥1`, `deadline: UTC`, `technical_caps: {calls: literal 1, output_tokens: integer 1..65536, wall_seconds: integer 1..1200}`, `usage_state: KNOWN/PARTIAL/UNKNOWN` și `provider_receipt_ref: Ref?`. Orice turn/call/model auxiliar/fallback aparține unui dispatch autentic; IDs/roluri revendicate de model nu schimbă purpose-ul contabilizat.

Ledgerul tranzacțional are `RESERVED → SENT → SETTLED`, respectiv `RELEASED` numai dacă este dovedit că nimic nu a fost trimis; pierderea răspunsului după send păstrează `UNKNOWN` și rezerva până la reconciliere. Persistăm intenția SENT înaintea trimiterii; crash în fereastra incertă nu rambursează fictiv. Două dispatchuri nu pot cheltui aceeași rezervă. Costul observat, estimarea și limita sunt câmpuri distincte; quota/preț Codex necunoscut nu devin zero. Plafon monetar strict este disponibil numai cu rezervare conservatoare verificabilă sau cap provider verificat; altfel cererea de plafon strict este BLOCKED, ori operatorul alege explicit caps tehnice și acceptă costul necunoscut, fără badge „financially enforced”.

Enforcement-ul cerut este **înainte de fiecare cerere de inferență efectivă**, inclusiv retry, fallback, delegare și auxiliare. Adaptorul folosește un seam trusted pre-call/proxy de provider capabil să asocieze exact requestul; H08 îl verifică pe pin, nu presupune o funcție native inexistentă. Reîncercările implicite sunt dezactivate sau primesc dispatch/rezervă nouă. Un hook after-call sau numai `prompt.submit` nu certifică această garanție. Dacă pinul nu permite legarea/refuzul înainte de send, G-MODEL rămâne BLOCKED până la extensie/patch minimal auditat, fără a înlocui Hermes. B06m fixează și probează caps de calls/output tokens/deadline la frontiera efectivă; o setare transmisă dar ignorată nu trece poarta.

Rezerva `VALIDATION` aparține ledgerului runului și nu poate fi consumată de recon/Brain/research/Jev. Purpose-ul vine din binding, nu din JSON. RunSnapshot fixează bugetele; subbugetele copiilor/auxiliarelor nu multiplică bugetul părintelui. Jev și maintenance folosesc aceeași disciplină de rezervare pe bugetul lor aprobat; nu moștenesc grantul unui run oprit. SHADOW nu influențează alegerile prin recomandare, dar consumă resurse și overheadul se măsoară explicit; nu este „fără cost/efect temporal”.

Bariera InstanceControl și fencingul se reverifică între reserve și send. Stop/Pause interzic dispatchuri noi, inclusiv wake nativ; anularea locală nu pretinde retragerea calculului remote deja trimis. Un tur cu submit incert se reconciliază, nu se repetă pentru a obține un răspuns. G-MODEL probează pozitiv un call admis și negativ cap epuizat, rezervări concurente, Stop între reserve/send, răspuns pierdut, retry/fallback neadmis și usage UNKNOWN; boot/status rămân zero provider calls. P2-inert folosește fixture de protocol fără provider; P2-live cere separat cont/model/date/buget autorizate.

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

**Review operator pentru raport, separat de validare:** `report_review_policy` este ales explicit în draft și fixat în revizia runului: `OPERATOR_REQUIRED` (preselectat conservator pentru un draft nou) sau `VALIDATOR_ONLY`. Primul cere `ReportReview=PENDING | APPROVED | HELD` pentru fiecare finding CONFIRMED; al doilea produce `NOT_REQUIRED`. Nu decide LLM-ul și nu derivăm cerința din culoarea severității. Păstrăm actorul, `claim_revision`, evidence manifest/version, `review_revision` și auditul. Acceptarea manuală nu produce CONFIRMED. Acceptarea cere ownership, revizie curentă și evidence disponibile; Hold respectă ownership/revizia fără a pretinde verificarea bytes lipsă; schimbările materiale ale claimului/evidence version invalidează acceptarea. La generare sunt eligibile numai findingurile tehnic CONFIRMED cu review APPROVED sau NOT_REQUIRED. Raportul păstrează copia stării la generare; deciziile ulterioare nu rescriu snapshotul anterior. Contractul de date UI este în specificația UI/UX §8; acest flux este propus, nu implementat în backend.

**ReportReview nu blochează COMPLETED** și nu menține modelul pornit: este o coadă editorială, separată de operational Action/Approval. Accept/Hold pot urma unui run STOPPED/COMPLETED, cu aceleași controale de ownership/revizie, fără a relansa execuția. În predicatul de mai jos „approval restant” înseamnă permisiune operațională/efect, nu includerea în raport.

**Predicat de finalizare:** numai supervisorul poate închide runul. `COMPLETED` cere frontiera de discovery epuizată în subsetul declarat, toate celulele obligatorii aplicabile cu rezultat probatoriu, toți candidații validați, niciun task/inbox/approval/cleanup/efect UNKNOWN restant și runtime/executori quiescenți. Propunerea Brainului de închidere nu este autoritate. Lucru restant din limită, policy/auth/unsupported relevant sau stagnare → `LIMITED` cu lista exactă; efecte externe nereconciliate → `NEEDS_RECONCILIATION`, chiar dacă raportul parțial poate fi exportat. Stagnare implicită: trei tururi consecutive fără observație/dovadă/precondiție nouă, consum de rezultat nou sau schimbare justificată de task; retries identice nu resetează contorul. Pragul este fixat în run manifest. `COMPLETED` certifică obligațiile catalogului în misiunea și scope-ul declarat (§9.3), nu siguranța întregii aplicații. Criteriile funcționale au outcomes separate; FAIL funcțional nu este automat vulnerabilitate sau run neterminat.

### Stop, pause, sănătate

**Progresul nu este stare de control.** `RunProgress` este proiecția server-side a supervisorului, cu `phase=PREPARE|RECON|INVESTIGATE|VALIDATE|FINALIZE|UNKNOWN`, `phase_active`, `phase_updated_at` și activitate redactată bounded. Faza rezultă din lucru admis și tranziții de domeniu, nu din textul Brainului; la activități mixte validarea are prioritate în rezumat, iar taskurile individuale rămân vizibile în stream. `phase_active=false` când runul nu este RUNNING. PAUSING/PAUSED/STOPPING/STOPPED/NEEDS_RECONCILIATION au precedență în banner; ultima fază poate rămâne numai etichetată istoric. Re-renderul, review-ul unui finding sau SSE replay nu pot reactiva faza. Barele requests/timp și coverage nu sunt un procent de „pentest complet”.

Stop nu cere confirmare modală: revocă `fencing_epoch`, blochează noi dispatchuri, întrerupe Hermes, închide admiterea proxy/context/procese și așteaptă quiescența. UI rămâne `STOPPING` cât verificarea nu e completă. La timeout, supervisorul comandă terminarea process groupului prin runtime-host/adaptorul executorului; watchdogurile locale sunt fallbackul bounded. Numai launcherul host poate opri containerele conform §4.3. Dacă un adaptor nu răspunde, supervisorul afișează escaladarea și efectele incerte, fără `STOPPED` sau dovadă de quiescență inventată; operatorul poate folosi oprirea de urgență a instanței. Nu declarăm anularea requesturilor deja expediate. Bariera `InstanceControl` se aplică suplimentar la shutdownul aplicației, nu numai fencingul runului curent.

Pause oprește **dispatchuri noi**, nu numai taskuri noi; acțiunile deja expediate se pot drena în timeout. Permituri emise dar nefolosite sunt invalidate. Wake nativ în timpul pauzei nu trebuie să producă inferențe noi; dacă pinul nu poate garanta asta, închidem runtime-ul după drenare și reluăm din checkpoint într-un runtime nou. Resume face preflight și reconciliere, nu reînvie threaduri.

Defaults de fixture, de confirmat prin probe: maximum doi copii; o acțiune target în zbor; maximum o cerere/secundă per origin fără burst; deadline per cerere 15 secunde; lease 5 secunde, heartbeat 1 secundă; Stop fără dispatch nou după commitul revocării, quiescență locală în 10 secunde sau escaladare vizibilă. Ceas monotonic pentru deadline local, UTC pentru audit. Nu sunt performanțe măsurate.

Health: probe incluse în scope/buget, baseline la preflight; 429 respectă `Retry-After` în limite, altfel backoff bounded; 503 sau trei eșecuri consecutive de health blochează noi dispatchuri și cere review. Nu reluăm mutații pe retry automat. Bugetul global include login, redirecturi, subresurse, health, baseline/control și validare. Costul AI estimat/necunoscut este separat de hard caps de timp/request; plafon financiar numai dacă poate fi rezervat/verificat înaintea apelului sau impus la provider.

### 6.1. Bucla de investigație condusă de Brain

**HF07, traseu normativ, nu run executat:** obiectiv → recon/mapping incremental → threat model/ipoteze → specialiști → validare independentă → delte/replanificare → recon suplimentar/altă investigație/chaining → raport/retest. Brainul conduce întregul fir; supervisorul admite/limitează și finalizează. Research este opțional când ajută o lacună concretă; improvement pregătește versiuni viitoare și nu înlocuiește investigația.

| Moment / revenire | Comportament și rezultat verificabil |
|---|---|
| Start/PREPARE | Cererea salvată este fixată în RunSnapshot; Brain propune MissionSpec, backendul validează FocusEnvelope. Preflight/auth/health și bootstrapul sunt bugetate. Nu există swarm la startup. |
| Recon inițial | Copil nativ Recon + unelte reutilizate observă operații/params/JS/forms/OpenAPI; maparea persistă provenance, observed/inferred și gaps. Un minim util permite prima ipoteză fără a aștepta recon „perfect”. |
| Threat model | Brain compune actori/obiecte/trust boundaries/tehnologii/ipoteze din facts citate. `ThreatModelRevision` este proiecție revizionată a Observation/Relationship, nu JSON global sau adevăr duplicat. Jev poate ranka; nu este obligatoriu per request. |
| Specialist | TaskBrief specific: ipoteză, baseline/probe/control, identitate/business, procedură fixată, capabilități și limite. Rezultat = claim/clue/contraexemplu/gap, nu numai finding. |
| Validator incremental | După eliberarea slotului, attempt/context independent produce probe proaspete și controale. Serviciul de verdict admite tehnic; nu așteptăm sfârșitul întregii campanii. |
| Contraexemplu / auth drift | Delta consumată o singură dată → închidere justificată, precondiție nouă, remapping ori altă ipoteză. Auth invalid nu devine negativ/FIXED; repetarea identică nu este progres. |
| Clue transversal | Exemplu de dezvoltare: canaryul traversal autorizat citează o operație omisă relevantă aceleiași misiuni. Este observație neîncrezătoare, nu instrucțiune sau extindere de scope. |
| Recon suplimentar | Brain cere confirmarea acelei operații/context auth, nu recrawl global. Harta/numitorul au revizie nouă și basis refs; un nou task BOLA poate reutiliza procedura fixată. Aceeași cauză produce occurrence, nu finding duplicat. |
| Path | Matching requires/provides adaptat din NeuroSploit generează ipoteză; test și replay probează ambii pași **și tranziția**. Canar→referință necesară→acces nepermis este scenariul bounded, nu rezultat pretins. |
| Reconciliere / raport | Frontieră/obligații/candidați/efecte/cleanup reconciliate, apoi predicat §6; lipsurile rămân LIMITED sau NEEDS_RECONCILIATION. Rendererul citește snapshot eligibil; report review nu ține runtime deschis. Retest = run nou/probe noi. |

Pool: **un copil în prima probă; apoi maximum doi copii activi, inclusiv validatorul/researcherul, pe lângă Brain**. Mapping/fingerprint/wordlist/parsing sunt module, nu agenți obligatorii. Brain poate aștepta fără inferență continuă. Specialistul care predă eliberează slotul; research așteaptă când validarea are prioritate. Eșec research blochează numai dependența sa, nu fire independente; auxiliarele deja pornite se drenează/opresc bounded la închidere.

Relațiile includ `observed-on/requires/yields/contradicts/tested-by/enables`, cu evidence, identity/auth epoch, state și revision. Handofful folosește TaskResultV1: source task/attempt, basis refs, new fact/delta, suggested family, required context, open items și cleanup refs. Nu pune un secret în new_fact; backendul poate injecta un handle numai într-un pas admis. AttackPath are `id/revision`, ordered step refs, transition evidence refs, preconditions/context și `INFERRED/PROVEN/INCOMPLETE/INVALIDATED`; same-host/CWE/keyword/Jev confidence nu probează edge-ul. `needs-review` și no-evidence nu intră în frontieră executabilă ca și capabilități probate. Un path incomplet păstrează findingurile componente; nici paths, nici occurrences nu cresc root-cause count. G-LOOP urmează G06a; G-PATH urmează G-LOOP și familiile necesare, fără obligație retroactivă în prima BOLA.

### 6.2. Module versionate, research și improvement

Definițiile/codul/config/prompturile sunt fixate per run; observațiile, taskurile și input artifacts pot crește adaptiv sub aceste definiții. **Configurare** = selectare/parametri/ordine; **metodologie** = pachet/procedură/overlay; **capabilitate nouă** = handler/parser/oracle/adaptor trusted + teste/release. Primele două nu cer modificarea schedulerului; ultima nu se obține dintr-un textarea cu cod. Nu există DSL arbitrar, `eval`, Jinja executabil, import path sau install hook din editor.

Contractele de mai jos au schema_version=1, id/revision/digest și regulile de tip/ownership/caps §9.3–9.4. Sunt documente/relații în agregatele existente, nu servicii/tabele/module obligatorii în P0:

| Definiție / owner | Câmpuri și invariant |
|---|---|
| WorkflowProfileRevision / settings | `phase_refs: Ref[]`, `selected_action_refs: Ref[]`, `config: object strict per schema`, `limits: Limits`, `dependency_refs: Ref[]`; clone/edit/reorder numai între module publicate, controale core nedezactivabile |
| PhaseDefinition / settings | `key: Key`, `label: Text`, `progress_phase: enum RunProgress`, `subphase_refs: Ref[]`, `expected_output_schema_refs: SchemaRef[]` |
| SubphaseDefinition / settings | `key: Key`, `action_refs: Ref[]`, `input_schema_refs: SchemaRef[]`, `prerequisite_refs: Ref[]`, `priority: integer 0..1000`, `optional: bool` |
| ActionDefinition / tasks registry trusted | `handler_id: Key`, `config_schema_ref/input_schema_ref/output_schema_ref: SchemaRef`, `procedure_refs: Ref[]`, `requires/provides/predicate_ids: Key[]`, `execution_class: PURE/RESEARCH_IO/TARGET_IO/MODEL`, `requested_capabilities: Key[]`, `effect_ceiling: enum §7`, `limits: Limits`, `retry_policy: NEVER/PURE_RECOMPUTE/READMIT`, `invalidation_predicate_ids: Key[]` |
| RunPlanSnapshot / runs | `run_ref: Ref`, `profile_ref: Ref`, `definition_refs: Ref[]`, `config_digest: Digest`; immutable definiții. PlanInstance separat: `iteration: integer 1..10`, `causation_ref: Ref`, `input_refs: Ref[]`, `task_refs: Ref[]`, `through_cursor: Cursor` |
| TechnologyObservation / surfaces | `product/vendor: Key`, `version_raw: Text`, `parsed_version: Text?`, `detector_ref: Ref`, `evidence_refs: Ref[]`, `epistemic_state: OBSERVED/INFERRED/CONTRADICTED`, `precondition_refs: Ref[]`; banner/version ambigue nu devin adevăr exact |
| ResearchRequest / tasks | `run/task/attempt/snapshot/mission: Ref`, `public_fact_refs: Ref[]`, `question: Text`, `sources_policy_ref: Ref`, `limits: Limits`; inputul permis de data policy, nu export brut de caz |
| ResearchResult / evidence + surfaces | `request_ref: Ref`, `status: COMPLETE/PARTIAL/BLOCKED/FAILED`, `source_records: {url: Text, retrieved_at: UTC, version: Text?, excerpt: Text, content_digest: Digest?}[]`, `lead_refs: Ref[]`, `preconditions: Precondition[]`, `gaps: Text[]`; digest numai pentru bytes recuperați, advisory ≠ finding |
| WordlistRecipeRevision / settings | `source_refs: Ref[]`, `kind: PATH/PARAMETER/EXTENSION/ROUTE_TEMPLATE/BENIGN_PROBE`, `transform_ids: Key[]`, `encoding: UTF8`, `seed: integer ≥0`, `max_entries: integer 1..10000`, `max_bytes: integer 1..1048576`, `ranking_ref: Ref?` |
| WordlistArtifact / evidence | `recipe_ref: Ref`, `input_refs: Ref[]`, `artifact_ref: Ref`, `counts_before/after: integer ≥0`, `exclusion_reasons: Text[]`, `truncated: bool`, `candidate_provenance_ref: Ref`; ordine exactă și digest, niciun overwrite al artifactului consumat |
| ImprovementDraft / settings | `target_ref: Ref`, `base_digest: Digest`, `reason/failure_category/expected_benefit: Text`, `source_refs: Ref[]`, `files_diff_ref: Ref`, `changed_capabilities: Key[]`, `proposed_test_refs: Ref[]`, `estimated_cost: decimal-string?`, `review_ref/eval_ref: Ref?`; autorul propune, nu publică singur |

Registry/compiler adaptează S09/M02/M03/M04/M06 și verificările `compile_plan` U06 în **același** modul tasks/runs: ID/schema/handler existent, dependency closure, DAG fără ciclu, exclusions și priorități stabile, hooks policy/capture/Stop obligatorii. Re-entry creează o instanță nouă cu cauzalitate către rezultat anterior, nu ciclu de așteptare între taskuri vechi. Max iterations/dedup/stagnare/limite produc LIMITED, nu loop infinit. Cache PURE leagă code/config/input digest/context și nu poate efectua I/O; I/O cere readmitere/buget, UNKNOWN cere reconciliere. Pipeline M07/M08/M09: decode → shape/context → normalize preserving raw → redact/project → persist evidence/event → notify; observer defect nu pierde eventul, guard defect nu permite efectul. Lifecycle instantiate/validate/prepare/claim/admit/execute/capture/persist/notify/close are cleanup testat, nu presupus din upstream.

**Research contextual:** fingerprint pasiv WebTech pe capturi → identificator/version parse valid → adaptoare OSV/vendor docs/search public → ResearchResult citat → lead/metodă candidată → aceeași frontieră Brain. Queryul conține produs/versiune publicabile, nu URL privat/client/PII/cookie/body/lexic privat. 429/backend fallback neaprobat/surse lipsă sunt blocaje, nu zero advisories. Rezultatul web/PoC este date neîncrezătoare; niciun cod recuperat nu se instalează/execută. Research Worker este copil nativ, intră în plafon și folosește tools Omnis cu egress propriu, nu web stock nelimitat.

**Wordlists:** reuse BBOT/CeWL/Kiterunner + subset Assetnote; generator pasiv determinist, fără spider/password lists. Păstrează raw/Unicode/short version tokens, provenance și caps înainte de admitere; CDN bytes au digest propriu, index SHA nu îi fixează. Input nou poate genera artifact nou sub recipe fixat. Fuzzerul este separat și fiecare request este Action autorizată; soft-404 se leagă de prefix/metodă/persona/epoch și se invalidează la drift. 401/403 nu se șterg generic. Ranking Jev este opțional și măsurat prin descoperiri utile/request, nu mărimea listei.

**Improvement:** lesson aprobat → draft → review → eval vulnerable/fixed/benign/regresii → Publish exact digest → numai runuri noi. Reporting nu așteaptă improvement. Slot de maintenance serializat după quiescență, home de produs fără arhive de caz sau granturi copiate, `WAITING_FOR_RUNTIME_SLOT` când ocupat; nu al doilea writer Hermes și nu auto-learning global. Native background review/curator/staging HM03–HM05 oferă intrări editoriale, nu publisher; la pin, write_approval poate fail-open la import failure, curator dry-run este doar prompt în calea de consolidare, iar snapshotul review-ului nu este implicit sanitizat. De aceea releases RO și publisherul Omnis rămân frontiera. Lessons cross-run trec data policy, fără truth held-out sau transcripte brute.

Cronul HM06 intră după ownership/draft/egress gates: `no_agent` enqueue cu wrapper trusted, apoi admission maintenance; nu cron LLM direct în home-ul activ și nu scheduler nou. Memoria/MCP/tool inventory se verifică (skip_memory nu este presupus); malformed wake nu este barieră fail-closed. Stop engagement oprește taskuri/research/dispatchuri model-target ale cazului; Stop maintenance oprește admiterea/jobs native și verifică quiescența, **pause schedule ≠ worker stopped**; Stop instance oprește ambele și păstrează datele. Maintenance nu moștenește aprobarea/bugetul cazului oprit. Restore începe stopped/locked, fără autoresume.

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
| InstanceControl | Identitatea instanței, admission_open, shutdown_command_id/generation, receipt de quiescență; barieră tranzacțională comună Start/Resume/Settings/admitere |
| Engagement / EngagementRevision / Run | Autorizație, scope, policy, data policy, bugete, mod/obiectiv/constraints și snapshot model/catalog; MissionSpec/FocusEnvelope derivate append-only conform §9.3; runul citează revizia imutabilă |
| Identity / AuthContext / BusinessRuleRevision | Secret refs, principal, epoch, lease și reguli ALLOW/DENY/UNKNOWN |
| Surface / Operation / Parameter / Observation / Relationship | URL brut separat de rută normalizată, metodă, tip, proveniență, observed/inferred, context identitate și evidence |
| Task / Attempt / RuntimeBinding / LaunchManifest | Rol, precondiții, ipoteză, skill digest, limite, lineage de încredere și fencing |
| Action / Approval / EffectRecord | Autoritate, argumente tipizate/redactate, revizii, dispatch, rezultat/UNKNOWN și cleanup |
| Evidence / Artifact | Proveniență executor, digest, size, stare, path intern generat, redactare și retenție |
| Candidate / Validation / Finding / Occurrence / RunFindingLink / Retest | Oracle, controale, severitate motivată, impact, remediere și probe; legătura unică run–finding–claim împiedică numărarea occurrences ca vulnerabilități distincte |
| ReportReview / ReportReviewDecision | FK engagement/run/finding/claim/evidence manifest/policy; required/status și review_revision; istoric append-only cu actor, command ID și cauzalitate. Migrarea aparține modulului findings, nu unui flag exclusiv UI. |
| DomainEvent / Inbox / Command / ReportSnapshot | cursor, revision, causation, idempotency, payload minim/redactat și snapshot reproductibil |

Relațiile sunt engagement-scoped, cu FK compuse/validare de ownership; fără joins între engagementuri pe baza unui ID ghicit. Normalizarea conservatoare păstrează exemplarele și contextul; nu unifică două obiecte cu politici diferite. Indexuri pe engagement/cursor, task/state, operation/identity și claim queue; paginare keyset, nu offset nelimitat.

### API Omnis v1 (contract propus, nu endpointuri deja existente)

- `/api/v1/engagements`, `/{id}`, `/{id}/revisions`: CRUD draft și validare; update cu `If-Match`/revision, 409 la conflict sau run activ.
- B09h introduce `GET/POST /api/v1/engagements/{id}/identities`, `GET/PUT /api/v1/identities/{id}` și `POST /api/v1/identities/{id}/verify`, deținute de identities/vault. Editarea identității în draft cere CAS/sesiune/CSRF și run oprit; secretul se persistă numai în seif, citirile expun handle/status/configured, niciodată valoarea. Verify login este acțiune funcțională autorizată, bugetată și atribuită, nu atac auth: 202 este receipt, iar readback verifică principal/rol/auth_epoch și evidence; invalid/expired/cross-engagement sunt refuzate. Reautentificarea unui run urmează ownerul/lease-ul și noul epoch din §8, nu un PUT care schimbă tacit identitatea. Formularul HTTP este disponibil cu B09h/G-AUTH-HTTP, assisted browser cu B09b/G03b; niciun endpoint nu este implementat prin acest document.
- Orice Start/Resume și admitere de lucru verifică și `InstanceControl` în tranzacția comună; `INSTANCE_SHUTTING_DOWN` refuză lucrul nou chiar dacă runul anterior este deja STOPPED. Citirile și Stop rămân disponibile.
- `/{id}/preflight`, `/{id}/runs`, `/runs/{run}/commands`: Start/Pause/Resume/Stop; comenzi cu idempotency key și readback; 202 înseamnă acceptată, nu finalizată. Serverul reface condițiile critice la Start, nu se bazează pe un rezultat UI stale.
- `/runs/{run}/events?after=cursor`: SSE cu `id`, replay din DB, heartbeat, last cursor; cursor expirat → `RESYNC_REQUIRED`, fetch snapshot și reabonare fără dublare. Snapshot include `through_cursor` consistent.
- `/runs/{run}/surfaces`, `/coverage`, `/tasks`, `/findings`, `/approvals`, `/evidence/{id}`: query bounded și scope validat. Autorizarea nu vine din filtrul clientului.
- `/settings/providers/{allowed_provider}/...`, `/settings/runtime`, `/settings/skills/...`: operații allowlisted, nu pass-through către Hermes.
- `/reports` și `/findings/{id}/retests`: snapshoturi imutabile și revalidare țintită cu buget/autorizație proaspete.

Errors: `{code, message, correlation_id, field_errors, retryable}`; fără traceback/secrete. Exemple: `SCOPE_DENIED`, `UNSUPPORTED_TRANSPORT`, `AUTH_BLOCKED`, `POLICY_CHANGED`, `EVIDENCE_UNAVAILABLE`, `RUNTIME_INCOMPATIBLE`, `NEEDS_RECONCILIATION`. Semantica retryable se referă la operația API, nu la reexpedierea automată pe țintă.

OpenAPI generat din Pydantic; tipuri TS generate în build. Tipurile generate nu sunt validator runtime și nu acordă drepturi; API validează tot. TanStack Query deține server state, URL deține filtre/selecția, React deține state local al formularului; fără Redux/Zustand inițial. Invalidări SSE pe entity revision și refetch, nu counter++ la orice event repetat.

### 9.1. Proiecții pentru cockpit, cursor și consistență

Contractul de citire este `ProjectionEnvelope`: `schema_version`, engagement/run explicite (sau context global), `scope_revision_id`, `through_cursor`, `as_of`, `data_state`, `data`, iar pentru colecții `next_page`/`has_more`/limita. `data_state` și disponibilitatea metricilor disting NOT_RUN/UNAVAILABLE/UNKNOWN de un zero măsurat. `scope_revision_id` este configurația imutabilă; `through_cursor` este versiunea datelor citite. Același scope poate avea coverage diferit după ștergerea evidence, la alt cursor; nu numim ambele același snapshot de date. În envelope-ul global `through_cursor=null`; cardurile poartă contextul/cursorul propriului run, iar `as_of` global nu poate fi folosit pentru SSE resume. Cursorul de pagină este legat și de filtre/sortarea keyset, nu poate fi mutat între queries.

Proiecția unei pagini — inclusiv counts de navigare și rezumat — se citește într-o tranzacție PostgreSQL read-only REPEATABLE READ, închisă înainte de orice I/O lent. Summary, Top findings, atenția și legenda unei pagini nu sunt cereri independente amestecate în frontend. Citiri separate poartă versiunea lor: clientul păstrează ultima proiecție completă ca stale până la înlocuirea coerentă, nu combină contoare de la cursori diferiți. Nu ținem tranzacții DB deschise între clickuri/pagini și nu construim un motor generic de time-travel în P0.

| Contract propus | Owner / semantica obligatorie |
|---|---|
| `GET /api/v1/dashboard` | `engagements` + proiecții `runs`: active run separat de engagementul selectat, atenție tipizată, sumar global și pagină de engagementuri. Globalul nu este suma paginii clientului. Pentru fiecare engagement alegem runul activ sau cel mai recent; nu însumăm runuri/retesturi istorice. Fără run → NOT_RUN, fără date demo. |
| `GET /api/v1/runs/{run}/summary` | `runs/projections.py`: status, RunProgress, bugete, counts, Top findings, operational approvals și report reviews. Confirmed/severity numără distinct finding ID din RunFindingLink, numai CONFIRMED; occurrences nu multiplică totalul. Remediation este o axă separată: totalul nu se numește „open vulnerabilities”. |
| `GET /api/v1/runs/{run}/events?after={cursor}` | Transportul Omnis citește DomainEvent, nu loguri Hermes. Envelope cu event ID, context, sequence, UTC, kind, actor/attempt, sumar redactat și referințe ownership-validated. Tipuri de UI: tool_called/result, decision, endpoint, validation, approval și control/progres. |
| Queries surfaces/coverage/findings/tasks | Răspuns bounded și context run/identity; pagina/filtrele și sumarul aferent declară aceeași versiune. Cursor de pagină din alt context sau versiune expirată → refetch, nu append de pagini incompatibile. |

Secvența durabilă rămâne **per engagement** în ordinea commiturilor (§6). Cursorul opac de transport leagă schema/contextul engagement/run și secvența; streamul unui run filtrează jurnalul engagementului și poate avea goluri legitime. Token invalid sau aparținând altui run/engagement → `CURSOR_CONTEXT_MISMATCH`, fără date; token prea vechi → `RESYNC_REQUIRED`. Snapshotul include `through_cursor` din aceeași citire; abonarea pornește strict după acesta, iar duplicate/out-of-order nu scad revizia sau dublează UI. ID-ul unui eveniment și cursorul nu sunt autorizație. SSE session expiry închide fluxul și cere reautentificare, nu dezactivează verificarea ownership.

Home revalidează sumarul la focus/mutări și prin polling bounded numai cât pagina este vizibilă; când există run activ, evenimentele lui pot invalida aceeași query. Nu inventăm un cursor global din mai mulți cursori per engagement. `as_of`/staleness sunt vizibile; Stop rămâne legat de ID/revizie chiar dacă între citiri s-a schimbat runul activ. Câmpuri agregate disponibile numai parțial sunt marcate astfel, nu completate cu zero.

Aceste DTO-uri se introduc incremental: B01b fixează envelope/error/revision; B03/B04 primul Dashboard real; B08 evenimente/stadiu/bugete; B10/B12 coverage; B13 findings/review/report. Existența contractului nu cere toate tabelele și endpointurile în P0.

### 9.2. Report review și snapshotul exportabil

`POST /api/v1/findings/{id}/report-review` este comanda propusă, deținută de `findings/report_review.py`: decision APPROVED/HELD, run/context, expected `claim_revision`, evidence manifest/version și `review_revision`, cu If-Match și command ID. Body-ul nu furnizează verdict, bytes sau o listă arbitrară de findinguri confirmate. `GET /api/v1/runs/{run}/findings` oferă starea curentă și auditul bounded; receiptul unei comenzi nu înlocuiește readbackul.

- Ownership, sesiune/CSRF, policy fixată, CONFIRMED și reviziile sunt verificate server-side. Accept cere evidence necesare disponibile, integre și legate de claim. **Hold este permis și când evidence sunt indisponibile**, fiind excludere, nu validare. Policy VALIDATOR_ONLY nu expune aceste mutări; required/status vin de la backend.
- `claim_revision`/manifestul descriu materialul verificat; `review_revision` descrie decizia operatorului. Accept/Hold nu incrementează claim_revision și nu își invalidează singure materialul. Material nou creează review PENDING când policy cere operator, altfel NOT_REQUIRED, și păstrează decizia veche istoric; CONFIRMED trebuie să aparțină claimului/manifestului citat, nu se moștenește de la o versiune veche necorespunzătoare; schimbarea disponibilității singură nu o rescrie.
- Use case-ul folosește UoW/CAS, FK de ownership și unicitate per legătură run/finding/claim/manifest/policy. Comanda identică repetată returnează același receipt, fără revizie/audit/event dublu; aceeași cheie cu alt payload → conflict. O comandă stale nu aplică decizia pe materialul nou. După verificarea bounded a bytes, commitul verifică reviziile/proveniența; retenția/invalidation concurentă nu poate lăsa o acceptare nouă pe un manifest schimbat.
- `POST /api/v1/runs/{run}/reports` creează din DB un snapshot coerent al setului eligibil la momentul generării, nu din lista trimisă de browser. `GET /api/v1/runs/{run}/reports` listează istoricul; `GET /api/v1/reports/{id}/artifacts/{format}` livrează HTML/JSON numai după ownership/integritate/AVAILABLE. Idempotency leagă aceeași cerere de același snapshot; raportul nu se regenerează din findings curente la download. Materializarea bounded este job durabil al supervisorului, nu BackgroundTask volatil în workerul API; admiterea lui verifică InstanceControl și nu pornește model/target. Shutdownul instanței îl drenează/reconciliază, separat de Stop assessment.
- Snapshotul îngheață IDs/revizii/material redactat, review/policy, scope, through_cursor/denominator, starea runului, excluderi/motive, disponibilitatea evidence și versiunea rendererului. JSON/HTML au DTO allowlist; fără material_snapshot intern sau alte copii ascunse ale bytes indisponibili. Exportul folosește protocolul STAGING→AVAILABLE din §10, caps și reconciliere; queued/202 nu este download ready. Failure și reîncercarea idempotentă nu mută snapshotul spre date mai noi.
- Raport parțial este permis când runul este neterminat/LIMITED sau există excluderi/limite, dar spune explicit ce lipsește. Nu numim un raport gol „aplicație sigură”. Un finding legat prin occurrence confirmată sau retest autorizat în RunFindingLink este numărat o singură dată; retestul citează claimul istoric și probele noi, fără duplicarea vulnerabilității. Disponibilitatea curentă nu șterge verdictul, dar exportul nou nu reproduce bytes declarați indisponibili. ReportReview nu este un grant de efecte, chiar dacă este realizat în timpul unui run.

### 9.3. Misiune: general sau focalizat

**HF01–HF03, adoptate:** concretizăm obiectivul existent; nu creăm chat DB sau două câmpuri de obiectiv. Contractele de mai jos sunt normative pentru B02/B04/B06/B10–B13, nu endpointuri implementate în P0.4.

Tipuri comune pentru §9.3–9.6: `Id` = UUID opac; `Revision` = integer ≥1; `Digest` = SHA-256 lowercase hex, 64 caractere; `Ref` = obiect strict `{kind: enum din registrul trusted, id: Id, revision: Revision, digest: Digest}`; `Cursor` = token opac verificat pe context; `Text` = string Unicode, fără coerciții. Toate câmpurile din tabele sunt obligatorii; numai `T?` acceptă null, iar `T[]` acceptă lista goală dacă nu se precizează minim. Niciun câmp suplimentar nu este ignorat; schema necunoscută se refuză. Metadata declarativă nu acordă autoritate. Ref-urile se rezolvă cu ownership, tip/revizie/digest și compatibilitate, nu doar prin existența ID-ului. Referințele la catalog sunt globale numai pentru releases publicate; excepția CandidateSnapshot pentru PACKAGE_EVAL este privată și limitată conform §9.8. Cele de caz sunt strict engagement/run-scoped. Tipurile se materializează în DTO/schema generată cu primul consumator, nu ca stuburi acum.

**Adresabilitate și digesturi fără ciclu:** `CanonicalJSON` înseamnă UTF-8 JSON cu chei sortate lexicografic, separatori compact `,`/`:`, ensure_ascii=false, fără BOM/newline, duplicate keys/NaN/Infinity interzise; numerele non-integer sunt decimal strings canonice (`0` sau fără zerouri inițiale/finale redundante). Array order este semnificativ; textul nu se normalizează. Regula de bytes este aceeași folosită pentru lista de fișiere §9.4. Pentru înregistrări persistate, backendul creează `RecordEnvelope={schema_version:1, kind:Key, id:Id, revision:Revision, payload:object strict, digest:Digest}`; `digest=SHA256(CanonicalJSON({schema_version,kind,id,revision,payload}))`. Digestul propriu este omis, nu înlocuit cu placeholder. Fiecare revizie este imuabilă; răspunsul modelului nu își atribuie record ID/revision. Tipurile care afișează id/revision/digest în tabele sunt forma aplatizată a acestui envelope (câmpurile nu se dublează în payload). PromptBundleRevision folosește exact această regulă pe payloadul cu toate base/role/package refs, composer/tokenizer și limite; nu hash-uiește propria valoare digest. TaskBriefV1 și TaskResultV1 primesc separat envelope-uri backend cu kind `task-brief` și `task-result`, ID-uri și revizii proprii. `brief_revision` din header este revizia brief-ului, **nu** cea a rezultatului; CriterionOutcome.task_result_ref se rezolvă la envelope-ul exact al rezultatului acceptat. Rezultat duplicat identic are același receipt; alt payload pentru aceeași cheie attempt/result cere conflict/reconciliere, nu overwrite.

Excepția explicită de conținut pentru Ref la catalog: package/technique/procedure/schema/overlay/file din același release poartă **digestul pachetului**, calculat din bytes sursă §9.4, nu hash-uri recursive ale indexului rezolvat. Backendul leagă `(kind,id,revision)` de package release și key/path unic; verifică și conținutul fișierului manifestat. Astfel Technique→Procedure→Technique nu creează hash autoreferențial. Referințele la alte releases sunt Ref externe deja fixate; dependency cycles între releases sunt refuzate. Alte Ref (mission, focus, snapshots, rezultate, evidence metadata) folosesc RecordEnvelope; pentru bytes artifact, digestul bytes este câmp separat în payload, verificat la citire. Aceste reguli nu cer un tabel nou per concept, ci adresabilitate/revizii la primul consumator.


| Câmp EngagementRevision / RunSnapshot | Tip / validare |
|---|---|
| `assessment_mode` | enum `FULL_ASSESSMENT`, `FOCUSED_TEST`; explicit, niciodată dedus din depth |
| `objective_text` | Text 1–8192 code points, maximum 32768 bytes UTF-8; focused respinge whitespace-only, fără trim/normalizare a originalului; full poate materializa explicit defaultul „Evaluează suprafața Web/API autorizată în limitele profilului selectat.” înainte de Save |
| `objective_constraints` | listă ≤64 de `{id: Id, kind: READ_ONLY/EXCLUDE_FEATURE/REQUIRE_CRITERION, text: Text ≤1024, operation_refs: Ref[]}`; numai restricții, referințe rezolvabile |
| `workflow_profile_ref`, `business_rules_ref` | Ref? în draft pentru ambele; workflow_profile_ref devine Ref obligatoriu la RunSnapshot/Start, business_rules_ref rămâne nullable când procedura nu cere reguli; profile/package/model/prompt/tool selections fixate la Start alături de scope/policy/data policy |

`PUT /api/v1/engagements/{id}` cu If-Match și command ID salvează draftul; `GET /api/v1/engagements/{id}` și `GET /api/v1/engagements/{id}/revisions` citesc exact textul/modul/revizia după reload/restart. Conflict 409 păstrează draftul local fără overwrite. B02 poate salva draft cu workflow_profile_ref=null înainte să existe catalogul; UI afișează CATALOG_UNAVAILABLE/NOT_SELECTED și Start blocat. B06/P4a-minim livrează primul profil/pachet publicat, apoi selectarea sa cere o revizie nouă explicită înainte de Start; nu seed fals sau referință inventată în P1. B02 adaugă câmpurile și migrarea în agregatul existent; dacă există drafturi vechi, backfill full + obiectiv default explicit cu proveniență, fără reinterpretarea runurilor istorice. Secretul aparține seifului/identităților, nu textarea; textul privat nu intră în URL, localStorage, log ori export public implicit. Proiecția spre model respectă data policy; marker detection nu este DLP universal.

**Save/Next/Back și preflight de sintaxă: zero LLM, zero target.** Review înainte de Start arată datele salvate, nu pretinde interpretare semantică AI. Probe online auth/provider rămân acțiuni explicite bugetate. Interpretarea Brainului are loc numai după Start/admission model, în PREPARE, înaintea investigațiilor/fuzz. Preview AI pre-Start nu este inclus în MVP: dacă este adăugat ulterior, cere comandă separată și acord/cost/data policy vizibile.

| Contract derivat | Câmpuri și tipuri |
|---|---|
| `MissionSpec` | `schema_version: 1`, `id: Id`, `revision: Revision`, `snapshot_ref: Ref`, `assessment_mode: enum de mai sus`, `summary: Text ≤4096`, `criteria: {id: Id, description: Text ≤1024, kind: SECURITY/FUNCTIONAL, oracle_ref: Ref?}[]` (1–64), `non_goals: Text[]`, `required_operation_refs: Ref[]`, `basis_refs: Ref[]`, `gaps: Text[]`, `done_when: {criterion_id: Id, required: bool}[]` |
| `FocusEnvelope` | `schema_version: 1`, `id: Id`, `revision: Revision`, `mission_ref: Ref`, `state: UNRESOLVED/BOUNDED/RESOLVED/BLOCKED`, `test_operation_refs: Ref[]`, `support_operation_refs: Ref[]`, `discovery_bootstrap: {seed_refs: Ref[], max_actions: integer 0..30, deadline_seconds: integer 0..300}`, `excluded_operation_refs: Ref[]`, `scope_ref: Ref`, `policy_ref: Ref`, `reason: Text ≤2048` |
| `CriterionOutcome` | `schema_version: 1`, `criterion_id: Id`, `mission_ref: Ref`, `task_result_ref: Ref`, `outcome: PASS/FAIL/BLOCKED/INCONCLUSIVE`, `evidence_refs: Ref[]`, `reason: Text ≤2048`; funcțional ≠ verdict de vulnerabilitate |

MissionSpec este propunere model-generated; compilerul verifică criteria IDs unice, `done_when` exact pe criteriile existente, operații reale și oracles instalate. Backendul construiește/validează FocusEnvelope; browserul/modelul nu poate publica această anvelopă ca grant. `BOUNDED` permite numai bootstrapul explicit și suportul admis; `UNRESOLVED/BLOCKED` nu permit hunting. Epuizarea bootstrapului fără delimitare cere clarificare/gap. Plafonul efectiv intersectează scope, efecte, bugete, identități, mission/focus și capabilitățile attemptului. Login/health de suport sunt declarate și contorizate: „nu testa autentificarea” nu interzice loginul funcțional și nu autorizează auth attacks.

RunSnapshot îngheață **cererea**; MissionSpec/FocusEnvelope sunt revizii derivate **append-only** legate de el, nu rescrieri ale snapshotului. Task/brief/result/action/coverage/report citează revizia consumată. Replan în aceeași misiune poate rezolva operații noi prin evidence, nu modifica material obiectivul. Schimbarea modului/obiectivului cere Stop și revizie/run nou; STEER clarifică/prioritizează numai în limitele existente. Conflict între prompt restrictiv și mod cere clarificare înainte de investigații largi. Focus semantic nu este regex și nu promitem sandbox perfect de limbaj natural: testele compară task/action traces cu misiunea.

| Comportament | General | Focalizat |
|---|---|---|
| Recon / ipoteze | Suprafața promisă de scope și profil, incremental | Numai criteriile și prerechizitele misiunii; fără scanare globală implicită |
| Clue nou | Poate deschide un fir admis | Numai dacă servește obiectivului; altfel `deferred-outside-objective`, fără pivot automat |
| Coverage | Universul cunoscut/promis al assessmentului | Universul fixat de regula de includere a misiunii, nu procent global al aplicației |
| Completion | Predicatul §6 | Același predicat pe obligațiile misiunii; COMPLETED nu înseamnă că toate criteriile au PASS |
| Raport / retest | Domeniu, lacune și probe | Titlu „Raport de test focalizat”, mod/rezumat autorizat, criterii/outcomes, prerechizite/excluderi; retest nou păstrează explicit misiunea |

`coverage/denominator.py` include mission/focus ref și `denominator_revision`. Suprafața din afara misiunii este **neinclusă/netestată**, nu not_applicable sau sigură. Unsupported/blocked/disabled/skipped în subsetul promis rămân obligații neacoperite și pot produce LIMITED; filtrele nu micșorează numitorul. Noi operații relevante pot materializa o revizie nouă în același univers. CriterionOutcome funcțional nu crește `tested_no_issue` sau numărul de findings; o constatare de securitate trece separat prin validator/oracle. Scopul nesuportat este explicat, nu convertit tacit într-un pentest complet. Snapshotul raportului și bytes HTML/JSON descărcați păstrează aceleași refs/limite ca proiecțiile.

### 9.4. Catalog: pachet, tehnică și procedură

**HF04.** `settings/skill_catalog` deține un singur catalog; Hermes păstrează încărcarea nativă. `skills/` este sursa metodologiei de produs, `.hermes/skills/` este numai dezvoltare. Layoutul de pachet este:

```text
skills/object-authorization/
  SKILL.md
  omnis.yaml
  references/methodology.md
  references/false-positives.md
  references/technologies/<overlay>.md
  templates/procedures/read-object.yaml
  templates/schemas/task-result.schema.json
  templates/requests/<reviewed-template>.json
  assets/wordlists/<reviewed-seed>.txt
```

`SKILL.md` are frontmatter nativ `name`, `description`, `version`, provenance; descriere scurtă și ID nativ corelat cu manifestul. Secțiuni stabile: când se folosește/nu se folosește; inputs/precondiții; ipoteză/invariant; metodă; baseline/probe/control; evidence/oracle; false positives/proof gaps; effects/limite/Stop/cleanup; output/handoff; surse/compatibilitate/evaluare. Overlay-urile sunt selectate numai pentru tehnologia/faptele relevante, nu încărcate integral. Testele upstream/adaptate, truth/canary și held-out sunt în workspace evaluator/dezvoltare **nemontat** investigatorului; nu în pachet. Helpers opționale nu rulează la import/editare; executabilul poate fi folosit numai prin adaptor trusted, niciodată shell din editor.

Tipuri suplimentare: `Key` = string `[a-z][a-z0-9_.-]{0,127}`, unic în namespace-ul registrului; `Version` = SemVer exact fără range/latest; `Path` = POSIX relativ UTF-8 ≤240 bytes, fără absolut, `..`, segment gol, backslash sau symlink; `SchemaRef` = Ref către JSON Schema 2020-12 local, fără remote/file refs; `Technology` = `{product: Key, version_scheme: SEMVER/PEP440/OPAQUE, versions: Text[], transports: Key[]}` (OPAQUE cere egalitate exactă, intervale numai prin parser trusted); `Precondition` = `{predicate_id: Key, input_refs: Ref[], expected: bool, on_missing: BLOCKED/INCONCLUSIVE}`; `Limits` = `{max_attempts: integer 1..10, max_actions: integer 1..300, deadline_seconds: integer 1..1200, max_output_bytes: integer 1..1048576, max_fanout: integer 1..2}`. Sunt plafoane cerute; runul poate numai să le restrângă. Listele nedeclarate altfel au maximum 128 elemente, Text nedeclarat altfel ≤4096 code points, fiecare DTO serializat ≤1 MiB; datele mari sunt artifacts, nu prompt inline.

| Contract | Câmpuri normative (regulile tip/null din §9.3) |
|---|---|
| `SkillPackageRevision` | `schema_version: 1`, `id: Id`, `package_key: Key`, `revision: Revision`, `version: Version`, `native_name: Key`, `skill_path: Path`, `manifest_path: Path`, `technique_refs: Ref[]`, `procedure_refs: Ref[]`, `support_files: Path[]`, `input_schema_ref: SchemaRef`, `output_schema_ref: SchemaRef`, `compatibility: Compatibility`, `provenance: Provenance[]`, `release_digest: Digest`, `publication: DRAFT/REVIEW/EVAL/PUBLISHED/RETIRED` |
| `TechniqueRevision` | `schema_version: 1`, `id: Id`, `revision: Revision`, `key: Key`, `package_ref: Ref`, `family: Key`, `cwe_ids: Text[]`, `standards: {name: Key, version: Text, item: Text}[]`, `objective: Text`, `hypothesis: Text`, `invariant: Text`, `method_ref: Path`, `applicability_predicate_ids: Key[]`, `technologies: Technology[]`, `limitations: Text[]`, `procedure_refs: Ref[]`; metoda generală, nu pașii unei variante |
| `ProcedureRevision` | `schema_version: 1`, `id: Id`, `revision: Revision`, `key: Key`, `technique_ref: Ref`, `objective: Text`, `applicability_predicate_ids: Key[]`, `technologies: Technology[]`, `input_schema_ref: SchemaRef`, `output_schema_ref: SchemaRef`, `preconditions: Precondition[]`, `identity_requirements: Key[]`, `business_rule_refs: Ref[]`, `requested_capabilities: Key[]`, `requested_effect_ceiling: enum §7`, `predicted_signal: Text`, `baseline: Step[]`, `probe: Step[]`, `control: Step[]`, `evidence_requirements: {kind: Key, minimum: integer 1..128, mandatory: bool}[]`, `oracle_ref: Ref?`, `slots: CaseSlot[]`, `false_positives: Text[]`, `invalidation_predicate_ids: Key[]`, `limits: Limits`, `stop_reason_ids: Key[]`, `cleanup: Step[]`, `cleanup_not_needed_reason: Text?`, `handoff_schema_ref: SchemaRef`, `outcomes: ProcedureStatus[]` |

`ProcedureStatus` = enum `SUCCEEDED/INCONCLUSIVE/BLOCKED/FAILED/CANCELLED/NEEDS_RECONCILIATION`, identic statusului TaskResultV1, **nu Key**. `Compatibility` = `{hermes_revision: Text exact Git SHA, brief_schema: 1, result_schema: 1, adapter_refs: Ref[], tool_refs: Ref[], predicate_refs: Ref[], oracle_refs: Ref[]}`. `Provenance` = `{repository: Text, revision: Text exact Git SHA, path: Path, source_digest: Digest, license_id: Text, notice_paths: Path[], modification_note: Text}`; first-party folosește repo/revizia proprie. `Step` = `{id: Key, action_definition_ref: Ref, tool_ref: Ref?, parameter_schema_ref: SchemaRef, parameters: object validat de acea schemă, input_bindings: {name: Key, source_ref: Ref, selector: Key?}[]}`. Selectorii sunt câmpuri schema-approved, nu expresii/Jinja/Python. `Step.input_bindings.source_ref` admite suplimentar `StepOutputRef={kind: STEP_OUTPUT, step_id: Key, output_name: Key}`. `Step` declară și `output_schema_ref: SchemaRef`; fiecare output_name este un câmp publicat al acelei scheme, cu tip/limită/sensibilitate. IDs de pas sunt unice în întreaga procedură (baseline/probe/control/cleanup), nu numai într-un grup. Ordinea este concatenarea acestor liste; STEP_OUTPUT poate referi numai un pas anterior din același BoundProcedure/attempt. Forward refs, ciclu, output/type necunoscut sau binding către alt attempt sunt refuzate la compilare. Rezolvarea din receiptul pasului reușit are loc imediat înaintea pasului consumator; output lipsă/invalid/expirat blochează acel pas și păstrează gaps/obligațiile cleanup, nu generează un placeholder. Un token volatil/secret este handle opac injectat de executor, nu text în prompt/log; rețeta de approval fixează câmpurile substituibile, fără interpolare/DSL. Se reverifică fencing/Stop înaintea consumului/dispatchului. Legarea între proceduri folosește un artifact/receipt deja persistat ori un task dependent nou, nu lookup global după numele pasului. Controls și step receipts din TaskResult se identifică prin `(bound_procedure_ref, step_id)`, astfel încât două proceduri cu pasul `control` să nu se amestece. `baseline/probe/control` cer fiecare minimum un pas la procedura executabilă; oracol obligatoriu și outcomes includ BLOCKED/INCONCLUSIVE. Cleanup gol cere motiv; limitele/cleanup și inputurile de identitate/business trebuie rezolvate înainte de execuție, nu completate ca adevăr de LLM. Un package template folosește sloturi tipizate pentru refs de caz; instanțierea în TaskBrief le rezolvă, fără a fixa un engagement în release global.

**Unicul manifest `omnis.yaml`:** obiect strict cu `schema_version`, `package_key`, `version`, `native_name`, `skill_path` (exact `SKILL.md`), `techniques` (TechniqueRevision template[]), `procedures` (Path[] în templates/procedures), `support_files`, `file_bindings: {entity_kind: Key, key: Key, path: Path}[]`, `input_schema_ref`, `output_schema_ref`, `compatibility`, `provenance`; tipurile sunt cele de mai sus. IDs/revision/template refs locale sunt declarate în manifest/fișierele sale; backendul rezervă identitățile/reviziile și rezolvă refs la înghețarea candidatului (§9.8); publicarea promovează exact acel rezultat. `publication`, `release_digest`, review/eval receipts și readiness sunt **metadata backend**, nu câmpuri autoautorizante YAML. Parent `package_ref` este rezolvat de backend după hash, nu un digest propriu scris în bytes care se hash-uiesc. Schema de template distinge referința locală de slotul de caz; regulile exacte de rezoluție sunt cele de mai jos.

**Template refs și slots — forme exacte, fără convenții ascunse:** în fișierele sursă, `TemplateRef` este union discriminat: `{kind: LOCAL, entity_kind: Key, key: Key}` pentru obiecte/fișiere din pachet sau `{kind: RELEASE, ref: Ref}` pentru release extern. Inputurile de caz folosesc `InputRef = Ref sau CaseSlotRef`, unde `CaseSlotRef={kind: CASE_SLOT_REF, name: Key}`. `CaseSlot={name: Key, expected_kind: Key, min_items: integer 0..128, max_items: integer 1..128}` se declară în `slots: CaseSlot[]` (maximum 128) al procedurii; min≤max și nume unic. Un InputRef scalar admite numai slot max_items=1; min=0 numai unde câmpul este nullable. Câmp listă admite slot bounded many; ordinea valorilor este păstrată. În template-urile sursă, partea Ref din InputRef folosește TemplateRef, nu ID-uri backend inventate.

`ProcedureTemplate` are câmpurile ProcedureRevision fără backend `id/revision`; Ref/SchemaRef de catalog sunt TemplateRef, iar inputurile de caz sunt CaseSlotRef sau TemplateRef. `TechniqueTemplate` are câmpurile TechniqueRevision fără backend `id/revision`, cu aceleași local/release refs și fără case slots. Manifestul folosește aceleași forme pentru refs. CaseSlotRef este permis **numai** în Precondition.input_refs, business_rule_refs și Step.input_bindings.source_ref; nu în technique/tool/oracle/schema refs, key, limits sau parametri liberi. Aceste trei poziții se citesc `InputRef` în tipurile din tabel pentru ProcedureRevision publicată; forma BoundProcedure cere toate Ref/CaseSlotRef statice rezolvate; StepOutputRef de mai jos rămâne legătură tipizată la outputul viitor al unui pas anterior, nu un case slot nerezolvat. Nicio valoare nu este interpolată ca text/cod. Valorile tipizate ale parametrilor sunt obținute numai prin input_bindings/schema adaptorului.

`file_bindings` declară explicit maparea `(entity_kind,key) → path` pentru orice fișier referit prin LOCAL; kind aparține enum-ului lowercase `schema/overlay/method/asset/prompt/template`. Exemplu inert: `{entity_kind: schema, key: task-result, path: templates/schemas/task-result.schema.json}`. Pathul trebuie să aparțină setului declarat prin skill_path/manifest implicit/procedures/support_files și digestului; aceeași pereche nu poate avea două paths, două bindings pentru același kind/path sunt refuzate. Technique/procedure LOCAL rezolvă `key` din definițiile parsate, package LOCAL rezolvă package_key; nu confundăm Key cu un path și nu ghicim stem-uri. Unknown kind/key sau un schema ref către overlay se refuză. Câmpul este parte din bytes omnis.yaml și din digest, nu un registru concurent.

La înghețarea CandidateSnapshot, resolverul alocă/păstrează IDs pe `(package_key, entity_kind, key)`, atribuie revision și rezolvă LOCAL/RELEASE; CASE_SLOT_REF rămâne explicit în **ProcedureRevision template publicat**, nu pretinde input de caz deja rezolvat. La assignment, `ProcedureBinding={procedure_ref:Ref, slot_values:{slot_name:Key, refs:Ref[]}[], bound_procedure_ref:Ref}` în TaskBrief rezolvă exact fiecare slot; scope/ownership/kind/revision/digest și cardinalitatea sunt verificate. Orice slot necunoscut/duplicat/lipsă/străin sau substituție în câmp fără slot este refuzată. Backendul materializează un `BoundProcedure` adresabil prin RecordEnvelope, cu `procedure_ref`, `slot_values`, `resolved_procedure` (fără case slots, cu StepOutputRef validat unde este necesar) și `mission_ref`; nu include propriul bound_procedure_ref în preimagine. Backendul creează întâi acest record, apoi îl leagă în ProcedureBinding din brief. Nu se rescrie releaseul global. Astfel „nerezolvat refuzat” înseamnă local/release refs la Publish și **orice case slot** la dispatch, nu interdicția template-urilor publicate.


Validare: YAML safe, fără duplicate keys/tags/aliases, depth ≤32, manifest ≤256 KiB; IDs unice, fișiere/referințe/schema/tehnică-părinte rezolvabile, paths confined fără symlink, no shadowing, fără handler/tool/oracle necunoscut în procedură executabilă. Known-but-uninstalled = dependency-unavailable; methodology-only poate fi publicat cu `oracle_ref=null`, dar **nu** selectat executabil. Toate fișierele pachetului trebuie declarate și incluse în digest; fișierele nedeclarate sunt refuzate. Digest release = SHA-256 al UTF-8 JSON compact al listei de `{path,sha256,size}` pentru fișierele regular complete, ordonată după bytes UTF-8 ai pathului, cheile ordonate lexicografic, separators `,`/`:`, ensure_ascii=false, fără newline/BOM. `sha256` se calculează pe bytes originali, `size` integer bytes; digestul derivat se stochează numai în backend, fără hash autoreferențial. Manifestul/procedurile originale și proveniența sunt păstrate; indexul rezolvat al backendului este derivat și leagă digestul releaseului.

**Draft → Review → Eval → Publish:** review și eval receipts aparțin backendului, leagă digestul material, author/reviewer IDs, corpus/protocol/model/tool versions și verdictul; editarea invalidează acceptările materiale. Autorul AI nu autoaprobă; traseul explicit al operatorului unic și al evaluatorului este în §9.8. Un `validated: true` inventat este respins. Publicarea methodology-only cere review/static eval; activarea executabilă cere fixtures vulnerable/fixed/benign și regresii ale procedurii. Knowledge-reviewed, dependency-ready, fixture-evaluated, benchmark-evaluated și permitted-for-run sunt axe calculate distincte. Publish/retire sunt CAS/idempotente cu audit/readback. RunSnapshot fixează releases și compatibilitatea: taskurile noi din run nu văd draftul/releaseul nou. Revocarea activă face Stop/fencing; rollback selectează un release vechi pentru runuri noi. Incompatibilitate de câmp/semantică cere schema major explicită și gate de migrare; nu interpretare parțială. Metoda/configurația evoluează fără schimbarea core-ului; protocol/oracle nou poate cere adaptor și teste.

### 9.5. PromptBundleRevision, TaskBriefV1 și TaskResultV1

**HF05.** Composerul deținut de `integrations/hermes` adaptează Strix `_resolve_skills`/`render_system_prompt` și metodologiile de rol, nu runtime-ul Strix. Compoziția este **base invariants + role instructions + TaskBriefV1 + skill/metodă + technology overlay necesar**. Nu moștenește automat tot istoricul Brainului sau toată biblioteca. Promptul și outputurile sunt date sub ModelProjection, nu tokenuri de autoritate.

`TaskHeader` = `{schema_version: 1, run_id: Id, task_id: Id, attempt_id: Id, snapshot_ref: Ref, mission_revision: Ref, focus_ref: Ref, through_cursor: Cursor, brief_revision: Revision, result_schema_ref: SchemaRef}`. Rol = `RECON/INVESTIGATOR/VALIDATOR/RESEARCH`; identitate prompt = `{persona_ref: Ref, auth_epoch: integer ≥0, label: Text ≤128}`, fără secret. Caps §9.4 se aplică; composerul are suplimentar context budget fixat în PromptBundle și refuză overflow al materialului mandatory, nu taie policy/precondiții în tăcere.

| Contract | Câmpuri normative |
|---|---|
| `PromptBundleRevision` | `schema_version: 1`, `id: Id`, `revision: Revision`, `digest: Digest`, `base_ref: Ref`, `role_refs: {role: enum de mai sus sau BRAIN, content_ref: Ref}[]`, `composer_revision: Text exact SHA`, `brief_schema: 1`, `result_schema: 1`, `package_refs: Ref[]`, `max_context_bytes: integer 1024..262144`, `max_context_tokens: integer 256..65536`, `tokenizer_revision: Text`, `provenance: Provenance[]` |
| `TaskBriefV1` | `header: TaskHeader` (include `schema_version`), `prompt_bundle_ref: Ref`, `assessment_mode: enum §9.3`, `objective_summary: Text`, `non_goals: Text[]`, `role: enum de mai sus`, `hypothesis: Text`, `operation_refs: Ref[]`, `priority_reason: Text`, `done_when: Key[]`, `return_when: Key[]`, `context: ContextItem[]`, `contradiction_refs: Ref[]`, `prior_attempt_refs: Ref[]`, `package_refs: Ref[]`, `technique_refs: Ref[]`, `procedure_refs: Ref[]`, `procedure_bindings: ProcedureBinding[]`, `criterion_bindings: CriterionBinding[]`, `overlay_refs: Ref[]`, `input_artifact_refs: Ref[]`, `identities: IdentityPrompt[]`, `allowed_capability_ids: Key[]`, `limits: Limits`, `deadline: UTC RFC3339`, `validation_reserve: {actions: integer ≥0, seconds: integer ≥0}`, `stop_conditions: Key[]`, `required_evidence: Key[]` |
| `TaskResultV1` | `header: TaskHeader` (include `schema_version`, exactele task/attempt/brief refs), `status: SUCCEEDED/INCONCLUSIVE/BLOCKED/FAILED/CANCELLED/NEEDS_RECONCILIATION`, `observation_refs: Ref[]`, `evidence_refs: Ref[]`, `candidate_claims: {claim: Text, basis_refs: Ref[], procedure_ref: Ref, bound_procedure_ref: Ref}[]`, `controls: {bound_procedure_ref: Ref, step_id: Key, outcome: PASS/FAIL/INVALID/NOT_RUN, evidence_refs: Ref[]}[]`, `contradiction_refs: Ref[]`, `gaps: Text[]`, `next_clues: {basis_refs: Ref[], summary: Text, suggested_family: Key?, disposition: IN_OBJECTIVE/DEFERRED_OUTSIDE_OBJECTIVE}[]`, `consumed_input_refs: Ref[]`, `criterion_results: CriterionResult[]`, `action_refs: Ref[]`, `effect_refs: Ref[]`, `cleanup_refs: Ref[]`, `usage: {state: KNOWN/UNKNOWN, model_calls: integer?, target_actions: integer?, cost: decimal-string?}` |

`ContextItem` = `{ref: Ref, epistemic_state: OBSERVED/INFERRED/CONTRADICTED, summary: Text, mandatory: bool}`; IdentityPrompt este tipul de mai sus. `done_when/return_when/stop_conditions/required_evidence` rezolvă predicate/cerințe din schema procedurii, nu cod. Procedura, overlay-ul, artifactul/wordlistul și orice input consumat citează revizia/digestul exact.

`CriterionBinding={criterion_id:Id, bound_procedure_ref:Ref, step_ids:Key[], outcome_rule_ref:Ref}` leagă assignmentul de criteriile MissionSpec, nu de numele unui predicat done_when. `CriterionResult={criterion_id:Id, bound_procedure_ref:Ref, control_step_ids:Key[], evidence_refs:Ref[], proposed_outcome:PASS/FAIL/BLOCKED/INCONCLUSIVE, gaps:Text[]}` leagă outputul de același assignment. Brief-ul are minimum un binding per criteriu alocat; rezultatul are exact perechile criterion_id/bound_procedure_ref alocate, fără criterii străine sau omise. Un task pregătitor/recon poate avea zero criterion bindings, dar atunci nu poate produce CriterionOutcome și justifică suportul în priority_reason/operation refs. Rule ref este handler/oracle trusted fixat în profil/procedură, nu un cod din prompt; backendul îl aplică pe receipts/evidence verificate și produce CriterionOutcome legat de task_result_ref. Propunerea copilului nu acordă PASS/FAIL automat. Două criterii cu aceeași procedură au bindings/outcomes distincte; lipsă oracle/controls → BLOCKED/INCONCLUSIVE. Pentru criterii SECURITY, verdictul de vulnerabilitate rămâne separat la validation; pentru FUNCTIONAL nu crește coverage de securitate.

`usage` necunoscut nu este zero; receipturile backendului, nu numerele copilului, dețin contabilizarea. `SUCCEEDED` nu înseamnă CONFIRMED; serviciul verifică existența/ownership/proveniența și oracolul separat. Un copil poate propune următorul task, dar nu îl admite.

RuntimeBinding/LaunchManifest din §5 rămân în afara JSON-ului model-facing; backendul leagă task/attempt/capabilități de copilul autentic **înainte de primul tool**. Orice role/revision/input străin sau stale blochează consumul. Adaptorul folosește numai suprafața verificată la pin; nu adaugă argumente native imaginare `tools/provider/skills per child`. Schimbarea rolului cere attempt nou. Validatorul primește claim/rețetă/precondiții și context independent, nu instrucțiunea de a confirma colegul. Clues noi vin prin tool results/handoff/steer; nu rescriem system prefix/tool schema în conversația activă și nu rupem prompt caching.

H03–H08 verifică compoziția golden, două goaluri identice corelate corect, missing/wrong digest/shadowing, ref cross-run, misiune stale, input lipsă, mandatory context trunchiat, prompt full moștenit într-un focused task, rezultat după Stop și no double wake. Golden composition certifică structura, nu eficacitatea: aceasta cere fixtures comportamentale și evaluarea separată din plan.

### 9.6. Unelte reale și invocări atribuite

**HF06.** Brainul selectează/cere capabilități pentru task; backendul acordă subsetul compatibil, evaluat și permis; copilul invocă adaptorul Omnis. Registrul ToolDefinition este cod/config trusted de release, separat de manifestul skillului care doar **cere** capabilități. Instalat pe disc ≠ compatibil cu schema/adaptorul ≠ evaluat pe fixture ≠ permis în acest run. Preflight citește receipturi distincte; niciun YAML/model nu se declară singur ready.

| Contract | Câmpuri normative, tipuri §9.3–9.5 |
|---|---|
| `ToolDefinition` | `schema_version: 1`, `id: Id`, `revision: Revision`, `key: Key`, `adapter_kind: LIBRARY/EXECUTABLE/SERVICE/HARDWARE`, `adapter_ref: Ref`, `artifact: LocalArtifact/ServiceArtifact`, `input_schema_ref: SchemaRef`, `output_schema_ref: SchemaRef`, `parser_ref: Ref`, `capability_ids: Key[]`, `transport_ids: Key[]`, `effect_classes: enum §7[]`, `dependency_refs: Ref[]`, `config_schema_ref: SchemaRef`, `template_refs: Ref[]`, `method_ids: Key[]`, `limits: ToolLimits`, `cancel_handler_id: Key`, `readback_handler_id: Key`, `egress_policy_ref: Ref`, `secret_injection_handler_id: Key?`, `capture_handler_id: Key`, `sanitation_handler_id: Key`, `compatibility_receipt_refs: Ref[]` |
| `ToolInvocation` | `schema_version: 1`, `id: Id`, `context: ExecutionContext`, `definition_ref: Ref`, `config_ref: Ref`, `template_refs: Ref[]`, `wordlist_refs: Ref[]`, `input_refs: Ref[]`, `parameters: object validat strict`, `identity_ref: Ref?`, `auth_epoch: integer ≥0`, `reservation_ref: Ref`, `fencing_epoch: integer ≥1`, `deadline: UTC RFC3339`, `action_refs: Ref[]`, `effect_receipt_refs: Ref[]` |
| `ToolResult` | `schema_version: 1`, `invocation_id: Id`, `definition_ref: Ref`, `parser_ref: Ref`, `status: SUCCEEDED/FAILED/BLOCKED/CANCELLED/UNKNOWN`, `exit_code: integer?`, `cancellation: NOT_REQUESTED/REQUESTED/CONFIRMED/UNKNOWN`, `execution: NOT_STARTED/STARTED/COMPLETED/UNKNOWN`, `effect_outcome: NONE/KNOWN/UNKNOWN`, `observation_refs: Ref[]`, `artifact_refs: Ref[]`, `evidence_refs: Ref[]`, `action_refs: Ref[]`, `truncation: {truncated: bool, captured_bytes: integer ≥0, total_bytes: integer?}`, `errors: {code: Key, message: Text, retryable: bool}[]` |



`LocalArtifact={kind: LOCAL, version: Version, digest: Digest, artifact_ref: Ref}` este obligatoriu pentru LIBRARY/EXECUTABLE (și firmware/controller local HARDWARE). `ServiceArtifact={kind: SERVICE, service_id: Key, version: Text?, attestation_receipt_ref: Ref, config_ref: Ref}` este obligatoriu pentru SERVICE: versiune exactă declarată dacă există, altfel null cu motiv în receipt, **fără digest/versiune de executabil inventate**. Receiptul atestă endpointul allowlisted, providerul, versiunea/revizia observabilă sau limita ei, config/TLS identity, timestamp și expiry; backendul verifică proaspăt compatibilitatea la admission. Dacă serviciul nu poate lega revizia/config de o atestare verificabilă, dependency-unavailable/BLOCKED. ToolDefinition însăși are RecordEnvelope/digest fixat; atestarea serviciului nu promite că bytes binarului remote sunt cunoscuți. Schimbarea materială/expirarea atestării blochează noi invocări și cere revalidare, nu hot-swap ascuns.

`ToolLimits` = `{timeout_seconds: integer 1..1200, stdout_bytes: integer 1..5242880, stderr_bytes: integer 1..1048576, memory_mib: integer 16..4096, cpu_millis: integer 1..1200000, pids: integer 1..128, disk_bytes: integer 0..1073741824, max_target_actions: integer 0..300}`. Limitele efective sunt minimul registry/config/task/run; consumul nested este contorizat, nu rezervat în paralel de două motoare. Capability requests se intersectează cu RuntimeBinding și rol; toolul model-facing primește numai definition ref, input refs și params tipizate. Reservation, fencing, identitate/secret handle și binding sunt atașate de backend, nu acceptate ca autoritate din JSON LLM. Captura brută privată, proiecția redactată pentru model și receiptul executării sunt distincte.

O invocare produce **zero sau mai multe Action target**: parser pur zero, scanner/crawler câte una per request/efect, inclusiv redirects/subrequesturi. ScannerActionWindow leagă invocation/attempt/identity/auth epoch/fencing/context generation/deadline; nu două ferestre pe același context. Policy/rezervarea/captura se aplică fiecărei Action la sink și leagă receiptul de invocare. La închidere generația este revocată; request întârziat nu este atribuit următorului task. Permit de invocare ≠ trafic nelimitat. Nu duplicăm authority/evidence în adaptor și nu înlocuim Action cu ToolInvocation.

Execuție cu argv/config tipizate, fără shell interpolation, environment allowlist, filesystem/network/resource limits, binar/config/template/wordlist cu digest verificat înainte de dispatch. Fără install/update/fetch templates în timpul taskului; secrets prin canal privat al adaptorului, nu argv/log/model. Un adaptor care nu poate demonstra request attribution, cancel/readback și egress fail-closed rămâne BLOCKED; nu primește fallback shell. Serviciile externe trebuie să declare versiunea sau receiptul verificabil; un endpoint mutable neverificabil nu pretinde același digest executabil.

Exit 0 nu confirmă finding. Zero matches cu `execution=COMPLETED` este semnal, nu negativ verificat fără procedură/control/oracle. Parser output este Observation/Candidate/evidence, nu verdict; crash/timeout/effect UNKNOWN impun reconciliere înainte de orice retry. Stop între admitere și dispatch refuză lucrul nou, stale child/lease după restart nu reutilizează resursa. Resursele investigatorului nu sunt împrumutate validatorului. Teste: installed/permitted separat, wrong binary/template digest, dependency lipsă, parametru necunoscut/injection, stdout oversized, zero matches versus tool failure, direct egress/redirect deny la sink și anulare verificată.

Portul comun admite biblioteci, executabile și servicii viitoare prin release de adaptor și teste, fără schimbarea schedulerului pentru fiecare tool. Dispozitive **hardware** ulterioare cer adaptor dedicat, resource lease, policy și fail-safe; nici USB/serial/RF, nici acces host implicit în MVP Web/API. Un registru extensibil nu este o permisiune generică pentru dispozitive.

### 9.7. Emitent și context înainte de primul copil

**F02 — fără copil fictiv și fără bypass al brokerului.** `ExecutionContext` este union discriminat strict construit de backend, nu ales din argumentele LLM. ToolInvocation din §9.6 păstrează contextul complet plus definition/config/inputs/identity/reservation/fencing/deadline; fiecare Action moștenește același owner/context și primește admitere/captură individuală. Variantele nu permit omiterea arbitrară a câmpurilor din RUN_TASK:

| Variantă | Câmpuri obligatorii / drept limitat |
|---|---|
| `RUN_TASK` | `kind: RUN_TASK`, `run_id: Id`, `snapshot_ref: Ref`, `task_id: Id`, `attempt_id: Id`, `mission_ref: Ref`, `focus_ref: Ref`, `runtime_binding_ref: Ref`; exact assignmentul copilului, context.mission_ref = TaskHeader.mission_revision. Numai capabilitățile admise și pașii procedurii |
| `BRAIN_TURN` | `kind: BRAIN_TURN`, `run_id: Id`, `snapshot_ref: Ref`, `turn_attempt_id: Id`, `runtime_binding_ref: Ref`, `mission_ref: Ref?`, `focus_ref: Ref?`; root binding către sesiunea Brain autentică, creat înaintea primului model/tool. Null numai în PREPARE până la publicarea planului derivat; permite context/propose-mission/prepare-task/consume-delta/request-finish, nu TARGET_IO sau research egress direct |
| `OPERATOR_CHECK` | `kind: OPERATOR_CHECK`, `engagement_revision_ref: Ref`, `check_attempt_id: Id`, `command_id: Id`, `check_plan_ref: Ref`, `cancel_epoch: integer ≥1`, `instance_generation: integer ≥1`; emitent determinist pentru verificare funcțională explicită, fără RunSnapshot/copil/MissionSpec inventat |

În câmpul comun ToolInvocation.fencing_epoch, RUN_TASK/BRAIN_TURN folosesc epochul runului, iar OPERATOR_CHECK folosește cancel_epoch; toate verifică suplimentar generația/admiterea InstanceControl și lease-ul ownerului. Un check încă RUNNING sau cu efect UNKNOWN blochează Start până la drain/reconciliere; un receipt SUCCEEDED se poate reutiliza numai în limitele de prospețime de mai jos.

B06 stabilește root binding și admiterea ModelDispatch pentru PREPARE; Brainul nu are voie să revendice identitatea unui copil sau OPERATOR_CHECK. Pluginul primește contextul trusted prin adaptor, în afara JSON-ului modelului. Scope și ownership la citiri se verifică după tipul emitentului: root vede numai runul său și proiecțiile permise, copilul numai assignmentul; niciunul nu poate citi alte engagementuri sau granturi.

**Preflight inert versus probe online:** Save/Next/Back și `POST /api/v1/engagements/{id}/preflight` verifică local sintaxa, closure/revizii/readiness și receipturi deja disponibile; zero apeluri model/target/provider. „Verify login”/„Check target health” sunt comenzi online **separate**, explicite, înainte de Start, după B07/B09h și permisiune/buget. Se creează din draft o revizie imuabilă a inputului verificat, fără a îngheța editarea viitoare a engagementului. Rețeta CheckPlan se compilează din operații funcționale trusted, nu dintr-un prompt.

`CheckPlan` este RecordEnvelope cu `purpose: LOGIN_VERIFY/HEALTH_CHECK`, `engagement_revision_ref: Ref`, `scope_ref: Ref`, `policy_ref: Ref`, `identity_ref: Ref?`, `recipe_ref: Ref`, `allowed_operation_refs: Ref[]`, `max_actions: integer 1..30`, `deadline: UTC`, `data_policy_ref: Ref`. Recipe/operations sunt instalate și verificate; nu scanner, payload de atac, discovery sau origin sugerat de țintă. Intersectăm permisiunea operatorului cu aceste limite la **fiecare request**, inclusiv redirect/login support. Efectele de sesiune sunt declarate, nu mascate read-only. Seiful injectează secretele numai adaptorului; modelul nu este pornit. OPERATOR_CHECK este refuzat cât un run este activ; refreshul dintr-un run aparține ownerului AuthContext și contextului taskului afectat (§8), nu unui canal pre-run care ocolește Stop.

`CheckReceipt` leagă check/command/contextul fixat, Action/evidence refs, principal/rol/auth_epoch verificate sau UNKNOWN, usage, `expires_at: UTC` și status `PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED/NEEDS_RECONCILIATION`. API: `POST /api/v1/identities/{id}/verify` și `POST /api/v1/engagements/{id}/health-check` întorc 202/check ID; `GET /api/v1/checks/{check}` oferă readback, `POST /api/v1/checks/{check}/commands` admite numai CANCEL cu expected revision/idempotency. Dublu click identic nu repetă loginul; alt payload cu aceeași cheie dă 409. Timeout/efect incert nu devin auth ready și nu produc retry automat.

Cancel check incrementează cancel_epoch și închide admiterea, apoi drenează/reconciliază; shutdownul instanței închide și aceste dispatchuri. Bariera InstanceControl, scope/effects/approval, bugetul, egressul și evidence store sunt cele comune B07; nu există transport HTTP direct din endpoint. No new dispatch după revocare se probează la sink. Verificarea nu începe un assessment și nu acordă capabilități de hunting unui run viitor.

La Start, backendul cere profil/model/catalog admise și revalidează receipturile cerute de profil: aceeași revizie materială, identitate/principal/epoch, operații/scope/policy și termen neexpirat. Receipt stale → preflight blocat/cerere de Verify explicit, nu sondare online ascunsă sau succes reciclat. Start fixează RunSnapshot numai cu inputurile revalidate, trece prin PREFLIGHT/READY și apoi RUNNING cu faza PREPARE; prima inferență are ModelDispatch admis. Eșec înainte de admiterea runului produce command refuzat, fără run activ fictiv; crash după admitere folosește reconcilierea normală. Numai după MissionSpec/FocusEnvelope validate se pot admite taskuri target; full nu sare peste această frontieră.

G03a/G-AUTH-HTTP verifică draft→Verify fără Brain, save inert, readback/restart, secret echo/cross-identity/stale scope refuzate, anulare și shutdown între admitere/send. H04/H08 verifică separat root versus child versus emitent sistem. Niciun endpoint/context de aici nu se introduce în P0; ownerii sunt runs/commands, identities/vault, policy și executori, odată cu primii consumatori.

### 9.8. Evaluarea candidatului și publicarea fără ciclu

**F01 / C01:** rezoluția și evaluarea preced Publish. `settings/skill_catalog` îngheață materialul reviewed într-un **CandidateSnapshot**, adresabil în namespace-ul privat de evaluare, nu în catalogul selectabil pentru assessment. Resolverul verifică schema/path/closure/compatibilitate și alocă identități/revizii înainte de eval; Publish promovează acel index/material, fără rezolvare nouă spre dependencies mobile. IDs/revisions rezervate unui candidat respins nu sunt refolosite pentru alt material. Excepția îngustă de adresare pentru refs nepublicate există numai sub admiterea de evaluare a acelui snapshot; modelul/browserul nu o obțin trimițând un digest.

`CandidateSnapshot` este RecordEnvelope cu `draft_ref: Ref`, `material_digest: Digest`, `resolved_index_digest: Digest`, `candidate_refs: Ref[]`, `dependency_closure_refs: Ref[]`, `profile_ref: Ref`, `compiler_revision: Text exact SHA`, `technical_review_ref: Ref`, `created_by: Id`. Materialul complet se păstrează read-only sub catalog/candidates, separat de workspace-ul editabil; nu montăm checkoutul/draftul mutabil. Ref-urile candidate folosesc identitățile/reviziile rezervate și digestul conținutului conform §9.3–9.4; access check cere snapshotul de evaluare care le conține. Profilele/prompturile/recipes pot fi înghețate în aceeași closure; externele trebuie rezolvate exact, fără cycles. Digestul propriului CandidateSnapshot nu intră în preimaginea componentelor sale. TechnicalReviewReceipt de dinaintea înghețării citează material/index digests, nu Ref-ul snapshotului care încă nu există; EvaluationReceipt ulterior citează snapshotul, fără referință inversă în preimagine.

`RunSnapshot.execution_purpose` este fixat de backend: `ASSESSMENT` pentru runurile normale și retest, `CONTRACT_PROBE` pentru proba inertă explicită, `PACKAGE_EVAL` pentru evaluarea autorizată a candidatului. Nu este selector care acordă permisiuni în UI/JSON. Pentru ASSESSMENT rămân obligatorii releases publicate și capabilități evaluate/permitted; PACKAGE_EVAL permite **numai** candidatul exact din `EvaluationAdmission`, fără promovare globală. Același supervisor, RuntimeBinding, ledger B06m/B07, broker, Stop și evidence se reutilizează; nu runtime sau transport paralel. Runurile de probă/eval sunt etichetate în Settings și excluse din findings/coverage/counts normale ale engagementurilor. Retestul de securitate rămâne ASSESSMENT nou cu legătura istorică explicită.

`EvaluationAdmission` leagă candidate snapshot, evaluator/protocol/corpus refs, profil informațional, permisiunea laboratorului, dependencies/model/data policy/bugete, owner/lease/fencing/deadline. Native solver nu vede truth/scorer/canary sau soluțiile held-out; evaluatorul păstrează fixture/reset separat. Execuția unui candidat nu permite handler necunoscut, draft code import, tool neinstalat, egress direct sau build proxy respins. STATIC/PURE nu au target/provider egress; prima eval cu model cere G-MODEL/G-DATA-EARLY și acord, prima eval cu target cere gate-urile transportului și permisiunea fixture. B11/B12 nu depind de editorul complet pentru a folosi acest traseu îngust.

`EvaluationReceipt` păstrează snapshotul și **același digest** de material/index/closure, evaluator/compiler/model/tool/protocol/corpus refs, tip `STATIC_PASS/PURE_PASS/FIXTURE_PASS/BENCHMARK_PASS` ori FAIL/BLOCKED, rezultatele/limitele, evidence refs și timpii. Sunt axe distincte: STATIC_PASS verifică structură/referințe; PURE_PASS verifică pași deterministi fără ținte/model; FIXTURE_PASS cere positive/fixed/benign și oracle relevant; BENCHMARK_PASS cere protocolul held-out. O inferență contract-probe H03/G02-live nu este fixture-evaluated pentru BOLA și nu califică security coverage.

**Ordine de bootstrap:** B06a îngheață și validează seed-ul de package/profile/schema pentru trei acțiuni PURE de recon/mapping pe input sintetic local; schema oracle aici verifică numai contractul, nu vulnerabilități. B06b publică exact seed-ul STATIC/PURE-qualified read-only, fără editor. Receipturile statice/PURE sunt documente mici în DB și fișierele catalogului hash-uite, nu evidence target AVAILABLE simulate; protocolul de blob capture B07 se introduce cu primul IO care îl cere. P4a îl selectează și citește readiness; P2-live probează nativ Brain/copil/prompt/binding fără target effects. B11/B12 îngheață separat candidatul BOLA cu oracol/transport real, rulează evaluarea lab-only și publică materialul calificat pentru primul assessment G05a/G06a. B14b/B14c adaugă UI-ul general și improvement peste aceeași mecanică, nu inventează atunci evaluatorul.

**Un singur operator, responsabilități distincte:** autorul AI/importerul poate propune numai draft; nu primește autoritate de Review/Publish și nu își evaluează singur truth-ul. Pentru editarea manuală, operatorul unic poate confirma explicit propriul material **după** review tehnic și eval produse de checkere/evaluator independente de autorul generator; auditul înregistrează `author_kind: OPERATOR/AI/IMPORT`, actorul confirmării, receipturile și digestul. Nu cerem un al doilea cont ascuns, dar nu transformăm clickul în dovadă tehnică. Confirmarea umană este înaintea Publish și după rezultatele necesare; editul ulterior invalidează ambele. Oracolul findingului/validatorul independent rămân neschimbate.

Publish verifică atomic expected draft/candidate/review/eval revisions, eligibilitatea și exactitatea materialului, apoi face releaseul selectabil pentru **runuri noi**. Nu modifică ASSESSMENT activ și nu poate alege „latest”. Static-only poate publica knowledge fără execuție; o procedură de securitate necalificată rămâne methodology-only. Eval eșuată/receipt din alt digest/autoapprove AI/held-out leakage sunt refuzate. Eval poate fi anulată prin aceeași comandă Stop a runului de evaluare; nu aprobă publicarea. G-REVISION/G04b probează draft D evaluabil numai în lab, assessment refuză D nepublicat, D→D2 invalidează receipts și Publish păstrează D byte-for-byte după restart.

## 10. Evidence, date și raport

**Protocol artefact:** (1) rezervare STAGING în DB; (2) scriere streaming bounded în fișier temporar exclusiv, fără nume ales de țintă; (3) flush/fsync, digest, rename atomic pe același filesystem, fsync director; (4) tranzacție DB care publică AVAILABLE plus eveniment; (5) reconciler pentru STAGING/orfani/lipsă. Cititorul verifică existența/integritatea înaintea operației probatorii. Hashul detectează modificarea, nu dovedește singur proveniența.

Stări: `STAGING`, `AVAILABLE`, `TRUNCATED`, `MISSING`, `CORRUPT`, `DELETED`; versiunea redactată este derivat cu legătură la raw. Oracle declară ce bytes sunt obligatorii; un fragment suficient poate susține o observație limitată, nu automat un verdict complet. Verdictul este refuzat dacă dovezile obligatorii sunt absente/incomplete.

Limite inițiale de fixture: request body recepționat 1 MiB; response pe wire 5 MiB; response decomprimat 5 MiB; evidence păstrat 5 MiB, ratio maxim decomprimare 20:1; artefact individual 20 MiB, 1 GiB/run. Guardul aplică bytes/time caps incremental înaintea bufferingului/decomprimării, și fără Content-Length/chunked; depășirea întrerupe consumul și închide upstreamul, nu doar trunchiază fișierul final. Pentru MVP răspunsul bounded este verificat înainte să fie predat browserului; streaming către Chromium este oprit. Trace-ul este oprit implicit și bounded când este cerut; upload OpenAPI/JS 5 MiB, depth/time limits și decodare incrementală. Memoria/CPU/PIDs/tmpfs au capuri de container, inclusiv la parser și Chromium; dumpul/trace-ul nu ocolește bugetul. Parametri ajustabili numai în revizie, niciodată nelimitat; depășirea se înregistrează, nu se ascunde. Rezervăm capacitatea înaintea unei acțiuni; disc plin oprește admiterea și păstrează starea efectului. G03a verifică bytes efectiv citiți, memorie bounded și închiderea conexiunii pe fixture chunked/decompression bomb, nu numai absența verdictului.

Inventar de date: DB, raw/derivate, seif, cookie/storageState, Hermes sessions/compaction/live logs/provider error dumps, screenshots, model payloads, exports și backups. Memorie globală/cloud memory/auto-learning/exporteri auxiliari dezactivate în runtime-ul de engagement. Inventarul include și queries/research artifacts/lessons/pending writes/cron outputs/curator reports/backups; numai material aprobat intră în maintenance §6.2. Providerul primește minimum necesar, conform data policy; redactarea headerelor nu garantează eliminarea PII din body/screenshot. Markeri sensibili sintetici verifică fiecare traseu în G-DATA.

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
| Katana/Nuclei/Schemathesis | Integrare prin adaptoare conform stack §10: recon, semnale, respectiv extensie E2 | Gate per transport/tool/template; sqlmap candidat E1, fără instalare/template-uri automate |

Pachet Brain: snapshot și cursor, vecinătate relevantă, observații/contradicții, frontieră neexplorată, precondiții lipsă, buget și truncation flag. Contextul se paginează; nu transmitem întreaga hartă la fiecare tur. Dedup task după ipoteză + suprafață + identitate/epoch + family revision; retest cere informație nouă sau motiv auditat.

Coverage key: operație × parametru relevant × identitate/epoch × familie aplicabilă × snapshot/procedură. `tested_no_issue` cere precondiții, test și control efectiv executate, evidence și versiune corecte; răspunsul LLM negativ nu crește numărătorul. `not_applicable` cere justificare, iar unknown/blocked rămân vizibile. Numitor gol = N/A. Descoperit/exercitat/testat/validat sunt indicatori diferiți. UI oferă trecere din fiecare celulă la test/dovadă.

**Materializarea numitorului:** `coverage/denominator.py` deține `denominator_revision`, legată de inventarul cunoscut, catalogul runului, aplicabilitate și contextul identității. Se creează celule pentru parametrii selectați de procedura versionată; procedurile fără parametru folosesc un sentinel explicit, nu câte o celulă pentru fiecare valoare. Operațiile inferred și aplicabilitatea necunoscută produc obligații pending/unknown, niciodată covered; lipsa parametrului/metodei necesare se păstrează ca obligație de discovery. Familia din subsetul promis dar indisponibilă rămâne unsupported. Numai N/A cu motiv/revizie este exclus; universul este suprafața cunoscută, nu toate endpointurile posibile ale aplicației.

Descoperiri noi, rezolvarea unui indiciu sau schimbarea aplicabilității produc o revizie nouă, fără a dubla surse echivalente. Refreshul aceleiași identități înlocuiește contextul curent cu epochul nou: celulele epochului vechi rămân istorice, nu se adună în numitorul curent și nu se transferă automat ca testate. Anonymous are context explicit fără pretenție de login verificat. Schimbarea principalului/tenantului nu este dedup cu identitatea veche.

`covered` curent cere test/control/proveniență complete și referințe evidence rezolvabile și actualmente verificabile pentru tuple-ul exact. Un rezultat istoric reușit rămâne stocat, dar evidence MISSING/DELETED/CORRUPT/TRUNCATED insuficiente îl scot din numărătorul curent; evenimentul disponibilității avansează cursorul proiecției, nu rescrie verdictul sau raportul vechi. Filtrele schimbă rândurile vizibile, nu numitorul runului; un subtotal filtrat are etichetă și numitor propriu. Orice lipsă/trunchiere a proiecției este explicită. Testele B10/B12 compară DB/UI/report la aceeași versiune de date și verifică denominator gol, noi indicii, epoch nou și proveniență greșită.

Evaluarea separă integrare, capabilitate cu ipoteză furnizată și E2E fără soluție furnizată. Evaluatorul deține adevărul de referință, canary-urile și resetarea; agentul nu vede seed DB, scorer sau source privilegiat. Profilul de informație este declarat: black-box URL sau grey-box cu identități/reguli/OpenAPI, nu revendicăm black-box când dăm reguli business.

Pragurile, corpusul vulnerable/fixed/benign held-out, repetările și baseline-ul sunt fixate în plan §15 înaintea rulărilor. Protocolul Omnis–Strix păstrează aceleași misiuni full/focused, informații inițiale, identități și bugete, separă cauze-rădăcină/occurrences/paths și măsoară FP/FN, replay, cost/latență/intervenții. Nu promitem superioritate sau paritate din bibliotecă/trei familii/E1. Rezultatele se publică per run, cu ratări atribuite discovery/planificare/investigație/validare și cost necunoscut explicit. Promovarea unei familii ca benchmark-validated este legată de exact skill/tool/model/corpus; nu este precizie universală.

## 12. Implementare și guvernanță

### 12.1. Arborele țintă și proprietatea fișierelor

**Organizarea este confirmată; API/control P0.1/P0.2 și bootstrapul web P0.3 există local, nu întregul arbore.** Alegem directoare **`api/` și `web/` la rădăcină**, în locul schiței anterioare `src/omnis` + `apps/web`. `api/` conține monolitul modular și supervisorul (același wheel/cod de domeniu, procese diferite); `cli/` va fi launcherul operatorului, nu un al doilea backend. Rootul păstrează documentele/uneltele existente. Fișierele de mai jos se creează numai în felia care le exercită; nu umplem P0 cu clase goale sau toate tabelele MVP.

```text
OmnisAI/
├── README.md / AGENTS.md / CONTRIBUTING.md / DESIGN.md / Makefile
├── .github/workflows/ci.yml             # gate comun, fără conturi/live LLM
├── api/
│   ├── pyproject.toml / uv.lock         # API + supervisor, nu Hermes/proxy
│   ├── alembic.ini                  # comoditate în checkout, nu artefactul instalat
│   ├── src/omnis/
│   │   ├── __init__.py
│   │   ├── api.py                      # app factory FastAPI, fără scheduler
│   │   ├── migrate.py                  # comandă dedicată: python -m omnis.migrate
│   │   ├── migrations/env.py / versions/ # aceeași migrare inclusă în wheel
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
│   │   │   ├── internal_api.py / internal_auth.py / local_control.py
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
│   │       ├── dashboard/ / engagements/ / setup/ / overview/ / stream/
│   │       ├── coverage/ / investigations/ / findings/ / reports/
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
│   ├── src/omnis_hermes/runtime_host.py / runtime_protocol.py
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

Numele separate prin `/` într-un rând cu fișiere înseamnă frați în directorul indicat, nu un singur path. `dist/`, builduri, caches și medii virtuale sunt generate/ignorate, nu surse versionate. Arborele este ținta incrementală; folderele viitoare nu sunt scaffold creat în P0.1.

**Amendament P0.1:** singura sursă a reviziilor Alembic este `api/src/omnis/migrations/`, pentru ca wheelul instalat să poată migra o DB goală din afara checkoutului prin `python -m omnis.migrate`. `api/alembic.ini` rămâne numai un alias de dezvoltare la același director, nu a doua copie a reviziilor. Mutarea corectează limitarea demonstrată de testul RED al wheelului; nu schimbă ordinea porților și nu autorizează un upgrade de date fără backup.

### 12.2. Modulul potrivit pentru fiecare comportament

Sub `api/src/omnis/modules/`:

| Modul | Deține | Fișiere speciale, numai când sunt necesare | Prima felie |
|---|---|---|---|
| `instance/` | Identitatea/admiterea instanței și intenția durabilă de shutdown | schema minimă la P0.1; `admission.py`, `shutdown.py` odată cu lifecycle | B01c/B01f |
| `engagements/` | Draft, revizie, scope declarat, autorizare și context business | `scope.py`, `business_rules.py` | B02 |
| `runs/` | Preflight, comenzi idempotente, run snapshot și tranziții | `preflight.py`, `commands.py`, `completion.py` | B04/B05/B07 |
| `tasks/` | Task/attempt, bindings, inbox/continuări și priorități | `binding.py`, `continuations.py` | B06 |
| `policy/` | Admitere/rezervări model la primul consumator; apoi efecte target, scope, approval și aceleași bugete | `admission.py`, `budgets.py` minimal; `effects.py` și extensia target ulterior | B06m, apoi B07 |
| `identities/` | Persona/auth context, refresh/lease, epoch, secret refs | `vault.py`, `refresh.py` | B09 |
| `surfaces/` | Operații/parametri/observații/relații, normalizare conservatoare | `normalization.py`, `imports.py` | B08/B10 |
| `coverage/` | Numitor, aplicabilitate, proceduri și dovada negativului | `denominator.py` | B10/B12 |
| `evidence/` | STAGING/finalizare, manifest, integritate, retenție | `store.py`, `projection.py`, `retention.py` | B07 |
| `validation/` | Reproducere independentă și gate deterministic, nu voturi | `oracles/object_access.py`, `reflected_xss.py`, `traversal_canary.py` | B12 |
| `findings/` | Verdict admis, RunFindingLink/occurrences, severitate, ReportReview/decizii și retest | `deduplication.py`, `report_review.py`, `retest.py` + migrarea legăturilor/reviziilor | B13a/B13b/B13d |
| `reports/` | Snapshot/export HTML/JSON inert, materializare și istoric | `render.py`, `templates/report.html` + migrare snapshot/artifact refs | B13c |
| `settings/` | Readiness provider, publicare catalog și data policy | `providers.py`, `skill_catalog.py` | B14/P4a |

**Șablon de modul, nu generator obligatoriu:** `domain.py` (stdlib, invariants), `service.py` (use cases), `ports.py` (Protocol pentru I/O), `models.py` (ORM), `repository.py` (SQL), `schemas.py` (DTO Pydantic), `routes.py` (HTTP). Nu creăm cele șapte fișiere dacă felia nu are cele șapte responsabilități. Testele au același nume de modul: `api/tests/unit/engagements/test_domain.py`, `api/tests/integration/engagements/test_repository.py`, `api/tests/contracts/test_engagements_api.py`.

**Navigare de produs:** Home/Dashboard · Engagement · Settings; în engagement **Overview · Brain stream · Findings · Coverage · Reports**. `dashboard/` deține selecția/rezumatul global, `overview/` stadiu/atenție/metrici, `stream/BrainStreamPage.tsx` pagina de evenimente, `coverage/CoveragePage.tsx` matricea și subvederea `EndpointInventory.tsx`/`OperationInspector.tsx`. `investigations/` și Setup rămân rute secundare; Settings este global. Route map-ul canonic este UI/UX §2; hashurile prototipului, inclusiv `#map`, nu sunt contracte URL ale aplicației.

**Exemplu web concret:** `web/src/features/findings/FindingsPage.tsx`, `FindingDetail.tsx`, `EvidenceBundle.tsx`, `ValidatorDecision.tsx`, `ReportReview.tsx`, `api.ts`, `queryKeys.ts`, `FindingsPage.module.css` și teste `*.test.tsx` lângă componente. Streamul consumă proiecții de evenimente, nu loguri interne Hermes. `shared/ui/RunControls/` deține componenta, CSS Module și testele Stop/Pause/Start reutilizate. Portăm compoziția/tokenurile și fonturile locale cu licența, nu HTML-ul, reducerul sau datele DEMO; fixture-urile de teste nu intră în bundle-ul/DB-ul produsului.

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

Astăzi `make check`/`make test` acoperă documente/unelte, API/control PostgreSQL și bootstrapul web. `make check-api`, `make test-api`, `make test-migrations`, `make check-api-wheel`, `make check-web`, `make lint-web`, `make typecheck-web`, `make test-web`, `make build-web`, `make test-contracts` și `make test-e2e` sunt implementate. E2E servește buildul real prin API și folosește numai coduri sintetice prin controlul privat. **Comenzi viitoare, nu deja funcționale:** `make dev`, `make build`, `make test-safety`, `make test-release`; se adaugă odată cu componentele lor. Un gate indisponibil raportează NOT-RUN/BLOCKED, nu exit 0. CI apelează aceleași comenzi locale; CI remote nu a fost executat. Launcherul instalat `omnis` rămâne P0.4, nu este înlocuit cu Vite sau Make.

Exemplu B02: test domain RED → modul `engagements` + migrare → repository pe PostgreSQL real → route/DTO/OpenAPI → tipuri generate + formular/query web → E2E create/reload/conflict → commit coerent. B07 adaugă policy/evidence cu aceleași frontiere, nu un director generic de „agenți” care ajunge să dețină DB și rețeaua. Corpul held-out/scorer rămâne într-un workspace evaluator separat, niciodată montat runtime-ului.

Migrațiile se execută o singură dată prin comandă dedicată înaintea startupului; schema incompatibilă blochează readiness. Backup înaintea migrațiilor distructive; rollback documentat sau restore, nu promisiune că orice migrație este reversibilă. CI fără secrete/scanări/LLM: format/typecheck/unit/contracts/build, DB reală de test, safety fixtures izolate. Live provider opt-in și buget explicit.

TDD pe felii verticale: test RED relevant → implementare minimă → GREEN → refactor. Commit mic per comportament/decizie, numai fișiere intenționate, mesaje cu motiv și verificări. Upgrade Hermes/dependințe prin branch dedicat, lock/digests, contract+safety suite, fără upgrade sub run activ. Nu încărcăm automat pluginuri/pachete din rețea la startup.

### Porți de decizie care rămân reale, nu ascunse

- **G-RUNTIME:** binding/lineage, credential ownership, wake și Stop native — dacă pică, P3 blocat până la extensie/patch minimal verificat.
- **G-DEPENDENCIES:** proxyul publicat cu dependențe afectate rămâne respins; B01e-build permite numai testarea unui build remediat în harness izolat autorizat. B01e-integrated în B07/B09 + G-NET închid admiterea de assessment; nu cerem proba integrată înainte să existe adaptorul care trebuie testat.
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
