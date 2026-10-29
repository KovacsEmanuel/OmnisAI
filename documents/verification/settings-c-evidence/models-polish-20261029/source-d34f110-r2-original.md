# R2 — review independent read-only, Settings Models

## Verdict

**CHANGES_REQUESTED_SOURCE_SCOPED pe d34f11066a93c15ce65ce4a8879986e63e025dbd.** Nu recomand lansarea QA de acceptare pe acest freeze înaintea adjudecării/remedierii celor două findings SOURCE de mai jos. Nu am identificat un nou blocker de auth/epoch, spend, secret sau izolare a fixture-ului în delta inspectată. Lipsa QA runtime nu este ea însăși un blocker circular: după fixuri, affected checks și freeze/re-review focalizat, consumerul bounded existent este calea potrivită.

Reviewul nu aprobă integrarea, instalarea sau estetica. Părintele reproduce/adjudecă findings și admite separat efectele.

## Identitate și limite

- Worktree: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`.
- Base: `83cade3fa662d38ecfd95f40c154e32acec70c05`.
- HEAD: `d34f11066a93c15ce65ce4a8879986e63e025dbd`; tree: `70b003495a25fb7dee9dd99d9f2eb22fbabde3f9`.
- Freeze citit: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-freeze-20261029.json`.
- Verificare independentă SHA256 pentru toate cele 11 fișiere schimbate + manifestul build + cele 4 assets: 16 identități verificate, exit0. HEAD/tree conforme. Patru symlinkuri de dependențe preexistente neadoptate/nemodificate.
- Canon citit cu `git show 2ea1ad8a511ce181a01d869854e94dae9672e50e:web/design/settings-final.md`, inclusiv Settings refinement/lifecycle/Remove; citite CURRENT, CONTRIBUTING, team-slice și contractele/callerii afectați.
- Nu am scris cod/teste/config în repository, nu am comis și nu am pornit API/browser/Docker/PG/provider/operator. Numai două reproduceri mici React/JSDOM cu HTTP synthetic, din scratch; fără rerularea celor 149 teste sau a vechiului settings_ui.

## Findings confirmate

### R2-01 — MEDIUM, regresie de stare: un Save local prezintă istoricul ca Connecting

- **Loc:** `web/src/features/engagement/SettingsModelsPage.tsx:418`, consumat la `:432`; `sending` este comun tuturor mutațiilor (`:185-208`), nu exclusiv admiterii unui model test.
- **Reproducer:** re-entry cu ultimul operation ID păstrat în storage și cu rezultat exact FINISHED/COMPLETED (Connected); Save assignments; ține GET-ul receiptului provider în așteptare. Singurul write este `save_selection`, fără model Start, dar rândul modelului devine `Connecting` pe durata Save-ului.
- **Probă reală SOURCE:** testul `R2-01` din scratch a ajuns la pending receipt, a verificat writes exact `['save_selection']`, apoi a observat `Exact modelExact/ModelConnectingTest...`. Assertul că nu trebuie afișat Connecting a eșuat.
- **Criteriu încălcat:** progresul de conexiune aparține checkului real și contextului său; modificarea locală normală nu creează progres de model fictiv și nu suprascrie starea persisted a unui model deja conectat.
- **Remediu minim:** limitează `starting` la admiterea efectiv pending a aceleiași operații, nu orice `sending` (de exemplu și bariera `operationPending`, verificată cu cazul de mai sus); păstrează Connected pe Save assignments/alte scrieri locale. Adaugă regresia mică în suita deținută.

### R2-02 — MEDIUM, focus/a11y: expirarea scoate din DOM controlul care are focus

- **Loc:** `web/src/features/engagement/SettingsModelsPage.tsx:143`, cu listenerul `focusin` la `:145` și controlul Dismiss la `:385`.
- **Reproducer:** Reload -> notificare scurtă -> focus pe `Dismiss notification` -> așteaptă restul de 5s. `place()` repornește timerul inclusiv când focusul este în notificare; callbackul elimină întreg aside-ul și butonul focalizat.
- **Probă reală SOURCE:** `R2-02` a verificat focusul pe Dismiss înainte de expirare; după 5001ms a observat `{ "connected": false, "activeTag": "BODY" }`. Assertul păstrării focusului a eșuat.
- **Criteriu încălcat:** păstrarea focusului keyboard pe controalele Models/notificării; timerul pasiv nu trebuie să elimine controlul utilizat. Este comportament preexistent păstrat de timerul rescris, nu pretind că a fost introdus pentru prima dată în acest candidat; intră însă în scope-ul explicit actual notification/focus/timers.
- **Remediu minim:** suspendă expirarea cât timp notificarea conține `document.activeElement`, reia timpul rămas după ieșirea focusului; cleanup și timer unic. Nu forța focusul în notificare și nu expira erorile. Regresie mică pe focus-in -> timp -> focus-out -> expirare.

## Probe SOURCE executate

Fișiere exclusive scratch:

- `/home/kali/.hermes/cache/scratch/settings-r2-d34f110-probe-20261029/review.test.tsx`
- `/home/kali/.hermes/cache/scratch/settings-r2-d34f110-probe-20261029/vitest.config.mts`
- `/home/kali/.hermes/cache/scratch/settings-r2-d34f110-probe-20261029/source-probes.log`
- symlink scratch `node_modules` către dependențele existente ale worktree-ului; cache Vite numai în scratch.

Comandă (cwd worktree):

```sh
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node web/node_modules/vitest/vitest.mjs run --config /home/kali/.hermes/cache/scratch/settings-r2-d34f110-probe-20261029/vitest.config.mts
```

Rezultat: **exit1, 2 teste / 2 FAIL, 553ms test time**, ambele eșecuri la aserțiunile de produs descrise, nu la setup. Probe de diagnostic intenționat RED, nu gate complet și nu runtime/API/PG. Importă source-ul exact al candidatului și fixture-ul SOURCE existent, fără patch sau copie modificată a producției.

## Scope fără finding nou în lectura SOURCE

- **Auth/grant replacement:** `ProviderSettings.tsx:8-22` demontează vechiul lifetime înaintea noii legături CSRF/scope; `useBrowserSession.ts:113-125` verifică epoch/phase înainte și după await, fără retry. Nu există delta de API auth/protocol/schema/deps.
- **Generation/consent:** generation capturată în review/direct consent rămâne pin pe Start (`SettingsModelWizard.tsx:91,117-121`, `SettingsModelsPage.tsx:255,328-339`), nu este reînnoită după readback. Entry/connection/output/catalog și limitele existente rămân în payload/validare; schimbările de cap/model reset consent; simplificarea copy nu schimbă inputul fix sau capurile.
- **Remove:** pin pentru entry/registry/selection/connection/generation (`:102-108`), revalidare current/busy/active/UNKNOWN/in-use/expanded la send (`:354-360`), command ID și receipt recovery fără resend. In-flight Cancel nu este ascuns de noua confirmare. Restore pe Cancel/Escape verifică originea focusului; succesul folosește fallback condițional, nu furt de focus dacă operatorul a plecat.
- **Async/Cancel/UNKNOWN:** lifetime abort/continuation abort la unmount; StrictMode reinstalează controllerul. `readTest(true)` oprește întâi continuation și folosește operația activă/state revision, nu istoricul expandat; manual UNKNOWN oprește unsent, păstrează același ID; Stop remaining nu declară refund sau anularea remote. `connectEntries` cere rezultat exact și latest readback înainte de următorul Start, nu reia secvența la revenire.
- **Secrete:** DOM key wipe înainte de await, la provider change/locked/unmount și Cancel; key nu intră în storage, confirmare sau notificare. Inline Replace este numai confirmarea feature-ului existent; nu adaugă o comandă nouă.
- **a11y SOURCE:** butoane native/nume, Escape pe controale, ținte CSS min44 și wrapping păstrate; algoritmul evită coliziunile și numără timpul vizibil. R2-02 rămâne excepția confirmată. Nu am făcut măsurători geometrice reale/contrast sau certificare screen-reader.

## Fixture și admiterea viitoare a QA bounded

- `entry_remove_ui` singur primește allowlist model `{fixture/selected, fixture/01}`, cu `max_tokens==64` și provider fallback false/require_parameters true. Celelalte scenarii păstrează restricțiile lor.
- Oracle-ul cere secvența exactă nouă **8 GET + 2 POST**, modele/capuri în ordine, trei Start totale cu generation și ID-uri distincte; exact12 mutații în browser, inclusiv Remove1/save_models2/selection1/revoke1/save_connection1/Refresh4/Start2. Citirea/cancelarea locală nu cere POST Cancel remote în acest journey.
- Browserul are route allowlist numai originul loopback al fixture-ului; senderul este legat de TLS peer local prin relay/DNS/connect controls. Runnerul existent construiește env curat și fixture nou, nu acceptă ambient DB/proxy config; nu există delta de runner/effect boundary în candidat.
- Census-ul celor 13 tabele verifică delte exacte/păstrarea istoricului, Remove18->17/re-add nou ID18/add19, apoi snapshot egal după restart API real; secret markers/checks rămân pe consumer. Listele exacte resping extra calls în verdict; sunt aserțiuni postfactum, nu un limitator universal pre-send al fixture-ului. Efectele sunt sintetice locale, nu buget upstream.
- Preflight de runtime (binar browser/imagine PG/UID/mounturi/cleanup propriu) trebuie verificat de QA înainte de singura invocare admisă. Nu am executat această etapă.
- Comanda existentă rămâne potrivită **după fixuri/freeze/re-review/preflight**: `PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-remove-ui-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600`.
- Vechiul `settings_ui` cu două FAIL/counter2 nu se rerulează și nu se resetează. Missing real QA este NOT_RUN, nu finding de cod și nu pretext pentru gate nou.

## Acoperire și neexecutat

AST TypeScript pe source-ul exact a numărat **55 situri JSX interactive**: ModelsPage29, Wizard22, Assignments4, separat cele3 navigări existente. Sunt situri condiționale/repetate, nu55 controale simultane și nu dovadă de coverage. Inventarul vechi50+3 nu reprezintă freeze-ul curent.

Journey-ul bounded propus nu certifică toate stările: provider discard pozitiv, Cancel remote activ, catalog Cancel/UNKNOWN, generation refusal, orphan și rare failure rămân SOURCE-only/NOT_RUN pentru runtime dacă nu sunt admise separat. Cele149 component PASS declarate de autor nu sunt echivalente cu all-controls runtime PASS; cele două combinații noi de stare/focus au scăpat acelei suite.

Reticle NOT_INTEGRATED/neexecutat; Chisel BLOCKED_NO_GO. Nu am inspectat capturi reale ale noului build și nu acord aprobare estetică. Fără operator UI/API, credentiale reale, tempkey.txt, documentul HTML protejat, servicii/Start/Stop/recover, trafic extern, rollout, push, T2 sau canonical/default-full.

**Pas următor:** părintele adjudecă R2-01/R2-02; developerul deținut face remediile minimale + RED/GREEN, apoi affected check/freeze/re-review focalizat. Restul lecturii SOURCE rămâne reutilizabil pe bytes neschimbați; ulterior se poate admite QA bounded existentă, fără extinderea harnessului.
