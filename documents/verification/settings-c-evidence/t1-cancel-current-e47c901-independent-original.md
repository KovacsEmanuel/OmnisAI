# Review independent SOURCE — current-revision Cancel e47c901

## Verdict

**SOURCE_ADMITTED_FOR_ONE_CURRENT_REVISION_QA**

Niciun finding concret blocant în delta revizuită. Se admite numai o singură QA fresh, bounded600s, pe nodul `api/tests/test_model_test_v2.py::test_api_pg_sdk_protocol_and_replay[settings_cancel_current_ui]`, opt-in explicit `OMNIS_SETTINGS_CANCEL_UI=1`, prin frontiera programatică existentă `prove_private_fixture` → `run_gate`/targetul `test-model-test-v2-pg`. Părintele păstrează pinurile, atestarea fixture-ului privat, semnalele, family/drain/cleanup, HOME/TMPDIR private și `PLAYWRIGHT_BROWSERS_PATH=/home/kali/.cache/ms-playwright`. Fără modificări runner/Make și fără rerun diagnostic vechi/default/known/broad. Counter2 rămâne consumat. Acesta este review SOURCE, nu QA executată, Cancel ACK observat, integrare, canonical PASS sau acceptare T1/operator.

## Identitate și scope

- Root `/home/kali/.hermes/cache/scratch/t1-narrow-20261029`.
- Bază `635c8fa7ae76ea541a9f12441fec9b717709c6da`; HEAD `e47c9017f6ab8a541dd4b5c155979bd620489215`; tree `aa177b8c727b8018b3563846b01eca9d448b1c6d`.
- Freeze `/home/kali/.hermes/cache/scratch/t1-cancel-current-e47c901-freeze.json`, SHA256 `df5ed635d0c555bba65f50f66ac8d6bfdb96a2457efdd8ed668177c61ce549ce`.
- Verificate programatic identitatea HEAD/tree, toate5bindings blob/SHA (4delta + SettingsWizard neschimbat), ambele patchuri exact față de Git și hashes/bytes declarate. Delta exact4căi test-only,89inserări/9ștergeri. API/CLI/UI production, ops și Makefile neschimbate față de baza reviewuită.
- Neversionate preexistente păstrate: `api/.venv`, `cli/.venv`, `web/node_modules`. Nicio modificare repo/commit făcută de reviewer.

## Cerință → consumer → risc → decizie

Controlul pozitiv trebuie să trimită prima anulare cu revizia RUNNING2 citită real de UI, să observe202 și aceeași operație FINISHED/CANCELLED4. Consumer: Settings real → client HTTP → API → LocalControl → owner/PG → peer TLS local existent. Riscul urmărit: revizie injectată, răspuns fabricat, citire nepotrivită, al doilea Start/Cancel, promovarea409 la succes ori slăbirea guardurilor. Source-ul admite proba finită; nu demonstrează singur remedierea produsului sau cauza FAIL-urilor istorice.

## Trasee și conservare

1. `web/tests/e2e/settings-models.mjs:156–220`: click real Test/consent/Send, PUT202 legat de operation_id; apoi click pe „Read test status”. Waiterii GET sunt armați înainte de click și cer exact URL-ul operației plus `/entries/latest/{entry_id}`. Ambele răspunsuri trebuie200/same-op/RUNNING2. Se așteaptă corpul/latest tail, `finished()` și două frame-uri înainte de primul Cancel. Fără cache injection, route fulfill sau răspuns sintetic al consumerului.
2. Callerul production confirmă traseul: `SettingsModelsPage.tsx:248–257,394–405,453–455`; `readTest` face GET operație → actualizează cache-ul produsului → GET latest → updateCheck, iar Cancel folosește `observed.state_revision`. `client.ts:83–102` și `model_test_routes.py:179–238` confirmă URL-urile/metodele/schema, nu un seam paralel. Pollingul GET automat poate coexista, însă latest tail provine din citirea UI; revizia stabilă cerută și assertul requestului Cancel refuză o revizie stale, nu o ascund.
3. `settings-models.mjs:196–220`: se cere request Cancel revision2, HTTP202, same-op/FINISHED/CANCELLED4 și readback HTTP exact pe aceeași operație.409 nu poate produce PASS. Se verifică1Start/1Cancel și lipsa PUT/Refresh suplimentare; secret checks/zero extern/pageErrors rămân în runner.
4. `test_model_test_v2.py:595–628,664–703`: callbackul observă peer-entry înainte de `owner.handle`, fără a ține settings.lock; pentru noul caz cere requested=observed revision2/RUNNING. Release în finally după handle; outer finally:2648–2682 eliberează peerul și pe erori anterioare. Census cere1system_operation/1entry, nicio selection și exact metadata GET + un POST TLS. CAS real rămâne în `model_test_runtime.py:327–367`.
5. `test_web_e2e.py:323–395`: cele două cazuri finite sunt before-only. Vechiul diagnostic rămâne DIAGNOSTIC; noul caz folosește PASS numai după asserturile stricte. settings-models/remove păstrează before+after, census/restart și labelul original. Marker-channel, secret checks, owner/family și cleanup sunt păstrate.
6. Conservare verificată byte-exact: întreg suffixul JS începând cu vechiul `settings-cancel-probe` este identic bazei; `passed:null`/DIAGNOSTIC versus true/PASS rămân distincte în `run.mjs:334–339`. Funcția observer și negativul wrong-ID/channel sunt AST-identice. Evaluarea expresiilor AST reale pentru registry seed/renew/loopback confirmă echivalența tuturor28cazurilor vechi; noul caz folosește aceleași predicate finite ca diagnosticul vechi.

## Verificări executate / limite

- Git status/diff/stat/HEAD/tree, `git diff --check 635c8fa..HEAD`: exit0.
- Asserturi inline Python `-I -B` de identitate5bindings/ambele patchuri/conservare diagnostic/negative: exit0.
- Asserturi inline pe AST real:28cazuri vechi echivalente, before-only/DIAGNOSTIC pentru vechi, before-only/PASS pentru nou, before+after/PASS pentru ceilalți2consumatori; production/runner neschimbate: exit0.
- `node --check web/tests/e2e/settings-models.mjs` și `node --check web/tests/e2e/run.mjs`: exit0. Acestea nu execută browserul sau funcționalitatea Cancel.
- Creat numai acest original scratch solicitat. Nu am lansat PG, Docker, browser, build, provider/model, pytest runtime sau proba600s; nu am accesat secrete/profiluri/protected files. Reticle NOT_APPLICABLE pentru review SOURCE; Chisel BLOCKED_NO_GO.
- Nicio schimbare propusă la CURRENT/operator/RECOVERY_REQUIRED.409 diagnostic observat anterior rămâne diagnostic separat; cauza vechiului409 nu este atribuită retrospectiv. Adjudecarea și QA reală aparțin părintelui.

**Omis intenționat:** re-auditul seamului/upgrade-ului deja aprobat și orice probe largi sau efecte. **Risc rămas:** sincronizarea UI și rezultatul202/CANCELLED4 trebuie confirmate în unica QA reală; SOURCE nu certifică runtime sau T1.
