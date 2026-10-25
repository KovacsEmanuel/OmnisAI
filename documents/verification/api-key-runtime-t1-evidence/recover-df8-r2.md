# Review2 independent — recuperare explicită T1

**Verdict: CHANGES_REQUESTED — un finding reprodus, limitat la refuzul IPC pre-efect.**

## Snapshot și limită

- HEAD `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`; tree `9d0a3a1e9e5a45ffcf31cf76eea879d68b52063c`; base `dd4f8747287496d1bb589de277455354d122892a`.
- Worktree `$W=/home/kali/.hermes/cache/scratch/t1-explicit-recovery-u4ipsfl1/src`, clean înainte/după. Cele 10 changed paths corespund manifestului. Identitatea wheelurilor/probelor verificată de părinte este context reutilizat, nu verificare fizică efectuată aici.
- Citite AGENTS, CONTRIBUTING, team-slice, CURRENT și contractul CLI afectat. Review complementar R2: autorizare, UID/peer/CID/daemon/storage/capability, pre-efect, concurență, incertitudine și cleanup. Nu redeschid canonical8 sau charterul SQL/history al R1.

## Finding R2-RECOVER-01

**Severity: HIGH (blocant pentru contractul pre-efect; nu escaladare de privilegii demonstrată).**

**Path:line:** `cli/src/omnis_cli/recover.py:126–135`, consumat la `:168–194`.

**Defect:** inventarul `dead=True` verifică inode/mod/owner pentru socket și forma fișierului `control.lock`, dar nu verifică dacă lockul este ocupat sau dacă socketul original încă acceptă conexiuni. Ambele situații trec cele două inventare, persistă intentul/journalul RECOVERING și ajung la `ControlRuntime.run("start", CID_original, effect=True)`.

**Reproducer:** `reviewer2_probe.py`, folosind `RecoveryFixture` existentă și callerul real `main(["recover", "--json"])`. DB/daemon/HTTP sunt doubles declarate; `runtime.run` este interceptat înaintea oricărui efect. Pozitiv: listener închis, inode păstrat, lock liber. Negative independente: (a) aceeași configurație, dar un OFD distinct deține `LOCK_EX` pe lockul original — al doilea FD confirmă efectiv conflictul; (b) socketul original privat acceptă efectiv o conexiune. În **toate trei**: `effect_calls=1`, `phase=RECOVERING`, intent prezent. Interceptorul întoarce exit4, nu un succes fabricat; zero POST/DELETE chiar și către Engine-ul sintetic.

`reviewer2_ipc.py` confirmă independent cu implementarea reală `LocalControl.__aenter__`: pozitivul este admis, lockul ocupat produce `BlockingIOError`, socketul activ produce `ValueError`. Refuzul real există, dar prea târziu: supervisorul execută `acquire`/reconcile/quiesce înainte de intrarea în LocalControl (`api/src/omnis/supervisor/__main__.py:105,158–179`; `api/src/omnis/transport/local_control.py:95–104`). Astfel pornirea și posibil takeoverul/bariera preced refuzul; intentul deja durabil blochează retry-ul obișnuit.

**Criteriu încălcat:** numai supervisor original mort, cu ownership verificat; stare foreign/incertă refuzată **înainte de efect**, fără pornire sau teardown. CID oprit nu demonstrează că IPC-ul rămas este abandonat.

**Remediu minim:** în inventarul `dead=True`, verificați nedistructiv disponibilitatea lockului existent prin FD privat + `flock(LOCK_EX|LOCK_NB)` și, pentru socket existent, acceptați numai `ECONNREFUSED` la proba bounded. Conexiune reușită/orice incertitudine → refuz înainte de intent și la revalidarea pre-start. Eliberați numai FD-ul propriu înaintea pornirii; nu ștergeți socket/cap/lock și nu țineți lockul împotriva noului supervisor. Reutilizați regula existentă din `lifecycle.py:151–152,175–210`, fără cleanup-ul acelei funcții. Adăugați cele două negative cu zero start/intent și păstrați pozitivul cu socket stale.

## Acoperire fără alte findings confirmate

- Inspecție: profil normal T1/READY5, bounds generation/epoch, UUID/CID, release/image/daemon/config și mounturi exacte, UID și stocare originală; fără recreate, OPEN, autoresume sau provider-send pe traseul recover.
- Intent fsync/readback înaintea startului, revalidare journal/owner, un singur start, retry blocat după întrerupere; fallback emergency dezactivat pentru recover.
- Lockurile lifecycle în aceeași ordine ca Start/Stop, aliasurile OFD și handofful către Stop-ownerul existent păstrate; Start queued nu devine restart implicit după STOPPED.
- Coroborare peer PID real + UID/capability, SHUTDOWN/FINALIZE corelate pe comandă/generație/epoch, grant exact și completion verificat înainte de STOPPED; bounds 4096/3600/16384 păstrate. Peer PID greșit refuzat înainte de trimiterea capability: **0 bytes**, versus 126 bytes pentru peerul exact.

## Probe executate

Cwd `$W`; outputurile sunt în `../evidence/reviewer2-*`.

1. `cli/.venv/bin/python -I -B ../evidence/reviewer2_probe.py` → **exit0**, defect confirmat, `reviewer2-probe.txt`.
2. Aceeași comandă cu argument `regression` → **exit0, 10 teste PASS**: cele 7 recover și 3 grant-client existente; `reviewer2-regression.txt`. SOURCE/sintetic: include ACK-loss, journal drift, queued Start/Stop/recover, Stop-owner/completion și bounds; nu Docker instalat.
3. `TMPDIR=$W/../evidence/reviewer2 api/.venv/bin/python -I -B ../evidence/reviewer2_ipc.py` → **exit0**, IPC privat real, fără DB; `reviewer2-ipc.txt`.
4. `TMPDIR=$W/../evidence/reviewer2 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml -q --tb=short api/tests/test_instance.py::test_owner_loss_new_shutdown_source api/tests/test_instance.py::test_shutdown_wire_maximum_and_rejected_inputs_source` → **exit0, 14 PASS SOURCE**, `reviewer2-api-source.txt`.

Numele directoarelor temporare ale fixture-ului au fost scurtate exclusiv sub `evidence/reviewer2*` pentru limita AF_UNIX; copiii Python au primit `-B`. Validatoarele/produsul nu au fost relaxate. Cleanup-ul fixture-ului a verificat reap/pidfd/join; directoarele temporare au dispărut, TMPDIR privat rămas gol. Create numai raportul, două reproducere SOURCE și patru outputuri; nicio editare în worktree.

**Neexecutat:** Docker/PG nou, QA fizică instalată, crash/signal fizic, provider/browser/rollout, canonical neschimbat; fișierul HTML protejat și datele operatorului necitite. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
**Risc rămas:** findingul necesită adjudecare/remediu/re-review focalizat; QA instalată rămâne NOT_RUN, nu prerechizit circular pentru review. T1 nu este închis.
