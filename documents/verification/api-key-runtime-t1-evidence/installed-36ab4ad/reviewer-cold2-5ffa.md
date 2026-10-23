# R2 — review independent de securitate / cold backup–restore

**Verdict: CHANGES_REQUESTED_SOURCE_SCOPED — R2-COLD-01 (MEDIUM).**

Snapshot: `5ffa130ce1b0bd4f80add2105ef54b6a38bf51eb`, tree `b2acd878d17f9fcd681a96f1ecfad185d5f70971`, baseline `fea84e2`. Checkoutul frozen a rămas clean/detached. La final am verificat programatic toate cele 9 bloburi și cele 9 SHA-256 din `cold-parent-freeze.json`: toate corespund. Reviewul nu aprobă integrarea părintelui.

## Finding confirmat

### R2-COLD-01 — MEDIUM — coliziunile de cale tar trec admiterea și suprascriu același fișier

- **Loc:** `cli/src/omnis_cli/backup.py:197–214` (`name in names` / `names.add(name)` pe numele necanonic); efectul este `archive(... restore=True)` la `backup.py:421`, cu extracția GNU tar definită la `backup.py:118–130`.
- **Scenariu/repro:** un tar finit conține fișierele obligatorii `18/docker/PG_VERSION` și `18/docker/global/pg_control`, apoi `18/docker/base/16384/123` cu `FIRST` și `18//docker/base/16384/123` cu `LAST`. `PurePosixPath(name).parts` validează aceeași cale, însă setul `names` folosește două stringuri diferite. `validate_tar` admite arhiva; GNU tar termină cu exit0 și același fișier fizic conține `LAST`. Dublura textuală exactă este refuzată, deci controlul existent verifică doar egalitatea stringurilor, nu coliziunea la extracție. Manifestul cu hashul corect al acestei arhive nu elimină problema: ambele intrări sunt chiar în payloadul hashuit. Arhiva poate păstra un pg_control real nemodificat; verificarea system_id nu detectează suprascrierea altui fișier de cluster.
- **Criteriu încălcat:** frontiera de import cerută pentru coliziuni/no-overwrite și validarea strictă înaintea helperului privilegiat. Nu este demonstrat un escape din stage sau o suprascriere a unui target preexistent; impactul confirmat este ambiguitatea/suprascrierea payloadului importat în targetul nou.
- **Remediu minim:** deduplicare după cheia canonică a căii validate (de exemplu tuple-ul `parts`), sau refuzul reprezentărilor necanonice; păstrarea regulilor pentru rădăcină, traversal și tipuri. Un test negativ pentru alias (`//` și/sau `./`) trebuie să refuze înaintea helperului, alături de controlul pozitiv și dublura exactă existente. Nu este necesar un framework nou.
- **Probă executată:** `python -B /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/logs/reviewer-cold2-alias-repro.py` — exit0, output real:

```text
CONTROL exact duplicate: REJECTED COLD_ARCHIVE_INVALID
DEFECT canonical-path alias duplicate: ADMITTED
EXTRACTION exit=0; same physical path overwritten: FIRST -> LAST
```

Proba folosește codul `validate_tar` frozen și `/usr/bin/tar` local, exclusiv pe fișiere private mici; nu pornește PG/Docker/provider/network. Scriptul: `../logs/reviewer-cold2-alias-repro.py`. Artefacte private păstrate: `../logs/cold2-alias-shmj1gke/`. Nu este probă cu tarul din imaginea PG și nu pretinde restore real.

## Restul scope-ului R2 — observații SOURCE, fără alt defect confirmat

- **FD binar / owner:** am urmărit callerii `archive`/`cold_identity` către `ControlRuntime.run`. Fișierele sunt deschise nofollow/nonblock și verificate ca regular, UID propriu, 0600, nlink1, dimensiune finită; stdoutul binar este numărat separat de captura text și nu este decodat. Deadline-ul este verificat înainte de spawn și în bucla selector/wait. Pe erori, pidfd-ul pinnează numai leaderul; `uncertain` și `family_drained=False` rămân conservative, fără killpg pe PID/PGID istoric. Nu am transformat aceste flags într-o afirmație de cleanup daemon/family real.
- **Helper fix / privilegii:** numai callerii finiți tar, sync și pg_controldata; imagine PG18 identificată prin digest/ID local, fără pull; network none, read-only rootfs, no-new-privileges, cap-drop ALL, DAC_OVERRIDE și doar la scriere CHOWN/FOWNER. Singurul bind este postgresul stage/sursei; fără shell/comandă importată, cheie sau vault mount. Identitatea daemonului și a bindului are verificări înainte/după. La rezultat incert nu se publică; codul nu dovedește dispariția unui helper daemon-side după timeout doar prin oprirea CLI-ului.
- **Import / date:** manifest finit și set fix, limite de fișiere/hashuri, tar raw/expanded limitat la 1 GiB, refuz linkuri/traversal/speciale, rehash/readback și verificarea clusterului înaintea publicării. Excepția confirmată este coliziunea de mai sus. Publicarea reutilizează `renameat2(RENAME_NOREPLACE)`, inclusiv pentru target gol concurent, cu fsync; stage-urile incerte sunt păstrate privat, fără ștergere recursivă a datelor străine.
- **Source / target / secrete:** backupul cere STOPPED și readback sub lifecycle locks, fără Stop implicit; restore cere target XDG nou și produce marker separat cu identitățile fizice noi. Master key nu este exportată; importul separat verifică fișierul și lungimea, iar UUID-ul instanței este păstrat. Am urmărit și `provider_vault.py:152–258`: ciphertextul existent cu cheie absentă/greșită ori UUID greșit rămâne LOCKED și bootstrapul nu îl înlocuiește.
- **Istoric / no replay:** `admit_restore` nu promovează vechile PID/CID/daemon grants în noul startup. Am urmărit `prepare_restore` → `_prepare_reconciliation` → jobul fix → `stop_reconcile` → `InstanceService.reconcile_stop`. Receiverul are input finit, verifică system_id și starea/grantul DB închis; nu acordă OPEN/lease. Intenția persistată JOB_PENDING precede efectul, ACK-ul exact și cleanupul jobului precedă supervisorul; pierderea ACK nu autorizează resend/model dispatch. Nu am probat aceste proprietăți pe servicii reale.

## Dovezi și limite

Dovezile furnizate de părinte sunt păstrate ca atare, nu rerulate ceremonial: 57 teste affected PASS/4.315s, quality Ruff/format/mypy PASS (26 surse), vault probe real FS/crypto cu OCI/PG doubles. Nu sunt restore real. Suita CLI largă este **NOT_GREEN** (366 PASS / 2 FAIL / 70 ERROR); clasificarea părintelui distinge 44 erori înainte de produs din lipsa entrypointului și celelalte 26 din familii observate și independent pe ab79. Nu atribui toate eșecurile baseline-ului și nu revendic broad PASS.

**Real PG/OCI/installed restore, timeout/lost-ACK daemon/family cleanup: NOT_RUN în acest review; QA reală aparține părintelui după reviewurile SOURCE.** Această lipsă nu este un blocker circular pentru admiterea QA; findingul concret R2-COLD-01 cere însă remediere/adjudecare. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Nicio modificare de produs/Git/servicii/config/credentiale/profiluri/HTML. Fișiere create numai raportul, un script mic și artefactele lui private.

Următorul pas: părintele reproduce/adjudecă R2-COLD-01; autorul remediază coliziunea și testul pe un candidat nou, urmat de re-review focalizat al deltei. Nu este cerută redeschiderea scope-ului SOURCE neschimbat sau un harness suplimentar.
