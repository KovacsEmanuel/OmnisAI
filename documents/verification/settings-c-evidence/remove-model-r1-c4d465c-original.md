# R1 independent — Remove model

## Verdict

**NO_CONFIRMED_SOURCE_BUG / ACCEPTANCE_BLOCKED_REQUIRED_PROOF.** Review funcțional/persistență/istoric/migrare/readback/UI SOURCE, nu acceptare runtime, vizuală sau integrare. Nu am găsit un defect de produs demonstrat în ramura Remove inspectată. Lacunele de mai jos nu sunt prezentate drept pierdere de date observată, dar împiedică acceptarea integrală a criteriilor obligatorii.

Snapshot: `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`, HEAD `c4d465c072ebbd246bd882441a7465b55b0b2ab6`, tree `19255f793ed90f78c59bf5f4e6f557691b10cd0f`, base `fa5451e9a9b64c1f922c42a664d818708d00ae34`; canon `0f4a8a7112026b33188683e8c614e2ca50d3556b`. Diff inventariat: 46 fișiere. Identitate Git la început și final; tracked clean. Trei legături untracked preexistente (`api/.venv`, `web/node_modules`, `tools/development/anti-slop/node_modules`) neatinse. Manifestul freeze citit; verificarea tuturor celor46 blobs/SHA aparține părintelui, nu o revendic drept verificare proprie repetată.

## Constatări — obligatoriu separate de buguri confirmate

### R1-P01 — HIGH, REQUIRED_PROOF_GAP: upgrade0016 populat și noile protecții DB

- **Loc:** `api/tests/test_provider_key_api.py:581-622,667-745`; `api/src/omnis/migrations/versions/0017_model_removal.py:15-34`; `api/src/omnis/core/schema.py:479-496,569-587`.
- **Scenariu/reproducer cerut:** pornește de la0016 cu registru, intrări/revizii și receipturi deja populate, inclusiv istoric de test/consum; aplică0017 și compară valorile istorice. Verifică retirement valid, refuz identity rewrite/unretire/re-retire/delete/truncate, FK retirement străin/inexistent, unicitate numai între membrii disponibili și readiness FAIL după eliminarea/slăbirea noului index/guard/FK.
- **Dovada actuală:** parametrizarea existentă este numai empty sau0015. Sămânța0015 are conexiuni/selecții/receipt Settings; intrările de registru apar abia în backfill0016 în aceeași rulare până la head. Testul negativ de readiness elimină vechiul `provider_model_entry_connection_fk`, nu protecțiile noi. Nu există aici dovada upgradeului unui registru0016 deja folosit ori controalele negative ale noului guard/index.
- **Criteriu:** `web/design/settings-final.md:105-114`, arhitectură§5.3: upgrade păstrează arhivele și retirement/identitate rămân ireversibile prin scrieri obișnuite.
- **Remediu minim:** extinde fixture/testul de migrare existent cu punctul0016 populat și controalele negative exacte; nu owner/runner/harness nou și nu încă o suită generală. Codul SQL inspectat pare să implementeze intenția; lipsa probei nu dovedește un defect SQL.

### R1-P02 — HIGH, REQUIRED_PROOF_GAP: istoricul intrării retrase și re-add fără Connected

- **Loc:** `api/tests/test_provider_key_api.py:399-432,458-503`; `api/src/omnis/modules/settings/provider_model_service.py:220-233,243-250`; callerii `provider_model_test.py:19-28` și `runs/model_test_runtime.py:193-262`.
- **Scenariu/reproducer cerut:** intrarea E nealocată are un test terminal autentic prin consumerul existent, outcome UNKNOWN sau COMPLETED, snapshot/usage/cost/receipt persistate. Remove E → restart/read exact operation și receipt, cu valorile istorice identice și E absentă numai din biblioteca viitoare. Re-add același model/conexiune cu E2 nou → latest(E2)=NOT_FOUND/Not tested, nu Connected moștenit; latest/operation(E) rămân citibile. Save cu ID E retras și **expected_revision=0**, registru proaspăt, trebuie refuzat fără scrieri. Selecția celorlalte modele și conexiunea/cheia rămân neschimbate.
- **Dovada actuală:** operația adăugată de test este un rând sintetic instance-scoped cu `{}` pentru snapshot, nu istoric al modelului retras. După Remove se verifică markerul retirement și numărul reviziilor intrării; nu readerii istorici/outcome/cost/snapshot. Re-add verifică status200/total64/selecție, nu latest/Connected. Save cu vechiul ID folosește expected_revision1 și este refuzat deja în `merge_models`, astfel că nu exercită refuzul explicit al ID-ului retras cu expected_revision0.
- **Criteriu:** păstrarea ALL history, retired-ID cannot reactivate, explicit re-add/new identity/no inherited Connected; canon:105-113 și arhitectură§5.3.
- **Remediu minim:** extinde consumerul PG existent cu istoric real inert/controlat și readbackurile respective, plus cazul expected_revision0. Nu sunt necesare apeluri provider/operator sau un nou framework. Nu afirm că istoria este ștearsă: implementarea Remove scrie numai revizia registrului, markerul identității și receiptul, iar readerul istoric pare să păstreze payloadurile.

## Acoperire SOURCE și limite de probă

| Criteriu | Evaluare |
|---|---|
| Remove persistent/CAS, nu filtru React sau omission Save | Implementat în `provider_model_service.py:96-110,204-250`; două CAS, soft retirement și receipt în admission. |
| Default/Brain/Investigator/Validator; fără fallback | `require_removable:116-122` compară exact connection/model inclusiv selecții stale; UI314-324 enumeră rolurile și cere reassign fără scriere. |
| Active/unsettled versus FINISHED/UNKNOWN | Guardul123-132 refuză orice operație ne-FINISHED. UI94-105,369-402 separă terminal UNKNOWN de sentinelul de read failure `'UNKNOWN'`; nu confund aceste două stări și nu raportez un bug fals. Cancel/read rămân în markup. |
| Istoric/retired ID/re-add | Direcție SOURCE corectă; P02 rămâne lipsă de probă. `require_registered` filtrează retirement; test prepare folosește registrul disponibil, istoricul resolve folosește snapshotul arhivat. |
| DTO/control/client/readback | Discriminated union strict; același PUT/control/owner. Clientul verifică command_id; `mutate`159-182 citește receiptul exact și compară replyul, apoi încarcă starea. Recovery147-157 trimite numai GET/search local, nu resend Remove/Test/Refresh. |
| 64 disponibile/16 pagină/65536 frame | Limitele și decoderul/paginarea sunt reutilizate, nu relaxate. Testul actual writer623-713 acoperă cadrul complet și limita; nu cer duplicarea lui doar fiindcă Remove are un DTO mic. După Remove nu există însă dovadă UI reală same-command cu toate paginile. |
| UI cerută | Numai expanded details; quiet destructive; flex align-center desktop/sub metrici mobil; min-height44 existent; Test rămâne separat; confirmarea numește modelul exact/provider; focus către Add după succes. SOURCE, nu aprobare estetică/keyboard real. |

**QA obligatorie încă NOT_RUN pentru acceptarea Remove:** consumer browser/API/PG real al aceleiași comenzi, inclusiv reply pierdut → GET exact fără resend și readback/restart/pagini. `web/src/app/SettingsModels.test.tsx:63-82` dovedește numai un double HTTP cu o singură intrare și remount, nu restart backend/PG. Stările Remove activ/refuzat/terminal UNKNOWN și focus desktop/mobil au nevoie de verificare scoped, nu de rerularea unui generic full suite. Acest review nu a lansat QA, conform mandatului. Overlap Remove–SaveSelection/TestStart și auth/epoch/CLI/release aparțin R2; nu le aprob și nu dublez findings R2.

## Dovezi și excluderi

Citite: AGENTS, CURRENT/CONTRIBUTING, skillurile review/status/ponytail, contractul Remove100-114/arhitectură§5.3; diffurile relevante API/core/migrare/contracts/web/teste și callerii afectați enumerați mai sus. `git diff --check base..HEAD`: exit0. Niciun test nou/rerulat, build, PostgreSQL, native/browser, serviciu, env/dump, credențială sau efect provider/operator. Rezultatele55PG/79model/124web/quality comunicate de developer rămân SELF_REPORT, nu acceptare independentă din acest raport.

Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Nu am modificat repo/teste/skills și nu am făcut commit/push; singurul fișier creat este raportul scratch. Full CLI regression nepromovat; vechile Cancel409/default-web FAIL/supervisor/canonical5400 NOT_RUN rămân nerezolvate, dar nu sunt findings noi ale Remove și nu sunt redeschise aici. Raportul nu resetează ciclurile lor QA.

Omis intenționat: operator/runtime QA, estetica live, auth/epoch/concurență/CLI (R2), auditul întregului proiect. Risc: sursa plauzibil corectă și testele existente nu certifică upgradeul istoricului0016 populat sau păstrarea/no-inheritance după Remove real.
