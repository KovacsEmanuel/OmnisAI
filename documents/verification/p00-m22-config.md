# M22 — config non-secret în worktree izolat

Bază: `ad3e1f28825ab6ff38361b940bbf3482493d03e4`, branch `p0-m22-config`.
Scope: U21–U23, parser strict și consumatorii P0 actuali; nu aprobă SL04/G00.

**Delta de integrare, după predarea istorică de mai jos:** parserul și fixurile `58aa37a`/`e767a87` sunt integrate local până la `ffbdd6a`. Re-reviewul independent `deleg_8f90ae49` pe exact `e767a87` a dat APPROVED_SCOPED pentru TOML/diagnostic: wheel195 și40 scenarii proprii, fără rebind, nu OCI sau deadline-uri fizice. Compoziția principală a trecut ulterior CLI202 sursă/wheel, dar `make check` pe `d81a396` a eșuat la fixture-ul status care omitea HOME/XDG_CONFIG_HOME. `7192172` repară mediul testului, nu parserul; pozitivul PG post-fix a trecut ulterior în `make check` pe `e336b7b`, cu exit0 și cleanup propriu verificat. U22/U23 fizice și G00 rămân deschise; [registrul curent](p04-stop-recovery.md) separă cod/probe/review.

**Probe noi pe principal, numai scoped:** `538ea7a` a mutat testul de buget normal de pe legacy `_resume_owned` pe `stop_instance`→`run_stop_owner` real cu peer Engine/DB sintetic: config privat `shutdown_timeout_seconds=15`, POST ținut în stall, PREPARED `api.stop`, fără COMPLETED/DELETE, owner pinuit și reaped. Mutantul care ignora bugetul a ratat limita la22.31s; mutantul care-l scurta la2s a fost refuzat după fixul oracolului. `deleg_7cb7f518` a aprobat numai testul; source273/wheel273 și release57 non-OCI au trecut pe bytes curenți. **Nu** este deadline Docker fizic.

`bbbc552` extinde fixture-ul **instalat** Stop, fără a schimba produsul: port aleator nonimplicit numai în `config.toml` privat, primul Start și Start explicit după Stop fără `--port`, origin/journal corelate; între ele, schimbarea portului în același config produce `CONFIG_PORT_CONFLICT`/exit2 cu startup.json, instance.json și inventarul neatinse, apoi configul original se restaurează. Reviewul inițial `deleg_db124c21` a respins un negativ care schimba doar flagul CLI; re-reviewul `deleg_5378d116` a aprobat negativul configurat pe aceiași bytes. `make check-installed-stop` pe această candidată: **exit0**, wheel273/release57 non-OCI și1 probă instalată nominală cu Stop→Start/sentinel→Stop, plus emergency `UNCERTAIN` intenționat; fixture-urile `s4-0mw53bnx`/`s4e-4gmfdaka` au `probe=PASS/cleanup=VERIFIED`, readback independent: câte3 CID-uri absente, rețeaua exactă nominală/proiectul emergency absent, listener/IPC absente, PGDATA inode păstrat, owner receipt COMPLETED doar pentru nominal și marker nereconciliat păstrat pentru emergency. Configul final 0600 are portul/instance origin originale. **U22 rămâne PARTIAL:** pair/open/Host/Origin/TTY pe port configurat și negativele exhaustive U21/U23 fizice nu sunt acoperite; un PASS O nominal nu închide M22/G00. **Înainte de `bbbc552`,** `make check` a ieșit2 la isolated venv din migrarea wheel deoarece runnerul sanitizat nu vedea Pythonul managed din HOME privat; după reproducerea izolată, un HOME privat cu pinul Python3.13.15 vizibil a trecut `test-migrations`20/20 și cleanup exact, dar F complet încă nu a fost rerulat pe acest mediu.

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
