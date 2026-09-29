# P0.4 — adjudecarea buclei de verificare

**Snapshot local:** `p04-control-topology-wip` la `f4c85e7`, față de `main` la `c4cb784`: 34 de commituri, 6.595 inserări/62 ștergeri în 33 de fișiere. Dintre inserări, 5.660 sunt în teste/probe, 741 în runtime/ops și 194 în documente/configurație/skill-uri (`git diff main...HEAD --numstat`). Aceste numere descriu munca, nu gradul de acceptare. Nu există push, CI remote sau G00 închis.

## Cauză și decizie

- Proba instalată de topologie pornește Compose și forwarderul direct, nu printr-o comandă de produs (`cli/integration/control_topology.py`). CLI-ul expune `status`, `install`, `install-image`, dar nu `start/pair/open/stop` (`cli/src/omnis_cli/main.py`). Imaginea instalată pornește încă `omnis.serve` (`ops/Dockerfile.control:14`); ownerul exec nou din `301b918` este numai WIP. Alte fault-injection tests nu pot demonstra L01–L05-control/L08-core în locul launcherului.
- `make check-api` verifică lock/audit/compile/lint/type, nu rulează `test-api` (`Makefile:22–41`). Cele 28 de teste focalizate au trecut pe snapshotul de cod anterior commiturilor procedurale, dar sunt probe limitate. `make test`/`make check` sunt **NOT-RUN/BLOCKED pe HEAD curent**: lipsesc variabilele proiectului PostgreSQL dedicat și `ops/compose.test.yaml:12` folosește `network_mode: host`, cu identitatea volumului, namespace-ul/egressul și listenerul încă neatestate suficient pentru gate-ul sigur. Exit 0 al unui `make check` WIP anterior lui `301b918` nu se transferă la HEAD-ul actual. Nu revenim la fixture-ul și mai riscant cu port Docker publicat.
- Hermes are `agent.verify_on_stop=true`, fără override de mediu în această sesiune. Implementarea instalată (`agent/verification_stop.py:158–225`, `agent/coding_context.py:466–491`, `agent/verification_evidence.py:424–452`) poate cere de două ori pe tur o verificare canonică după edit; recunoaște `make test`/`make check`, nu `make check-api` sau pytest focalizat. Este un nudge bounded, nu dovada că testele focalizate au eșuat. Greșeala operațională a fost să repetăm probele parțiale și răspunsurile de status, apoi să extindem oracolul de test în locul unei comenzi de produs.
- **Înghețăm extinderea harnessului de owner.** `f4c85e7` păstrează trei fișiere de teste pe ramura WIP, nu le declară acceptate: ultimul review complet al rescue-ului a fost oprit pentru re-scope. Moartea supervisorului înainte de publicarea identității descendenților rămâne UNCERTAIN fără un scope de procese gestionat. `301b918` rămâne WIP cu erori `waitpid`/gate-write/reap și teardown nesigur în testele legacy; nu schimbăm CMD-ul imaginii până la remediere/probă instalată. Păstrăm separat calea `omnis.serve` deja instalată, fără a o confunda cu noul owner.

## Dispoziția commiturilor ramurii (toate cele 34 din snapshot)

| Grup / commituri | Dispoziție |
|---|---|
| Checkpoint topologie: `84542d2`, `0cd9de1`, `171c849` | Istoric WIP, nu launcher. |
| Transport/topologie: `faba7ff`, `689be45`, `ce4a25f`, `a50d7ec`, `19b614b`, `8cccb9f`, `f30032b` | Păstrăm transportul UDS/forwarder și probele instalate, fără credit L01–L05. |
| Owner instalat vechi: `8e46c0d`, `7201f3b`, `2369eac`, `1b0e62e` | Păstrăm remedierile/istoricul; nu deducem că ownerul exec nou este instalat. |
| Corecții ale probei: `1636364`, `6a57e57`, `4d398ec`, `c655fe4`, `84b2d8a`, `94631b7` | Dovezi parțiale; nu reluăm repetat `check-installed-control` ca substitut pentru `omnis start`. |
| DB disposable: `dc54797`, `d8f79df`, `dad8ad4` | Nu facem blanket revert la port Docker publicat; refacem/atestăm fixture-ul înainte de gate. |
| Lecții ops: `fa680df`, `ed8e188`, `93157dc`, `3b8ce31`, `17c0c62` | Proceduri, nu gate-uri de produs. |
| Status parțial: `be77b94`, `57df95f` | Istoric versionat, nu rezultat pe HEAD-ul curent. |
| Worker/owner exec: `6883d1e`, `301b918` | WIP reversibil; blocăm promovarea în OCI până la controlul erorilor și teardownului. |
| Oprirea buclei: `1ebadf7`, `f4c85e7` | Skill-uri ajustate și harness înghețat ca checkpoint WIP, fără acceptare G00. |

## Calea critică următoare

1. **Prerechizitul gate-ului:** proiect PostgreSQL disposable cu ownership/izolare dovedite, fără `network_mode: host` neattestat sau port Docker publicat. Revizuim planul de backup/teardown care păstrează volumul înainte de DDL; numai după probe pozitive și negative rulăm `make check` pe checkout curat. Dacă nu este posibil, marcăm BLOCKED, nu PASS.
2. **Produsul, nu încă un oracol:** prima comandă instalată `omnis start --no-open` din afara checkoutului, cu release/instance identity, lock, port străin, migrare și readiness HTTP/status; folosim calea instalată `omnis.serve` până când înlocuitorul owner exec are probele necesare. Adăugăm un target de test al launcherului *doar când există codul*, cu readback exact al resurselor proprii. Acest increment avansează L01/L02/L03/L04 parțial, nu G00.
3. **Pairing și stop durabil:** `omnis pair` TTY-only, `open` pe origin verificat și `omnis stop` cu barieră/admitere/generație în DB, crash/restart, concurență și date păstrate. Abia pe artifactul instalat, după remedierea tuturor criteriilor L01–L05-control/L08-core și negativele LAN/IPv6, decidem G00. Ownerul exec WIP se promovează separat numai dacă dovada shutdownului pe entrypointul ales o cere; nu îl folosim pentru a amâna launcherul la infinit.

**Handoff:** `make check-api` exit 0 și 28/28 teste owner/worker/harness focalizate sunt probe locale înguste înaintea acestei note; `make check`/`make test` pe HEAD actual, instalarea noului owner, CI remote și G00 sunt NOT-RUN/BLOCKED. Nu am dezactivat `agent.verify_on_stop`, nu am slăbit Makefile și nu am schimbat date Docker/DB. `AGENTS.md` a rămas nemodificat: aprobarea interactivă pentru editarea lui a expirat; nu ocolim protecția. Regulile anti-buclă sunt în skill-urile versionate de delivery și review (`1ebadf7`).
