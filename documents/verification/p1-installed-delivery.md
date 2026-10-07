# P1 — livrare locală persistentă pentru operator

## Contract autorizat și stare

**IN_PROGRESS, nu PASS.** Bază produs `682449be2c5afcd8fee8b5c93d7b3966b714ac3b`; P1/B02–B04/G01 era deja acceptat pentru drafturi inerte. Operatorul a autorizat acum instalarea separată, comanda `omnis`, QA Dashboard/Setup pe build/API/PostgreSQL instalate, inspectarea logurilor și remedierea blocantelor, apoi pregătirea P2. Această felie nu implementează P2 și nu activează assessment/model/provider/ținte.

Arhitectura §4.1–4.4 și planul §6 decid comportamentul; nu este un plan de produs concurent. Contractul arhitectului read-only susține schema nouă `0008_engagement_edit` prin migratorul existent `--initialize` → Alembic head. Nu este necesar scaffold nou. Releaseul păstrează versiunea `0.1.0`, deci un root nou evită coliziunea de bytes cu P0. Nu facem upgrade/adopție/migrare a instalării vechi.

## Efecte și proprietate

- Launcher nou, numai dacă absent: `/home/kali/.local/bin/omnis`, wrapper regular executabil către CLI wheel în `/home/kali/.local/share/omnis-p1/cli-venv`.
- XDG_DATA_HOME `/home/kali/.local/share/omnis-p1`; XDG_STATE_HOME `/home/kali/.local/state/omnis-p1`; XDG_CONFIG_HOME `/home/kali/.config/omnis-p1`. Wrapperul elimină XDG_RUNTIME_DIR numai pentru invocarea lui; IPC folosește fallbackul privat din state. Niciun export global sau profil shell/Hermes modificat.
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
