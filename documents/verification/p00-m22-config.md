# M22 — config non-secret în worktree izolat

Bază: `ad3e1f28825ab6ff38361b940bbf3482493d03e4`, branch `p0-m22-config`.
Scope: U21–U23, parser strict și consumatorii P0 actuali; nu aprobă SL04/G00.

**Delta de integrare, după predarea istorică de mai jos:** parserul și fixurile `58aa37a`/`e767a87` sunt integrate local până la `ffbdd6a`. Re-reviewul independent `deleg_8f90ae49` pe exact `e767a87` a dat APPROVED_SCOPED pentru TOML/diagnostic: wheel195 și40 scenarii proprii, fără rebind, nu OCI sau deadline-uri fizice. Compoziția principală a trecut ulterior CLI202 sursă/wheel, dar `make check` pe `d81a396` a eșuat la fixture-ul status care omitea HOME/XDG_CONFIG_HOME. `7192172` repară mediul testului, nu parserul; pozitivul PG post-fix a trecut ulterior în `make check` pe `e336b7b`, cu exit0 și cleanup propriu verificat. U22/U23 fizice și G00 rămân deschise; [registrul curent](p04-stop-recovery.md) separă cod/probe/review.

**Probe noi pe principal, numai scoped:** `538ea7a` a mutat testul de buget normal de pe legacy `_resume_owned` pe `stop_instance`→`run_stop_owner` real cu peer Engine/DB sintetic: config privat `shutdown_timeout_seconds=15`, POST ținut în stall, PREPARED `api.stop`, fără COMPLETED/DELETE, owner pinuit și reaped. Mutantul care ignora bugetul a ratat limita la22.31s; mutantul care-l scurta la2s a fost refuzat după fixul oracolului. `deleg_7cb7f518` a aprobat numai testul; source273/wheel273 și release57 non-OCI au trecut pe bytes curenți. **Nu** este deadline Docker fizic.

`bbbc552` extinde fixture-ul **instalat** Stop, fără a schimba produsul: port aleator nonimplicit numai în `config.toml` privat, primul Start și Start explicit după Stop fără `--port`, origin/journal corelate; între ele, schimbarea portului în același config produce `CONFIG_PORT_CONFLICT`/exit2 cu startup.json, instance.json și inventarul neatinse, apoi configul original se restaurează. Reviewul inițial `deleg_db124c21` a respins un negativ care schimba doar flagul CLI; re-reviewul `deleg_5378d116` a aprobat negativul configurat pe aceiași bytes. `make check-installed-stop` pe această candidată: **exit0**, wheel273/release57 non-OCI și1 probă instalată nominală cu Stop→Start/sentinel→Stop, plus emergency `UNCERTAIN` intenționat; fixture-urile `s4-0mw53bnx`/`s4e-4gmfdaka` au `probe=PASS/cleanup=VERIFIED`, readback independent: câte3 CID-uri absente, rețeaua exactă nominală/proiectul emergency absent, listener/IPC absente, PGDATA inode păstrat, owner receipt COMPLETED doar pentru nominal și marker nereconciliat păstrat pentru emergency. Configul final 0600 are portul/instance origin originale. **U22 rămâne PARTIAL:** pair/open/Host/Origin/TTY pe port configurat și negativele exhaustive U21/U23 fizice nu sunt acoperite; un PASS O nominal nu închide M22/G00. **Înainte de `bbbc552`,** `make check` a ieșit2 la isolated venv din migrarea wheel deoarece runnerul sanitizat nu vedea Pythonul managed din HOME privat; după reproducerea izolată, un HOME privat cu pinul Python3.13.15 vizibil a trecut `test-migrations`20/20 și cleanup exact, dar F complet încă nu a fost rerulat pe acest mediu.

**U23 fizic pre-efect pe codul `cfd541e`, numai Start lock-wait:** după două felii test-only separate fără dovadă fizică, ramura `496bd80` a primit `CHANGES_REQUESTED` pentru fuse race și copii necontabilizați; nu a fost integrată. Proba a fost mutată în `run_lock_expiry` existent: config privat 0600 selectează startup30/cleanup31, CLI-ul instalat nu transmite timeout explicit, părintele ține lockul original pe data-home și nu admite primul efect Docker. RED-ul unit a refuzat lipsa configului; GREEN controale3/3, Ruff/format și release non-OCI wheel273/release57 exit0. Review `deleg_49102cf1`: **APPROVED_SCOPED_TEST** pentru fault pre-efect. `make check-installed-start` pe `s-MIZ7xy` a ieșit **0**: lock refuzat exit2/`LIFECYCLE_BUSY` după **30.100 s**, `startup_budget=30s`, fără root de instanță, CID/rețea ori cleanup allowance intrat. Cele cinci fixture-uri fizice proprii (`s2-9x13zhal`, `s2db-2g51vr7z`, `s2i-9sq2bjd_`, `s2i-sv3f3jjq`, `s2i-z00_pywp`) au `PASS/VERIFIED`; readback independent le-a găsit CID/rețea/imagine/listener/IPC absente, PGDATA inodes originale. Rootul lock `s2lock-pldo_m7d` conține **numai** configul privat neschimbat, fără `s/omnis` sau `r/omnis`; cele zece CID-uri/opt rețele străine sunt neschimbate. Receiptul sintetic `test-only` FAIL/UNCERTAIN rămâne separat, fără efect Docker. Acesta este **U23 Start lock fizic scoped**, nu shutdown/cleanup stall fizic, U23 complet sau G00; F→S→P→O după această editare de test nu a fost rerulat.

**U23 Stop pre-efect pe commitul de test `9e20185` — scoped, nu owner/daemon stall.** Proba instalată ține OFD-ul original `data/omnis/lifecycle.lock` al fixture-ului READY; fișierul privat 0600 setează `shutdown_timeout_seconds=15` fără override CLI. Cu lockul ținut, `omnis stop --json` a refuzat exit2/`LIFECYCLE_BUSY` în **15.115s** (cerut14–22), fără schimbare în journal/instance, lista și starea CID-urilor, identitatea și inspectul complet al rețelei, controlul UDS/admission, rândul barierei PG ori inventarul receipturilor Stop. Configul original a fost restaurat înainte de Stop normal. `deleg_c77ac7f4` a respins primul oracol pentru omisiunea network/control/DB/receipt; părintele a reprodus `resource_snapshot` false-green cu network schimbată/admission închisă. `deleg_7613ca6a` a respins cleanupul după `TimeoutExpired`: părintele a reprodus `teardown → FAIL/VERIFIED`. Gardul minim păstrează locatorul `FAIL/UNCERTAIN` pe timeout/răspuns malformat/restore fail și interzice teardown-ul READY până la readbackul complet; testele RED→GREEN **2/2**, Ruff check/format PASS, re-review `deleg_911f2c79` **APPROVED_SCOPED_TEST** după controale de timeout, reply malformat, excepție după spawn, restore eșuat și pozitivul normal. `make check-release-install` pe ultimii bytes: exit0, wheel273/release59.

După ultima editare, `make check` în HOME/XDG/TMPDIR private și pinuri Python3.13.15/uv0.12.19/Node24.21.0 la `f-a93ihr/db-88af7381ff0747fa`: **exit0**, API358/migrări20/E2E7/CLI273 sursă+wheel/release59, hashurile celor două fișiere schimbate identice înainte/după. Runnerul a consemnat `code=0/family_drained=true`, CID-ul propriu absent, rețeaua/socketul absente și datele PG18 păstrate în `data/18/docker` (readback independent). `make check-installed-stop` la `o-1L9gjA`: **exit0**, wheel273/release59, 1 test instalat, `INSTALLED_STOP_LOCK_EXPIRY` de mai sus, Stop→Start/sentinel→Stop verificat și emergency UNCERTAIN păstrat. Citirea independentă `o-1L9gjA/independent-readback.json` arată pentru `s4-vsc15kew` și `s4e-3m675pdd` `PASS/VERIFIED`, toate CID-urile exacte, network/image create, socketurile și listenerul absente, PGDATA inode originală, configul nominal 0600 restaurat, șase etape de receipt nominal `STOPPED`; emergency rămâne `UNCERTAIN` cu marker și fără receipt STOPPED fabricat. Inventarul înainte/după al daemonului, celor **10 CID-uri/8 rețele/21 imagini** străine este identic, zero containere running. Controlul sintetic `s2i-kz5ywx4m` rămâne **FAIL/UNCERTAIN** intenționat (`start_oracle_probe.py`): zero CID/rețea, fără endpoint Unix viu în `/proc/net/unix`, dar pathname-ul test-only `http/api.sock` este păstrat, nu declarat cleanup de produs. Primul F din aceeași sesiune a ieșit0 pe **bytes amestecați** în timpul remedierii și nu primește credit de candidat. Nici aceste două gate-uri nu certifică shutdown/cleanup sub **stall owner/daemon**, C01–C17, M22 integral, secvența completă F→S→P→O pe ultima candidată, reviewul final sau CI.

**U21 refuz pe consola instalată, fără OCI.** Din wheelul instalat de O la `o-1L9gjA/omnis-p04-cli-check/bin/omnis`, în cwd/HOME/XDG/TMPDIR private distincte și fără image receipt, părintele a invocat cele **șase comenzi reale** (`omnis`, `start --no-open --json`, `status --json`, `pair`, `open`, `stop --json`) pentru **zece configurații invalide**: cheie secretă necunoscută, bool ca integer, shutdown14, fișier0644, symlink către fișier propriu, director config0775, port float, TOML malformat, cleanup29 și startup29. Toate **60/60** au dat exit2/`CONFIG_INVALID`, fără markerul sintetic în output și fără fișiere în state/data/IPC; pozitivul `status --json` fără config și cu config valid privat a dat în ambele cazuri exit3/`NOT_INSTALLED` fără efect, deci nu este un oracol always-refuse. Matricea sanitizată este în `u21-console-znd_mg08/results.json`; citirea independentă după probe a confirmat același daemon, **10 CID-uri/8 rețele/21 imagini** și zero running ca înainte de O. Acestea sunt refuzuri pre-efect în absența unei instalări, **nu** proba tuturor comenzilor pe un READY existent, precedență/rebind, Host/Origin/TTY sau U21/M22 integral.

**U22 pair/open pe port configurat, fără pierderea defaultului.** `2b52a76` adaugă în fixture-ul instalat `config.toml` privat0600 cu port aleator neimplicit și leagă originul TTY/instance/journal/status/reuse de acesta; primul test ar fi înlocuit proba TTY implicită pe8765. Parentul a reprodus RED pe acea pierdere; `88fe2cb` păstrează separat primul fixture TTY/default8765, adaugă al doilea TTY/configurat și apoi non-TTY/default8765, fiecare cu state root/cleanup propriu. Reviewul `deleg_4186ea35` a aprobat numai oracolul test-only. Primul P `p-q5EZzF` a ieșit2 **înainte de OCI**, deoarece testul de retenție a imaginii aștepta un singur Start; inventarul străin a rămas identic, iar receiptul sintetic FAIL/UNCERTAIN nu avea CID/UDS viu. `d37b040` a remediat strict secvența de test și a injectat assertion/timeout la **ambele** invocări; `deleg_bd17d8cb` APPROVED_SCOPED_TEST, `make check-release-install` wheel283/release61 exit0. Al doilea P `p-AzA7ZJ` a ieșit2 după primul TTY PASS/VERIFIED: în al doilea fixture configurat, `pair` a refuzat corect exit2/`CONFIG_PORT_CONFLICT` la Origin străin, înaintea identity-check-ului care dă exit4 în fixture-ul implicit; oracolul îi cerea greșit exit4. Al doilea fixture era `FAIL/cleanup=VERIFIED`, cu CIDs/network/IPC absente, PGDATA originală, **nu PASS**.

Imaginea păstrată de `runtime_pending` după acest FAIL a fost retrasă **operațional separat, numai cu aprobarea explicită exactă a operatorului**, fără force/prune/volume: tag `omnis-control-e62b6e17752e49b090b39d1d84af510c:0.1.0`, ID `sha256:876e4e6031d49066560f8ee6d25a78afc790b44b329df0c5bcddb05e8ffb4ce7`, daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`. Preflightul `p-image-retire-xmynqD/intent.json` a pinuit tagul unic, zero containere dependente, cele două PGDATA inodes și hashurile receipturilor; `docker image rm <tag>` a dat ACK nou `Untagged`/`Deleted`, iar procesul independent `independent-readback.json` a confirmat absența exactă a tagului/ID-ului, inventarul celorlalte10 CID-uri/8 rețele/21 imagini identic, datele/receipturile nemodificate. Nu reexecuta efectul consumat; vechiul P FAIL rămâne arhivat.

`d1be1d1` a corectat numai așteptarea pe **același canal instalat**: config nonimplicit + Origin străin → exit2/`CONFIG_PORT_CONFLICT`, default fără config → exit4/`RECOVERY_REQUIRED`; ambele refuzuri păstrează pairing issuance, listenerul străin necontactat și instanța restaurată. Review focalizat `deleg_627f9a90` **APPROVED_SCOPED_TEST**; config5/5 și `make check-release-install` wheel283/release61 exit0. `make check-installed-pair-open` pe HEAD-ul `d1be1d1`, root `p-ilqigy`, a ieșit **0**, wheel283/release61 și1 test instalat cu **trei fixture-uri fizice proprii**: `s2-av41fkfo` TTY/default8765, `s2-5at9l86z` TTY/configurat48119, `s3h-9bsit0te` non-TTY/default8765, toate `PASS/VERIFIED`. TTY-urile au probat codul one-use/expiry, Host/Origin, sesiunea în Chromium de laborator și refuzurile lor; `opener=BROWSER_LAUNCH_FAILED` nu este dovadă de fereastră OS. Readbackul independent `p-ilqigy/independent-readback.json`: fiecare CID exact, network/image nouă, IPC/listener absente, PGDATA inode originală, originul din instance egal portului atestat, configul configurat0600 restaurat, daemonul și cele10 CID-uri/8 rețele/21 imagini preexistente identice. Controlul sintetic `s2i-sae8dcy9` rămâne FAIL/UNCERTAIN cu zero CID/UDS viu, pathname test-only păstrat. **U22 pair/open configurat este avansat scoped, nu U22/M22 complet, secvența finală F→S→P→O sau G00.**

## Contract de implementare și probă

**Limită confirmată la integrarea `bd5ee23`:** reviewul independent `deleg_051de493` aprobă scoped compatibilitatea config/origin și propagarea deadline-ului în cod. Ramura etichetată `normal` din `test_config_deadlines.py:126–129` apelează însă `_resume_owned`, nu ownerul integrat `run_stop_owner`; dovada sa nu certifică U23 pe traseul nou. Testele respective rămân probe ale consumatorului legacy/emergency. Startup30/shutdown15/cleanup configurat sub stall pe ownerul instalat și combinația configurată Host/Origin/TTY rămân **NOT_RUN**; gate-ul S s-a oprit la observerul argv, nu la un defect M22 demonstrat.

- Config numai `$XDG_CONFIG_HOME/omnis/config.toml`, implicit `~/.config/omnis/config.toml`; lipsa nu creează directoare/fișiere.
- Patru chei root: `port` (1024–65535; default 8765), `startup_timeout_seconds` (30–300; default 180), `shutdown_timeout_seconds` (15–180; default 180), `cleanup_timeout_seconds` (30–180; default 100). Numai integer exact; nicio cheie necunoscută sau secretă.
- CLI explicit > config > defaults numai la instanță nouă. Receiptul/instance origin existent rămâne autoritate inclusiv la restart. O selecție explicită divergentă refuză, fără rescrierea originului, journalului sau adoptarea datelor.
- Refuz sanitizat înainte de lock/Docker/UDS/browser pentru config invalid în default/start/status/pair/open/stop. Fișier privat 0600, director Omnis 0700, owner curent, fără hardlink/symlink ori ancestor replaceable; path absolut/canonic. Config absent nu autorizează ignorarea unei căi existente nesigure.
- Deadline startup/shutdown monotonic propagat în consumatorii existenți; cleanup are allowance nou separat numai după eșecul startupului. Așteptările forwarder consumă deadline-ul, nu un timeout fix mai mare.
- Căi permise: `cli/src/omnis_cli/config.py`, wiring în main/start/stop/status/verified, `cli/tests`, `cli/README.md`, acest document. Nicio modificare globală/HTML/Makefile/profil. Dacă un consumator real cere alt fișier, justificarea precede editarea aici.
- TDD vertical, output RED/GREEN real în scratchul privat al worktree-ului; source import verificat; build/wheel instalat și executat din cwd extern cu HOME/XDG private și hashuri comparate.
- Fără Docker/PG/OCI, servicii existente, network provider/ținte sau push. Boundary cu runtime substituit nu dovedește deadline fizic Docker. Gate-urile fizice și review independent sunt NOT_RUN/delegare părinte; reconcilierea cu noul Stop este obligatorie înainte de integrare.
- Rollback: revert commiturile M22 în ordine inversă; nu există migrare ori rescriere de date/config a operatorului.

## Proveniență inițială

`uv 0.12.19`; `uv sync --locked --no-config --offline --directory api` și `cli`: exit 0. Python 3.13.15. `cli/.venv/bin/python -I` importă `omnis_cli` din acest worktree (`cli/src/omnis_cli/__init__.py`), nu principalul.

## Rezultate

### Extindere minimă justificată înainte de editare

`ControlRuntime.run` în `cli/src/omnis_cli/start_runtime.py` este consumatorul real al deadline-urilor Start/Stop/cleanup. La timeout, reap-ul liderului folosește încă `process.wait(timeout=5)` după expirarea deadline-ului; astfel propagarea din start/stop singură nu poate satisface U23. Se admite aici strict înlocuirea acelui timeout cu timpul rămas în bugetul runtime, cu RED pe un child propriu și observarea argumentului `wait`, fără schimbarea autorității/familiei/ACK Docker și fără refactor. Dacă reap-ul nu se poate confirma în buget, incertitudinea existentă rămâne sticky; această probă nu certifică daemonul fizic.

## Predare pe snapshotul testat

Ultimul cod de produs: `90bd6e3`; suite/config console și corecții statice până la
`8330845`. Documentarea ulterioară nu schimbă bytes produs/test. **Cod M22 implementat
în acest worktree; neintegrat, NOT_REVIEWED.** U21–U23 au dovezi locale parțiale,
nu închidere G00. SL04/fence din principal nu a fost integrat în această ramură.

### Comenzi și output real

Cwd pentru toate comenzile source: `/home/kali/.hermes/cache/scratch/omnis-p0-m22-config`.
`UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`.
Logurile private sunt sub `cli/.venv/m22-evidence/` (ignorate Git, pot expira).

| Ciclu | Comanda (prefix `cli/.venv/bin/python -I -m unittest discover -s cli/tests`) | RED | GREEN / commit |
|---|---|---|---|
| 01 | `-p test_config.py -v` | exit1, șase dispatchuri ignoră config secret | exit0; `2676279` |
| 02 | `-p test_config.py -v` | exit1, default startup absent | exit0; `ea7c553` |
| 03 | `-p test_config.py -v` | exit1, patru căi absente nesigure admise | exit0; `e96b918` |
| 04 | `-p test_config_consumers.py -v` | exit1, șapte refuzuri lipsă la consumatori | exit0; `57e2c87` |
| 05 | `-p test_config_consumers.py -k precedence -v` | exit1, port8765 în loc9010 și flag startup absent | exit0; `10190c5` |
| 06 | `-p test_config_consumers.py -k allowance -v` | exit1, deadline cleanup600 în loc531 | exit0; `972c4b7` |
| 07 | `-p test_config_consumers.py -k stop_config -v` | exit1, deadline280 în loc115 și flag absent | exit0; `35687db` |
| 08 | `-p test_config_deadlines.py -v` | exit1, fuse-ul salvează childul și fluxul ajunge la seam daemon; cleanup fără deadline | exit0; `ab8cedc` |
| 09 | `-p test_config_deadlines.py -k runtime_timeout -v` | exit1, reap fix5 depășește0.15 | exit0; `90bd6e3` |

Fișiere `01-red.log`…`09-red.log`, perechile `*-green.log`, `10-green.log` și
`11-console.log` păstrează outputul efectiv. GREEN-urile 05–07 au rulat întregul
`-p 'test_config*.py'`, 09 întregul `test_config_deadlines.py`. Review independent
nu a fost executat de subagent.

Regresii finale, după ultimul cod:

```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS \
  XDG_CONFIG_HOME="$PWD/cli/.venv/m22-config" \
  cli/.venv/bin/python -I -m unittest discover -s cli/tests -v
```

**exit0, 194 teste, 31.147s**, `final-source.log`. M22 adaugă 14 metode de test;
console testul are 72 combinații invalide (numărate prin AST), procese reale în
cwd/XDG private; nu emite coduri/nu creează state/data/IPC și păstrează configul.

Wheel extern nou `W=/home/kali/.hermes/cache/scratch/m22w-7Td0Flrp`:

```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS \
  UV_OFFLINE=1 TMPDIR="$W" HOME="$W/home" XDG_CONFIG_HOME="$W/config" \
  XDG_STATE_HOME="$W/state" XDG_DATA_HOME="$W/data" XDG_RUNTIME_DIR="$W/ipc" \
  make check-cli-wheel UV="$UV" CLI_PY="$PWD/cli/.venv/bin/python"
```

**exit0, 194 teste, 32.016s**, `final-wheel.log`; build din worktree, venv/install
private și teste din cwd extern,
console smoke `status` exit3/NOT_INSTALLED. Nu a rulat gate-ul `test-cli-live`/PG.
Import instalat cu `-I`, verificat din cwd `$W`:
`$W/omnis-p04-cli-check/lib/python3.13/site-packages/omnis_cli`.
Toate **17 module** `.py` instalate au SHA-256 identic sursei acestui worktree,
comparare programatică și manifest local `source-wheel.sha256`.
Wheel: `$W/omnis-p04-cli-wheel/omnis_cli-0.1.0-py3-none-any.whl`, SHA-256
`4ef3fab443a2005ecf4c1733393c1795111b3dc6cf4e8c5db81eaa0ee7b915f0`.

Static: `api/.venv/bin/python -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests`
și `ruff format --config api/pyproject.toml --check cli/src cli/tests`: exit0,
42 fișiere formatate. `mypy --config-file api/pyproject.toml --no-incremental cli/src`:
exit0, 17 fișiere, fără Any/cast/ignore pentru validare.
`python scripts/render_docs.py --check`: exit0, fără scriere HTML.
`python -m unittest discover -s tests/documentation -v`: exit0, 62 teste.
`git diff --check`: exit0.

### Eșecuri relevante și limite

- Prima regresie neizolată după validarea căilor a refuzat directorul ambiental
  `~/.config/omnis` cu mod0775. Nu s-au citit secrete și nu s-a modificat configurația
  operatorului. Rerularea cu XDG_CONFIG_HOME privat a trecut. Părintele trebuie să
  izoleze și config-home în gate-urile sale, nu să relaxeze parserul.
- Două seams istorice pentru `start_instance(port)` au avut TypeError după wiringul
  kwargs; adaptate numai semnăturile testelor în `10190c5`, păstrând assertions.
  Ruff a găsit importuri/capturi de variabile de buclă; remediate test-only în `27e31a2`.
- Copiii proprii rezistenți la TERM au verificat deadline rămas0.2s, returnare sub0.65s,
  SIGKILL efectiv și reap exact, fără fuse în GREEN. Cazul runtime observă timeoutul
  transmis către `wait` și face readback/reap separat al childului propriu. Nu este
  un deadline fizic Docker, o dovadă de familie daemon ori o promisiune de reap în
  kernel blocat; uncertainty/family_drained=false sunt păstrate când dovada lipsește.
- Startup30/shutdown15 pe lock/HTTP/control/daemon stall **la durata configurată
  integrală**, flux config-valid cu Docker/PG/Host-Origin/TTY real și crash-cut-urile
  SL04: **NOT_RUN aici**. Testele de propagare a deadline-urilor folosesc runtime/ceas
  substituit și nu primesc credit fizic. Suitele existente includ UDS/procese locale.
- `make check`, `check-installed-start`, `check-installed-pair-open`,
  `check-installed-stop`, M03 suport/UID/LAN/IPv6, CI remote și reviewul de integrare:
  **NOT_RUN**, rezervate părintelui. Reticle CLI: NOT_APPLICABLE; Chisel NO-GO,
  neexecutat. Fără Docker/PG/servicii preexistente/provider/ținte/push/HTML original.
- Config și journal origin nu se rescriu. Conflictul explicit refuză înainte de
  consumatori; un config valid nu autorizează rebind pe STOPPED. Niciun receipt
  legacy nu este adoptat. Resursele de test noi sunt locale, efemere; wheelul și
  logurile sunt păstrate ca artifact, nu există container sau serviciu creat aici.

### Delta pentru părinte și lecție reutilizabilă

| Rând | Cod în ramură | Probe | Review / pas |
|---|---|---|---|
| U21 M22 parser | implementat + toți consumatorii P0 | source/wheel local PASS scoped | NOT_REVIEWED; review exact |
| U22 origin | fără rebind, conflict înainte de efect, receipt păstrat | boundary local + regresii existente; OCI NOT_RUN | reconciliază cu Stop/fence |
| U23 bugete | startup/shutdown/cleanup, waits/reap bounded | propagare locală + children reali; stall fizic NOT_RUN | gate-uri părinte |
| SL04/M03/G00 | neschimbate în principal | NOT_RUN pe integrare | nu aproba din acest raport |

Lecție de transmis skillurilor repo prin părinte: izolează `XDG_CONFIG_HOME` la fel
ca HOME/state/data pentru o nouă sursă de config, validează ancestorii chiar când
fișierul lipsește și caută timeouturi fixe în consumatorii inferiori (inclusiv reap).
Nu schimba profiluri/skills globale dintr-un worktree cu scope limitat.
