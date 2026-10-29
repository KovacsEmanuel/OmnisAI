# R1 — focused re-review READ-ONLY ed611aa

**Verdict: SOURCE_ADMITTED_FOR_NARROW_AFFECTED_QA.** Findings SOURCE blocante noi: **[]**. Admitere a deltei UI/callerilor, nu PASS independent runtime/browser, integrare, rollout sau T2. R2 păstrează ownershipul oracle-ului API.

## Snapshot și dovada read-only

- Root exact: `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`.
- **IDENTITY_BEGIN = IDENTITY_END:** HEAD `ed611aa40c90f62f4f511cc1951a68970e2ba51b`; tree `38463d72bb4271bc11ec6f05074be4cf9d108ada`.
- La ambele citiri: tracked/index clean; exclusiv aceleași trei căi untracked preexistente `api/.venv`, `tools/development/anti-slop/node_modules`, `web/node_modules`. Nicio editare/stage/commit în checkout.
- Bază de comparație: `190fae18e57e115a8a86559cec386b9ea147fd4b`. Delta are exact cele cinci căi declarate: `api/tests/test_model_test_v2.py`, `web/src/features/engagement/SettingsModelsPage.tsx`, `web/src/app/SettingsModels.test.tsx`, `web/tests/e2e/run.mjs`, `web/tests/e2e/settings-models.mjs`. Reviewul meu privește ultimele patru și callerii direcți, nu oracle-ul atribuit R2.
- Manifest `/home/kali/.hermes/cache/scratch/remove-model-freeze-ed611aa.json`: SHA256 verificat `663ba083b57e00dcee29471bf5aaf5a5b0e01594e0389e68d6892adf41b0047a`. Verificat independent match blob+SHA256 pentru cele patru fișiere UI; cele 53 bindings complete rămân verificarea declarată a părintelui, nu o pretind repetată.
- Blobs UI: page `5a6aae048bb2325d2e915245bbdc47be78572256`; component tests `d8890e238f1fc64500f482b2f921c1fadb6fb12f`; runner `ace22bdb1f198de9e1a47fca05732f7735006d7b`; journey `f7cfb648747db93c4ac3f6ae6c89760f40bf86af`.
- `git diff --quiet 190fae1..HEAD -- api/src`, respectiv `cli/src` și CSS-ul Settings: fiecare exit0, neschimbate. Nu redeschid backend/CLI/storage/migrarea0017 sau baseline-ul vizual.

## Contract → cod → dispoziție

### B — explicație contextuală in-use: CLOSED_SOURCE_SCOPED

Criteriu: `web/design/settings-final.md:100-114`, UI/UX:159-171, arhitectură:341: dependencies enumerate lângă obiect, reassign explicit, fără autounassign/replacement, fără pierderea istoricului/Cancel.

`SettingsModelsPage.tsx:325-334,392,413-419`: același predicat pentru render și handler verifică cele patru roluri prin connection ID și model exact, intenționat fără a permite retragerea doar fiindcă revizia conexiunii a devenit stale. Explicația persistentă este în detaliile aceluiași rând și legată prin `aria-describedby`; known-in-use este native-disabled și nu deschide confirmarea. Nu mai depinde de un mesaj afișat numai în recovery la începutul paginii. Predicatul nu scrie assignments. Refuzul autoritativ MODEL_IN_USE și CAS rămân neschimbate pentru stare concurentă/necunoscută.

`SettingsModels.test.tsx:112-125` verifică localitatea, disabled, asocierea explicației, zero confirmări/zero writes pentru Default/Brain/Validator; rolul Investigator urmează același set finit. Nu cer o parametrizare nouă pentru fiecare rol fără o ramură diferită. Journey-ul nativ: `settings-models.mjs:59-73`, hint vizibil în viewport, Tab la Test și apoi sare controlul disabled, zero writes. CSS/poziționarea Remove nu au fost redesenate.

### C — fallback comun și callerii: CLOSED_SOURCE_SCOPED / runtime independent pending

`SettingsModelsPage.tsx:147-168,332-340`: helperul capturează inițiatorul, urmărește `focusin`, iar finalizarea amână decizia într-un RAF. Fallbackul la Add models cere simultan lifetime viu, lipsa unei mutări observate, origin deconectat și focus efectiv pe body. Nu mai există focus necondiționat după succes. Listenerul este scos în callback înaintea oricărei tentative de focus; ambele apeluri sunt finalizate din `finally`, inclusiv error/abort. Cleanupul existent :107-110 avortează lifetime și citirea la unmount, iar guardul RAF împiedică focusul după unmount. Nu am identificat un scenariu concret de focus post-lifetime sau de listener activ cu efect asupra altei pagini; nu propun un owner/abstraction suplimentar pentru o posibilitate abstractă de scheduling.

Callerii verificați:
- Remove normal: wrapperul acoperă întregul `mutate`, inclusiv exact receipt, reload și busy cleanup. Dismiss nu instalează listener și nu scrie. Refuz/error cu inițiator încă prezent nu trimite focusul la Add.
- Read current state în recovery (:348-352): controlul dispare după readback confirmat; helperul oferă fallback dacă focusul revine la body.
- Header Reload / Recover exact receipt (:343-345): butonul supraviețuiește și își schimbă numai numele/starea, deci `origin.isConnected` conservă focusul. Nu există motiv pentru un fallback forțat aici.
- `readCheck` (:269-272): doar ramura fără check confirmat apelează `readCurrent`; helperul nu schimbă operația/Cancel, nu pornește un Test și nu mută focusul dacă operatorul l-a mutat ori inițiatorul rămâne.

Gardurile auth/readPrivate/epoch, blocked/busy, pending command identity, recovery receive-only și continuările/Cancel sunt nemodificate. Noul helper nu introduce resend, refresh provider sau auto-reassign. `useBrowserSession.ts:113-124` rămâne fence-ul citirilor private; nu am reluat auditul său global.

`SettingsModels.test.tsx:84-110` ține în așteptare exact receipt și verifică normal/recovered × focus nemutat/mutat; este SOURCE/component, nu native QA. Alegerea Models ca destinație păstrează un control existent în DOM și demonstrează că wrapperul nu fură focusul. Nu maschează testul de fallback cu focus forțat la Add.

## Admiterea probei native și limitele ei

`settings-models.mjs:74-124` nu mai aplică `.focus()` pe Remove după Tab: pornește de la disclosure, Tab→Test→Tab→Remove la1440/1280/390/320. Enter activează confirmarea, dismiss păstrează Remove și zero writes. Acceptul folosește dialog API Playwright; **nu** dovedește Enter/Escape fizic în fereastra OS. Faultul pierde replyul numai după HTTP200 real; recovery activează controlul existent prin Enter și verifică focus Add după dispariția rândului/inițiatorului. Inițializarea focusului pe disclosure/recovery nu este revendicată ca navigare Tab completă din capul paginii.

`run.mjs:142-144` păstrează fullPage=true implicit pentru callerii existenți; numai capturile noi opt-in sunt viewport. Captura și geometry/hit-testul urmează aceeași centrare/scroll, fără o schimbare de produs/skip-link. Nu am inspectat PNG-urile și nu emit acceptare estetică din sursă.

Am citit read-only rezultatul public `pytest-14/test_api_pg_sdk_protocol_and_r0/browser-result.json`: passed=true, Chromium153.0.8010.12, lostReplyRecovered=true, apiRestartReadback=true, externalRequests0/pageErrors0, secretChecks=true. Receipturile developer `db-188755bf15374df9/gate.log.result.json` și `db-a5e5b7315ac0443f/gate.log.result.json` au code0/family_drained=true. Sunt **dovezi DEVELOPER, nu execuție independentă de mine**; nu pretind readback nou al cleanupului sau validarea oracle-ului R2. Cele109 componente,4PG și1browser sunt raportarea developerului din checkpoint, nu o execuție R1.

**Decizie pentru QA:** este admisă prima probă independentă bounded pe consumerul existent `test-settings-remove-ui-pg` și freeze-ul actual, după verdictul complementar R2 și preflightul părintelui. Ea trebuie să stabilească noul hint contextual, Tab/skip-disabled/dismiss, recovered-receipt fallback, readback/no-resend și inspecția capturilor. Lipsa acestei QA nu este un blocker SOURCE circular.

Normal-success și moved-focus sunt în prezent numai component; **native direct-success/moved-focus NOT_RUN** rămâne o limită explicită, nu un PASS transferat. Nu identific o obligație de a adăuga încă un journey nativ normal înaintea admiterii celui existent: ambele căi folosesc același test DOM de disconnection/body și aceeași actualizare a cache-ului; normalul are în plus await-ul invalidării înaintea finalizării, nu un nou control/focus mechanism. Nu există în bytes citite un reproducer specific care să ceară extinderea harnessului. Dacă verdictul final va pretinde explicit native direct-success sau native no-focus-steal, acea afirmație cere observarea acelei căi; nu o acordă acest raport.

## Verificări proprii / limite păstrate

Comenzi read-only: Git status/HEAD/tree/diff, hash/blob checks pentru cele4fișiere, `git diff --check 190fae1..HEAD` exit0; `node --check web/tests/e2e/run.mjs` exit0; `node --check web/tests/e2e/settings-models.mjs` exit0. Niciun test component/PG/browser/build executat.

Originalele R1/R2 pe c4d465c și190fae1 și dispozițiile R1-P01/P02/R2-P02 CLOSED_SOURCE/PROOF_SCOPED rămân la scope-ul lor; această re-review nu le anulează și nu le extinde. R2-P01 rămâne adjudecarea separată R2. Operator RECOVERY_REQUIRED/schema16, R2-R01 BLOCKED_OPERATOR_UPGRADE, recovery fără autorizare; Cancel409/default-web2FAIL/counter2/canonical5400NOT_RUN neschimbate. Nu am inspectat operatorul, env, credențiale, fișierele protejate sau loguri PG raw; zero efecte runtime/provider/push. Reticle NOT_INTEGRATED/NOT_RUN; Chisel BLOCKED_NO_GO.

Singurul fișier creat: acest raport scratch, în afara checkoutului. Părintele deține adjudecarea, QA și integrarea.

Omis: reauditul scope-ului neschimbat/R2, execuția runtime și inspecția imaginilor. Risc: SOURCE admission nu certifică încă QA independentă pe ed611aa, OS-dialog keys ori upgrade/recovery operator.
