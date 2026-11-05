# CLI Omnis — operare locală și lucru din surse

`omnis-cli==0.1.0` este un wheel separat, fără dependențe API/Hermes. **`omnis` și `omnis start` pornesc/reutilizează instanța și încearcă deschiderea originului verificat. `omnis start --no-open [--json]` rămâne varianta explicită fără browser.** `omnis status [--json]` verifică read-only aceeași instanță și ruta HTTP/assets. `omnis pair` emite codul numai în TTY, `omnis open` deschide numai originul verificat, iar `omnis` implicit pornește/reutilizează și încearcă deschiderea; la prima pornire în TTY emite și codul inițial, fără a-l reemite la reuse. `omnis stop [--json]` există pe wheel: persistă bariera înainte de quiescență/finalizare și oprește numai resursele P0 atestate; la indisponibilitate păstrează un marker nereconciliat și exit 4. [SL04](../documents/verification/p04-stop-recovery.md) are adjudecarea `P0_LOCAL_USABLE=PASS_LOCAL_RECORDED` pentru un singur operator pe această VM, nu certificarea universală a crashurilor. [SL02](../documents/verification/p04-installed-start.md) și [SL03](../documents/verification/p04-pair-open.md) păstrează probele la reviziile lor. CI remote și peerul extern rămân pentru distribuire/portare, nu condiții ale utilizării locale.

## DEVELOPMENT opt-in în aceeași instalație — verificat local scoped

Pentru profilul `t1-provider-settings`, după backup/restaurare probate și **Stop
verificat**, configurația existentă poate selecta explicit checkoutul trusted:

```toml
development_workspace = "/cale/absoluta/canonica/OmnisAI"
```

Cheia este opțională: absentă = `RELEASE`; prezentă = `DEVELOPMENT`, nu certificare
imuabilă. Maximum **512 bytes ASCII imprimabili**, fără `..`, aliasuri, trailing
slash ori symlinkuri. Configul rămâne maximum4096 bytes/0600. La Start se verifică
ownerul/căile, pachetul bounded4096 intrări și manifestul web (32KiB,128 fișiere,
2MiB/fișier,8MiB cumulat). Nu puneți fișiere private în cele două directoare montate.

- UI: din checkout, `npm --prefix web run build`, apoi refresh la **același origin**.
  Numai `web/dist` este montat read-only la `/opt/omnis/web`, numai în API. Un build
  incomplet/corupt dă indisponibilitate temporară, nu fallback sau READY fals.
- Python: **`omnis stop --json` → editare → `omnis start --no-open --json`**.
  Numai `api/src/omnis` se montează read-only peste
  `/usr/local/lib/python3.13/site-packages/omnis` în API și supervisor; `python -I`
  rămâne. Fără autoreload; editarea sursei backend cât rulează este nesuportată.
- Nu se montează home/checkoutul complet, `.hermes`, dependențe sau chei în API.
  DB, vault/master, control, UID/GID, caps, rețea, Host/Origin/sesiune/CSRF și Stop
  rămân neschimbate. Joburile de reconciliere/migrare folosesc codul instalat.
- Selectorul este legat de noul receipt format5, **numai după STOPPED**. Reuse cu
  selector diferit refuză `CONFIG_MODE_CONFLICT`, fără al doilea proces. Status,
  Pair/Open, Stop și recover folosesc modul încercării, nu configul schimbat ulterior.
  Schimbarea sintactic validă a selectorului, sursa lipsă ori buildul invalid nu
  blochează retragerea resurselor atestate. Configul malformat rămâne refuzat.
- Rollback: Stop autentic, eliminați cheia din config, Start explicit. Același
  UUID/origin/PGDATA/date/chei și digest/imagine păstrate; fără restore DB sau
  rescriere de granturi. Dependențele/schema/baza cer release separat, nu acest mount.

CLI-ul extins se livrează explicit în launcherul/venv-ul existent după review și
QA; nu modifică releaseul păstrat. Produsul `6aa4d5e` are reviewuri complementare,
wheel400PASS și QA OCI/PG/browser cu restart Python, două builduri UI și rollback.
Prima QA a eșuat în callerul browser; corecția `10d2de6` și PASS-ul ulterior sunt
distincte în [registru](../documents/verification/settings-c-evidence/ui-result.json).
Nu rulați proba izolată următoare pe datele/configul operatorului.

### Instalația operatorului pe această VM

Un singur root activ: `/home/kali/.local/share/omnis-settings-c-9e51d10`, origin
`http://127.0.0.1:8780`, UUID `d694129b-a3e5-446d-9e5b-fe9bc19abed8`.
`omnis` global și `<root>/omnis` operează aceeași instalație. Starea operatorului
este consemnată în [registru](../documents/verification/settings-c-evidence/ui-result.json);
verificați starea curentă, nu deduceți autostart:

Tranziția explicită revizuită pe aceleași date a avut istoric
**READY27/epoch16, CLI/release0.1.1 și schema0017_model_removal**, DEVELOPMENT,
cu următorul Start normal `reused=true`. **După reboot, recuperarea autorizată
a ajuns exit0/STOPPED29 și Start explicit exit0/READY30/epoch18**, aceeași
identitate/release/schemă. CLI-ul reparat post-reboot este instalat după reviewuri,
QA și backup actual0017 restaurat în copie izolată; datele/istoricul/ciphertextul
sunt verificate, fără apel provider inițiat de agent. Models `ae92a65` rămâne
integrat; operatorul a confirmat manual modelele vizibile/Connected și Test,
Refresh, Remove și conectări noi funcționale. Tabul automat separat a rămas
neasociat; nu s-au exportat cookie-uri ori automatizat pairingul.
[Rezultate actuale și limite](../documents/verification/settings-c-evidence/models-polish-20261029/blocked-resume.md).
Datele adăugate ulterior de operator nu sunt în backupul anterior recuperării.
Gate-ul de audit încă blochează T1. READY nu este remediu al cauzei istorice
necunoscute sau promisiune de disponibilitate.

```sh
omnis status --json
omnis start                  # explicit, start/reuse și browser verificat
omnis start --no-open --json   # explicit, sau reuse dacă este deja READY
omnis stop --json
# UI, din /home/kali/OmnisAI; nu install și nu build de imagine:
PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH npm --prefix web run build
# Apoi refresh în browser. Python: Stop -> editare -> Start.
```

Configul privat este `<root>/c/omnis/config.toml`, cu
`development_workspace = "/home/kali/OmnisAI"`. Pentru rollback: Stop verificat,
eliminați **numai această cheie**, apoi Start; CLI-ul capabil rămâne instalat.
Slotul/imaginea curentă0.1.1 sunt coerente; releaseul/imaginea veche7673066,
datele și cheile sunt păstrate. Eliminarea cheii development selectează bundleul
curent0017, **nu downgrade0016**. Backupurile actuale sunt
`/home/kali/.local/share/omnis-backups/t1-finalization-20261029T194541Z`
și `/home/kali/.local/share/omnis-backups/t1-upgrade-bb760e5-stopped26`;
masterul rămâne separat. Restaurarea nativă și rollbackul cunoscut **preOPEN**
au probe scoped; după OPEN nu există downgrade automat/fără pierderi sau
restore cross-digest admis. Nu repetați `upgrade`, recovery ori restore pentru
inventar. Git revert nu restaurează DB/chei/servicii. Nu restaurați backupul
launcherului P1/r1. Nu modificați Python în timp ce rulează; schimbările de
dependențe/schemă/protocol cer o tranziție explicită, nu un nou profil gol.
Start/Open cer deschiderea în profilul desktop curent. Cu sesiune validă, browserul
ajunge în Dashboard; prima asociere sau sesiunea expirată cer pairing manual ales
explicit. `omnis pair` se execută în terminal local; codul se introduce direct în
UI, niciodată în URL/chat. Nu se automatizează autentificarea.
Modul development nu este un release imuabil certificat. Corecțiile quality și
fixture sunt verificate; probele funcționale curente au trecut în scope-urile lor.
Canonicalul rămâne FAIL la auditul dependenței OpenAPI/minimatch, fără fix
compatibil publicat. Întrebarea pentru backport a expirat fără răspuns; nu este
autorizație și nu se maschează auditul. Nu este lipsă de pairing sau PASS global
din recovery; FAIL/TIMEOUT-urile vechi rămân istorice. T2 nu este autorizat.

[`operator-launcher.sh`](operator-launcher.sh) este artefactul sursă pentru aceleași
două fișiere `<root>/omnis` și `/home/kali/.local/bin/omnis`, numai pe această VM;
nu este installer, generator sau al treilea launcher activ. Se aplică explicit
după review și QA. Păstrează `env -i`, HOME/XDG private și PATH fix pentru aplicație.
Capturează `HOME` și cele patru valori XDG din mediul invocării sub numele
`OMNIS_DESKTOP_HOME` și `OMNIS_DESKTOP_XDG_{CONFIG_HOME,DATA_HOME,STATE_HOME,RUNTIME_DIR}`;
păstrează numai allowlistul grafic
`DISPLAY`, `WAYLAND_DISPLAY`, `XDG_CURRENT_DESKTOP`, `DBUS_SESSION_BUS_ADDRESS`,
`XAUTHORITY`, `LANG`. Numai `browser.launch` restaurează HOME/XDG desktop pentru
openerul fix `xdg-open`; XDG absent/gol înseamnă default desktop, nu root privat.
CLI fără wrapper folosește contextul desktop obișnuit. Nu se propagă `BROWSER`,
credentiale, SSH, `PYTHONPATH` sau variabile arbitrare; nu se montează home-ul.

### QA installed finită, numai după reviewurile complementare

Consumerul existent `test_release` are opt-in `OMNIS_INSTALLED_DEVELOPMENT_PROBE=1`.
Necesită CLI candidat deja instalat într-un venv QA izolat, toolchainurile fixate,
`web/dist` construit, cache Chromium/Playwright fixat și imaginile de bază deja
pregătite. Folosește release/proiect/state fresh proprii, nu adoptă instalări.

```sh
# Preflight SOURCE fără Docker/build/instalare:
cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_development.py -v
cli/.venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py -k development_probe -v
# Numai QA autorizată: <cli-QA> și <cache-Chromium> sunt căi absolute pregătite.
PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin \
OMNIS_UV=/home/kali/.local/share/omnis-toolchains/uv-0.12.19 \
OMNIS_CLI_BIN=<cli-QA>/bin/omnis \
OMNIS_DEVELOPMENT_NODE=/home/kali/.local/share/omnis-toolchains/bin/node \
PLAYWRIGHT_BROWSERS_PATH=<cache-Chromium> \
OMNIS_INSTALL_IMAGE_PROBE=1 OMNIS_INSTALLED_DEVELOPMENT_PROBE=1 \
cli/.venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py \
  -k test_real_api_web_and_cli_bundle_is_checkout_independent -v
```

Celelalte opt-in-uri `OMNIS_*PROBE` trebuie absente. Părintele fixează deadline-ul
exterior și ownerul QA înaintea efectelor. Scenariul verifică RELEASE→DEVELOPMENT,
două builduri Vite succesive în copie sintetică, bytes/health, importurile și
restartul Python, sentinel DB/identități, denials Host/Origin/session/CSRF/assets,
browserul session existent și rollback DEVELOPMENT→RELEASE→Stop/readback.
Copiile de source/build se șterg numai după cleanup verificat; PGDATA/receipturile
se păstrează. La incertitudine nu se pretinde cleanup. Desktop/mobile/focus și
acceptarea vizuală Settings se verifică separat/reutilizează scoped, nu sunt
certificate de scenariul browser session. Fără provider/target traffic sau T2.

## Upgrade finit T1/S1 — fără upgrade implicit la Start

`omnis upgrade` admite exclusiv profilul `t1-provider-settings` și perechile
**0.1.0/0016→0.1.1/0017** sau **0.1.1/0017→0.1.2/0019**. Sursa trebuie să fie
STOPPED verificat, cu receipt/grant original complet și masterul seifului prezent.
Nu se admite replay, salt de versiuni, schema arbitrară sau adoptarea unui catalog
preexistent. Aceasta este calea de produs; SOURCE nu certifică rolloutul S1.

```sh
# CLI candidat instalat separat; bundle și destinație absolută, în afara state/data.
<cli-candidat>/bin/omnis upgrade --bundle <bundle-0.1.2> --backup <snapshot-nou> --json
```

Comanda păstrează configurația și UUID-ul, verifică backupul T1 prin restore izolat,
apoi construiește imaginea țintă, creează catalogul privat S1 și migrează sub fence-ul
Stop. Publică metadata numai după readback fizic al schemei și folosește Start-ul
normal, inclusiv modul DEVELOPMENT selectat explicit. Checkoutul DEVELOPMENT
ales trebuie pregătit separat pentru versiunea țintă; upgrade nu îl modifică.
Receiptul rămâne format5; payloadul Stop și plafonul16KiB nu se schimbă.

Un `upgrade.json` T1 **COMPLETE validat și legat de sursa curentă** este păstrat
byte-exact în noul `upgrade-source-<uuid>/upgrade.json`, împreună cu metadata sursei;
vechiul director rămâne intact. Orice intent activ, necunoscut sau UNCERTAIN refuză
continuarea. Rollbackul automat există numai pentru eșecul cert, drenat, pre-OPEN:
restaurează versiunea sursă din metadata salvată și păstrează copia eșuată în
carantină. După OPEN ori rezultat necunoscut, nu se face downgrade/retry automat.

**Backupul unei instanțe S1 cu catalog rămâne `COLD_CATALOG_UNSUPPORTED`.** Acest
upgrade verifică snapshotul T1 de dinaintea migrării; nu implementează backup S1 și
nu include masterul separat în arhiva backupului.

Consumerul instalat existent se selectează din cele două perechi de bundle-uri;
numele opt-in/testului T1 este păstrat. Numai după review și cu owner/deadline QA:

```sh
OMNIS_T1_UPGRADE_PROBE=1 \
OMNIS_T1_OLD_BUNDLE=<copie-bundle-0.1.1> \
OMNIS_T1_UPGRADE_BUNDLE=<bundle-0.1.2> \
OMNIS_T1_OLD_CLI=<venv-vechi>/bin/omnis \
OMNIS_CLI_BIN=<venv-candidat>/bin/omnis \
cli/.venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py \
  -k test_t1_populated0016_upgrade_installed -v
```

Aceleași intrări și filtrul
`test_t1_upgrade_known_preopen_failure_restores_installed_snapshot` verifică rollbackul.
Fixture-ul este propriu/sintetic, fără conturi sau modele live; nu folosi wrapperul,
state-ul sau bundle-ul activ al operatorului ca destinație QA. Pentru regresia T1
se păstrează intrările0.1.0→0.1.1. În DEVELOPMENT, consumerul montează pachetul API
al bundle-ului țintă, nu sursele unei versiuni mai noi peste schema veche.

## Recuperare explicită T1 — acceptată local scoped, fără autoresume

`omnis recover [--json]` recuperează **numai** profilul normal `t1-provider-settings`
cu journal READY format 5 și lease originală expirată atestată în PostgreSQL.
Sunt admise două cazuri stricte: supervisorul original oprit cu DB/API/forwarder
încă vii, sau **post-reboot**, cu toate cele trei CID-uri originale `exited`, fără
stări parțiale și cu boot-ul forwarderului diferit de boot-ul OS curent. Releaseul,
daemonul, rețeaua, mounturile, PGDATA, seiful și modul trebuie să rămână identice.
Portul nu poate avea un listener străin; IPC-ul vechi trebuie să fie privat,
stabil și fără peer viu. O instanță sănătoasă, resurse absente/înlocuite, alt profil,
metadata nesigură, Stop în curs/fence ori marker nereconciliat sunt refuzate.

În cazul post-reboot, intentul durabil și copia READY originală preced primul
efect: pornirea **o singură dată a aceluiași CID DB**. Identitatea DB/schema și
lease-ul/OPEN-ul original, fără fence, se verifică înaintea celorlalte servicii.
Logul anterior și IPC-ul stale verificat sunt păstrate prin rename NOREPLACE în
`recovery-<attempt>/`, nu șterse; logul nu ocupă arhiva folosită de Start normal.
Forwarderul existent este relansat înaintea supervisorului reconciler; API-ul
pornește abia după owner/epoch/bariera închisă și quiescența verificate. Identitățile
noi sunt observate, nu copiate din receiptul vechi. Callerul păstrează ownership-ul
forwarderului până la drain/reap, inclusiv când handshake-ul sau ACK-ul eșuează.

Comanda persistă un intent `recovery-<attempt>.json`, verifică din nou identitățile,
apoi pornește **o singură dată același CID supervisor**. Noul owner execută reconcilierea și
quiescența existente cu admission închisă; produce un SHUTDOWN nou autentic,
FINALIZE și grantul către Stop-ownerul existent. Exit 0 înseamnă exclusiv
**STOPPED verificat**, cu resursele proprii retrase și datele păstrate. Nu înseamnă
READY sau reluarea operațiilor; pornirea ulterioară cere separat
`omnis start --no-open --json`. Nu se execută OPEN, Pair, Refresh, Test model,
provider IO, pull, migrare ori upgrade în recuperare.

Bugetul efectelor de recuperare/Stop este `shutdown_timeout_seconds`, fără
modificări ale lease-urilor sau timeouturilor configurate. Numai cleanupul copilului
forwarder nou folosește limita existentă `stop_forwarder` (maximum 27s), inclusiv
după expirarea bugetului operației; nu mai admite efecte DB/controller. Reap-ul se
verifică înainte de publicarea STOPPED. Un ACK/readback/reap incert nu autorizează
retransmiterea efectului.
**Recuperarea întreruptă nu se reia în acest increment:** intentul rămâne, iar
Start/Stop/recover refuză continuarea. Nu ștergeți manual intentul/socketul/capability
pentru a forța retry. Limitele protocolului rămân neschimbate; journalul READY
admis are generation cel mult 9223372036854775804, rezervând takeover, SHUTDOWN
și limita existentă a cererii FINALIZE.

Pentru operator, backupul verificat este prerechizit operațional separat; această
ramură nu face backup/restore automat. SOURCE folosește daemon/SQL/control doubles,
forwarder și Stop-owner reale; Start este probat până la frontieră inertă, nu un
reboot fizic. QA instalată opt-in este `test_t1_post_reboot_installed` din
`cli/integration/test_release.py`, cu `OMNIS_T1_REBOOT_PROBE=1`,
`OMNIS_T1_REBOOT_BUNDLE`, `OMNIS_T1_REBOOT_WORKSPACE` și `OMNIS_CLI_BIN` absolute.
Ea creează numai o instalare fresh proprie, copiază source/buildul DEVELOPMENT,
taie exact procesele fixture-ului și modifică **explicit numai boot-ul din journal**
ca simulare; verifică recover→STOPPED→Start normal→Stop și sentinelul/datele.
Nu repornește hostul, nu adoptă instalarea operatorului și nu este executată implicit.
Cere două reviewuri pe bytes exacți înaintea efectelor; datele/logurile se păstrează
și orice cut/ACK incert oprește proba fără retry. Nu închide T1/T2 sau canonicalul.

CLI-ul nou singur nu actualizează API-ul din imagine. Introducerea inițială a
recuperării necesita ambele wheeluri într-un bundle normal nou, după review și
QA; remediul post-reboot curent schimbă numai CLI-ul, deoarece API-ul0.1.1
instalat are deja suportul necesar. Releaseul 0.1.0 existent
este immutable; nu suprascrieți instalarea curentă și nu folosiți restore între
digesturi diferite drept upgrade. Aceste condiții istorice nu cer reinstalarea
actualei0.1.1: rolloutul CLI este deja verificat. Acceptarea globală T1 rămâne
blocată de audit; datele operatorului și releaseurile existente se păstrează.

## Pregătire explicită, separată de startup

**Status local:** SL02 Start, SL03 Pair/Open și SL04 Stop/restart explicit au acceptare locală scoped; `make check-installed-stop` pe `ccd9a1c` și Pair/Open pe consumatori neschimbați au exit0 cu cleanup exact și date păstrate. `assessment_ready=false`. Stop incert păstrează marker/fence și cere recovery manual; cele două recuperări istorice rămân RECOVERY_PENDING, fără ALL_CLEAN. CI remote și alte hosturi/UID-uri nu sunt autorizate de acest verdict. [Evidență](../documents/verification/p04-stop-recovery.md).

Linux/amd64, operator nonroot, Docker Unix local și Compose v2. Toolchain de build: uv **0.12.19**, Python **3.13.15**, Node **24.21.0**/npm **11.19.0**. Nu instalați în mediul Hermes și nu înlocuiți toolchain-ul global.

1. Pregătiți mediile din lockuri: `uv sync --locked --no-config --no-python-downloads --python 3.13.15 --directory cli`; API/web conform README-urilor lor.
2. Construiți ambele wheeluri: `uv build --no-config --wheel api --out-dir <scratch>/api-wheel` și echivalentul pentru `cli`. Instalați CLI-ul în venv separat: `uv pip install --no-config --python <venv-cli>/bin/python --no-deps <scratch>/cli-wheel/omnis_cli-0.1.1-py3-none-any.whl`.
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

## Profilul de artefacte Settings offline — verificat scoped

`build_control_bundle.py --runtime-metadata <prepared-root>` sigilează cele patru
metadate native standard și `Dockerfile.hermes` într-un release format 2 cu profilul
finit `p4a-settings-offline`. `omnis install-image --runtime-context <prepared-root>`
verifică exact sursele rezultate după cele trei overlays, wheelurile, requirements,
license-ul și metadatele, apoi construiește numai din copia privată proprie.
Symlinkurile/hardlinkurile, fișierele executabile suplimentare și hashurile diferite
sunt refuzate. Mediile/cache-urile/logurile producerului nu sunt copiate în imagine.
Același `image.json` format 2 leagă ambele imagini de release/proiect/daemon;
receipturile control-only format 1 rămân distincte. Limitele releaseului rămân
2 MiB/fișier și 8 MiB cumulat.

**Lifecycle-ul cu patru roluri este verificat offline pe instalare nouă**, selectat exclusiv
prin release/image receipt `p4a-settings-offline`: CLI-ul aplică template-ul JSON
finit din wheel peste Compose-ul sigilat, fără profile/config ambiental. Ordinea
este DB/schemă → RuntimeHost → supervisorul cu un singur RuntimeClient → API → OPEN.
RuntimeHost este PID1 direct, fără rețea/ports, cu rootfs read-only și numai bindurile
private `native-ipc` → `/runtime` și `provider` → `/state/provider`. API nu le montează.
Provider home este păstrat, cu identitatea fizică verificată la reuse/Stop/restart;
nu se copiază profile personale. Managementul pornește numai prin Settings explicit.
Startup format 3 și inventarul/completion Stop v2 sunt distincte de formele control-only;
Stop păstrează DB barrier/drain/FINALIZE/grant și ordinea
forwarder → API → supervisor → runtime → DB → network → IPC. Rezultatele incerte nu
publică STOPPED. [QA instalată și adjudecarea](../documents/verification/p4a-installed-evidence/parent-offline-acceptance.json)
leagă reviewurile de UI/API/config nativ real, reload și Stop→Start→read-only pe aceeași
configurație păstrată, plus cleanup exact. Candidatul testat este integrat în `3926649`;
instanța QA este oprită. Nu este rollout peste r1/P0, upgrade, OAuth, catalog complet,
inferență sau trafic de țintă; canonicalul final și restul P4a/P2-live rămân separate.

## Contractul startului

`--no-open` este opțional. `start --port`, `--startup-timeout` și
`--cleanup-timeout` se aplică și traseului cu browser, cu aceleași limite.
`start --json` produce un singur obiect JSON sanitizat, fără text uman sau cod de
pairing, inclusiv în TTY: `reused=false/true` distinge pornirea nouă de reuse când
startupul reușește, iar `browser_outcome` distinge `BROWSER_NOT_INVOKED`,
`BROWSER_UNAVAILABLE`, `BROWSER_LAUNCH_FAILED`, `BROWSER_LAUNCH_UNCONFIRMED` și
`BROWSER_LAUNCH_ACCEPTED`. `browser_opened=false` nu certifică absența ferestrei:
openerul nu poate confirma fereastra/sesiunea. Deadline-ul openerului rămâne 8s;
timeoutul este incert, nu eșec definitiv. Openerul absent/eșuat/expirat întoarce
exit 2/3/3, fără să oprească serviciile READY. Refuzul verificării instanței
împiedică openerul. `start --no-open --json` păstrează exact formatul/exitul anterior,
fără noul câmp `browser_outcome`, fără browser sau issuer.

`omnis` și `omnis start` fără JSON păstrează emiterea inițială numai la startup nou
în TTY; reuse/non-TTY nu emit cod. Disclosure incertă împiedică openerul.
Acest cod nu autentifică browserul: pairingul se completează manual în UI.

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

Pentru cele patru chei numerice, numai integer exact: bool/float/string, interval invalid, table/cheie necunoscută,
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

După un STOPPED complet, **Start nou explicit** păstrează receiptul și intenția de restart, pornește numai DB proprie și execută jobul fix `python -I -m omnis.stop_reconcile` din schema `0006_stop_reconciliation`. ACK-ul corelat trebuie persistat înaintea noului supervisor/acquire/OPEN. Un fence incert sau un ACK de reconciliere lipsă rămâne `RECOVERY_REQUIRED`, nu autoresume. Compoziția `e336b7b`, integrată local în `bd5ee23`, are probă fizică nominală Stop→Start/sentinel→Stop; G00 local este adjudecat prin probele instalate [din registrul SL04](../documents/verification/p04-stop-recovery.md); experimentele istorice de crash nu sunt poartă numerotată.

Buget startup implicit 180 s, configurabil conform M22, cu limite individuale mai mici; cleanup are buget separat finit (implicit 100 s). La eșec se încearcă numai cleanupul resurselor proprii, fără a opri o instanță sănătoasă preexistentă. Procesele/writerii proprii preced DB; o operație daemon/familie incertă păstrează DB pentru recuperare. Eroarea unei operații sau a jurnalului nu produce succes fals. Datele și diagnosticul privat rămân; niciodată `down -v`/prune/reset DB.

Exit startup: **0** READY verificat, **2** precondiție/config/port refuzat, **3** startup/readiness eșuat, **4** recovery/cleanup incert. JSON nu conține DSN, parole, capabilities sau pairing. Un locator vechi, fără jurnal SL02, păstrează statusul conservator `HTTP_UNVERIFIED`; acel ACK nu certifică dashboardul. După simpla instalare, fără instanță creată, `status` poate da `NOT_INSTALLED`/exit 3.

`SO_REUSEADDR=False` rămâne strict. TIME_WAIT nu este listener și nici promisiune de rebind imediat; proba de teardown citește absența resurselor/listenerului propriu, nu adoptă orice răspunde pe port.

**SL03:** `pair` refuză non-TTY/JSON înainte de emitere (exit 2), inclusiv sondă TTY indisponibilă; codul se consumă o dată și expiră după 5 minute în PostgreSQL. La `omnis` nou în TTY se emite codul inițial prin același issuer; la reuse sau non-TTY nu se invalidează codul și pairingul ulterior se cere explicit. Un write TTY parțial raportează disclosure incertă/exit 4, nu pretinde că nu s-a afișat codul. `open`/`omnis` fac readback complet identitate/receipt/HTTP/asset înainte de originul local; opener absent exit 2, cod nenul/eșec exit 3, timeout neconfirmat exit 3, acceptat exit 0. Acceptarea `xdg-open` nu dovedește o fereastră ori sesiunea web: browserul de laborator și sesiunea au probă separată. Serviciile READY rămân pornite când openerul eșuează sau expiră timeoutul. Traseul SL03 singur nu certifică G00; verdictul local combină Start/Stop și negativele relevante. Pentru alt host/UID rămân izolarea și gate-urile distribuției, iar fiecare adaptor de efect nou își probează Stop/recovery la introducere. Nu există runtime Hermes, provideri/Jev, proxy/executori, conturi sau trafic de assessment în această felie.

## Verificare

- `make check UV=/cale/uv-0.12.19` (alias `make test`): gate canonic cu runnerul DB UDS/no-network integrat; nu este implicit testul OCI. [Baseline DB închis](../documents/verification/p04-test-db-integration.md); verdictul lui nu se transferă codului nou.
- **`make check-installed-start UV=/cale/uv-0.12.19`**: opt-in Docker/OCI, construiește/instalează explicit artefactele curente, apoi execută comanda de produs din alt cwd, concurență/reuse/status/negative/SIGTERM și cleanup/readback cu date păstrate. Fără `run_probe` în locul comenzii.
- **`make check-installed-pair-open UV=/cale/uv-0.12.19`**: gate distinct L05-control, build din wheelul curent, TTY/PTY real, one-use/expiry, Host/Origin, sesiune/logout în browser propriu, refuzuri stale/foreign/closed, `omnis` nou/reuse și open headless; nu certifică fereastra OS `xdg-open` și nu închide singur G00 local.
- **`make check-installed-stop UV=/cale/uv-0.12.19`**: gate SL04 opt-in, wheel/bundle din cwd extern și XDG noi; Stop normal/idempotent → Start nou cu sentinel PG păstrat, Start concurent Stop-first refuzat, status STOPPING/STOPPED și urgență API indisponibilă cu marker durabil/exit4. Nu dovedește singur Pair/Open ori izolarea altui host/UID; G00 local a fost adjudecat împreună cu celelalte probe reale.
- `check-control-image`, `check-installed-image`, `check-installed-control` rămân probe opt-in separate. Ultimul este [harnessul istoric de topologie](../documents/verification/p04-host-uds.md), nu dovada SL02 sau `omnis stop`.

Rollback cod: inspectați commitul și dependențele, `git revert <sha>`, reconstruiți artefactele și rerulați probele. Git nu inversează DB/imaginile/procesele externe. Recuperarea lor cere readback exact al ownershipului; nu se deduce din port, prefix sau un PID dintr-un fișier. Probe numai în XDG scratch noi; nu se reutilizează automat clusterele disposable păstrate.
