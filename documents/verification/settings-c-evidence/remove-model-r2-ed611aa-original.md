# R2 — focused re-review ed611aa / bf0320a, READ-ONLY

## Verdict și dispoziții

**APPROVED_SOURCE_SCOPED / SOURCE_ADMITTED_FOR_AFFECTED_REMOVE_QA. Findings noi confirmate: niciunul.**

**R2-P01 CLOSED_SOURCE_SCOPED:** remediul închide reproducerul concret al oracle-ului Start-first (delta model_record neatribuită acceptată / comparație numai provider). Nu este certificare universală de absență a curselor și nu este acceptare independentă runtime. Proba afectată pe bytes curenți poate fi admisă separat; lipsa acestei QA nu este un blocker circular SOURCE.

**R2-R01 rămâne BLOCKED_OPERATOR_UPGRADE/HIGH**, separat și neschimbat. Nicio autorizare recover/upgrade/Start/migrare operator nu rezultă din acest review. R2-P02 rămâne CLOSED_SCOPED la dovada originală CLI privată, nu installed-release acceptance. Aprobările SOURCE API/CLI/storage/migrare0017/auth/limite originale și închiderile R1-P01/P02 se păstrează numai în scope-ul lor neschimbat.

## Identitate BEGIN / scope

- Root analizat: `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`.
- HEAD `ed611aa40c90f62f4f511cc1951a68970e2ba51b`; tree `38463d72bb4271bc11ec6f05074be4cf9d108ada`.
- BEGIN: tracked/index clean; untracked preexistente păstrate: `api/.venv`, `tools/development/anti-slop/node_modules`, `web/node_modules`.
- Bază: `190fae18e57e115a8a86559cec386b9ea147fd4b`; remediu test/oracle `bf0320a3b825866ae1c25df441c8e7f7db1812f2`. Comparat diff-ul complet API test; celelalte patru fișiere schimbate sunt UI/teste UI, atribuite R1.
- Freeze `/home/kali/.hermes/cache/scratch/remove-model-freeze-ed611aa.json`, SHA256 `663ba083b57e00dcee29471bf5aaf5a5b0e01594e0389e68d6892adf41b0047a`: verificare directă Python/hashlib + `git rev-parse HEAD:<path>`, toate53 bindings blob/SHA corespund. `git diff --check 190fae1..HEAD`: exit0; diff API/CLI source: gol.
- Original R2/190 citit și SHA256 reconfirmat: `/home/kali/OmnisAI/documents/verification/settings-c-evidence/remove-model-r2-190fae1-original.md`, `b85bf65322a4c26aadfac489adb2a8b528e4b05542bb3ef57775bbe868c16b36`.
- Citite AGENTS, CONTRIBUTING, CURRENT/map din candidat, contract arhitectură §5.2–5.3/Remove, team-slice și skillurile relevante. CURRENT/map ale candidatului păstrează READY istoric; mandatul actual și CURRENT al părintelui sunt UNAVAILABLE/RECOVERY_REQUIRED, fără recovery autorizat. Nu am consultat starea operatorului.

## R2-P01 — atribuție, referințe și istoric

| Criteriu | Sursă / constatare |
|---|---|
| Census integral, fără exceptarea tabelelor întregi | `api/tests/test_model_test_v2.py:787–816,1068–1111,1183–1203`: toate13 tabele sunt comparate; provider rows nu primesc excepție. |
| Rădăcină și dispatch ale Start-ului admis | `:974–1011`: Operation este validată din JSON pentru instance/operation exacte; Dispatch din payload JSON pentru același instance/operation, cu egalitate dispatch ID payload/coloană. `model_command_v2` este exceptat numai pe operation=command=Start identity și action=start. |
| Închidere pe Ref, nu substring de payload | `:1012–1066`: cheia exactă instance/id/kind/revision/digest; traversare numai pe câmpurile Ref enumerate ale producerilor. O valoare opacă ce conține operation ID nu conferă ownership. |
| Paritate cu producerii reali | `provider_model_test.py:55–83`: snapshot→capabilities→catalog_ref; `model_test_runtime.py:409–498`: Operation/config/input, scope/owner/permit/Dispatch; `:864–905`: outcome→scope/dispatch/requested/output. Câmpurile urmărite corespund producerilor, catalog/input/output rămân frunze. |
| Append-only și shared/foreign immutable | `:1068–1076`: toate rândurile existente model_record/model_command/op-event/dispatch/dispatch-event trebuie păstrate byte-equal chiar dacă apar în closure. Filtrarea foreign păstrează egalitatea exactă a celorlalte rânduri, inclusiv alte operații; catalogul shared nu poate fi rescris doar pentru că este referențiat de Start. |
| Pozitiv și negativ în consumerul existent | `:1186–1203`: quiet și overlap legal pe același helper; delta neatribuită este contestată în fiecare dintre13 tabele, inclusiv model_record cu operation ID numai ca payload bait. |

Nu s-a schimbat produsul API, schema, autoritatea, timeoutul, fereastra de lease sau serializarea produsului pentru a face oracle-ul verde. Defectul inițial datetime/JSON rămâne un eșec al observerului, nu RED de produs și nu dovadă de product race.

## Fazele reale și SENT / relay / sink

- `:1139–1147`: bariera rămâne în admission real, înainte de yield; primul snapshot este după commitul primului writer, încă în lockul exterior Settings. Producerul `model_test_runtime.py:499–501` publică workerul abia după întoarcerea admission, deci snapshotul inițial este admission/RESERVED, nu settlement.
- `:1166–1187`: a doua cerere ajunge înainte de release; gather așteaptă ambele răspunsuri. Oracle-ul compară snapshotul post-admission cu censusul post-refuz, înainte de Cancel. În acest interval permite progres numai pentru Start-ul cunoscut. Acesta este scope-ul no-write al refuzului; nu pretind că helperul este apelat din nou după Cancel.
- `:1207–1217,1260–1275`: overlap restabilește admission/callbackurile în finally înainte de Cancel; Cancel nu este cerut sub lockul/bariera ținută. Peerul poate rămâne suspendat la răspuns, apoi este eliberat, iar workerii sunt drenați.
- `:1252–1258,1278–1315`: baseline de contoare înainte de Start, apoi census settled după FINISHED/drain. Dispatchul este obținut din instance+operation cunoscute; SENT0/1 este numărat pentru acel dispatch. Scope-urile OPEN/WRITE observate trebuie să aibă instance și ID exacte; conectările și requesturile la sink sunt cel mult SENT. Sinkul observat cere ruta POST și modelul fixture exact. SENT0 impune zero OPEN/WRITE/handoff/request; un handoff observat cere WRITE și SENT1. Numărul de send-uri ciphertext nu este confundat cu numărul requesturilor TLS.
- Instrumentele sunt cele existente: `:446–465` physical connect/send, `:483–505` relay OPEN și WRITE-ACK, `:240–252,324–325` request complet la peer înaintea holdului de răspuns. Counters acoperă observațiile de la baseline până la verificarea după drain, nu sunt o demonstrație separată de zero bytes post-ACK Cancel sau o probă universală pentru toate interleavingurile. Zero SENT rămâne legal dacă Cancel câștigă înaintea send-ului; nu am cerut forțarea unui SENT artificial.

## Verificări independente inerte executate

Fără import/execuție a testului integrat și fără socket/DB/browser: `PYTHONPATH=api/src api/.venv/bin/python -B -c ...`, extragere/compilare a nodului AST exact `unchanged_except_start` și DTO-urile reale instalate.

Ieșirea finală, exit0:

```text
EXACT_AST_POSITIVE quiet/legal progress PASS
EXACT_AST_NEGATIVE foreign/bait delta 13 of 13 REJECTED
EXACT_AST_NEGATIVE existing referenced record/valid dispatch update REJECTED
EXACT_AST_NEGATIVE foreign operation update REJECTED; SOURCE_ONLY no network/PG/browser
```

Controlul folosește census sintetic minimal, nu rânduri PG inventate drept dovadă live. Separat, blocul AST exact `:1279–1315` a trecut SENT0/no-I/O și SENT1/relay+sink cunoscute și a respins: scope relay străin, SENT duplicat, conectare suplimentară, request sink străin și handoff fizic fără SENT. Acel Python a terminat exit0 înaintea comenzii distincte de filtrare a logului.

Încercări auxiliare nereușite, păstrate ca limite ale probei reviewerului: selecția AST inițială a întâlnit altă atribuire `tables`; o mutație Dispatch a fost respinsă mai devreme de DTO cu ValidationError, nu AssertionError-ul așteptat; deepcopy inițial al namespace-ului includea modulul json. Corectate numai comenzile inerte ale reviewerului, fără editarea vreunui fișier. Primul regex de summary nu a găsit linia; filtrul numeric corectat a confirmat numai `4 passed in 32.33s`. Nicio concluzie de produs nu provine din aceste erori.

Dovada existentă a developerului, citită fără relansare: target `test-settings-remove-pg`, public log `/home/kali/.hermes/cache/scratch/remove-r2-attribution-pg-final.log`; receipt `/home/kali/.hermes/cache/scratch/db-a5e5b7315ac0443f/gate.log.result.json`: code0/family_drained=true; summary filtrat strict4PASS32.33s. Public cleanup: container/network/socket absente, uncertain=false. Nu am afișat raw gate/DSN și nu transform acest rezultat în QA independentă proprie. Checkpointul păstrează primul FAIL datetime și încercările ulterioare.

## Admitere QA / limite

R2 admite SOURCE proba afectată pe runnerul existent, target `test-settings-remove-pg`, bounded600, fixture fresh izolată și cleanup/readback exact; nu un harness nou, alt grant, deadline mărit ori rerun global. QA UI `test-settings-remove-ui-pg` este distinctă și admisibilă din perspectiva R2, condiționată de verdictul complementar R1 pe UI/focus. Nu cer ca rezultatul runtime care trebuie produs de QA să existe deja pentru admiterea ei. Developer109component/PG/browser și parent QA190 rămân dovezi separate, nu acceptare independentă a UI noi.

Legacy default-web2FAIL/Cancel409/counter2, canonical≤5400s NOT_RUN și R2-R01 rămân neschimbate. Fără T2, installed lifecycle/upgrade/recovery, provider live, model/Refresh nou, install/build, servicii, push sau acces la credentiale/protected files. Reticle NOT_APPLICABLE în scope-ul R2 SOURCE; Chisel BLOCKED_NO_GO.

## Identitate END

HEAD/tree identice cu BEGIN, reconfirmate direct la `2026-10-29T16:20:33Z`; tracked/index clean și aceleași trei untracked preexistente. Singurul fișier creat este acest raport scratch; nicio editare repo/config/skill și niciun commit. Integrarea/adjudecarea și închiderea runtime aparțin părintelui după reviewul complementar și QA afectată pe bytes curenți.

Neexecutat: PG/browser independent, full canonical/CLI101, UI/focus R1 sau operare operator. Riscul rămas este lipsa QA independente pe remediul curent, nu un product race demonstrat ori permisiune de upgrade.
