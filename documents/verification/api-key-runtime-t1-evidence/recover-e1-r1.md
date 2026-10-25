# R1 — re-review focalizat al remediului IPC

**Verdict: APPROVED_SOURCE_SCOPED — numai delta finală. Findings concrete noi: niciunul.**

## Snapshot și compoziție

HEAD `e1b01a32b278b2368a2855083731f6273c70ba14`, tree `0665ae0d9616677d22d06996c36e1f4f4e5ac6a8`; baza delta `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`. Verificate independent HEAD/tree, clean înainte/după, cele 10 paths/blob/SHA față de `dd4f8747287496d1bb589de277455354d122892a` și exact două paths modificate ulterior: `cli/src/omnis_cli/recover.py`, `cli/tests/test_recover.py`. SHA256 delta: `6d7a7eebefd431719ac3032f0e1f510db97dc2e23fcef497d68f2f0c34e240e5`. Manifest: `freeze-r2fix.json`.

Verdictul se compune cu `reviewer1.md` **numai în charterul R1 original**, pe cele opt paths neschimbate și logica SQL/API/history/Stop-owner neafectată. Hashurile rapoartelor/reproducerelor originale sunt păstrate. Nu redeschid acele aprobări și nu transfer această aprobare asupra QA fizice/distribuției.

## Cerință → cod → dovadă

- **Refuz înaintea persistenței/efectului:** `_inventory(dead=True)` (`recover.py:130–172`) deschide numai lockul existent, validează FD-ul privat, încearcă `LOCK_EX|LOCK_NB` fără așteptare și admite socketul existent numai pe `ECONNREFUSED`. Connect folosește `min(0.2, remaining_deadline)`; succesul, timeoutul și erorile incerte refuză. Socketul și identitatea lockului sunt reverificate. Prima invocare (`:205`) precedă intentul; negativele `test_recover.py:223–276` contestă OFD-ul/listenerul reale și cer zero start, scrieri recovery, intent, control sau teardown, cu journal/IPC/cap păstrate.
- **Persistență și autoritate originală:** `recover.py:206–231` păstrează ownerul și recordul original, persistă/readback intentul și RECOVERING, apoi reexecută inventarul mort și revalidează owner/intent/journal înaintea unicului start pe CID-ul original. `write_record` existent păstrează fsync/publicare/sync director. Negativele `test_recover.py:278–331` introduc lock ocupat/listener pe același inode după persistarea autentică: zero start, intent/RECOVERING păstrate, retry refuzat. Nu există rollback distructiv sau emergency fallback nou.
- **FD eliberat și caller real păstrat:** `finally` (`recover.py:165–166`) închide numai FD-ul probei înainte de copil. `test_recover.py:128–135` verifică independent disponibilitatea lockului chiar la start. Pozitivul (`:675–701`) păstrează inode-ul socketului, dovedește `ECONNREFUSED` real și ajunge prin `main(["recover","--json"])` → `stop_instance(recover=True)` → `recover_barrier` → SHUTDOWN/FINALIZE/ARM_STOP → Stop-owner/completion existente la STOPPED, cu date păstrate. Nu apare OPEN/re-SEND/provider.
- **Incertitudine:** `test_recover.py:333–387` verifică TimeoutError/EACCES injectate și înlocuiri efective de inode lock/socket, fără start/scrieri; lockul propriu poate fi recâștigat după eroare.

**R2-RECOVER-01:** remediul satisface criteriul pre-efect și ordinea/persistența din charterul R1. Aceasta este aprobarea complementară R1 a deltei; adjudecarea finală rămâne părintelui.

## Execuție proprie

Cele patru teste existente numite mai sus: **4 PASS, exit0, 3.321s**, prin `cli/.venv/bin/python -I -B -c …`; comanda integrală în `r1fix-source-command.txt`, output în `r1fix-source.txt`. Originea SOURCE verificată; HOME/XDG/TMPDIR private sub `evidence/r1fix`; copiii Python au primit `-I -B`. Cleanup reap/pidfd/join trecut, TMPDIR gol, checkout și originalele neschimbate. Sunt IPC/Stop-owner reale cu Engine/SQL/control/start/familie-container sintetice, nu recuperare Docker instalată. Cele 383 SOURCE/383 wheel și identitatea artefactelor rămân dovezi distincte ale autorului/părintelui, nereexecutate aici.

**Neexecutat:** API/SQL/PG și canonical neschimbate, Docker/browser/provider/QA fizică; fără produs, date operator, chei sau documente protejate modificate. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
**Risc rămas:** QA fizică instalată NOT_RUN, nu prerequisite circular al verdictului SOURCE; T1 rămâne PARTIAL/NOT_ACCEPTED, fără rollout sau închidere.
