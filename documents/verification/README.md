# Verificări: baseline istoric și implementare locală

`stack-probe.json` păstrează output real și limitele probelor de dependențe din 25 septembrie 2026. `stack-probe-inputs/` conține inputurile și lockurile reproducerii; nu este scaffoldul aplicației și nu pornește Hermes sau o scanare. Nu se copiază aceste probe ca implementare de domeniu.

**Implementare locală actuală:** [P0.1](p01-local-readiness.md) · [P0.2](p02-local-control.md) · [calitate Python](p02-python-quality.md) · [P0.3 bootstrap/pairing](p03-local-bootstrap.md), cu [rezultate browser](p03-browser.json) și capturi în `p03-ui/` · [P0.4 topologie host-only parțială](p04-host-uds.md) · [fixture PostgreSQL fără publicație Docker](p04-safe-test-db.md) · [adjudecarea buclei P0.4 și calea critică](p04-loop-adjudication.md). Aceste dovezi sunt separate de probele istorice de mai jos. G00/P0.4 și CI remote nu sunt închise implicit de existența unui raport.

## Amendamente autorizate, incorporate în canon

[Amendamentul skill-uri/copii din notițele originale](omnis-skill-pattern-amendment.md) păstrează sursa, cele 19 decizii de adaptare și limitele native; contractele și ordinea se introduc în același canon.

[Deep review-ul de flux și livrare](omnis-deep-review.md) urmărește dependențele implicite și scenariile cap-coadă după HF01–HF10; verdictul și remediile sunt separate de gate-urile runtime.

[Verificarea amendamentului HF01–HF10](omnis-amendment-verification.md) consemnează codul documentar schimbat, review-urile, comenzile reale PASS/FAIL/BLOCKED/NOT-RUN și WIP-ul păstrat; nu este un nou plan.

HF01–HF10 sunt în [arhitectură](../Omnis_MVP_Architecture.md), [plan §17](../Omnis_Implementation_Plan.md), [UI/UX](../Omnis_UI_UX_Spec.md) și [stack §10](../Omnis_Stack_Baseline.md). Un singur baseline, nu încă un plan alternativ. Contractele noi sunt **SPECIFICATE / RUNTIME NOT-RUN**; P0.4/G00 rămân deschise și WIP-ul DB nu este integrat prin documentare.

Surse și rațiuni **istorice, adjudecate**:
- [Dosarul Sol](omnis-pentest-review-proposal.md), cu recomandări înlocuite explicit în plan §17.
- [Review OSS/Strix](omnis-upgrade-review.md) și [inventarul pinurilor/75 ghiduri + README](omnis-upgrade-review.inventory.json).
- [Suplimentul modular](omnis-modularity-research-supplement.md), inclusiv §12 walkthrough de referință, și [manifestul 34 unități / 98 referințe source-test](omnis-modularity-research-supplement.reuse.json).
- [Handofful final](omnis-final-amendment-handoff.md), sursa HF01–HF10; aprobarea amendării nu mai este pending. Niciunul dintre dosare nu certifică runtime/eficacitate sau importul deja activ al componentelor.

Starea curentă a codului și matricea PĂSTRĂM / CORECTĂM ACUM / EXTINDEM sunt în plan §19.1–19.2. [Integrarea DB autorizată](p04-test-db-integration.md) înlocuiește ulterior blockerul fixture/conftest/CI: un singur runner UDS pentru make check/test, cu atestare și cleanup propriu. Rezultatele sunt separate de G00 și CI remote; nu reluăm harnessul owner ca substitut al launcherului.

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

[Recontrolul pinurilor înainte de implementare](preimplementation-pins.json) conține 33 răspunsuri de metadate exacte, cu URL/versiune/timestamp și limitele explicite ale probei. Verifică publicarea pinurilor, nu compatibilitatea unui nou lock, întregul lanț de dependențe sau funcționarea aplicației. Proxyul respins nu a fost pornit sau reaprobat prin această verificare.

[Auditul final înainte de implementare](preimplementation-check.json) păstrează outputul real `make check`, rezultatul browserului, verificarea DAG-ului și lipsa modificărilor în prototipul acceptat/AGENTS.md. Plan §19 este handofful P0.1, iar registrul PA01–PA09 separă remedierea în specificație de gates neexecutate. Scrierea protejată a statusului AGENTS a rămas blocată de aprobarea expirată; nu a fost ocolită sau raportată ca reușită.

[Verificarea locală P0.1](p01-local-readiness.md) consemnează separat API-ul instalabil, migrarea din wheel pe PostgreSQL real, controalele negative, review-urile și limitele. Nu rescrie probele preimplementare și nu declară G00 sau CI remote trecute.

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

Stop/focus/dialog/drawer, scope-ul global/contextual, new/setup, filtrele, stările empty/error/stale și controalele demo pliate rămân acoperite. Capturi desktop/mobil și dropdownul de review au fost inspectate real. Testul CSS zoom 200% nu înlocuiește verificarea zoomului nativ; screen-readerul și alte browsere rămân neverificate. **Probele nu constituie integrare backend sau aprobare vizuală.** Acceptarea vizuală a fost dată ulterior explicit de utilizator pentru `df17a29`; pornirea implementării rămâne separată, în sesiunea nouă, conform planului.

Tokenurile se verifică/exportă cu `@google/design.md@0.4.0`:

```sh
npm exec --yes --package=@google/design.md@0.4.0 -- designmd lint DESIGN.md
npm exec --yes --package=@google/design.md@0.4.0 -- designmd export --format dtcg DESIGN.md
```

Exportul DTCG versionat este `documents/Omnis_Design.tokens.json`. Pachetul prototipului HTML + `documents/assets/` este offline, cu `connect-src 'none'` și `form-action 'none'`; datele sunt DEMO. Geist/Geist Mono sunt vendorizate în CSS ca fonturi data-URI, cu OFL și checksums în `assets/`; nu există cereri către font CDN la afișare. Browser verification a documentelor/prototipului nu este un test al viitoarei aplicații.
