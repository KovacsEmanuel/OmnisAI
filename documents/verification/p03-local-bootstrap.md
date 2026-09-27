# P0.3 — bootstrap web real, pairing și stare locală

**IMPLEMENTAT LOCAL / verificări țintite trecute; adjudecarea finală a review-urilor în curs.** Bază curată `040f26f`. Autorizația utilizatorului acoperă exclusiv bootstrapul web/pairing P0.3 din plan §4/§5/§16/§19 și arhitectură §4/§12. Nu este închiderea G00, P0.4, P1 sau certificarea execuției target. CI remote **NOT-RUN**, fără push.

## Contract și rezultat observabil

- `web/` are manifest și lock proprii, React/TypeScript/Vite exact din baseline; Router declarativ, Query pentru server state, HTML nativ, CSS Modules/tokenuri. Nu s-au schimbat pinuri sau instalări personale. Radix nu este încă necesar unui widget complex; nu s-a adăugat o alternativă de stack.
- Neautentificat → cod one-use prin formular → readback al sesiunii cookie → identitate/generație/lease/barieră reale → logout confirmat prin readback. API-ul, pairingul persistent, Host/Origin/CSRF și controlul privat existente sunt refolosite, nu rescrise.
- OpenAPI Omnis este generat în `contracts/omnis.openapi.json`, apoi în `web/src/shared/api/generated.ts`; check read-only și controale de drift în `make check`/CI. Clientul validează separat răspunsurile runtime, fără casts ca dovadă.
- Build static real, servit de API same-origin. `OMNIS_WEB_ROOT` este explicit; manifestul/hashurile/extensiile/dimensiunile și symlinkurile sunt verificate. CSP/no-store/no-referrer, fără fallback către checkout, `.env`, documente sau DEMO. Vite este numai dev, fără `.env` și fără Origin rewrite/CORS permisiv.
- `api_ready` depinde de DB/schemă; `dashboard_ready` cere și assets/control privat cu identitate/epoch/generație potrivite. Health HTTP 200 păstrează semantica API-ready, deci launcherul viitor trebuie să citească booleenii/motivele. `assessment_ready=false`; admission nu este deschis de UI. Statusul brut al supervisorului rămâne conservator pentru dashboard.

Perimetru efectiv: web, export contracte, integrarea minimă API/static/readiness, teste/Make/CI, documentație și skill-urile de dezvoltare relevante. Nicio migrare nouă în P0.3; schema rămâne `0004_pairing_receipts`. `AGENTS.md` protejat, prototipul acceptat și runtime-ul personal nu sunt modificate.

## Matrice cerință → dovadă

| Cerință | Probă executată / owner | Limită explicită |
|---|---|---|
| Pairing/sesiune/status/logout reale | `api/tests/test_web_e2e.py` + `web/tests/e2e/run.mjs`: PostgreSQL migrat, supervisor și Uvicorn reale, build Vite de producție; ID comparat cu controlul privat | Nu launcher instalat/OCI P0.4 |
| Cod invalid, expirat, consumat/replay | Browser real + expiry SQL pe baza UUID atestată; emiterea digestului numai prin `control.sock` | Coduri exclusiv sintetice; nicio emitere HTTP de test |
| Cookie/CSRF/Host/Origin | E2E valid/deny, reload/logout și suitele HTTP P0.2 păstrate; cookie HttpOnly/Strict/Path, fără Domain verificat API | HTTP loopback, nu TLS; același UID/root exclus |
| Loading/eroare/expiry/indisponibilități | Teste componente; E2E proces API oprit, supervisor oprit, lock PostgreSQL real, expiry de sesiune și browser offline | Lock DB și offline Chromium nu acoperă toate blackhole-urile OS |
| Fără succes optimist sau răspuns vechi drept autoritate | Readback pairing/logout, generație locală pentru toate continuările auth, polling suspendat în mutații, răspunsuri întârziate reproduse RED | Serverul rămâne autoritatea; nu s-a demonstrat bypass server-side în defectele UI |
| Readiness inertă și bounded | Assets lipsă/modificate/symlink refuzate, socket absent cu lease viu refuzat, lease neschimbat sub polling până la expiry; loader blocat cu deadline/un singur worker/anulare/exit proces | Workerul filesystem nu poate fi întrerupt, dar nu se multiplică și nu ține procesul în viață |
| Fără coduri/tokenuri în URL/log/storage | Observator browser + canal privat de markeri către părinte; verifică inclusiv input.value, HTML, stdout/stderr ale tuturor proceselor, local/session/IndexedDB/CacheStorage; controale negative pentru token brut | Nu DLP universal; numai markeri sintetici observați pe canalele declarate |
| Keyboard/focus/erori/contrast/responsive | E2E 320/390/1024/1280/1440, skip link, focus și aria-describedby, controale ≥44px, reduced motion, forced colors, CSS zoom 200% | Chromium; fără screen-reader, alte browsere sau zoom nativ certificat |
| Fidelitate vizuală | Capturi reale inspectate față de `df17a29`: capsulă, display, double-bezel, scara tipografică; numai pairing și stare P0 | Testele/comparația nu sunt o nouă aprobare vizuală a utilizatorului |

[Rezultate E2E și contrast](p03-browser.json) · [pairing desktop](p03-ui/pairing-desktop.png) · [pairing mobil](p03-ui/pairing-mobile.png) · [instanță reală](p03-ui/instance-desktop.png) · [offline/stale](p03-ui/offline.png). Capturile nu conțin coduri, cookies sau CSRF. Cele **7 scenarii** au verdictul final scris de părinte numai după cleanup și verificarea logurilor, cu zero requesturi externe/erori JS observate. Observerul browserului nu este sandbox OS.

## Comenzi și rezultate înregistrate

Mediu: API Python **3.13.15**, uv **0.12.19** explicit, Node **24.21.0**, npm **11.19.0**, PostgreSQL **18.6** digest-pinned. Browser: `@playwright/test==1.63.0`, Chromium **153.0.8010.12 / build 1243**, fallback Ubuntu 24.04 pe Kali. Instalarea browserului a fost explicită; nu s-a înlocuit Chromium-ul personal.

- `make check UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv` la `519519c`: **exit 0**; 141 API/control/tooling, 10 migrare/livrare, 20 Vitest, 7 E2E; 28 documentation, 11 development, 4 controale anti-slop, 5 tooling web. Ruff/mypy, contracte, build/wheel și audituri incluse.
- După întărirea harnessului `0139f03`/`b7cb7ee` și corecția de reaping `5082cc7`, aceeași comandă canonică directă: **exit 0**, **145 API/control/tooling + 10 migrare/livrare + 20 Vitest + 7 E2E**; 28 documentation, 11 development, 4 controale anti-slop și 6 tooling web. Controalele Python de cleanup/markeri sunt incluse în cele 145, nu adăugate încă o dată.
- `make check-web`, `make lint-web typecheck-web test-web build-web`, `make test-contracts` au fost exercitate direct în felii. Audit npm: zero vulnerabilități cunoscute raportate; audit uv: 37 pachete fără advisories/status advers cunoscut. Nu sunt garanții exhaustive de supply chain.
- Reproducere din worktree curat `abf5a19`, mediu API nou și două instalări `npm ci`: gate complet **exit 0**, 141+10, 15 Vitest și 6 E2E din acea revizie. Manifestul/hashurile buildului coincid cu checkoutul principal al aceleiași revizii. Corecțiile UI și harness ulterioare au probe separate de mai sus; nu rescriem această reproducere ca fiind pe HEAD final.

Comenzile de setup/operare sunt în [api/README.md](../../api/README.md) și [web/README.md](../../web/README.md). Verificările nu instalează automat dependențe și nu relaxează gate-urile Python. Testele componente cu fetch substituit sunt marcate și separate de backend-real E2E.

## Review și remedieri

1. Contracte: lipsa driftului TS din gate-ul canonic — RED make dry-run, `a9de7a1`; cale cu spații — reproducer filesystem real, `bac7cea`; exporter format/lint — `e6b5fbe`. Pinurile și contractele deterministe au fost verificate independent.
2. Backend: status IPC reînnoia lease-ul — expiry PostgreSQL schimbată RED, apoi `d11d99b`; asset I/O fără deadline — ASGI blocat RED, apoi `9934b3a` cu operație unică și exit bounded. **Adjudecare independentă: ambele RESOLVED**, fără blocant nou în perimetrul analizat; reviewerul a rulat 15 teste noDB și gate-urile statice, nu DB fără environment. Părintele a rulat regresiile DB.
3. UI: răspunsuri auth întârziate rescriau expiry/logout — ambele ordonări reproduse RED, apoi `7ff487f`; Query offline păstra false live/READY și inventa istoric la prima eroare — 3 RED, apoi `ecdd8a0`, inclusiv nou E2E offline. **Adjudecare independentă: ambele RESOLVED**, cu 5 probe ad-hoc trecute, fără modificări în repo; aceste probe nu înlocuiesc unit/E2E-urile părintelui.
4. Harness: aserțiunea API putea întrerupe cleanup-ul supervisorului; timeout-ul Node necesita ownership/teardown pentru descendenți — `0139f03`, controale cu procese reale și escaladare. Anti-leak putea omite valori brute/live input; nu s-a constatat scurgere efectivă — `b7cb7ee`, markeri pe canal separat și controale pozitive/negative. Adjudecarea finală este în curs.

O verificare inițială a linkului de licență a eșuat sub 44px; E2E a ghidat corecția, păstrată în `09ebfc2`. Unele verificări de format au eșuat și au fost corectate înaintea commiturilor verzi. Browser Use a expirat la captură; alternativa Playwright a produs screenshoturi reale, nu imagini sintetizate.

Gate-ul complet a surprins și starea Linux `X` (dead) în timpul reapingului, după ce testul accepta numai `Z`. Rularea cu 1 eșec/144 trecute a fost refuzată. `5082cc7` recunoaște doar absent/identitate schimbată/Z/X, nu procese running/sleeping/stopped, conform [proc_pid_stat(5)](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html). Zece repetări ale controalelor reale și apoi gate-ul integral au trecut.

## Eșecuri de mediu, rollback și porți

Prima rulare în worktree curat a moștenit Node 22/npm 9 și a fost refuzată de gate; **nu este PASS**. Mediul a fost restabilit explicit la pinurile scratch, lockurile reinstalate și gate-ul rerulat cu succes. Un cleanup a găsit variabilele efemere absente: nu s-au citit credentiale personale; identitatea exactă Compose/container/volum a fost reverificată și s-a oprit numai proiectul deținut. Skill-urile proiectului rețin procedurile, nu memoria globală.

Proiectele `omnis-p01-p03-*` sunt sintetice și dedicate, cu port loopback dinamic și volume atestate. Cleanup fără `down -v`; volumele rămân. Worktree-ul de reproducere a fost eliminat normal după status curat, fără reset/clean/force. P0.3 nu migrează date personale. Rollback: inspectarea dependențelor commiturilor → `git revert` → reconstruirea web/contractelor și rerularea gate-urilor; Git nu oprește servicii și nu restaurează DB.

**Rămân în afară:** launcherul `omnis`, manifestul/topologia/UID P0.4 și probele complete de instalare; G00 complet; P1 engagement, SSE, Hermes, provideri/OAuth, executori/proxy, LLM/ținte și evaluări. Nicio operație de produs către provider/țintă, niciun cont personal sau push. Acceptarea vizuală a prototipului nu este o certificare nouă a portării.
