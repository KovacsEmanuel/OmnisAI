# P0.2 — control local, probe și limite

**Stare: IMPLEMENTED_LOCAL / re-review final în curs.** Bază `6baa57f`; implementare și corecții până la `5be62b4`, proceduri până la `e994f19`. Rezultatele de mai jos sunt ale proceselor/testelor executate de părinte, nu deduse din review. Contract: [plan §5/§19](../Omnis_Implementation_Plan.md), [arhitectură §4/§6/§12](../Omnis_MVP_Architecture.md), [perimetrul și deciziile P0.2](p02-contract.md). Nu închide G00.

## Comparativ cu planul și arhitectura

| Criteriu P0.2 | Implementare și probă locală | Limită |
|---|---|---|
| B01d: Host/Origin/session/CSRF | `security/host_origin.py`, `sessions.py`, `routes.py`; `/api/session`, `/api/logout`, `/api/instance`. Allow/deny pe același ASGI și TCP real: Origin absent/străin/null/duplicat, Host fals/duplicat, CSRF străin, cookie ambiguu, body bounded și erori fără input reflectat. | HTTP loopback asumat; nu TLS, UI sau SSE. |
| L05-control: pairing one-use, expirare, limitare | PostgreSQL serializează consumul/crearea sesiunii și cele 5 încercări/minut. Expiry verificată cu timpul DB după lock; sesiune 12h și logout persistent. `0004_pairing_receipts` fixează emiterea/digestul/TTL; retry după consum, expirare sau înlocuire nu reactivează codul. | Emitentul CLI/afișarea TTY aparțin P0.4. Codurile sunt sintetice; niciun cont personal. |
| Control Unix autentificat, bounded | `transport/local_control.py`: kernel peer UID + capability per boot, director privat/canonic, lock și fișiere 0600, comenzi tipizate. Refuz UID/token vechi/greșit, payload necunoscut, frame mare/duplicat și path nesigur. Anularea startupului închide listenerul și permite restart. | Mappingul UID și mounturile instalării containerizate rămân P0.4/P2. Same-UID/root malițios exclus. |
| A03/§6: supervisor separat, unic, fenced | `python -I -m omnis.supervisor`; al doilea proces este refuzat, lease expirat nu poate admite/reînnoi/publica quiescență. Procesul iese bounded la blocarea DB. Restart API real păstrează sesiunea și epochul supervisorului. | Nu există scheduler de assessment, Hermes sau adaptoare de efecte. |
| B01f/L08-core: barieră tranzacțională | `modules/instance/service.py`: aceeași blocare DB pentru admitere, shutdown și receipts UUID/generație. Marker inert în tranzacția verificată; Stop înainte refuză, Stop concurent așteaptă commitul, lease expirat anulează scrierea. | Markerul este creat numai de harness. Nu este task/scanare simulată de produs. |
| Restart/crash/ACK | Procese reale SIGKILL înainte de shutdown, după commit, după quiescență și răspuns pierdut; readback persistent, retry idempotent, capability nouă, fără autoresume. OPEN cere finalizare inertă, epoch nou și comandă explicită. | FINALIZE/quiescența nu dovedesc containere oprite. P0.4 verifică separat identity/receipt; P2/P3 extind predicatul cu adaptoarele reale. |
| Migrări și artifact instalat | Empty DB → `0004`; upgrade din `0001`, `0002`, `0003` păstrează identitatea/bariera și sesiunile existente, invalidează pairing pending fără receipt. Wheel instalat cu dependențe hash-locked rulează migrator, supervisor și Uvicorn din afara checkoutului, prin Unix IPC și listener loopback rezervat. | Niciun upgrade pe date personale/reale și nici restore certificat. |
| L03: startup/status/health inert | Profil fără credentiale/provider/runtime. Harnessul wheel are guard Python pentru connect/DNS/child process și control negativ înainte de I/O; fluxul permis contactează numai DB deținută. Domain import independent de FastAPI/ORM/Hermes. | Guard Python ≠ sandbox OS sau G-NET. Nu certifică integrările inexistente. |

## Verificare executată după corecții

`make check UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv` — **exit 0**, după setup-ul izolat din `api/README.md`, pe Python **3.13.15**, uv **0.12.19**, PostgreSQL **18.6** digest-pinned, Node **24.21.0** / npm **11.19.0**:

- 28 teste documentare, 11 development și 4 cazuri reale Oxlint;
- **85 teste API/control**, inclusiv fixture ownership, sessions, HTTP, concurență, IPC și procese;
- **10 teste migrare/livrare**, inclusiv wheel instalat și cele trei revizii precedente;
- lock/dependințe compatibile, audit OSV fără vulnerabilități cunoscute în 31 de pachete; build și import wheel, compileall, renderer fără drift și `git diff --check` trecute.

Auditul de dependențe nu garantează absența vulnerabilităților. Compileall este verificare de sintaxă, nu typecheck Python complet. Niciun build/typecheck React sau test browser de produs nu este pretins: `web/` nu există încă. CI remote este **NOT-RUN** (nu s-a cerut push).

## Review și remedieri

Auditul inițial a definit matricea înainte de implementare, fără a certifica runtime-ul. Review-ul de securitate pe `04d6fad` a găsit trei probleme medii, toate reproduse de părinte înainte de corecție:

1. **Listener rămas la anularea startupului** — RED cu socket real; `0943e5d` memorează serverul/inode-ul și aplică mode înainte de await-ul de serving; 5 teste IPC GREEN.
2. **Replay care reactiva codul one-use** — trei RED pe PostgreSQL (consumat/înlocuit/expirat); `2e7726f` adaugă issuance UUID + receipt imuabil și conflicte. 35 teste țintite GREEN, inclusiv replay IPC/HTTP din wheel.
3. **Lipsă deadline după middleware** — RED pentru pairing/logout și calea soră status; `5be62b4` aplică timeout DB de 3 secunde și răspuns 503 sanitizat. Fault injection după scriere PostgreSQL confirmă rollback/no cookie; 13 teste HTTP GREEN. Proba este un stall injectat, nu o simulare completă a tuturor blackhole-urilor de rețea.

Un control suplimentar refuză ancestorii IPC nesiguri (`6751d3a`); prima variantă prea strictă refuza și un cache group-writable protejat deja de directoare owner-only, iar inspecția permisiunilor a ghidat corecția. Re-review-ul celor trei mecanisme și comparația finală de conformitate sunt încă în curs la această versiune a notei.

## Eșecuri de mediu, cleanup și porți deschise

O rerulare a gate-ului a eșuat când variabilele efemere de test nu mai existau: întâi pinul UV gol, apoi `OMNIS_TEST_DATABASE_URL` absent. Aceste rulări sunt **FAIL/BLOCKED**, nu PASS și nu motiv de relaxare a fixture-urilor. Setupul/testele/cleanupul au fost reunite într-un harness scratch, apoi comanda canonică a fost rerulată direct cu mediul refăcut și a trecut.

Proiectele Compose au nume unice `omnis-p01-p02-*`; verificarea finală de mai sus a folosit `omnis-p01-p02-b12f5c9d4629ac2c`. Cleanupul oprește numai proiectul deținut, fără `down -v`; volumele sintetice sunt păstrate. Nu s-au adoptat DB, `.env` sau credentiale personale. Git revert nu restaurează schema/datele; pe date reale este obligatoriu backup/restore explicit.

**Rămân în afara acestei subfaze:** P0.3 bootstrap web, P0.4 launcher/manifest/topologie și dovada containerelor oprite; G00 complet, SSE/B08, Hermes/P2, proxy/confinare, conturi/model/buget și trafic target. `dashboard_ready=false`, `assessment_ready=false` sunt stări reale, nu porți trecute implicit.
