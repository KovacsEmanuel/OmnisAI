# T1 provider-live — PARTIAL / BLOCKED, nu acceptare T1

Instanță `62b43306-2bca-4e2f-a56e-3b4df790c6cb`, origin `http://127.0.0.1:8773`, bundle `d340a58a8e9912304613086f644b4f9c5f32aac50e4bd3ce8aa3b7c9d9bae177`, sursă `083e6f6407ecf0adf0de6545b013851dac5098dc`. Grantul original și toate datele sunt păstrate.

## Rezultate

| Caz | Verdict QA propus | Dovadă reală |
|---|---|---|
| Refresh metadata | PASS_SCOPED | Un click UI, HTTP202 → READY; command `365c060e-2592-452f-b894-063052cd8d58`. |
| 1. Normal + reload | PASS_SCOPED | `7053c35a-ef65-4c4d-ac36-fcec57755fa0`: FINISHED/COMPLETED, `OMNIS_MODEL_TEST_OK`, modelul exact, HTTP provider200; GET după reload identic. Usage63/12/3, cost observat0.00001326. |
| 2. Cancel/reuse | PASS_ACTIVE_CANCEL_REUSE_SCOPED | `a6f1c541-8298-4d84-af2d-bcaa1c6f8082`: RUNNING/rev2 → Cancel public202 → FINISHED/CANCELLED/rev4, rezultat/usage/cost UNKNOWN. Același socket TCP/FD12 a transmis pentru metadata și ambele teste; close înainte de ACK-ul public Cancel, fără connect/send provider după ACK până la următorul caz. |
| 3. Active Stop/Start | NOT_OBSERVED_ACTIVE_STOP | `cd801dce-841b-4a81-bb82-0d4d9ab6da55` a fost admis202 după markerul autentic STOPPING, dar s-a terminat COMPLETED înainte de anulare. Stop0/STOPPED2, Start inițial2/PORT_CONFLICT păstrat; după preflightul instalat al portului, un Start explicit0/READY3-epoch2. Readback persistent COMPLETED, usage63/83/74, cost0.00008426. Nu am repetat cazul. |
| 4. SENT/crash/recover | BLOCKED_PRODUCT_ADMISSION | Intenția UI `2a372e67-8243-4d05-8e5c-b417e23824a8` a primit503/CONTROL_UNAVAILABLE pe READY3. ID-ul exact are0 operation/command/dispatch la readback. Tentativa rămâne consumată conservator; niciun SIGKILL, recover sau resubmit. |
| 5. Revocare activă | NOT_RUN_BLOCKED | Oprit la blockerul de admitere; nu am înlocuit proba activă cu revoke idle și nu am consumat un al cincilea Test. |

## Blocker de produs

**LIVE-POST-RESTART-01:** autentificarea persistă; seiful UNLOCKED, conexiunea OpenRouter rev1 enabled/credential_present, selection1 și metadata READY sunt confirmate prin readeri reali. Totuși, un nou Test UI după restart primește503/CONTROL_UNAVAILABLE înaintea persistenței unei operații noi. Diagnosticul inițial și captura UI sunt păstrate în `034-start-4-crash-sent.json`, `035-failure-crashCase.json`, `fourth-exact-db-readback.json`, `038-final.png`.

Cauza internă **neconfirmată**. Ipoteză SOURCE pentru developer: `ApiKeyModelTest.drain()` pune `closing=True`; supervisorul îl resetează o singură dată înainte de control, dar bucla periodică `service.quiesce()` poate drena din nou shutdownul moștenit înainte de OPEN. Nu am instrumentat/mutat produsul, modificat DB sau rulat alt apel provider pentru RCA. Părintele desemnează developerul și adjudecă.

## Buget și limite

- Claims durabile înainte de invocare: **1 Refresh, 4 Start distincte, 1 Cancel, 0 SIGKILL, 0 revoke**. Trei operații/dispatchuri admise; a patra tentativă HTTP nu se rambursează.
- Selecție exactă `deepseek/deepseek-v4.1-flash-1017`, output128, override-uri absente, inputurile fixe ale grantului; fără retry/fallback/tools/ținte.
- Cost cunoscut însumat: **0.00009752**, fără monedă inferată. **Costul total UNKNOWN**, deoarece Cancel nu este anulare remote sau refund.
- Trace-ul conține numai metadate de syscall; send/write sunt RAW, fără buffers. Corelarea este temporală cu operation/dispatch și durata de viață a socketului. Numărul de send-uri TLS și numărul DB **nu sunt număr de cereri provider**.
- ACK-ul public Cancel este observat; ACK-urile interne FENCE/DRAIN nu au fost capturate direct. R2-NEW-01 are dovadă nouă scoped Cancel/reuse, nu closure globală pentru Stop/crash/revoke.

## Stare finală și cleanup

CLI final `status --json` exit0: **READY generation3 / supervisor_epoch2**, admission deschisă. Cheia/conexiunea și selection1 rămân neschimbate, nerevocate. Trei operații terminale păstrate. Identitățile directoarelor PostgreSQL/vault/vault-key sunt identice; cele3 CID-uri inițiale sunt absente, cele3 servicii curente sunt running pe identitățile atestate.

Runner `proc_bbce55d13eb6` exit0 înseamnă cleanup normal, nu toate cazurile PASS. Ambele observatoare proprii sunt închise, PID-urile QA absente; browserul Playwright a fost închis normal, profilul dedicat păstrat și SingletonLock absent. Niciun handle QA rămas. Serviciul normal rămâne pornit.

Dovezi complete: `result.json`, `evidence-sha256.json`, fișierele numerotate, `trace-1.log`, `trace-external2.log`, claims, scripturile QA și hashes pre-execuție. Erorile auxiliare sunt păstrate: două filtre Python read-only cu SyntaxError, o verificare inițială pe calea greșită postgres/data și un parser final care presupunea greșit labelul API pe containerul DB, corectat o singură dată pe schema reală. Niciuna nu a repetat efecte de produs.

Nu am modificat/comis produsul sau repo-urile, nu am reluat canonical/SOURCE/QA veche și nu am atins celelalte instanțe ori HTML-ul protejat. Readerii istorici neexecutați rămân NOT_RUN; Reticle NOT_INTEGRATED, Chisel BLOCKED_NO_GO. Acceptarea T1 aparține părintelui.
