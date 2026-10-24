# R1 — review independent focalizat startup T1

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: niciunul.** Fixul poate avansa la artefact/QA după verdictul complementar R2; acest review nu aprobă distribuția, runtime-ul instalat sau închiderea T1.

## Snapshot și mandat

- Checkout read-only: `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`.
- Bază: `be72942d82dfa6caf0c1c42c095306a5e33eaa81`.
- HEAD: `92e36082d64b8ae49437df1976876b0d66ba089f`; tree `f82811691df67b073e0bc28b16332651c26dd638`.
- `freeze.json`: HEAD/tree/clean, setul exact de trei căi, bloburile și SHA256 ale fișierelor, plus SHA256 al diff-ului `1123cbf7ef6b5990ed31616706c21456176d58a86d13829b7540be75333c19e2`, verificate programatic: MATCH, exit0.
- Delta: numai `api/src/omnis/supervisor/__main__.py`, `api/tests/test_supervisor.py`, `api/tests/test_runtime_supervisor.py`. `git diff --check be72942..92e36082`: exit0.
- Cerință → consumer → risc → decizie: boot T1 fără provider IO, fără consumarea lease-ului prin pregătire inertă → `supervisor.run()` → expirare înainte de READY ori autoritate prematură → admiterea/remedierea fixului SOURCE înaintea artefactului. Nu audit al runtime-ului legacy.

## Constatări pe cod și probe

| Cerință | Constatare și ancoră |
|---|---|
| Pregătire inertă înainte de acquire | `supervisor/__main__.py:79–98` păstrează readiness, validează perechea vault/keys și incompatibilitatea runtime, validează egress exact `/vault`, apoi face importurile și construiește `ModelSender` înainte de `acquire`. `ApiKeyModelTest` importă tranzitiv senderul; și acel cost este acum pre-acquire. Nu apare heartbeat suplimentar, retry sau timeout mărit. |
| Fără autoritate/provider IO din constructor | `model_sender.py:247–255` construiește transportul/TLS/clientul HTTPX, nu apelează `send`/`metadata`. `model_relay.py:34–39` memorează numai calea și starea goală; citirea capability-ului/conectarea rămân în `rpc`, nu în constructor. TLS poate citi trust-store-ul local: „inert” nu înseamnă zero citiri locale, ci fără provider, credential ori efect autorizat de execuție. `ProviderVault` și ownerii rămân post-acquire. |
| Lease și ordinea de recuperare păstrate | `__main__.py:98–107,151–172`: acquire → owned status/identity → owneri → reconcile → quiesce → control/READY. Nu se deschide admission. `instance/service.py:303–307,329–363,489–517,975–979` păstrează Stop fence, exclusivitatea ownerului, lease de 5s pe ceas DB, verificarea epoch/live și refuzul ownerului expirat. Reconcile nu este mutat înainte de acquire, iar inherited work nu primește resend (`model_test_runtime.py:74–143`). |
| Validări și acquire refuzat | `__main__.py:83–97,259–288`: gardurile nu dispar; configurația invalidă este refuzată chiar înainte de acquire. Dacă acquire ridică excepție, `epoch` rămâne None, senderul deja construit este închis, nu se execută release pentru un owner necâștigat, engine-ul este disposed și handler-ele de semnal sunt scoase. Testele noi `test_runtime_supervisor.py:18–75` acoperă refuzul acquire, lipsa keys, runtime incompatibil și egress invalid, inclusiv sender închis/zero fișiere create. |
| Cold import/metadata fără pornire implicită | Importurile mutate rămân în corpul `run`, nu la nivelul modulului. Importul simplu nu construiește sender și nu cheamă `metadata`; testul cold verifică absența OpenAI/sender înainte de run și interzice send/metadata/TCP/DNS/subprocess. Nu revendic execuția unui doctor instalat. |

Testul `test_supervisor.py:18–156` injectează explicit întârzierea de 5.25s în import/construcție, păstrând ceasurile și lease-ul real; controalele sunt cold, before-acquire și owner-loss. Verifică READY/heartbeat/exit, închiderea senderului, admission închisă, zero system operations/dispatches și readbackul lease-ului. Controlul owner-loss cere în continuare LEASE_LOST, exit3, fără READY/heartbeat. Testul este despre noul defect reprodus, nu despre cauza istorică.

## Dovezi citite, fără rerulare PG/QA

- `red2/db-4389d2f2e3f247d5/gate.log`: **3 failed / 3 passed, 49.92s**. Import și constructor: exit3/LEASE_LOST; al treilea RED verifică schimbarea intenționată a pregătirii înainte de acquire refuzat, nu un al treilea defect de produs.
- `green/db-f0120e045fb148bd/gate.log`: **111 passed, 115.54s**; nodeid-urile celor cinci cazuri cold și patru cazuri guards/cleanup sunt PASSED. Suita este mixed SOURCE/private-PG, nu 111 probe instalate.
- `source.log`: **50 passed, 4.36s**. Quality exit0 este raportat în FREEZE; nu am rerulat lint/mypy. Primul RED necurat rămâne consemnat, fără promovare la RED curat.
- Reproducerea independentă a bazei pe PG din contextul părintelui este proveniență furnizată, nu o execuție făcută de R1.

## Dispoziție și limite

Remediul închide **la nivel SOURCE/review R1** defectul concret „import/construcție inertă post-acquire consumă lease-ul înainte de READY”, susținut de RED→GREEN al autorului și reproducerea părintelui. **DURABLE-T1-START-01 rămâne UNKNOWN ca atribuire cauzală istorică.** Un stall real după acquire trebuie încă să fie refuzat; fixul nu promite boot infailibil și nu relaxează această regulă.

Nu am implementat, pornit servicii/PG, executat teste/QA, accesat provider/chei/seif/profiluri vechi, modificat integration-src/canonical5, citit HTML-ul protejat sau făcut push. Am creat numai acest raport în scratch, fără schimbări în checkout. Reticle: NOT_APPLICABLE; Chisel: BLOCKED_NO_GO.

**Neexecutat:** build/reseal, doctor instalat, QA instalată și canonical; acestea rămân la părinte/etapa autorizată. **Risc rămas:** aprobarea SOURCE nu se transferă automat artefactului și nu dovedește cauza incidentului istoric.
