# R2 — re-review independent focalizat, a4f5dbc

## Verdict

**APPROVED_SOURCE_SCOPED. R2-01 și R2-02: CLOSED_APPROVED_SOURCE_SCOPED pe snapshotul de mai jos. Niciun finding nou concret în remediile și impactul restrâns inspectate.**

**SOURCE_APPROVED_FOR_EXISTING_BOUNDED_QA:** recomand admiterea QA reale prin consumerul existent `test-settings-remove-ui-pg`, după preflightul fără efecte și admiterea efectelor de către părinte. Nu cer ca această QA să fi trecut deja pentru a-i permite execuția. Acesta nu este runtime PASS, acceptare all-controls, integrare, instalare sau aprobare estetică.

## Identitate și scope

- Worktree: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`.
- Bază re-review: `d34f11066a93c15ce65ce4a8879986e63e025dbd`.
- HEAD: `a4f5dbc67221e3c0387a88db7bb8e78de4c6ccfa`; tree: `3d1068bbf0c2be227153357e746f21fc526c3da6`.
- Commituri fix: `36741e717f54e5cfeb491a233604f969f5abf860`, `a4f5dbc67221e3c0387a88db7bb8e78de4c6ccfa`.
- Freeze: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r2fix-freeze-20261029.json`, SHA256 `ccf982f039d1e145ba884e94d391e03b5f72ddbf3bb26e245a4d42d664125534`.
- Diff SHA256: `6cbe93d3d331b0c0ea61b85c10c88df1155195dc7d2dfcdb4bac356c37332fc6`.
- Exact două fișiere schimbate: `web/src/features/engagement/SettingsModelsPage.tsx` și `web/src/app/SettingsModels.test.tsx`; 87 inserări/6 ștergeri. Fără delta backend, API, schema, CSS, dependențe, config, exports sau fixture/mjs.
- Verificat independent cu Git/hashlib: HEAD/tree/diff, toate cele11 blobs/SHA sursă, egalitatea celor9 fișiere neschimbate cu baza, manifestul build și cele4 assets, SHA-urile ambelor reviewuri originale și ale logurilor din freeze. Toate conforme, exit0; tracked worktree/index curate. Cele4 symlinkuri de dependențe preexistente nu au fost adoptate sau modificate.
- Scope afectat: calculul row status și callerii `startTest`/`connectEntries`/`saveKeys`/`SettingsAssignments`; efectul notificării, dismiss și lifetime-ul `ProviderSettings`; cele4 regresii adăugate și controalele SOURCE existente pentru Save & connect. Nu am redeschis auditul celor9 fișiere neschimbate.

## Dispoziții explicite

| Finding | Dispoziție | Cod și dovadă | Impact restrâns |
|---|---|---|---|
| **R2-01 — false Connecting la Save local cu operație istorică terminată** | **CLOSED_APPROVED_SOURCE_SCOPED** | `SettingsModelsPage.tsx:98,420` cere acum `operationPending` împreună cu `bound` și `sending`. Pentru operația observată FINISHED/COMPLETED, un `save_selection` nu mai satisface `starting`. Regresia nouă ține receiptul Save în așteptare, cere exact `['save_selection']`, Connected fără Connecting, apoi Connected și după settlement. Proba originală părinte: FAIL înainte → PASS după fix. | `startTest:246-263` setează operația nouă și entry-ul înainte de await; în admiterea ținută, operația nouă fără rezultat rămâne pending. `connectEntries:291-328` și ramura `connecting` de la `:434` păstrează progresul până la latest readback exact, fără Connected prematur. Controalele SOURCE neschimbate din `SettingsWizard.test.tsx:377-429` verifică ambele frontiere. Payloadul, consentul, dispatchul și Cancel/Stop nu sunt modificate. |
| **R2-02 — timerul elimină Dismiss focalizat și pierde focusul în BODY** | **CLOSED_APPROVED_SOURCE_SCOPED** | `SettingsModelsPage.tsx:125-150`: înainte de placement, timerul este oprit și timpul efectiv consumat este scăzut; `node.contains(document.activeElement)` suspendă expirarea și repoziționarea. `focusout` reapelează prin microtask după stabilizarea focusului, inclusiv la blur în BODY. Regresiile verifică păstrarea focusului peste5s, ieșire spre BODY/control nou și expirarea numai după timpul rămas; proba originală părinte trece. | `:131,149` refuză callbackul vechi după cleanup prin `disposed`, anulează timerul și dezabonează evenimentele/observerul. La focusout→focusin urmat de microtask, fiecare apel anulează timerul anterior; în interior nu pornește altul. La coliziune, notificarea focalizată rămâne în loc; după blur poate fi ascunsă fără să consume timpul rămas și redevine expirabilă când există spațiu. Nu există apel nou `.focus()` sau furt de focus. |

### Verificări de impact, fără finding nou

- **Erori/recovery:** lista `confirmations` și filtrul `:122-124` sunt neschimbate; timerul nu primește erorile/uncertitudinea. Recovery contextual `:489-496` rămâne persistent; testul existent de incertitudine este păstrat.
- **Focus și cleanup:** păstrarea poziției este intenționată numai cât timp focusul rămâne în notificare. Ieșirea spre alt control nu îl refocalizează. La înlocuirea notificării sau unmount, callbackurile focusout/ResizeObserver vechi nu pot programa un timer pe lifetime-ul nou. Același guard acoperă cleanup/replay StrictMode la nivel SOURCE; nu pretind o probă nouă dedicată StrictMode pentru timer.
- **Callerul de Save:** `SettingsAssignments.tsx:46-49` rămâne `save_selection` prin `saveKeys`/`mutate`, cu receipt exact și readback existente, fără model Start. Nu sunt schimbate datele salvate sau suprafețele de secrete/efecte.

## Dovezi reutilizate, nu rerulate

- Review R1 original: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r1-independent-d34f110-20261029.json`, SHA256 `740e2894f2fc638e433c126402750f48f909cf87422d79c8a7d5505bb5f81e4b`.
- Review R2 original: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r2-review-d34f110-20261029.md`, SHA256 `88984b630f016264a9db7797b0f04a72e2d3437fb4344fa245e10c10f3ea7195`. Concluziile sale neschimbate se păstrează; numai cele două findings primesc dispozițiile de mai sus.
- `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r2-parent-red.log`: cele2 probe originale eșuează la aserțiunile de produs înainte de fix. `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r2-parent-green.log`: aceleași2 probe PASS pe fix; SHA256 green `48575a27358abb9baaf05eafd4500ef30f6f93c38b88c31d7732b6b46cda16f3`. Am citit și probele/configul: importă direct App/sursa worktree-ului, fără copie de producție patchuită.
- Affected după ultima editare: `npm test -- src/app/SettingsModels.test.tsx src/app/SettingsWizard.test.tsx src/app/ProviderKeySettings.test.tsx` — **153 PASS/3 fișiere, exit0**,32.1s wrapper; originalul `/home/kali/.hermes/cache/scratch/settings-inline-feedback-r2fix-verified-affected.log` citit.
- `npm run lint`, `npm run typecheck`, `npm run build` — **exit0** în logurile finale frozen citite; buildul include contract/design check și manifestul celor4 assets. Am verificat bytes ai buildului, nu am reconstruit produsul.
- Rulat în acest re-review: verificările directe Git/hashlib de mai sus, `git diff --check d34f11066a93c15ce65ce4a8879986e63e025dbd..a4f5dbc67221e3c0387a88db7bb8e78de4c6ccfa`, status/index și difful complet al celor2 fișiere — **exit0**. Nu am rerulat cele153 teste sau cele2 probe: nu am identificat un defect nou care să justifice reluarea.

## Admiterea QA și limitele acceptării

Consumerul și oracolele sale nu au delta în acest fix; aprobările R1/R2 pentru frontiera sa bounded sunt reutilizabile. Comanda existentă, din worktree-ul candidat, rămâne:

```sh
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-remove-ui-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600
```

Înaintea efectelor, părintele/QA verifică prerechizitele existente browser/PG/UID/mounturi/env și leagă ownerul fresh, deadline-ul și cleanup/readback exact. Nu autorizez operator API/UI, provider upstream sau model real; fixture-ul local sintetic este frontiera propusă. Nu introduc target, harness sau excepție nouă.

Inventarul anterior **55 situri JSX +3 navigări** este neschimbat, nu a fost renumărat și nu este coverage. Mandatul Models UX all-controls rămâne de demonstrat prin probele admise și raportarea explicită a golurilor; un PASS al journey-ului bounded nu certifică automat toate controalele/stările. Aceste goluri nu sunt un nou blocker SOURCE pentru a începe QA.

**Propunere de status pentru părinte:** fixurile IMPLEMENTED; dovezi SOURCE PASS_LOCAL_RECORDED; re-review APPROVED_SOURCE_SCOPED; QA reală ADMISIBILĂ_BOUNDED/NOT_RUN aici. Adjudecarea și integrarea aparțin părintelui. T1 NOT_CLOSED, legacy settings_ui/counter2 EXHAUSTED, FAIL-urile existente și supervisor UNKNOWN rămân neschimbate.

## Fișiere și neexecutat

Creat numai acest raport original în scratch. Nicio modificare de produs/test/config/jurnal/skill, commit, push sau efect runtime; fișierele protejate nu au fost citite sau hash-uite. Reticle NOT_INTEGRATED/neexecutat; Chisel BLOCKED_NO_GO.

Am omis auditul nou, rerulările neschimbate și orice API/PG/Docker/browser/provider/operator/canonical/default-full/T2. Risc rămas: geometria/focusul în browserul real, acoperirea efectivă all-controls și estetica nu sunt certificate de acest review SOURCE.
