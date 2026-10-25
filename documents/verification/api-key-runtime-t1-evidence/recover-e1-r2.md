# R2 re-review focalizat — R2-RECOVER-01

**Verdict: APPROVED_SOURCE_SCOPED fix. R2-RECOVER-01 (HIGH) închis pe bytes finali pentru charterul pre-efect. Niciun finding nou confirmat.**

## Snapshot și scope

- Worktree: `/home/kali/.hermes/cache/scratch/t1-explicit-recovery-u4ipsfl1/src`.
- HEAD `e1b01a32b278b2368a2855083731f6273c70ba14`; tree `0665ae0d9616677d22d06996c36e1f4f4e5ac6a8`.
- Delta verificată față de `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`: numai `cli/src/omnis_cli/recover.py` și `cli/tests/test_recover.py`.
- SHA256 source: `d4eb35f53b1f085976fe24cdfe8f2c14e6e0e84236acb6517c17db6190586599`; teste: `d84c832cbb2cd012cac0db71053b30371b8071fc3eab74a1c8caa6650c9f68a2`; corespund freeze-ului. Originea importului SOURCE verificată efectiv.
- Reutilizez `reviewer2.md` pentru autorizare/bounds/peer/Stop-owner/concurență neschimbate. R1 SQL/history și celelalte opt paths rămân în aprobarea lor originală, fără extindere. Identitatea completă 10 paths și 113API/27CLI wheel este evidența părintelui, nu QA fizică nouă a acestui review.

## Dispoziția findingului original

`reviewer2.md:15–25` și `parent-r2-reproduction.txt` documentează originalul: OFD ocupat și socket original live treceau inventarul și atingeau fiecare un start interceptat, cu intent/RECOVERING deja persistate. Reproducerul original cere deliberat `effect_calls == 1`, iar vechiul fixture avea listener implicit live.

**Nu am rerulat sau rescris scriptul original și nu îl declar PASS.** Am exercitat testele actuale de produs prin același `main(["recover", "--json"]) → stop_instance(recover=True) → recover_barrier`, cu criteriul corect zero-effect pentru negative. Pozitivul păstrează inode-ul după închiderea listenerului; negativul live folosește explicit `prepare(live_control=True)`. Aceasta schimbă pregătirea fixture-ului, nu scenariul findingului.

| Criteriu | Cod și dovadă observată |
|---|---|
| OFD original ocupat, înainte de intent | `recover.py:132–146`; flock real pe două OFD distincte; exit4/IPC_OWNERSHIP_UNCERTAIN, zero start/scrieri recovery/intent/POST/DELETE, journal și IPC păstrate. |
| Socket original live, înainte de intent | `:147–159`; conexiune reală pe inode-ul original; exit4/IPC_PEER_STILL_LIVE, aceleași absențe de efect. |
| Ambele forme după intent | Al doilea inventar `:223`, înainte de start `:231`; lockul devine ocupat sau socketul deja bound începe să asculte după persistarea/readbackul RECOVERING. Ambele refuză exact, zero start/teardown; intentul și RECOVERING rămân, retry refuzat. |
| Incertitudine/identitate | TimeoutError și EACCES injectate la connect → IPC_OWNERSHIP_UNCERTAIN; înlocuiri reale lock/socket în timpul probei → IPC_IDENTITY_MISMATCH. Zero start/scrieri; lockul original poate fi reacquis. |
| Pozitiv same-channel | ECONNREFUSED real pe socket stale cu inode păstrat și lock liber; un OFD independent ia lockul la start. Un singur start sintetic, completion Stop-owner real → STOPPED; PGDATA și sentinel păstrate. |

Inspecția `recover.py:130–172,205–231` confirmă: numai lock existent, fără O_CREAT; O_NOFOLLOW/O_NONBLOCK; regular/UID/0600/nlink1/gol; flock exclusiv nonblocking o singură dată; numai ECONNREFUSED admite. Timeoutul folosește `remaining(deadline, 0.2)` (`lifecycle.py:26–30`: minimul cu deadline-ul original, deadline expirat refuzat). Postcheckurile verifică inode socket/lock; contextul socket și finally închid descriptorii proprii. Nu există cleanup/unlink în noua probă și lockul nu rămâne ținut la pornirea supervisorului.

## Execuție și integritate

Cwd = worktree. Comandă efectivă:

```sh
set -o pipefail
cli/.venv/bin/python -I -B ../evidence/reviewer2-r2fix-probe.py 2>&1 | tee ../evidence/reviewer2-r2fix-probe.txt
```

**Exit0; 4 metode PASS, 8 subcazuri negative PASS, 3.271s.** Runnerul selectează nemodificate cele patru teste relevante existente. Doar numele temporare sunt scurtate sub `evidence/r2fixreview*` pentru AF_UNIX; HOME/XDG/TMPDIR private și copiii Python primesc -I/-B. Subprocessurile sunt restrânse la interpreterul propriu. **9 fixtures eliminate, 37 copii reaped, rootul privat eliminat**, cu aserțiuni efective de cleanup.

Git status/diff/HEAD/tree și verificarea hashurilor source/originalelor: exit0. `git diff --check`: exit0. Worktree clean, fără editare source/teste sau commit. Originalele freeze/review/reproducer/reproducerea părintelui rămân byte-exact. Create numai acest raport, runnerul și outputul său în evidence.

## Limite și predare

Kernel flock/AF_UNIX și fișierele private sunt reale; Engine/SQL/start/control/familia-container sunt doubles declarate. Nu am rerulat 383SOURCE/383wheel, quality, PG sau canonical neschimbate. Fără Docker, DB nouă, browser/provider/secret, date operator ori citirea HTML-ului protejat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

**QA fizică instalată rămâne NOT_RUN, nu prerequisite circular al acestui verdict. T1 rămâne PARTIAL/NOT_ACCEPTED.** Părintele poate adjudeca închiderea findingului SOURCE și admiterea QA separată; această aprobare nu certifică recuperarea Docker instalată sau închiderea T1.
