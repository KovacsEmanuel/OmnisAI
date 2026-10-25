# R2-RECOVER-01 — remediu frozen, fără acceptare T1

## Identitate și scope
- Worktree exclusiv `/home/kali/.hermes/cache/scratch/t1-explicit-recovery-u4ipsfl1/src`, branch `impl/t1-explicit-recovery-20261025`.
- Commit nou local **`e1b01a32b278b2368a2855083731f6273c70ba14`**, tree `0665ae0d9616677d22d06996c36e1f4f4e5ac6a8`; worktree clean. Fără amend/squash/push.
- Delta față de candidatul `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`: numai `cli/src/omnis_cli/recover.py` și `cli/tests/test_recover.py`; diff SHA256 `6d7a7eebefd431719ac3032f0e1f510db97dc2e23fcef497d68f2f0c34e240e5`.
- Față de baza `dd4f8747287496d1bb589de277455354d122892a`: aceleași 10 paths ale candidatului inițial; diff SHA256 `b7e2e7b049aaa0ca4ee1a0a9ef77e9deb428990f612e612fb4c463303348958b`.
- `freeze-r2fix.json` conține toate paths/blob/SHA pentru ambele delte, comenzi/exits, hashuri de probe, wheeluri și module parity. `freeze.json`, R1/R2 și reproducerele originale sunt păstrate byte-exact.

## Produs și controale
Consumer: CLI real `main(["recover", "--json"])` → `stop_instance(recover=True)` → `recover_barrier` → ambele inventare `dead=True`, apoi Stop-ownerul existent numai pe calea admisă. Criteriul este refuzul unui IPC încă deținut înaintea efectului, nu un PASS de harness.

Inventarul deschide numai lockul existent cu O_NOFOLLOW/O_NONBLOCK, verifică fișier regular/UID/mode0600/nlink1/gol și încearcă o singură dată flock exclusiv nonblocking. Pentru socketul existent/pinned, connect este limitat la min(0.2s, timpul rămas din deadline-ul original); numai ECONNREFUSED este stale. Succesul, timeoutul sau eroarea incertă refuză. Inode socket/lock sunt revalidate; FD-ul propriu se închide în finally înaintea copilului. Nu creează/șterge IPC, nu așteaptă eliberarea lockului și nu schimbă cleanup-ul shared.

- Preflight: OFD distinct ocupat și socket original live, independente, cu kernel flock/connect reale → zero daemon start, intent, scrieri recovery/journal și teardown; inode/cap păstrate.
- Revalidare: după persistarea/readbackul autentic al intentului și RECOVERING, lockul devine ocupat sau același socket bound devine listener → zero start, UNCERTAIN și intent/RECOVERING păstrate. Retry refuză prin validatorul existent.
- Pozitivul fixture-ului închide listenerul inițial, păstrează inode-ul și verifică ECONNREFUSED real. La start, un OFD independent poate lua lockul; fluxul ajunge la completion-ul/receipturile reale Stop-owner → STOPPED, cu Engine/SQL/control/start/familie-container sintetice declarate.
- Controale suplimentare: TimeoutError/EACCES injectate numai la proba socketului propriu; înlocuiri efective de inode lock/socket în timpul probei. Refuz fără scrieri/start și lockul original poate fi reluat după eroare.

## Probe și comenzi
Cwd = worktree. Toolchain existent: Python3.13.15, uv0.12.19, Ruff0.16.9, mypy2.3.1. Pentru unittest:

```sh
export TMPDIR=/home/kali/.hermes/cache/scratch/r2f-zudnw0fn
export XDG_CONFIG_HOME=$TMPDIR/config
export XDG_RUNTIME_DIR=
cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -v
../evidence/cli-wheel-env-r2fix/bin/python -I -B -m unittest discover -s cli/tests -v
```

| Probă | Rezultat și limită |
|---|---|
| TDD `-p test_recover.py -k control_ipc -v` înainte de produs | exit1; 2 metode/4 subcazuri ating incorect startul interceptat; `r2fix-red.txt` |
| Recover după fix | 10 metode PASS/exit0; `r2fix-green-final.txt`; ultima editare ulterioară este numai bindingul closure de test, rerulat integral mai jos |
| SOURCE final | **383 PASS, exit0, 98.596s**, `r2fix-cli-source-final.txt` |
| Wheel final | **383 PASS, exit0, 98.111s**, `r2fix-cli-wheel-final.txt` |
| Ruff check `--no-fix`, format `--check` pe `cli/src cli/tests` | exit0 după ultima editare; config `api/pyproject.toml`, interpreter API propriu, `-I -B` |
| mypy `--no-incremental --output=json cli/src` | exit0 după ultima editare; același manifest strict, PYTHONPATH/MYPYPATH eliminate |
| `uv build --no-config --offline --wheel cli --out-dir ../evidence/cli-wheel-r2fix` | exit0; wheel nou final |
| Instalare wheel | venv nou privat din interpreterul CLI existent, offline/no-deps; exit0; origine reală verificată |
| Git | diff --check exit0, commit separat/readback, clean |

Comenzile integrale/exits și SHA-urile outputurilor sunt în freeze. Testele executate folosesc IPC/fișiere/procese proprii; directorul TMPDIR este gol după cleanup. Fixture-urile existente verifică reap/pidfd/join. Callerul recovery pe wheel este importat din noul site-packages; copilul Stop-owner al fixture-ului existent selectează explicit SOURCE. Nu prezentăm acest lucru drept recuperare Docker instalată.

### Artefacte
- CLI final: `cli-wheel-r2fix/omnis_cli-0.1.0-py3-none-any.whl`, SHA256 **`9f73d9944676f812f2f23c3a79814d8b2323fa721c0386dd54953e112116eb24`**. **27/27 module** identice SOURCE↔wheel↔instalat; origine `cli-wheel-env-r2fix/lib/python3.13/site-packages/omnis_cli/recover.py`.
- API reutilizat, fără rebuild: `api-wheel/omnis_api-0.1.0-py3-none-any.whl`, SHA256 **`26e403514e6d98d21d4b5f2100dae2ab4a36f2eab98fb3a84c256d73dfcc3987`**; **113/113 module** reconfirmate identice sursei.
- `_owner` SQL neschimbat byte-exact față de df8; SHA256 al funcției `df544ff739ffc1b48a13f98122e35180b8f82d54e3684f488ebdff40de82304b`. API/SQL/history/Stop-owner și celelalte 8 paths ale freeze-ului inițial sunt neschimbate. PG original și R1 APPROVED_SOURCE_SCOPED se reutilizează numai în charterul neschimbat; nu aprobă noul guard IPC.

## Încercări nereușite păstrate
- `r2fix-green.txt`: primele controale preflight/revalidare au trecut noul refuz; două aserțiuni suplimentare de retry cereau eronat RECOVERY_INTERRUPTED. `_preflight_record` refuză deja faza RECOVERING cu RECOVERY_REQUIRED înaintea verificării intentului. Corectată aserțiunea la comportamentul existent, fără modificare de produs/validator.
- Ruff a cerut binding explicit pentru variabilele closure din subteste; corectat fără ignores. `r2fix-ruff.txt` păstrează ultima eroare pre-final. Suitele complete/quality de mai sus sunt după ultima editare.
- Reproducerul R2 original confirmă BUG pe df8 și nu a fost modificat/reexecutat pentru a obține verde. Noile teste de produs cer zero effect. Niciun ciclu suplimentar de harness fără progres de produs: remediul a schimbat efectiv cele patru refuzuri; nu s-a lansat o a treia frontieră/harness.

## Predare / limite
**AICI: implementare SOURCE/wheel verificată; focused re-review NOT_RUN; QA fizică NOT_RUN; T1 PARTIAL/NOT_ACCEPTED.** Părintele re-reviewuiește bytes finali, apoi decide admiterea QA fizice. Nu am editat trackingul comun și nu am aprobat propria integrare.

Fără Docker/PG nou, provider/model/target/browser, date operator/chei, fișierul HTML protejat, global/profile, deployment sau push. Nu am rerulat API/PG/canonical/docs neschimbate. READY9 nu a fost atinsă. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Revertul commitului revine numai asupra codului/testelor, nu asupra stării externe.

Lecție pentru părinte, dacă actualizează ulterior skillul de testare: un CID mort nu dovedește IPC abandonat; pozitivul recovery trebuie să păstreze inode stale real, iar negativele să conteste OFD-ul și listenerul înainte și după intent. Nu am modificat skilluri în afara ownershipului.
