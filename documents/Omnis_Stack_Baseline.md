# Omnis — stack și versiuni, baseline v1

**Verificat la 25 septembrie 2026 · Linux x86_64 · Decizii pentru implementare, nu produs instalat**

## 1. Verdict

**Frontendul și nucleul API au o combinație exactă rezolvată și exercitată în probe izolate. Proxyul publicat este respins pentru trafic target din cauza dependențelor cu advisories.** Hermes, browserul întărit, DB/migrațiile și întreaga aplicație nu au fost validate live în această livrare.

Registrul machine-readable este [Omnis_Stack_Baseline.versions.json](Omnis_Stack_Baseline.versions.json): versiuni, engines/peers, integrități npm, metadate PyPI, advisories și digests de imagini. [Outputul verificărilor](verification/stack-probe.json) și [inputurile reproductibile](verification/README.md) separă testele efectiv executate de porțile viitoare. Pinurile directe din tabel provin din aceste metadate și din rezolvările executate, nu din presupunerea „latest funcționează împreună”.

## 2. Runtime și infrastructură

| Componentă | Alegere exactă | Motiv / stare |
|---|---|---|
| Node.js | **24.21.0 LTS** | Descărcat în scratch de la nodejs.org, checksum verificat; executat `--version`; nu schimbă Node-ul hostului.[14] |
| npm | **11.19.0** | Versiunea inclusă în distribuția Node aleasă; executată în probe. Nu npm latest 12 implicit.[14] |
| CPython API | **3.13.15**, build normal cu GIL | Instalare scratch separată, importuri și teste efective; 3.13 rămâne baseline comun compatibil cu pinul Hermes, nu 3.14 forțat |
| uv | **0.12.19** | Wheel oficial verificat prin digest; folosit pentru venv/rezolvare/install cu hashes |
| PostgreSQL | **18.6**, `postgres:18.6-bookworm` | Metadate/digest verificate, serverul nu a fost pornit; ramură suportată conform politicii publice.[16] |
| Hermes | **0.21.5**, `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` | Pin auditat, `requires-python >=3.11,<3.14`; mediu separat, nu upgrade al instalării personale |
| Docker/Compose pe host | **27.5.1+dfsg4 / 2.32.4-3**, observate | Client/server și Compose răspund; aceasta nu certifică deploymentul sau hardeningul |

Python 3.13 se apropie de trecerea la suport numai de securitate; release-ul 3.13.16 din calendar nu este tratat ca disponibil înaintea publicării. Reevaluăm patchul Python înaintea releaseului, nu îl înghețăm pentru totdeauna.[15] Un pin auditat astăzi nu justifică amânarea unui security update.

**Docker/Compose:** folosim interfața Compose v2 și un manifest testat pe hostul Linux de referință, fără `network_mode: host`, socket Docker în runtime sau containere privilegiate. Distribuția hostului, kernelul/seccomp/nftables și versiunile efective intră în manifestul P0/G-NET. Nu inventăm un număr „minim sigur” universal de Engine. Un host diferit trebuie să treacă aceeași suită înainte de target effects.

## 3. Frontend

| Rol | Pachete și pinuri |
|---|---|
| UI | `react==19.3.0`, `react-dom==19.3.0` |
| Limbaj și build | `typescript==5.9.3`, `vite==8.3.1`, `@vitejs/plugin-react==6.1.1` |
| Navigare | `react-router==8.4.0`, declarative mode, fără framework/SSR |
| Server state | `@tanstack/react-query==5.103.2` |
| Primitive accesibile | `radix-ui==1.6.7`; CSS Modules + variabilele DESIGN.md |
| Tipuri | `@types/react==19.3.0`, `@types/react-dom==19.3.0`, `@types/node==24.13.6` |
| Contract API | `openapi-typescript==7.13.0`, numai schema Omnis locală |
| Test runner | **`vitest==4.1.11`**, `jsdom==30.1.1` |
| Testing Library | `@testing-library/react==16.3.3`, `@testing-library/dom==10.4.2`, `@testing-library/jest-dom==7.0.1`, `@testing-library/user-event==14.6.7` |
| Browser E2E | `@playwright/test==1.63.0`; buildul browserului se fixează împreună |

În acest tabel, `==` înseamnă pin exact descriptiv; în `package.json` se scrie valoarea simplă `"19.3.0"`, fără `^` sau `~`.

### Două alegeri care diferă de latest

- TypeScript latest observat în cercetare era 7.0.2, dar `openapi-typescript@7.13.0` declară peer TypeScript `^5.x`. Alegem 5.9.3; nu `--force`/`--legacy-peer-deps`.[17]
- Vitest 5.0.1 + jest-dom 7.0.1 **a eșuat efectiv** la `tsc --noEmit` cu TS2428 pentru declarațiile `Assertion`. Vitest 4.1.11 a trecut același typecheck și testul DOM/Radix/router. Nu am ascuns conflictul prin `skipLibCheck: true`. Eșecul și corecția sunt în registrul probelor.

Dev install explicit `npm ci --include=dev`; teste cu `NODE_ENV=test`, build cu profil de producție explicit. Mediul gazdă al probelor moștenea production și a făcut `React.act` indisponibil; nu era un bug al aplicației. P0 trebuie să neutralizeze acest tip de moștenire în scripturile documentate.

**Nu adăugăm:** Tailwind/shadcn obligatoriu, Redux/Zustand, Monaco, canvas graph, bibliotecă mare de charts, Storybook înaintea nevoii sau fonturi remote. Componentele de bază au test/demonstrație locală și tokenuri. Radix ajută mecanica interactivă, nu certifică automat accesibilitatea paginii.

## 4. API, persistență și teste Python

| Rol | Pin |
|---|---|
| API/DTO | `fastapi==0.141.1`, `pydantic==2.13.5` |
| ASGI | `uvicorn==0.54.0`; primul deployment un singur proces API, supervisor separat |
| ORM/migrații | `SQLAlchemy==2.0.54`, `alembic==1.20.0` |
| Driver async | `psycopg[binary]==3.3.6`, `greenlet==3.5.6`; DSN SQLAlchemy `postgresql+psycopg://` |
| HTTP adapter/API testing | `httpx==0.28.1` |
| Seif target AEAD | `cryptography==50.0.1` |
| Teste | `pytest==9.1.1`, `pytest-asyncio==1.4.0` |

**Decizie explicită:** SQLAlchemy async, sesiune per unitate de lucru, fără sesiune globală sau I/O sincron în event loop. Proba a construit dialectul async psycopg; nu s-a conectat la DB. Nu adăugăm `asyncpg`, `psycopg_pool` sau două ORM-uri. SQLAlchemy 2.0 este ramura de mentenanță; 2.1.0 tocmai publicat nu este adoptat automat pentru primul increment.[21]

Rezolvarea API cu hashes a produs un mediu compatibil, inclusiv Starlette **1.7.0** și pydantic-core **2.46.5**; întregul set este păstrat în inputurile probei. Manifestul aplicației va avea propriul `uv.lock` și security review; nu copiem mediul Hermes peste API.

Testul FastAPI folosește HTTPX `AsyncClient + ASGITransport`. Calea `TestClient` a avertizat despre deprecarea HTTPX în Starlette curent; am ales un test ASGI explicit, fără a adăuga un al doilea client numai pentru acel smoke. Pentru startup/shutdown real și pool DB avem teste de lifecycle separate în P0/P3.

AES-256-GCM cu nonce unic per criptare și AAD legat de engagement/identitate/tip de secret; cheie în afara DB/repo/backup. Nonce-ul fix din proba disposable este folosit o singură dată cu cheie proaspătă și text sintetic; nu este modelul de implementare a seifului. Cheia lipsă produce LOCKED. Threat modelul nu protejează de root/același UID compromis.

## 5. Recon, browser și parsere

| Componentă | Pin / moment |
|---|---|
| Playwright Python | **1.63.0**, mediu executor separat; P3b |
| Chromium | Buildul livrat pentru Playwright 1.63.0, plus digest al imaginii; nu Chrome personal sau `latest` |
| JSON | stdlib Python, cu byte/depth/time limits |
| XML robots/sitemap | `defusedxml==0.7.1`; DTD/entities interzise, limită de resurse |
| YAML | `PyYAML==6.0.3`, safe loader + alias/depth/input budgets |
| OpenAPI validation | `openapi-spec-validator==0.9.0`; subset MVP 3.0/3.1, import local, `$ref` externe/file interzise |

Pinii parserelor sunt verificați ca publicare/metadate, nu printr-un test complet de recon. `defusedxml` are metadate vechi; Requires-Python permisiv nu certifică Python 3.13. Implicit nu facem fetch de `$ref` sau validare de țintă la upload. OpenAPI 2.0/3.2 se marchează unsupported până la probe proprii, chiar dacă biblioteca poate suporta mai mult.

Driver, browser și imagine Playwright se actualizează împreună; documentația avertizează asupra mismatchului dintre versiunea bibliotecii și imagine.[5] Imaginile `mcr.microsoft.com/playwright/python:v1.63.0-noble` și JS echivalent au digesturi verificate, dar **nu sunt executorul hardened livrat**. Interpreterul din imagine poate fi diferit de Python 3.13.15; P3b fie îl înregistrează și testează separat, fie construiește imagine proprie pornind de la Python ales. Nu afirmăm un interpreter neinspectat.

Katana/Nuclei/sqlmap nu sunt dependențe baseline. Orice adaptor ulterior are pin de binar/templates/digest, politică de efecte, captură, probe de bypass și laborator; un nume în SKILL.md nu instalează sau autorizează toolul.

## 6. Proxy: blocaj confirmat, nu compatibilitate presupusă

`mitmproxy==12.2.3` publicat impune limite care țin `cryptography` la ≤48.1, `h2` la 4.3.0, `msgpack` la ≤1.1.2 și `tornado` la ≤6.5.5.[18] Combinația rezolvată include **cryptography 48.0.1, pyOpenSSL 26.2.0, mitmproxy-rs 0.12.11**. Se rezolvă, dar nu este aprobată.

Metadatele de advisories pe versiunile exacte au semnalat probleme pentru **cryptography, h2, msgpack și tornado**. Pentru cryptography, sursa indică remedieri în 49.0.0/50.0.0, în afara capului pachetului candidat.[19] Detaliile/aliasurile/fixed_in pentru toate sunt păstrate în JSON, fără a susține că toate sunt exploatabile în traseul Omnis. Lipsa exploitabilității demonstrate nu justifică alegerea lor ca frontieră de securitate nouă.

**Decizie: REJECTED_FOR_TARGET_USE.** Nu am instalat sau pornit proxyul afectat și nu am dat trafic prin el. Nu coborâm API crypto, nu activăm `ssl_insecure`, nu forțăm resolverul și nu folosim CONNECT opac ca scurtătură.

**B01e, owner integrare/executori:**

1. Verifică dacă există release upstream cu constrângeri remediate; dacă nu, propune patch minimal de packaging/cod peste tagul exact, cu licență și surse păstrate.
2. Rezolvă lock separat, actualizează toate dependențele afectate și verifică întregul set, nu numai cryptography; orice cap schimbat este decizie review-uită, nu override ascuns.
3. Execută teste upstream relevante, import/start, CA/cert validation, HTTP parsing/body buffering, conexiuni reutilizate, failure modes și G-NET.
4. Fixează commit/digest al buildului aprobat. Până atunci, P3a/P3b sunt **BLOCKED**; fundația/web și P2 inert pot începe.

Arhitectura alege frontiera HTTPS inspectabilă și un adaptor mitmdump îngust; gate-ul nu lasă implementatorul să înlocuiască asta cu un transport neobservabil. Dacă patchul necesar devine substanțial, revenim cu ADR de alternativă înainte de implementare, nu promitem un fork mic fără probe.

## 7. Lockfiles, imagini și upgrades

- **Web:** `package-lock.json`, Node/npm exacte, `npm ci --include=dev` pentru CI; transitivele sunt fixate în lock, nu refăcute la fiecare run.
- **Python:** proiecte/medii și `uv.lock` distincte API, Hermes, browser și proxy. `uv sync --locked`, hashes și inventar minimal; fără `pip install` la pornirea unui task.
- **Hermes:** cod+dependințe ale SHA auditat, configurație/tool inventory exportate sanitizat, patchuri separate dacă sunt necesare. Un Git SHA fără lock/build provenance nu este suficient.
- **OCI:** tag + digest de index și `platform: linux/amd64`; digestul manifestului platformei se înregistrează. Tagurile Node/Python/Postgres/Playwright au fost recitite din registry și coincid cu cele salvate. Nicio imagine nu a fost executată pentru validarea topologiei.
- **Postgres 18:** mountul și `PGDATA` versionat trebuie luate din documentația exactă a imaginii 18, nu copiate din exemple ≤17.[22] P0 validează persistența/restart/backup pe volumul ales.
- **Upgrade:** branch/commit dedicat; resolve + advisory/SBOM/licențe + unit/contracts/safety + smoke real; migrare și rollback/restore documentate. Fără actualizări automate în timpul runului.

Nu înlocuim verificarea actualizărilor cu o promisiune că exact pin = sigur. Auditul npm a raportat zero advisories pentru lockul probei la data verificării; checkul PyPI al API nu a raportat advisories pentru setul rezolvat. Acestea nu sunt audituri exhaustive de securitate sau licență.

## 8. Ce a fost executat și ce nu

| Verificare | Rezultat real | Limită |
|---|---|---|
| Runtime Node/npm/uv/Python alese | Executate în scratch; versiuni confirmate | Nu au înlocuit instalările personale |
| Rezolvare API cu hashes + instalare + `uv pip check` | Trecut | Nu este DB conectată sau runtime Hermes |
| FastAPI/Pydantic/ASGI, SQLAlchemy async dialect, AEAD sintetic | Trecut | Nu este API-ul produsului sau implementarea seifului |
| npm lock/install/audit | Trecut; zero advisories raportate | Nu audit complet de supply chain/licențe |
| TypeScript strict (`skipLibCheck: false`) | Trecut după alegerea Vitest 4.1.11 | Nu verifică componente Omnis inexistente |
| Vite build | Trecut | Warnings `use client` din librării, consemnate pentru aplicația client-only; nu build fără warnings |
| Testing Library / Radix dialog / router | Un test smoke trecut cu NODE_ENV=test | Nu UI E2E complet |
| Proxy resolve/advisories | Resolve trecut, security gate RESPINS | Nicio pornire/țintă; trebuie B01e |
| Digests imagini | Readback verificat din registry | Fără pull/run/hardening test |
| DESIGN.md CLI 0.4.0 | Zero erori și zero warnings; DTCG exportat | Nu certificare WCAG a produsului |

Nu au fost conectate conturi, apelate modele, lansate scanări sau implementată aplicația Omnis. Probele sunt programe mici separate, păstrate ca dovezi/reproduceri sub `documents/verification/`, nu un frontend/backend stub prezentat ca produs.

**Recontrol înainte de implementare:** [preimplementation-pins.json](verification/preimplementation-pins.json) păstrează răspunsurile de metadate pentru cele 33 de pinuri directe web/API/test/parsers verificate: toate versiunile exacte există în registre. Nicio versiune nu a fost schimbată. Acest recontrol nu a reinstalat pachete, nu a auditat transitivele/npm advisories și nu a executat imagini sau produsul; lockurile de produs și recontrolul securității rămân B01a/B01e. Absența unor ID-uri în câmpul PyPI nu este certificat de securitate. Probe și timestamps istorice rămân separate de acest snapshot.

## 9. Prag de pornire

**GO pentru fundație, web persistent și probe Hermes inerte. NO-GO pentru target effects până la B01e + binding + confinare.** Stackul este suficient de concret pentru implementatori; necunoscutele reale au owner, test și fază blocată, nu sunt ascunse sub „folosim latest și vedem”.

## Sources

[5] https://playwright.dev/python/docs/docker — https://playwright.dev/python/docs/docker
[14] https://nodejs.org/dist/index.json — Node.js release metadata
[15] https://peps.python.org/pep-0719 — CPython 3.13 release schedule
[16] https://www.postgresql.org/support/versioning — PostgreSQL supported versions
[17] https://registry.npmjs.org/openapi-typescript/7.13.0 — openapi-typescript exact metadata
[18] https://pypi.org/pypi/mitmproxy/12.2.3/json — mitmproxy dependency bounds
[19] https://pypi.org/pypi/cryptography/48.0.1/json — cryptography 48.0.1 advisory metadata
[21] https://www.sqlalchemy.org/download.html — SQLAlchemy maintained branches
[22] https://raw.githubusercontent.com/docker-library/docs/master/postgres/README.md — PostgreSQL official image volume and PGDATA
