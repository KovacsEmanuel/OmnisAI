# Verificări ale baseline-ului, nu aplicația Omnis

`stack-probe.json` păstrează output real și limitele probelor de dependențe din 25 septembrie 2026. `stack-probe-inputs/` conține inputurile și lockurile reproducerii; nu este scaffoldul aplicației și nu pornește Hermes sau o scanare. Nu se copiază aceste probe ca implementare de domeniu.

## Reproducere în scratch

Copiază subdirectorul dorit în scratch (`$TMPDIR`, nu în runtime-ul personal). Folosește exact Node 24.21.0/npm 11.19.0 sau CPython 3.13.15/uv 0.12.19 din baseline. Instalarea pachetelor are nevoie de rețea către registry; probele nu cer conturi AI.

### Web

Din copia `web/`:

```sh
npm ci --include=dev --ignore-scripts
node node_modules/typescript/bin/tsc --noEmit
NODE_ENV=production node node_modules/vite/bin/vite.js build
NODE_ENV=test node node_modules/vitest/vitest.mjs run --environment jsdom
npm audit --include=dev --json
```

Smoke: import/build React + Router + Query + Radix și un test DOM pentru dialog. `@vitejs/plugin-react` este instalat în setul verificat, dar smokeul de bază nu îl configurează; P0 trebuie să exercite configurația reală a produsului. Buildul a emis warnings despre `use client`; nu sunt mascate în raport. Nu există server dev expus sau o aplicație completă.

### API

Din copia `api/`:

```sh
uv venv --python 3.13.15 .venv
uv pip sync --python .venv/bin/python --require-hashes resolved.txt
.venv/bin/python smoke.py
uv pip check --python .venv/bin/python
```

Testele ASGI sunt in-process și folosesc date sintetice. Dialectul PostgreSQL async este construit fără conectare. AES-GCM folosește o cheie nouă și o singură criptare; nonce-ul fix este exclusiv pentru această probă, nu pentru seiful produsului. DSN-ul `unused` nu contactează un server.

### Ce nu se reproduce prin aceste comenzi

Migrații/DB reală, browser executor hardened, egress/HTTPS policy, native Hermes child binding/wake, providers/OAuth, eficacitate pentest și E2E Omnis. Acestea au porți separate în plan. Proxyul candidat respins nu are instrucțiuni de pornire aici; nu se transformă un dependency resolve reușit într-un executor permis.

## Documente și UI offline

Din rădăcina repo-ului, într-un mediu cu `Markdown==3.10.2`:

```sh
python -m unittest discover -s tests/documentation -v
python scripts/render_docs.py
python scripts/render_docs.py --check
```

Rendererul acceptă numai Markdown trusted al proiectului. **Nu este sanitizer și nu se folosește pentru evidence de la ținte.** CSP a cititoarelor blochează scripts/subresurse ca defense-in-depth, nu transformă rendererul într-un parser pentru conținut ostil. HTML este generat din Markdown; nu se editează în paralel cele două formate.

Verificarea browserului necesită Playwright Python și Chromium local, separat de viitorul executor de produs:

```sh
python tests/documentation/browser_check.py --include-documents --output "$TMPDIR/omnis-docs-browser-check.json"
```

Aceasta verifică prototipul DEMO, regresiile Stop/focus/context și cititoarele offline; raportul păstrat este `documents/verification/browser-check.json`, nu rezultate de pentest. Revizia UI `df17a29` are **116 checks trecute**, fără erori JavaScript sau cereri HTTP(S) neașteptate. Comanda `make check` a trecut: 22 teste documentation/model, 11 development și 4 cazuri Oxlint. Node syntax check și DESIGN.md CLI 0.4.0 lint au trecut; exportul DTCG corespunde sursei.

Fluxul exercitat prin clickuri: Dashboard → Overview cu metrici/Severity/buget → stream filtrat → endpoint exact → raport cu două findings eligibile → acceptarea pentru raport a celui de-al treilea CONFIRMED → raport nou cu trei. HTML și JSON au fost descărcate și citite; redescărcarea raportului vechi păstrează snapshotul inițial. Candidatul Critical nu intră în contoarele confirmate sau ca vulnerabilitate în raport. Stările evidence indisponibile se propagă în finding, inspector, coverage și exportul nou, fără rescrierea verdictului sau a raportului vechi. Payloadurile HTML/SVG de control rămân text.

Review-ul independent a găsit o fază reactivată greșit după Stop + rerender și un contur de focus parțial acoperit la Tab/Shift+Tab. Părintele a reprodus ambele RED și a verificat corecțiile GREEN, inclusiv revenirea prin tastatură la 1440/390px. Review-ul vizual a dus la metrici Home value-first, Top findings mai dens, readiness de raport compact și evenimente de 97px la 1440px, cu ținte clicabile de minimum 44px. Coverage păstrează intenționat contextul operation/identity, nu copiază clase sau succese nesusținute din template. Lecțiile sunt în UI/UX §0 și skill-urile proiectului.

Stop/focus/dialog/drawer, scope-ul global/contextual, new/setup, filtrele, stările empty/error/stale și controalele demo pliate rămân acoperite. Capturi desktop/mobil și dropdownul de review au fost inspectate real. Testul CSS zoom 200% nu înlocuiește verificarea zoomului nativ; screen-readerul și alte browsere rămân neverificate. **Aceasta nu este aprobare vizuală a utilizatorului sau integrare backend**; G-DESIGN rămâne deschis.

Tokenurile se verifică/exportă cu `@google/design.md@0.4.0`:

```sh
npm exec --yes --package=@google/design.md@0.4.0 -- designmd lint DESIGN.md
npm exec --yes --package=@google/design.md@0.4.0 -- designmd export --format dtcg DESIGN.md
```

Exportul DTCG versionat este `documents/Omnis_Design.tokens.json`. Pachetul prototipului HTML + `documents/assets/` este offline, cu `connect-src 'none'` și `form-action 'none'`; datele sunt DEMO. Geist/Geist Mono sunt vendorizate în CSS ca fonturi data-URI, cu OFL și checksums în `assets/`; nu există cereri către font CDN la afișare. Browser verification a documentelor/prototipului nu este un test al viitoarei aplicații.
