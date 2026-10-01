# P0.4b / SL02 — comanda instalată start headless

**Acceptare actuală: APPROVED_SCOPED după [remedierea SC01/SC02](p04-start-remediation.md).** Cod final `b8217cb`, reviewuri distincte și make check + OCI secvențiale PASS, cu limitele 16 COVERED / 6 PARTIAL / 4 DEFERRED. [Auditul RED](p04-start-completeness-review.md), execuțiile de mai jos la `1dfa022` și eșecul intermediar rămân istorice, nu se rescriu. O DB din proba incertă intermediară rămâne RECOVERY_PENDING, locator în noul registru; ultimele probe au cleanup verificat/date păstrate. Nu este acceptare fără omisiuni și nu închide G00; urmează SL03.

## Contract înainte de cod

Bază verificată: `c4e8b4f67c3de715fca673f670e64ddb52a1bba1`, branch `p04-control-topology-wip`, tracked curat. Singurul untracked preexistent: `documents/Omnis_Notite_Originale.html`, protejat/neatins (SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`). Integrarea DB este închisă conform registrului său; PASS-ul de pe `bd06bcd` nu se transferă acestei felii.

**Obiectiv:** wheelul CLI curent, instalat separat și invocat din alt cwd, execută `omnis start --no-open`: preflight inert → lock/intenție proprie → PostgreSQL propriu → migrare dedicată autorizată numai pe schemă goală → API `python -I -m omnis.serve` + supervisor inert → forwarder host detached → verificare identitate/readiness HTTP/assets/control. Al doilea start reutilizează aceeași instanță sănătoasă fără migrare/restart; concurența nu produce duplicate. Status read-only verifică aceeași cale. `assessment_ready=false`, `browser_opened=false`, fără pairing automat.

**Perimetru:** modulele existente `cli/src/omnis_cli/{main,instance,control,status,release,compose,forwarder}.py`, modulele startup/health strict consumate de comandă și testele CLI/installed; `api/src/omnis/migrate.py` și environmentul Alembic numai pentru lock/identitate/no-upgrade, fără editarea migrărilor 0001–0004; health/API numai dacă identitatea observabilă cere un contract minimal; Compose/builder numai pentru consumatorul real. Make/gate, README-urile și planul/status/readiness afectate. Nu se copiază harnessul în produs, nu se importă checkout/teste din wheel.

**Păstrăm:** strict loader/checksums/receipt imagine, topologia Compose instalată `ops/compose.yaml` din sursa `ops/compose.control.yaml`, DB/API/supervisor pe bridge intern fără porturi Docker, UDS HTTP/control separate, UID/capability, InstanceControl/lease/fencing/barieră, forwarderul și limitele sale de trafic, fixture-ul backpressure corectat în `bd06bcd`, runnerul DB integrat și datele existente. Ownerul exec WIP nu este promovat. AGENTS rămâne protejat, designul acceptat nu se redeschide.

**Acceptare:** RED→GREEN pe comportamente; probe reale cu wheel/release/imagine curente, XDG nou sub scratch și PostgreSQL 18.6; preflight/release/port/paths/identity greșite refuzate; deadline total HTTP și startup; shutdown incomplet nu redeschide admiterea; cleanup parțial încearcă toate resursele proprii, drenează procesele înainte DB, păstrează date/diagnostic și raportează UNCERTAIN dacă readbackul lipsește. Proba instalată execută comanda, nu `run_probe`. Review independent read-only, remedieri reproduse, gate `make check` pe codul nou și probă Docker opt-in distinctă. Toate rezultatele de mai jos vor numi revizia/comanda/exit/limita, fără loguri brute sau secrete.

**Non-goals:** SL03 pair/open și SL04 stop/recovery operațional, assessment, Hermes/runtime/Brain/proxy/executori, schema pentest, conturi/provider/OAuth/Jev/ținte. Fără stuburi pentru comenzi nelivrate, autostart OS, implicit pull/build/install/update, firewall/daemon/toolchain global, push/deploy. G00/L01–L05/L08 complete și CI remote rămân deschise/NOT-RUN.

**Efecte externe / rollback:** înaintea probelor există două containere străine observate (`8143ec40ecab`, `dabab333533b`); nu le adoptăm/oprim. Pregătim explicit artefactele din pinuri în scratch; fiecare probă are root privat/proiect/intenție înainte de creare. Numai resursele create și atestate ale încercării sunt oprite/eliminate, fără `down -v`/prune/ștergere PGDATA. Datele/diagnosticul se păstrează privat; o intenție incertă blochează retryul automat. Revert Git pe commitul coerent inversează numai codul; recuperarea externă necesită reatestarea daemonului/CID/mounturilor/IPC înaintea opririi exacte, nu kill după port sau PID stale.

## Stare inițială

Toolchain disponibil și verificat: API/CLI Python 3.13.15, uv 0.12.19, Node 24.21.0/npm 11.19.0 din căile scratch documentate; Docker 27.5.1+dfsg4 / Compose 2.32.4-3. Pythonul documentelor este 3.13.12. Nicio probă de startup produs executată încă la acest checkpoint inițial; această secțiune fixează contractul, nu verdictul livrării.

## Implementare și probe înaintea gate-ului final

Codul migrării este în `26347c0`; calea verticală de produs, inclusiv status/readiness și cleanupul propriei încercări, este în `e664c8f`; proba opt-in este în `ae40cdd`. Rezultatele de mai jos descriu checkpointurile din sesiune, nu transferă PASS-ul `bd06bcd` și nu închid G00.

### RED, erori reale și remedieri

- Wheelul baseline instalat în `/home/kali/.hermes/cache/scratch/s2-8vdw8gbw/venv`, din `cwd/` extern, a refuzat `start --no-open --json` cu exit 2: comandă necunoscută. Releaseul și imaginea au fost pregătite explicit înaintea probei; niciun serviciu nu a fost pornit de acel RED.
- Primele încercări de produs au expus valorile implicite reale Compose (`ipam: {}`, `entrypoint: null`), reprezentarea `HostConfig.Binds` a bindului deja verificat complet prin `Mounts`, apoi faptul că `compose create` nu acceptă `--no-deps`. Au fost corectate punctual, păstrând atestarea exactă și adăugând `--no-recreate`, fără schimbarea topologiei. Într-o încercare a rămas un container doar creat; CID-ul a fost recuperat după readback exact, nu printr-un `down` global. Datele nu au fost șterse pentru GREEN.
- Prima comandă instalată READY și primul reuse au trecut pe rootul `s2-n584z_iv`, origin implicit `127.0.0.1:8765`; aceeași instanță/containere/timestamps/generație/epoch după ieșirea launcherului. Proba ad-hoc `hermes-verify-*` a confirmat acestea, apoi a dat RED pentru vechiul status `HTTP_UNVERIFIED`. Scriptul ad-hoc a fost eliminat; nu este suita de acceptare finală.
- Migrarea startup a avut RED: un cluster ID greșit era ignorat și se executa DDL. `--initialize` verifică acum pe aceeași conexiune `system_identifier` și DB, apoi advisory lock tranzacțional și absența obiectelor existente. Review-ul F1 a găsit large objects/collations omise; patru cazuri non-table au dat **4 failed / 13 passed**, apoi **17 PASS** după remediu. Upgrade-ul explicit normal și migrațiile 0001–0004 sunt păstrate. Ultima probă țintită: runner `--target test-migrations`, root `db-863dcfa9a6824b3b`, exit 0; readback container/rețea/socket absente, date păstrate. Lint/format/mypy API PASS.
- Review-urile produsului au identificat și închis R1–R7: nonce/atestare compusă; lock comun al proiectului pentru state roots diferite; păstrarea DB sub incertitudine; handofful handle-ului forwarder la eșec; legarea peer-ului API de namespace/cgroup; deadline înainte de spawn; output Docker limitat incremental; jurnal de cleanup care nu reduce exit 4 la exit 3. R2 a necesitat încă o regresie: flagurile apărute în remove non-DB se recitesc chiar înaintea DB. Ambele subcazuri au fost RED, apoi GREEN și PASS independent cu mutantul vechi respins.
- Proba inițială de SIGTERM la `MIGRATING` a observat corect `UNCERTAIN`, dar observatorul făcea ulterior rescue DB fără să fi închis incertitudinea daemonului. **Acel exit 0 istoric al probei nu este acceptarea cleanupului de întrerupere.** Review-ul B1–B4 a cerut refuzul rescue-ului incert, verificarea `FAILED_CLEANED` înainte de rescue, snapshoturi de restart, locator durabil înainte de launch/finally și refuzul Make flags nesigure. Predicatele/motivele au fost reproduse, nu doar reformulate.
- Observatorul verifică acum SIGTERM în etapa de produs `VERIFYING`, după operațiile Docker mutante, distinctă de `FORWARDING`; cere exact exit 3 / `FAILED_CLEANED` / `cleanup=[]` și absența resurselor **din cleanupul produsului**, înainte de orice rescue. Timeoutul retry-ului a avut un RED separat care autoriza rescue; incertitudinea este acum setată înainte de fiecare invocare și eliberată numai după răspuns/readback, cu locator păstrat.
- Această probă mai strictă a găsit defectul real de IPC: pe `s2i-uaey15wf`, toate containerele/rețeaua erau absente, dar `control.sock` și capul privat rămăseseră după întreruperea supervisorului în startup. CLI a raportat corect exit 4; proba a eșuat și a păstrat locatorul. Remediul de produs reclamă numai IPC-ul acestui scope nou după teardown reconciliat, sub lockul serviciului, cu inode/UID/mode verificate și `ECONNREFUSED`; nu șterge lockuri și nu semnalizează PID-uri din fișiere. Testul real dead/live UDS a fost RED→GREEN; re-review IPC PASS bounded. Recuperarea separată a celor două fișiere vechi a confirmat **2 → 0**, cu date păstrate, în `s2i-uaey15wf/ipc-recovery.json`; jurnalul istoric UNCERTAIN nu a fost rescris drept READY.

### Proba instalată reproductibilă

Comanda opt-in, cu pinurile disponibile explicit:

```sh
export PATH="/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin:/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools:/usr/bin:/bin"
make check-installed-start UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
```

Pregătește separat wheeluri/release/imagine din lockuri și apoi execută **console scriptul instalat**, nu `run_probe`. Verificările obișnuite scot flags OCI/start din mediu; `-n/-t/-i/-q` pe ținta nouă sunt refuzate înaintea rețetelor. Proba istorică `check-installed-control` rămâne separată.

Ultimul checkpoint instalat înainte de commitul probei: **exit 0**, log `/home/kali/.hermes/cache/scratch/sl02-proof-final-rerun.log`: **67 teste CLI wheel**, **37 release/observer checks**, apoi **1 integrare OCI instalată reală**. Proiect `omnis-local-3c76429246e14e21ac9aeba1554f9e3f`, imagine `sha256:9a419635684d561320ee52c246a9b622bf6291a1fd61eac2b441d52595af062b`, instance `b58319fe-2c21-4595-9cf2-3bcdda4f3ed2`. Roots păstrate: `s2-537w8q46/s/omnis` și `s2i-yl1oon1s/s/omnis`; receipturi private `probe-receipt.json` leagă proiectul, data home, state root și rezultatele probei/cleanupului separat. SIGTERM: `FAILED_CLEANED`, exit 3, apoi retry exit 4 fără efecte. Tagul imaginii de test este eliminat după readback. Rerularea finală pe cod comis este consemnată separat mai jos.

Acoperire efectivă:

| Criteriu | Canal de dovadă și limită |
|---|---|
| Wheel curent / cwd extern / prerechizite explicite | CLI instalat în venv separat, bundle și image receipt reale; `.env`, Compose/config și executabil Docker capcană în cwd |
| Start / HTTP / assets / control / status | DB PostgreSQL 18.6, job dedicat din imagine, API `omnis.serve`, supervisor și forwarder reale; toate asseturile comparate; status fără schimbarea receipturilor |
| Reuse / concurență / supraviețuirea launcherului | Două procese CLI de start, un singur set DB/API/supervisor, un singur instance ID; timestamps/restart count/epoch/generație neschimbate la reuse |
| Refuzuri preflight / identitate | Release corupt, daemon/imagine nepotrivite, cale relativă, port listener și bound-only, metadata contradictorie și intenție stale injectată; fără adopție/restart |
| Schema / migrare / barieră | Refuz real al schemei incompatibile, fără remigrare; lock DB/cluster ID/non-table data în testele migratorului; shutdown incomplet nu redeschide admiterea |
| Readiness negativă | Socketuri TCP/UDS reale pentru trickle/deadline total/limite/redirect; API-ready 200 cu dashboard indisponibil și asset corupt testate la consumatorul HTTP (IPC substituit doar în aceste unit teste) |
| Erori parțiale și cleanup | SIGTERM instalat în VERIFYING; bind race real al forwarderului; dead/live IPC; fault-uri înguste pentru daemon/handle/jurnal/remove și locator, fără mock peste calea pozitivă de produs |
| Inert și fără secrete | `assessment_ready=false`, `browser_opened=false`, pairing issuance 0, un singur OPEN de instanță; sentinel local provider/proxy necontactat, env allowlisted, output/record/log fără secrete sintetice. Nu este monitorizare exhaustivă de syscalls/egress |
| Date și resurse | Stop/remove numai pe ownership verificat; CID/rețea/listener/IPC readback; binduri păstrate, fără `down -v` sau reset. Nu este backup/restore ori stop/start operațional |

### Review independent — închis punctual înaintea gate-ului final

Rapoartele complete sunt în scratch; deciziile durabile sunt rezumate aici și în commituri, fără transferul probelor simulate către runtime:

- `sl02-migration-fix-review.md`: F1 CLOSED; lock și identitate pe aceeași conexiune păstrate. Observațiile neblocante despre readbackul obiectelor și ordinea statement-urilor rămân declarate.
- `sl02-fixes-review.md` + `sl02-r2-final-review.md`: R1–R7 și lock cross-state CLOSED; R2 final a respins independent mutantul vechi în ambele subcazuri.
- `sl02-ipc-fix-review.md`: PASS pentru cleanup fresh după teardown reconciliat, lockuri existente și peer inactiv; fără acceptare a stopului operațional sau ownerului WIP. Linkcount 1 este verificat pentru lock/cap, nu declarat ca invariant general pentru socketuri.
- `sl02-proof-fix-review.md` + `sl02-b1-final-review.md`: B1–B4 CLOSED. Ultimul re-review a executat independent numai testul unitar de timeout/retry (fakes și tempdir), nu gate-ul OCI; acesta este executat separat de părinte.

### Gate comun, documente și conservare

Prima încercare `make check` pe codul nou a fost întreruptă de limita toolului foreground la 420 s: runnerul a raportat **exit 130**, nu PASS. Au trecut 54 docs, 35 development și 218 API; migrațiile au fost întrerupte. Root `db-cef8998b562f43cd`, proiect `omnis-p01-fa488bcc98884a22ab4f08bcb33f2423`; receipt/family cleanup și readback container/rețea/socket absente, date păstrate. Nu este timeoutul intern de 3600 s al gate-ului și nu este o regresie dedusă din heartbeat. Execuția finală folosește un proces urmărit, nu repetarea unor suite parțiale ca substitut.

Documente: renderer și `--check`, **54 teste PASS**, **116 controale Chromium PASS**, zero erori JS/cereri externe. O corecție de text a restaurat markerii expliciți P0.1/P0.2 ceruți de testul documentar, fără slăbirea lui. Inspecție vizuală la 1440px a planului §19.2 și arhitecturii §4.1: text lizibil, fără clipping/redesign. Capturi private `sl02-final-plan.png`, `sl02-final-architecture.png` sub scratch. AGENTS și prototipul/designul nu au fost editate.

Readback separat al primelor probe: `/home/kali/.hermes/cache/scratch/sl02-resource-readback.json` confirmă nouă roots/probe fără servicii proprii active și eliminarea celor șase taguri create de pregătirea manuală; datele/receipturile private rămân. Probele suplimentare au locator și readback proprii. Scratch este diagnostic disposable, **nu backup permanent**. Containerele străine de la baseline nu au fost adoptate/oprite.

**Limite încă explicite:** CI remote NOT-RUN, LAN/IPv6/rutare directă spre containere NOT-RUN, SIGKILL în toate etapele și recovery operațional/persistență stop-start sunt SL04, pairing TTY/open/browser sunt SL03. Intenția stale este fault-injected, nu o probă exhaustivă de crash. Predicatele DB-goală nu sunt o certificare a fiecărui catalog PostgreSQL posibil; testele de identity verifică refuzul/readbackul, nu instrumentează toate statement-urile anterioare unui rollback. Actorul malițios same-UID/root rămâne în afara garanției. G00 și L01–L05/L08 complete nu sunt declarate închise.

## Verdict final pe codul comis

**SL02 headless verificat local.** Revizie testată: `1dfa022f44e9f3e6154a91459a7b3801ded25db5`. Checkoutul tracked a fost curat înainte și după ambele gate-uri; singurul untracked a rămas HTML-ul original protejat. Nu au existat editări de cod/config/test în timpul execuțiilor. Commitul care adaugă această secțiune modifică numai registrul, nu codul verificat.

### Gate canonic: PASS

Cu același PATH pin-uit documentat mai sus:

```sh
make check UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
```

Proces urmărit `proc_446adf4f744c`: **exit 0**, confirmat prin readbackul procesului, nu din heartbeat. Log exterior `sl02-final-check.log`; log/manifest/receipt private în `/home/kali/.hermes/cache/scratch/db-47e0459f5e5b48e1/`.

| Componentă executată | Rezultat în această rulare |
|---|---|
| Documentație | 54 teste PASS; HTML-uri sincronizate |
| Development | 35 teste PASS; anti-slop PASS |
| API | 218 teste PASS |
| Migrări / wheel API instalat | 17 teste PASS |
| Web | 6 tooling + 20 unit + 7 E2E cu backend real PASS |
| CLI | 67 sursă + 67 wheel instalat + 1 integrare CLI/DB PASS |
| Release / observer | 37 teste PASS |
| Lock / audit / lint / format / mypy / TypeScript / contracts / build | PASS |

Fixture canonic: proiect `omnis-p01-5035baa8d3b34748aa9c2dd6792e1e37`, CID `8892443fc0774eb9fa106a84e75d24e49d801a3573ba107e22796967ad307557`, PostgreSQL 18.6, system ID `7691403587275681822`. Receipt exact: `{schema_version:1,code:0,family_drained:true}`. Runnerul și readbackul separat au confirmat CID/rețele/socket absente și `PG_VERSION=18` păstrat. `make test` este aliasul aceleiași căi, nu o a doua execuție raportată.

### Comanda instalată / OCI opt-in: PASS separat

După încheierea gate-ului canonic, fără concurență pe venvuri/artefacte:

```sh
make check-installed-start UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
```

**Exit 0** pe aceeași revizie `1dfa022`; log `/home/kali/.hermes/cache/scratch/sl02-committed-installed.log`. Prerechizite executate: 67 teste CLI wheel și 37 release/observer; apoi integrarea opt-in reală a comenzii. Proiect `omnis-local-338b6c051c26415bbc2fb6d629fab7e9`, imagine instalată `sha256:9ab6840ed5afb8a797b178983e6b8c4f4338cf7a9370461ce5642e0352d198a2`.

- Starturile concurente, reuse și status au verificat instanța `a0ddd150-4507-4028-b66b-a51d989207f1`; root păstrat `/home/kali/.hermes/cache/scratch/s2-u5t36pl1/s/omnis`.
- Încercarea separată de SIGTERM în VERIFYING a produs `FAILED_CLEANED`, exit 3, pe instanța `a14e7d26-9040-4aad-be84-a5264b03a19b`; retry-ul a refuzat cu exit 4 fără schimbarea journalului/resurselor. Root păstrat `/home/kali/.hermes/cache/scratch/s2i-p5xt3bpm/s/omnis`.
- Ambele receipturi au `probe=PASS`, `cleanup=VERIFIED`. Readbackul independent final din `sl02-final-readback.json` confirmă daemonul exact, absența tuturor CID-urilor înregistrate și a inventarului proiectului, rețelei, tagului imaginii, IPC-urilor și forwarderului/listenerului propriu. `postgres/18` și datele rămân; un jurnal READY păstrat după teardownul probei este istoric, nu autoritate că serviciile încă rulează.
- Nu există resurse active ale acestor probe care să necesite recuperare. IPC-ul rezidual al încercării eșuate anterioare a fost recuperat separat și documentat mai sus. Receipturile/DB-urile disposable nu sunt instalații operaționale de reutilizat automat.

**Conservare și Git:** `omnis.serve`, forwarderul și fixture-ul de backpressure, runnerul DB, `api/src/omnis/core/db.py`, migrațiile 0001–0004 și AGENTS au rămas neschimbate față de baseline în perimetrele cerute. HTML-ul original are în continuare SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`, untracked/nestaged. Commituri locale separate: `a0f5687` statusuri DB, `44537e4` contract, `26347c0` migrare, `e664c8f` comandă/readiness/cleanup, `ae40cdd` probă opt-in, `ad74946` procedură ops, `1dfa022` utilizare/status/readers. Fără push/deploy.

Următoarea felie este **SL03 / P0.4c / B01f pair/open**. Acest verdict nu închide SL03/SL04, L01–L05/L08 integral, G00 sau CI remote și nu schimbă `assessment_ready=false`.
