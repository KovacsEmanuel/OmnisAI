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

QA pe consumerul real PG→owner→copil→receipts→MethodCheck/inbox/readback și cele două reviewuri complementare exact-snapshot sunt pendinte. Native SOURCE nu devine INSTALLED și nici metoda PURE nu devine turn/inference. Formele contractate încă neacoperite, M1/M2 și criteriile nonempty rămân deschise până la probele lor. Full canonical final este NOT_RUN; FAIL-urile istorice nu sunt șterse. B06c/B06m owner reserve→SENT și P4a-minim urmează în ordinea autorizată. Fără cont/model/target/r1/adopție/push.
