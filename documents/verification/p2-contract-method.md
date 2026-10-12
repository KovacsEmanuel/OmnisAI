# B06b — metoda nativă CONTRACT/PURE (WIP)

Autoritate: plan §7.1 și contractul B06b C01–C12; nu este un plan sau audit nou. Baza de lucru este `abac977cf841429a65b4304d9c7abf01233dd3d5`. Codul integrat este încă necomis și în review; acest registru nu închide B06b, G02-inert sau P2.

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

## Gates rămase

### Remedieri după primul review și QA reală

Reviewul independent `B06b-CONTRACT-PURE-v4-normative-snapshot1` a cerut schimbări: **N1-F01**, producerul records refuza `CONTEXT_OVERFLOW`; **N1-F02**, RuntimeHost refuza orice final v4 SUCCEEDED deoarece cerea încă BLOCKED. Ambele sunt defecte de produs, nu simple lipsuri de dovadă.

- F01: schema rezultatului reutilizează `$defs` locale pentru Ref, lista de refs, rezultatul metodologic și identitatea bound. Draft 2020-12 aplică și constrângerile-sibling ale `$ref`. Headerul, ordinea/cardinalitatea, refs exacte, câmpurile obligatorii/necunoscute, DONE, CHECK_ONLY și limitele nu sunt eliminate. Plafonul agregat **65536** rămâne neschimbat; seed-ul și inputul QA records rămân aceleași. Măsurările intermediare 65816/65732/65603 încă refuzau; reprezentarea finală are **65418 bytes** și produce assignmentul real PG. Refuzurile istorice nu devin PASS retroactiv.
- F02: terminalul așteptat este SUCCEEDED exclusiv pentru v4; cold v1–v3 păstrează BLOCKED și comparațiile de binding/root/entries. Reproducerul independent cu peer substituit a trecut de la exit1 la **exit0**, v3 și v4 acceptate pe aceeași cale. Acesta certifică consumerul de wire SOURCE, nu autenticitatea copilului.
- QA reală a avansat la startup/owner. Prima tentativă post-F01 a refuzat `AF_UNIX path too long`: numai fixture-ul a primit un leaf scurt propriu sub TMPDIR. Tentativele următoare au păstrat `TASK_INDETERMINATE`/exchange unavailable înaintea metodei. Profilarea a fost restrânsă la evenimentele folosite, nu s-au prelungit granturile. Un marker open din diagnostic era citirea propriului bootstrap de traceback după SIGTERM; s-a permis numai acel fișier exact, nu credentiale sau un home suplimentar.
- Stackul nativ a arătat prima încărcare `run_agent → model_tools → discover_builtin_tools` înaintea constructorului: importul listează întregul inventar stock, deși helperul importat este folosit numai de CLI list-tools. RED SOURCE a confirmat importul în modul inert. Fixul minimal păstrează importul stock în afara modului inert și refuză explicit helperul în modul inert, fără autoload de tools/plugins. **10 controale SOURCE PASS**, iar patchul cu aceleași 15 fișiere a fost reaplicat/hash-verificat; patch SHA256 `2decfa157e01475c0f706cf34706c591015dff5ddbe094cd7544faf9b767492d`. Tentativa PG după fix rămâne FAIL la prima încărcare; nu afirmăm că numai discovery explica toate timeouturile.
- După ultima schimbare de produs: `make check-runtime` **exit0, 421 pytest + 6 AST, Ruff0/mypy15**. Runnerul existent `contract_method_native_probe.py` pe pinul complet, home nou, **exit0 / 14 teste / effects=[]**, inclusiv read/tool real în AIAgent, replay și refuzuri. Frontiera este SOURCE cu assignment/authority de fixture, nu instalat și nu consumer PG cap-coadă.
- Fixture-urile PG ale tentativelor părintelui au cleanup/readback propriu DB/rețea/socket absente, uncertain=false; datele/logurile private sunt păstrate. Nu se copiază tracebacks brute, DSN sau capability în Git/chat.

Reviewurile complementare pe snapshotul exact curent sunt în curs. Traseul PG→owner→copil→MethodCheck/inbox complet rămâne **NOT_RUN/BLOCKED** după frontieră; numai producerul a avansat. Plafonul, deadline-urile și oracolele de metodă nu au fost slăbite. Următorul pas este consumerul de încărcare nativă, nu un alt input, verifier sau provider.

QA pe consumerul real PG→owner→copil→receipts→MethodCheck/inbox/readback și cele două reviewuri complementare exact-snapshot sunt pendinte. Native SOURCE nu devine INSTALLED și nici metoda PURE nu devine turn/inference. Formele contractate încă neacoperite, M1/M2 și criteriile nonempty rămân deschise până la probele lor. Full canonical final este NOT_RUN; FAIL-urile istorice nu sunt șterse. B06c/B06m owner reserve→SENT și P4a-minim urmează în ordinea autorizată. Fără cont/model/target/r1/adopție/push.
