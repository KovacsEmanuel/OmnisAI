# Review independent final focalizat — 0c8bff

## Verdict și admitere

**APPROVED_FOCUSED_SOURCE_SCOPED. Findings concrete noi: niciunul în delta inspectată.** Recomand admiterea **unei singure probe fresh bounded prin consumerul existent `test-settings-remove-ui-pg`, timeout600s**, după preflightul fără efecte și admiterea resurselor de către părinte. Nu cer ca aceeași probă să fi trecut deja pentru a o admite. Nu am lansat-o.

Reviewul compune aprobările R1/R2 anterioare și re-reviewul `a4f5dbc` pentru bytes/comportamente neschimbate cu aprobarea de față pentru delta `a4f5dbc..0c8bff`. Nu este PASS API/PG, acceptare whole-product/all-states, integrare, instalare ori aprobare estetică.

## Identitate, scope și verificare efectivă

- Worktree: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`.
- Bază: `a4f5dbc67221e3c0387a88db7bb8e78de4c6ccfa`.
- HEAD: `0c8bff7676b0f0be23b27b77da63ff57ee08cdf0`; tree: `ad622788df6daec982497f3a489d846c7c877eb5`.
- Freeze: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-identities-20261030/freeze-supplement.json`; SHA256 `3e02bd774e13304d8eca89272ce43325cb9b1432f9a794e53410049dfa65f346`.
- Diff complet citit: șase fișiere,255 inserări/6 ștergeri: trei fișiere component-test, două mjs și **o singură linie produs**, `SettingsModelsPage.tsx:136`.
- Scope reach: callerii reali de picker/cap/navigation/disclosure/recovery din teste, fixture-ul comun `settingsBackend`, SOURCE built-App/capture și cei doi selectori Provider din consumerul API/PG; efectul existent de notification placement/focus/expiry. Fără API/schema/config/dependency/export/dispatch/CAS delta.
- Verificat direct Git/hashlib: toate11 blobs/SHA sursă și toate5 fișiere build corespund freeze; HEAD/tree conforme; `git diff --check a4f5dbc..0c8bff` exit0. Tracked/index curate; cele patru symlinkuri de dependențe preexistente nu au fost adoptate/modificate. Main `6a98002152cfe830a48649e99f146cf93b531be3` neatins; fișierele protejate nu au fost citite/hash-uite.
- Citite contractul actual `web/design/settings-final.md` §Settings refinement/assignments, CURRENT, regulile de admitere și team-slice; numai ORIENT/read-only.

## Dispoziții

| Subiect | Dispoziție și motiv |
|---|---|
| Coverage test-only | **APPROVED_SOURCE_SCOPED.** Cele10 cazuri noi folosesc App/fixture/calleri existenți: patru roluri editează separat picker+cap, verifică payload/readback/remount și peers; override-urile revin explicit la Use default. Două navigări keyboard verifică destinație/retur, aria-current, ștergerea secretului nesalvat și zero scrieri. Refresh pozitiv, Cancel catalog, orphan RUNNING Cancel și Stop fără proiecție locală au acțiuni/aserțiuni reale la nivel SOURCE, nu numărătoare de cod. Ultimul este etichetat corect fault React/Query sintetic, nu fapt server. Dismiss, disclosure open/close și Previous offset0 completează teste existente. Nu cer58 controale native sau toate combinațiile stărilor. |
| QA-A4F5DBC-01 — Provider exact | **OBSERVER_SELECTOR_CORRECTED; admisibil fresh.** `settings-models.mjs:173,178` folosește combobox/name exact în ambele locuri, fără timeout/action/count relaxation. SOURCE built-App după Back demonstrează exactLabel0/exactRole1 și provider openrouter; selectarea altui provider urmată de Cancel/Enter și Escape păstrează Saved key și selecția New/Model. Aceasta verifică remediul callerului; nu inventează DOM-ul lipsă al eșecului istoric și nu atribuie un defect Back produsului. FAIL-ul55.01s și prefixul Remove/recovery17 rămân originale. |
| SOURCE observability | **APPROVED_FOCUSED.** Rulează Vite preview pe buildul real, requesturile sunt synthetic HTTP și externul e blocat. Captura înainte de focus face blur înaintea resize, apoi scroll0/paint, verifică vizibilitate/viewport și bounding boxes reale ale țintelor; abia după aceasta focalizează Dismiss. Nu folosește fullPage pentru a pretinde vizibilitate în viewport. Count9 protejează inventarul concret de headings/identități/stări; captura320 a fost inspectată separat prin vision. `locator('small').getByText(...)` elimină ambiguitatea reală strong/small fără să schimbe identitatea cerută. |
| Toast — ocluzie label/hint și identity | **CLOSED_APPROVED_FOCUSED pe linia136.** Selectorul include acum label/hint,h1–h3,identity,state,saved și connectionHeading small; exclude în continuare propria notificare și boxurile fără suprafață. Algoritmul finit existent rămâne limitat de numărul țintelor și mută numai în sus; vizibilitatea și expirarea sunt condiționate de poziție sigură. Nu schimbă confirmările eligibile, mesajele de succes, saved states ori efectele. Cele nouă cazuri component verifică elemente/clase reale după blur; native verifică geometria actuală la1440/1280/390/320. În captura320 finală notificarea este lângă Models, fără ocluzie observată a provider/model/status/label/hint/controalelor vizibile. |
| Focus/expiry și R2-01/R2-02 | **CLOSED_SCOPED păstrat.** Delta nu modifică guardul pending pentru Connecting, early-return când notificarea conține focusul, timerul de timp vizibil, cleanup/disposed ori microtask focusout. Nu ascunde/repoziționează notificarea focalizată și nu fură focus. Reutilizat re-reviewul independent `settings-inline-feedback-r2fix-independent-a4f5dbc.md`; nu redeschis authority/CAS/effect guards neschimbate. |
| Save & connect pending capture | **ADMISSIBLE_QA / NOT_RUN aici.** Unica adăugare la captura consumerului real este `row('fixture/01').scrollIntoViewIfNeeded()` plus `toBeInViewport({ratio:1})` înaintea screenshotului existent, fără schimbarea Start/Stop/consent/oracle-urilor. Captura SOURCE320 scroll0 nu certifică Save: selectorul este parțial tăiat la marginea viewportului și Save nu apare; limită declarată, nu pretins PASS. |

## Dovezi existente citite, nu rerulate

- Freeze/loguri finale: component **172 PASS/3 fișiere**,28.54s; RED comportamental pentru cele șapte identități noi **7 FAIL/2 PASS**, apoi GREEN. Cele două cazuri label/hint provin din suplimentul anterior; nu confund RED fixture-ambiguity cu RED de produs.
- `native.log` original final: retained/moved/stale/long64 PASS,10.101346408s/cap90; Node raportează5 teste incluzând părintele, nu cinci scenarii independente. Logul înregistrează exactRole1/exactLabel0 și clearance true pentru cele patru viewporturi, cu nouă identități reale fiecare.
- Loguri finale lint/typecheck/build citite; exit0 în freeze. Build nou Vite8.3.5/index-Cz2ykhnr.js verificat prin SHA; nu am reconstruit. Sintaxa mjs exit0 este probă frozen, nu comandă rerulată de mine.
- Suplimentul SOURCE `.../settings-inline-feedback-source-supplement-20261030/freeze-supplement.json` mapează C03,C13,C23,C25,C27,C28,C31/C48,C36,C39,C53/C55 și N1/N2/N3; am comparat cu definițiile efective, nu am promovat inventarul55situri+3navigări în live coverage.
- `.../settings-inline-feedback-qa-a4f5dbc-20261030/result.json` citit: eșecul și secțiunile NOT_REACHED rămân valabile; SOURCE nou nu transformă acel run în PASS.

## Frontiera următoarei probe și limite

Comanda deja existentă, din worktree-ul candidat:

```sh
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-remove-ui-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600
```

Admiterea rămâne pe fixture fresh proprie, PG/API/browser reale și peer TLS sintetic local, cu deadline/cleanup/readback ale runnerului existent. Nu modifică oracolele finale8GET/2POST noi sintetice,64IDs fixture,12mutations/19entries/connectionRev3, census13tabele/restart; **aceste rezultate sunt de obținut, nu verificate de acest review**. Nu autorizează trafic provider/model real, operator, Refresh upstream, canonical ori legacy `settings_ui`. Counter2 EXHAUSTED și cele două cicluri observer SOURCE deja consumate se păstrează, fără reset sau alt loop. Lipsa PASS fresh rămâne NOT_RUN, nu blocker circular de cod pentru proba admisă.

Creat numai acest raport original în scratch. Niciun cod/test/fișier repo/skill modificat, niciun commit/install/API/PG/browser/Docker/runtime effect. Reticle NOT_INTEGRATED/neexecutat; Chisel BLOCKED_NO_GO. Integrarea și acceptarea finală aparțin părintelui.

Am omis auditul și toate rerunurile; nu am certificat toate stările/combinările, screen readers/cross-browser sau estetica.
Risc rămas: consumerul real API/PG și captura Save & connect pending trebuie încă să treacă pe bytes finali; aprobarea de aici nu închide T1.
