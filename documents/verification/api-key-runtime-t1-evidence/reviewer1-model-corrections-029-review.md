# R1 — re-review focalizat NON-RELAY, corecții ModelTest 029

**Verdict: APPROVED_CORRECTIONS_SOURCE_SCOPED.** Niciun finding nou blocant în delta admisă. Nu este aprobare T1, integrare, release/installed, browser sau canonical PASS. **R2-NEW-01 HIGH rămâne OPEN** și împiedică aprobarea întregului traseu de send/drain.

## Snapshot / ownership / limită

- Produs citit exclusiv din checkoutul frozen detached/clean `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-029`.
- HEAD `0299082dd652db35f533a22d2cd61f5629708935`; tree `67e357837033ffe1f1534d8ed77ccd7893f3241a`.
- Bază re-review `95a8bf94c18f7cca973ad771fa944d209aa28cd6`; checkpoint known-fix `63f26fb5ec2beb781763c588187225791524571c`.
- Delta Git reală 95a8→029: **16 paths, +990/−69**. Known-fix a avut 12 paths, ABCD 11 paths în parte suprapuse; acestea nu se adună drept 23 paths. Identitățile finale sunt în anexa de mai jos; toate cele 11 blob/SHA din `../logs/abcd-freeze.json` corespund independent fișierelor frozen.
- Main observat numai read-only: `562b12eb3cecc7eb5f418fe5fc76a0a2ff2a9ce3`, HTML untracked preexistent păstrat; fișierul protejat nu a fost citit. Nu am citit produsul mutable `runtime-src`; numele său apare doar în logurile istorice ale autorului.
- Cerință→consumer→risc→decizie: corecțiile concrete de parser/receipt/accounting/redacție/outage/recovery → API/control/owner/SDK + callerii reali web → efecte ambigue, date invalide/secrete, latch sau ID greșit → decide numai readiness SOURCE a corecțiilor pentru integrarea părintelui și următoarea QA admisă.
- Nu am rulat teste/probe de produs, PG/SQL/OCI, rețea/socket/provider, browser, native, instalare, citiri de mediu/credentiale. Am citit producerii/oracle-urile și ieșirile reale deja înregistrate; am executat numai Git read-only și verificări locale JSON/hash. Nicio modificare produs/test/docs/Git/skills; numai acest raport scratch.

## Reutilizare explicită, nu un nou audit integral

Rapoartele originale `../logs/reviewer1-model-core-95a8-review.md` și `../logs/reviewer2-model-core-95a8-review.md` rămân originale **CHANGES_REQUESTED** la 95a8. Reutilizez strict observațiile favorabile/semantica neschimbată în scope-ul lor: root/owned refs și store/migrare, imutabilitate, ordinea admission→SENT→SDK, config snapshot pin-uit, autentificare și limite existente, wiring Settings/drain, dependențe/topologie/distribuție. Nu reemit aprobare generală pentru aceste zone și nu transform observațiile SOURCE în probe installed/live. În modulele schimbate au fost recitite numai hunk-urile și callerii/ramurile afectate.

Nu s-au redeschis fixture breadth, stil, vechiul runtime ori întregul authority audit. Distribuția originală nu a fost refăcută/reseilată; nicio aprobare nu se transferă automat unui viitor bundle.

## Dispoziție pentru fiecare finding original și corecție admisă

| ID / alias original | Dispoziție | Cod și oracle pe bytes curenți |
|---|---|---|
| R1 K1 HIGH; R2 known #2 — Refresh exact receipt | **CLOSED_SOURCE_SCOPED** | `model_test_runtime.py:118–144,197–210,399–405`: request/result selectate după command ID, selection revision din cererea proprie pentru receipt, replay înaintea config/admission, read explicit fără operation projection. `model_test_routes.py:77–85,127–135` verifică identitatea; `ModelTestControl` refuză read cu două identități. Testul `test_model_test_v2.py:389–419,488–523,599–664` compară A după B, payload conflict, GET A și absent404, edit selecție, apoi replay/read A în proces OS nou; traffic rămâne exact, fără replay provider. |
| R1 K2 MEDIUM; R2 known #1 — strict POST JSON | **CLOSED_SOURCE_SCOPED** | `model_test_routes.py:93–104` partajează raw-body `unique_json_object`/`reject_json_constant` înainte de control pentru Start/Refresh/Cancel; callerii nu au bypass. `test_model_test_v2.py:305–365` trimite duplicates/NaN/±Infinity pe toate trei, cere422, zero comenzi owner/traffic și același census al celor5 tabele mutate. Validarea DTO/auth/body-bound existentă rămâne. |
| R1 K5 MEDIUM — Make flags / missing fixture | **CLOSED_SOURCE_SCOPED** | `Makefile:12–15,35–38` include exact noul target în guard și păstrează fixture denial înainte de pytest. `tests/development/test_test_db_gate.py:294–328` verifică `-n/-t/-q/-i`→exit2/mesaj exact și marker-shell fără efect, apoi lipsa fixture→exit2/mesaj exact. Logul păstrat `make-final.log` este1 test OK, nu PG. |
| R1 N1 HIGH — raw usage / settlement latch / public parity | **CLOSED_SOURCE_SCOPED** | `model_sender.py:283–306,327–340` extrage usage din JSON original și îl scoate înainte de validarea SDK; numai `type(v) is int` și0..9007199254740991 devine fapt. Negative/unsafe/bool/string/fraction rămân null, nu0; completion ACK valid rămâne COMPLETED cu USAGE_INVALID. `model_test_contract.py:141–143,171–173` strict bounds pentru Outcome/View; decoderul `modelTest.ts:9–12,36–37` are același interval și nullable. `model_test_runtime.py:698–731` păstrează PARTIAL/UNKNOWN, inclusiv reasoning valid independent; nu pretinde KNOWN pentru invalid usage. Oracle SDK real cu HTTPX MockTransport: `test_model_sender.py:124–178`,15 combinații; teste contract bounds, plus PG `negative_usage/unsafe_usage/coerced_usage/invalid_reasoning`: FINISHED/COMPLETED, null/PARTIAL, USAGE_INVALID, cost null, `not settlement_failed`, replay fără send (`test_model_test_v2.py:432–487`). |
| R1 N2 HIGH = R2-NEW-02 HIGH — secret echo la cutoff | **CLOSED_SOURCE_SCOPED** | `model_sender.py:333–335` redactează stringurile complete înainte de limita256 pentru model/id; textul este redactat înainte de retenția8192. `test_model_sender.py:85–121` probează512/0 și31/250 prin SDK. PG `secret_long/secret_cross`, `test_model_test_v2.py:438–451`, verifică modelul public exact și absența întregii chei/prefixului canary atât în toate payloadurile PG cât și în răspunsul public. Claim limitat la exact-secret echo; nu DLP universal. |
| R1 N3 MEDIUM = R2-NEW-03 MEDIUM — refuz CAS / unknown / Settings | **CLOSED_SOURCE_SCOPED** | `ModelTest.tsx:46–97`: pointerul propriu și markerul de refuz definitiv sunt persistate separat; numai read explicit cu404 pe exact acel ID + marker egal + read current reușit șterge pointerul refuzat. UNKNOWN/lost response nu primește marker și404 singur nu eliberează ID-ul, inclusiv după reload. Nu există resend automat; consent se resetează. `ProviderSettings.tsx:64–68` invalidează imediat `['private','model-test']` după Save, fără mutarea snapshotului. Runtime `:150–165` citește requested din ref-ul immutable, nu defaultul curent. Oracle `ModelTest.test.tsx:26–65,74–111`: invalidation explicită imediată (RED autentic după întărirea oracle-ului), snapshot/id active păstrate;409→reload→GET404→read latest/reset propriu, fără mutation suplimentară; lost-response→404 păstrează ID și blochează resend. |
| R2-NEW-04 MEDIUM — metadata outage / streaming sibling | **CLOSED_SOURCE_SCOPED** | `model_sender.py:226–249` normalizează explicit httpcore/httpx NetworkError/ProtocolError/TimeoutException atât la request cât și la consumarea răspunsului; `send:346–358` prinde și httpcore streaming errors, întorcând UNKNOWN sanitizat. SendDenied este ValueError și Refresh îl settlează normal (`model_test_runtime.py:443–513`); excepțiile DB/control neînrudite și CancelledError nu sunt blanket-caught. Teste `test_model_sender.py:19–82`: socket refuzat, ReadError/RemoteProtocolError/ReadTimeout din ResponseStream pentru metadata și send, RuntimeError/cancel propagation. PG `metadata_refused/metadata_eof` (`test_model_test_v2.py:366–399`) persistă FAILED/METADATA_UNAVAILABLE, fără latch/retry; Refresh nou explicit sănătos și receipt vechi neschimbat. Nu este afirmație că orice clasă de defect SDK este normalizată. |
| Noua corecție GET/Cancel response ID binding; observație R2 §72 | **CLOSED_SOURCE_SCOPED** | `client.ts:62–69,82–105`: GET exact op și Cancel compară operation_id; GET/POST metadata compară command_id și cer operation_id null. `ModelTest.test.tsx:67–72` respinge DTO altfel valid al altei operații pe ambele canale; getterul receipt are aceeași verificare explicită în sursă. Nu am cerut fixture breadth suplimentară. |

### Blockeri originali rămași explicit deschiși — fără închidere prin acest verdict

- **R2-NEW-01 HIGH — OPEN, în afara aprobării:** guard/drain local nu certifică sinkul fizic al relay-ului. Scenariul original DNS/connect/queued copy după Cancel/Revoke rămâne în raportul R2; `cli/src/omnis_cli/forwarder.py:349–409`, local `model_test_runtime.py:57–67`/`model_sender.py:360–364`. Remediul minim rămâne owner/epoch fence + ACK drain la relay, apoi re-review exact și actual-consumer negative. Nu am citit viitoarele editări relay și nu le aprob.
- **R1 K3 HIGH = R2 known #3 — OPEN/BLOCKED:** graful canonical API-key-only nu este adaptat; `Makefile:23` încă include check-runtime. Fixul Make flags nu închide această cerință. Canonical nou NOT_RUN; fără native/OAuth preparation sau skips pentru GREEN.
- **R1 K4 HIGH = R2 known #4 — OPEN/NOT_RUN:** testul OS-process `test_model_test_v2.py:599–664` pleacă din operație/receipt deja terminale și release ordonat. Demonstrează read/replay istoric finit fără resend, nu crash cu SENT nesettled, abrupt owner loss ori supervisor installed restart. Metadata PENDING owner-loss păstrează cele2 încercări SHUTDOWN_INCOMPLETE / GENERATION_CONFLICT, cauză neatribuită; nicio a treia rulare și nicio reclasificare PASS.
- **R1 K6 MEDIUM = R2 known #5 — OPEN/adjudicare părinte:** broad CLI FAIL istoric rămâne neadjudecat. Testele SOURCE/UI curente nu îl fac GREEN și nu justifică diagnostic nou fără reproducer relevant.
- Historical readers installed, first independent actual-consumer installed/browser și live provider/Orca sunt NOT_RUN aici; nu sunt aprobate prin readback-ul testului terminal SOURCE.

## Dovadă reală înregistrată, citită — nu rerulată de reviewer

Am citit codul producer/oracle după ultimele editări și următoarele ieșiri raw, nu doar numerele freeze:

| Comandă / artefact | Rezultat înregistrat | Limită |
|---|---|---|
| `TMPDIR=../m4 api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-model-test-v2-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 300` | `../logs/abcd-final-pg.log`: exit0; `../m4/db-f01c67b14e35492f/gate.log`:21 PASS/55.31s; receipt raw `{"schema_version":1,"code":0,"family_drained":true}` | Autor, private PG/TLS fixture SOURCE; nu relay real/installed/provider. |
| `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_model_sender.py api/tests/test_model_test_v2_contract.py -q --tb=short --basetemp=$TMPDIR/a4-final` | `../logs/abcd-final-source.log`:27 PASS/1.10s, exit0 în freeze | SDK + declared doubles și contracte; nu independent execution. |
| `npm --prefix web test -- src/app/ModelTest.test.tsx src/shared/api/client.test.ts src/shared/api/providerKeys.test.ts` | `../logs/abcd-final-web-tests.log`:3 files/28 PASS, exit0 în freeze | React/DOM test env, nu browser/visual/installed QA. |
| `make lint-api typecheck-api`; `make test-contracts`; `make lint-web`; web typecheck | Exit0 în freeze; citite API-quality, contract-generation/tooling/tsc, lint și final tsc logs | `make test-contracts lint-web` inițial exit2 la tsx lipsă DUPĂ contract/typecheck; remediere prerequisite locală înregistrată, apoi lint separat exit0. Nu normalizez tentativa eșuată. |
| `python -B -m unittest discover -s tests/development -p test_test_db_gate.py -k test_model_test_pg_refuses_unsafe_make_flags_before_recipes -v` | `../model-knownfix-evidence/make-final.log`:1 test OK, exit0 în freeze | Refuzuri Make în fixture/copii, fără DB. |

SHA-urile raw ale final SOURCE27, UI28, PG21 și receiptului PG au fost calculate și comparate cu freeze: toate identice. Cleanup-ul fizic este **reutilizat de la părinte**, nu reexecutat: `../logs/parent-model-abcd-readback.json` confirmă exact CID/rețea absente, socket gol, data/password păstrate fără citirea conținutului, code0/drained. `parent-model-knownfix-readback.json` și cleanup-readback-ul original păstrează cele7 fixtures și eșecurile; vechi10PG/30.20s și13UI nu sunt adunate cu probele curente.

RED→GREEN citit: usage15 FAIL→GREEN; echo2 FAIL→GREEN; outages4 FAIL plus control1 PASS→GREEN; GET/cancel/recovery3 FAIL→GREEN; Settings oracle întărit1 FAIL→GREEN. Primele oracle-uri Settings mascate de polling și eșecurile tsc/mypy/prerequisite sunt păstrate în freeze/loguri, nu șterse sau creditate ca probe green. Nu s-a cerut altă suită ori alt harness.

## Comenzi proprii / rezultat / incidente

- ORIENT în `/home/kali/OmnisAI`: `pwd; git status --short --branch; git rev-parse HEAD; git diff --stat` — exit0, main readonly de mai sus, untracked protejat preexistent.
- Frozen: `git status --short --branch`, `git rev-parse HEAD 'HEAD^{tree}'`, `git diff --stat`, `git diff --name-status`, `git diff --numstat`, diff-urile focalizate și log-ul 95a8..HEAD — exit0 după rezolvarea tokenului Git ambiguu.
- Prima comandă a folosit `95a8`, ambiguu între commit și blob: exit128, fără efecte. Am reluat cu commitul exact `95a8bf94c18f7cca973ad771fa944d209aa28cd6` / prefixul neambiguu `95a8bf9`; nicio identitate nu a fost presupusă din eșec.
- `git diff --check 95a8bf9 HEAD` — exit0; `git diff --quiet` și `git diff --cached --quiet` — exit0; status final gol, HEAD/tree nemodificate.
- Citiri locale source/tests/reports/logs/contract JSON și SHA256/blob compare — exit0; niciun secret real sau valoare password citită. Nu am folosit interpretere pentru execuția produsului și nu am rulat owner-loss harness.
- Reticle **NOT_INTEGRATED** pentru această revizuire UI SOURCE fără browser; Chisel **BLOCKED_NO_GO**. Nu sunt verdicte de reviewer suplimentare.

## Anexă — exact delta final 95a8→029

Bloburile și SHA256 de mai jos au fost citite/calculare din frozen, nu copiate orbește din handoff:

| Path | Blob Git final | SHA256 final |
|---|---|---|
| `Makefile` | `a546700c1782150563eefdc61bb092745e4c1fb3` | `8bcb52686f61dbdfe67fbbd50d0dcb2b48a18a894f5f23ec539438c201582fdb` |
| `api/src/omnis/modules/runs/model_test_contract.py` | `f465fa353ebf9f42baadf38f4b66ba56754e2501` | `354900679851958e08aea012ab50622a8429acb1b5611b336a964abf52de2968` |
| `api/src/omnis/modules/runs/model_test_models.py` | `44f83104ff95bedbc42d20f6e05e7b8f97314f1c` | `997f132206d912015895c1f213537213187a9d5ae156dfbe66bd9a52fdac181f` |
| `api/src/omnis/modules/runs/model_test_routes.py` | `edba7861a318d4ec6b4e9bb94d385af2d33c70f3` | `f55b596c73212eacb51bbf6b6e65bba88f27af12ad66c70e4ae9b3f43d0776df` |
| `api/src/omnis/modules/runs/model_test_runtime.py` | `dff032fa0efa28857a28ca2406d4ae17e8f32f8f` | `0048f2ea74c6f7dc36a09ec2332e8a59c9e6dfb729c6c3117efe8c12861c1a10` |
| `api/src/omnis/supervisor/model_sender.py` | `c078d55e8110c1bab44293490b2a6fcd7a8e76f8` | `990c7d1cf0080c5e5a2b72ca294106b8ba61121a4c651c9089bb5aca77bfe95b` |
| `api/tests/test_model_sender.py` | `e24f136570e661c73e082a1ab14e3f420958c826` | `1b7f1090d86855d939e54c3a221b4917c6078b2500cb0d21ac7ba6b9261327b3` |
| `api/tests/test_model_test_v2.py` | `86a0f5673d7b09209a0cd4c11ddbc792e005a785` | `1378fafda1cdd466dd3de1a7d9c086843ff16c427f06615553d435a64f9a21de` |
| `api/tests/test_model_test_v2_contract.py` | `7e5c6c86b8f237263c62eca970562fad5329a8a1` | `71c0b49e4a8e38cfeaee37310937dca45de0f56bd8d9678e93d49c44067181c0` |
| `contracts/omnis.openapi.json` | `b76ea664a83cb2a9934fbc0288928034c6764002` | `7c274d4021dead0d0bee0fe3b92f4c9fc19050469bdb1dfd1a6d83cef16a3d61` |
| `tests/development/test_test_db_gate.py` | `fc8ce56c40ed3cdced510ff2b0699f6e77cc0fb8` | `3aca5678be0b2acb1dc415b14154330f79280271cd11d37b48f4935e8c8501ed` |
| `web/src/app/ModelTest.test.tsx` | `056953b3e0202715b4cc1abcb958355be959da85` | `477181b1130448d170440f774e201e9f7459059c1dba0fafcab8af9f76c2548b` |
| `web/src/features/engagement/ModelTest.tsx` | `fd80f02cd5f5e2230bf93c6ecfce6b5f577daa7e` | `aaafbbd33270f499cfc64410c6918749b3a311a4b5f14df40029e0b14cf58103` |
| `web/src/features/engagement/ProviderSettings.tsx` | `0b60b7a0bb10dfc41cb96ee349016f0580ca04e4` | `d27ca1d7c6aa640c3cbe24444181f342e89b82d3c91eb62f9bab9d46e9a0c396` |
| `web/src/shared/api/client.ts` | `a7b6240c6da3ea117d0b3c82749e05c426bc9e0b` | `72f32f259fc1f9c741e3de8298f391f845db5f2bee629fab5722962a91ce1787` |
| `web/src/shared/api/generated.ts` | `26159e1689dada4d0ac4a80719481aa3b1d3f175` | `3e45dd46add9cc9674693ee4a33c5199aa1221620ecfaad6ded96685d6f1d595` |

## Predare

AICI: corecții implementate în candidat neintegrat; dovezi **PASS_RECORDED_SCOPED**, review R1 **APPROVED_CORRECTIONS_SOURCE_SCOPED**. Părintele rămâne owner pentru adjudicare/integrare, reviewurile complementare și QA independentă.

**Parent final SOURCE după relay și prima QA independentă pe consumatorul real rămân obligatorii.** Canonical/broad CLI/crash și installed historical readers rămân în tracking, fără T1/T2 approval ori continuare automată.

Singurul fișier creat/modificat: `../logs/reviewer1-model-corrections-029-review.md`; niciun commit. Nu am modificat raportul original 95a8.

Necontrolat: relay nou, installed/browser/provider, crash SENT, canonical și broad CLI; nu am extins fixture breadth sau auditul vechi.
Risc rămas: relay HIGH deschis; aprobarea se limitează la corecțiile NON-RELAY de pe bytes029, nu la siguranța integrală a produsului.
