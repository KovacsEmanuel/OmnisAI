# Omnis — stack și versiuni, baseline v1

**Probe de pinning istorice: 25 septembrie 2026 · Baseline amendat HF01–HF10 · P0.1–P0.3 locale, P0.4 parțial; runtime pentest neimplementat**

## 1. Verdict

**Frontendul și nucleul API au o combinație exactă rezolvată și exercitată în probe izolate. Proxyul publicat este respins pentru trafic target din cauza dependențelor cu advisories.** Hermes și browserul întărit nu sunt validate live. DB/migrațiile/controlul și webul au ulterior probe locale P0.1–P0.3; CLI/topologia P0.4 sunt parțiale, G00 deschis. Tabelul §8 este proba istorică de dependențe, nu starea actuală a întregului produs.

Registrul machine-readable este [Omnis_Stack_Baseline.versions.json](Omnis_Stack_Baseline.versions.json): versiuni, engines/peers, integrități npm, metadate PyPI, advisories și digests de imagini. [Outputul verificărilor](verification/stack-probe.json) și [inputurile reproductibile](verification/README.md) separă testele efectiv executate de porțile viitoare. Pinurile directe din tabel provin din aceste metadate și din rezolvările executate, nu din presupunerea „latest funcționează împreună”.

## 2. Runtime și infrastructură

| Componentă | Alegere exactă | Motiv / stare |
|---|---|---|
| Node.js | **24.21.0 LTS** | Descărcat în scratch de la nodejs.org, checksum verificat; executat `--version`; nu schimbă Node-ul hostului.[14] |
| npm | **11.19.0** | Versiunea inclusă în distribuția Node aleasă; executată în probe. Nu npm latest 12 implicit.[14] |
| CPython API | **3.13.15**, build normal cu GIL | Instalare scratch separată, importuri și teste efective; 3.13 rămâne baseline comun compatibil cu pinul Hermes, nu 3.14 forțat |
| uv | **0.12.19** | Wheel oficial verificat prin digest; folosit pentru venv/rezolvare/install cu hashes |
| PostgreSQL | **18.6**, `postgres:18.6-bookworm` | Metadate/digest verificate inițial; ulterior server real în probele locale P0.1–P0.4, fără G00; ramură suportată conform politicii publice.[16] |
| Hermes | **0.21.5**, `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` | Pin auditat, `requires-python >=3.11,<3.14`; mediu separat, nu upgrade al instalării personale |
| Docker/Compose pe host | **27.5.1+dfsg4 / 2.32.4-3**, observate | Client/server și Compose răspund; aceasta nu certifică deploymentul sau hardeningul |

Python 3.13 se apropie de trecerea la suport numai de securitate; release-ul 3.13.16 din calendar nu este tratat ca disponibil înaintea publicării. Reevaluăm patchul Python înaintea releaseului, nu îl înghețăm pentru totdeauna.[15] Un pin auditat astăzi nu justifică amânarea unui security update.

**Docker/Compose:** folosim interfața Compose v2 și un manifest testat pe hostul Linux de referință, fără `network_mode: host`, socket Docker în runtime sau containere privilegiate. Distribuția hostului, kernelul/seccomp/nftables și versiunile efective intră în manifestul P0/G-NET. Nu inventăm un număr „minim sigur” universal de Engine. Un host diferit trebuie să treacă aceeași suită înainte de target effects.

## 3. Frontend

**Consumator real P0.3:** `web/package.json`/`package-lock.json` folosesc subsetul necesar din pinurile de mai jos; nicio versiune selectată nu a fost schimbată. React/Router/Query și buildul sunt exercitate prin [probe de produs locale](verification/p03-local-bootstrap.md), separat de smoke-urile istorice. Radix rămâne disponibil ca alegere pentru widgeturi complexe, fără instalare inutilă în formularul nativ de bootstrap. Oxlint/React/a11y refolosesc unealta development fixată; aceasta nu intră în bundle. E2E folosește Playwright 1.63.0 și Chromium 153.0.8010.12/build 1243, nu browserul/executorul personal. Gate-urile și setup-ul sunt în [web/README.md](../web/README.md).

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
| Calitate Python, numai dev | **`ruff==0.16.9`, `mypy==2.3.1`**; amendament verificat local înainte de P0.3 |

**Decizie explicită:** SQLAlchemy async, sesiune per unitate de lucru, fără sesiune globală sau I/O sincron în event loop. Proba a construit dialectul async psycopg; nu s-a conectat la DB. Nu adăugăm `asyncpg`, `psycopg_pool` sau două ORM-uri. SQLAlchemy 2.0 este ramura de mentenanță; 2.1.0 tocmai publicat nu este adoptat automat pentru primul increment.[21]

Rezolvarea API cu hashes a produs un mediu compatibil, inclusiv Starlette **1.7.0** și pydantic-core **2.46.5**; întregul set este păstrat în inputurile probei. Manifestul aplicației va avea propriul `uv.lock` și security review; nu copiem mediul Hermes peste API.

Testul FastAPI folosește HTTPX `AsyncClient + ASGITransport`. Calea `TestClient` a avertizat despre deprecarea HTTPX în Starlette curent; am ales un test ASGI explicit, fără a adăuga un al doilea client numai pentru acel smoke. Pentru startup/shutdown real și pool DB avem teste de lifecycle separate în P0/P3.

**Amendament de calitate Python:** `ruff==0.16.9` și `mypy==2.3.1` sunt fixate în grupul dev al API și în lock, nu în runtime. Ruff verifică lint/format, mypy strict verifică sursele și testele cu pluginul oficial Pydantic tipizat, fără casts sau excluderi pentru a ascunde erori. `make lint-api`/`make typecheck-api` intră în gate-ul comun și au controale pozitive/negative executabile. [Proveniența, rezultatele pe checkout curat și limitele](verification/p02-python-quality.md) sunt separate de probele istorice de dependențe de mai sus; acestea nu sunt rescrise drept certificare a produsului.

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

Katana și Nuclei au integrare planificată explicit în §10, fără a fi instalate/admisibile astăzi; sqlmap rămâne candidat E1. Orice adaptor are pin de binar/templates/digest, politică de efecte, captură, probe de bypass și laborator; un nume în SKILL.md nu instalează sau autorizează toolul.

## 6. Proxy: blocaj confirmat, nu compatibilitate presupusă

`mitmproxy==12.2.3` publicat impune limite care țin `cryptography` la ≤48.1, `h2` la 4.3.0, `msgpack` la ≤1.1.2 și `tornado` la ≤6.5.5.[18] Combinația rezolvată include **cryptography 48.0.1, pyOpenSSL 26.2.0, mitmproxy-rs 0.12.11**. Se rezolvă, dar nu este aprobată.

Metadatele de advisories pe versiunile exacte au semnalat probleme pentru **cryptography, h2, msgpack și tornado**. Pentru cryptography, sursa indică remedieri în 49.0.0/50.0.0, în afara capului pachetului candidat.[19] Detaliile/aliasurile/fixed_in pentru toate sunt păstrate în JSON, fără a susține că toate sunt exploatabile în traseul Omnis. Lipsa exploitabilității demonstrate nu justifică alegerea lor ca frontieră de securitate nouă.

**Decizie: REJECTED_FOR_TARGET_USE.** Nu am instalat sau pornit proxyul afectat și nu am dat trafic prin el. Nu coborâm API crypto, nu activăm `ssl_insecure`, nu forțăm resolverul și nu folosim CONNECT opac ca scurtătură.

**B01e, owner integrare/executori — două praguri, fără ciclu cu P3:**

1. Verifică dacă există release upstream cu constrângeri remediate; dacă nu, propune patch minimal de packaging/cod peste tagul exact, cu licență și surse păstrate.
2. Rezolvă lock separat, actualizează toate dependențele afectate și verifică întregul set, nu numai cryptography; orice cap schimbat este decizie review-uită, nu override ascuns.
3. **B01e-build:** teste upstream/import/start inert, CA/cert validation și primitive HTTP ale buildului remediat; fixează commit/digest/lock/licențe. Verdict LAB_TEST_ONLY, nu assessment ready. Buildul publicat respins nu este o alternativă de testare implicită.
4. **B01e-integrated:** B07/B09 construiesc și verifică broker/addon/buffering/reuse/failure modes/G-NET în harness izolat, cu fixture/sinks explicit autorizate și egress extern închis. Controale pozitive/negative la aceeași frontieră; lipsa addonului nu permite trafic. Abia apoi build+integrare închid G-DEPENDENCIES pentru transportul respectiv și permit startupul normal al executorului. Fără pragul necesar, execuția P3 rămâne BLOCKED; fundația/web și P2 inert pot continua.

Arhitectura alege frontiera HTTPS inspectabilă și un adaptor mitmdump îngust; gate-ul nu lasă implementatorul să înlocuiască asta cu un transport neobservabil. Dacă patchul necesar devine substanțial, revenim cu ADR de alternativă înainte de implementare, nu promitem un fork mic fără probe.

## 7. Lockfiles, imagini și upgrades

- **Web:** `package-lock.json`, Node/npm exacte, `npm ci --include=dev` pentru CI; transitivele sunt fixate în lock, nu refăcute la fiecare run.
- **Python:** proiecte/medii și `uv.lock` distincte API, Hermes, browser și proxy. `uv sync --locked`, hashes și inventar minimal; fără `pip install` la pornirea unui task.
- **Hermes:** cod+dependințe ale SHA auditat, configurație/tool inventory exportate sanitizat, patchuri separate dacă sunt necesare. Un Git SHA fără lock/build provenance nu este suficient.
- **OCI:** tag + digest de index și `platform: linux/amd64`; digestul manifestului platformei se înregistrează. Tagurile Node/Python/Postgres/Playwright au fost recitite din registry și coincid cu cele salvate. Proba inițială de metadate nu a executat imagini; probele instalate P0.4 ulterioare sunt în verification/p04-host-uds.md, nu certificare a launcherului.
- **Postgres 18:** mountul și `PGDATA` versionat trebuie luate din documentația exactă a imaginii 18, nu copiate din exemple ≤17.[22] P0 validează persistența/restart/backup pe volumul ales.
- **Upgrade:** branch/commit dedicat; resolve + advisory/SBOM/licențe + unit/contracts/safety + smoke real; migrare și rollback/restore documentate. Fără actualizări automate în timpul runului.

Nu înlocuim verificarea actualizărilor cu o promisiune că exact pin = sigur. Auditul npm a raportat zero advisories pentru lockul probei la data verificării; checkul PyPI al API nu a raportat advisories pentru setul rezolvat. Acestea nu sunt audituri exhaustive de securitate sau licență.

## 8. Probe istorice de dependențe — executat versus neexecutat

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

În livrarea istorică de pinning nu au fost conectate conturi, apelate modele, lansate scanări sau implementată aplicația Omnis. Fundația implementată ulterior este documentată în README/plan §19; amendamentul curent nu lansează servicii sau inference. Probele de aici sunt programe mici separate, păstrate ca dovezi/reproduceri sub `documents/verification/`, nu un frontend/backend stub prezentat ca produs.

**Recontrol înainte de implementare:** [preimplementation-pins.json](verification/preimplementation-pins.json) păstrează răspunsurile de metadate pentru cele 33 de pinuri directe web/API/test/parsers verificate: toate versiunile exacte există în registre. Nicio versiune nu a fost schimbată. Acest recontrol nu a reinstalat pachete, nu a auditat transitivele/npm advisories și nu a executat imagini sau produsul; lockurile de produs și recontrolul securității rămân B01a/B01e. Absența unor ID-uri în câmpul PyPI nu este certificat de securitate. Probe și timestamps istorice rămân separate de acest snapshot.

## 9. Prag de pornire

**GO pentru fundație, web persistent și probe Hermes inerte. NO-GO pentru target effects până la B01e + binding + confinare.** Stackul este suficient de concret pentru implementatori; necunoscutele reale au owner, test și fază blocată, nu sunt ascunse sub „folosim latest și vedem”.

## 10. Reutilizare OSS adoptată, nu runtime paralel

**HF04–HF08, decizie de baseline:** produs independent peste Hermes nativ și fundația Omnis. Adoptăm implementări, teste, prompturi și metodologie reale, nu doar idei. Nu importăm orchestratoarele Strix/PentestGPT/NeuroSploit/PentAGI/Shannon. Matricea de mai jos este backlog normativ de import/adaptare; **niciun import sau binar nou nu este instalat/admis prin acest amendament**. Pinurile de cercetare nu devin lockuri de produs prin redenumire.

Proveniența exactă, intervalele/hashurile și schimbările necesare rămân în [manifestul reuse](verification/omnis-modularity-research-supplement.reuse.json) și [inventarul OSS/Strix](verification/omnis-upgrade-review.inventory.json). Acestea sunt anexe de surse; ordinea/deciziile sunt aici și în plan, nu în recomandările istorice. Recontrolul a numărat 34 unități (26 cod/conținut/date + 8 mecanisme native), 98 referințe source/test și 75 ghiduri Strix + README, dintre care 29 de vulnerabilități. Toate rămân source-reviewed/not-imported, nu capabilități certificate.

### 10.1. Pinurile surselor selectate

| Repository | Revizie inspectată exactă |
|---|---|
| `CyberSecurityUP/NeuroSploit` | `5d4e7e0347219ceae22735ec6af3d8cdd0561ded` |
| `GreyDGL/PentestGPT` | `e8b1bb77d1ac00329675cec3b060aba971ec1ac8` |
| `KeygraphHQ/shannon` | `327c10fd90a6186a9f035b4b6ddb5bbba1839e92` |
| `NousResearch/hermes-agent` | `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` |
| `ShielderSec/webtech` | `7141d3542b650df9f984deba6213e2911ee7b9d1` |
| `assetnote/kiterunner` | `7d5824cda9a2eef86d8d18b05b713d7e260f34d2` |
| `assetnote/wordlists` | `6dea231f4cbd356a637851b1c13b83de4da00adb` |
| `blacklanternsecurity/bbot` | `a6fb827bb144cdb85b52e142a4d6e14ed5f94b69` |
| `digininja/CeWL` | `ca01aeae1c77bb086ef757611dea6377b8d1168b` |
| `projectdiscovery/katana` | `29f4d1cbaffc634f79f389c59f34be6f85fcde5d` |
| `projectdiscovery/nuclei` | `47f74706a54261ecbbbac617a75c1ec5ef9bddd7` |
| `schemathesis/schemathesis` | `be1b46696dc7eb8aa472054d1b46c95e8f069382` |
| `scrapy/scrapy` | `5d789b24f994bcdfca97c34d976c73739e064849` |
| `typesafe-ai/typesafe-sdk-python` | `f078f1e208a0d885154dc758344ae4fce77ac168` |
| `usestrix/strix` | `ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2` |
| `vxcontrol/pentagi` | `ea665308baaff015b226f308438a68d929d0f29b` |

### 10.2. Unități de import cu consumator și probe

C = copiere/adaptare de sursă+teste; PORT = algoritm portat cu atribuire; P = pachet/executabil fixat prin adaptor; N = suprafață nativă păstrată. Nu portăm un engine Go în Python și nu adăugăm Go/Rust/Twisted/Temporal în control plane pentru helpers. Fiecare import păstrează licența/notices, upstream commit, hash de fișier și diff de adaptare. Snapshotul original poate rămâne quarantine, nemontat runtime-ului; doar releaseul selectat intră în catalog.

| ID | Sursă concretă / formă | Destinație și ticket | Adaptare și verificare obligatorie |
|---|---|---|---|
| U01 | C Strix `strix/skills/`, toate 75 ghiduri din inventar | `skills/`, B06/B11 apoi B14b/E1–E4 | Lot inițial root/recon/IDOR/counterevidence/severity; restul importat/revizuit în loturi. Golden/frontmatter/ID/ref/digest; methodology-only ≠ execuție. `test_skill_dir_extension.py` adaptat: shadowing nu este permis. |
| U02 | C Strix `_resolve_skills`, `render_system_prompt`, `system_prompt.jinja` | composer Hermes B06; S01/S03/S06 | `tests/test_runner_root_prompt.py`; missing skill refuzat, fără „test ALL/2000 steps”, terminal generic sau întreg istoric moștenit. |
| U03 | C Strix `output_store.py::_take_prefix/_take_suffix/_head_tail/bound_text` | evidence preview B07/B08, S07 | `tests/test_output_store.py`; limita include notice (proba istorică 10 bytes → 45 a eșuat), UTF-8/paginare/opaque artifact, nu spill raw comun. |
| U04 | C Strix `tools/threat_model/tools.py`, notes/agent_finish | runs/surfaces/tasks B10/B18a, S04/S05 | `tests/test_threat_model_tool.py`; rubrici structurate și amendamente append-only PostgreSQL, nu JSON globals; clue→revizie→task. |
| U05 | C Strix `report/writer.py::safe_fence/parse_fenced_code/render_vulnerability_md` | reports B13c, S08 | `test_fenced_code.py`, `test_report_writer.py`; snapshot eligibil, markup inert; csv_safe numai la un export CSV ulterior, nu motiv de a adăuga CSV acum. |
| U06 | C PentestGPT activ `pentestgpt_agent/src/pentestgpt_agent/plan.py::compile_plan`, `pentestgpt_agent/src/pentestgpt_agent/execution.py::_exact_receipt_slice` | tasks/validation/evidence B06/B12 | `pentestgpt_agent/tests/test_plan.py`, `test_execution.py`; basis/dependency/revision și bytes exacte. Fără SQLite MemoryKernel, wrapper vechi, classifier lexical de efect sau limită globală arbitrară de un task. |
| U07 | PORT NeuroSploit `neurosploit-rs/crates/harness/src/typesafe.rs::same_finding/progress_checkpoint/response_origin`, `neurosploit-rs/crates/harness/src/pipeline.rs::typesafe_prune_agents` | integrations/jev B06j/B14j | Teste typed fixtures/sentinel/unknown; ranking nu șterge coverage, fără defaults optimiste/raw body/jev-latest; nu portăm clientul Rust. |
| U08 | PORT NeuroSploit `neurosploit-rs/crates/harness/src/chain.rs::Capability/provides/requires/derive_links/path_for`, `neurosploit-rs/crates/harness/src/pipeline.rs::attack_chain/chain_from_seed`, `agents_md/chains/` | findings/attack_paths + tasks B18c | Păstrează testele din chain.rs, adaugă needs-review exclus din frontieră executabilă, identity/state/epoch și evidence per edge; Jev validate=true nu este oracle. |
| U09 | PORT PentAGI `backend/pkg/providers/helpers.go::repeatingDetector/executionMonitor`, `backend/pkg/templates/prompts/task_assignment_wrapper.tmpl` + debrief | tasks/context B06/B18a | `helpers_test.go::TestRepeatingDetector/TestExecutionMonitorDetector_*`; key include identitate/procedură/stare, nu pierde diferențe materiale; fără stack Go/Graphiti. |
| U10 | P Katana `pkg/engine/parser/`, `pkg/navigation`, `pkg/output/result.go` JSONL | executors/recon B10a/B15 | Crawler/parsers upstream, nu crawler nou. Compatibilitate JSONL și sink allow/deny/cancel; update/form submit/off-origin neaprobat refuzate; fiecare request atribuit. |
| U11 | P Nuclei `pkg/templates`, `pkg/operators`, `pkg/output.ResultEvent` | adaptor semnale B15n, expuneri E1 | Engine fixat; subset HTTP de templates cu provenance/digest/licență **distincte, încă de selectat**. Fără code/JS/headless/network/OAST; matcher hit ≠ verdict, zero match ≠ negativ, secret/PII controls. |
| U12 | P Schemathesis `specs/openapi`, generators/stateful links/checks | adaptor generator API E2 | Caz generat→Action brokered, seeds/shrinking/cleanup contorizate, no remote refs; contract failure ≠ vulnerabilitate. Lock/probe Python separate, fără fuzz runtime paralel. |
| U13 | P `typesafe-sdk` 0.7.2, client async, model candidat `jev-1.13.0` | integrations/jev B06j/B14j | `RetryPolicy(max_retries=0)`, MockTransport tests upstream, deadline; dependență `httpx2` în lock separat, nu presupunere de compatibilitate HTTPX. Payload final/answers/model exact; no extra_body/header override, missing→fallback. |
| U14 | PORT candidat Shannon task grouping (R07), nu Temporal/pi | tasks/grouping E3, necritic pentru MVP | Suplimentul înlocuiește „numai referință” cu shortlist tehnic; AGPL-3.0 rămâne obligație reală. Importul copiat așteaptă decizia de distribuție/licență, fără a bloca BOLA/alte importuri; duplicate/unknown labels și observații negrupate păstrate. |

Unitățile S/M/R/HM de mai jos **completează**, nu dublează U01–U14. Referințele source/test și destinațiile integrale sunt rezolvabile în manifest; test absent upstream înseamnă teste Omnis de scris, nu test upstream pretins trecut. Aceste rânduri stabilesc primul consumator; nu cer tot catalogul înainte de prima vulnerabilitate.

| ID | Formă / unitate concretă la pinul de mai sus | Destinație | Ticket / probă și limită |
|---|---|---|---|
| S01 | copy_adapt: `strix/agents/prompt.py::_resolve_skills; render_system_prompt` | `integrations/hermes/src/omnis_hermes/prompt_bundle.py` | B06/H03 — Golden root/leaf/mode, missing package and immutable bundle digest. Teste: controale Omnis din manifest. |
| S02 | copy_adapt_subset: `strix/skills/__init__.py::_parse_skill_content; validate_requested_skills; load_skills` | `api/src/omnis/modules/settings/skill_catalog.py` | B06/P4a — Duplicate ID, malformed frontmatter, path escape, missing ref and silent override rejected. Teste: controale Omnis din manifest. |
| S03 | copy_adapt_content: `strix/skills/coordination/root_agent.md::Threat model; coverage reconciliation; coordination` | `skills/omnis-engagement/references/coordination.md` | B06/B18a — New clue changes next task; consumed delta does not re-spawn. Teste: controale Omnis din manifest. |
| S04 | copy_adapt_schema_and_validation: `strix/tools/threat_model/tools.py::_REQUIRED_SECTIONS; _missing_sections; _save_impl; _amend_impl` | `api/src/omnis/modules/runs/threat_model.py` | B10b — Concurrent amendment preserved; unknown observation cannot become observed. Teste: controale Omnis din manifest. |
| S05 | copy_adapt_contract_not_coordinator: `strix/tools/agents_graph/tools.py::create_agent contract; agent_finish contract` | `api/src/omnis/modules/tasks/handoffs.py` | B06/H04/H06 — Wrong child/attempt/result refs refused; no duplicate wake. Teste: controale Omnis din manifest. |
| S06 | adapt_interface: `strix/tools/load_skill/tool.py::load_skill` | `integrations/hermes/src/omnis_hermes/skills_projection.py` | B06/H03 — Loading knowledge does not install dependencies, grant tools or mutate prompt prefix. Teste: controale Omnis din manifest. |
| S07 | copy_adapt: `strix/tools/output_store.py::UTF-8 head/tail previews` | `api/src/omnis/modules/evidence/preview.py` | B07/B08 — UTF-8 intact; whole preview cap including notice; unavailable artifact not fabricated. Teste: controale Omnis din manifest. |
| S08 | copy_adapt: `strix/report/writer.py::csv_safe; safe_fence; render_vulnerability_md` | `api/src/omnis/modules/reports/render.py` | B13c — Hostile markup inert; missing bytes not exported; existing snapshot unchanged. Teste: controale Omnis din manifest. |
| S09 | copy_adapt_registry_validation_only: `strix/agents/factory.py::_ensure_unique_tool_names; register_agent_tools` | `api/src/omnis/modules/tasks/module_registry.py` | B06/G-MODULE — Duplicate type ID fails before release; role cannot obtain extra tool authority. Teste: controale Omnis din manifest. |
| S10 | copy_adapt_content: `strix/skills/analysis/counterevidence.md::Closure, counterevidence and revision` | `skills/omnis-evidence/SKILL.md` | B11/B12 — No proof gap or dead target counted as a secure negative. Teste: controale Omnis din manifest. |
| R01 | copy_adapt_passive: `webtech/target.py::parse_regex_string; checks` | `api/src/omnis/modules/surfaces/fingerprints.py` | B10b — Offline positive/negative/contradictory signatures; ReDoS/time cap; no network. Teste: controale Omnis din manifest. |
| R02 | copy_adapt: `webtech/parser.py::WTParser` | `api/src/omnis/modules/surfaces/fingerprints.py` | B10b — Meta/script path preserved; inline JS never executed. Teste: controale Omnis din manifest. |
| R03 | port_to_python: `cewl.rb::extract_path_components; word count/grouping; frequency sort` | `api/src/omnis/modules/surfaces/wordlists.py` | B10d — Reproducible corpus; v1/Unicode retained per recipe; no secrets/query values; hard entry/byte caps. Teste: controale Omnis din manifest. |
| R04 | port_schema_and_rendering_subset: `pkg/proute/route.go::Route; Path; Query; Body` | `api/src/omnis/modules/surfaces/route_candidates.py` | B15 — GET/POST body distinctions retained; candidate outside scope or unknown field is blocked. Teste: controale Omnis din manifest. |
| R05 | adapt_baseline_model: `pkg/kiterunner/preflight.go::WildcardResponse; targetWildcardDetection` | `api/src/omnis/modules/surfaces/response_baselines.py` | B10d/B15 — Soft404 versus real route differentiated without dropping all 401/403; baseline drift invalidates. Teste: controale Omnis din manifest. |
| R06 | reuse_data_index: `data/technologies.json::Technology-indexed corpus metadata` | `api/src/omnis/modules/settings/wordlist_sources.py` | B10d — Zero-entry list stays empty; million-entry source truncated before admission; no HTML execution from Download field. Teste: controale Omnis din manifest. |
| R07 | port_to_python: `apps/worker/src/ai/reconciliation/task-formation-schema.ts::buildTaskFormationSchema; parseGroup; acceptTaskGroups` | `api/src/omnis/modules/tasks/grouping.py` | E3, licență înainte de import — Valid group accepted; cross-group reuse invalidates each claimant; unknown labels do not disappear from frontier. Teste: controale Omnis din manifest. |
| M01 | copy_adapt_subset: `bbot/core/event/base.py::BaseEvent.json`; `bbot/core/event/base.py::BaseEvent.id`; `bbot/core/event/base.py::BaseEvent.uuid`; `bbot/core/event/base.py::BaseEvent.data_hash` | `api/src/omnis/modules/surfaces/events.py` | B10b — Două observații ale aceluiași obiect păstrează două ocurențe și parent/evidence refs; redelivery aceeași ocurență este idempotentă; cross-engagement parent respins. Teste: `bbot/test/test_step_1/test_events.py::test_event_hashing`. |
| M02 | copy_adapt_subset: `bbot/modules/base.py::BaseModule._event_precheck`; `bbot/modules/base.py::BaseModule._event_postcheck`; `bbot/modules/base.py::BaseModule._event_postcheck_inner` | `api/src/omnis/modules/tasks/module_registry.py` | B06/G-MODULE — Observation de tip permis selectează doar subscriberii activi; tip necunoscut, handler eroare și epoch expirat refuzate; replay nu dublează taskul. Teste: `bbot/test/test_step_1/test_modules_basic.py::test_modules_basic_checks`. |
| M03 | copy_adapt_subset: `bbot/scanner/preset/preset.py::Preset.merge`; `bbot/scanner/preset/preset.py::Preset.bake`; `bbot/scanner/preset/preset.py::Preset.add_module`; `bbot/scanner/preset/preset.py::Preset._is_valid_module` | `api/src/omnis/modules/runs/plan_snapshot.py` | B06/P4a — Preset A + override B produce un snapshot determinist și diff vizibil; dependency exclusă/ciclu/ID necunoscut blochează publicarea; draft nou nu schimbă run activ. Teste: `bbot/test/test_step_1/test_presets.py::test_preset_module_resolution`. |
| M04 | copy_adapt_subset: `bbot/scanner/preset/validate.py::_classify_loc`; `bbot/scanner/preset/validate.py::_format_errors`; `bbot/scanner/preset/validate.py::validate_preset`; `bbot/core/config/models.py::BaseModuleConfig` | `api/src/omnis/modules/settings/skill_catalog.py` | B14b — Config bun publicat/readback; typo nested + timeout invalid returnează toate câmpurile cu 422; secret sentinel absent din erori; schema lipsă refuzată. Teste: `bbot/test/test_step_1/test_validate_preset.py::test_validate_preset_multiple_errors`, `bbot/test/test_step_1/test_validate_preset.py::test_validate_preset_config_modules_as_list`. |
| M05 | copy_adapt_subset: `bbot/core/helpers/wordcloud.py::WordCloud.mutations`; `bbot/core/helpers/wordcloud.py::WordCloud.modifiers`; `bbot/core/helpers/wordcloud.py::WordCloud.add_word`; `bbot/core/helpers/wordcloud.py::WordCloud.get_number_mutations`; `bbot/core/helpers/misc.py::gen_numbers` | `api/src/omnis/modules/surfaces/wordlists.py` | B10d/B15 — Termeni sintetici + limite produc artifact determinist/digest și provenance; plafon depășit trunchiat explicit; cookie/PII excluse; nicio cerere target. Teste: `bbot/test/test_step_1/test_helpers.py::test_word_cloud`. |
| M06 | copy_adapt_subset: `scrapy/utils/conf.py::build_component_list` | `api/src/omnis/modules/tasks/component_order.py` | B06/G-MODULE — Ordine diferită salvată apare în readback și execuție; disabled nu rulează; duplicate ID/priority invalid respinse; policy hooks obligatorii nedezactivabile. Teste: `tests/test_utils_conf.py::TestBuildComponentList`. |
| M07 | copy_adapt_subset: `scrapy/pipelines/__init__.py::ItemPipelineManager._add_middleware`; `scrapy/pipelines/__init__.py::ItemPipelineManager.process_item_async`; `scrapy/middleware.py::MiddlewareManager._process_chain` | `api/src/omnis/modules/surfaces/ingestion.py` | B10a — Ordine A→B verificată, output B derivat din A; invalid la B împiedică persistarea; raw evidence și receipt de rejeție rămân; anulare fără event de succes. Teste: `tests/test_pipelines.py::TestPipeline.test_pipeline`, `tests/test_pipelines.py::TestPipeline.test_process_item_exception`. |
| M08 | copy_adapt_subset: `scrapy/core/downloader/middleware.py::DownloaderMiddlewareManager._add_middleware`; `scrapy/core/downloader/middleware.py::DownloaderMiddlewareManager._process_request`; `scrapy/core/downloader/middleware.py::DownloaderMiddlewareManager._process_response`; `scrapy/core/downloader/middleware.py::DownloaderMiddlewareManager._process_exception` | `executors/http/src/omnis_http/action_hooks.py` | B07 — A/B se aplică înainte și B/A după; redirect/retry devine propunere reautorizată; PolicyDenied și Cancelled nu sunt convertite în succes, Stop între propunere/dispatch refuză. Teste: `tests/test_downloadermiddleware.py::TestResponseFromProcessException.test_process_response_called`, `tests/test_downloadermiddleware.py::TestResponseExceptions.test_processed_middleware_not_called`. |
| M09 | copy_adapt_subset: `scrapy/utils/signal.py::_send_catch_log_asyncio`; `scrapy/signalmanager.py::SignalManager.connect`; `scrapy/signalmanager.py::SignalManager.disconnect` | `api/src/omnis/transport/events.py` | B08 — Consumator UI eșuat nu pierde eventul DB ori alt consumator; retry din cursor recuperează; duplicate event nu dublează wake/task; observerul nu autorizează efect. Teste: `tests/test_utils_signal.py::TestSendCatchLog.test_send_catch_log`. |
| HM01 | use_native_surface_not_copy: `tools/delegate_tool.py::Native delegation` | `integrations/hermes/src/omnis_hermes/` | B10c/H04 — Per-run researcher; trusted binding, budget and Stop. Teste: controale Omnis din manifest. |
| HM02 | use_native_surface_not_copy: `agent/subagent_lifecycle.py::Native lifecycle API` | `integrations/hermes/src/omnis_hermes/` | B06/H04 — Optional plugin surface with active parent; no durable worker assumption. Teste: controale Omnis din manifest. |
| HM03 | use_native_surface_not_copy: `agent/background_review.py::Native review fork` | `integrations/hermes/src/omnis_hermes/` | B14c — Sanitized maintenance session plus proposal tool, no active-release writer. Teste: controale Omnis din manifest. |
| HM04 | use_native_surface_not_copy: `agent/curator.py::Native curator` | `integrations/hermes/src/omnis_hermes/` | B14c — Working library only; dry_run prompt is not read-only enforcement. Teste: controale Omnis din manifest. |
| HM05 | use_native_surface_not_copy: `tools/skill_manager_tool.py::Native staging/approval` | `integrations/hermes/src/omnis_hermes/` | B14b — Draft source only; separate publisher and RO release; import failure tested. Teste: controale Omnis din manifest. |
| HM06 | use_native_surface_not_copy: `cron/scheduler.py::Native periodic scheduling`; `cron/scheduler_prompt.py::_parse_wake_gate` | `integrations/hermes/src/omnis_hermes/` | B21m, după G-HERMES-BOUND — no_agent enqueue first; exclusive maintenance admission; explicit memory/MCP/provider. Teste: controale Omnis din manifest. |
| HM07 | use_native_surface_not_copy: `hermes_cli/plugins.py::Native plugin tools and skills` | `integrations/hermes/src/omnis_hermes/` | B06 — Narrow product tools, no user-profile changes or generic admin proxy. Teste: controale Omnis din manifest. |
| HM08 | use_native_surface_not_copy: `tools/async_delegation.py::Native completion recovery` | `integrations/hermes/src/omnis_hermes/` | B06/H06/H07 — Unknown work and idempotent inbox reconciliation, not resume of thread. Teste: controale Omnis din manifest. |

### 10.3. Admitere și înlocuiri explicite

Katana devine reutilizare planificată B10/B15, Nuclei adaptor de semnale B15n/E1, Schemathesis E2; sqlmap rămâne candidat E1 fără pin/admitere încă. Textul vechi „nu dependențe baseline” pentru toate trei este înlocuit: **selectat pentru integrare nu înseamnă instalat, evaluat sau permis**. B10 folosește subsetul parser/crawl care trece gate-ul transportului; dacă binarul nu poate atribui requests, acesta rămâne blocat, nu se recreează preventiv engine-ul și nu se ocolește brokerul.

**Copyleft la pin, nu licență presupusă permisivă:** BBOT și Kiterunner au `LICENSE` AGPL-3.0, WebTech `LICENSE` GPL-3.0; CeWL `cewl.rb:18` declară CC-BY-SA 2.0 sau GPL-3+. Shannon AGPL-3.0 nu este singura unitate cu obligații de distribuție. Aceeași verificare de compatibilitate/notices se aplică fiecărui port, fără a șterge shortlistul tehnic ori a porni alt runtime. Decizia necesară privește importul/distribuția unității, nu aprobarea deja dată pentru amendamente; nu pretindem aviz juridic. Sursa este fișierul de licență la SHA-ul din §10.1, nu metadata unei versiuni latest. Lista source-test a manifestului este incompletă pentru S/R/HM; testele Strix/U06–U13 din tabel trebuie fixate prin hash în felia lor, nu declarate deja importate sau executate.

Buildurile/executabilele și corpusurile cer hashes/licențe/lockuri proprii în felia de import; SHA-ul repo-ului nu certifică binarul sau bytes Assetnote de pe CDN. Engines nu fac auto-update la runtime. BBOT se extrage fără Ansible/scan helpers/_exec_config_class/env/scope merge; Scrapy fără Twisted/Crawler, signals nu sunt inbox durabil; WebTech fără downloader și cu malformed regex/ReDoS controls; CeWL fără Ruby spider/PII/password lists; Kiterunner fără suita de preflight mutatoare. Aceste adaptări sunt cerințe de test, nu invitație să înlocuim implementările cu descrieri conceptuale.

Admission model B06m/G-MODEL se introduce înainte de prima inferență P2-live, în monolitul și adaptorul Hermes existente; B07 și Jev extind același ledger, nu adaugă un serviciu de billing sau runtime paralel. Seam-ul pre-call/limitele/retryurile sunt probă la pin, nu capabilitate native presupusă.

Jev este inclus în produs, configurabil OFF/SHADOW/ADVISORY, nu prerechizit BOLA și nu validator. Modelul/SDK/întrebările/data policy sunt fixate per run; probele live cer cont/date/buget explicit. Licențele/notices exacte se păstrează la import, iar un conflict de distribuție blochează **unitatea afectată**, nu suspendă întregul baseline într-o nouă dezbatere. Nu se introduc dependențe ori module goale acum.

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
