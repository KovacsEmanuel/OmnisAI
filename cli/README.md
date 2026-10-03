# CLI P0.4 — SL02/SL03 locale + SL04 stop/recovery parțial

`omnis-cli==0.1.0` este un wheel separat, fără dependențe API/Hermes. **`omnis start --no-open [--json]` pornește și verifică P0-control din afara checkoutului.** `omnis status [--json]` verifică read-only aceeași instanță și ruta HTTP/assets. `omnis pair` emite codul numai în TTY, `omnis open` deschide numai originul verificat, iar `omnis` implicit pornește/reutilizează și încearcă deschiderea; la prima pornire în TTY emite și codul inițial, fără a-l reemite la reuse. `omnis stop [--json]` există pe wheel: persistă bariera înainte de quiescență/finalizare și oprește numai resursele P0 atestate; la indisponibilitate păstrează un marker nereconciliat și exit 4. [SL04](../documents/verification/p04-stop-recovery.md) este încă PARTIAL/BLOCKED, nu certificat pentru toate crash-cut-urile. [SL02](../documents/verification/p04-installed-start.md) și [SL03](../documents/verification/p04-pair-open.md) au verdicte istorice separate. G00 și CI remote nu sunt închise.

## Pregătire explicită, separată de startup

**SL02:** REMEDIATION_PASS în scope pe `c914fda`, nu transferat automat noilor bytes; [registrul remedierii](../documents/verification/p04-deep-remediation.md) și [matricea](../documents/verification/p04-deep-remediation-matrix.json) păstrează M03/config, M21/SL04 și M22/parser PARTIAL înainte G00. **SL03:** comenzile pair/open/implicit și L05-control pe artefact instalat au probe locale în [registrul SL03](../documents/verification/p04-pair-open.md). **SL04 WIP:** Stop normal/repetat, restart explicit și urgență exit 4 probate punctual pe fixture-uri proprii; faulturile neacoperite și reviewul final blochează PASS integral. G00 deschis, CI remote NOT_RUN, assessment_ready=false. Cele două recuperări istorice rămân RECOVERY_PENDING separat, fără ALL_CLEAN sau autorizație de recovery/push.

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
<venv-cli>/bin/omnis stop --json
# Numai după STOPPED verificat, pornire nouă explicită (nu autoresume):
<venv-cli>/bin/omnis start --no-open --json
# Dintr-un TTY interactiv, cu instanța verificată și READY:
<venv-cli>/bin/omnis pair
# Deschidere fără pornire, respectiv pornire/reutilizare + deschidere:
<venv-cli>/bin/omnis open
<venv-cli>/bin/omnis
```

`install` copiază idempotent releaseul; `install-image` construiește explicit imaginea și păstrează receiptul. Numai buildul explicit poate descărca dependențele cu hashes. **Start/status nu fac pull, build, instalare sau upgrade.** Releaseul este input local trusted al operatorului: checksumurile verifică consistența, nu o semnătură independentă. [Istoric bundle](../documents/verification/p04-bundle-install.md), [artefact imagine](../documents/verification/p04-image-artifact.md), [receipt imagine](../documents/verification/p04-image-install.md).

## Contractul startului

### Configurație non-secretă M22

CLI citește numai `$XDG_CONFIG_HOME/omnis/config.toml`, implicit
`~/.config/omnis/config.toml`, niciodată un fișier din cwd. Lipsa fișierului
folosește defaults fără să creeze config/directoare. Fișierul trebuie să fie
regular, owner curent, mod exact **0600**, fără hardlink; directorul `omnis`
privat **0700**. Calea absolută/canonică și ancestorii nereplaceable se verifică
și când fișierul lipsește; symlinkurile și căile relative se refuză.

```toml
port = 8765
startup_timeout_seconds = 180
shutdown_timeout_seconds = 180
cleanup_timeout_seconds = 100
```

| Cheie root | Interval inclusiv | Default | Override CLI |
|---|---|---|---|
| `port` | 1024–65535 | 8765 | `start --port` |
| `startup_timeout_seconds` | 30–300 | 180 | `start --startup-timeout` |
| `shutdown_timeout_seconds` | 15–180 | 180 | `stop --shutdown-timeout` |
| `cleanup_timeout_seconds` | 30–180 | 100 | `start --cleanup-timeout` |

Numai integer exact: bool/float/string, interval invalid, table/cheie necunoscută,
cheie secretă, TOML malformat ori fișier prea mare sunt refuzate sanitizat cu
`CONFIG_INVALID`/exit 2 înainte de lock, Docker, UDS ori browser, inclusiv în
`status`, `pair`, `open` și comanda implicită. Nu puneți credentiale în acest fișier.
Un override valid nu ascunde un config invalid.

Pentru instanță **nouă**, CLI explicit > config > defaults. Pe instanța deja
înregistrată, inclusiv STOPPED/restart, receiptul și originul verificat rămân
autoritate: omiterea portului reutilizează portul existent, nu defaultul 8765.
Config/CLI cu port divergent refuză `CONFIG_PORT_CONFLICT`, inclusiv la `stop`;
nici măcar un override CLI nu adoptă un config divergent față de receipt. Pentru
a opera instanța existentă, eliminați cheia `port` din config (și flagul divergent)
sau readuceți selecția la portul originului înregistrat, apoi rulați Status/Stop.
Un Stop complet **nu** autorizează singur schimbarea portului la următorul Start.
Nu editați journalul sau `instance.json` pentru rebind; acesta cere o procedură
explicită de recovery/reconciliere.

Startup și shutdown propagă un singur deadline monotonic; cleanup începe un
allowance separat numai după eșecul încercării noi și nu prelungește startupul.
Limitele locale mai mici rămân, iar așteptările forwarder/reap nu adaugă timp peste
bugetul rămas. Un buget scurt poate produce refuz/UNCERTAIN, nu garantează Stop
complet. Deadline-ul clientului nu anulează un request Docker admis; incertitudinea
daemonului/familiei și datele păstrate nu sunt șterse. Status/pair/open păstrează
bugetele lor de diagnostic existente, validând tot configul și originul.

[Registrul M22](../documents/verification/p00-m22-config.md) separă probele
source/wheel și copii locali de gate-urile fizice/reviewul de integrare NOT_RUN.
Pentru testele CLI folosiți și un `XDG_CONFIG_HOME` privat nou; nu relaxați parserul
pentru o configurație ambientală nesigură și nu modificați configul operatorului.

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

`STARTING`/`MIGRATING` nu înseamnă READY. Un jurnal neREADY, un PID stale, alt release/daemon/instance sau admiterea închisă cer reconciliere explicită, nu retry care lansează duplicate. SL02 istoric **nu implementa** Stop/restart; traseul SL04 nou permite Start explicit numai după `STOPPED` local + readbackul exact și o generație/epoch nou, păstrând PGDATA fără migrare. Un marker `unreconciled.json` refuză Start și statusul este `RECOVERY_REQUIRED`, niciodată `STOPPED` dedus din absența serviciului.

CLI-ul curent armează fence-ul durabil numai după FINALIZE verificat, apoi transferă lockurile originale unui owner **Stop-only**. Grantul leagă instanța/comanda/generația/ownerul/epoch-ul de daemon și inventarul exact; `STOP_PENDING` și `STOP_UNCERTAIN` refuză acquire/OPEN independent de expirarea lease-ului ori `release`, fără TTL de deblocare. Ownerul persistă intenția înaintea fiecărui efect și completion numai după ACK/readback verificat. `PREPARED`, ACK pierdut sau owner mort nu autorizează retry orb ori STOPPED dedus din CID absent.

După un STOPPED complet, **Start nou explicit** păstrează receiptul și intenția de restart, pornește numai DB proprie și execută jobul fix `python -I -m omnis.stop_reconcile` din schema `0006_stop_reconciliation`. ACK-ul corelat trebuie persistat înaintea noului supervisor/acquire/OPEN. Un fence incert sau un ACK de reconciliere lipsă rămâne `RECOVERY_REQUIRED`, nu autoresume. Compoziția `e336b7b`, integrată local în `bd5ee23`, are probă fizică nominală Stop→Start/sentinel→Stop; crash-cut-urile și G00 rămân distincte în [registrul SL04](../documents/verification/p04-stop-recovery.md).

Buget startup implicit 180 s, configurabil conform M22, cu limite individuale mai mici; cleanup are buget separat finit (implicit 100 s). La eșec se încearcă numai cleanupul resurselor proprii, fără a opri o instanță sănătoasă preexistentă. Procesele/writerii proprii preced DB; o operație daemon/familie incertă păstrează DB pentru recuperare. Eroarea unei operații sau a jurnalului nu produce succes fals. Datele și diagnosticul privat rămân; niciodată `down -v`/prune/reset DB.

Exit startup: **0** READY verificat, **2** precondiție/config/port refuzat, **3** startup/readiness eșuat, **4** recovery/cleanup incert. JSON nu conține DSN, parole, capabilities sau pairing. Un locator vechi, fără jurnal SL02, păstrează statusul conservator `HTTP_UNVERIFIED`; acel ACK nu certifică dashboardul. După simpla instalare, fără instanță creată, `status` poate da `NOT_INSTALLED`/exit 3.

`SO_REUSEADDR=False` rămâne strict. TIME_WAIT nu este listener și nici promisiune de rebind imediat; proba de teardown citește absența resurselor/listenerului propriu, nu adoptă orice răspunde pe port.

**SL03:** `pair` refuză non-TTY/JSON înainte de emitere (exit 2), inclusiv sondă TTY indisponibilă; codul se consumă o dată și expiră după 5 minute în PostgreSQL. La `omnis` nou în TTY se emite codul inițial prin același issuer; la reuse sau non-TTY nu se invalidează codul și pairingul ulterior se cere explicit. Un write TTY parțial raportează disclosure incertă/exit 4, nu pretinde că nu s-a afișat codul. `open`/`omnis` fac readback complet identitate/receipt/HTTP/asset înainte de originul local; opener absent exit 2, cod nenul/eșec exit 3, timeout neconfirmat exit 3, acceptat exit 0. Acceptarea `xdg-open` nu dovedește o fereastră ori sesiunea web: browserul de laborator și sesiunea au probă separată. Serviciile READY rămân pornite când openerul eșuează sau expiră timeoutul. **Rămân de certificat:** crash-cut-urile și recovery/persistența SL04 dincolo de traseul nominal instalat. L01–L05/L08 complete, peer LAN/IPv6 și G00 rămân distincte. Nu există runtime Hermes, provideri/Jev, proxy/executori, conturi sau trafic de assessment în această felie.

## Verificare

- `make check UV=/cale/uv-0.12.19` (alias `make test`): gate canonic cu runnerul DB UDS/no-network integrat; nu este implicit testul OCI. [Baseline DB închis](../documents/verification/p04-test-db-integration.md); verdictul lui nu se transferă codului nou.
- **`make check-installed-start UV=/cale/uv-0.12.19`**: opt-in Docker/OCI, construiește/instalează explicit artefactele curente, apoi execută comanda de produs din alt cwd, concurență/reuse/status/negative/SIGTERM și cleanup/readback cu date păstrate. Fără `run_probe` în locul comenzii.
- **`make check-installed-pair-open UV=/cale/uv-0.12.19`**: gate distinct L05-control, build din wheelul curent, TTY/PTY real, one-use/expiry, Host/Origin, sesiune/logout în browser propriu, refuzuri stale/foreign/closed, `omnis` nou/reuse și open headless; nu certifică fereastra OS `xdg-open` ori G00.
- **`make check-installed-stop UV=/cale/uv-0.12.19`**: gate SL04 opt-in, wheel/bundle din cwd extern și XDG noi; Stop normal/idempotent → Start nou cu sentinel PG păstrat, Start concurent Stop-first refuzat, status STOPPING/STOPPED și urgență API indisponibilă cu marker durabil/exit4. Nu acoperă încă toate crash-cut-urile, topologia/UID/LAN/IPv6 sau G00.
- `check-control-image`, `check-installed-image`, `check-installed-control` rămân probe opt-in separate. Ultimul este [harnessul istoric de topologie](../documents/verification/p04-host-uds.md), nu dovada SL02 sau `omnis stop`.

Rollback cod: inspectați commitul și dependențele, `git revert <sha>`, reconstruiți artefactele și rerulați probele. Git nu inversează DB/imaginile/procesele externe. Recuperarea lor cere readback exact al ownershipului; nu se deduce din port, prefix sau un PID dintr-un fișier. Probe numai în XDG scratch noi; nu se reutilizează automat clusterele disposable păstrate.
