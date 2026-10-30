# Review independent — dbf3a13 / Stop → receive-only Read

## Verdict

**ADMIT_SCOPED_FIRST_MINI_PROBE** pe freeze-ul verificat; **niciun finding blocant demonstrat** pentru prima mini-probă. Nu este runtime PASS, acceptare Models/T1, integrare sau autorizare de rerun complet. Orchestratorul păstrează admiterea efectelor/preflightului și bugetul unic.

- HEAD `dbf3a13738b728c93b537578679693e61e5bedd3`, tree `1964a77927768b853f2f04e8e8019fc0271260ad`, base `baf592220415b7e5d199d77b71c1538e9dcec748`.
- Toate cele 7 blobs și SHA256 din `freeze.json` coincid cu fișierele worktree; diff SHA256 `a629fc7842b81743d94e44e2e27bdaf6997e75c598e7485b324e184dcb65812e` coincide. Delta: 222 additions/12 deletions, test/runner-only. Tracked/index curate; dependency links preexistente neatinse.

Cerință → consumer → risc → decizie: mandat §3 Stop/readback → built App/paired API/owner PG/TLS peer existente → succes din operație greșită, redispatch/Cancel sau confundarea Stop cu continuarea sănătoasă → admiterea unei singure probe înguste, nu promovarea dovezilor vechi.

## Oracol și efecte

1. `web/tests/e2e/settings-models.mjs:341–360`: reține răspunsul REAL202, nu substituie admiterea. Verifică wizard închis,01 Connecting și02 Not tested, apoi Stop înainte să elibereze răspunsul. Astfel un Stop care nu întrerupe continuarea ar încerca al doilea Start și ar cădea, nu ar primi PASS.
2. `:361–384`: settlementul folosește GET pe aceeași operation ID; apoi butonul real Read produce exact și latest. Ambele cer200, aceeași operation/entry/connection și revizii, current=true, FINISHED/rev3, COMPLETED/COMPLETED, model01/cap64 și proiecții egale. Nu deduce rezultatul din simplul text Connected.
3. `api/tests/test_model_test_v2.py:611–615,725–755`: interzice Cancel și al doilea Start ÎNAINTE de owner; verifică exact două catalog GET și un model POST, peer01 finalizat, zero workers/settlement_failed, aceeași generation/op/entry, readback owner exact=latest și concordanța cu browserul, două entries/o operație/un SENT, fără assignment. `settings-models.mjs:385–393` mai cere02 Not tested/latest404 și lista exactă a intențiilor browserului. Nu există allowance nou generic pentru trafic.
4. Receive-only este real: `model_test_runtime.py:314–321` tratează read exclusiv prin view; `SettingsModelsPage.tsx:265–274` citește exact apoi latest, fără Start. `:291–328,365` arată separarea dintre abortarea continuării și readback; sursele runtime sunt neschimbate și nu au fost reauditate.

## Observație, limite și remedii minime

- `settings-models.mjs:346,362–375,396–398` păstrează admiterea, ultimul settlement și exact/latest înaintea aserțiunilor finale; finally scrie JSON și la assertion failure. `test_model_test_v2.py:638–653,710–724` păstrează comenzile, răspunsurile proiectate, peerul și workerii înainte de owner drain. Acestea discriminează operație activă/terminală versus UI care nu reflectă readbackul.
- **Limită neblocantă:** mini-proba nu înregistrează `document.visibilityState`, `document.hasFocus()` sau un snapshot UI între release și Read. Nu poate atribui FAIL-ul istoric pollingului/focusului și nu poate demonstra că Connected trebuia să apară automat după Stop. Pentru această admitere nu depinde de acel polling: settlementul este GET explicit, apoi Read explicit. Dacă diagnosticul următor chiar depinde de auto-polling, remediul minim este o observație nesensibilă visibility/focus + starea rândului la frontiera respectivă, nu timeout mai mare, alt harness sau fix de produs presupus.
- **Limită de scope:** proiecția mini nu compară toate câmpurile DTO (de exemplu observed_model/requested_provider); nu trebuie raportată ca egalitate byte-exact integrală a răspunsurilor. Identitatea/reviziile/current cerute aici sunt explicit comparate, iar Connected trece prin consumerul existent. Nicio matrice generală nouă nu este necesară pentru prima probă.
- Healthy full route `settings-models.mjs:220–242` nu mai apasă Stop și păstrează verificările ulterioare exact/terminal/current/latest. Este **NOT_RUN** și rămâne obligatorie separat; mini-proba nu o înlocuiește.
- SOURCE marker absent/1PASS99skipped nu demonstrează cauză sau vindecarea vechiului4PASS/1FAIL. Acel FAIL și contoarele legacy default-web2/SOURCE2 rămân deschise și nu au fost resetate.

## Deadline și cleanup

Browser communicate120s (`test_web_e2e.py:357`), expect15s (`run.mjs:16`), waits15s și owner settle15s sunt păstrate. Runner600s trebuie transmis explicit prin argv-ul existent; defaultul runnerului nu este600. Scenariul nou are numai etapa before, un browser/fără API restart. Page routes se încheie cu resolve + unrouteAll(wait), fără eliminarea allowlistului global context. Cleanupul existent rămâne: owned API/browser family, heartbeat, owner drain, sender/relay/server/peer tasks și lease/engine (`test_model_test_v2.py:2797–2831`). Nu există modificare de transport/deadline produs.

## Verificări executate / efecte

Read-only Git/status/diff și citire focalizată contract/calleri; verificare programatică freeze7/7 și diff; `git diff --check <base> <head>` exit0; `node --check` pentru cele două mjs exit0; `ast.parse` pentru cele trei fișiere Python exit0. Snapshotul HEAD/tree/clean tracked reconfirmat la sfârșit.

Nu am executat SOURCE, PG, API, browser, build, provider, servicii sau comenzi operator; nu am accesat protected files/credentials/env/DSN/raw Docker. Nu am modificat repo-uri și nu am comis. Singurul fișier creat este acest raport scratch. Reticle: NOT_APPLICABLE acestei revizuiri statice; Chisel: BLOCKED_NO_GO.

Risc rămas: admiterea permite să aflăm rezultatul, nu îl garantează; orice FAIL trebuie păstrat și adjudecat din observațiile aceleiași operații, fără retry efectual ori promovarea acceptării T1.
