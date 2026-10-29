# R1 focused re-review — 190fae1

**Verdict: SOURCE_ADMITTED_FOR_NARROW_REMOVE_QA.** Niciun blocker SOURCE nou confirmat în scope. Nu este acceptare runtime/browser/vizuală, integrare sau rollout.

## Identitate și limită

- IDENTITY_BEGIN: worktree `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`, HEAD `190fae18e57e115a8a86559cec386b9ea147fd4b`, tree `42f33c5a788203eaf4a7d95fc8fb8e88b713f7c5`.
- Bază de re-review: `c4d465c072ebbd246bd882441a7465b55b0b2ab6`. Delta: cele 10 fișiere de teste/fixture/wiring, 990+/29-. Am verificat independent zero diff în `api/src`, `cli/src`, `web/src`; aprobarea anterioară a produsului se compune numai în scope-ul său, nu este audit nou al tuturor celor 46 fișiere.
- Tracked/index clean; cele trei symlinkuri untracked de dependențe preexistente neatinse. Checkoutul comun observat: HEAD `9c58c99a230af947153a87dc4e19a535b61b7423`, tree `005792826a23f1a9a8fd4d558a2d01e1feb6a9db`; fișierele protejate untracked nu au fost citite.
- Original R1: `/home/kali/OmnisAI/documents/verification/settings-c-evidence/remove-model-r1-c4d465c-original.md`, SHA256 `6e56ce3619504c116541a47a65b524513d01c0748a6b97d4cc894744d2194687`.
- Checkpoint autor: `/home/kali/.hermes/cache/scratch/remove-model-proof-checkpoint-190fae1.md`, SHA256 `c939f6243e17e218af2fba93290e5052c92ca1cdb07917cd7ce2d9bc0bfb7e67`.
- Manifest: `/home/kali/.hermes/cache/scratch/remove-model-proof-freeze-190fae1.json`, SHA256 `ac7ca48377a5c6760f07564f0d7f44e3a781b406ca81a70814a95f712797c67e`. Verificarea completă 53 blobs/SHA și distribuția veche aparțin părintelui; nu le revendic repetate.

## Dispoziții

### R1-P01 — CLOSED_SOURCE / PROOF_SCOPED

`api/tests/test_provider_key_api.py:581,623-668,669-898,899-928,988-1095` închide lipsa din original: parametrizare empty/0015/0016, migrare explicită la0016, populare ÎNAINTE de upgrade0017 și egalitate integrală a rândurilor colectate după upgrade. Numai coloana nouă `removed_registry_revision` este separată și cerută NULL. Conexiunile, selecțiile și receiptul Settings vechi sunt comparate separat.

Seedul0016 este declarat sintetic, nu model call: receipt registry tipizat, EntryCapabilities/EntrySnapshot/Projection, operation și evenimente, start command, dispatch RESERVED/SENT/SETTLED și outcome UNKNOWN cu usage9/7 și cost `0.000016`. Nu este vechiul snapshot `{}` prezentat drept istoric de model autentic. Proba de migrare nu pretinde că arhiva sintetică a executat providerul.

Controalele SQL exercită rewrite model/entry/connection/instance, DELETE/TRUNCATE, FK retirement inexistent și numai în namespace străin (rollback), retirement valid, refuz unretire/re-retire, re-add cu identitate nouă și unicitate numai disponibilă. `schema_reason_on` este consumerul efectiv pentru index absent/neunic, guard absent/disabled/funcție slăbită și FK absent/NOT VALID; fiecare mutație este rollback, urmată de readiness pozitiv. Nu s-a adăugat downgrade.

Limita: SOURCE inspectat plus dovada PG a autorului reutilizată, nu PG executat independent și nu upgrade operator.

### R1-P02 — CLOSED_SOURCE / PROOF_SCOPED

`api/tests/test_model_test_v2.py:130-149,713-783,807-826,888-959,1182-1221` ajunge în ramura entry, nu legacy/instance-scoped: PUT `/api/v1/model-test/entries` autentificat → ASGI → control UDS → ApiKeyModelTest/prepare EntrySnapshot → ModelSender → peer TLS local controlat → PG. Peerul validează modelul și max_tokens/fallbacks; consumerul produce FINISHED/COMPLETED și usage KNOWN9/7. Nu este INSERT manual de operație cu snapshot gol.

După Remove, exact operation și latest(E) sunt comparate cu întregul view anterior, cu unica schimbare așteptată `current: false`. Censusul celor 13 tabele păstrează integral recordurile/snapshot/outcome/usage/cost/commands/events/dispatch și entry revisions; conexiunea și selecțiile au și egalitate a view-ului public. Costul autentic nu este revendicat ca valoare nenulă: peerul nu furnizează cost; se păstrează valoarea arhivată/necunoscută. Non-null cost este acoperit de seedul sintetic P01, distinct.

Excluderea tabelelor de registry/identity/receipt din comparația Remove este intenționată: acestea sunt write-setul comenzii. Păstrarea celorlalte identități se compune cu sursa neschimbată `provider_model_service.py:96-110,243-256`: filtrare numai a ID-ului cerut, UPDATE calificat `(instance_id,entry_id)`, zero entry-revision writes pentru Remove. Nu revendic o comparație raw separată a celorlalte rânduri identity în acest test.

Save(E retras) folosește registry proaspăt2 și **expected_revision0**: trece de conflictul trivial al vechiului fixture și ajunge la refuzul explicit de identitate arhivată `provider_model_service.py:220-233`, 409 REVISION_CONFLICT, cu întreg census neschimbat. E2 nou are latest404/NOT_FOUND ÎNAINTE de primul său Test; selecția/conexiunea rămân neschimbate. Testul separat ulterior al E2 pentru overlap nu mai este confundat cu lipsa istoricului: la reconstrucție se compară rezultatul său autentic terminal, cu current false.

Consumerul este reconstruit cu owner/epoch/vault/sender noi, reconcile și exact/latest/receipt readback fără schimbări de census sau trafic. Acesta NU este restart OS al ownerului; checkpointul nu îl revendică astfel. Restartul API subprocess are proba browser pregătită de mai jos. Acceptance runtime/restart owner instalat nu este închis prin acest verdict SOURCE.

## Noul consumer Remove — admis SOURCE, browser NOT_RUN

`entry_remove_ui` este opt-in și selectat prin `Makefile:37-40`, runnerul existent și `settings_models_browser(..., scenario="settings-remove")`; nu introduce framework/server family nou. `api/tests/test_model_test_v2.py:827-887` pregătește un istoric EntryTest real controlat, 18 membri locali și Default pe alt model. ID-ul țintei plasează intrarea pe pagina2; browserul verifică explicit acest lucru înaintea mutației.

`web/tests/e2e/settings-models.mjs:6-134` corespunde callerului real `SettingsModelsPage.tsx:147-182,314-336,378-402`: disclosure/Enter, refuz local Used by Default, confirmarea exactă și dismiss fără PUT, confirm/Enter cu singurul Remove. Faultul face `route.fetch()` până la HTTP200/receipt COMIS și abia apoi pierde replyul; nu este un răspuns de succes fabricat. Recovery folosește butonul existent și sursa sa GET exact + reload; oracle-ul citește separat receiptul aceleiași comenzi și paginile, 17 membri unici/fără țintă, istoricul exact/latest și conexiunea/selecțiile neschimbate. Reload nu retrimite Remove/Test/Refresh. Re-add este seed explicit HTTP cu ID nou, apoi reload UI → Not tested/latest404, nu pretins flow UI Add complet.

`api/tests/test_web_e2e.py:278-385` lansează/oprește/relansează efectiv API subprocess pe aceeași DB și același owner UDS; etapa after citește receiptul/istoricul/E2 și refuză writes. Censusul tuturor celor 13 tabele este egal între etape. Nu pretinde restart OS al ownerului sau installed release lifecycle. Callerul exterior verifică zero trafic TLS nou în browser.

La1440/1280/390/320 sunt programate assertions focus/outline/44px/hit-test/metric-overlap/overflow și capturi. Sunt SOURCE, **nu rezultate executate**: plasarea dreapta/centrare desktop/sub metrici mobil, ordinea reală Tab și estetica necesită QA/inspecția capturilor; `.focus()` nu certifică singur navigarea completă Tab. Nu sunt prerequisite circulare de admitere a acestei QA. Nicio nouă constatare blocantă demonstrată în control/oracle pentru prima probă îngustă.

## Verificări și limite

- Read-only: Git identities/status/delta; diff produs0; `git diff --check c4d465c..190fae1` exit0; `node --check web/tests/e2e/run.mjs` și `node --check web/tests/e2e/settings-models.mjs` exit0. Contract Remove100-114 și producer/readeri afectați inspectați.
- Dovadă autor reutilizată: gate PG target `test-settings-remove-pg`, raport4PASS19.53s/PG18.6 UDS/network_none. Am citit numai sumarul sigur `remove-proof-pg3.log` și `db-1608b5c479284ce4/gate.log.result.json`: code0/family_drained=true; readback owned resources absent/uncertain=False. Nu am citit logul PG raw și nu pretind execuție independentă. Eșecul anterior E2 latest după Test rămâne eșec de fixture, nu RED de produs.
- Scope R2 overlap/auth/epoch/CLI/runner security/TLS-library preflight nu este reapropiat. R2-R01 BLOCKED_OPERATOR_UPGRADE rămâne deschis; operator UNAVAILABLE/RECOVERY_REQUIRED conform mandatului, fără verificare sau recuperare de către mine. Vechile Cancel409/default-web2FAIL/counter2/canonical5400NOT_RUN și lipsa T2 nu sunt resetate.
- Nicio execuție PG/browser/build, servicii/operator/provider, migrare, model call, config/env/secret/cookie/dump; nici editare/stage/commit/push/skill. Singurul fișier nou este acest raport scratch. Reticle NOT_INTEGRATED/NOT_RUN; Chisel BLOCKED_NO_GO.
- IDENTITY_END: worktree `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`, HEAD `190fae18e57e115a8a86559cec386b9ea147fd4b`, tree `42f33c5a788203eaf4a7d95fc8fb8e88b713f7c5`; tracked/index clean, aceleași trei symlinkuri untracked. Părintele deține adjudecarea și acceptarea finală.

Omis: runtime/browser/inspecție vizuală și scope R2. Risc: admiterea SOURCE permite QA îngustă, nu garantează că journey-ul sau geometria vor trece și nu certifică upgrade operator/restart OS owner.
