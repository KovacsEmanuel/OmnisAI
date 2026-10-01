# SL03 / P0.4c / B01f — registru pair/open

## Contract înainte de modificarea codului

Bază: `0a38cb22d7efb36cfe03ab85a47102cdb73da020`, branch `p04-control-topology-wip`; singurul fișier preexistent neversionat `documents/Omnis_Notite_Originale.html` este protejat și nu intră în felie. Recuperările istorice rămân neatinse. Autoritate: arhitectură §4.1–4.5 pentru comportament, plan §4.2/§5/§19.2 pentru ordine și gates, handofful `p04-pair-open-implementation-prompt.md` pentru dovada cerută. SL02 PASS istoric nu certifică noii bytes.

**Rezultat:** `omnis pair` emite un cod nou numai după verificarea TTY stdin/stdout, release/instanță/receipt/DB/control/HTTP/assets și înregistrarea digestului SHA-256 prin IPC privat existent (`pairing`, UUID issuance); serverul rămâne unicul owner al expirării 5 min, consumului atomic și sesiunii. `omnis open` verifică aceleași identități și deschide numai `origin + '/'`, fără cod ori pornire. `omnis` reutilizează startupul SL02, așteaptă readiness, apoi încearcă deschiderea aceluiași origin; nu emite cod automat și nu pretinde autentificare. `start --no-open [--json]` și status rămân neschimbate.

**Output/exit propus, de confirmat în probe:** `pair` scrie codul numai pe stdout TTY după ACK; `pair --json`, stdin/stdout non-TTY refuză înainte de generare/trimitere, exit 2, diagnostic fix `PAIRING_TTY_REQUIRED`/`PAIRING_FORMAT_REFUSED` pe stderr, fără code/JSON. Eroarea de verificare produce doar diagnostic sanitizat, fără cod: precondiție/config 2, indisponibilitate/readiness 3, recovery/incertitudine 4 (conform `StartError`). `open` și `omnis` raportează originul numai după verificare, apoi distinct `BROWSER_LAUNCH_ACCEPTED` (exit 0, **nu** dovadă de fereastră/sesiune) ori `BROWSER_UNAVAILABLE` (exit 2), `BROWSER_LAUNCH_FAILED` (exit 3); startupul eșuat păstrează propriul motiv/cod și nu invocă openerul. Niciun `browser_opened=true` nu se deduce din return code-ul openerului. Pentru CLI se folosește `xdg-open` cu argv list, URL exact, mediu minim, fără stdout/stderr de subprocess reflectat și timeout finit; nu se folosesc URL-uri/porturi din cwd sau profilul browserului.

**Fișiere permise:** `cli/src/omnis_cli/{main,start,pairing,browser,verified}.py`, `cli/tests/`, `cli/integration/`, `Makefile`, `cli/README.md`, `README.md`, `documents/verification/{p04-pair-open,implementation-status}.md` și skill-uri `.hermes/skills/omnis-*` doar pentru lecții dovedite. API/security/web numai cu contract/test/review dacă integrarea cere o schimbare minimă. Fără parser M22, SL04, provider/target/assessment, servicii boot, profil Hermes, recovery istoric sau push.

**Acceptare:** test-first RED/GREEN pentru TTY/format, refuzuri identitate/readiness/origin, ACK fără leak, opener absent/eșuat/acceptat, implicit new/reuse și regresiile headless/status. Probe pe wheel instalat din cwd extern și XDG privat: PTY real, pairing API/session/logout și expirare/consum, canal fals/stale/străin, URL exact; mock opener = numai consumer, browser real numai cu probă separată. `make check` urmat de `make check-installed-start` secvențial și noua probă L05-control instalată, cu toolchain fixat și identități bytes/readback/cleanup atestat. Review independent read-only pe snapshot exact; fiecare FAIL/BLOCKED/NOT_RUN rămâne explicit.

**Rollback:** `git revert` pentru commiturile de cod/documentare după inspecția dependențelor, reconstruirea wheelului și rerularea gates; Git nu inversează DB, procese sau codurile emise. Nicio ștergere/oprire a recuperărilor sau datelor preexistente.

## Execuție și adjudecare

În curs; rezultatele se completează numai din output real. Nu promova SL03/G00 din acest contract.
