# SL04 — owner host Stop-only: contract de integrare și predare

## Verdict și scop

Bază **19457b1eb8640849cd185c85bdf2b0b137cddeff**, worktree
`/home/kali/.hermes/cache/scratch/omnis-sl04-owner-integration`, branch
`sl04-stop-owner-integration`. Ultimul cod produs: **0207156**; snapshotul final
cod + teste: **6ffc9d7**. Commitul acestei note nu modifică artefactul.

**IMPLEMENTED în biblioteca CLI; probe locale PASS, integrarea Stop/Start și
Docker/PostgreSQL fizic NOT_RUN, review independent NOT_REVIEWED.** Părintele
integrează și adjudecă. Nu se activează grantul doar pentru că acest modul există.
Nu s-au modificat `start.py`, `stop.py`, `start_runtime.py`, `control.py`,
`status.py`, `verified.py`, API-ul, IPC-ul serviciilor, oracle-ul, checkoutul
principal, resurse istorice, profiluri Hermes ori provider/target. Niciun push.
Tracerul respins nu a fost preluat. Nu există cgroup manager sau supervisor nou.

## Interfețe exacte

Import din `omnis_cli.stop_owner`:

```python
prepare_stop_inventory(runtime, root, control, record) -> dict[str, object]
run_stop_owner(runtime, root, control, record, grant,
               *, lock_fds=(data_fd, state_fd), deadline=None) -> None
verify_stop_completion(runtime, root, control, record, grant=None) -> None
```

- `runtime`: `ControlRuntime` deja validat, fără `uncertain` și cu
  `family_drained=True`; `root/control` sunt căile canonice existente. Deadline
  este **absolut `time.monotonic()`**, nu durată. Bugetul ownerului este minimul
  deadline-ului runtime/apelantului și 180 s de la apel.
- Toate apelurile de integrare se fac sub **ambele lockuri lifecycle existente**,
  în ordinea data → state. `prepare_stop_inventory` este read-only, nu armează
  DB, nu generează command ID și nu execută Docker CLI. Citește doar Engine UDS
  și identitățile locale. `run_stop_owner` validează FD-urile originale efectiv.
- `record` este receiptul existent strict, cu `stop_command`, `finalize_command`,
  `stop_generation == finalized_generation == stop_expected + 1` și epochul
  supervisorului. `startup.json` trebuie să fie identic cu obiectul transmis.
  Ownerul **nu scrie niciodată `startup.json`**.
- Grantul are exact cheile `version`, `state`, `instance_id`, `command_id`,
  `finalize_command_id`, `generation`, `owner_epoch`, `daemon_id`, `inventory`;
  `version=1`, `state=STOP_PENDING`, tipuri discrete exacte. Un grant mixt,
  `STOP_UNCERTAIN`, bool în loc de int, float sau cheie suplimentară refuză.
- Receiptul separat este `root / f"stop-{stop_command}.json"`, derivat prin
  `omnis_cli.stop_receipt.receipt_path(root, record)`. După verificare părintele
  poate citi `receipt["grant"]` pentru reconcilierea DB. Lipsa ori un receipt
  PREPARED/RUNNING/incomplet nu autorizează relansarea ownerului.
- Erorile trebuie proiectate de caller ca **UNCERTAIN/exit 4**, fără fallback
  la vechiul teardown destructiv după armarea grantului. Ownerul fixed-entrypoint
  însuși iese 4 la refuz; unele precondiții publice propagă `OSError`/`StartError`.

Inventarul fixează release/project/attempt, inode PGDATA și system ID, trei
CID-uri în ordinea API/supervisor/DB cu rol, image ID, amprenta config/mounts și
incarnarea procesului, network ID imutabil + amprentă, identitatea forwarderului
și listenerul, socketurile **originale**, inode-urile lockurilor IPC și
inode/amprenta capability-ului. Niciun raw env/parolă/capability în inventar.
Config/Env rămân doar în răspunsul privat Engine, apoi sunt hash-uite.
Limite: inventar compact ≤2900 bytes, grant compact ≤3600 bytes. Pe fixture-ul
executat: **1799 / 2081 / 2177 bytes** (inventar compact / grant compact / grant
`json.dumps` implicit), sub frame-ul API de 4096 bytes. Schema este validată și
la readback, inclusiv imaginea PostgreSQL instalată; fingerprinturile nu sunt
semnături criptografice împotriva unui atacator same-UID, exclus de arhitectură.

## Wiring obligatoriu în Start și Stop — în sarcina părintelui

1. **Start / `launch_forwarder`:** păstrează entrypointul existent
   `python -I -m omnis_cli.forwarder --socket-dir ... --port ...` și adaugă exact
   la sfârșitul argv `--stop-attempt <attempt_uuid_canonical>` al startupului
   deja persistat. Acest branch nu modifică `launch_forwarder`. Forwarderele
   fără flag refuză noul Stop normal (`STOP_FORWARDER_DRAIN_UNSUPPORTED`), nu
   primesc dovadă de drain retroactivă.
2. **Stop:** păstrează SHUTDOWN/quiesce/FINALIZE/atestările DB ale părintelui.
   Capturează cele două descrieri originale:
   ```python
   with lifecycle_lock(data_home / "omnis", deadline) as data_fd:
       with lifecycle_lock(root, deadline) as state_fd:
           # record FINALIZE fsynced/readback; fără efect host încă
           inventory = prepare_stop_inventory(runtime, root, control, record)
           # API arm-stop real, grant corelat și fence durabil; implementat de părinte
           # NU fabrica grantul ca în fixture-ul explicit sintetic al testelor.
           run_stop_owner(runtime, root, control, record, grant,
                          lock_fds=(data_fd, state_fd), deadline=deadline)
           verify_stop_completion(runtime, root, control, record, grant)
           # Numai acum publică STOPPED și lista completă STOP_STAGES în startup.json.
   ```
   Context managerul `lifecycle_lock` face acum `yield fd`; închide FD-ul fără
   `LOCK_UN`. Nu deschide alte lockuri pentru owner și nu elibera explicit OFD-ul.
3. **Stop repetat / CLI mort înainte de publicația STOPPED:** dacă receiptul
   separat există, nu apela iar `run_stop_owner`. Sub aceleași lockuri apelează
   `verify_stop_completion` pe receiptul STOPPING/STOPPED curent. Numai receiptul
   COMPLETED și readbackul integral permit publicația/repetarea STOPPED. Orice
   altă stare rămâne recovery, fără retry stop/rm și fără deducerea ACK din absență.
4. **Start explicit cu date păstrate:** înaintea primului efect nou și înaintea
   rescrierii startupului, verifică receiptul vechi prin
   `verify_stop_completion`. Păstrează grantul vechi verificat pentru tranzacția
   DB de reconciliere. Părintele pornește numai DB atestată, reconciliază fence-ul
   **înainte** de noul supervisor/acquire/OPEN, apoi continuă Start. Această
   bibliotecă nu poate dezarma singură fence-ul și nu implementează autoresume.
5. **Cleanup servicii:** API/supervisor trebuie să închidă și să elimine propriile
   IPC prin mecanismul existent, sub lockurile lor. Ownerul verifică inode-urile
   originale, apoi absența + lock exclusiv după ACK stop și drain. Stale/foreign
   socket/cap, inclusiv symlink dangling, produc 4 **înainte de efectele următoare
   asupra DB**. Nu unlink, rename, arhivare sau rebind în owner pentru a obține PASS.

Intentul forwarderului este fix `stop-forwarder-{attempt}.json` sub state, cu
version/attempt/command_id/forwarder/listener_inode. Forwarderul existent publică
`stop-forwarder-{attempt}-drained.json` cu același conținut și `drained=true`
**după** listener, taskuri copy/client și transports închise. Receiptul este
fsync/readback. Lipsa, altă comandă ori drain incert nu autorizează continuarea.
Fișierele rămân dovezi private per-attempt; nu sunt socketuri arhivate.

## Protocol și limite operaționale

- Fixed exec `sys.executable -I -m omnis_cli.stop_owner <channel_fd> <data_fd>
  <state_fd>`, cwd state, env doar PATH fix, stdin/stdout/stderr DEVNULL.
  Canalul este socketpair anonim `AF_UNIX/SOCK_SEQPACKET`, nu server IPC nou.
- Ownerul verifică peer UID/PPID, pin parent pidfd, FD/inode/flock și `/proc`
  fdinfo pentru ambele originale cât CLI ține lockurile; le reverifică înainte
  de READY. CLI pin-uiește ownerul înainte de bootstrap și de unicul ADMIT.
  EOF sau parent mort înainte de ADMIT: zero efect host. Receiptul este legat
  și de launcherul originar; un PREPARED abandonat nu este adoptabil.
- După ADMIT nu mai există parent-death kill/liveness gate. CLI poate muri;
  ownerul păstrează ambele OFD-uri și termină receiptul. Un CLI încă viu așteaptă
  bounded; după deadline/grace poate opri numai ownerul pin-uit și păstrează
  incertitudinea. Nu există `waitid(WEXITED)` blocant după DONE: se folosește
  WNOHANG/WNOWAIT și reap bounded, inclusiv pe răspuns de eroare/EOF.
- Client Engine **fără copii**: GET info, image/container/network inspect și
  liste filtrate, POST stop CID (`t=15`), DELETE CID (`force=false&v=false`),
  DELETE network ID exact. Nu există create/start/exec, proxy, URL/argv public
  generic, shell sau retry. ACK mutație exact **204**; read-only exact **200**.
  304/404 la mutație, timeout/ACK pierdut nu completează etapa. 404 la inspect
  după ACK rm este absență permisă. Socket/peer/daemon reconfirmate; total budget,
  cap 1 MiB wire, 16 KiB headers și JSON depth 32, fără redirect/proxy.
- Etape distincte: forwarder, api.stop, api.rm, supervisor.stop, supervisor.rm,
  db.stop, db.rm, network.rm, ipc. Fiecare PREPARED fsynced/readback precede
  mutația; ACK + readback/drain precede intrarea fsynced în completed. Numai
  receiptul final COMPLETED este reutilizabil.
- Container rm cere stare exited, PID 0, ExitCode exact 0, OOMKilled/Dead/
  Restarting/Paused false, config original și familie drenată. Implementarea
  Linux citește **cgroup v2 existent**: cale cu CID exact, inode original,
  pidfd lider, apoi `cgroup.events populated=0` (include descendenți) ori cgroup
  dispărut după ACK. Nu creează/mută/omoară procese prin cgroup și nu deleagă unul.
  Un host unde această dovadă nu e disponibilă refuză înainte de semnalul către
  forwarder; compatibilitatea fizică trebuie probată de părinte. Niciun drept de
  a adopta procese străine, cgroup v1 sau alt layout necunoscut.

## Commituri, RED/GREEN și artefact

Ordine de integrare (toate locale):

| Commit | Schimbare / dovadă |
|---|---|
| `7316ca1` | FD lifecycle original. RED: context manager returna None; GREEN: duplicatul păstrează flock după închiderea callerului. |
| `897c061` | Engine childless tipizat. RED: modul absent; GREEN: UDS 204 vs 304/404/500, o singură mutație, trickle total-deadline. |
| `dbb93ae` | Forwarder drain durabil. RED: flag absent/EOF readiness; GREEN: bytes în ambele sensuri, clienți ținuți vii, drain și receipt după SIGTERM; 11 regresii forwarder. |
| `653c2df` | Owner/handoff/receipt și probe. RED-uri reale: owner lipsă, owner nereaped pe EOF post-admitere, incarnare CID omisă, IPC stale detectat prea târziu, familie neprobată după semnalul forwarder. GREEN: originale, pin/lock failures, parent-death, owner-death, ACK fără waitid blocant, no-op/lost ACK/IPC rămas. |
| `f3f29f4` | Readback strict. RED: cheie necunoscută în inventarul COMPLETED acceptată; GREEN: inventar și launcher malformed refuzate. |
| `98ca10d` | Engine JSON depth. RED: structură foarte adâncă acceptată; GREEN: chunked pozitiv, size/nesting negative, 3/3. |
| `0207156` | Binding DB image la readback. RED: alt image ID bine format acceptat; GREEN: refuz pe același canal; observare owner fără copii în timpul requestului. |
| `6ffc9d7` | Probă suplimentară stock-entrypoint: EOF după READY cu launcher viu → exit4/zero efect și refuz relansare PREPARED. |

**Ultima verificare după cod/teste:**

- `cli/.venv/bin/python -I -m unittest discover -s cli/tests -v`, umask077:
  **194 teste / OK / exit0**, log privat
  `/home/kali/.hermes/cache/scratch/omnis-sl04-owner-integration-final-source.log`.
- Build cu uv pinuit: `uv build --no-config --offline --wheel cli --out-dir ...`,
  venv nou Python3.13.15, `uv pip install --no-config --offline --no-deps`.
  Cwd extern, Python `-I`, import verificat din site-packages al venv-ului nou;
  aceeași suită **194 / OK / exit0**, fără ResourceWarning în log.
- Artefact final: `/home/kali/.hermes/cache/scratch/s4owner-final-0seL06/dist/omnis_cli-0.1.0-py3-none-any.whl`;
  SHA256 `77df5f7085e4bcbe96863199e836a6d834d73c8422f34e68cb5ea84408f4f9da`.
  Hashurile modulelor `stop_owner/stop_receipt/stop_engine/forwarder/lifecycle`
  sunt identice sursă → wheel. Log wheel: același root, `wheel-tests.log`.
- Ruff check/format CLI: **exit0**, 46 fișiere formatate conform pinului;
  mypy `--no-incremental`: **exit0**, 19 module sursă. `git diff --check`: exit0.
  API și CLI environments create numai prin uv locked/offline, fără instalare globală.
- Din logul wheel: **16 probe Stop-owner/Engine/forwarder/receipt, toate OK**, incluse
  în cele 194 (nu un al doilea total). `python scripts/render_docs.py --check`:
  exit0; `python -m unittest discover -s tests/documentation -v`: **62 / OK / exit0**.
  Scanul diff-ului produs nu a găsit shell=True/os.system/eval/pickle; verificarea
  căilor schimbate a confirmat zero module interzise ori fișiere API.

**Delimitarea probelor:** procesele, anonymous FD-urile, flock/pidfd, parent/owner
SIGKILL, TCP/UDS forwarder și fsync/readback sunt reale, exclusiv fixtures noi.
`stop_owner_fixture.py` este un **peer Engine sintetic**, nu Docker. Pentru
pozitivele care execută tot teardownul, numai `_ContainerFamily` este înlocuit
explicit în procesul de test cu pidfd-uri ale proceselor sintetice ținute vii;
asta **nu certifică cgroup/Docker fizic**. Stock entrypoint este exercitat separat
la READY/EOF, FD-uri independente cu aritate corectă, pin failure și refuzul
familiei neprobabile. Parent-death înainte de ADMIT păstrează writerul canalului
în observer ca să nu confunde EOF cu dovada morții părintelui. Parent-death după
ADMIT este injectat la requestul Engine, ambele lockuri rămân indisponibile,
ownerul termină; owner-death pe același canal păstrează PREPARED/refuz de reuse.
No-op Engine lasă procesele vii: nu există succes obținut din expirarea lor naturală.

## Ce rămâne NOT_RUN / responsabilitate de integrare

- API grant real, fence/reconcile PostgreSQL, snapshotul compus cu schimbările
  părintelui, Start → Stop → Start instalat și sentinel PG păstrat.
- Docker fizic: ACK-uri Engine, cgroup/PID/drain, cleanup-urile reale API/supervisor,
  faulturi după fiecare ACK/fsync și compatibilitatea exactă a daemonului instalat.
- `make check`, `make check-installed-start`, `make check-installed-pair-open`,
  `make check-installed-stop`: **NOT_RUN în acest workstream**, interzise aici;
  părintele le deține serial. Nu se repetă probe locale pentru un reminder.
- Review independent al acestui snapshot: **NOT_REVIEWED**, cerut la integrare.
  Reticle CLI/procese: NOT_APPLICABLE. Chisel: NO-GO/BLOCKED, neexecutat.
- S04/S06/SL04 globale rămân PARTIAL; M03/M22/G00/CI remote nu sunt promovate.
  Nicio recuperare istorică nu a fost citită ca autoritate ori operată.

Lecții de reutilizat la review: original OFD, nu lock similar; ACK ≠ EOF/exit;
identitatea unui CID include și incarnarea procesului; validează schema completă
și bindingurile readbackului offline; verifică cleanup-ul fiecărui serviciu înainte
să atingi DB; seam-ul cgroup sintetic nu devine probă Docker. Rollback: `git revert`
în ordinea inversă a dependențelor, rebuild și regresii; Git nu dezarmează fence-uri
DB și nu reconciliază receipturi incerte. Nu șterge dovezile ca mecanism de retry.
