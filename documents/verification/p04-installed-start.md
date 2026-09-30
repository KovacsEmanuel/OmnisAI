# P0.4b / SL02 — comanda instalată start headless

## Contract înainte de cod

Bază verificată: `c4e8b4f67c3de715fca673f670e64ddb52a1bba1`, branch `p04-control-topology-wip`, tracked curat. Singurul untracked preexistent: `documents/Omnis_Notite_Originale.html`, protejat/neatins (SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`). Integrarea DB este închisă conform registrului său; PASS-ul de pe `bd06bcd` nu se transferă acestei felii.

**Obiectiv:** wheelul CLI curent, instalat separat și invocat din alt cwd, execută `omnis start --no-open`: preflight inert → lock/intenție proprie → PostgreSQL propriu → migrare dedicată autorizată numai pe schemă goală → API `python -I -m omnis.serve` + supervisor inert → forwarder host detached → verificare identitate/readiness HTTP/assets/control. Al doilea start reutilizează aceeași instanță sănătoasă fără migrare/restart; concurența nu produce duplicate. Status read-only verifică aceeași cale. `assessment_ready=false`, `browser_opened=false`, fără pairing automat.

**Perimetru:** modulele existente `cli/src/omnis_cli/{main,instance,control,status,release,compose,forwarder}.py`, modulele startup/health strict consumate de comandă și testele CLI/installed; `api/src/omnis/migrate.py` și environmentul Alembic numai pentru lock/identitate/no-upgrade, fără editarea migrărilor 0001–0004; health/API numai dacă identitatea observabilă cere un contract minimal; Compose/builder numai pentru consumatorul real. Make/gate, README-urile și planul/status/readiness afectate. Nu se copiază harnessul în produs, nu se importă checkout/teste din wheel.

**Păstrăm:** strict loader/checksums/receipt imagine, topologia Compose instalată `ops/compose.yaml` din sursa `ops/compose.control.yaml`, DB/API/supervisor pe bridge intern fără porturi Docker, UDS HTTP/control separate, UID/capability, InstanceControl/lease/fencing/barieră, forwarderul și limitele sale de trafic, fixture-ul backpressure corectat în `bd06bcd`, runnerul DB integrat și datele existente. Ownerul exec WIP nu este promovat. AGENTS rămâne protejat, designul acceptat nu se redeschide.

**Acceptare:** RED→GREEN pe comportamente; probe reale cu wheel/release/imagine curente, XDG nou sub scratch și PostgreSQL 18.6; preflight/release/port/paths/identity greșite refuzate; deadline total HTTP și startup; shutdown incomplet nu redeschide admiterea; cleanup parțial încearcă toate resursele proprii, drenează procesele înainte DB, păstrează date/diagnostic și raportează UNCERTAIN dacă readbackul lipsește. Proba instalată execută comanda, nu `run_probe`. Review independent read-only, remedieri reproduse, gate `make check` pe codul nou și probă Docker opt-in distinctă. Toate rezultatele de mai jos vor numi revizia/comanda/exit/limita, fără loguri brute sau secrete.

**Non-goals:** SL03 pair/open și SL04 stop/recovery operațional, assessment, Hermes/runtime/Brain/proxy/executori, schema pentest, conturi/provider/OAuth/Jev/ținte. Fără stuburi pentru comenzi nelivrate, autostart OS, implicit pull/build/install/update, firewall/daemon/toolchain global, push/deploy. G00/L01–L05/L08 complete și CI remote rămân deschise/NOT-RUN.

**Efecte externe / rollback:** înaintea probelor există două containere străine observate (`8143ec40ecab`, `dabab333533b`); nu le adoptăm/oprim. Pregătim explicit artefactele din pinuri în scratch; fiecare probă are root privat/proiect/intenție înainte de creare. Numai resursele create și atestate ale încercării sunt oprite/eliminate, fără `down -v`/prune/ștergere PGDATA. Datele/diagnosticul se păstrează privat; o intenție incertă blochează retryul automat. Revert Git pe commitul coerent inversează numai codul; recuperarea externă necesită reatestarea daemonului/CID/mounturilor/IPC înaintea opririi exacte, nu kill după port sau PID stale.

## Stare inițială

Toolchain disponibil și verificat: API/CLI Python 3.13.15, uv 0.12.19, Node 24.21.0/npm 11.19.0 din căile scratch documentate; Docker 27.5.1+dfsg4 / Compose 2.32.4-3. Pythonul documentelor este 3.13.12. Nicio probă de startup produs executată încă; această notă fixează contractul, nu verdictul livrării.
