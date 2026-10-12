# B06b — metoda nativă CONTRACT/PURE (tracer SOURCE adjudecat)

Autoritate: plan §7.1 și contractul B06b C01–C12; nu este un plan sau audit nou. Baza de lucru este `abac977cf841429a65b4304d9c7abf01233dd3d5`. Codul este comis în `35ff2f4` (exit UDS), `381c394` (schema/pins) și `fb97c8e` (metodă nativă/inbox). Tracerul records SOURCE este adjudecat scoped; acest registru nu închide B06b, G02-inert sau P2.

## Contractul feliei

- Reutilizează seed-urile publicate capture/records, supervisorul, RuntimeHost/NativePeer, mappingul și store/inboxul existente.
- Protocolul v4 și `ContractAdmission` sunt distincte de cold/NO_MODEL și de inițializarea providerului. Copilul AIAgent execută metoda deterministă, nu o conversație LLM și nu un emitter în backend.
- Bindingul comis precede primul read/tool. Citirile sunt limitate la assignmentul immutable, iar StepOutput consumă outputul real anterior. Ownerul păstrează bariera InstanceControl/lease pe metoda PURE finită; Stop nu autorizează un release nou.
- Rezultatul și receipts autentificate sunt persistate înaintea MethodCheck. Checkerul verifică refs, pași, schema și context fără să reruleze algoritmii. Catalog owner și supervisor lease owner sunt identități distincte.
- Schema `0012_contract_methods` adaugă SUCCEEDED numai cu result/check, cu pins explicite API/CLI/bundle. Nu migrează profiluri existente. Inboxul nu confundă metoda copilului cu un tur Brain: admitted/turn_completed rămân false; consumul de domeniu este separat.

## Probe adjudecate până acum

| Probă | Rezultat și limită |
|---|---|
| Producer nou | RED: parametrul method_execution absent; GREEN: compoziție v4 validată și pe consumerul nativ. SOURCE, nu execuție instalată |
| Identități owner | RED: supervisor distinct de catalog → METHOD_RECEIPT_MISMATCH; fix: ownerul catalogului vine explicit de la callerul calificat, nu din lease |
| Checker + producer după fix | 95 pytest PASS, exit0; Ruff check/format0 și mypy4 fișiere0. Nu autenticitate nativă ori PG din state holders sintetice |
| `make check-runtime` | exit0:420 pytest +6 AST, Ruff0/mypy15. Gate de componente, nu canonicalul complet sau G02 |
| Migrare/producer PG, tentativa1 | exit2,1FAIL/3PASS: oracle-ul includea și NOT NULL PostgreSQL18, comparându-le cu setul separat de constraints c/f/p/u. FAIL păstrat |
| Migrare/producer PG, tentativa2 | exit0,4PASS; filtru identic frontierei de constraints din consumerul de schemă. Dovadă pentru upgrade/DDL și producer, nu copil/inbox cap-coadă |
| Cleanup DB | Ambele familii terminate; runnerul a citit DB/rețea/socket proprii absente, uncertain=false; datele păstrate |
| Distribuție patch | 15 originale/patched validate; git apply/reapply exit0 și hashes egale. Corecțiile contextului gol din diff sunt metadata, nu source changes |

Comenzile PG folosesc exclusiv `ops/run_test_db_gate.py:prove_private_fixture("test-contract-method-pg", "/home/kali/.local/share/omnis-toolchains/bin/uv", 600)` și toolchain-ul fixat. Logurile private rămân în scratch; nici DSN, capability sau credentiale nu sunt copiate aici.

## Istoric de remedieri — FAIL-urile sunt păstrate

### Remedieri după primul review și QA reală

Reviewul independent `B06b-CONTRACT-PURE-v4-normative-snapshot1` a cerut schimbări: **N1-F01**, producerul records refuza `CONTEXT_OVERFLOW`; **N1-F02**, RuntimeHost refuza orice final v4 SUCCEEDED deoarece cerea încă BLOCKED. Ambele sunt defecte de produs, nu simple lipsuri de dovadă.

- F01: schema rezultatului reutilizează `$defs` locale pentru Ref, lista de refs, rezultatul metodologic și identitatea bound. Draft 2020-12 aplică și constrângerile-sibling ale `$ref`. Headerul, ordinea/cardinalitatea, refs exacte, câmpurile obligatorii/necunoscute, DONE, CHECK_ONLY și limitele nu sunt eliminate. Plafonul agregat **65536** rămâne neschimbat; seed-ul și inputul QA records rămân aceleași. Măsurările intermediare 65816/65732/65603 încă refuzau; reprezentarea finală are **65418 bytes** și produce assignmentul real PG. Refuzurile istorice nu devin PASS retroactiv.
- F02: terminalul așteptat este SUCCEEDED exclusiv pentru v4; cold v1–v3 păstrează BLOCKED și comparațiile de binding/root/entries. Reproducerul independent cu peer substituit a trecut de la exit1 la **exit0**, v3 și v4 acceptate pe aceeași cale. Acesta certifică consumerul de wire SOURCE, nu autenticitatea copilului.
- QA reală a avansat la startup/owner. Prima tentativă post-F01 a refuzat `AF_UNIX path too long`: numai fixture-ul a primit un leaf scurt propriu sub TMPDIR. Tentativele următoare au păstrat `TASK_INDETERMINATE`/exchange unavailable înaintea metodei. Profilarea a fost restrânsă la evenimentele folosite, nu s-au prelungit granturile. Un marker open din diagnostic era citirea propriului bootstrap de traceback după SIGTERM; s-a permis numai acel fișier exact, nu credentiale sau un home suplimentar.
- Stackul nativ a arătat prima încărcare `run_agent → model_tools → discover_builtin_tools` înaintea constructorului: importul listează întregul inventar stock, deși helperul importat este folosit numai de CLI list-tools. RED SOURCE a confirmat importul în modul inert. Fixul minimal păstrează importul stock în afara modului inert și refuză explicit helperul în modul inert, fără autoload de tools/plugins. **10 controale SOURCE PASS**, iar patchul cu aceleași 15 fișiere a fost reaplicat/hash-verificat; patch SHA256 `2decfa157e01475c0f706cf34706c591015dff5ddbe094cd7544faf9b767492d`. Tentativa PG după fix rămâne FAIL la prima încărcare; nu afirmăm că numai discovery explica toate timeouturile.
- După ultima schimbare de produs: `make check-runtime` **exit0, 421 pytest + 6 AST, Ruff0/mypy15**. Runnerul existent `contract_method_native_probe.py` pe pinul complet, home nou, **exit0 / 14 teste / effects=[]**, inclusiv read/tool real în AIAgent, replay și refuzuri. Frontiera este SOURCE cu assignment/authority de fixture, nu instalat și nu consumer PG cap-coadă.
- Fixture-urile PG ale tentativelor părintelui au cleanup/readback propriu DB/rețea/socket absente, uncertain=false; datele/logurile private sunt păstrate. Nu se copiază tracebacks brute, DSN sau capability în Git/chat.

La acel checkpoint, reviewurile și traseul PG complet erau NOT_RUN/BLOCKED. Datele și afirmațiile anterioare rămân istorice, nu se transferă la probele ulterioare.

## Consumerul real și adjudecarea snapshotului 5

- **QA12 PASS_SOURCE_SCOPED:** runnerul existent `prove_private_fixture("test-contract-method-native-pg", "/home/kali/.local/share/omnis-toolchains/bin/uv", 600)`, exit **0**, **1 pytest PASS în 20.96s**. Qualify/Publish pe seedul records nemodificat → selection NO_MODEL/context/input/prepare → owner/client/Host/Peer stdio reale → AIAgent real → read și două transformări PURE → rezultat/receipts autentice → persistare → MethodCheck COMPLETE → inbox/readback/replay/reconcile și duplicat post-Stop. Observație: AIAgent1/read1/handlers2, TaskResult1/receipts3/artifacts2; fără sink/effect interzis observat pe canalul finit Python. Numai workerul pregătirii documentare este un prerequisite double declarat. Aceasta nu este proba INSTALLED sau de sandbox OS.
- Fixture-ul menține **lease-ul real**, cu `InstanceService.heartbeat` pe același owner/epoch și îl oprește înainte de Stop. Nu schimbă TTL sau deadline-uri. Tentativa11 refuza corect LEASE_LOST când fixture-ul nu întreținea ownerul; nu era motiv de slăbire a guardului. Profilarea include adaptorul pentru handler census și separă metoda publică AIAgent(self) de helperul de implementare(agent).
- Tentativa10 a avansat la copilul real, dar a rămas în teardown: pe Python3.13 `Server.wait_closed` așteaptă și transporturile active. Runnerul exact a primit TERM prin pidfd, a încheiat **130**, apoi a verificat familia/DB/rețeaua/socketul absente, uncertain=false. Reproducerul idle UDS: RED Timeout0.5s → `close_clients` înainte de wait → GREEN **15 teste host**, EOF/unlink/lock reuse reale. Nu se revendică handler breadth sau containment.
- **SEC3-F01:** reviewul security3 a demonstrat writer/reader păstrate după anularea v4 `_exchange`. Părintele a reprodus RED la owner după send pe UDS real; fixul închide canalul și reridică excepția în interiorul fence-ului, fără al doilea grant/resend și fără resetarea intenției comise. GREEN **3 teste owner**, Ruff/mypy2 exit0. DB/fence/grant în acest negativ sunt doubles SOURCE, nu dovadă PG de anulare.
- După ultima editare de produs: `make check-runtime` **exit0, 422 pytest +6 AST, Ruff/mypy15**. Verificarea ad-hoc cerută a rulat **3 teste PASS/exit0** pe schema partajată, UDS exit și owner cancellation; helperul propriu a fost șters după attestation prin FD/conținut. Aceasta nu înlocuiește canonicalul.
- Două reviewuri complementare au verdict **APPROVED_SCOPED** pe aceleași **47 hashes**, părintele confirmând lipsa driftului înainte de commit: `B06b-focused-independent-security-snapshot5` / SHA256 `c87b595053a8275a9c6d6fa799c8555c5904b1da282b421674cbe057b8229fe7`, și `B06b-CONTRACT-PURE-normative-snapshot5-focused-independent-review` / SHA256 `a3c61d6896cc017dcb0858d579270fa9c916ae5b4f6694b411f56ec96a1d98e9`. Au închis scoped N1-F01/F02, SEC3-F01 și exit-ul hostului; reviewerul security a reprobat bytes vechi RED și bytes curenți GREEN pe ambele defecte de cleanup. Raportul complet și limitele sunt păstrate în scratch; concluziile adjudecate sunt aici.
- QA12: cleanup/readback DB/rețea/socket proprii absente, uncertain=false, date păstrate. Snapshotul executat/reviewed are aceiași bytes ca commitul `fb97c8e` și cele două prerequisite commits. Canonicalul exact solicitat este pornit ca `proc_85e6150485ed`; **IN_PROGRESS, nu PASS**. Probe focalizate și review nu schimbă FAIL-urile canonicale istorice.

## Restul B06b/P2 rămâne deschis

Nonempty CriterionBinding/CriterionResult/done_when/return_when și predicatele calificate, M1/M2, restart receive-only/lost reply și primul rezultat nou tardiv HELD nu sunt închise de acest tracer. Duplicatul post-Stop nu este primul late-held; readback/reconcile în procesul curent nu este restart real. Capture are probe SOURCE reținute, nu noul journey PG records. Descriptorul checkerului nu probează independent closure-ul implementării sale, iar migrarea nu are istoric nonempty demonstrat. INSTALLED și P2-live sunt NOT_RUN. B06c/B06m reserve→SENT→transport/UNKNOWN și P4a-minim rămân în ordinea planului; fără cont/model/target/r1/adopție/push sau închiderea globală P2.
