# R1 — re-review focalizat cold restore

**Verdict: APPROVED_SOURCE_CORRECTIONS_SCOPED.** Niciun finding nou confirmat în scope-ul atribuit. R1-COLD-01 este închis SOURCE; criteriul de dezactivare/reactivare explicită este satisfăcut în codul urmărit, nu certificat prin restore real.

## Identitate și limită

Checkout readonly: `fd1459b2edd0fa4f6cb895f964ff0d027f5b9dce`, tree `18799fcb8dac08697e8eac61e30607c249c5c2fb`; delta remedierilor față de `469029bafde0a1041d32358813331e0b3da530f9`, autor final `bcb933f64a970a49cd19dfdef6875ad0faa35a10`. Am verificat programatic fiecare cale din `cold-fix-integrated-freeze.json`: SHA-256 local, blob HEAD și blob la author_head corespund toate. `git diff --check 469029b HEAD` exit0; checkout clean/detached la ultimul readback.

Am citit rapoartele originale `reviewer-cold1-5ffa.md` și `reviewer-cold2-5ffa.md`. Aprobarea prezentă păstrează scope-ul R1 neschimbat descris concret în primul raport; nu îl înlocuiește cu un audit universal al restartului și nu aprobă scope-ul R2. Cerință → consumer → risc → decizie: status stopped restaurat și conexiuni inactive → CLI status/Start, jobul privat real, CAS/readback DB înaintea Supervisor → proiecție falsă, reactivare tacită ori resend → admiterea QA locală după reviewurile necesare versus remediu SOURCE.

## Dispoziții și traseu verificat

### R1-COLD-01 — CLOSED_SOURCE_CORRECTION_SCOPED

- `cli/src/omnis_cli/status.py:37–38,78,116–145` distinge rootul cu `restore.json` fără startup curent. Nu contactează controlul privat în acest caz. Reutilizează `admit_restore`, verifică portul, absența containerelor/rețelei și repetă readbackul admission/marker; proiectează `RESTORED_STOPPED`, provenance `RESTORE_ADMISSION`, `admission_open=false`, fără generation/epoch istorice.
- `backup.py:480–565` validează schema/starea markerului, identitățile fizice noi root/PGDATA/vault/key, manifestul, fișierele și legătura instance/release/schema/proiect. Nu copiază receiptul istoric în startup curent. Runtime-ul construit de status face inspect/read-only, nu Start/Stop/migrare/reconciliere. Marker invalid, startup invalid sau resurse conflictuale nu devin stopped sănătos.
- Testul nou `cli/tests/test_cold_backup.py:100–179` trece prin CLI `main(["status", "--json"])` și filesystem real, cu doubles PG/OCI declarate: control IO și efectele sunt interzise, bytes înainte/după sunt identici, iar marker/resource/startup invalide sunt refuzate. RED-ul status păstrat arată lipsa guardului de control; GREEN-ul și suita finală includ remediul. Nu îl prezint drept restore real.

### CANON-RESTORE-CONNECTION-REACTIVATION — APPROVED_SOURCE_SCOPED

- Arhitectură §8.1, `documents/Omnis_MVP_Architecture.md:522`: importul master key sau primul Start nu trebuie să reactiveze cheia din snapshot. Remediul este o tranziție DB explicită la restore, nu substituirea prin consimțământ generic de Test.
- `backup.py:568–583` validează restore-ul și system_id, apoi persistă intenția cu UUID-ul `restore_id` validat; markerul devine STARTING. `restart.py:69–114,125–156` leagă intenția de attempt, request, hashurile istorice și markerul STARTING cu același restore_id; compară intenția cu readbackul durabil înaintea efectului. JOB_PENDING este persistat înaintea create/start.
- `restart.py:193–211,226–267` selectează numai argv fix `python -I -m omnis.stop_reconcile --restore`, atestat înainte și după execuție cu `restore=True`. `start_runtime.py:519–587,598–637` refuză argv diferit și modul restore pe alt rol. Jobul nu montează seiful și nu primește secrete în argv.
- Receiverul real `api/src/omnis/stop_reconcile.py:32–60,83–93` admite numai lipsa argumentelor sau exact `--restore`, păstrează inputul Stop V1 ≤16 KiB și trimite flagul explicit la `InstanceService.reconcile_stop`. Identitatea clusterului și validarea URL-ului rămân în traseul real; ACK-ul păstrează forma V1.
- `api/src/omnis/modules/instance/service.py:838–915` păstrează lock order-ul existent instance→lease (`271–295`), schema/system_id și closed generation/epoch/command/grant. Numai pe restore nou și grant exact adaugă pentru headurile enabled revizia următoare cu `enabled=FALSE`, păstrând instance/connection UUID, provider, secret_id și credential_revision. Nu modifică rânduri istorice, selections, ciphertext sau cheia master. Receiptul și ștergerea fence-ului prin CAS rămân în aceeași tranzacție.
- `_reconciled_readback:811–836` verifică receiptul exact, fence absent și niciun head enabled; verificarea are loc înainte de commit și într-o nouă tranzacție după commit, împreună cu contextul/closed stop, înaintea ACK. Traseul nou este exclusiv SQL local; nu introduce provider/SDK/rețea externă sub tranzacție.
- `provider_key_service.py:106–121,194–204,238–290` citește aceleași headuri și cere enabled plus revizia exactă. Selecția veche nu ocolește dezactivarea. Save explicit ulterior, cu CAS, publică o nouă conexiune enabled; simplul autounlock/import nu scrie acest head. Reviziile disabled existente rămân nemodificate.

### Ordine, replay, istoric și restart normal — păstrate SOURCE

`start.py:1125–1134,1171–1191` folosește ramura restore numai fără jurnal curent. După primul Start, markerul păstrat nu preia prioritatea față de startup READY/STOPPED: status folosește traseul normal, iar următorul Stop→Start apelează `prepare_restart`, nu restore. Intenția normală are restore_id null și jobul rămâne fără `--restore`; conexiunile nu sunt dezactivate la restart normal.

`start.py:1327–1389,1419–1453` cere identitatea DB și reconcilierea înainte de creare/pornire Supervisor/API. `restart.py:240–267` cere ACK exact, exit/state/ownership și cleanup job confirmate, apoi ACKED durabil înainte de întoarcere. Replay exact al serviciului nu mai inserează headuri și revalidează closed state; head enabled sau takeover produce refuz. ACK pierdut/cut nu autorizează resend: JOB_PENDING/marker STARTING/jurnalul UNCERTAIN păstrează DB și blochează un Start nou (`start.py:1568–1593`). Testele wiring verifică inclusiv primul Start restaurat, lost ACK și lipsa evenimentelor noi la retry (`test_restart_wiring.py:25–68,430–478`).

Rândurile originale R1 privind backup numai după Stop, no-overwrite, master export separat, provenance immutable, queued Start/UNOWNED și intent-before-effect își păstrează concluziile la scope-ul original. Delta tar este vizibilă, dar dispoziția R2-COLD-01 aparține reviewerului R2.

## Dovezi citite, nu rerulate

- `cold-fix-status-red.log`: RED, 1 test/3 subcase failures; `cold-fix-status-green.log`: 24 teste PASS/4.601s.
- `cold-fix-reactivation-red.log`: 6 failed/3 passed; `cold-fix-reactivation-green.log`: 9 PASS/0.38s. Testele SOURCE acoperă flagul exact, restore versus normal, replay și refuzul headului enabled; attestation separat 1 PASS/0.008s.
- Manifestele de comenzi păstrate leagă `python -I -m unittest discover -s cli/tests -v` de `cold-fix-final-cli2.log`: **373 PASS/89.136s/exit0**.
- `python -I -m pytest -c api/pyproject.toml api/tests/test_cold_restore_reconciliation.py api/tests/test_stop_reconcile.py -q`: **46 PASS/12.00s/exit0**, `cold-fix-final-api.log`; SOURCE/doubles, nu PG.
- Ruff check exit0; format check **364 fișiere**; mypy **141 surse**, exit0, din logurile finale `*2.log`. Collect-only API: **3204 colectate**, nu executate. Cele două cazuri din `api/tests/test_cold_restore_pg.py` au fost citite și rămân **NOT_RUN**, nu PG PASS.

Aprobările CLI/UI neschimbate rămân reutilizate numai la scope-ul lor. Nu am lansat servicii, teste, instalări/builduri, PG/OCI/native/browser/provider, nu am inspectat credentiale/profiluri/private logs istorice și nu am modificat produsul, Git ori documentele canonice. Singurul fișier creat este acest raport; fără reproducer nou, fiindcă nu există finding concret nou.

**Predare:** R1-COLD-01 închis SOURCE și reactivare explicită aprobată SOURCE pe fd1459b; după verdictul complementar R2, părintele poate continua QA locală admisă pe bytes finali. Lipsa probei reale nu devine blocker circular de cod. T1 și acceptarea installed/fizică nu sunt închise. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Neefectuate: restore real PG/OCI/installed, crash/lost-ACK fizic, provider/live și gate canonic complet; nu am reluat auditul/harnessul neschimbat.
Risc restant: dovada SOURCE/doubles nu certifică restaurarea fizică sau reactivarea prin produsul instalat; acestea rămân QA explicită a părintelui, fără resend ori acord live presupus.
