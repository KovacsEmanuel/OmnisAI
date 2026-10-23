# R1 — oracle-fea — APPROVED_SOURCE_SCOPED

**Verdict propriu: F01/F02 închise pentru cele două lacune temporale concrete din oracle378.** Aserțiunile post-ACK exclud expiry drept explicație accidentală în scenariile identificate, în domeniul temporal UTC existent. Niciun blocker concret nu supraviețuiește în acest scope. Nu este PG PASS sau certificat de completitudine universală.

## Snapshot / scope

Frozen `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-fea`: HEAD `fea84e2d987d56db3a3f701f0b3d396f7fe21a64`, tree `0c92f4852572673498a18ac60a92563c9dbe633c`; base `37877c83ac2525f5480c5e5db091ea429eeec43b`. Singura deltă: `api/tests/test_model_test_v2.py`, **+4/−0**, blob `ff500ea451f1bfd114c46101c71976fc4392fea6`, SHA-256 `49ccce5ee641be375bf85fbd56a2fac5a7e9d694f8c5b2bf2db9183bd2d4c3f8`. Identități conforme cu `parent-oracle-fea-freeze.json`; frozen clean; `git diff --check BASE HEAD` exit0.

Aprobările SOURCE pentru produsul878 și scope-urile deja aprobate din oracle378 sunt reutilizate neschimbate, fără reaudit sau extindere. Schimbarea atinge numai cele două predicate din test; niciun caller, fixture, config, export sau produs modificat.

## Dispoziții

- **R1-378-F01 — CLOSED_SOURCE_SCOPED.** La `:869`, `datetime.now(UTC) < late_deadline` este cerut după primirea/decodarea ACK-ului raw WRITE (`:866–868`). `late_deadline` rămâne limitat de deadline-ul scope-ului și de now+0.4s (`:846–850`). Dacă brokerul procesează frame-ul după acest expiry, observația post-ACK nu mai trece. Un răspuns DENIED/size=0 sosit prea târziu nu mai poate fi creditat drept dovadă fence. Verificarea pre-send, schema, scope/connection reale, request UUID nou, next sequence, identitatea exactă a răspunsului și contoarele rămân.
- **R1-378-F02 — CLOSED_SOURCE_SCOPED.** La `:761–763`, după ACK-ul acțiunii și înainte de readback/release, timpul trebuie să fie anterior ambelor deadline-uri OPEN capturate: `min(utc(connect_scope.deadline), utc(connect_deadline))`. Contraexemplul expiry înainte de câștigarea settlement-ului de către Cancel nu mai poate trece acest predicat. Rămân RUNNING/op ID/revizia inițială, ACK202, FINISHED/CANCELLED, readback identic, FENCE/DRAIN pe scope-ul OPEN, release încă blocat și zero efecte tardive față de baseline-ul post-ACK. Nu confund această situație cu terminal-wins/409.
- **`connect_deadline` — cale atribuită confirmată.** `physical_phase` este inițializat `""` (`:277`) și atribuit din scenariu (`:679`). Prima ramură `== "connect"` (`:711`) atribuie simultan `connect_scope, connect_deadline = model_opens[-1]` (`:714`). Nu există atribuire a lui `physical_phase` între această ramură și cea post-ACK (`:758`), nici în callbackurile fixtureului. Dacă unpack-ul eșuează, execuția se oprește înainte de utilizare. Advisory-ul Pyright nu identifică astfel o cale runtime unbound; nu este necesară inițializare artificială sau ignore.

Diff-ul exclusiv aditiv păstrează toate predicatele/limitele anterioare, inclusiv DNS drain, expiry fără Cancel, terminal-wins, timeouturi, release/cleanup și contoare. Nu introduce autoritate DB nouă. Remediu suplimentar: niciunul pentru F01/F02 în scope-ul cerut.

## Dovezi / limite

Review static propriu pe bytes curenți și citiri Git/local read-only. Nu am rerulat teste, quality gates, PG, servicii sau rețea. `oracle-time-counterexample.log` este numai demonstrație cu timestampuri fixe, nu interleaving observat sau probă PG. Logurile păstrate arată collect28/exit0 și quality/exit0; nu sunt execuții ale acestui review. Aprobarea nu presupune PG PASS, nu aprobă T1 integral și nu înlocuiește QA reală. Counterul harness-only istoric rămâne2. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Incident procedural: verificarea auxiliară de reconstrucție textuală a fost oprită de un assert care număra atât predicatul pre-send existent, cât și noul predicat post-ACK; nu este defect al sursei și nu creditez reconstrucția byte-for-byte ca verificată. Identitățile și diff-ul Git au fost citite separat, cu succes. Scrierea raportului a necesitat un al treilea apel, depășind limita solicitată de două; fără alte audituri sau rerulări.

Creat numai acest raport; fără mutații Git/produs/DB. HTML-ul untracked preexistent din checkoutul comun a rămas neatins. Părintele adjudecă integrarea și admiterea QA.

Omis: consumer/PG runtime și reauditul scope-urilor aprobate. Risc: ceasul UTC existent nu oferă dovadă universală la salturi de ceas; schedulingul lent poate produce FAIL conservator, nu falsul PASS temporal identificat.
