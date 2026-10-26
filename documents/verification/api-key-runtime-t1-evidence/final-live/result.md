# Lot final provider-live — rezultat scoped

Instanță `e10da359-a48f-40f3-ad2f-7641a3f6bb83` · bundle `a5b89393716f31868e97d7f5201249ab1de76f6395300cecc5d657890e34dba4` · source `5d5bbfb35b3833ef6d8be0f2e2651cf235a515a2`.

**Executate 4/4 teste, 1 Refresh, 1 SIGKILL pidfd, 1 revocare locală. Fără retry/refund ori apel suplimentar. T1 nu este declarat acceptat.**

| Frontieră | Rezultat real |
|---|---|
| Restart inițial | Stop→Start normale exit0; PGDATA identic, autounlock și connection/selection rev1 persistate fără Save/rebind. READY3/epoch2. |
| Refresh unic | HTTP202→200, READY autentic; 0.976s între receipturile metadata. |
| 1 normal — `1c11dd5d-a98f-4f21-a120-6d5c7832f679` | HTTP202→200; COMPLETED, `OMNIS_MODEL_TEST_OK`; model cerut=observat; usage KNOWN, cost_observed 0.00001341; reload identic. |
| 2 Stop activ — `64068254-d5a9-49c0-a7cc-8bc3de1fa2c2` | RUNNING/SENT observat înaintea CLI Stop. COMPLETED precede STOPPING și bariera; quiesce/finalize și STOPPED reale, apoi Start/readback. **STOP_REQUEST_DURING_ACTIVE_NO_POST_ACK_SCOPED**, nu active cancellation/drain sau ACK intern FENCE. |
| 3 crash SENT — `d4c59b8a-ac89-48c4-ab0e-095f04a9fc72` | PIDFD original pregătit înaintea Test; revalidări postclaim, un SIGKILL; owner gone/lease expirat→recover STOPPED→Start explicit; UNKNOWN/OWNER_LOST persistat, un singur dispatch/SENT, fără resend. Usage/cost UNKNOWN. |
| 4 revoke activ — `569ef2e2-b632-41fa-8206-8a2cf509451d` | RUNNING/SENT→revoke HTTP200/receipt200; connection rev2/enabled=false; UNKNOWN/CANCELLED persistat. Socket provider închis înaintea ACK public. Nu dovedește anulare remote; usage/cost UNKNOWN. |

## Buget, trafic, persistență

- Grant consumat integral: 4 Start **de teste** + 1 Refresh. CLI separat: 3 Start, 2 Stop, 1 recover, 1 status. Toate mutațiile au claim durabil anterior invocării.
- Ledger final: 4 operații, 4 dispatch-uri; fiecare RESERVED→SENT→SETTLED o singură dată. Model commands: 4 start + 1 refresh. Readback ulterior identic, fără comandă suplimentară.
- Două rezultate au usage/cost KNOWN; subtotal `cost_observed=0.00002532`. **Total UNKNOWN**, fără refund pentru crash/revoke.
- `trace-analysis.json` leagă cele 3 trace-uri de PID/FD/inode/lifetime și timestamps. Socketul provider din primul trace este reutilizat; numărul TLS send/connect nu este numărul HTTP calls. În revoke se observă numai scriere TLS pe lifetime înaintea închiderii, nu cerere HTTP completă. FD numeric reutilizat după close nu moștenește identitatea socketului provider.

## Stare și limitări

- Final **READY8/epoch5**, seif UNLOCKED; connection **rev2, enabled=false**, selection rev1 nemodificată. Operatorul trebuie să reactiveze explicit ulterior. Date/artefacte/loguri private păstrate.
- Runnerul original **exit1 după toate rezultatele**, în callback-ul stderr al observerului (referință `tracer` nulă în timpul detach). Nu este ascuns: `runner.stderr`, `first-diagnostic-finalizer.json`.
- S-a executat numai acțiunea existentă `finish` în continuarea read-only, **exit0**: citiri finale, status READY, `context.close()` normal. Trei tracere absente, forwarder TracerPid=0, browserul dedicat și ownerii QA absenți. Nouă CID-uri retrase din **acest root** sunt absente; cele trei servicii curente rămân intenționat active.
- Preflightul a corectat strict doi readeri QA (permisiune PG host și SELECT fără rând); verificarea argv a fost corectată la delimitator NUL real. Diagnosticele inițiale rămân. Nicio modificare de produs/DB directă, niciun nou harness lifecycle.
- Active-cancellation/drain prin Stop rămâne NOT_OBSERVED; vechiul case3 păstrat. Al cincilea test pe conexiune revocată NOT_RUN (neautorizat). SOURCE/Cancel/reuse istorice nu au fost rerulate sau promovate la toate intercalările fizice; compoziția P7 și acceptarea T1 aparțin părintelui.

Dovezi principale: `result.json`, `trace-analysis.json`, `runner-inputs.json`, `readback-runner-inputs.json`, `final-owned-resource-verification.json`, `final-process-exact-verification.json`, readbackurile per caz.

Neexecutat: SOURCE/canonical/QA veche/T2, reactivare, extra provider Test, alte roots, cod produs, commit/push. Riscuri: două costuri UNKNOWN și lipsa reproducerii installed active-Stop-cancellation; rezultatul nu este un PASS global al runnerului.
