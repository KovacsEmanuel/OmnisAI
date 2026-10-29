# R2 — Remove model, review independent read-only

## Verdict și identitate

**APPROVED_SOURCE_SCOPED pentru auth/limite/admission și serializarea writerilor; acceptarea end-to-end și rolloutul rămân BLOCKED/NOT_RUN.** Nu am confirmat un nou defect blocant de implementare în acest scope. Lipsurile de probă de mai jos nu sunt prezentate ca race-uri demonstrate și aprobarea SOURCE nu le închide.

- Root: `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`; branch `feat/settings-remove-model`.
- Base `fa5451e9a9b64c1f922c42a664d818708d00ae34`; HEAD `c4d465c072ebbd246bd882441a7465b55b0b2ab6`; tree `19255f793ed90f78c59bf5f4e6f557691b10cd0f`.
- La început și sfârșit: toate cele46 fișiere corespund blob/SHA256 din `remove-model-freeze.json`; tracked/index clean. La sfârșit: și cele5 fișiere dist corespund manifestului. Cele3 untracked preexistente sunt `api/.venv`, `tools/development/anti-slop/node_modules`, `web/node_modules`; nu le-am modificat.
- Citite AGENTS/README CURRENT/CONTRIBUTING, contractul Remove din `web/design/settings-final.md:100–114`, arhitectura §5.3 și procedurile de review/API/release. CURRENT-ul README cu READY24 este istoric față de informația primită: operator UNAVAILABLE/RECOVERY_REQUIRED, fără autorizație de recovery.

## Blocante de cod

**Niciunul confirmat independent în scope-ul R2.** Nu este asigurare universală de absență a defectelor; UI/persistența istorică/migrarea funcțională au reviewul complementar R1.

## Findings — lipsuri de probă

### R2-P01 — MEDIUM — Overlapurile Remove nu sunt probate la consumerul real

- **Fișier:linie:** `api/tests/test_provider_key_api.py:375–442` (compară `:341`, gather pentru SaveModels); calleri reali `provider_key_service.py:241–249,333–348`, `provider_model_service.py:201–250`, `runs/model_test_runtime.py:327–345,369–441`.
- **Scenariu/reproducer:** Remove și SaveSelection care atribuie exact intrarea, respectiv Remove și entry Test start, lansate concurent, forțând fiecare ordine de admitere. Testul nou face Remove, apoi un Save stale **secvențial**; rândul NEEDS_RECONCILIATION este inserat sintetic, nu provine din Test start. Aceste probe nu demonstrează overlapul declarat. Nici Remove–SaveModels nu are overlap nou demonstrat.
- **Criteriu:** contractul cere linearizare reală între Remove/SaveModels/SaveSelection/Test start; shared-helper assertions sau două cereri secvențiale nu sunt proba ambelor ordini.
- **Remediu minim:** o probă bounded pe consumerii existenți HTTP/control/owner/PG, fără provider, cu ambele ordini pentru perechile afectate. SaveSelection-first ⇒ MODEL_IN_USE; Remove-first ⇒ MODEL_NOT_REGISTERED la noua atribuire. Test-start-first ⇒ OPERATION_ACTIVE la Remove, Cancel/readback păstrate; Remove-first ⇒ NOT_FOUND la noul entry start și zero operation/dispatch nou. Pentru SaveModels, CAS determină câștigătorul, fără resuscitarea ID-ului retras. Nu țineți o barieră sub lockul necesar lui Cancel.

### R2-P02 — MEDIUM — Proba CLI schimbată nu are încă regresie acceptată pe bytes corecți

- **Fișier:linie:** `cli/tests/test_status.py:25–32,47–50`; `cli/tests/test_installed_pointer_schema.py:116–124`; `cli/src/omnis_cli/main.py:70–98`; loguri `remove-cli-tests2.log:1–136`, `remove-cli-schema.log:10–38`, `remove-cli-narrow2.log:1–12`.
- **Scenariu/reproducer:** tentativa67 este **11 FAIL /67 în8.472s**, nu67 PASS. Tracebackul încercării schema citează explicit `/home/kali/OmnisAI/cli/src/omnis_cli/{start,instance}.py`, nu candidatul. Testul subprocess invocă executabilul de lângă `sys.executable`, deci schimbarea importului părinte nu repară singură sursa subprocessului. În plus, StatusTest izolează XDG_STATE_HOME și XDG_RUNTIME_DIR, nu XDG_CONFIG_HOME; `main()` încarcă config înainte să ajungă la status. `remove-cli-narrow.log` încă avea1FAIL/6; numai `remove-cli-narrow2.log` are6PASS și SOURCE candidat.
- **Criteriu:** probe pe artefactul exact, mediu propriu, fără a promova refuzurile de configurare/source greșit în verdict de produs.
- **Remediu minim:** păstrați încercările originale; validați importul și executable source în mediul QA pregătit, izolați și configurația și rulați numai grupul CLI/release afectat după preflight. Nu este necesar un nou canonical sau repararea operatorului pentru aceste erori de harness.
- **Contaminare:** logurile arată refuzuri de config/schema și nu demonstrează modificarea configurației ori efecte asupra operatorului. Ambient config putea fi citit; cauza exactă a conținutului privat nu este stabilită și nu am citit-o. Nu deduc ALL_CLEAN, dar nici incident de mutație a operatorului din aceste assertion failures.

## Finding — prerechizit de rollout

### R2-R01 — HIGH pentru rollout, nu defect al comenzii Remove — schema0017 nu merge cu CLI/release0016 păstrate

- **Fișier:linie:** `api/src/omnis/core/db.py:16,103–106`; `cli/src/omnis_cli/instance.py:103`; `start.py:60,471–472,999–1025,1372–1424`; `release.py:23–24,69–77,295–301`; `backup.py:309–317`; `ops/build_control_bundle.py:171–189`; contract existent `cli/README.md:23–37,148–153`.
- **Scenariu/reproducer:** mountul development afectează API/supervisor, nu CLI-ul host și nu joburile instalate de migrare/reconciliere. API candidat cere0017, DB0016 refuză readiness; după migrare, CLI vechi cere0016, deci nu atestă DB0017. CLI nou nu este o punte: locatorul0016 este respins de `load_instance`; release/snapshot0016 sunt respinse de noile verificări. Restartul păstrat nu execută upgrade, iar releaseul continuă să fie0.1.0 în același slot imuabil: instalarea peste bytes diferiți este refuzată. Restore cere același schema/digest, nu oferă upgrade între releaseuri.
- **Control inert executat:** exact `Instance`/`load_instance` extrase AST din base și HEAD, numai cu input literal și private reads înlocuite, fără fișiere fixture/DB. Base acceptă0016 și respinge0017; HEAD respinge0016 și acceptă0017. Exit0. Este SOURCE, nu instalare reală.
- **Criteriu:** nu declarați că old installed CLI/release suportă rolloutul development0017; păstrați Stop/recovery, UUID/date/istoric/chei și rollbackul verificat.
- **Prerechizit exact:** tranziție separată, explicit autorizată și reviewuită, care livrează CLI0017 + API/control image/reconcile artifacts0017 compatibile și o migrare/lifecycle/release-identity transition pentru **aceeași instanță păstrată**, cu backup/restaurare probate și acces păstrat la toolchainul vechi. Fresh fixture0017 este suficientă pentru QA izolată, nu migrează operatorul. Nu instalați doar CLI nou peste0016, nu falsificați schema/digest/receipturile, nu folosiți restore cross-digest și nu înlocuiți datele cu o instanță goală. Candidatul nu conține/nu probează acea tranziție. Operatorul actual rămâne blocat până la mandatul și remediul propriu, fără Start/Stop/recover aici.

## Auditul callerilor și ordinele legale — SOURCE

- HTTP: `security/host_origin.py:104–112,160–175,182–212` păstrează Host/Origin exact, auth/sesiune/CSRF și excepția65536 numai pentru PUT-ul registrului. `provider_model_routes.py:93–106` folosește discriminant strict și refuză BOM/duplicate/non-finite. `KeyDTO` păstrează extra-forbid/strict; Remove are UUID și revizii integer bounded. Limitele globale3600/4096 nu au fost schimbate.
- Control: `provider_key_routes.py:47–101` verifică peer UID, frame complet/capability/context comandă, limita request/reply65536. `transport/local_control.py:62–87,198–211,335–388` păstrează aceeași autentificare/capability,16clienți, deadline și encoder bounded. Pagini16/available64 rămân; nu există limită globală mărită.
- Wiring real: `supervisor/__main__.py:105–116,182–195` construiește un singur ProviderSettingsOwner și îl dă și model-test ownerului. `ProviderSettingsOwner.handle:245` ține același lock pentru Remove/SaveModels/SaveSelection. Test start folosește acel lock la `model_test_runtime.py:327`; verifică membrul prin `provider_model_test.prepare:34–43` în admission.
- Lock order: Settings lock → admission → `InstanceService._locked:413–440`, instance_control FOR UPDATE apoi supervisor_lease FOR UPDATE. Owner/epoch/lease expiry, stop fence și generation sunt verificate în admission înainte și owner/expiry din nou după corp (`service.py:629–641`). Remove nu ține lockul pentru rețea/operator și nu schimbă Cancel. Final physical writer folosește aceeași ordine, fereastră bounded existentă.
- Remove/receipt/CAS sunt în aceeași tranzacție. Replay exact este verificat înaintea admission și rămâne receive-only după Stop/restart; payload diferit cu același command ID ⇒ COMMAND_CONFLICT. Entry străin/inexistent nu este găsit în registrul instanței. Save vechi pierde CAS; chiar cu noua revizie a registrului, ID retras este refuzat explicit (`provider_model_service.py:221–233`). Un ID nou poate readăuga perechea, fără refolosirea celui vechi. Nu am identificat un bypass nou de authority în acest flux.
- Remove verifică toate cele4 assignments după conexiune/model, inclusiv referințe stale; nu le rescrie. Orice system_operation ne-FINISHED blochează; FINISHED/UNKNOWN nu blochează. Commiturile settlementului existent păstrează operation/outcome/ledger împreună; această observație nu înlocuiește proba overlap cerută.

## Probe păstrate și proveniență

- Citire limitată a logurilor existente, fără relansare: provider PG **55PASS60.36s**, model-test-v2 **79PASS/1SKIP141.17s**, runner exit0/owned cleanup readback în ambele. Web log **124PASS**; docs **87PASS**, fără a le transfera la installed QA.
- Pinurile schimbate în testele schema/CLI și `api/tests/fixtures/b06a_durable/releases.py:347–348` sunt verificări ale headului curent. În diff-ul46 nu apar originale de evidence din `documents/verification`, migration0016 sau pinuri de artefacte istorice rescrise. Aceste actualizări nu recertifică vechile releaseuri. Păstrați logurile FAIL și generați separat probele noi; nu rescrieți originalele pentru verde.
- `git diff --check base..HEAD`: exit0. Niciun PG/browser/build/provider/model/target/native effect executat de reviewer. Niciun cod/test/config/skill edit, stage/commit/push ori operator action. Singurul fișier creat este acest raport scratch.

**Neexecutat/risc:** overlap PG nou, CLI/release installed acceptance, rollout/migrare/restaurare operator și QA browser nu sunt certificate. Reticle NOT_INTEGRATED/NOT_RUN; Chisel BLOCKED_NO_GO. Legacy Cancel409/default-web2FAIL/supervisor underlying cause și canonical5400NOT_RUN rămân neschimbate; acest Remove nu resetează cele2 cicluri harness-only.
