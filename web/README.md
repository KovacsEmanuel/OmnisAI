# Web P0.3 — bootstrap local, nu P1

React/TypeScript/Vite consumă API-ul real pentru pairing, sesiune, logout și statusul instanței. Nu importă modelul/scripturile prototipului, nu creează engagementuri și nu pornește assessmenturi. Funcțiile viitoare sunt `UNAVAILABLE`/`NOT_RUN`, cu motiv. [SL02 `omnis start --no-open`](../cli/README.md) servește acest build din releaseul instalat; pairingul TTY și browser/open sunt SL03. Nu există endpoint public de emitere a codurilor.

**HF01–HF10 în specificație, nu în acest bootstrap:** selectorul general/focused, obiectivul Brain, Skills/Jev/Runtime și findingurile se livrează în felii P1+ din plan. Nu activăm butoane false sau date DEMO pentru amendamentul documentar. Fixture-ul DB este acum integrat/atestat pe UDS/no-network; E2E/backend au trecut în gate-ul local de pe `bd06bcd`, conform [registrului final DB](../documents/verification/p04-test-db-integration.md). Probele P0.3 de mai jos rămân istorice; CI remote și G00 nu sunt închise.

## Mediu și comenzi reproductibile

Din rootul repo-ului, cu **Node 24.21.0 / npm 11.19.0**, API **Python 3.13.15** și **uv 0.12.19**. Verifică executabilul uv separat; cel global poate avea altă versiune. Nu schimba uneltele personale pentru a rula proiectul. API-ul și uneltele development au propriile medii/lockuri.

```sh
node --version
npm --version
/cale/absoluta/uv-0.12.19 --version
npm --prefix web ci --include=dev --ignore-scripts --no-fund
npm --prefix tools/development/anti-slop ci --include=dev --ignore-scripts --no-fund
# Instalare explicită a browserului fixat de Playwright 1.63.0, nu la fiecare test:
web/node_modules/.bin/playwright install chromium

make generate-contracts       # API -> contracts/omnis.openapi.json -> generated.ts
npm --prefix web run generate:design
make lint-web typecheck-web test-web build-web
make test-contracts           # check read-only, inclusiv drift și toolchain
make check-web                # cele de mai sus + audit npm
```

`generate:*` sunt operații de dezvoltare explicite. Verificările/buildul nu instalează pachete și nu repară tacit driftul. Vitest fixează `NODE_ENV=test`; Vite build fixează `NODE_ENV=production`. `skipLibCheck=false`; pinurile sunt din registrul existent, fără `latest`, override-uri sau dependențe runtime oportuniste. Radix rămâne alegerea pentru widgeturi complexe viitoare; bootstrapul folosește HTML nativ.

## Buildul final este servit de API, nu de Vite

După migrarea explicită și pornirea supervisorului conform [api/README.md](../api/README.md), API-ul primește căi absolute. `OMNIS_CONTROL_DIR` este același director privat verificat al supervisorului; `OMNIS_DATABASE_URL` este deja furnizat prin environment, nu în argv, URL sau fișierele web.

```sh
OMNIS_WEB_ROOT="$(pwd)/web/dist" \
OMNIS_CONTROL_DIR="/cale/privata/existenta" \
OMNIS_HTTP_PORT=8765 \
api/.venv/bin/python -I -m uvicorn omnis.api:create_app --factory \
  --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

Deschide `http://127.0.0.1:8765/`, fără cod în query/fragment. `/` și fișierele allowlisted din manifestul `web/dist/omnis-web.json` sunt singura suprafață statică. Hashurile, dimensiunile și lipsa symlinkurilor sunt verificate la citire; manifestul este input trusted de release, nu semnătură împotriva operatorului malițios. Lipsa/modificarea unui asset dă `WEB_UNAVAILABLE`, fără fallback la checkout sau DEMO. Assets din `documents/`, `.env`, tipurile generate, testele și source maps nu sunt servite.

`GET /health/ready` păstrează semantica HTTP a API-ului: **200 înseamnă DB/schemă/API disponibile**, nu automat dashboard ready. Consumatorul verifică explicit `dashboard_ready` și `dashboard_reason`. Dashboardul cere și build verificat + status privat autentificat, cu aceeași identitate/generație/epoch. Citirea nu reînnoiește lease-ul. `assessment_ready=false`, independent de health. Un shutdown nereconciliat nu este redeschis de UI. Rootul web poate afișa indisponibilitatea DB/control fără a pretinde că assessmentul există.

Așteptarea asseturilor are deadline de 1 secundă, separat de probele DB/control. Cererile concurente/anulate partajează cel mult o operație filesystem în zbor per aplicație. Operația OS nu poate fi întreruptă de Python; workerul daemon nu ține procesul în viață și nu se creează o coadă de retryuri.

## Sesiune și date

- Codul one-use se transmite numai în body-ul `POST /api/pairing`; câmpul se golește la submit. UI verifică apoi cookieul prin `GET /api/session` înainte să afișeze instanța.
- Cookie opac `HttpOnly; SameSite=Strict; Path=/`, fără `Domain`; limita este HTTP loopback, nu TLS. CSRF legat de sesiune, numai în `X-CSRF-Token` pentru logout.
- Logout cere ACK și readback fără sesiune. Eroare/timeout nu devin succes; retryul mutației nu este automat.
- Un singur writer de autentificare serializează pairing/logout, suspendă pollingul lor concurent și fence-uiește toate continuările cu o generație locală. Expiry anulează citirile vechi; un răspuns întârziat nu poate rescrie un logout confirmat.
- Codurile/CSRF/sesiunea nu intră în URL, loguri, localStorage, sessionStorage, IndexedDB sau CacheStorage. Query păstrează server state numai în memorie; nu există persister, service worker ori devtools în build.
- Loading, eroare, expiry, răspuns invalid și status stale sunt explicite. Proiecția veche, dacă este păstrată la eroare/pauză sau după 15 secunde fără confirmare, este etichetată stale; sesiunea este unverified după 30 secunde. Prima cerere eșuată nu inventează un răspuns istoric. Query folosește explicit `networkMode: always`: Internet offline nu înseamnă localhost indisponibil și nu trebuie să suspende verificările. Datele de test sunt în `tests/`, nu în entrypoint.
- Pollingul statusului este o citire locală, nu SSE. Nu există provideri/OAuth, apeluri LLM sau trafic target.

## E2E cu backend real

Pregătește **numai DB-ul disposable atestat** conform [api/README.md](../api/README.md), apoi:

```sh
make test-e2e
make check UV=/cale/absoluta/uv-0.12.19
```

E2E folosește lockul/binarul Chromium asociat cu `@playwright/test==1.63.0`, nu browserul personal. Pytest creează o bază UUID pe clusterul test verificat, procese API/supervisor proprii și un listener loopback rezervat. Driverul emite coduri sintetice prin `control.sock`; helperul de expiry/lock este exclusiv de test și refuză DB-uri fără numele/ownershipul fixture-ului. Nu există endpoint de debug în produs.

Probe: pairing invalid/valid/expirat/replay, cookie/CSRF/Host/Origin, reload/sesiune/logout, expiry după pairing, supervisor/API oprite real, PostgreSQL blocat real, tastatură/focus/formular, viewporturi 320/390/1024/1280/1440, contrast/reduced motion/forced colors și CSS zoom 200%. Capturile și rapoartele fără secrete sunt în `$TMPDIR/omnis-p03-e2e/<caz>/`. Screen-readerul, alte browsere, zoomul nativ și topologia containerizată de produs nu sunt certificate de această probă. Interceptorul browserului nu este sandbox OS.

## Dezvoltare cu Vite — separat de artifact

`npm --prefix web run dev` ascultă numai `127.0.0.1:5173`, cu port strict, Host/Origin exacte, fără CORS permisiv și fără citire `.env`. Proxyul păstrează Host/Origin, nu rescrie un origin străin într-unul acceptat. Pentru această configurație **exclusiv dev**, pornește API-ul pe TCP 8765 cu `OMNIS_HTTP_PORT=5173`; accesul direct la API pe Host 8765 este atunci refuzat intenționat. Revino la `OMNIS_HTTP_PORT=8765` pentru buildul same-origin. Vite nu este serverul final al produsului.

## Proveniență vizuală

Portare limitată din `df17a29`: capsula globală, antetul display, panourile double-bezel, scara tipografică, tokenurile și fonturile locale. DESIGN.md → `documents/Omnis_Design.tokens.json` → `src/shared/styles/tokens.css`; drift verificat. Fonturile originale Geist/Geist Mono sunt verificate după hashurile din `documents/assets/fonts-provenance.json`; acea proveniență este păstrată alături de copia generată. Licența OFL este livrată ca asset text (se normalizează numai whitespace-ul terminal, după verificarea originalului). Nicio cerere CDN la afișare. Prototipul nu este copiat ca aplicație și aprobarea sa vizuală nu este o nouă aprobare automată a portării.
