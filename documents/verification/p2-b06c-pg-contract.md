# B06c — extensie autorizată PG / copy-installed projection

Baza acestei felii de probe: `5b0e6c247ed17c17b3bc15a42d34c0d956a2ea82`; codul de produs revizuit `77b4b01`. Operatorul a predat C03 (mesaj79036), iar effects.json fixează holder=b06c, sesiunea20261010_185056_cd318d, numai fixture-uri NOI owned PG/readback/copy-installed projection, UDS/no-network și zero model/provider/target. Transfer suplimentar: Makefile exclusiv pentru targetul minimal PG; runnerul, schema, CLI, main și WIP B06m rămân read-only. Acesta nu este acord warm/native SDK.

## Rezultat și limita probei

Seed records first-party nou → calificare/publicare reale prin helperul existent C03 → snapshot/selection/context/input/assignment persistente → ModelProjections.prepare/read pe PostgreSQL real → reconectare/proces nou cu aceeași proiecție → serializer/gate carrier reale din wheel copy-installed, cwd/HOME separate. Consumatorul proiecției și resolverul/store-ul nu sunt dublate. Datele brute sintetice ale fixture-ului sunt private; numai bytes proiectate și digests intră în readbackul model-facing.

Prerechizitele cold de transport pot folosi numai fixture-ul de protocol existent din testele C03 (`worker_fixture`, stage), declarat explicit ca input sintetic de laborator; acesta NU probează un loader/root/copil nativ și NU devine autoritate de model. Se folosesc InstanceService/fence și ManagedAdmission.commit_binding reale, fără runtime/SDK/provider nou. Dacă acest seed nu satisface contractul real al readerului, rezultatul rămâne BLOCKED; nu se patch-uiește resolverul și nu se declară fake consumer drept integrare.

## Paths și probe pereche

Schimbări permise: test nou `api/tests/test_model_projection_pg.py` (plus suport nou numai `*model_projection*` dacă necesar), target Makefile și note `documents/verification/p2-b06c*`. Codul de produs nu se schimbă fără defect valid reprodus. Reutilizăm `fixtures/c03_records.py`, `fixtures/c03_journey.py`, store/InstanceService/ManagedAdmission, migrarea existentă și runnerul `ops/run_test_db_gate.py` fără editări.

Pozitiv: Ref/digest/context/owner exacte, INSERT imuabil, replay fără record nou, reader persistent și proces/engine nou, bytes carrier și SHA256 independente, module efectiv instalate hash-identice cu snapshotul. Negative: foreign owner/run/projection/binding/composition, stale revision/digest/type, lipsă approval/known-secret/unclassified, raw/extra sentinel și size. Refuzurile se probează la frontiera corespunzătoare și fără sidecar/ledger suplimentar, nu doar pe dicționarul convenabil. NO_MODEL și released cold sunt păstrate; fără full SDK request credit.

## Runner, date și resurse

CLI-ul runnerului are allowlist fără target projection, dar funcția existentă `prove_private_fixture(gate_target,uv,timeout)` acceptă targetul Make. Makefile va apela această funcție existentă, iar când primește fixture-ul atestat va executa doar pytest focalizat; fără alt runner/framework și fără make check integral. Uneltele pin-uite existente r3-5gjabhuw/tools sunt citite/reutilizate, nu instalate global: uv0.12.19, Node24.21.0/npm11.19.0 au fost verificate real. API/CLI venv proprii Python3.13.15.

Registrează un scratch root nou scurt, HOME/installed/log/manifest și planul cleanup înaintea instalării/launchului. Runnerul emite și reține DISPOSABLE_INTENT project/root înainte de create/up, apoi CID/system-id în fixture.json; acestea sunt identitățile exclusive de cleanup. PG are network_mode=none și socket privat; zero port publicat. Cleanup exclusiv prin runner după family_drained, stop/remove exact CID atestat și readback CID/network/socket. Root/PGDATA/catalog/receipts/wheels păstrate; fără prune/old-resource adoption și fără schimbarea holderului.

Nu folosim migrated_database_url care face DROP DB la teardown pentru dovada de date păstrate. Pe fixture-ul nou, baza proprie a runnerului va fi atestată prin conftest și migrată cu Alembic real; datasetul sintetic rămâne în PGDATA după cleanup. Probe installed/restart noi, nu wheel/receipt istoric reciclat. QA independentă serială a acestui consumer va folosi alt root nou și aceiași bytes aprobați. Re-reviewurile focalizate vor lega test/Makefile/product de commit exact; remedierea eventuală cere reproducer/minimal fix/check/re-review.

Rollback: revert separat test/Makefile/note; nu șterge datele fixture-ului. Final: cleanup verificat și handoff bounded pentru b06m, fără a schimba effects.holder, a lansa succesor sau a închide SL10/native connector.
