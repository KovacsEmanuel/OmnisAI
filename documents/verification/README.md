# Verificări: baseline istoric și implementare locală

**Orientare globală:** [harta de implementare și review MVP/post-MVP](implementation-status.md) proiectează starea pe planul canonic și separă codul, probele și aprobarea de review. [Contractul/probele skillului de predare](project-status-skill.md) privesc procesul de dezvoltare, nu runtime-ul produsului.

**C11 same-Host actual:** [consumer/FAIL-uri și limite](p2-method-lost-reply.md), [receipt exact](p2-method-lost-reply-close.json); d7a51f3 integrat byte-exact/reviewedscoped, F01/N01 închise, final autentic recuperat fără redispatch și un caz nativ post-Stop PASS. Fulltarget FAIL302/303 păstrat/cauzaUNKNOWN; canonical NOT_RUN, B06b/P2 neînchise.

**Increment actual B06b:** [C04 CONTRACT/no-oracle](p2-c04-criteria.md), [receipt exact](p2-c04-complete-close.json), [prerechizită compactă](p2-assignment-compact.md) și [metodă/istoric receive-only](p2-contract-method.md). `77c835d` este integrat byte-exact/reviewed scoped: două perechi de criteriu native și două outcomes BLOCKED+reason persistente,121SOURCE/4PG-native/19SOURCE-integration exit0 și cleanup propriu. Nu oracle pozitiv ori închidere B06b/P2; canonical post-fix NOT_RUN și FAIL-uri păstrate.

**Ultima acceptare C03 records:** [registru](p2-b06b-c03-records.md), [CLOSE](p2-b06b-c03-records-close.json), [arhivă](p2-b06b-c03-records-evidence/README.md). Produs20611d1 și teste/canonical c0261a7: input structurat persistent/calificare/Publish/binding/consum nativ inert, reviewuri complementare, QA installed/history/browser și make check neredus exit0/drained. Browser59IDs reconciliate47PASS/8excluderi/4NOT_IMPLEMENTED,63imagini inspectate. FAIL-urile și limitele rămân; nu B06b/G02/faza2 închise. Paragrafele de pregătire de mai jos sunt istorice.

**Pregătire SL09/B06b după B06a CLOSED_SCOPED_STATIC_PURE:** [contractul bounded](p2-b06b-next-contract.md) mapează C01–C12 la producători/consumatori/probe și separă H03–H08 core de B06c/B06m/P4a/P2-live. [Analiza/checkpointul](p2-b06b-preparation-analysis.json) păstrează reviewul inițial CHANGES_REQUESTED, remedierile documentare RED→GREEN, obligațiile viitoare și riscul fingerprintului. [Promptul copy-ready](p2-b06b-implementation-prompt.md) este neexecutat; nu autorizează Publish/Task/copil/model sau restart/adopție r1 în sesiunea de pregătire. SL09 rămâne NOT_IMPLEMENTED/NOT_RUN/NOT_REVIEWED pe axele produsului.

**Predare P1 pentru operator:** [instalare persistentă r1, utilizare și rollback](p1-installed-delivery.md), [receipt final](p1-installed-gate.json), [QA live](p1-installed-live.json) și reviewurile [normativ](p1-installed-normative-review.json)/[binding](p1-installed-binding-review.json). CLOSED_SCOPED local pe `c82a8d4`: două aprobări scoped,29PASS/35capturi și gate canonic final exit0/drained; `omnis` durabil, Dashboard/drafturi/Stop/restart reale, assessment=false. [Restul B05/P2](p2-b05.md) rămâne separat și neînchis; fără rollout P0, inference sau ținte.

**Completarea B05 stock slot/bootstrap:** [contract și rezultat](p2-b05-slot-inventory.md), [receipt final](p2-b05-slot-gate.json), [re-review fix nativ](p2-b05-slot-native-review.json) și [review documente](p2-b05-slot-evidence-review.json). CLOSED_SCOPED numai acest perimetru E-B05-03 pe `dfc549a`: QA instalată nominală A1→B1→A2 exit0/SessionDB nativă și inventar same-native, `make check` exit0/drained, cleanup17 CIDs proprii/date păstrate. QA suplimentară rămâne NOT_PASS_PROTOCOL_DEVIATION, nu execuție contractual PASS; observațiile sale sunt păstrate delimitat cu FAIL. B05/G02/P2 neînchise, B06 neînceput. La readback după reboot,13 foreign sunt oprite/neschimbate și r1 nu este revendicat READY live; acceptarea P1 de mai sus rămâne istorică.

`stack-probe.json` păstrează output real și limitele probelor de dependențe din 25 septembrie 2026. `stack-probe-inputs/` conține inputurile și lockurile reproducerii; nu este scaffoldul aplicației și nu pornește Hermes sau o scanare. Nu se copiază aceste probe ca implementare de domeniu.

**Implementare locală actuală:** [P0.1](p01-local-readiness.md) · [P0.2](p02-local-control.md) · [calitate Python](p02-python-quality.md) · [P0.3 bootstrap/pairing](p03-local-bootstrap.md), cu [rezultate browser](p03-browser.json) și capturi în `p03-ui/` · [P0.4 topologie host-only parțială](p04-host-uds.md) · [fixture PostgreSQL fără publicație Docker](p04-safe-test-db.md) · [adjudecarea buclei P0.4 și calea critică](p04-loop-adjudication.md). [SL02 — comanda instalată start headless](p04-installed-start.md) și [SL03 — pair/open/implicit pe CLI instalat](p04-pair-open.md) consemnează distinct probele comenzilor, nu ale harnessului. Aceste dovezi sunt separate de probele istorice de mai jos. G00 local este închis numai prin [adjudecarea probelor instalate](p04-stop-recovery.md), nu prin existența acestor rapoarte; CI remote este separat pentru distribuire.

## Amendamente autorizate, incorporate în canon

[Auditul de completitudine SL02](p04-start-completeness-review.md) păstrează istoricul SC01/SC02, ulterior remediate în [registrul lor](p04-start-remediation.md). [Remedierea aprofundată actuală](p04-deep-remediation.md) consemnează și RT-F01/RT-F02/AR01/AR02/AR03/RT-PG01/RT-M01, reviewurile adjudecate și perechea canonică finală exit0/exit0 pe c914fda: REMEDIATION_PASS / READY_FOR_SL03: YES numai pentru dezvoltarea următoarei felii. [Auditul remediilor SL02](p04-deep-remediation-matrix.json) păstrează 19 COVERED scoped/3 PARTIAL/4 DEFERRED la revizia **SL02**; nu atestă G00/CI remote/ALL_CLEAN sau SL03/SL04 prin acel gate istoric. Acceptarea scoped ulterioară a SL03 este în [registrul separat](p04-pair-open.md).

[Promptul de remediere SC01/SC02](p04-start-remediation-prompt.md) și [promptul aprofundat](p04-deep-remediation-prompt.md) sunt handoffuri istorice: scope, regresii, review și gate-uri separate. Existența lor nu închide defectele; execuțiile și dispozițiile curente sunt în registrele de mai sus, iar statusul pentru operator se afișează direct în chat.

**Criteriul activ pentru P0 pe această VM:** [arhitectura §4.5](../Omnis_MVP_Architecture.md) și [planul §5](../Omnis_Implementation_Plan.md) cer comenzi instalate reale Start/Stop/Start explicit, date păstrate, refuzul resurselor străine, control local și `UNCERTAIN` conservator. [Harta curentă](implementation-status.md) păstrează verdictul. Vechiul inventar numerotat de faulturi și mandatul de a-l executa integral au fost scoase din arborele activ prin decizia operatorului; ele rămân în istoria Git numai ca proveniență, **nu** criterii de implementare sau review. [Registrul SL04](p04-stop-recovery.md), [M22](p00-m22-config.md) și [SL03](p04-pair-open.md) păstrează rezultate și FAIL-uri istorice, fără a transforma etichetele lor vechi în porți noi. CI remote și izolarea altui host/UID sunt distincte pentru distribuire/portare, nu blocaje pentru folosirea locală inertă.

[Promptul de execuție P1](p1-implementation-prompt.md) împarte B02→B03/B04→G01 în felii verticale și citează sursele canonice; promptul în sine nu este dovadă de implementare sau verdict CI. [P1-data](p1-data.md) închide B02 numai pentru draftul inert local. [P1-web](p1-web.md) păstrează B03 închis local scoped pe `d66b3db`, cu [re-review A02](p1-web-a02-review.json), [gate-ul B03](p1-web-a02-gate.json) și [browserul B03](p1-web-a02-browser.json), iar [receiptul B04/G01](p1-web-b04-gate.json) închide local/scoped wizardul inert pe `ddb42d2` după `make check` exit0/drained și QA live separată pe browser/API/PostgreSQL proprii. [Reviewul](p1-web-review.json), [gate-ul](p1-web-gate.json) și [browserul](p1-web-browser.json) pe `b9fde3d` rămân istorice. [NSS V2 și instalarea reală](p1-web-a02-dns-v2.json) păstrează separat prerechizitul și [reviewul helperului](p1-web-a02-dns-review-v2.json), fără bypass sau schimbarea hostului. Nu se promovează runuri, CI remote, model/țintă sau rollout peste P0; editul cu run activ așteaptă B06.

[Amendamentul skill-uri/copii din notițele originale](omnis-skill-pattern-amendment.md) păstrează sursa, cele 19 decizii de adaptare și limitele native; contractele și ordinea se introduc în același canon.

[Deep review-ul de flux și livrare](omnis-deep-review.md) urmărește dependențele implicite și scenariile cap-coadă după HF01–HF10; verdictul și remediile sunt separate de gate-urile runtime.

[Verificarea amendamentului HF01–HF10](omnis-amendment-verification.md) consemnează codul documentar schimbat, review-urile, comenzile reale PASS/FAIL/BLOCKED/NOT-RUN și WIP-ul păstrat; nu este un nou plan.

HF01–HF10 sunt în [arhitectură](../Omnis_MVP_Architecture.md), [plan §17](../Omnis_Implementation_Plan.md), [UI/UX](../Omnis_UI_UX_Spec.md) și [stack §10](../Omnis_Stack_Baseline.md). Un singur baseline, nu încă un plan alternativ. Contractele viitoare sunt **SPECIFICATE / RUNTIME NOT-RUN**; P0 local a fost adjudecat separat pe artefact instalat, nu de acest amendament documentar.

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
