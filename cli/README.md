# CLI P0.4 — SL02: start headless instalat

`omnis-cli==0.1.0` este un wheel separat, fără dependențe API/Hermes. **`omnis start --no-open [--json]` pornește și verifică P0-control din afara checkoutului.** `omnis status [--json]` verifică read-only aceeași instanță și ruta HTTP/assets. Rezultatele, reviziile, eșecurile și limitele sunt în [registrul SL02](../documents/verification/p04-installed-start.md). G00 și CI remote nu sunt închise.

## Pregătire explicită, separată de startup

Linux/amd64, operator nonroot, Docker Unix local și Compose v2. Toolchain de build: uv **0.12.19**, Python **3.13.15**, Node **24.21.0**/npm **11.19.0**. Nu instalați în mediul Hermes și nu înlocuiți toolchain-ul global.

1. Pregătiți mediile din lockuri: `uv sync --locked --no-config --no-python-downloads --python 3.13.15 --directory cli`; API/web conform README-urilor lor.
2. Construiți ambele wheeluri: `uv build --no-config --wheel api --out-dir <scratch>/api-wheel` și echivalentul pentru `cli`. Instalați CLI-ul în venv separat: `uv pip install --no-config --python <venv-cli>/bin/python --no-deps <scratch>/cli-wheel/omnis_cli-0.1.0-py3-none-any.whl`.
3. `make build-web`; exportați requirements API cu `uv export --locked --no-config --directory api --no-dev --no-emit-project --no-header --no-annotate --format requirements-txt --output-file <scratch>/requirements.txt --quiet`.
4. Construiți bundleul: `OMNIS_UV=/cale/uv-0.12.19 cli/.venv/bin/python -I ops/build_control_bundle.py --api-wheel <abs-wheel-api> --cli-wheel <abs-wheel-cli> --requirements <abs-requirements> --web-root <abs-web/dist> --output <abs-bundle-nou>`.
5. Pregătiți explicit imaginile fixate, dacă lipsesc:

```sh
docker pull --platform linux/amd64 python:3.13.15-slim-bookworm@sha256:3e2de9c40ca4e3d73240059f9d48baff27908f10293e985a2f382a0378e6df4a
docker pull --platform linux/amd64 postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650
```

Din orice director, cu roots XDG explicite dacă nu doriți defaults:

```sh
<venv-cli>/bin/omnis install --bundle <abs-bundle>
<venv-cli>/bin/omnis install-image
<venv-cli>/bin/omnis start --no-open --json
<venv-cli>/bin/omnis status --json
```

`install` copiază idempotent releaseul; `install-image` construiește explicit imaginea și păstrează receiptul. Numai buildul explicit poate descărca dependențele cu hashes. **Start/status nu fac pull, build, instalare sau upgrade.** Releaseul este input local trusted al operatorului: checksumurile verifică consistența, nu o semnătură independentă. [Istoric bundle](../documents/verification/p04-bundle-install.md), [artefact imagine](../documents/verification/p04-image-artifact.md), [receipt imagine](../documents/verification/p04-image-install.md).

## Contractul startului

- Release instalat sub `$XDG_DATA_HOME/omnis/releases/0.1.0`, receipturi private `installed.json`/`image.json`. Configurația trusted este **`ops/compose.yaml` în bundle**, din sursa `ops/compose.control.yaml`; nu se caută Compose, `.env`, configurări sau executabile Docker în cwd.
- Origin implicit `http://127.0.0.1:8765/`. `--port <1024..65535>` este o selecție explicită numai pentru o instanță nouă. Repetarea fără flag folosește originul înregistrat. Un port străin, inclusiv doar `bind()` fără `listen()`, este refuzat; fără kill sau auto-port. Bindul efectiv al forwarderului este verificat separat de preflight.
- Lock comun al proiectului instalat și lock per state root; nonce unic de încercare, daemon/image/container IDs, configurații/binduri/UID/rețea și IPC verificate. PID-ul, labelul Compose și un HTTP 200 nu sunt autoritate suficiente.
- DB proprie → health bounded → job instalat `python -I -m omnis.migrate --initialize` → API **`python -I -m omnis.serve`** + un supervisor inert → forwarder host detached. Migrarea verifică clusterul și baza pe conexiunea DDL și ia un advisory lock tranzacțional. Schema/datele existente nu sunt upgradate de acest mod.
- PostgreSQL 18 folosește bindul `postgres/` traversabil `0711` sub state root `0700`; PGDATA rămâne al imaginii. DB/API/supervisor folosesc numai bridge-ul intern `control`, fără porturi Docker publicate. API și control au UDS separate; API/supervisor nu primesc Docker socket.
- Readiness corelează DB/schema/control, namespace-ul/cgroup-ul peer-ului API, listenerul forwarderului și bytes-urile fiecărui asset trusted. Probe HTTP cu deadline total și limită de bytes, fără redirects/proxy ambiental/DNS arbitrar. `instance.json` este locator, nu autoritate DB.
- La succes: `dashboard_ready=true`, `assessment_ready=false`, `browser_opened=false`. Se deschide admiterea numai pentru această instanță nouă verificată, în generația permisă; niciun assessment nu pornește. Nu se emit coduri de pairing headless.
- Al doilea start sănătos reutilizează aceleași procese, fără remigrare/restart sau writer nou. Închiderea terminalului nu oprește serviciile. Nu se instalează autostart OS.

## Stare, erori și limite operaționale

State root: `$XDG_STATE_HOME/omnis` (implicit `~/.local/state/omnis`). `instance.json` păstrează formatul strict existent; `startup.json` este jurnalul privat al încercării/resurselor. IPC: `$XDG_RUNTIME_DIR/omnis`, sau `runtime-ipc/` sub state. Directoare private/canonice, fișiere 0600, fără symlinkuri sau adopție a resurselor vechi.

`STARTING`/`MIGRATING` nu înseamnă READY. Un jurnal neREADY, un PID stale, alt release/daemon/instance sau admiterea închisă cer reconciliere explicită, nu retry care lansează duplicate. SL02 **nu implementează** restartul unei instanțe oprite, recuperarea operațională sau comanda `omnis stop`.

Buget startup 180 s, cu limite individuale mai mici; cleanup are buget separat finit. La eșec se încearcă numai cleanupul resurselor proprii, fără a opri o instanță sănătoasă preexistentă. Procesele/writerii proprii preced DB; o operație daemon/familie incertă păstrează DB pentru recuperare. Eroarea unei operații sau a jurnalului nu produce succes fals. Datele și diagnosticul privat rămân; niciodată `down -v`/prune/reset DB.

Exit startup: **0** READY verificat, **2** precondiție/config/port refuzat, **3** startup/readiness eșuat, **4** recovery/cleanup incert. JSON nu conține DSN, parole, capabilities sau pairing. Un locator vechi, fără jurnal SL02, păstrează statusul conservator `HTTP_UNVERIFIED`; acel ACK nu certifică dashboardul. După simpla instalare, fără instanță creată, `status` poate da `NOT_INSTALLED`/exit 3.

`SO_REUSEADDR=False` rămâne strict. TIME_WAIT nu este listener și nici promisiune de rebind imediat; proba de teardown citește absența resurselor/listenerului propriu, nu adoptă orice răspunde pe port.

**Ulterior:** SL03 pairing TTY/open/browser verificat; SL04 stop durabil/crash/recovery/persistență. Comenzile respective nu sunt expuse ca stuburi. L01–L05/L08 complete, peer LAN/IPv6 și G00 rămân distincte. Nu există runtime Hermes, provideri/Jev, proxy/executori, conturi sau trafic de assessment în această felie.

## Verificare

- `make check UV=/cale/uv-0.12.19` (alias `make test`): gate canonic cu runnerul DB UDS/no-network integrat; nu este implicit testul OCI. [Baseline DB închis](../documents/verification/p04-test-db-integration.md); verdictul lui nu se transferă codului nou.
- **`make check-installed-start UV=/cale/uv-0.12.19`**: opt-in Docker/OCI, construiește/instalează explicit artefactele curente, apoi execută comanda de produs din alt cwd, concurență/reuse/status/negative/SIGTERM și cleanup/readback cu date păstrate. Fără `run_probe` în locul comenzii.
- `check-control-image`, `check-installed-image`, `check-installed-control` rămân probe opt-in separate. Ultimul este [harnessul istoric de topologie](../documents/verification/p04-host-uds.md), nu dovada SL02 sau `omnis stop`.

Rollback cod: inspectați commitul și dependențele, `git revert <sha>`, reconstruiți artefactele și rerulați probele. Git nu inversează DB/imaginile/procesele externe. Recuperarea lor cere readback exact al ownershipului; nu se deduce din port, prefix sau un PID dintr-un fișier. Probe numai în XDG scratch noi; nu se reutilizează automat clusterele disposable păstrate.
