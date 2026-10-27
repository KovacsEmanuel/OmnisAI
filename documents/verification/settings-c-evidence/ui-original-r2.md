# R2 — Settings C: CHANGES_REQUESTED_SOURCE_SCOPED

Review ID: R2-SETTINGS-C-57ae4967. Raport original; părintele păstrează acești bytes și adjudecă/remediază separat.

## Snapshot și limită

- Repo: `/home/kali/OmnisAI`; base/HEAD `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Candidate ID: `57ae496709f00413e31fd8741fd0d41f6c6b6733bb04be0b6ddfe97d36a15f39`.
- Manifest: `/home/kali/.hermes/cache/scratch/uic/frozen-candidate.json`, SHA-256 `e48cee247a16a8197bef3c44d885ac78dd7954494c24302890499cb8d59afc27`.
- Legare explicită la TOATE cele 32 căi owned din manifest, inclusiv cele 9 fișiere noi untracked; hashurile tuturor au fost recitite la început și la final, fără diferențe. Index diff gol; `git diff --check` exit0. Lista integrală este mai jos.
- Review complementar R2: secrete/auth/generation, incertitudine, concurență, Cancel/Stop, guardul assignment și oracle/preflight al consumerilor reali. Nu substituie R1, QA API/PG/browser sau acceptarea estetică.
- Nicio editare de produs/docs/index/skills, commit, DB, browser-consumer, serviciu/operator instance, provider/network/auth sau push. Numai SOURCE React/jsdom cu fetch sintetic, un test SOURCE existent și Makefile copiat în scratch cu shell care refuză orice rețetă. Căile private protejate nu au fost citite.

## Findings

### R2-C01 — HIGH / P1 — scope-ul Settings nu urmărește schimbarea grantului autentificat

**Fișier/linie:** `web/src/features/engagement/ProviderSettings.tsx:9–12`; calleri: `useBrowserSession.ts:18–24,43–46,113–125`, `SettingsModelsPage.tsx:21–23,71–74`, `SettingsModelWizard.tsx:36–53,73–88`.

**Criteriu:** cheia write-only trebuie ștearsă/infirmată la schimbarea auth generation; pending operation/receipt dintr-o sesiune nu este adoptat de altă sesiune/instanță. Fingerprintul persistat trebuie să aparțină grantului curent, fără token brut în storage/query key.

**Repro real SOURCE / RED:** App-ul real + BrowserSessionProvider + client/decodere reale + fixture-ul HTTP existent. A este autentificat, deschide wizardul și introduce o cheie sintetică nesalvată; următorul `/api/session` întoarce un grant valid sintactic B (simulează pairing în alt tab, fără o stare intermediară UNAUTHENTICATED); se invalidează query-ul `session`, deci rulează `api.session` real. Query-ul confirmă B, însă inputul vechi păstrează valoarea și wizardul rămâne activ. În al doilea caz, un save A cu răspuns pierdut păstrează `Recover exact receipt` după trecerea la B. Ambele aserțiuni de separare a sesiunilor sunt RED.

**Cauză:** query key-ul `['private','settings-session-scope']` este constant; nici `enabled`, nici key-ul paginii nu se schimbă când un session poll confirmă alt CSRF în aceeași pagină. Hashul A rămâne `scope.data`. Epoch-ul existent nu avansează pentru tranziția autentificat-A → autentificat-B. Prin urmare nu rulează cleanup-ul cheii/lifetime-ului, iar state-ul vechi este utilizabil împreună cu noul context de sesiune. Nu afirm un bypass server-side sau o exfiltrare efectivă.

**Dovadă:** `r2-seams.test.tsx` primele două teste; `source-repro-nodeenv-test.log`: 2 failed / 1 passed, exit1, 4.01s. Testul de control Cancel în timpul save-ului cheii este GREEN și nu pornește catalog după închidere.

**Remediu minim:** leagă derivarea/acceptarea scope-ului de grantul/identitatea de sesiune curentă; nu randa/adopta SettingsModelsPage cu rezultatul vechi cât timp se calculează bindingul nou. Schimbarea grantului trebuie să închidă/invalideze wizardul și lifetime-ul vechi și să nu adopte pointerele vechi. Nu pune CSRF brut în query keys sau sessionStorage. Adaugă aceste două regresii la testele Settings existente.

### R2-C02 — MEDIUM / P2 — noul gate poate întoarce succes cu verificarea ocolită

**Fișier/linie:** `Makefile:12–17,36–39`; regresia existentă: `tests/development/test_test_db_gate.py:377–415`.

**Criteriu:** comanda canonică/targetul de verificare nu trebuie slăbit prin dry-run/touch/question/ignore-errors; contractul Make existent cere refuz înainte de rețete.

**Repro real / RED:** copie byte-exactă a Makefile în scratch, `SHELL=<scratch>/no-effect-shell` care execută exclusiv `exit 97`. Pentru `test-model-test-v2-pg`, fiecare dintre `-n/-t/-q/-i` este refuzat cu exit2 și mesajul `Unsafe Make flags`. Pentru noul `test-settings-models-ui-pg`: `-n` exit0, `-t` exit0, `-q` exit1 fără guard, `-i` exit0 chiar dacă shellul refuză toate rețetele. Nicio rețetă produs/DB nu a fost executată. Rezultatele exacte: `make-negative-controls.json` (8 combinații).

**Cauză:** noul target lipsește din lista `filter` a guardului existent. Acesta este un defect al targetului, nu o reclasificare a dry-run-ului autorului: `make -n` din freeze a fost declarat corect PREflight, nu PASS. Runnerul privat are propriul mediu filtrat; nu pretind că invocarea lui normală ar moșteni aceste flags.

**Remediu minim:** adaugă `test-settings-models-ui-pg` pe linia guardului și în tuple-ul targeturilor din testul negativ existent; păstrează toate cele patru flags și aserțiunea că nicio rețetă nu a pornit. Fără wrapper/framework nou.

### R2-C03 — MEDIUM / P2 — producătorul installed SENT a fost extins, census-oracle-ul său nu

**Fișier/linie:** `api/tests/installed_sent_probe.py:175–182`; consumer/oracle: `api/tests/test_model_test_v2.py:1668–1685`; definiția scrierilor: `api/src/omnis/modules/settings/provider_model_service.py:163–220`.

**Criteriu:** callerii/fixture-urile afectate și oracle-ul exact de persistență trebuie aliniate; gate-ul existent `test-model-test-v2-pg` nu poate fi livrat cu un census contradictoriu. Nu se elimină exactitatea oracle-ului pentru a obține verde.

**Repro SOURCE structural / RED (nu PG):** noul `PROBE` în modul `produce` execută `save_models` înaintea `save_selection`. `handle_models` comite câte o scriere în `provider_model_registry_revision`, `provider_model_entry`, `provider_model_entry_revision`, `provider_model_command`. La tăierea SENT toate acestea diferă față de `before`, dar setul exact permis de aserțiunea `cut` le exclude pe toate patru. Citirea AST a setului exact din consumer și a SQL-urilor INSERT ale producerului returnează aceste patru lipsuri; aserțiunea SOURCE de includere este RED/exit1. Detalii: `installed-census-source.json`. Nu am executat originalul installed/PG și nu îi atribui un exit runtime observat.

**Remediu minim:** include cele patru tabele nou scrise în setul exact `before → cut`; păstrează comparațiile complete `cut → after → final` pentru a demonstra că recover/replay nu rescriu registrul. Rulează consumerul real affected numai după review/admitere, nu un census mai permisiv sau un skip.

## Cerință → cod → dovadă/dispoziție

| Cerință R2 | Cod/call path | Dovadă și limită |
|---|---|---|
| Secret DOM-only; wipe submit/cancel/provider/unmount/auth generation | Wizard:36–88,108–114; ProviderSettings:9–12 | Wipe explicit fără secret în React state/storage; controlul SOURCE Cancel GREEN; auth generation RED, R2-C01. |
| Pending secretless, legat de sesiune; recovery receive-only | SettingsModels:42–67; Page:80–115,131–165 | SHA-256 CSRF, UUID-uri validate; recovery citește receiptul exact și cache/current, fără resend/Refresh; separarea granturilor RED, R2-C01. |
| O acțiune/revizie/snapshot; Cancel fără escaladare după await | Page:92–115,141–176; Wizard:68–105 | Busy/lifetime/generation fence inspectate; Cancel în save cheie GREEN, numai scrierea locală deja admisă continuă, fără catalog ulterior. Save & test folosește intrarea confirmată și verifică wizard generation. Nu este QA runtime. |
| Boot/reload/typing fără provider IO; refresh explicit | Page:43–61,119–139; Wizard:47–51,68–88,116–125 | Boot și typing folosesc search cache; doar Continue/Refresh cheamă refresh. Readback catalog nu face refresh. SOURCE inspection, nu trafic provider observat. |
| Save models nu schimbă Default; assignments exacte și stale vizibile | Page:167–176; Assignments:14–47,65–72 | Save models are caller distinct; stale refs nu sunt înlocuite; explicit overrides/output caps se păstrează. Inspecție SOURCE; R1 deține breadth funcțional. |
| Guard membership în tranzacția ownerului; CAS/replay rămân | provider_key_service:210–230,242–276,330–369; InstanceService.admission:464–476 | Guard verifică fiecare ref non-null, connection ID/rev/exact model și ultima revizie a entry-ului în aceeași admission transaction. Replay precede noua validare. Testul existent `assignment_membership`: 1 passed / 33 deselected / exit0, fără DB. |
| Revoke/Replace invalidează wizardul, stale Continue nu reconectează | Page:191–208; Wizard:35–53,73–88,98–105 | Pinned connection ID/rev/enabled, stale hard barrier și close la Disable inspectate. Nu reaprob backendul catalog/test deja acceptat; QA reală rămâne NOT_RUN. |
| Cancel/readback independente; Stop neinterceptat; focus native/ARIA | Page:75,183,209–213; Wizard:107–140; CSS | Wizard inline, fără modal/inert/global key trap; Cancel separat, readback operație în afara wizardului; handlers transient guard vs native hard stale. Nu există probă nouă de Stop activ/keyboard/screen-reader. |
| Consumer real pozitiv și refuz exact pe același canal | settings-models.mjs:54–77; test_model_test_v2:507–532; test_web_e2e:278–385 | Preflight SOURCE urmărit: fixture/02 non-default, Default00/Brain01 cap37 nemodificate; intentul original reutilizat cu ID nou după Disable cere exact409 CONNECTION_UNAVAILABLE, un SENT total; restart API/census. Nu a fost lansat. Make/oracle blockers R2-C02/C03. |
| Deadline/ownership/cleanup/fără trafic extern | test_web_e2e helper; run.mjs:83–139; test_model_test_v2:475–485,1526–1558 | Driver120s/stage, caz300s, heartbeat, owned_children/cleanup_all și finally drain/close inspectate; browser extern blocat și marker/leak checks existente. Cleanup runtime neexercitat în R2. |

## Comenzi și rezultate proprii

1. Status/base/diffcheck + verificare directă SHA-256 pentru toate cele32 fișiere și manifest la început/final: exit0, zero mismatch; 9 owned untracked, index nemodificat.
2. `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH TMPDIR=/home/kali/.hermes/cache/scratch/r2-settings-57ae-4p36wfno NODE_ENV=test timeout --signal=TERM --kill-after=5s 60s web/node_modules/.bin/vitest run --config /home/kali/.hermes/cache/scratch/r2-settings-57ae-4p36wfno/vitest.config.mjs --reporter=verbose`: exit1, 2 auth RED / 1 Cancel GREEN. Nu este suită completă sau browser consumer. Tentativa scratch anterioară fără NODE_ENV=test a eșuat la `React.act is not a function` înaintea scenariilor; `source-repro.log` rămâne păstrat și nu este probă de produs.
3. `TMPDIR=<scratch> timeout --signal=TERM --kill-after=5s 60s env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS api/.venv/bin/python -I -B -m pytest -p no:cacheprovider -c api/pyproject.toml api/tests/test_provider_key_settings.py -q -k assignment_membership`: exit0, 1 passed / 33 deselected,0.25s (`assignment-source.log`).
4. Opt invocări Make pe copia byte-exactă și shell no-effect: vechi4×exit2/guard; nou0,0,1,0/fără guard (`make-negative-controls.json`).
5. Aserțiune SOURCE structurală pe expected changed-table set și SQL-urile noului producer: exit1, exact4 tabele lipsă (`installed-census-source.json`). Nu PG RED.

## Toate căile frozen acoperite de binding

```text
Makefile
api/src/omnis/core/errors.py
api/src/omnis/modules/settings/provider_key_routes.py
api/src/omnis/modules/settings/provider_key_service.py
api/tests/installed_sent_probe.py
api/tests/test_model_test_v2.py
api/tests/test_provider_key_api.py
api/tests/test_provider_key_settings.py
api/tests/test_web_e2e.py
contracts/omnis.openapi.json
ops/run_test_db_gate.py
web/src/app/ModelTest.test.tsx
web/src/app/ProviderKeySettings.test.tsx
web/src/app/SettingsModels.test.tsx
web/src/app/SettingsWizard.test.tsx
web/src/app/Wizard.test.tsx
web/src/features/engagement/ModelTest.tsx
web/src/features/engagement/ProviderSettings.tsx
web/src/features/engagement/Settings.tsx
web/src/features/engagement/SettingsAssignments.tsx
web/src/features/engagement/SettingsModelWizard.tsx
web/src/features/engagement/SettingsModels.module.css
web/src/features/engagement/SettingsModels.ts
web/src/features/engagement/SettingsModelsPage.tsx
web/src/features/engagement/Wizard.tsx
web/src/features/engagement/copy.ts
web/src/shared/api/errors.ts
web/src/shared/api/generated.ts
web/tests/e2e/provider-settings-focus.mjs
web/tests/e2e/run.mjs
web/tests/e2e/settings-models.mjs
web/tests/settings-fixtures.ts
```

## Verdict și neexecutat

CHANGES_REQUESTED_SOURCE_SCOPED pentru snapshotul exact; R2-C01/C02/C03 necesită adjudecare și remedii minimale ale autorului, apoi checks afectate și re-review focalizat. Nu înseamnă defect dovedit în backendul catalog/test neschimbat sau anularea acceptărilor lui istorice. Nu deduc absența altor defecte din acest review.

Nu am rulat DB/installed/browser-consumer/canonical, provider live, screen-reader sau review estetic; nu am repetat full lint/build/suitele autorului. Reticle NOT_INTEGRATED în această verificare SOURCE, Chisel BLOCKED_NO_GO. Riscul rămas este autorizarea/adoptarea state-ului UI peste schimbarea grantului și două incompatibilități concrete de gate/oracle; produsul nu este acceptat runtime.
