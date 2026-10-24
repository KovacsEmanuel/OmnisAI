# Review independent R2 — SENT recovery, be72942

## Verdict

**APPROVED_TEST_DELTA_SCOPED — fără findings concrete noi în delta examinată.** Aprobarea privește siguranța și fidelitatea probei la frontiera **installed API component process boundary**, nu acceptarea finală T1 și nu QA independentă executată. Produsul, manifestele și dependențele sunt neschimbate. Candidatul poate merge la adjudecarea părintelui și etapa QA admisă separat.

**Findings:** `[]`. Nu există un defect demonstrat pentru care să cer remediere în aceste două fișiere. Limitele explicite de mai jos nu sunt redenumite defecte și nu cer alt harness/framework.

## Identitate și mandat

- Checkout: `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`, curat la început și la final; branch `impl/t1-sent-recovery`.
- Bază: `f26beb4e9f7611dbec0b0c1a15f03e1761fc8317`.
- HEAD: `be72942d82dfa6caf0c1c42c095306a5e33eaa81`.
- `api/tests/installed_sent_probe.py`: blob `cc23c4b1db12a0583966ca0bb9bdda75bf7626ec`; SHA256 `e3050cf8d148d5a575eddf223afa6ed9f047ac6ae872cd4572ebd6556d55e093`.
- `api/tests/test_model_test_v2.py`: blob `917267660f2f65e0fe2505955927892118cdb593`; SHA256 `d2f5fbf7c4e293ab5831bdb0cd0e4393a2c62f5e2234b2d185c02b7c3c9fe92f`; delta nouă de la linia1002.
- Identități confruntate cu `sent-freeze.json`; diff numai aceste două căi. `git diff --check f26beb4..be72942`: exit0.
- Review read-only: cod, callerii afectați și dovezi deja existente. Nicio suită/test QA, PG, build/install, serviciu sau apel provider lansat. Singura scriere este acest raport original, în afara checkoutului.

Cerință → consumer → risc → decizie: crash după SENT comis → `ApiKeyModelTest.run/reconcile` din wheel importat normal → resend, succes inventat, scăpare provider/secret sau cleanup fals → acceptarea ori refuzul **probei restrânse**, fără închiderea frontierelor mai largi.

## Constatări pozitive, legate de cod

1. **Seam separat de produs/distribuție.** Helperul și `PROBE` sunt în `api/tests`; buildul normal selectează `omnis` (`api/pyproject.toml:1–6`). Instalarea este offline/no-config, export locked și sync require-hashes (`installed_sent_probe.py:18–60`). Copiii folosesc Pythonul venv, `-I -B`, cwd privat și mediu allowlist, fără PYTHONPATH ori credentiale ambientale (`test_model_test_v2.py:1030–1048`). Proba verifică mulțimea/hashurile modulelor și originile importurilor (`installed_sent_probe.py:91–103`). Readbackul meu al ambelor venv-uri păstrate confirmă **113/113 module identice cu sursa**; helperul nu este instalat. Nu există switch/seam nou în producție.

2. **Metadata sintetică explicită, nu falsificarea ledgerului.** Refuzul inițial cere `CAPABILITIES_REQUIRED`. Numai metoda `metadata` a instanței sender este înlocuită temporar; fixture-ul intră în guardul real, iar refreshul real produce capabilities/receipt READY (`installed_sent_probe.py:175–197`; runtime `model_test_runtime.py:475–595`). Nu sunt injectate rânduri SENT/outcome prin SQL de test. Secretul este literal sintetic, seiful și directoarele de chei sunt fresh și private; DSN-ul fixture-ului trece prin stdin, nu argv.

3. **Cut real înainte de SDK și control negativ real al tripwire-ului.** `sys.monitoring` observă intrarea codului original `ModelSender.send`; producerul este SIGKILL, celelalte moduri ies79 la orice intrare send, metadata originală iese80 (`installed_sent_probe.py:114–135`). Testul cere exit79 și zero schimbări DB/relay pentru negativ, apoi exact `installed → ready → send_entry` și exit `-SIGKILL` (`test_model_test_v2.py:1105–1111`). În runtime, tranzacția RUNNING/SENT se încheie înainte de decriptare/send (`model_test_runtime.py:737–748`). Censusul pe conexiune separată după moarte verifică SENT comis, fără outcome și fără settle (`test_model_test_v2.py:1112–1142`). Nu este simplă excepție Python ori abandon de task.

4. **No-provider-IO pe traseul concret examinat.** Copilul refuză DNS și socketuri non-UDS (`installed_sent_probe.py:106–112`). Relay-ul host SOURCE primește guard test-only ce admite exclusiv FENCE/DRAIN și păstrează validarea originală (`test_model_test_v2.py:1090–1103`). În callerul real, validarea este înaintea DNS/connect și a citirii corpului WRITE (`cli/src/omnis_cli/model_relay.py:88–101,124–173`). Astfel nici regresia tripwire-ului send nu permite OPEN/WRITE către provider pe acest traseu. Acesta este un guard de test pe cod trusted, **nu sandbox OS general** și nu dovadă pozitivă TLS/SDK/live. Nicio canary/date private nu sunt trimise providerului de această probă.

5. **Recovery fără readmisie sau resend.** Se așteaptă expirarea reală a lease-ului, fără mutation/release shim (`test_model_test_v2.py:1143–1156`). `InstanceService.acquire` închide admission la owner-loss și avansează epoch (`service.py:309–344`); fiecare recovery verifică admission închis. `reconcile` drenează scope-ul moștenit înainte de settlement și nu programează work (`model_test_runtime.py:74–143`). Sunt cerute UNKNOWN/OWNER_LOST, usage UNKNOWN, output ABSENT, valori observate/cost/tokens nule, replay identic și conflict la payload schimbat (`installed_sent_probe.py:204–225`). Censusul cere append-only pe istoricul afectat, un singur operation/dispatch, apoi al doilea proces recovery cu view identic și **numai supervisor_lease schimbat**, fără al doilea FENCE/DRAIN (`test_model_test_v2.py:1157–1183`). Apelurile `start/refresh` de recovery sunt replay receive-only, nu autorizări noi.

6. **Cleanup și scurgeri în scope.** `subprocess.run(timeout=20)` așteaptă/reap copilul, iar SIGKILL închide întregul proces producer. Recovery închide sender, eliberează lease și dispose engine; părintele închide și așteaptă relay-ul cu timeout și cere socket absent (`installed_sent_probe.py:227–230`; `test_model_test_v2.py:1040–1049,1184–1188`). Listenerul real anulează/așteaptă clienții și refuză drain incert (`cli/src/omnis_cli/forwarder.py:53–74`). Fixture-ul IPC privat este eliminat de `TemporaryDirectory`; DB este cea disposable atestată, nu una arbitrară (`api/tests/conftest.py:22–25,46–80,114–156`). Nu am găsit în delta nouă o cale concretă spre cont/cheie/date ale operatorului.

## Dovezi citite, nu rerulate

- Logul original `dev-tmp/db-5299334083d4430e/gate.log` arată comanda țintei și **71 passed in116.74s**. `sent-pg-author-attempt2-exit.json` consemnează exit0. Acesta este rezultatul autorului pentru ținta întreagă, nu71 probe noi și nu execuția reviewerului.
- Am recalculat SHA256 și parsarea etapelor pentru **8/8 stdout** enumerate în FREEZE: toate coincid; toate cele8 stderr au0bytes. Outputurile recovery păstrează FINISHED/UNKNOWN/OWNER_LOST/UNKNOWN/ABSENT; nu conțin literalul secret sintetic sau `canary`. Nu am citit fișierele de chei/seif.
- Cele8 PID-uri proprii din FREEZE sunt absente acum din `/proc`. Nu am scanat/oprit alte procese.
- `sent-pg-author-attempt2.log` păstrează `network_none=true`, exit0 și readback autor `absent=True networks_absent=True socket_absent=True uncertain=False`, date reținute. Nu am reinterogat Docker/PG; cleanupul containerelor/networkurilor rămâne **readback înregistrat al autorului**, nu nouă QA independentă.

## Limite și dispoziții

- **R2-NEW-01 final rămâne OPEN**: testul nu execută DNS/connect/WRITE/TLS și nu dovedește frontiera finală Cancel/Stop post-ACK a supervisorului normal instalat. Nu închide acel finding prin FENCE/DRAIN pe un relay fără data-plane activ.
- Nu este startup/restart normal al întregului supervisor instalat, test web/API public de auth, positive SDK/provider outcome/usage, crash după handoff upstream sau istoric installed exhaustiv. Readbackul UNKNOWN este corect pentru cutul de aici, nu succes de model.
- Contoarele istorice **PENDING/metadata=2** și **connect/write=2**, FAIL-urile și dispozițiile lor rămân nemodificate; nu au fost rerulate ori resetate.
- Reticle: NOT_APPLICABLE. Chisel: BLOCKED_NO_GO.
- Nicio implementare, schimbare de skill/global, commit, push ori atingere/citire a `documents/Omnis_Notite_Originale.html`.

**Predare:** reviewul delta test-only este aprobat scoped; acceptarea produsului și QA independentă rămân la părinte. Am omis QA/PG și frontierele neschimbate din afara mandatului. Riscul de raportare rămas este promovarea acestei probe restrânse la închidere T1/R2-NEW-01; acest raport nu o autorizează.
