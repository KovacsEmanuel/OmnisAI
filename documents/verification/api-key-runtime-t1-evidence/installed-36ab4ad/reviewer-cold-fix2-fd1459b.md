# R2 — re-review focalizat al corecțiilor cold restore

**Verdict: APPROVED_SOURCE_CORRECTIONS_SCOPED. Niciun finding nou confirmat în delta și callerii afectați.**

Snapshot integrat: `fd1459b2edd0fa4f6cb895f964ff0d027f5b9dce`, tree `18799fcb8dac08697e8eac61e30607c249c5c2fb`; autor `bcb933f64a970a49cd19dfdef6875ad0faa35a10`, bază remedii `469029bafde0a1041d32358813331e0b3da530f9`. Checkoutul read-only a rămas clean/detached. Am verificat programatic toate cele **13 bloburi Git și 13 SHA-256** din `cold-fix-integrated-freeze.json`: corespund fișierelor citite. Remediile sunt separate: `b8ee9de` status, `dde7bc0` restore/reactivare și `bcb933f` tar.

Contract: R2-COLD-01 → admiterea reală `restore` înainte de extracție; restore-only → intent/argv/attestation/job DB → ACK înainte de servicii/OPEN; risc: payload ambiguu, autoritate extinsă sau reactivare/replay implicit. Decizia este admiterea SOURCE a corecțiilor pentru QA, nu acceptarea runtime. R1 păstrează ownershipul reviewului complementar de persistență/ordine. Încărcare presupusă: topologia existentă, local-first, un singur operator.

## Dispoziții și frontiere verificate

| Cerință | Cod/caller și control citit | Dispoziție R2 |
|---|---|---|
| **R2-COLD-01 — coliziuni tar** | `cli/src/omnis_cli/backup.py:192–224,369–372,421`; `cli/tests/test_cold_controls.py:94–156` | **CLOSED_SOURCE_SCOPED**. Setul deduplică tuple-ul `PurePosixPath(...).parts`, nu stringul brut. Dublura exactă, `18//docker/...` și `18/docker/./...` ating aceeași cheie și sunt refuzate înainte de `archive`. Controlul fără alias păstrează `FIRST`; controalele negative cer zero extracții, target nepublicat și sursă/snapshot neschimbate. |
| Rădăcini/fișiere obligatorii, limite și retenție | `backup.py:192–224,361–427`; controalele existente `test_cold_controls.py:17–92,158–221` | Tratarea rădăcinii director `.` și a prefixului `./` rămâne neschimbată; fișierele obligatorii folosesc acum aceleași tuple ca membrii. Reprezentările GNU tar uzuale nu devin refuzate prin această schimbare. Nu sunt relaxate deadline-ul, numărul de intrări, expanded limit, refuzul traversal/link/special/PAX/mode, hash/FD readback sau publicarea no-replace. Compatibilitatea unui tar nou produs efectiv de GNU tar **nu a fost executată în acest re-review**. |
| Status restore fără autoritate istorică | `cli/src/omnis_cli/status.py:37–38,78,116–145`; `test_cold_backup.py:100–178` | `RESTORED_STOPPED` cere marker și admitere valide, fără startup, resurse/network absente și două readbackuri stabile. Nu contactează controlul pentru acest traseu; nu proiectează generation/epoch din arhivă, nu declară dashboard/control/assessment READY. Marker STARTING, resurse străine și startup invalid nu primesc această proiecție. Nu este probă că un serviciu real este oprit. |
| Mod restore fix, legat de intent | `backup.py:568–584` → `restart.py:69–114,125–156,193–210,226–228` | Admiterea restore furnizează UUID-ul markerului în intentul persistent. Consumerul cere marker STARTING cu același UUID, intent PREPARED byte-identic, attempt/system ID/hashuri exacte și resursele finite DB/network. Numai acest traseu adaugă `--restore`; restartul normal păstrează argv fără flag și nu dezactivează conexiuni. Marker absent/malformat/nepotrivit refuză înainte de crearea jobului când intentul selectează restore. |
| Attestation și receiver | `start_runtime.py:519–587,599–638,685–769`; `api/src/omnis/stop_reconcile.py:32–63,83–109`; `test_cold_restore_mode.py`; `test_cold_restore_reconciliation.py:90–118` | Attestorul acceptă numai argv exact corespunzător modului ales, înainte și după execuție; restore pe alt rol este refuzat. Imaginea, userul, lipsa mounturilor, confinarea și env-ul exact rămân verificate. Receiverul admite numai `[]` sau `["--restore"]`, înainte de citirea inputului/DB; nu introduce mod arbitrar, SQL, path sau env importat. JSON V1/unique keys, 16 KiB, timeout și bindingul system ID rămân. |
| Reactivare explicită și istoricul imuabil | `api/src/omnis/modules/instance/service.py:811–915`; consumerul existent `modules/settings/provider_key_service.py:106–121,194–204,278–290` | Cu `restore=True`, numai headurile enabled ale instanței primesc revizie nouă `enabled=FALSE`, păstrând connection/secret/credential refs. Nu se rescriu reviziile vechi, ciphertextul, selecțiile sau ledgerul. Consumerul existent folosește exact aceleași headuri per provider; selecția veche nu devine conexiune activă. Dezactivarea, receiptul și eliminarea fence-ului sunt în tranzacția închisă; readbackul din tranzacție și cel de după commit refuză orice head încă enabled înainte de return/ACK. |
| Eșec/lost ACK/no replay | `restart.py:155–267`; `start.py:1280–1294,1383–1389,1474–1482,1515–1545`; `test_restart_wiring.py:28–32,173–267,289–298,443–454` | JOB_PENDING este durabil înainte de job; rezultatul/receiptul/exitul/cleanupul exacte preced ACKED, iar acesta precede serviciile și OPEN. ACK pierdut/invalid, fault de scriere, resursă străină sau rezultat incert nu autorizează un al doilea job ori OPEN. Pe replay DB nu se mai inserează revizii; restore refuză receiptul dacă headuri enabled persistă. Fence/generation/epoch/cluster și contextul închis sunt reverificate. Datele sunt păstrate la incertitudine; nu deduc cleanup fizic din flags. |

### R2-COLD-01: legătura cu findingul original

Raportul imuabil `reviewer-cold2-5ffa.md` și reproducerea părintelui `parent-cold2-alias-repro.log` rămân valide pentru bytes vechi: alias admis, GNU tar exit0, `FIRST → LAST`. Le-am citit; nu le-am rescris și nu le prezint drept execuție pe candidatul nou. Corecția tuple-ului închide exact mecanismul reproducerii; testul nou atacă același consumer `main(["restore", ...])`, cu manifest rehashuit și interdicție explicită a extracției înainte de refuz. Eșecul inițial al testului GREEN din cauza copierii metadata rămâne în freeze; nu este șters și nu este declarat succes. Oracle-ul final păstrează refuzul înainte de helper și sursa/snapshotul nemodificate.

**R1-COLD-01:** corecția proiecției și controalele negative sunt compatibile cu frontiera R2, fără acordare de autoritate. Dispoziția independentă completă de persistență/ordine aparține R1; acest raport nu o substituie.

**CANON-RESTORE-CONNECTION-REACTIVATION (§8.1/522):** aprobat numai SOURCE în frontiera R2 descrisă. Reactivarea nu este implicită la Start, iar istoricul și referințele rămân. Semantica reală PG, commit/readback și intercalările fizice rămân pentru QA admisă.

## Dovezi și limite

Am executat numai citiri SOURCE/Git și verificarea identităților; **nu am rerulat teste sau servicii**. Am citit ieșirile păstrate pentru comenzile din freeze:

- CLI `python -I -m unittest discover -s cli/tests -v`: **373 teste / 89.136s / OK**, exit0 conform freeze; entrypointul propriu al părintelui, nu vechile 366/2/70 și nu restore fizic.
- API SOURCE `python -I -m pytest -c api/pyproject.toml api/tests/test_cold_restore_reconciliation.py api/tests/test_stop_reconcile.py -q`: **46 passed / 12.00s**, exit0 conform freeze; DB doubles, nu PG.
- Ruff check: all checks passed; format: **364** fișiere; mypy: **141** surse, fără probleme. Aceste rezultate nu certifică securitatea/runtime.
- API **3204 collected** este exclusiv collect-only; inclusiv cele două cazuri parametrizate PG noi sunt **NOT_RUN**, nu PASS.

Scope-ul SOURCE neschimbat pentru FD binar, ownerul procesului și helperul fix privilegiat rămâne exact cel din reviewul original, fără redeschidere generală sau extindere de aprobare. Nu transfer probele vechi de Stop idle la restore. Real PG/OCI/installed restore, tar produs proaspăt în imaginea PG, timeout/lost-ACK și dispariția efectivă a helperului/familiei daemon-side: **NOT_RUN aici**. Lipsa acestor probe nu este un blocker circular SOURCE; QA aparține părintelui după cele două reviewuri aprobate și preflightul admis. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. **Fără închidere T1.**

Singurul fișier creat este acest raport; fără modificări de produs, Git, DB, servicii, profiluri, credentiale sau HTML și fără provider/model/network/build/install.

**Neexecutat:** QA fizică PG/OCI/installed și cleanup daemon/family; riscul rezidual trebuie verificat pe artefactul final, nu dedus din SOURCE sau mocks.
