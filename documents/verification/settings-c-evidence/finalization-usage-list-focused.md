# Review independent focalizat — lista verticală Settings + QA Cancel202

**Verdict: APPROVED_SOURCE_SCOPED_COMPOSED. Findings noi: niciunul. QA-HTTP-202-01: CLOSED_SOURCE_SCOPED pe callerul QA final.** Nu este acceptare a integrării de către părinte, aprobare estetică, runtime PASS sau autorizare de relansare QA.

## Admitere și freeze

Cerință → consumer → risc → decizie: contract f7b9dd8, UI/UX:161 și web/design/settings-final.md:56–64 → lista/rândul Settings și callerii lor existenți → pierderea semanticii/focusului, valori false sau oracle Cancel incompatibil cu ruta reală → verdict exclusiv SOURCE pentru următoarea decizie a părintelui. Fără audit general sau efecte.

Main `/home/kali/OmnisAI`: `97d36ace48feea276086e2aba5fa1d3ba126d1df`; baza aprobată `1629ade`. QA `/home/kali/.hermes/cache/scratch/fqa-a488b26`: `8a02a6c90e77aa7623008e425d69b74e59f1bdf8`; baza aprobată `3fe4a93`. Manifest exact: `/home/kali/.hermes/cache/scratch/settings-usage-list-integrated-freeze.json`, revalidat pe cele cinci bloburi/SHA la început și final. Identitățile complete sunt în anexa de readback. Niciun tracked diff existent la început/final. Untracked preexistente păstrate; conținutul `tempkey.txt` și `documents/Omnis_Notite_Originale.html` nu a fost citit.

Scope/callers: main Page, CSS module, SettingsWizard.test.tsx, main E2E; QA E2E final combinat. Definițiile globale de stil/tokenuri și ruta Cancel sunt numai context read-only. Config, exports și fixture-uri nu cer schimbări. Arborii web/src, api/src și cli/src sunt identici între cele două HEAD-uri. Producerul QA Python are SHA neschimbat, verificat la final; nu i se reface auditul.

## Constatări și compoziție

### Lista/focus/labels: APPROVED_SOURCE_SCOPED

- `SettingsModelsPage.tsx:367–387`: buton nativ cu aria-expanded/controls/describedby și secțiune hidden; `dl`/`dt`/`dd` native păstrate. Numai cele două etichete devin Input tokens/Output tokens; Cost și valorile rămân reale. `?? 'Unknown'` conservă zero și nu inventează monedă. Test:47 și E2E main:302/QA:275 sunt cuplate la exact aceleași etichete și continuă comparația valorilor reale. Testul încă se numește „capsule”; numele istoric nu este criteriu de produs și nu justifică editare.
- `SettingsModels.module.css:25–34`: trei rânduri grid, două coloane minmax(0,1fr), valori la dreapta/tabular-nums, fără border/background/radius de capsulă; lățime280px/max100%, border-box global și overflow-wrap:anywhere. Nu apare la SOURCE o regresie concretă de overflow; geometria reală pe mobil/zoom rămâne de inspectat nativ.
- `:26–27`: specificitatea locală corectează hover/expanded față de fundalul transparent din :25. Focus-visible rămâne outline2px solid din --color-border/offset1px; regula este doar pentru disclosure și nu modifică focusul celorlalte controale. Definiții reale tokens.css:6–9: #726d62 pe #131412 și #191b18. Contrast calculat din sursă: **3.589401521559418 / 3.367715985543742**, peste3:1. Nu este o măsurare de screenshot.
- global.css:1,7,15 și CSS local:44 păstrează border-box, min-width44px/min-height44px, plus focusul global pentru rest. Nu există forced-color-adjust:none ori outline:none; outline solid rămâne supus ajustării UA în forced colors. Regula @media locală:77 nu îl anulează. Aceasta este inspecție SOURCE, nu probă de browser/OS forced-colors.
- Main delta este exact9 inserări/8 ștergeri în4fișiere. Nu schimbă handleri, selecție/ownership, backend, provider sau autorizare. Contextul de eșec/UNKNOWN și Cancel/recovery în afara detaliilor hidden rămân neschimbate. Aprobările anterioare ca33 R1/R2 rămân compuse în scope-ul lor; nu sunt redeschise și nu sunt emise ca probe noi. Originalul `finalization-capsule-focused.md` SHA25a602f2…ee397 a fost citit/verificat.

### QA-HTTP-202-01: CLOSED_SOURCE_SCOPED, nu rezoluție a HTTP409 real

- Reproducerul defectului de oracle: ruta efectivă `api/src/omnis/modules/runs/model_test_routes.py:220–238` declară HTTP202 pentru Cancel entry; result:127–144 întoarce EntryTestView. Vechiul caller cerea200 la ambele Cancel. Chiar un răspuns corect202 era respins înainte de parsarea JSON. Remediul minim existent este corect la QA E2E:230–246 și321–337: JSON citit întâi/o singură dată, status strict202, apoi aceleași verificări de request revision2, ID real, FINISHED/revision4/CANCELLED/UNKNOWN/reason/output.
- Mesajul de eșec construiește explicit numai status, error.code, request.expected_state_revision, state, state_revision, operation_id și îl taie la4096 caractere. Câmpurile opționale ale răspunsului absente devin null; expected_state_revision este citit din requestul real și verificat separat ca2. Nu se copiază body/input/output/cheie/request integral. Nu acceptă409, nu retry și nu resend.
- Comparația cu baza3fe4a93 arată exclusiv cele două blocuri Cancel și etichetele usage; cele șapte postcondiții terminale ale fiecărui Cancel au fost comparate exact cu baza. QA:309–344 păstrează identitatea lui B, RUNNING/revision2, istoria A neschimbată și două Starts/două Cancels; :393–397 păstrează inventarul și no-resend. Timeouts/waits nu se schimbă.
- Remediu suplimentar solicitat: niciunul pentru acest finding SOURCE. Eroarea reală409 anterioară și lipsa codului/reviziei de request observate rămân. Nu se atribuie retrospectiv REVISION_CONFLICT ori altă cauză; cursa PENDING1→RUNNING2/CAS este numai ipoteză. Noul diagnostic ajută o eventuală probă admisă separat, nu dovedește cauza.

## Verificări executate independent

Node fixat v24.21.0; node --check pentru ambele E2E finale: exit0. git diff --check în ambele checkouturi: exit0. Opt cazuri **SOURCE_SYNTHETIC** pe cele două blocuri extrase exact în memorie: 202/rev2 acceptat,200/rev2 refuzat,409/rev2 refuzat,202/rev1 refuzat pentru fiecare bloc; JSON o singură citire, chei exacte și excluderea sentinelurilor input/output din diagnostic: toatePASS/exit0. Nu s-a importat/rulat callerul E2E și nu s-au produs cereri HTTP. Calculele de contrast și revalidarea freeze/tree/SHA au exit0. Outputul efectiv al comenzilor este anexat, nu sintetizat ca rezultat runtime.

Dovada developerului122affected/3fișiere/26.40s, extra103/25.84s și lint/types/parser0 este context furnizat, nu rerulare independentă aici. Logul existent settings-cancel-202-source-proof.log a fost citit: cele două erori inițiale ale helperului efemer sunt păstrate, urmate de8cazuri syntheticPASS; acest log nu este runtime proof.

## Limite și status propus

Cod prezentare IMPLEMENTED; probă independentă SOURCE scoped; review APPROVED_SOURCE_SCOPED_COMPOSED. Părintele decide integrarea și admiterea buildului/inspecției native fără Test/provider. Niciun finding concret nou; severitate/reproducer/remediu noi: N/A.

Default full-web rămâne NOT_PASS:1FAIL/292PASS/37.65s apoi4FAIL/289PASS/46.38s/bootstrap-timeouts/cauzăUNKNOWN. Vechiul baseline286PASS și isolated3PASS nu le explică. Real controls QA: FAIL37.61s/toast, apoi FAIL16.73s/Cancel409; ambele păstrate. Counter harness-only2, fără al treilea QA larg/default retry. Canonical5400s NOT_RUN/neconsumat; supervisorUNKNOWN; T1/T2/global/acceptarea vizuală neînchise.

Nu s-au rulat full-web/cele122teste, build/browser/native/PG/servicii/model/provider/target, nu s-au citit credentiale/mediu și nu s-au editat repository/docs/skill-uri, stage/commit/push sau alte profile. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Numai acest raport original scratch și captura auxiliară de comenzi au fost create.

Omis intenționat: auditul general, acceptările neschimbate și probele cu efecte. Riscul rămas: geometria/focusul real și aspectul listei nu sunt acceptate vizual, iar blocajele runtime/global nu sunt închise de acest verdict.

## Anexă — output real al comenzilor read-only/SOURCE

```text
$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git rev-parse HEAD
8a02a6c90e77aa7623008e425d69b74e59f1bdf8

exit=0

$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git status --short --branch
## qa/settings-final-controls-a488b26
?? api/.venv
?? cli/.venv
?? web/node_modules

exit=0

$ /home/kali/OmnisAI :: git diff 1629ade HEAD -- web/src/features/engagement/SettingsModelsPage.tsx web/src/features/engagement/SettingsModels.module.css web/src/app/SettingsWizard.test.tsx web/tests/e2e/settings-models.mjs
diff --git a/web/src/app/SettingsWizard.test.tsx b/web/src/app/SettingsWizard.test.tsx
index e3722b5..4427027 100644
--- a/web/src/app/SettingsWizard.test.tsx
+++ b/web/src/app/SettingsWizard.test.tsx
@@ -44,7 +44,7 @@ it.each(['known', 'unknown', 'partial-zero'] as const)('expands a minimal %s usa
   expect(toggle).toHaveFocus(); expect(toggle).toHaveAttribute('aria-expanded', 'true');
   expect(details).toBeVisible();
   const metrics = within(details).getByLabelText('Test usage');
-  expect(within(metrics).getAllByRole('term').map(node => node.textContent)).toEqual(['Input', 'Output', 'Cost']);
+  expect(within(metrics).getAllByRole('term').map(node => node.textContent)).toEqual(['Input tokens', 'Output tokens', 'Cost']);
   expect(within(metrics).getAllByRole('definition').map(node => node.textContent)).toEqual(usage === 'known' ? ['12', '7', '0.001'] : usage === 'unknown' ? ['Unknown', 'Unknown', 'Unknown'] : ['0', 'Unknown', 'Unknown']);
   expect(details).not.toHaveTextContent(/Test completed|Requested model|Observed model|OMNIS_MODEL_TEST_OK|FINISHED|COMPLETED|revision|\$|€/);
   expect(modelRow(entry.model)).not.toHaveTextContent(saved.operation_id!);
diff --git a/web/src/features/engagement/SettingsModels.module.css b/web/src/features/engagement/SettingsModels.module.css
index 1c93dde..67593ba 100644
--- a/web/src/features/engagement/SettingsModels.module.css
+++ b/web/src/features/engagement/SettingsModels.module.css
@@ -23,14 +23,15 @@
 .model { border-top: 1px solid var(--color-divider); padding-block: 4px; }
 .modelRow { display: flex; align-items: center; gap: 12px; }
 .workspace .modelToggle { display: flex; flex: 1; flex-wrap: wrap; align-items: center; gap: 8px 12px; min-width: 0; padding: 10px 4px; text-align: left; background: transparent; border-color: transparent; border-radius: var(--radius-sm); box-shadow: none; font-weight: 400; }
-.modelToggle:hover, .modelToggle[aria-expanded=true] { background: var(--color-elevated); }
+.workspace .modelToggle:hover, .workspace .modelToggle[aria-expanded=true] { background: var(--color-elevated); }
+.workspace .modelToggle:focus-visible { outline: 2px solid var(--color-border); outline-offset: 1px; }
 .modelRow > button:not(.modelToggle) { flex-shrink: 0; }
-.modelDetails { width: fit-content; max-width: 100%; margin: 4px 0 12px; padding: 10px 16px; border: 1px solid var(--surface-hairline); border-radius: var(--radius-lg); background: var(--color-elevated); font-size: 13px; overflow-wrap: anywhere; }
+.modelDetails { width: 280px; max-width: 100%; margin: 8px 0 12px; padding: 4px; font-size: 13px; overflow-wrap: anywhere; }
 .modelDetails[hidden] { display: none; }
-.usage { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; }
-.usage > div { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
+.usage { display: grid; gap: 8px; margin: 0; }
+.usage > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; min-width: 0; }
 .usage dt { color: var(--color-secondary); }
-.usage dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
+.usage dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
 .review .row { padding-block: 12px; }
 .identity { min-width: 0; flex: 1 1 240px; overflow-wrap: anywhere; }
 .identity strong { font-weight: 500; }
diff --git a/web/src/features/engagement/SettingsModelsPage.tsx b/web/src/features/engagement/SettingsModelsPage.tsx
index a844536..43c9391 100644
--- a/web/src/features/engagement/SettingsModelsPage.tsx
+++ b/web/src/features/engagement/SettingsModelsPage.tsx
@@ -383,7 +383,7 @@ export function SettingsModelsPage({ scope }: { scope: string }) {
             {check?.usage_state === 'PARTIAL' && <p className={styles.hint}>Usage is incomplete.</p>}
             <section id={detailsId} hidden={!open} className={styles.modelDetails} aria-label={`Model details for ${entry.model} via ${providerName(connection.provider)}`}>
               {check ? <>
-                <dl className={styles.usage} aria-label="Test usage"><div><dt>Input</dt><dd>{check.input_tokens ?? 'Unknown'}</dd></div><div><dt>Output</dt><dd>{check.output_tokens ?? 'Unknown'}</dd></div><div><dt>Cost</dt><dd>{check.cost_observed ?? 'Unknown'}</dd></div></dl>
+                <dl className={styles.usage} aria-label="Test usage"><div><dt>Input tokens</dt><dd>{check.input_tokens ?? 'Unknown'}</dd></div><div><dt>Output tokens</dt><dd>{check.output_tokens ?? 'Unknown'}</dd></div><div><dt>Cost</dt><dd>{check.cost_observed ?? 'Unknown'}</dd></div></dl>
                 {!needsRecovery && !terminalUnknown && (!passed || !matching || check.observed_model !== check.requested_model) && <button type="button" className={styles.quiet} disabled={checkSelectionBlocked(check)} onClick={() => readCheck(check)}>Read test status</button>}
               </> : <p>{uncertain ? 'No result confirmed. Read back before another test.' : 'No saved test for this model.'}</p>}
             </section>
diff --git a/web/tests/e2e/settings-models.mjs b/web/tests/e2e/settings-models.mjs
index ea73448..94258e0 100644
--- a/web/tests/e2e/settings-models.mjs
+++ b/web/tests/e2e/settings-models.mjs
@@ -299,7 +299,7 @@ export async function runSettingsModels({ page, check, paired, origin, output, s
   await check(modelDetails).toBeFocused(); await check(modelDetails).toHaveAttribute('aria-expanded', 'true');
   await check(test.getByText('Connected', { exact: true })).toBeVisible();
   const usage = test.getByLabel('Test usage', { exact: true });
-  await check(usage.locator('dt')).toHaveText(['Input', 'Output', 'Cost']);
+  await check(usage.locator('dt')).toHaveText(['Input tokens', 'Output tokens', 'Cost']);
   await check(usage.locator('dd')).toHaveText([results[1].input_tokens, results[1].output_tokens, results[1].cost_observed].map(value => value === null ? 'Unknown' : String(value)));
   await check(test.getByText('Operation details', { exact: true })).toHaveCount(0);
   await check(test.getByLabel('Model response', { exact: true })).toHaveCount(0);

exit=0

$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git diff 3fe4a93 HEAD -- web/tests/e2e/settings-models.mjs
diff --git a/web/tests/e2e/settings-models.mjs b/web/tests/e2e/settings-models.mjs
index 2260a16..5cf5ac4 100644
--- a/web/tests/e2e/settings-models.mjs
+++ b/web/tests/e2e/settings-models.mjs
@@ -227,9 +227,16 @@ export async function runSettingsModels({ page, check, paired, origin, output, s
   const cancelled = page.waitForResponse(response => response.url() === `${origin}${tests}/${id}/cancel`);
   await operation.getByRole('button', { name: 'Cancel test', exact: true }).click();
   const cancelReply = await cancelled;
-  assert.equal(cancelReply.status(), 200);
-  assert.equal(cancelReply.request().postDataJSON().expected_state_revision, 2);
   const terminal = await cancelReply.json();
+  assert.equal(cancelReply.status(), 202, JSON.stringify({
+    status: cancelReply.status(),
+    error_code: terminal.error?.code ?? null,
+    expected_state_revision: cancelReply.request().postDataJSON().expected_state_revision,
+    state: terminal.state ?? null,
+    state_revision: terminal.state_revision ?? null,
+    operation_id: terminal.operation_id ?? null,
+  }).slice(0, 4096));
+  assert.equal(cancelReply.request().postDataJSON().expected_state_revision, 2);
   assert.equal(terminal.operation_id, id);
   assert.equal(terminal.state, 'FINISHED');
   assert.equal(terminal.state_revision, 4);
@@ -265,7 +272,7 @@ export async function runSettingsModels({ page, check, paired, origin, output, s
   await check(operation.getByText('Operation details', { exact: true })).toHaveCount(0);
   assert.ok(!(await operation.textContent()).includes(id));
   const usage = operation.getByLabel('Test usage', { exact: true });
-  await check(usage.locator('dt')).toHaveText(['Input', 'Output', 'Cost']);
+  await check(usage.locator('dt')).toHaveText(['Input tokens', 'Output tokens', 'Cost']);
   await check(usage.locator('dd')).toHaveText([terminal.input_tokens, terminal.output_tokens, terminal.cost_observed].map(value => value === null ? 'Unknown' : String(value)));
   await modelDetails.click();
   assert.equal(writes.filter(item => item.path === tests).length, 1);
@@ -311,9 +318,16 @@ export async function runSettingsModels({ page, check, paired, origin, output, s
   const secondCancel = page.waitForResponse(response => response.url() === `${origin}${tests}/${activeId}/cancel`);
   await other.getByRole('button', { name: 'Cancel test', exact: true }).click();
   const secondCancelReply = await secondCancel;
-  assert.equal(secondCancelReply.status(), 200);
-  assert.equal(secondCancelReply.request().postDataJSON().expected_state_revision, 2);
   const secondTerminal = await secondCancelReply.json();
+  assert.equal(secondCancelReply.status(), 202, JSON.stringify({
+    status: secondCancelReply.status(),
+    error_code: secondTerminal.error?.code ?? null,
+    expected_state_revision: secondCancelReply.request().postDataJSON().expected_state_revision,
+    state: secondTerminal.state ?? null,
+    state_revision: secondTerminal.state_revision ?? null,
+    operation_id: secondTerminal.operation_id ?? null,
+  }).slice(0, 4096));
+  assert.equal(secondCancelReply.request().postDataJSON().expected_state_revision, 2);
   assert.equal(secondTerminal.operation_id, activeId);
   assert.equal(secondTerminal.state, 'FINISHED');
   assert.equal(secondTerminal.state_revision, 4);

exit=0

$ /home/kali/OmnisAI :: git show f7b9dd8 -- documents/Omnis_UI_UX_Spec.md web/DESIGN.md
commit f7b9dd8bd623b7554646667d0dff2977b57ac857
Author: bsploit <kovacsemanuel34@gmail.com>
Date:   Thu Oct 29 11:10:45 2026 +0200

    docs(settings): replace rejected usage pill with an elegant vertical list
    
    Why: operator explicitly rejected actual1629ade nativebuild a29d6d75 after click/Space/Enter inspection: white rowoutline looks odd and singlelinecapsule is not elegant; requests simplealignedInputtokens/Outputtokens/Cost list. Scope stays same3 realmetrics underrow, no rawdiagnostics, framework, extraowner or palette. Retainvisiblekeyboardfocus/contrast with restrainedhouse styling, never remove accessibility for aesthetics. Newvisualdirection recorded before productauthoring; still NOT_ACCEPTED.
    
    Verification: canonicalUIHTML regenerated; render--check0/documentation87PASS/diff0. No code/runtime/effects from thiscommit. Separatetechnicalblockers remain: fullweb1FAIL+4FAIL across2runs causeUNKNOWN; QA2Cancel409/unrecordedreason and wrong200oracle versusdeclared202; no newdefault/fullQA/canonical attempt. Rollback: revert onlynewpresentationcontract, notoperatorstate.

diff --git a/documents/Omnis_UI_UX_Spec.md b/documents/Omnis_UI_UX_Spec.md
index b4838b8..a93fb4c 100644
--- a/documents/Omnis_UI_UX_Spec.md
+++ b/documents/Omnis_UI_UX_Spec.md
@@ -158,7 +158,7 @@ Settings API-key-only păstrează layoutul acceptat: conexiune/provider, câmp s
 
 **Settings C selectat, simplificat prin mandat ulterior:** [referința offline](../web/design/settings-final.html) păstrează baseline-ul vizual, iar [contractul funcțional actual](../web/design/settings-final.md) guvernează controalele noi. Coloana Settings este centrată maximum900px în shellul1180px; titlu/taburi/secțiuni/wizard/assignments aliniate, text left-aligned. Păstrăm paleta/fonturile/panourile, controale46px/minimum44×44 și focus/loading stabile. English-only. Un singur Add models global; provider card cu modele/status/acțiuni compacte și Connection options în partea de jos. Nu card separat mare de test sau Test details permanent. Confirmările apar ca notificări discrete dreapta-jos; erorile/UNKNOWN au acțiuni corecte și rămân accesibile până la rezolvare/închidere explicită, cu starea relevantă și în rândul modelului. Nu toast efemer ca singura dovadă a unei erori critice.
 
-**Finalizarea cerută de operator:** rândul principal al modelului este controlul accesibil de expandare; detaliile reale apar imediat dedesubt în aceeași unitate, fără al treilea buton Read check/săgeată. Statusul și acțiunea rămân compacte, cu Test separat de expandare și fără controale interactive imbricate. Citirea/expandarea nu retrimite un test; Cancel și recuperarea operației active/neconfirmate rămân vizibile și cu detaliile închise, fără a le schimba ținta la selectarea istoriei. **Rafinarea vizuală ulterioară cerută pe buildul real:** expandarea este delimitată într-o capsulă fină, minimală, cu valorile reale **Input / Output / Cost**, fără repetarea succesului/identităților egale. **Operation details nu mai apare în UI**; UUID-urile, reviziile, răspunsul tehnic și diagnosticul complet rămân în backend/API pentru depanare, nu se șterg și nu se mută în alt owner. Un mismatch, eșec, rezultat parțial/UNKNOWN sau consum necunoscut păstrează explicația scurtă și recuperarea corectă în context; estetica nu elimină avertismentul ori falsifică eligibilitatea. Confirmarea utilă unică este o pastilă compactă dreapta-jos, fără a acoperi acțiunile/focusul pe mobil; eroarea acționabilă rămâne lângă obiect. Catalogul are progres discret și eroare scurtă în engleză lângă listă, cu cauza inspectabilă secundar, nu statusuri brute duplicate în pagină/wizard/toast. Testul exact salvat, disponibilitatea metadatelor și eligibilitatea pentru assignment sunt fapte distincte prezentate împreună, fără badge verde forțat, revocare/fallback ori refresh upstream implicit. Persistența cheii nu dovedește citirea catalogului. [Mandatul de finalizare](verification/settings-finalization-prompt.md) cere QA pe aplicația reală și acceptarea vizuală a operatorului înainte de unica rulare canonică finală autorizată; această rafinare nu este încă acceptare estetică.
+**Finalizarea cerută de operator:** rândul principal al modelului este controlul accesibil de expandare; detaliile reale apar imediat dedesubt în aceeași unitate, fără al treilea buton Read check/săgeată. Statusul și acțiunea rămân compacte, cu Test separat de expandare și fără controale interactive imbricate. Citirea/expandarea nu retrimite un test; Cancel și recuperarea operației active/neconfirmate rămân vizibile și cu detaliile închise, fără a le schimba ținta la selectarea istoriei. **Ultimul feedback vizual pe buildul real respinge pastila cu toate valorile pe o linie și conturul alb mare al rândului:** expandarea devine o listă verticală elegantă, simplă, cu cele trei rânduri **Input tokens / Output tokens / Cost**, etichete și valori reale aliniate, fără repetarea succesului/identităților egale ori alt panou decorativ. Focusul de tastatură rămâne vizibil și contrastant, dar discret, folosind stilul casei; nu se elimină pentru estetică. **Operation details nu mai apare în UI**; UUID-urile, reviziile, răspunsul tehnic și diagnosticul complet rămân în backend/API pentru depanare, nu se șterg și nu se mută în alt owner. Un mismatch, eșec, rezultat parțial/UNKNOWN sau consum necunoscut păstrează explicația scurtă și recuperarea corectă în context; estetica nu elimină avertismentul ori falsifică eligibilitatea. Confirmarea utilă unică este o pastilă compactă dreapta-jos, fără a acoperi acțiunile/focusul pe mobil; eroarea acționabilă rămâne lângă obiect. Catalogul are progres discret și eroare scurtă în engleză lângă listă, cu cauza inspectabilă secundar, nu statusuri brute duplicate în pagină/wizard/toast. Testul exact salvat, disponibilitatea metadatelor și eligibilitatea pentru assignment sunt fapte distincte prezentate împreună, fără badge verde forțat, revocare/fallback ori refresh upstream implicit. Persistența cheii nu dovedește citirea catalogului. [Mandatul de finalizare](verification/settings-finalization-prompt.md) cere QA pe aplicația reală și acceptarea vizuală a operatorului înainte de unica rulare canonică finală autorizată; această rafinare nu este încă acceptare estetică.
 
 Connection→Models→Review păstrează saved key și confirmarea Save/readback înaintea catalogului explicit. Eliminăm explicațiile repetate, reload/catalog noise și saltul necerut de scroll/focus; progresul rămâne accesibil fără a muta focusul ales de operator. Search și scrollbar folosesc stilul casei; chips au glyph X mic, păstrând zona de apăsare și numele accesibil. Review arată toate modelele, fără selector de test redundant, cu acord scurt explicit pentru numărul de verificări și costul posibil. Save models este local; Save & connect execută secvența finită din arhitectură§5.3 și afișează progresul/Cancel fără card duplicat. Connected înseamnă ultimul test exact reușit și încă actual, nu GET catalog, configurație salvată sau promisiune de disponibilitate continuă. Stările Not tested/Connecting/Failed/Unconfirmed/Unavailable rămân distincte; nu resetarea silențioasă a erorilor, defaults sau override-urilor. Disable/rotirea invalidează wizardul și badge-ul; Retry nu retrimite un efect UNKNOWN.
 

exit=0

$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git ls-files *model_test_routes.py *settings*cancel* *settings*proof*
api/src/omnis/modules/runs/model_test_routes.py
api/tests/test_model_test_routes.py

exit=0

$ /home/kali/OmnisAI :: git diff --check

exit=0

$ /home/kali/OmnisAI :: /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node --check /home/kali/OmnisAI/web/tests/e2e/settings-models.mjs

exit=0

$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git diff --check

exit=0

$ /home/kali/OmnisAI :: /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node --check /home/kali/.hermes/cache/scratch/fqa-a488b26/web/tests/e2e/settings-models.mjs

exit=0

$ /home/kali/OmnisAI :: /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node --version
v24.21.0

exit=0

$ /home/kali/OmnisAI :: /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node -
SOURCE_SYNTHETIC first 202 2 ACCEPT json_reads=1
SOURCE_SYNTHETIC first 200 2 REJECT json_reads=1
SOURCE_SYNTHETIC first 409 2 REJECT json_reads=1
SOURCE_SYNTHETIC first 202 1 REJECT json_reads=1

exit=0

$ /home/kali/OmnisAI :: /home/kali/.local/share/omnis-toolchains/node-v24.21.0-linux-x64/bin/node -
SOURCE_SYNTHETIC second 202 2 ACCEPT json_reads=1
SOURCE_SYNTHETIC second 200 2 REJECT json_reads=1
SOURCE_SYNTHETIC second 409 2 REJECT json_reads=1
SOURCE_SYNTHETIC second 202 1 REJECT json_reads=1

exit=0

END_HEAD /home/kali/OmnisAI 97d36ace48feea276086e2aba5fa1d3ba126d1df
$ /home/kali/OmnisAI :: git status --short --branch
## checkpoint/p2-batch2-pause-20261015...origin/checkpoint/p2-batch2-pause-20261015 [ahead 76]
?? documents/Omnis_Notite_Originale.html
?? tempkey.txt
exit=0
END_HEAD /home/kali/.hermes/cache/scratch/fqa-a488b26 8a02a6c90e77aa7623008e425d69b74e59f1bdf8
$ /home/kali/.hermes/cache/scratch/fqa-a488b26 :: git status --short --branch
## qa/settings-final-controls-a488b26
?? api/.venv
?? cli/.venv
?? web/node_modules
exit=0
END_EXACT /home/kali/OmnisAI/web/src/features/engagement/SettingsModelsPage.tsx blob=43c9391a11472cc2c002eea3e75b2c6b4492fc5e sha256=800b0c7fc992f56e5a8cbd31a1426a32fd770b381ddc0f1559a548b6390d07b6
END_EXACT /home/kali/OmnisAI/web/src/features/engagement/SettingsModels.module.css blob=67593ba97f740a5f0fdc84578f08f76fcf8f7c3a sha256=c5a032531f00335a28698906cca9e97ddcc96cf363c28cddfae58023c527232f
END_EXACT /home/kali/OmnisAI/web/src/app/SettingsWizard.test.tsx blob=4427027a68a69e0b3acddc236ee6bffbb106c461 sha256=a5e0339fc54533147ceaa062d2eac6a600bfad8e494e8ecef08ab341d844fe68
END_EXACT /home/kali/OmnisAI/web/tests/e2e/settings-models.mjs blob=94258e04307cd67dcf927220feac2c1981ea12b6 sha256=d8f5b9f0cbf9c3f54f06ced598d3c0a4fd8cfd1038b47171be61f3d062156a83
END_EXACT /home/kali/.hermes/cache/scratch/fqa-a488b26/web/tests/e2e/settings-models.mjs blob=5cf5ac43996b395a742fe9d81f3bf839a17249d1 sha256=e10d67766cbedc4a4695cbe41f6a1dcfe4e5f7977a8ccb3bb8ebf0cce5b47a79
UNCHANGED_QA_PRODUCER /home/kali/.hermes/cache/scratch/fqa-a488b26/api/tests/test_model_test_v2.py sha256=34cf202c633a42710ba291dfc668be24c3148d2de0663f001041169667843dce
SOURCE_TREES_IDENTICAL web/src
SOURCE_TREES_IDENTICAL api/src
SOURCE_TREES_IDENTICAL cli/src
ACTUAL_SOURCE_HTTP_CANCEL_ASSERTION (read only; not executed):
1283:                         json={
1284:                             "action": "cancel",
1285:                             **context,
1286:                             "catalog_command_id": waiting_id,
1287:                             "command_id": str(uuid4()),
1288:                         },
1289:                         headers=headers,
1290:                     )
1291:                     assert cancelled.status_code == 202 and cancelled.json()["state"] == "FAILED"
1292:                     assert cancelled.json()["reason"] == "CANCELLED_OR_STOPPED"
1293:                     assert not owner.tasks
1793:                         cancelled = await http.post(
1794:                             "/api/v1/model-test/" + second_id + "/cancel",
1795:                             json={
1796:                                 "command_id": str(uuid4()),
1797:                                 "expected_state_revision": before["state_revision"],
1798:                             },
1799:                             headers=headers,
1800:                         )
1801:                         assert cancelled.status_code == 202
1802:                         assert cancelled.json()["state"] == "FINISHED"
1803:                         assert cancelled.json()["finish_reason"] == "CANCELLED"
PRIOR_REPORT_SHA256 25a602f261bcff0fe7bd948fdcf23e138ac9131fbaff94a41a745dd0180ee397
```
