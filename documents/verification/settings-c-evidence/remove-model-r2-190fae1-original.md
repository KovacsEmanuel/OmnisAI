# R2 — re-review focalizat 190fae1, read-only

## Identitate BEGIN / scope

- Root `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`.
- HEAD `190fae18e57e115a8a86559cec386b9ea147fd4b`; tree `42f33c5a788203eaf4a7d95fc8fb8e88b713f7c5`.
- Tracked/index clean; numai cele trei untracked preexistente: `api/.venv`, `tools/development/anti-slop/node_modules`, `web/node_modules`.
- Verificare directă: toate cele53 blob/SHA256 din `remove-model-proof-freeze-190fae1.json` corespund; diff-ul față de c4d465c conține numai cele10 fișiere test/fixture/wiring declarate. `git diff --exit-code c4d465c..HEAD -- api/src cli/src web/src` și `git diff --check c4d465c..HEAD`: exit0.
- Compun aprobarea SOURCE originală R2 pentru produsul neschimbat; nu redeschid scope-ul R1. Original R2 citit: `/home/kali/OmnisAI/documents/verification/settings-c-evidence/remove-model-r2-c4d465c-original.md`, SHA256 `ab95c8275d2847e04fd9a2259346f228f6205298d550bdfde126925d1fcfd23a`.
- README CURRENT/map păstrează READY istoric; autoritatea mandatului curent rămâne operator UNAVAILABLE/RECOVERY_REQUIRED, fără recovery autorizat. Acesta nu este un raport runtime al operatorului.

## Verdict

**SOURCE_ADMITTED_FOR_NARROW_REMOVE_QA**, strict pentru targetul existent nou `test-settings-remove-ui-pg`, pe aceste bytes și fixture fresh izolată. Niciun nou blocker de siguranță/compatibilitate confirmat pe callerul browser. QA browser rămâne NOT_RUN; admiterea SOURCE nu presupune că QA trebuie să fi trecut deja.

**R2-P02 CLOSED_SCOPED. R2-P01 PARTIALLY_CLOSED: overlapurile reale sunt probate; rămâne un gap concret al oracle-ului de atribuție no-write în Start-first. R2-R01 rămâne BLOCKED_OPERATOR_UPGRADE.** Gap-ul de probă P01 nu este defect de produs demonstrat și nu interzice QA browser distinctă, fără worker activ.

## R2-P01 — overlap real acceptat; atribuție incompletă

- `api/tests/test_model_test_v2.py:978–994`: bariera este în interiorul `original_admission(expected, holder, fencing_epoch)`, nu în locul lui. Callerii existenți păstrează lockul Settings comun; `InstanceService.admission:632–641` validează owner/epoch/expiry, stop fence și generation înaintea yield și owner/expiry după. Snapshotul primului writer este făcut după tranzacție, înainte să se elibereze lockul exterior.
- `:997–1024`: al doilea task HTTP este pornit cât timp primul este ținut; callbackul LocalControl al celei de-a doua cereri semnalizează `arrived` înainte de release. Sunt cereri concurente reale, nu două apeluri secvențiale. Toate cele șase ordini sunt prezente și au motivele corecte: Selection-first MODEL_IN_USE, Remove-first MODEL_NOT_REGISTERED, Start-first OPERATION_ACTIVE, Remove-first NOT_FOUND, ambele SaveModels CAS REVISION_CONFLICT. Anti-resurrection și census complet pe denials fără worker sunt prezente.
- Cancel `:1087–1101` este după întoarcerea `overlap`, care restabilește admission/callbackurile în finally; nu așteaptă sub bariera/lockul ținut. Readback FINISHED este păstrat. Corectarea așteptării E2 după Testul real nu modifică produsul și nu elimină controlul NOT_FOUND înaintea primului Test E2.
- Proba executată de autor, citită fără relansare: summary-ul filtrat strict din gate este `4 passed in 19.53s`; `gate.log.result.json` are schema_version1/code0/family_drained=true. `remove-proof-pg3.log` confirmă targetul și owned cleanup absent/networks_absent/socket_absent=true, uncertain=false. Nu am afișat logul raw sau DSN.

### P01 rămas — MEDIUM, proof gap, nu bug de produs

**Loc:** `api/tests/test_model_test_v2.py:1029–1034` și lipsa atribuirii în ramura Start-first `:1082–1101`.

**Scenariu:** când primul writer este entry Test start, oracle-ul citește13 tabele dar compară numai cele7 `provider_*`. Cele6 tabele model/operation/dispatch sunt excluse integral, nu doar rândurile/schimbările legitime ale operației admise. Un rând model_record fără legătură cu Start, ori o schimbare în istoricul unei alte operații, nu este detectat de această ramură. Variabilele existente model_opens/model_writes/handed și evenimentele SENT nu sunt verificate pentru această cursă, care revine înaintea aserțiunilor altor scenarii.

**Control inert executat:** am compilat/executat exact nodul AST `if` de la1027–1034 cu census13, un delta neatribuit în `model_record_v2` și niciun delta provider. Exit0: `EXACT_ORACLE_NEGATIVE_CONTROL: unowned model_record_v2 delta ACCEPTED by lines1027-1034`; 13 tabele citite/7 comparate. Este control sintetic al oracle-ului, nu efect SQL ori reproducere de bug de produs.

**Remediu minim:** în același fixture/oracle, atribuie delta model/operation/dispatch operației Start admise și referințelor ei; istoricul străin rămâne identic. Leagă eventualele SENT/relay/sink observate de acea operație (zero este legal dacă Cancel câștigă înainte de send), fără a excepta tabele întregi. Folosește contoarele deja existente; fără runner/helper nou și fără a ține Cancel sub lock. Re-review/rerun numai proba afectată, nu canonical sau legacy Settings.

## R2-P02 — CLOSED_SCOPED

- `cli/tests/test_status.py:25–49` izolează HOME/config/state/runtime și restabilește mediul prin patch.dict; runtime fixture corespunde căii reale. `test_installed_pointer_schema.py:64–71,117–125` izolează și config, iar subprocessul este sibling `omnis` al interpreterului.
- Verificare directă read-only a artefactelor existente: toate28 fișierele Python CLI sunt byte-equal între candidat, wheelul privat și site-packages din `/home/kali/.hermes/cache/scratch/remove-proof-cli-venv`. Shebangul siblingului indică exact acel venv. Niciun build/install relansat.
- `remove-cli-proof4.log`:101 execuții unittest/16.892s/OK, grupul celor8 module declarat. Este regresie scoped pe artefactul corect, nu full installed release acceptance și nu rescrierea vechiului67/11FAIL. Erorile UDS/runtime ale proof3 și încercările vechi rămân păstrate.

## Preflight noul caller browser — admis SOURCE

- Makefile: target dedicat cu build-web, fixture obligatorie, exact un node-id `entry_remove_ui`, opt-in separat `OMNIS_SETTINGS_REMOVE_UI=1`; choices runner și guardurile unsafe Make sunt extinse, nu ocolite. Agregatul `test-e2e` păstrează vechiul settings-models și adaugă Remove. Scenariul vechi32/2Starts2Cancels nu este înlocuit și nu a fost relansat aici.
- Runnerul păstrează pin/deadline/owned-family cleanup și mediul allowlisted. Overrides ambientale OMNIS_B06B nu ajung în gate; `own_source=True` selectează sursa candidatului prin callerul existent.
- Fixture-ul pregătește18 intrări și un istoric real prin peer TLS local înaintea browserului, apoi verifică fără trafic nou; driverul este separat de vechiul journey. Census13 la restart/readback nu exclude tabele. Fluxul/oracle-ul UI detaliat aparține reviewului R1; nu dublez acel audit.
- Riscul anterior de `ssl.create_default_context` monkeypatch cu semnătură incompatibilă **nu există în bytes actuali**: fixture-ul nu înlocuiește această funcție; contextul TLS este dat explicit ModelSender. DNS/socket patches sunt încă proces-wide și au fost verificate pentru callerul incidental real `wait_api`.
- Control inert cu HTTPX/httpcore instalate în API venv: constructorul real `httpx.Client(base_url=origin, trust_env=False, timeout=0.5)`, apoi GET `/health/ready` pe socket Mock fără creare/conectare/send de socket real, folosind exact funcțiile AST controlled_dns/controlled_send ale fixture-ului. Rezultat200/dashboard_ready=true; getaddrinfo real cere `('127.0.0.1',18765,0,SOCK_STREAM)` fără kwargs, admis de ramura entry_remove_ui; connect țintește loopbackul exact, send este acceptat și nu este atribuit upstreamului. Host străin este refuzat. SSL are semnătura standard inclusiv cafile/capath/cadata. Acesta verifică biblioteca/callform, nu launch/readiness/browser live.
- Prima comandă inertă a avut SyntaxError de quoting înainte de execuție; comanda corectată de mai sus a trecut. Nicio concluzie de produs din acea eroare.

## Limite / identitate END

HEAD/tree și tracked/index clean reconfirmate la final identice cu BEGIN; cele trei untracked preexistente rămân. Singurul fișier creat de reviewer este acest raport scratch; fără editări repo/config/skill, commit/push, PG/browser/build/install/native/provider/model/operator/service/migrare sau citire de configurații/credentiale/cookies/protected files. Reticle NOT_INTEGRATED/NOT_RUN; Chisel BLOCKED_NO_GO.

R2-R01 installed0016→0017 rămâne BLOCKED: wheelul privat nu autorizează upgrade-ul aceleiași instanțe, nu repară release identity și nu falsifică metadata. Legacy Cancel409/default-web2FAIL/counter2 și canonical5400NOT_RUN rămân neschimbate; fără T2. Părintele adjudecă integrarea și gap-ul P01.

Neexecutat: QA browser/PG nouă, installed lifecycle/upgrade sau recovery operator. Risc rămas: Start-first oracle-ul actual nu certifică atribuția no-effect integrală, chiar dacă toate cele șase ordini au trecut.
