# R1 — 878895d — APPROVED_SOURCE_SCOPED

**What this change does:** mută DNS/TCP readiness în OPEN, în afara admisiei SQL. WRITE păstrează verificarea CURRENT și serializarea cu Cancel/Stop/revoke, dar brokerul execută numai un singur `send` nonblocking pe socketul deja conectat. Separă expirarea de Cancel și distinge Cancel admis de CAS stale după settlement.

## Snapshot și scope

- Checkout read-only: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-878`.
- Base: `fb54beace973b7c49422b197404f04c8baa6a9dd`.
- HEAD: `878895d3a4dda1f50c394dd01a711ac79acd1586`.
- Tree: `f666a1b26d9fd530291227f7da1f766bd86f6e9b`.
- Status inițial/final: detached HEAD, clean. `git diff --check BASE HEAD`: exit 0.
- Cele 9 fișiere din `parent-878-freeze.json`: am reverificat programatic SHA-256 pe bytes, blob HEAD și blob BASE; toate corespund. `../freeze.txt` concordă.
- Scope: toate cele 9 delte, contractul arhitectură §5:220–235, `InstanceService.admission`, producerii `metadata_guard`/`write_guard`/`physical_window`, callback-ul CURRENT, callerii ModelSender, Cancel/settlement/drain și revoke. Nu audit general, nu T1/T2 approval.

## Verdict

**APPROVED_SOURCE_SCOPED. Nu am identificat un finding CODE blocant în această deltă.** Schimbarea repară mecanismul demonstrat de RED: TCP connect nu mai poate aștepta sub guardul WRITE. Aprobarea privește bytes/scope de mai sus, nu dovada PostgreSQL sau acceptarea T1. Părintele adjudecă și admite separat consumerul PG după reviewurile necesare.

## Contract → implementare → oracle

1. **Readiness fără SQL deschis.** `api/src/omnis/supervisor/model_sender.py:120–129` părăsește contextul guard înainte de RPC OPEN. Scope-ul și deadline-ul vin din Authority emisă de producer, nu din date HTTP ori dintr-o autoritate reconstruită în test. `api/src/omnis/modules/runs/model_test_runtime.py:452–473,476–514,598–706` leagă fereastra de lease și deadline și validează starea/configurația/dispatchul curent. OPEN nu primește automat dreptul de a trimite ciphertext ulterior.

2. **Fereastră bounded și fence pe readiness.** `cli/src/omnis_cli/model_relay.py:115–176` validează deadline-ul OPEN/WRITE în fereastra de cel mult 0.5s și sub deadline-ul scope-ului. După DNS verifică fence/closed/expiry înainte de connect, apoi verifică din nou după connect; timeoutul deține așteptarea. Socketul este creat nonblocking. OPEN este introdus în conexiuni și tasks înaintea așteptărilor; FENCE închide/anulează, iar DRAIN include resolverul încă viu (`:33–44,101–113,134–159,222–236`). Resolverul nu primește ulterior o cale detașată de connect/send. Deadline-ul trecut după ieșirea SQL refuză conservator, nu este reînnoit de broker.

3. **Handoff local, nu așteptare upstream sub SQL.** `cli/src/omnis_cli/model_relay.py:179–207` cere socket pregătit, verifică identitatea owner/generation/provider și secvența, consumă secvența înainte de efect, verifică fence/deadline/limite și execută exact un `socket.send(body)`. Nu mai există `sock_connect` sau `sock_sendall` în WRITE. Partial/backpressure/closed/expiry închid conservator, fără reluarea restului. Limitele 65536/frame și 4MiB/conexiune rămân. SQL încă acoperă IPC-ul privat finit și ACK-ul handoff-ului, nu o operație care așteaptă progresul rețelei externe. Această distincție este compatibilă cu serializarea ultimului send din arhitectură §5:233; nu echivalez un ACK IPC local cu un răspuns provider.

4. **CURRENT pe fiecare payload, inclusiv stream TLS reutilizat.** Callback-ul din `model_sender.py:129` citește CURRENT la utilizare, iar `api/src/omnis/supervisor/model_relay.py:179–203` intră din nou în guard pentru fiecare bucată. `CipherStream.scope` și scope-ul conexiunii brokerului sunt actualizate pentru operația curentă. READ nu deține admisia. Așteptarea conservatoare până la deadline în cazul ACK pierdut/cancel în WRITE a rămas; nu se eliberează voluntar guardul cu o fereastră de handoff încă validă și neconfirmată.

5. **Cancel/Stop/revoke păstrează ordinea.** Cancel verifică CAS înaintea FINISHED, persistă STOPPING/cancel_epoch, apoi anulează/drenează în afara lockului de settings (`model_test_runtime.py:249–277,436–450`). `drain_models` așteaptă taskurile, brokerul și reconcilierea (`:59–72`); Stop comite închiderea înainte de runtime drain (`instance/service.py:489–517`); revoke apelează model_drain după commit și ieșirea lockului (`provider_key_service.py:331–334`). Nu am găsit o mutare nouă de network wait în aceste tranzacții.

6. **Protocol și callerii afectați.** Ambele copii ale protocolului cer UTC și pentru OPEN; sunt byte-identice și compatibile cu noul caller care furnizează deadline. Testele directe OPEN afectate au fost actualizate. Testul DNS cu adresă placeholder interceptează connect înaintea oricărui efect extern; nu se bazează acum pe faptul că vechiul OPEN nu conecta.

## Review al oracle-ului PG, fără execuție PG

- `api/tests/test_model_test_v2.py:669–754`: expirările connect și WRITE sunt ramuri fără Cancel concurent. WRITE întârzie RPC-ul producătorului înainte de handoff, sub fereastra guardului (`:344–351`), nu simulează un send blocant al brokerului. FINISHED/UNKNOWN, usage/cost necunoscute, contoarele înainte/după release și lipsa settlement_failed sunt cerute. DNS Cancel/revoke/Stop păstrează threadul resolver deținut și verifică lipsa ACK/FINISHED până la release.
- `:613–624`: settlement-ul real este terminal înainte de Cancel; expected revision 2 este revizia RUNNING reală (`model_test_runtime.py:737–740`). Oracle-ul cere exact 409/REVISION_CONFLICT și readback terminal neschimbat, nu tratează 409 ca ACK de Cancel.
- `:755–863`: pausa este pe body-ul JSON înaintea apelului original `Stream.write`, deci înaintea noului guard/body handoff; headerul anterior a parcurs deja RPC-ul real. În codul curent, callback-ul CURRENT produce scope-ul celui de-al doilea dispatch pe conexiunea reutilizată. Wrapperul capturează scope/connection/sequence/deadline reale (`:330–355`), nu fabrică Authority din DB. Cancel cere exact 202, FINISHED/CANCELLED, readback identic și ACK-urile FENCE/DRAIN pe scope-ul capturat. Contoarele sunt capturate după ACK și reverificate după tentativa raw/release, nu comparate numai cu un total anterior operației.
- **Limită importantă a afirmației:** raw WRITE de la `:817–847` este un replay exact al unei secvențe deja consumate, cu deadline-ul original. DENIED probează respingerea acelui replay producer-scoped după ACK; singur nu izolează fence-ul ca motiv al refuzului, deoarece duplicate-sequence și eventual expiry sunt refuzuri independente. Nu îl creditez ca probă a unui *nou* WRITE altfel admisibil sau ca probă PG deja executată. Pentru scopul cerut de replay exact, împreună cu ACK-urile scoped, boundary-ul pre-body și contoarele, nu este un blocker CODE. Testul SOURCE separat verifică deja old-scope FENCE cu next sequence și fereastră proaspătă (`test_model_relay_scopes.py:183–202`); nu transfer autoritatea acelui scope sintetic asupra consumerului PG.

## Dovezi citite și comenzi efectiv executate

Read-only: `git status --short --branch`; `git rev-parse HEAD HEAD^{tree}`; `git show -s --format=fuller HEAD`; `git diff --stat BASE HEAD`; `git diff BASE HEAD`; `git diff --check BASE HEAD`. Python stdlib a verificat cele 9 SHA/bloburi față de manifest. Citiri/search-uri locale ale surselor și contractelor enumerate mai sus și ale logurilor originale, prin read_file/search_files. Un lookup inițial al numelui arhitecturii a ratat fișierul; am găsit și citit `Omnis_MVP_Architecture.md`, nu am inferat contractul din rezumat.

Dovezi istorice citite, **nu rerulate**:

- `../red-readiness.log`: 2 FAIL, `connect_under_guard == [True]` în loc de `[False]`; 33 deselected, 1.94s. RED-ul inițial are parametri False/True, nu pretind că toate cele șase moduri finale au fost executate RED.
- `../green-final.log`: 86 PASS / 2.89s. Comanda din commit: `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_model_sender.py api/tests/test_model_relay_scopes.py api/tests/test_model_relay_protocol.py api/tests/test_model_test_v2_contract.py -q --tb=short`. Public SDK/broker/TLS owned, **SOURCE lock-double, nu SQL**. Cele șase moduri finale verifică healthy/veto/connect-expiry/backpressure/partial/closed, connect fără lock, lipsa async upstream writes și handoff numai sub lock.
- `../cli-final.log`: 2 forwarder + 1 held-DNS/fence unittest PASS; acesta cere DRAIN BUSY înainte de release și zero connect ulterior.
- `../quality-final-pass.log`: `[][]`, All checks passed, 77 files already formatted; mesajul commitului leagă quality de comenzile sale. Nu confund aceste câteva linii cu o nouă rulare proprie.
- `../collect-final.log`: 27 colectate / 1.18s, inclusiv cele trei scenarii schimbate. **Collect-only nu dovedește comportamentul PG.**

## Limite și următoarea decizie

Nu am executat teste, PG, network, provider, browser, instalări sau efecte de produs. Nu am schimbat surse, teste, documente canonice, Git sau counterul harness-only. Cauza vechilor interleavings/409 rămâne UNATTRIBUTED; acest review stabilește defectul de readiness și noul boundary, nu rescrie istoria. Nu transfer vechile rezultate PG asupra noului candidat.

După adjudecarea părintelui și reviewul complementar, următorul obiectiv legitim este **un consumer PG bounded pe sursa curentă**, cu aceste oracle-uri și cleanup propriu, nu altă rerulare SOURCE, full T1/T2 automat sau condiția circulară de a avea deja PASS-ul pe care QA trebuie să îl producă. Counterul istoric rămâne 2; constatarea/remedierea de produs nu îl resetează.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Singurul fișier creat de acest review este acest raport. Riscul rămas: SOURCE nu certifică ordinea/tranzacțiile/lease și readback-ul PostgreSQL reale, iar replay DENIED nu identifică singur motivul fence.
