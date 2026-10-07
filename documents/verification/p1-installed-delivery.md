# P1 — livrare locală persistentă pentru operator

## Contract autorizat și stare

**CLOSED_SCOPED local — instalare persistentă P1 utilizabilă de operator pe această VM single-user; IMPLEMENTED / PASS_LOCAL_RECORDED / APPROVED_SCOPED.** Produs și binding instalat probate pe `c82a8d44b679b0712ba417b17453c58c43f1a1b7`, cu fixul `110c16c`; [receiptul final](p1-installed-gate.json) leagă reviewurile, QA independentă, gate-ul canonic și adjudecarea părintelui. Bază produs inițială `682449be2c5afcd8fee8b5c93d7b3966b714ac3b`; P1/B02–B04/G01 era deja acceptat pentru drafturi inerte. Operatorul a autorizat instalarea separată, comanda `omnis`, QA Dashboard/Setup pe build/API/PostgreSQL instalate, loguri și remedierea blocantelor, apoi pregătirea P2. Această felie nu implementează P2 și nu activează assessment/model/provider/ținte. Nu este un release distribuit, backup certificat sau aprobare estetică/WCAG.

Arhitectura §4.1–4.4 și planul §6 decid comportamentul; nu este un plan de produs concurent. Contractul arhitectului read-only susține schema nouă `0008_engagement_edit` prin migratorul existent `--initialize` → Alembic head. Nu este necesar scaffold nou. Releaseul păstrează versiunea `0.1.0`, deci un root nou evită coliziunea de bytes cu P0. Nu facem upgrade/adopție/migrare a instalării vechi.

## Efecte și proprietate

- Launcher nou, numai dacă absent: `/home/kali/.local/bin/omnis`, wrapper regular executabil către CLI wheel în `/home/kali/.local/share/omnis-p1/cli-venv`.
- Homes ale candidatului inițial: DATA `/home/kali/.local/share/omnis-p1`, STATE `/home/kali/.local/state/omnis-p1`, CONFIG `/home/kali/.config/omnis-p1`. **Wrapperul livrat folosește subroots `r1`** explicate mai jos și în [referința exactă](p1-installed-launcher.sh.txt); candidatul inițial rămâne oprit, cu datele păstrate. Wrapperul elimină XDG_RUNTIME_DIR numai pentru invocarea lui; IPC folosește fallbackul privat din state. Niciun export global sau profil shell/Hermes modificat.
- Roots noi 0700; receipts/loguri 0600; numai bind-rootul PostgreSQL este 0711 conform contractului PG18. Interpreter Python 3.13.15 durabil, nu scratch.
- Build cu uv 0.12.19, Node 24.21.0/npm 11.19.0 și lockurile curente. Imagine proiect nou legată de manifest. Servicii numai DB/API/supervisor, control bridge intern și zero porturi Docker; forwarder host pe 127.0.0.1:8765, după refuzul unui port străin.
- Resursele vechi/străine și `documents/Omnis_Notite_Originale.html` rămân neatinse. Nu citește/configurează credentiale personale; codul de pairing al QA trece privat din PTY către browser, fără argv/env/URL/log.
- Non-obiective: autostart OS, LAN/multi-user/remote, push/CI, upgrade P0, backup/restore de date vechi, nouă aprobare estetică, Reticle instrumentation sau Chisel.

Preflight real: noul launcher/roots absente, `~/.local/bin` deja în PATH, Docker 27.5.1/Compose 2.32.4-3 și imaginile base exact-pin prezente; fără listener pe 8765. Refuzul ambiental CONFIG_INVALID este explicat de directorul vechi `~/.config/omnis` mod 0775, fără config.toml; nu îl chmodăm și nu relaxăm parserul. Rootul nou este o instalare independentă, nu un bypass de validare.

## Acceptare și verificare

1. `omnis` instalat funcționează din cwd exterior; wheel/manifest/assets/image și schema 0008 atestate.
2. Dashboard real și New/Setup în cinci pași, Save→GET exact, reload, mod/obiectiv/scope/context/matrice/bugete/politică salvate fără trafic; Start și paginile viitoare indisponibile cu motive.
3. Două taburi: CAS 409, editări locale păstrate și fără overwrite; validare 422 și focus către câmp.
4. Pair/session/logout, Host/Origin/CSRF/unauth denials, fără secrete în URL/storage/output; keyboard/focus și viewports mobile/desktop pe browser real.
5. Stop repetat și Start explicit: aceeași PGDATA/draft/revizie/digest, autoritate nouă și fără migrare/autoresume; instanța livrată este lăsată READY separat de cleanupul browserului/probelor.
6. Loguri ale CID-urilor exacte și forwarderului inspectate bounded, datele generate inventariate fără secret files/env dump; erorile sunt adjudecate, nu ascunse sub un exit 0.
7. Două reviewuri complementare snapshot-bound și QA live independentă; defectele confirmate primesc RED→GREEN și re-review focalizat. Probe existente neschimbate nu se reauditează fără motiv.

Părintele este autorul instalării/wrapperului; al doilea dezvoltator deține numai driverul browser în scratch, fără lifecycle sau editări repo. Reviewurile sunt read-only; resursele și integrarea rămân ale părintelui. Concluziile și hashurile probelor vor fi persistate aici/în receipt după executare, nu deduse din contract.

## Inversă / recuperare

Înainte: launcher și roots noi absente. Inversă normală: același `omnis stop --json`, exit 0 plus STOPPED și absența resurselor/listenerului propriu. Se păstrează PGDATA, secretul DB generat și receipturile; nu `down -v`, prune sau downgrade. Retragerea launcherului numai la cerere și după compararea hashului propriu; vechiul profil nu are nevoie de restaurare fiindcă nu este modificat. Git revert inversează numai notele/codul versionat, nu DB/serviciile. Orice exit 4 / ACK pierdut / identitate schimbată păstrează date și marker, cu BLOCKED/RECOVERY_REQUIRED; fără retry orb.

Backup/restore și upgradeul între releaseuri nu sunt promise de această instalare nouă; rămân probe G-OPS/G08 separate. Nu se copiază live PGDATA. Reticle: NOT_INTEGRATED în produs, Playwright/DOM/screenshot independent; Chisel BLOCKED/NO-GO, nefolosit.

## Adjudecare intermediară și candidat corectat

- Review normativ `P1-N01-DASHBOARD-SETUP-CONTRADICTION`: CONFIRMED în sursă, asset servit și screenshot real; textul B03 neagă Setup B04. `110c16c` corectează numai hintul randat, cu regresie consumer RED exit1 → 2/2 GREEN și `make check-web` exit0 după ultima editare. Re-review instalat rămâne pending. Reviewul complementar `b9ceacd` este APPROVED_SCOPED; CLI/API/ownership/topologia lui nu s-au schimbat.
- Gate-ul canonic pe produsul inițial `b9ceacd` a trecut `make check` exit0; DB disposable `omnis-p01-8b468ed9fc4b408f8c0f052a43809034` a avut readback `absent=True`, networks/socket absente, uncertain=False și date sintetice păstrate. Nu atribuim acest verdict textului corectat ulterior; gate-ul web afectat a fost rerulat separat.
- Instanța inițială a trecut creare/editare/5 pași/GET/reload/CAS409/422/auth și Stop repetat → Start explicit → browser/PG readback. Același dataset, revizie3/digest/payload, generație1→2(STOPPED)→3, epoch1→2. Restartul imediat a refuzat conservator PORT_CONFLICT cu TIME_WAIT propriu observat; după 65s Start a trecut. Driverul a avut un selector greșit pentru cardurile UNAVAILABLE și a confundat focus programatic după pointer cu focus-visible de tastatură; corecțiile oracle nu au schimbat produsul sau slăbit aserțiunile. Un prim caz422/focus nu a trecut, dar reproducerul restrâns pe aceeași revizie a trecut fără editare de produs; cauza acelui prim eșec nu este stabilită. Receipturile intermediare FAIL sunt păstrate, nu rescrise ca PASS.
- Logurile de pornire/restart sunt fără alarmele căutate. PostgreSQL inițial a consemnat **două erori ale sondelor SQL ale părintelui**, nu ale aplicației: tabel inexistent `engagements` și coloană inexistentă `name` în `engagement`. După citirea migrației, query-ul corect a confirmat persistența; istoricul acestor erori nu este șters. Nu pretindem că toate logurile istorice au fost goale sau fără erori.
- Corecție de evidență: mesajul commitului `b9ceacd` spune 12 payloaduri, dar readbackul real și ambele reviewuri confirmă **10/10** fișiere de manifest. Numărul10 este autoritatea probei.

### Livrare fără overwrite/upgrade implicit

Versiunea imutabilă0.1.0 refuză bytes diferiți în același root; nu ocolim această regulă. Instanța inițială este **candidat QA provizoriu**, cu numai datele sintetice generate aici, nu date ale operatorului. Va fi oprită normal și păstrată cu date/receipturi. Candidatul corectat este instalat **aditiv**, cu XDG homes noi `/home/kali/.local/share/omnis-p1/r1`, `/home/kali/.local/state/omnis-p1/r1`, `/home/kali/.config/omnis-p1/r1`; subdirectorul CLI durabil inițial rămâne reutilizat byte-identic. Wrapperul se schimbă numai după Stop/readbackul candidatului provizoriu. Nicio migrare, copiere PGDATA, release overwrite, ștergere de dataset sau modificare P0.

Before/after: wrapperul inițial SHA256 `4c982652a1f5f50f58db383e41f81e392af0d44228b29848154d39661096cde8`; roots r1 absente înainte de această instalare. Inversă: Stop verificat al candidatului r1, apoi restaurarea wrapperului inițial din referința Git `b9ceacd` numai la cerere, fără Start automat și fără ștergerea vreunuia dintre datasets. Schimbarea wrapperului nu mută datele vechi în r1. Candidatul nou va avea propriul proiect/image/instance/schema0008 și va primi re-review și QA live independente înainte de acceptare finală. Acesta este ultimul candidat al acestei livrări, nu o funcționalitate de upgrade sau un plan nou.

## Acceptare finală — candidat r1

Paragrafele intermediare de mai sus păstrează statusul de la acele încercări, nu restanțe curente. Părintele a recitit rapoartele complete, verificat hashurile și adjudecat criteriile 1–7 pe produsul înghețat `c82a8d4`:

| Contract | Dovadă reală și verdict scoped |
|---|---|
| CLI/artefacte/schema | Comanda instalată din cwd exterior: exit0/READY; manifest10/10, CLI21/21 și API41/41 comparate byte-exact; schema `0008_engagement_edit`. |
| Dashboard/New/Setup | Browser Chromium/Playwright1.63.0 + API/PostgreSQL reale: creare, General→Focused, cinci pași, Save→GET/payload exact, reload; count1 din DB. Nu date DEMO. |
| Concurență/erori | Conflict real două taburi409 păstrează editările locale fără overwrite;422 real + focus către eroare/câmp și dataset neschimbat. |
| Sesiune/UI | Pairing privat PTY/stdin, logout și401; negative Host400/Origin403/CSRF403; keyboard/focus și320/390/1280/1440. În total29 checks PASS și35 capturi, nu64 teste funcționale. |
| Stop/restart/persistență | Stop, Stop repetat, Start explicit no-open: exit0/0/0; absența vechilor CID-uri/rețea/forwarder pinned/listener/IPC, PGDATA păstrată. Același engagement și rând complet,3 revizii, revizia curentă3/digest/payload identice după restart/logout; generation1→2→3, epoch1→2. TIME_WAIT propriu,65s așteptare bounded, Start reușit din prima. |
| Loguri/topologie | Exact DB/API/supervisor, bridge intern, zero porturi Docker/mounts suplimentare; tail250 pe CID/loguri și verificarea privată a codului emis în tail300 + forwarder: zero alarme/patternuri căutate. Inventarul celor10 resurse străine și candidatul provizoriu au rămas neschimbate. Nu tracer universal. |
| Review/gate final | Două re-reviewuri APPROVED_SCOPED pe `c82a8d4`, [normativ](p1-installed-normative-review.json) și [binding](p1-installed-binding-review.json), apoi [QA independentă](p1-installed-live.json) PASS_SCOPED_LIVE_QA. Gate canonic final `proc_de22b09c9cf4`: `make check` exit0/family_drained=true;479 bindings produs/helper/wrapper identice înainte și după QA/gate. |

Gate-ul final a executat62 docs/42 development,402 API/22 migrare/74 web/9 E2E reale,284 CLI source +284 CLI wheel,1 CLI status integrare,61 release,44 runtime +6 native-build AST și lint/type/build/contracts/audit. Acestea sunt rezultate per suită, **nu un total unic** și nu dovadă pentru consumatori nelivrați. Audit point-in-time:37 pachete API fără vulnerabilități cunoscute, npm zero. Fixture-ul DB `omnis-p01-22a8589fd1fb4e7f87c011d4326780dd` a fost retras exact cu networks/socket absente, uncertain=False și date sintetice păstrate în scratch; r1 nu este fixture-ul gate-ului și rămâne pornit.

**P1-N01 → RESOLVED_SCOPED:** RED/GREEN și fixul minim `110c16c`, assetul corectat live SHA256 `979e43efd816153df75017bd4d8fe476013faa98ab3ff399dc5dd54ef4150dd7`, regresie consumer independentă2/2 și ambele journey-uri finale verifică textul vizibil. Nu există blocker confirmat rămas în acest scope. `P1-QA-OBS01` este o observație copy neblocantă: tagline-ul generic despre Start este calificat alăturat prin assessment indisponibil, iar Start este dezactivat. `P1-QA-OBS02` este limita capturilor viewport, nu un overlap reprodus; scrolling/DOM/focus au probe separate. Nu transformăm acestea în defecte de execuție sau aprobare estetică.

Rapoartele și oracolele istorice sunt arhivate byte-identic: [browser](p1-installed-browser.mjs.txt), [transport privat](p1-installed-private-run.py.txt), [snapshot](p1-installed-snapshot.py.txt). Au paths/identități fixe și nu sunt comenzi publice portabile; nu relaxa atestările pentru a le executa pe alt HEAD. Trei capturi reale păstrate: [Dashboard1440](p1-installed-after-dashboard-1.png), [Setup390 după restart](p1-installed-after-restored-review-390.png), [Review1440](p1-installed-before-review-1440.png). Restul32 rămân scratch cu hashurile în receipt și pot expira. Concluziile/dovezile adjudecate sunt durabile în Git, nu numai în scratch. Logurile sanitizate ale r1 rămân local în state, nu în Git.

## Utilizare acum

Instanța este lăsată **READY** la `http://127.0.0.1:8765`, instance `3e901f05-6bc5-4cc0-961d-007feb652de7`, release0.1.0, generation3/epoch2, `dashboard_ready=true`, **`assessment_ready=false`**. Browserul QA și driverele proprii sunt închise; sesiunea QA a făcut logout. Un draft sintetic `Installed P1 synthetic draft` este păstrat intenționat, nu un finding sau autorizație de trafic.

Din orice director, într-un terminal interactiv:

```sh
omnis status --json
omnis pair
omnis open
```

Introdu codul afișat de `pair` numai în pagina locală de pairing, nu în chat/log/config; este one-use și expiră în5 minute. Deschide manual URL-ul dacă openerul OS nu confirmă fereastra. `omnis` simplu pornește/reutilizează și încearcă browserul, dar la reuse nu emite din nou cod: cere `omnis pair` explicit dacă sesiunea lipsește. Din Dashboard poți crea și edita drafturi, parcurge Setup, salva și reîncărca; declarațiile de scope/buget/politică **nu declanșează trafic**. Brain/findings/coverage/rapoarte/provider/catalog rămân explicit unavailable.

Oprire și pornire ulterioară, fără reset de date:

```sh
omnis stop --json
omnis status --json
# Numai după STOPPED verificat:
omnis start --no-open --json
omnis pair
```

Nu există autostart OS. Serviciile detached nu depind de terminal/checkout sau de scratch; build tools/QA nu sunt necesare utilizării instalării existente. Dacă restartul imediat refuză PORT_CONFLICT după Stop verificat, inspectează listenerul; TIME_WAIT propriu poate cere așteptare finitǎ (65s în probă), nu kill/adopție/port schimbat. La exit4/RECOVERY_REQUIRED/identitate neconformă oprește retry-urile și păstrează datele/receipturile pentru reconciliere. Nu edita manual journalul sau credențialele generate.

- Release/imagine: `/home/kali/.local/share/omnis-p1/r1/omnis/`.
- PGDATA/receipturi/IPC/forwarder: `/home/kali/.local/state/omnis-p1/r1/omnis/`.
- Loguri sanitizate de QA/readback: `/home/kali/.local/state/omnis-p1/r1/omnis/logs/p1-delivery/`.
- Config separat: `/home/kali/.config/omnis-p1/r1/omnis/`; nu pune secrete aici. Profilul P0 și Hermes personal nu sunt modificate.

## Continuarea P2 pregătită, neexecutată

Următoarea felie canonică este **restul B05/E-B05-03**, nu un nou Dashboard și nu B06 anticipat. B05.1 nominal/lease/Stop/drain rămâne CLOSED_SCOPED la `3c496e8`; [registrul B05](p2-b05.md) și plan §7/§19 păstrează canaries/restart/A→B→A, failure/watchdog/boot/epoch/pierderea autorității și inventarul efectiv pe pin ca restanțe. Probe native/OCI pe fixture nouă proprie, cu secrete numai sintetice, zero provider/model/ținte și readback exact; rezultatele simulate rămân SIMULATION.

După acceptarea perimetrului B05: B06a catalog/closure STATIC-PURE → B06b task/copil/lineage → B06c proiecții și B06m admission/budget inerte → P4a minim → numai cu acord cont/model/buget prima probă P2-live fără ținte. G02-inert/live rămân neînchise; această predare nu promovează G-MODEL/data/egress, nu implementează P2 și nu autorizează conturi sau inferență. Păstrează r1 instalat și folosește fixture-uri separate pentru viitoarele probe.
