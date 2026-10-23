# R1 — EXACT80 relay WIP: CHANGES_REQUESTED / BLOCKED_SOURCE

## Rezultat și identitate

**CHANGES_REQUESTED; acceptarea relay rămâne BLOCKED_SOURCE.** Nu este acceptare T1, integrare, QA independentă ori GREEN. R2-NEW-01 HIGH rămâne deschis: reproducerea părintelui pe relay-ul vechi nu se închide prin această implementare WIP și prin cele două Cancel oracle-uri eșuate.

Review read-only pe `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-80`, detached și curat: HEAD `80c3ecd7d4618bf998cc573bf4a7c36834283e91`, tree `02045ec990426bc1ed7e08d69f69ebcae733951b`, base `0299082dd652db35f533a22d2cd61f5629708935`. Delta reală: 15 fișiere, +1604/-67. Am citit runtime/sender, ambele roluri relay și protocolul, callerii startup/forwarder/settings/admission, testele afectate și gate.log-urile exacte. Contractul relay curent a fost citit prin `git show 55510b1:documents/verification/api-key-runtime-t1.md`, fără schimbarea Main sau citirea runtime-src mutabil. Cleanup/15 identități rămân readbackul părintelui și freeze-ul, nu o nouă probă fizică a reviewerului.

## Must fix / dovezi obligatorii

### 1. HIGH — Cancel connect/write nu are ACK admis demonstrat; cauza precisă a avansului reviziei nu este observată

**Tip:** required missing proof + oracle ambiguity, NU defect de produs atribuit doar din 409.

**Fișiere:** `api/tests/test_model_test_v2.py:280–317,627–693`; `api/src/omnis/modules/runs/model_test_runtime.py:260–277,436–446,708–772`; `cli/src/omnis_cli/model_relay.py:179–200`.

**Scenariu/evidență:** prima operație autentică este terminată; testul închide numai poolul (`:628–630`), setează faza și pornește explicit `second_id`. Hookul DNS/`sock_connect`/`sock_sendall` setează `physical_entered` înaintea efectului fizic. Pentru connect/write este deja primul WRITE din handshake TLS al celei de-a doua operații, NU un hook garantat pe body-ul HTTP model. GET-ul `:642` și POST Cancel `:662` folosesc același `second_id`; expected revision vine din acel GET, nu din prima operație. Nu am găsit aici „wrong operation producer”.

WRITE este în `settings.lock` + admission SQL și are o fereastră fizică de cel mult0.5s. Cancel trebuie să ia aceeași blocare, deci nu poate comite STOPPING în interiorul acelei ferestre cât timp WRITE o deține. Hookul ținut poate expira; workerul poate termina FAILED/UNKNOWN și incrementa revizia înaintea admiterii Cancel. Aceasta este o ordine permisă de sursă, NU o atribuire a execuției înregistrate. `handle:264–265` emite REVISION_CONFLICT exact când revizia persistentă nu mai este expected; testul nu salvează perechea expected/current, finish_reason și ordinea settle/CAS. Nu putem spune din output dacă avansul concret a fost RUNNING→FINISHED sau altă intercalare. **Cauza exactă a celor două 409 rămâne NOT_OBSERVED/UNATTRIBUTED**, nu „race demonstrată”, nici bypass Cancel demonstrat.

**Corecție de cronologie după steeringul părintelui; rawurile au fost recitite integral:** al DOILEA fixture, `rf/db-b4eb525368364525/gate.log:4–19`, are47PASS/2FAIL,75.70s și ambele Cancel409/REVISION_CONFLICT la aserțiunea ACK682. `logs/relay-final-pg.log` îl localizează exact. Al TREILEA, cel mai recent fixture, `rf/db-f3872c984c94453e/gate.log:4–17`, are24PASS/2FAIL,75.61s: connect686 observă2 versus1+0; write689 observă handed6 versus5, cu ultimul chunk1535bytes. `logs/relay-boundaries-pg.log` îl localizează exact; NU conține409. Acea execuție a ajuns la oracle-ul efectelor, nu a eșuat la ACK. Nu este permis să transferăm409 din fixture2 către fixture3, să numim47PASS ultimul rezultat sau să cumulăm numerele.

**ACK/terminal/stage din fixture3:** rawul arată conectare/handoff suplimentare; nu arată statusul Cancel sau reviziile. Frozen80 are explicit testul ACK la682, terminal FINISHED la686 și oracle connect la689/write692. Fixture3 raportează connect la686/write689: este o variantă de producer/test diferită de frozen80, iar Git conține un singur checkpoint80 pentru întregul WIP, fără un commit intermediar care să lege acea variantă. Ajungerea la count oracle NU dovedește202 dacă acea variantă nu verifica ACK. Nici FINISHED ulterior, singur, nu dovedește FINISHED-CANCELLED; poate fi un terminal FAILED/UNKNOWN. **Accepted Cancel ACK în fixture3: NOT_OBSERVED; terminal finish_reason/revision și ordinea față de handoff: NOT_OBSERVED.** Legătura hookului din80 cu prima scriere TLS a second_id este demonstrată din sursă; transferul exact al aceleiași ordini/assertions către fixture3 este neprobat. Prin urmare extra connect/TLS bytes sunt FAIL-uri reale păstrate, dar nu pot fi adjudecate drept efect post-Cancel admis și nici absolvite ca simplă cursă CAS din acel raw. Nu există claim de409 curent sau de24/47PG pe bytes80.

**Criteriu:** un Cancel CAS409 nu este ACK și nu dovedește frontieră post-Cancel; nu se poate cere legitim suprimarea unei tranziții terminale deja câștigate doar pentru a obține202. Trebuie păstrate separat cazul Cancel comis→fence/drain→terminal și cazul terminal câștigat→refuz CAS, fără resend și fără efect după expirarea grantului.

**Remediu/decizie minimă:** NU modificați CAS-ul produsului și NU acceptați409 în loc de ACK. Cele două cicluri harness-only sunt consumate; nu propun alt framework, observer, a treia rescriere/rulare sau resetarea counterului. Părintele trebuie întâi să fixeze frontiera de probă: admiterea Cancel versus expirarea unui WRITE deja admis, pe aceiași producători reali. Dacă logurile existente nu conțin reviziile/ordinea, limita rămâne BLOCKED_SOURCE. O eventuală investigație viitoare cere admitere explicită, strictă, pe frontiera produsului și trebuie să păstreze oracle-ul post-ACK; numai un bypass demonstrat pe acea frontieră justifică fixul minimal al developerului desemnat. Cele48 teste pure finale nu înlocuiesc această dovadă și PG după ultimele editări este NOT_RUN.

### 2. MEDIUM — eșecul DNS obișnuit este promovat în defect permanent de autoritate/control

**Tip:** new source bug, trasat static; fără reproducere executată de reviewer.

**Fișiere:** `cli/src/omnis_cli/model_relay.py:136–161,215–226`; `api/src/omnis/supervisor/model_relay.py:126–131`; `api/src/omnis/modules/runs/model_test_runtime.py:584–595`.

**Scenariu/reproducer minim:** primul OPEN pentru Refresh primește `socket.gaierror` din getaddrinfo. Resolverul prinde OSError și lasă `rows=[]`, apoi OPEN face `auth_addresses(rows)[0]`. Nu există conversie explicită a acelui răspuns gol la UPSTREAM_UNAVAILABLE; refuzul de adresă ajunge la ramura ValueError/DENIED, nu la eroare upstream. În plus, acea ramură închide Connection numai pentru WRITE, nu OPEN. Senderul tratează DENIED ca RelayFailure și setează latchul `relay.failed`; metadata-finally refuză să scrie receipt FAILED, iar viitoarele comenzi/Stop nu pot revendica settlement sănătos. Un DNS outage finit devine indisponibilitate permanentă a ownerului până la recovery, nu Refresh FAILED urmat de Refresh nou explicit. Comentariul resolverului însuși numește răspunsul gol „ordinary upstream refusal”.

**Criteriu:** o lipsă autentică ACK/autoritate trebuie să rămână incertă; un DNS resolver terminat cu eroare cunoscută, fără socket/handoff, trebuie clasificat upstream și resursele OPEN retrase. Nu slăbiți DENIED/noACK și nu convertiți arbitrar toate excepțiile în succes.

**Remediu minim:** tratați explicit răspunsul DNS gol/eroarea getaddrinfo în OPEN ca UPSTREAM_UNAVAILABLE și închideți acel Connection; păstrați refuzurile de adresă non-globală și erorile protocol/capability/scope distincte. `forwarder.py:220–223` confirmă că auth_addresses([]) ridică ValueError; nu este numai o presupunere despre helper. Un singur regresion finit pe același broker și Refresh actual (eroare DNS→receipt FAILED→Refresh nou sănătos, fără resend) este suficient după admiterea fixului; nu adăugați framework ori retry automat. Acest finding nu atribuie retrospectiv cele două FAIL Cancel sau owner-loss.

### 3. MEDIUM — ordinea cold-start este plauzibil reparată în sursă, dar gate-ul CLI nu ajunge acolo

**Tip:** required missing proof, NU regresie de parser dovedită.

**Fișiere:** `cli/src/omnis_cli/start.py:1108,1422–1441,1471–1483`; `cli/src/omnis_cli/forwarder.py:112–142,468`; `api/src/omnis/supervisor/__main__.py:149–154`; `cli/tests/test_start.py:255–267`; `cli/src/omnis_cli/config.py:48–88`.

**Scenariu/evidență:** format5 pornește forwarder/broker înainte de supervisor/API și persistă identitatea lui; HTTP listenerul deferred validează `api.sock` la fiecare accept, nu fabrică readiness din absență. Supervisorul reconciliază înainte de quiesce. Aceste schimbări rup ciclul identificat în contract fără DNS/provider la boot. Reconcile fără operații active nu cere relay ACK; când există lucru moștenit cere drain, deci nu există shortcut general „socket absent=quiescent”. Totuși acest inventar inițial este numai system_operation, nu o dovadă nouă pentru metadata PENDING owner-loss, rămasă deschisă.

`logs/relay-last-cli.log`:52 executate/7FAIL, CONFIG_INVALID înaintea startupului. `start_instance:1108` cheamă load_config înainte de resurse/ordinea schimbată. Test setUp izolează XDG_DATA/STATE/RUNTIME, **nu XDG_CONFIG_HOME/HOME**; parserul citește configurația ambientală și refuză locații/chei/valori invalide. Aceasta identifică o frontieră de setup incomplet izolată, dar fără mediul/configurația efectivă din acea execuție NU dovedește cauza concretă a celor7refuzuri. Nu am citit configurația personală și nu cer relaxarea parserului.

**Criteriu/remediu minim:** nu folosiți acest run pentru credit cold-start/cleanup format5. Părintele trebuie să adju­dece prerechizitul/configurația privată a runnerului existent și să ceară numai pozitivul format5 pe bytes finali când este admisă proba relevantă, cu launcher/journal/cleanup real verificabile. Broad CLI istoric rămâne FAIL_UNADJUDICATED; fără rerulare acum, fără schimbări de produs justificate doar de CONFIG_INVALID și fără refacerea întregii infrastructuri.

## Semantica citită: ce există și ce nu aprobă

- **Producer legitim:** scope-ul MODEL_DISPATCH vine din dispatch/op/snapshot persistente, nu din browser sau digest autoemis; write_guard rezolvă owner/scope/config/projection/permit, SENT, epochs, deadline/caps și conexiunea revocabilă în admission serializat. METADATA_COMMAND are command UUID și owner/generation/epoch/deadline din metadata-request; nu pretinde SystemOperation/model permit. CipherStream rezolvă CURRENT la fiecare ciphertext WRITE, inclusiv TLS reutilizat.
- **Frontiera fizică:** OPEN rezolvă DNS fără SQL și nu conectează TCP; connect și sendall sunt numai în WRITE. Guardul rămâne peste ACK-ul bounded de handoff, nu peste răspunsul providerului. AnyIO TLS este public și verifică certificatul/hostname; brokerul vede ciphertext, nu cheia providerului. READ nu ține tranzacția SQL. Nu am constatat un await al răspunsului providerului sub admission.
- **Clock/fereastră:** physical_window citește clock_timestamp/expires_at după toate verificările de refs, include timpul query-ului în bugetul monotonic și deduce20ms din deadline-ul transmis. Brokerul revalidează UTC/end≤0.5s, deadline și fence înaintea handoffului și după send. Query-latency are numai testul cu AsyncMock (`test_model_relay_protocol.py:162–185`), nu măsurătoare PG curentă. Sincronizarea ceasurilor și scenariile de lease/head-change nu devin PASS din lectura sursei.
- **Stop/Revoke/Cancel:** Cancel comite STOPPING/cancel_epoch apoi anulează taskurile și drenează; Revoke/SaveConnection comit noul head în același settings.lock și drenează abia după ieșirea din lock/admission. Worker finally nu settlează Cancel/Deadline înainte de drain. Relay.failed/settlement_failed împiedică terminalizarea, iar drain_models refuză quiescența. InstanceService.quiesce cere runtime_drain true și revalidează owner/generation înainte de quiesced; noACK nu devine FINISHED-CANCELLED. Erorile pot lăsa RUNNING nesettled sau shutdown STOPPING/UNCERTAIN; nu pretind toate proiecțiile literal STOPPING.
- **Scope vechi/reuse:** brokerul compară owner/epoch/generation/instance/provider și secvența; scope-ul curent al streamului se mută la noul WRITE. FENCE/DRAIN sunt pe egalitatea întregului Scope, astfel vechiul A nu închide B după reuse. Testul real broker `test_model_relay_scopes.py:98–117` verifică A→B, fence A, owner diferit, cancel_epoch diferit și duplicate WRITE. Este broker/raw-bytes, nu PG/TLS/Cancel API. Scope cancel_epoch2 nu fencează automat vechiul epoch1: corectitudinea depinde de producerul runtime care păstrează dispatch epoch1 pentru drain, nu de un wildcard nou.
- **UNKNOWN/no resend:** SENT precede SDK; timeout/outage fără răspuns cunoscut păstrează UNKNOWN, nu NOT_SENT/refund. Secvența broker este consumată înaintea efectului, retries SDK/pool sunt0; reconcile moștenit settlează fără programare/resend. Nu este probă crash/SENT, metadata owner-loss sau installed restart.

## NON-RELAY029: numai închiderile scoped neschimbate

Reutilizez explicit cele7corecții din raportul `reviewer1-model-corrections-029-review.md`, nu verdictul întreg: K1 receipt/GET Refresh command-bound; K2 strict JSON POST; K5 Make flags; N1 usage per-componentă/bounds; N2 redacție înainte de limitare; N3 recovery UI/refuz definitiv versus UNKNOWN și invalidation Settings; R2-NEW-04 taxonomie excepții transport/stream. **CLOSED_SOURCE_SCOPED029 pe semantica neschimbată**, inclusiv ID binding GET/Cancel citat anterior. Noul mecanism relay poate introduce noua regresie DNS de mai sus; aprobarea veche nu acoperă noul transport, guard, finally/reconcile sau startup.

## Probe înregistrate, NU rerulate

- Prima integrare production-relay:21PASS/62.42s, receipt code0/drained, conform freeze; nu probă curentă pe80.
- Al DOILEA fixture PG: `rf/db-b4eb525368364525/gate.log`:47PASS/2FAIL,75.70s, runner code2/drained; Cancel409 la682. Argv include test_model_relay_protocol.py (23teste pure suplimentare), nu scopes.
- Al TREILEA / cel mai recent fixture PG: `rf/db-f3872c984c94453e/gate.log`:24PASS/2FAIL,75.61s, runner code2/drained; extra connect686 / handoff689, fără409 în raw. Argv NU include cele23protocol pure, nici scopes. Numerele nu se adună și niciunul nu devine total curent80. **PG pe bytes80 după ultimele editări ACK/deadline/query-latency este NOT_RUN. Freeze-ul original are o discrepanță de cronologie/count pe care părintele o consemnează separat; nu l-am modificat.**
- `logs/relay-last-unit.log`:48PASS/1.26s (protocol/scopes/sender), autor; nu rerulare independentă, nu48PG.
- CLI:52executate/7FAIL;25profile PASS anterior nu acoperă automat ultima ordine startup. Quality din freeze: mypy277/format358, fără transfer în runtime PASS.
- Preexistent metadata PENDING owner-loss:2cicluri SHUTDOWN_INCOMPLETE/GENERATION_CONFLICT, cauză neatribuită; nici rerulat, nici închis. Canonical API-key-only, broad CLI adjudicat, crash/SENT, installed/native/browser/historical readers/live/provider/Orca rămân NOT_RUN/open.

Comanda PG păstrată în freeze (NEEXECUTATĂ aici): `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH UV_CACHE_DIR=../core-uv-cache TMPDIR=../rf api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-model-test-v2-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 300`. Unit păstrat: `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_model_relay_protocol.py api/tests/test_model_relay_scopes.py api/tests/test_model_sender.py -q --tb=short`.

## Comenzi proprii și limite

Numai git status/rev-parse/diff(--stat/--unified/--check/--quiet), git show pentru registrul55510b1, read_file/search_files și Python stdlib/AST pentru citiri locale; nicio importare/executare produs. Identitatea finală HEAD/tree și checkoutul curat au fost reconfirmate, git diff --check și quiet exit0. Un batch read_file a eșuat KeyError(content) înaintea citirilor; fallbackul stdlib prin terminal a recuperat secțiunile omise. Două outputuri lungi au fost trunchiate; secțiunile necesare au fost recitite focalizat, nu presupuse din trunchiere. Raportul este singurul write autorizat. Bugetul de apeluri cerut a fost depășit pentru recuperarea citirii eșuate și publicarea raportului; nicio probă effectful suplimentară.

Reticle NOT_APPLICABLE pentru relay/CLI; Chisel BLOCKED_NO_GO. Nu am modificat skilluri/produs/teste/docs/Git, nu am pornit SQL/PG/OCI/provider/target/browser/install/native, nu am citit env/keybytes/password sau HTML protejat. Părintele adjudecă; numai developerul desemnat implementează eventualul fix DNS sau alt fix demonstrat.

Singurul fișier creat: `../logs/reviewer1-relay-wip-80-review.md`; niciun commit. R1: CHANGES_REQUESTED/BLOCKED_SOURCE, R2 relay HIGH încă OPEN.

Necontrolat: execuție nouă, PG pe bytes80, startup installed/native, crash/SENT, browser/provider și canonical.
Risc: frontieră Cancel connect/write nedovedită; 409 nu este ACK, iar DNS outage are un nou traseu de latch permanent în sursă.
