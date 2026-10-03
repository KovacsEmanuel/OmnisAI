# SL04 — wiring Start → Stop-owner → Start DB-only/reconcile

## Verdict și snapshot

**IMPLEMENTED în consumatorii CLI; source/wheel privat PASS; OCI/PostgreSQL NOT_RUN; review independent NOT_REVIEWED.** Nu este integrare în principal sau acceptare SL04/G00.

- Worktree: `/home/kali/.hermes/cache/scratch/omnis-sl04-installed-integration`, branch `sl04-installed-integration`.
- Bază primită: `f6901f1d708d459329b2c0b6117f26623988f71f`.
- Snapshot cod + teste verificat final: **`dc013ed7038d380ffb5676422717bd1492f29a71`**. Commitul acestei note nu modifică artefactul.
- Autoritate: arhitectură §4.1–4.5, [contract DB](p04-stop-db-reconciliation.md), [contract owner](p04-stop-owner-integration-contract.md), AGENTS/CONTRIBUTING. Fără modificări API, schemă, stop_engine, stop_receipt, IPC, Compose/validate_config, deadline policy, PID1, toolchain, profiluri sau HTML.
- În `stop_owner.py` este schimbată **numai semnătura `_View.run`**, cu parametrul opțional `stdin`; implementarea rămâne refuzul executării de comenzi. R1–R4 ale ownerului NU sunt reparate/importate aici.

## Interfețe și comportament livrat

### Start și Stop

`launch_forwarder(root, port, deadline, *, ownership=None, stop_attempt=None)` păstrează consumatorii existenți. `start_instance` transmite întotdeauna `stop_attempt=str(record['attempt'])`; argv real primește trailing `--stop-attempt <attempt>`.

Stop păstrează SHUTDOWN/quiesce/FINALIZE, persistența/readbackul FINALIZE și atestarea DB existentă. Sub originale `data_fd`, `state_fd` primite de la `lifecycle_lock`:

1. `prepare_stop_inventory` read-only;
2. `request(control, {op: arm_stop, instance_id, command_id, finalize_command_id, generation, owner_epoch, daemon_id, inventory}, deadline=...)` pe clientul autentificat existent;
3. validare exactă a grantului întors, fără fabricare în produs;
4. `run_stop_owner(..., lock_fds=(data_fd, state_fd), deadline=deadline)`;
5. `verify_stop_completion`, apoi toate `STOP_STAGES`, STOPPED fsynced/readback.

Normal Stop și repetarea nu mai apelează `_resume_owned`. După FINALIZE/armare, erorile nu intră în emergency. STOPPING finalizat fără receipt owner, PREPARED/incomplet sau grant incompatibil refuză fără reemitere; COMPLETED independent permite publicarea STOPPED dacă apelantul precedent a murit/pierdut publicația. Stop repetat, `readback_stopped`, Start și Status cer dovada owner. Eșecul citirii acesteia este exit4, nu un fals STOPPED/exit0 sau o simplă indisponibilitate exit3.

**Compatibilitate cu R1 al părintelui:** toate importurile owner din Stop sunt **locale consumatorilor**. Ownerul poate importa top-level `_stopping_record` fără ciclu. Proba în interpreter nou injectează numai dependența de import, nu copiază commitul R1.

### Restart explicit și jobul fix

Modul nou minimal `omnis_cli.restart`:

- `prepare_restart(runtime, root, control, stopped, attempt) -> dict[str, object]`;
- `reconcile_database(runtime, root, control, record, intent, env) -> None`.

După atestarea owner/PGDATA/instance/release/daemon/resurselor și înainte de înlocuirea startupului:

- `stopped-<old_stop_command>.json`: **copia exactă a bytes-ilor** vechiului STOPPED, inclusiv whitespace/CRLF; file fsync + directory fsync + byte readback;
- `restart-<old_stop_command>.json`: intent separat cu version/state, old stop/attempt, hashul copiei, new attempt, request, network/job, ACK. ID-ul nou de reconciliere este în `request` înainte de job. Un intent deja existent refuză o nouă încercare oarbă.

Se creează/pornește numai DB proprie și rețeaua control. Sunt verificate system ID, instance ID și schema originale înainte de job și de supervisor. Nu se rulează migrare de upgrade pe date păstrate.

Job: imaginea API instalată, `python -I -m omnis.stop_reconcile`, fără argumente libere, mounts, Docker socket sau ports; UID/GID mapped, rootfs read-only, cap-drop ALL, no-new-privileges, restart no, pull never și control network. Rolul `reconcile` este atestat înainte/după execuție: command, image, attempt, project/role, network inclusiv la container creat, zero mounts/binds/tmpfs, confinement și env exact derivat din imagine + cele două variabile allowlisted ale migratorului. DSN nu intră în argv sau diagnostic.

`docker create --interactive --attach stdin --attach stdout --attach stderr` fără TTY configurează OpenStdin/StdinOnce și attach; `start --attach --interactive` primește inputul. `ControlRuntime.run(..., stdin: bytes | None = None)` extinde runnerul existent: max16384 bytes înainte de spawn, scriere nonblocking în selectorul existent, EOF real prin close, aceleași ownership/deadline/sticky uncertainty guards. Nu există supervisor generic nou.

Inputul exact: `version`, `reconciliation_id`, `system_identifier`, `grant`, `completion_sha256`. Hashul este SHA256 al **bytes-ilor reali** ai receiptului owner COMPLETED, citit binar/no-follow, nu al unui obiect JSON reserializat. Se verifică stabilitatea bytes-ilor și la admiterea jobului.

Succesul cere JSON unic exact/corelat, fără chei duplicate/extra sau stdout mixt, stderr gol, exit client0, container Exited0/PID0/fără OOM/Dead/Paused/Restarting, client family drained, nicio incertitudine ori resursă străină. Jobul propriu este eliminat/readback, apoi ACK-ul se persistă/readback **înainte de supervisor create/start/acquire/OPEN**. Testul pozitiv continuă la READY/generația3; absența fence-ului nu este folosită ca autoritate.

Orice rezultat incert păstrează DB, intentul și copia STOPPED; nu face rebind, autoresume sau alt job. Erorile restartului sunt exit4. Dacă restartul a născut deja un forwarder propriu, reutilizează stop/reap bounded pe pidfd-ul deținut și păstrează locatorul diagnostic, fără PID numeric fallback sau teardown al DB.

## Dovezi RED/GREEN și limitele canalelor

| Frontieră | RED efectiv | GREEN / control |
|---|---|---|
| Forwarder din Start real | argv fără trailing attempt în probele caller | 24 teste forwarder; callerul observă argv procesului real |
| Stop normal | noul test ajungea în `_resume_owned`, nu arm/owner | consumator real + fișiere/flock; originale FD, ordine finalize→inventory→arm→owner→verify; wrong grant și pierdere arm/owner fără fallback |
| Stdin | trei erori pentru parametrul inexistent | max16KiB + EOF real; oversize fără spawn; backpressure timeout cu incertitudine și copil reap |
| Restart | copia STOPPED absentă înainte de DB create; traseul vechi încerca cleanup | bytes/copii/intent reale, ordine DB-only→reconcile→ACK→supervisor→OPEN→READY; DB/OCI/HTTP/forwarder explicit substituite în acest test |
| Rol reconcile | `CONTAINER_ROLE_INVALID` | command/env/noMount/image/attempt/confinement mutate pe același attestor |
| Network creat | rețeaua străină acceptată când Running=false | refuz înainte de start, pozitivul pe același canal |
| Owner proof lipsă | Start/Status exit3 în loc de4 | ambele intrări exit4, jurnal neschimbat; receipturi PREPARED/pending/partial/foreign/extra refuză și Stop |
| R1 import | ImportError pe modul Stop parțial inițializat | importuri locale; probă nou interpreter fără copiere R1 |
| Pierdere startup write | exit3 după intent restart durabil | exit4, copii/intent păstrate, fără efect/retry |
| Forwarder restart întrerupt | copil ținut pe pipe încă viu (`returncode=None`) | copil închis/reap0 prin ownerul real, DB și intent păstrate; rescue de test numai după aserțiune |

`test_lifecycle_consumers.py` merge dincolo de mocks de funcții: clientul control autentic pe **UDS privat sintetic**, owner exec real, forwarder real, lockuri/FD/pidfd și receipturi reale. Numai peerul Engine și dovada cgroup (`SyntheticFamily`) sunt substituite; SQL/readiness sunt seams explicit marcate. Verifică Stop, repetare fără alte mutații și pierderea publicației STOPPED pe ambele părți ale scrierii după owner COMPLETED. Un Start într-un copil gate-uit/pin-uit iese abrupt cu `os._exit(91)` la prima frontieră DB; părintele citește copia exactă/intentul și refuzul retryului. Nu este SIGKILL Docker/PG sau crash-cut fizic instalat.

Negativul de reconciliere acoperă ACK pierdut/mixt/străin, tip bool versus int, chei extra/duplicate, stderr, client nonzero, container nonzero/OOM, cancel, family nedrenată, incertitudine sticky, resursă străină și scriere ACK pierdută. Niciunul nu atinge supervisor/OPEN. Eșec după ACK înainte de servicii păstrează și el DB/intent și refuză retry.

Fixture-urile owner au fost mutate 0005→0006, fără adopție legacy. Vechiul test care permitea replay după stage-uri parțiale cere acum **refuz și zero efecte sub ambele epoch-uri**: contractul s-a înăsprit, nu s-a slăbit oracle-ul de crash. Oracle-urile OCI nu au fost editate.

## Verificarea finală executată

Toolchain: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv` **0.12.19**, Python **3.13.15**. API/CLI venv proprii prin `uv sync --locked --no-config --offline --directory api` și `--directory cli`, exit0. Configurația testelor este numai un XDG_CONFIG_HOME nou privat; profilul operatorului nu este modificat.

Pe **dc013ed**, umask077, source apoi wheel **serial**:

```text
XDG_CONFIG_HOME="$PWD/cli/.venv/test-config" cli/.venv/bin/python -I \
  -m unittest discover -s cli/tests -v
# 235 tests, OK, exit0, 43.217s

uv build --no-config --offline --wheel cli --out-dir "$PROOF/dist"
uv venv --no-config --no-python-downloads --python 3.13.15 "$PROOF/venv"
uv pip install --no-config --offline --no-deps --python "$PROOF/venv/bin/python" \
  "$PROOF/dist/omnis_cli-0.1.0-py3-none-any.whl"
uv pip check --no-config --python "$PROOF/venv/bin/python"
# fiecare exit0

cd "$TMPDIR"
XDG_CONFIG_HOME="$PROOF/config" "$PROOF/venv/bin/python" -I \
  -m unittest discover -s "$REPO/cli/tests" -v
# 235 tests, OK, exit0, 41.466s; cwd extern; import din site-packages verificat

api/.venv/bin/python -I -m ruff check --config api/pyproject.toml cli/src cli/tests
api/.venv/bin/python -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests
api/.venv/bin/python -I -m mypy --config-file api/pyproject.toml --no-incremental cli/src
# exit0 / exit0 (58 fișiere) / exit0 (21 module)
git diff --check
# exit0
```

- `PROOF=/home/kali/.hermes/cache/scratch/sl04-wiring-delivery-JaQgkm`.
- Wheel SHA256: `0acc71bd34516aed908d8051241b78dbec390355c355f9c3bdd8caa26ee9ec27`.
- **21 module identice bytes source → wheel → site-packages**; readback executat, nu inferat din build.
- Log source: `/home/kali/.hermes/cache/scratch/sl04-wiring-delivery-source.log`; wheel: `$PROOF/wheel-tests.log`. Fără ResourceWarning în cele două loguri finale.
- Scan limitat pe liniile de produs adăugate: fără shell=True/os.system/eval/exec/pickle. Nu înlocuiește reviewul independent.
- Documente: `/home/kali/.hermes/cache/scratch/p0tools-k39nr13l/docs/bin/python -I scripts/render_docs.py --check` → cele cinci HTML canonice OK, exit0; același interpreter cu `-I -m unittest discover -s tests/documentation -q` → **62 tests / OK / exit0**. Niciun HTML regenerat. `git diff --check` → exit0. Scanul suplimentar de literali credentials pe diff-ul produs: zero matches; scanul căilor a găsit numai fișierele permise și nota proprie.

Încercări nereușite păstrate: primul baseline fără XDG_CONFIG_HOME izolat a raportat CONFIG_INVALID, fixture owner schema0005 și **215 teste /77 failures/18 errors**; wrapperul a expirat la180s după outputul suitei. Nu este baseline verde. Primul whole source după wiring/schema a avut **226 /5 failures/2 errors**, limitate la vechile fixture-uri pozitive fără owner; au fost înlocuite cu dovezi sintetice explicit marcate și validatoare reale. Primul peer de test nou omitea câmpurile de corelare SHUTDOWN și a fost refuzat; fixture-ul a fost corectat, clientul nu a fost relaxat. Comanda forwarder imediat înainte de `f1f63bc` a omis env-ul izolat și a eșuat; rerularea explicită ulterioară a dat24/24. Corpul `5215f28` spune25 teste process; outputul exact era **22 process +3 stdin**, nu25 process. Rezultatele finale de mai sus înlocuiesc aceste formulări prea largi, fără rescriere de istoric.

## Commituri de preluat, în ordine

`f1f63bc` → `5932cbb` → `5215f28` → `88e1f44` → `4a113f4` → `a628381` → `921dc52` → `fa6c2cd` → `6bb35b1` → `7569c88` → `b6051c5` → `8d84117` → `dc013ed`, apoi commitul acestei note. Istoric păstrat; fără amend/squash/push.

## Integrare rămasă la părinte

1. Review independent pe acest snapshot și integrare cu owner R1–R4 (`0a94e4f`, `50ad705`, `a017909`, `6fc209e`) **numai după verdictul lor**. Nu au fost cherry-pick-uite aici. Păstrează fixurile ownerului și singura extensie de semnătură `_View.run(stdin=None)`; importurile locale din Stop previn ciclul anunțat.
2. Păstrează M03 Compose al părintelui `d81a396`; `validate_config` și oracle-ul său nu au fost schimbate aici. Metoda nouă din `test_start_attestation.py` privește rolul OCI reconcile, nu configurația Compose.
3. Rebuild API/CLI/release în imaginea reală și review/gates canonice seriale după integrare. **Docker, PostgreSQL, sentinel de date, OpenStdin/StdinOnce/EOF prin daemonul real, cgroup/drain, grant DB real și tranzacție reconcile: NOT_RUN aici.** Toate gates `make check`, installed-start/pair-open/stop sunt în sarcina părintelui.
4. ACK-ul pierdut intenționat rămâne recovery; această felie nu introduce comandă de recovery/replay automat. Nicio resursă istorică nu a fost adoptată/operată și nu se pretinde ALL_CLEAN global. Procesele/UDS testelor finale aparțin numai fixture-urilor noi.

Lecții pentru integrare: verifică **consumatorul**, nu doar helperul; copie binară + fsync director înainte de înlocuirea singurului jurnal; EOF Docker cere attach stdin la create, nu numai `-i` la start; persistența ACK și exit/drain sunt probe diferite; reținerea DB nu permite abandonarea copilului host încă deținut. Lecțiile sunt păstrate în această notă de proiect; scope-ul nu permite schimbarea skill-urilor/profilurilor personale.

Rollback: `git revert` în ordinea inversă a dependențelor, rebuild și regresii. Revertul Git **nu** șterge intenturi, nu dezarmează fence DB și nu autorizează retryul efectelor incerte.

## Status global — delta propusă, nu acceptare

| Zonă | Implementare | Probe | Review / pas |
|---|---|---|---|
| P0.1–P0.3 / SL01–SL03 | Stare anterioară păstrată | Nu recertificate fizic aici | Registrul principal rămâne al părintelui |
| **AICI SL04 wiring CLI** | IMPLEMENTED scoped | Source235/235 + wheel235/235, lint/types PASS | NOT_REVIEWED; integrare/review exact |
| Owner R1–R4 + DB reconcile compus | Prerechizite externe acestei ramuri | NOT_RUN pe snapshotul compus | Părintele adjudecă și integrează |
| SL04 fizic / crash cuts | Acceptare încă PARTIAL | OCI/PG NOT_RUN | Gates seriale pe release reconstruit |
| M03 / M22 | Nu promovate prin această felie | Probe proprii la părinte | Păstrează lucrul separat |
| G00 / CI remote | Deschis | NOT_RUN aici | Fără transfer de verde |
| P1–P8 / MVP rămas / extensii E | Nelivrate de această felie | NOT_RUN | Ordinea planului, fără provideri/ținte |

Reticle: NOT_APPLICABLE proprietăților CLI/proces; Chisel: NO-GO/BLOCKED, nefolosit. Harta globală/README nu sunt modificate de copil; părintele aplică numai delta acceptată.
