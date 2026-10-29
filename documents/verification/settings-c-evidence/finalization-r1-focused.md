# R1 — re-review focalizat al remediilor Settings

**Verdict: APPROVED_SOURCE_SCOPED_COMPOSED.** R1-F01 și R1-F02 sunt închise pentru SOURCE pe snapshotul exact de mai jos; nicio constatare concretă nouă în delta/callerii afectați. Se compune cu scope-ul neschimbat al reviewului R1 original, nu cu un audit global și nu cu QA/runtime/acceptare estetică. Integrarea și închiderea porților aparțin părintelui.

## Snapshot și scope

- Bază a remediilor: `a488b2611b96fbb6edc4d4c4bbd0c2de21a45b90`; produs reviewuit: **`ca33c1a86b5cf34a054dc837965f0957b458a1f6`**. Delta de produs este numai `97350b5` + `ca33c1a`; `d40067c` păstrează rapoarte/metadata.
- Blobs verificabile atât în commit, cât și în checkout:
  - `web/src/features/engagement/SettingsModelsPage.tsx`: `c77504541d76e5c43344d624b7bcae55f726156c`.
  - `web/src/features/engagement/SettingsModelWizard.tsx`: `d6a0cfc882dea2994129820bdb020b17f9e9e1c8`.
  - `web/src/app/SettingsWizard.test.tsx`: `f393432c215df63dde1ea7f8c6faea7034e04255`.
- Checkoutul a avansat în timpul reviewului la `fdcdf8f15244f125057072a3b6f6a49397db4aa0`: `git diff ca33c1a..HEAD` arată exclusiv adăugarea documentară `finalization-controls-review.json`; sursa/callerii/fixture-urile testate sunt neschimbate. Documentul nou nu este obiectul acestui verdict.
- Citite diff-ul real, componentele și unicul caller al wizardului, `ProviderSettings`/scope-ul sesiunii, fixture-ul existent, clientul/decoderele reale și testele afectate. Mandat §3.A/C, arhitectură §5:231 și UI/UX:161–165 sunt criteriile, nu un total de teste.
- Originalul `documents/verification/settings-c-evidence/finalization-r1-original.md` rămâne **CHANGES_REQUESTED la a488b26**, nemodificat: blob `ba152af661673e30e8814da81e1dcb76dc32cf4c`, SHA256 `c6c00771a3d1963b8fdcf9a18b9229268e8d39f3908b26c348d8be5062b2791e`. Nu rescriu concluziile/probele istorice și nu extind scope-ul lui.

## Dispoziția fiecărui finding original

| Finding | Dispoziție pe ca33c1a | Cerință → cod → dovadă |
|---|---|---|
| **R1-F01 MEDIUM** — FINISHED/UNKNOWN blochează Test nou | **CLOSED_SOURCE_SCOPED** | `SettingsModelsPage.tsx:94–106` separă terminalul local de rezultatul remote: UNKNOWN nu mai ține singur operația activă și nu mai este selectat înaintea unei operații nonterminale. `:359–388` păstrează Unconfirmed/UNKNOWN și citirea receive-only în afara detaliilor închise; `:329–333` păstrează recuperarea unui rezultat orfan. Reproducerul original F01 și controalele COMPLETED/NEEDS trec. Regresiile permanente FINISHED/NEEDS, fresh-unknown-first/remembered-unknown/remembered-completed verifică acord nou nebifat, un singur Start cu ID nou după consimțământ și Read/Cancel către operația B reală, nu istoricul A. |
| **R1-F02 MEDIUM** — progresul catalogului anterior maschează eroarea listei curente | **CLOSED_SOURCE_SCOPED** | `SettingsModelsPage.tsx:30,38,82–83,142–145,337–349,393–420` și `SettingsModelWizard.tsx:16–18,44–52,67–94,118–126`: providerul și conexiunea pinned sunt deținute împreună în ownerul existent; feedbackul/notificarea și suprimarea cer **ID + revision**, nu providerul inițial. La A/PENDING → B/FAILED, eroarea B/SCHEMA_UNSUPPORTED rămâne lângă lista B și inspectabilă; recuperarea A rămâne distinctă pe cardul A, cu explicație și Read/Cancel. Reproducerul original trece după compatibilizarea strict diagnostică descrisă mai jos; regresiile permanente verifică și revizia veche, cauza CONNECTION_STALE separată de METADATA_UNAVAILABLE curent, păstrarea selecțiilor și lipsa unui refresh suplimentar. |

**Controale de siguranță păstrate:** `operationPending` încă include lipsa readbackului, lifecycle nonterminal, `testUnknown` și eroarea queryului; pending Start nu devine terminal prin acest fix. NEEDS_RECONCILIATION păstrează blocarea și Cancel. `startTest`/consimțământul/generația și secvența existentă nu sunt relaxate; UNKNOWN/erorile opresc modelele netrimise și reload/late success nu reiau secvența. `refresh()` încă refuză un refresh cât `catalogOperation` există; `catalogRead()` cere aceeași operație/conexiune/revizie. Pinii stale, placeholderul limitat la aceeași identitate, receipt readback și wipe/unmount rămân în callerii existenți. Fără schimbare de API/backend/contract, owner paralel sau efect implicit nou.

## Probe executate independent

Toate sunt **SOURCE/jsdom + HTTP doubles**, prin App/componente/decodere autentice și fixture-ul existent, nu API/PG/provider QA. Node verificat: `v24.21.0`; Vitest `4.1.12`. Director comun al noilor artefacte: `/home/kali/.hermes/cache/scratch/settings-review1-ca33c1a/`.

### 1. Rularea originală nemodificată

```sh
NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run --config /home/kali/.hermes/cache/scratch/settings-review1-a488b26/vitest.config.ts --reporter=verbose
```

**Exit 1, 3 PASS / 1 FAIL, 4.46s**, păstrat în `original-rerun.log`. F01 și ambele controale sunt PASS. F02 se oprește exclusiv în `review1.test.tsx:96`, înaintea aserțiunilor finale: `console.log` folosește `getByRole` pentru recuperarea veche în wizardul B. Fixul mută corect acea recuperare în cardul A; prezența ei în wizardul B nu este criteriu de produs, ci presupunerea diagnostică a reproducerului vechi. Acest FAIL rămâne consemnat, nu este declarat PASS original.

### 2. Aceleași patru scenarii și aserțiuni, diagnostic compatibil

Copie scratch a testului original; **o singură linie schimbată, numai în console.log**: `getByRole(...).textContent` → `queryByRole(...)?.textContent`. Niciun `expect`, scenariu, fixture ori cod de produs schimbat. Verificare programatică: exact o linie diferită (96), toate liniile cu `expect(` identice. Originalul rămâne intact, SHA256 `580b4545aebbb2f7514b8ca7280f9fa5a22c183dffacadf8b85b96693b615b23`; copia are `d5963034e3754ec567f2c20c481fdc0b9cdb11961bd895ef99805174b16e59a8`.

```sh
NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run --config /home/kali/.hermes/cache/scratch/settings-review1-ca33c1a/vitest.config.mts --reporter=verbose
```

**Exit 0, 4 PASS, 2.88s**, `repro-diagnostic-compatible.log`. F01: `FINISHED/UNKNOWN`, Test și Read vizibile, Cancel absent. F02: provider curent OrcaRouter, read FAILED/SCHEMA_UNSUPPORTED, mesajul real al listei este `Models could not be loaded. Refresh the list or enter an exact model ID.`; cauza rămâne în detaliile catalogului. Niciun model call real.

### 3. Regresii permanente focalizate, nemodificate

Din `/home/kali/OmnisAI/web`:

```sh
NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run src/app/SettingsWizard.test.tsx src/app/ProviderKeySettings.test.tsx --reporter=verbose -t 'recovers the actual active check|remote UNKNOWN with local|expands history without replacing|UNKNOWN entry admission|manual read uncertainty|ends the unsent sequence|current OrcaRouter catalog failure|earlier connection revision recovery|provider switch confirmation|StrictMode effect replay|catalog lost reply|keeps catalog readback|explicitly updates a stale saved identity|cancel before an in-flight key save'
```

**Exit 0, 34 PASS / 70 nealese prin filtru, 31.54s**, `permanent-focused.log`. Acoperă exact ambele fixuri, active Read/Cancel, pending admission, read uncertainty, secvență fără autoresume, switch refuzat/selecții, revizii vechi, recuperare catalog fără resend și callerul async de key-save/unmount. Totalul 34 și cele 70 nealese au fost numărate programatic din output, concordante cu rezumatul Vitest.

```sh
NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run src/app/SettingsWizard.test.tsx --reporter=verbose -t 'preserves receive-only recovery for an orphan'
```

**Exit 0, 2 PASS / 81 nealese prin filtru, 2.51s**, `orphan-focused.log`: RUNNING și FINISHED/UNKNOWN orfane rămân vizibile/receive-only; terminalul UNKNOWN nu oferă Cancel fictiv.

## Integritate și predare

- `git diff --check` exit0; tracked/index curate la început și la final, blobs de produs identice cu ca33c1a. Nicio editare/commit/push făcută de reviewer în repo.
- Fișiere create numai în scratch: acest raport, configul de probă, copia testului cu diagnostic compatibil, trei loguri de test focalizate plus logul rulării originale; symlink către dependențele web existente și cache Vitest. Nicio dependență nouă, framework ori test permanent schimbat.
- Nu rerulez full suite/lint/types/canonical deja raportate de părinte; ele nu sunt probe executate de acest reviewer și nici motivul închiderii celor două findings. Reviewul R2 este separat, neadjudecat aici.
- Propunere către părinte: închide **numai R1-F01/R1-F02 SOURCE** pe manifestul de mai sus; păstrează originalele și FAIL-ul diagnostic; compune această aprobare cu reviewul R1 neschimbat și cu reviewul complementar necesar. QA pe consumerul real și acceptarea vizuală rămân porți distincte, neexecutate aici.

Neexecutat: build/web/dist, browser–API–PG/servicii, operator/credentiale/env/dumpuri, apeluri provider/model/țintă, estetică, canonical sau T2; cele două fișiere untracked protejate au rămas necitite/neatinse. Reticle **NOT_INTEGRATED**, Chisel **BLOCKED_NO_GO**.
Risc rămas: această aprobare SOURCE nu dovedește integrarea/runtime-ul ori remedierea cauzelor upstream/supervisor UNKNOWN; nu acordă acceptare în numele operatorului.
