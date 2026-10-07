# P2-inert / SL07-B05 — consumator de slot și inventar bootstrap

## Contractul continuării E-B05-03

**Completarea slot/bootstrap E-B05-03: CLOSED_SCOPED numai pentru consumatorul inert instalat, pe produs `dfc549a`.** [Receiptul actual](p2-b05-slot-gate.json) păstrează QA nominală `PASS_SCOPED_WITH_NOT_RUN`, gate-ul canonic nou exit0/drained și dispoziția explicită a QA suplimentare `NOT_PASS_PROTOCOL_DEVIATION`. La înregistrarea contractului implementarea/QA erau NOT_RUN; contractul de mai jos este păstrat ca proveniență, nu o nouă sarcină. Întreg B05/G02 rămâne PARTIAL/OPEN. Fără B06, Task/Attempt, Brain/copil, Settings, model/provider/țintă sau rollout P0/P1. Autoritate: arhitectură §5, plan §7/§19 și [registrul B05](p2-b05.md). [H02/authority](p2-b05-h02.md) și receipturile sale rămân istorice la bytes/probe declarate; nu transferăm gate-ul produsului `e5edb25` asupra acestei implementări.

Baza citită și verificată: `e27d1aaf2a80f432f9b0de7be7fc8280f10546c6`, branch `p04-control-topology-wip`, tracked clean. Singurul untracked este `documents/Omnis_Notite_Originale.html`, protejat/necitit. Arhitect read-only independent `deleg_7be3f807`: raport scratch `b05-continuation-e27d1aa-architect.md`, SHA256 `346f372bc78a90e7766d65d75d579d0d1e1bc82bf86351ebb0684e0d1118fedb`. Recomandarea este adjudecată mai jos ca frontieră de implementare, nu drept dovadă runtime. Nu lipsește o decizie nouă a operatorului.

## Rezultatul observabil

Stock `python -I -m omnis.supervisor` selectează un engagement existent în PostgreSQL, restaurează numai starea lui înainte de launch, consumă inventarul emis de același proces Hermes inert și, la close nominal, verifică drainul aceluiași boot înainte de arhivare și release. Traseul instalat A→B→A folosește trei booturi noi explicite, același slot și același provider store sintetic. Runtime-ul B nu are montate arhivele/controlul și nu vede starea A. Codul de produs, nu driverul QA, execută archive/restore.

Nu se implementează rearm/reset în host, scheduler, daemon nou, Docker socket în componente, RPC passthrough sau import Hermes în API. API/web și instalarea persistentă P1 r1 rămân neatinse, `assessment_ready=false`.

## Interfețe fixate înainte de RED

Numele de mai jos sunt **contracte noi de implementat**, nu comenzi deja disponibile.

### Selectarea inertă de caz

- Opt-in trusted la entrypointul supervisorului: `OMNIS_RUNTIME_CASE_ID` și `OMNIS_RUNTIME_STATE_ROOT`, ambele prezente ori ambele absente. Case ID este UUID canonical strict; rootul este absolut/canonical/privat și nu vine din JSON RPC/LLM. Case mode cere `OMNIS_RUNTIME_INERT_PROBE=1` și runtime IPC distinct.
- Deploymentul propriei fixture provisionază rootul, leaf directories stabile și o policy privată identity-bound în `control/`. Policy fixează instance ID, identitățile dev/inode ale roots, approval/digestul configurației comune, source bindings și lista finită de state families. Dev A documentează schema exactă livrată în raport; nu introduce env-uri/grants arbitrare pentru a ocoli policy.
- Topologie: `active/` la `/state/active`; `active-support/{work,os-home,codex,tmp,managed-empty,xdg/{config,cache,state,data}}` montate individual la paths fixe `/state/...`; `archives/<UUID>/` și `control/` numai supervisorului. Runtime nu primește rootul părinte. Nu redenumi roots/mountpoints: mută numai children clasificate, după drain.
- Provider store `/state/active/auth.json` și `auth.lock` rămân singulare în slot, fără copie/symlink în archive/support. `config.yaml` rămâne numai cu digestul aprobat. `.env` absent în această primă frontieră. Catalog executabil writable/development skills și auth fallback în os-home/codex refuzate. `managed-empty` trebuie să rămână gol.
- Policy de stare este source-bound la Hermes `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Inventarul static inițial `state-tool-inventory.json` are SHA256 `a2020b35cf5cee08d671c3421b81119b8fc7b1beaae4b39cc488eab4c1874cad`; nu este inventar de tools încărcate. Confirmă ancorele înainte de clasificarea oricărei familii noi.
- Conservă state DB și întreg bundle-ul SQLite/WAL/SHM/journal/recovery, sessions/logs/cache și derivatele case-only aprobate; conservă work/XDG/TMP. Un path neclasificat, symlink/hardlink/special file, root înlocuit, destination ocupat sau EXDEV refuză pre-move. Fără copy fallback, checkpoint SQLite, ștergere de recovery ori adoptare implicită.
- Engagement ID trebuie citit prin `EngagementService.read` stock înainte de restore/launch. Metadata typed leagă instance/case/owner/epoch, launch generation, boot și source policy. Generația DB curentă nu este confundată cu launch generation.
- Guardul typed minim al `InstanceService` reutilizează ordinea lockurilor, `_require_owner`, `_require_generation`, stop fence și DB time. Refuză admission/run incompatibil și lease expirat/stale înainte de mutare. Operațiile FS sunt finite, cu plafon explicit de entries/bytes/deadline, fără I/O nelimitat în event loop și fără prelungire de lease pentru harness.
- Preflight eșuat/stale owner/drain false sau UNCERTAIN înseamnă zero mutări. Dacă o operație începută eșuează ori pierde bugetul/autoritatea între mutări, păstrează datele și journalul incomplet și refuză orice launch/restore următor; nu pretinde zero mutări sau atomicitate DB+FS în acel caz.
- Journal PREPARED și lista identity-bound sunt fsynced înainte de primul rename; COMMITTED numai după toate mutările, readback/fsync și validarea autorității. O active case neterminată nu poate fi adoptată din faptul că un host nou este IDLE. Recuperarea manuală nu este autoresume și nu se creditează drept close nominal.
- Ordine obligatorie: prepare/restore → launch → heartbeat/renew imediat → observație; close nominal → stock drain+status STOPPED pentru același boot/fence → guard owner curent → archive/readback/commit → IPC close → release. Excepție/lease loss/drain incert: cleanup conservator, fără archive complet fals.

### `bootstrap_inventory` — event nativ și proiecție stock

În inert mode, payloadul `gateway.ready` existent primește `bootstrap_inventory`. NativePeer îl validează și îl reține; RuntimeHost îl proiectează în status; RuntimeClient îl validează; supervisorul case-mode îl consumă și îl leagă la receiptul cazului. Nu se adaugă RPC/metodă/OPS nouă. Înainte de ready statusul are `bootstrap_inventory=null`; după ready snapshotul valid rămâne disponibil și după STOPPED, fără actualizare ascunsă.

Schema exactă a obiectului (extra fields refuzate, tipuri JSON exacte, fără coercion):

- `schema_version`: integer exact `1`.
- `observation`: string exact `NATIVE_BOOTSTRAP`.
- `scope`: string exact `/state/active`.
- `registry`: exact `status`, `generation`, `count`, `entries`.
- `plugins`: exact `status`, `count`, `entries`.

Registry:

- `REGISTERED_SNAPSHOT`: generation integer ≥0, count integer 0–256 egal cu lungimea entries; entries sunt sorted/deduped după name, fiecare obiect exact `{name, toolset}` cu stringuri nonempty ≤128 caractere. Overlayul scope-ului existent înlocuiește aceeași cheie globală ca în pin. Snapshotul nu înseamnă enabled/model-facing/efect permis.
- `NOT_INITIALIZED`, `NOT_OBSERVED_BUSY`, `LIMIT_EXCEEDED`, `NOT_OBSERVED_INVALID`: generation/count/entries sunt toate null. NOT_INITIALIZED numai dacă modulul/singletonul lipsește, nu dacă un registry existent este gol.

Plugins:

- `PLUGIN_SNAPSHOT`: count integer 0–128 egal cu lungimea entries; entries sorted/deduped după name, exact `{name, loaded, enabled, deferred, error_present}`. Name string nonempty ≤128 caractere; celelalte câmpuri booleans exacte, fără conținutul erorii/configului.
- `NOT_INITIALIZED`, `NOT_OBSERVED_BUSY`, `NOT_OBSERVED_IN_PROGRESS`, `LIMIT_EXCEEDED`, `NOT_OBSERVED_INVALID`: count/entries null. Manager absent nu este construit. Manager existent dar discovery incomplet/in-flight nu devine snapshot empty-success.

Plafoane: payload serializat UTF-8 ≤24 KiB în frameul existent de64 KiB; totalul așteptărilor pe locks ≤50 ms. Overflow refuză observația explicit fără truncare prezentată drept completă. Nume/control characters invalide refuzate; projectionul exclude paths, schemas, handlers, descriptions, credentials, env/config/error text și `repr`.

Observerul citește numai `sys.modules` și obiecte/cache-uri deja existente pentru `/state/active`, cu locks bounded. Nu importă/discover/prewarm `tools.registry`, `model_tools`, plugin managers, providers/MCP; nu invocă check_fn/dynamic schemas/get_definitions/get_plugin_manager/agent constructor/_get_db. Native inert real poate raporta sincer NOT_INITIALIZED; nu inițializăm tooluri ca să fabricăm un pozitiv. Un populated registry de test este SIMULATION/source-bound dacă nu există natural în procesul instalat.

NativePeer refuză payload absent/malformed/count mismatch/extra fields/duplicate raw keys și al doilea ready. Eventul complet poate păstra metadatele native existente, dar inventarul proiectat este strict. RuntimeClient cere snapshot pentru READY/STOPPED după launch și nu trimite câmpuri native arbitrare în case receipt. Boot/generation/epoch sunt cele ale transportului autentic, nu revendicate din inventar.

## Ownership și flux

Arhitectul bounded este finalizat. Parent creează două worktrees explicit din HEAD local verificat după acest contract; nu din remote. Doi dezvoltatori leaf, fără commit/push în checkoutul comun:

| Autor | Căi permise | Livrabil și RED principal |
|---|---|---|
| Dev A | `api/src/omnis/supervisor/__main__.py`, nou `case_slot.py`; `modules/instance/service.py` numai guard; `api/tests/test_runtime_supervisor.py`, `test_runtime_service.py`, noi `test_case_slot.py`, `test_case_slot_service.py` | Product restore/launch/drain/archive/release; A→B→A real filesystem, fixed roots, provider/config excluderi, incomplete/crash refuzat. Guard PG real cu expirare și lock overlap observat. |
| Dev B | inert `entry.py`, patch/patch-manifest, `pin.json` numai overlay hashes; `runtime_protocol.py`, `runtime_host.py` numai snapshot; `runtime_client.py` numai inventory validation; runtime tests + nou `test_bootstrap_inventory.py`; build test structural dacă necesar | Producer nativ read-only și transport typed; absent≠empty, busy/incomplete/overflow, sinks forbidden, strict framing/count/duplicates, denials RPC neschimbate. |
| Parent | `Makefile`, această notă/receipturi noi, harness scratch/provisionare nouă | Integrare byte-exact, granular commits, două reviewuri pe același snapshot, remedieri focalizate, QA instalată independentă, gate final, cleanup exact/readback. |

Dev B nu modifică state inventory pentru ancore fără nevoie: policy Dev A rămâne source-bound și sursele Hermes nemodificate relevante rămân la pin. Nicio repin/dependency upgrade. Parent deține orice schimbare necesară de manifest/gate; dezvoltatorii raportează necesitatea, nu editează fișierele celuilalt.

## Acceptare și probe

1. RED→GREEN executat și păstrat pentru fiecare comportament; focused regressions/lint/type trecute pe bytes integrați. Python API3.13.15, UV0.12.19 și deps existing, fără instalare în profilul personal.
2. Două reviewuri complementare pe snapshot final exact: R1 normativ/order/persistence/mounts; R2 provenance/input/PG fencing/crash uncertainty/inventory no-prewarm. Findings originale adjudecate; blocker→repro/minimal fix/checks/re-review, nu aprobare implicită.
3. QA distinctă, fixture nouă PG/OCI/stock supervisor și imagine/wheels noi source-bound. Un singur slot și provider store sintetic; booturi seriale A→B→A. Writerul finit `SessionDB` pinuit seed/read este separat și joined înaintea mutărilor; gateway inert nu pretinde execuție de sesiune când session.create este deny.
4. Verificare mount namespace: B nu vede archive A/control și nici case derivatives A la fixed paths. DB/sessions/cache/support ale A reapar la restore; B nu. Hashuri/booleans sintetice și metadata numai, fără raw DB/log/auth.
5. Installed negatives focalizate pe aceleași căi: case/instance absent/wrong, unknown state/fallback auth, busy/drain incert și lease stale pre-move, incomplete journal/noul host IDLE nu adoptă. Alte pure denial classes rămân unit/integration evidence, nu inventate ca native installed scenarios.
6. Inventar bootstrap din același PID/stdio nativ consumat până la receipt; NOT_INITIALIZED observat este acceptabil și nu închide H08 Brain/copil. Peer fixtures malformed și populated registry pure sunt SIMULATION. Native denied methods rămân −32601 cu ping control.
7. Canonical `make check` pe produsul final înghețat, nu redenumirea unor focused tests. După documente: renderer check, docs/development și diff check. Regenerare HTML numai la normative Markdown modificate.
8. Parent retrage numai resursele noi identity-bound după settlement, verifică exact CID/network/socket/process readback și păstrează datele sintetice/PGDATA/imagini/journals/receipturi. Fără prune/reset/DROP pe fixture QA, fără cleanup istoric repetat. P1 r1 verificat neschimbat la predare.

## Limite și rollback

Acest contract nu este implementare, review de cod sau probă live. Întreg B05/E-B05-03 rămâne PARTIAL/OPEN până la adjudecarea rezultatelor; G02-inert/live nu primește PASS dintr-un snapshot registry. H03–H08/binding/catalog B06, management refresh, syscall tracing universal, CI remote și rollout sunt excluse.

Rollback cod: inspectează dependențele și `git revert` pentru commiturile noi, fără rescriere de istorie. Git nu inversează mutările FS/PG/procesele; orice fixture păstrează before/after și journalul, iar refuzul/uncertainty se raportează înainte de recovery manual. Commituri locale, push numai la cerere.

## Rezultat executat și acceptare delimitată

Părintele acceptă **numai completarea stock slot/bootstrap** pe `dfc549a16d59caf6981ccb1d91db748f80c6dbb1`: prepare/restore înainte de launch, engagement citit din PG, renew imediat, inventar emis de același nativ și, nominal, drain/STOPPED → archive/readback/COMMITTED → IPC close → release. Nu declară o execuție QA suplimentară conformă sau întreg B05/G02 închis. [Receiptul](p2-b05-slot-gate.json) separă aceste axe; [reviewul fixului nativ](p2-b05-slot-native-review.json) este copia exactă, nu un verdict nou.

### Implementare, remedieri și review

- `fde35ee`: producerul bootstrap și transportul strict; `09eed94`: consumatorul stock, guardul typed și slotul cu roots stabile. Predările A6/B10 au fost integrate byte-exact după reboot; fixture-ul comun lipsit de inventory a fost corectat după RED, fără schimbarea OPS/argv.
- Două reviewuri complementare pe `09eed94` au cerut trei remedii independente: `7e9db40` conservă bugetul UTF-8 nativ; `72e1e39` refuză bool/float pentru schema version; `6ad3a87` păstrează PREPARED până după readback, verificarea finală și ieșirea guardului. RED-urile și regresiile au fost executate. Dispoziția independentă extinsă pe `6ad3a87` este APPROVED_SCOPED, SHA `28b87e3f9ebb5f5e0d98be5884a543f3db5cca463aeac750fa2c63d797eff2b3`,22 bindings; reviewul R1 focalizat a eșuat la furnizor `content_policy_blocked`, fără aprobare inferată.
- Gate-ul anterior pe `6ad3a87` a trecut, dar QA instalată `deleg_eb696a8f` a găsit **QA-B05-NATIVE-STATE-01**: A1 Stop/archive exit3, `Unclassified case state`. Raportul SHA `eefcf2ce33950e74efc4186645d5687334535f69b507a54360e5c2e42073f7bc` rămâne **BLOCKED_NOT_PASS**; arborele real/receipturile nu au fost migrate, reparate ori reclasificate pentru a fabrica succes.
- `dfc549a`: după scanner real RED și regresie RED, policy schema2 leagă manifestul separat și11 ancore native. Acceptă numai SOUL default pinuit, două locks regulate goale, maximum5 backupuri `config.yaml.good.<timestamp>` cu digestul configurației credential-free exacte `inert: true\n`, plus cele șapte directoare skeleton **empty-only**. Nu este allowlist de cataloage executabile sau configurație arbitrară; config/provider store rămân SHARED singulare. Policy1/stale digests refuzate, fără adoptare/migrare. Traversal/link/auth/root/budget/lease/drain/PREPARED rămân intacte.
- Parent:91 teste afectate/Ruff/mypy exit0. Re-review independent `deleg_1d14d0f7`: **APPROVED_SCOPED**,79 pure PASS,3 crash-cut subprocess existente deselectate explicit; cele38 negative noi acoperă active și archive. SHA `c75dbe700b46af5febfe927533cc30a85160e20c5647ee08c7ec3bee2d4bd4c1`, toate4 fișiere și11 surse native verificate. Acest review nu certifica singur installed QA.

### QA instalată nominală — rezultat real, nu markeri substituiți

`deleg_e1cbc91d`, driver instalat `python -I -B .../b05qdfc/qa/installed-qa.py`, **exit0 / PASS_SCOPED_WITH_NOT_RUN**, raport SHA `a712e5ca9793aee523156a5e3ebc658377d61416658c97aeaf110ed2e6ca2a6d`. Wheel API SHA `15010ae640ead513e5caf48097438a8d18f6bc8b86e4dff6326faa9fd549209c`,42 module byte-bound; adaptor SHA `8ad49ba73ae46fce14618c40e30a98a5872b4af3256118fdda8dcd48e3bf6c42`; imagine nouă `sha256:0c2d1599d0f0fd720fa3c5197c782d91871625b24e6035f4303ecaed0d9ae5a4`, UID1000:1000, argv fix `-I`, fără rețea/root writable sau archive/control mounts.

| Criteriu | Dovadă / rezultat | Limită |
|---|---|---|
| Stock A1→B1→A2 | Trei booturi distincte; supervisor instalat exit0/0/0; restore înainte launch și archive după drain; driverul nu mută starea | Un singur slot inert, date sintetice; nu run/Task |
| SessionDB și starea A | Writer/reader din pin, exit0/0/0, joined; sesiune/message și derivate; receipt tree A1 archive exact egal cu A2 restored active, inclusiv directories/dev/inodes | Canaries auxiliare sunt sintetice; SessionDB nu este înlocuit cu SQLite/JSON marker |
| Izolare B/A | B nu vede sesiunea A ori archive/control; A revine fără sesiunea B; mounts/inode-uri roots/provider/config stabile | Namespace/container propriu, nu protecție față de root/același UID ostil |
| Inventar bootstrap efectiv | Aceeași observație READY→case receipt→STOPPED în toate3 booturile: registry `REGISTERED_SNAPSHOT`, generation3,count3 (`manage_catalog/setup`, `manage_connections/connections`, `todo_list/todo`); plugins `NOT_INITIALIZED`, câmpuri null | Registered ≠ enabled/model-facing/efect autorizat; fără discover/prewarm; nu inventar Brain/copil H08 |
| Drain și release | pidfd readable, `/proc` absent/reaped și OCI census fără nativ; journal COMMITTED/ARCHIVE și lease released în fiecare pozitiv | waitid exit cause NOT_OBSERVED; nu toate crash cuts ori atomicitate DB+FS |
| Șase denials instalate | missing case, wrong instance, unknown state, fallback auth, PREPARED journal, unclosed ACTIVE: exit3, IDLE fără launch și bytes/inode-uri neschimbate | ACTIVE injectat testează consumatorul, nu un crash producer real |

### QA suplimentară — observații păstrate, protocol FAIL

`deleg_111d04a0`, raport handoff SHA `6186c9994eedfdf3cc11b312efe5e4220afecc955c74dbc2be3365890e201d60`: verdictul execuției rămâne **NOT_PASS_PROTOCOL_DEVIATION**. Cele patru observații de produs sunt `PASS_SCOPED_WITH_LIMITS`, cu controale nominale exit0 și negative exit3:

- Policy digest greșit și `slot.lock` ocupat efectiv refuză fără launch/move; policy corectă/holder eliberat și joined permit close COMMITTED.
- Renewal suspendat → expirare reală PG → `owned_status` refuzat la close, înainte de `slot.archive`; ACTIVE/COMMITTED_RESTORE păstrate, fără ARCHIVE sau release fals. Nu certifică expirarea **în interiorul** unei tranziții FS începute.
- PID1 runtime suspendat cu pidfd → drain reply indisponibil la close; supervisor exit3, fără ARCHIVE/release. `scenario_uncertain=true` rămâne; resumption/settlement ulterior sunt retragere fizică separată, nu close nominal.

**NQA-ISOLATION-01:** importarea helperului anterior cu `-I`, fără `-B`, a creat `b05qdfc/qa/__pycache__/installed-qa.cpython-313.pyc` în afara `nqa` permis. `PYTHONDONTWRITEBYTECODE` nu protejează această invocare deoarece `-I` implică `-E`. Artefactul SHA `17e530f0768dd3034e8fa8981663c48313442fe949a47baf469e4785ae6b17cb` și FAIL sunt păstrate; nu ștergem fișierul și nu reluăm efectele pentru a ascunde abaterea. Scanul metadata nu este dovadă universală a absenței altor syscalls.

Adjudecare read-only independentă `deleg_4f606d6c`, SHA `492734cfb37dbbf3fac92390e0a1269c106b7ec03c8b0b61888175723be68d6b`: observațiile hash-bound rămân utilizabile delimitat; abaterea de scope blochează un PASS contractual necalificat, nu falsifică automat toate comenzile de produs. **Dispoziția părintelui:** acceptă nominalul și păstrează strict aceste observații suplimentare cu FAIL atașat; nu certifică întreaga execuție QA suplimentară. Cele42 module/source/wheel și fixture-urile/runtime mounts nu au fost substituite. Două încercări de harness anterioare BLOCKED (settlement, apoi max6runtime) rămân în receipt, fără promovare.

Prevenția a fost probată separat, în fixture sintetică: `python -I` + env-only creează pyc, `python -I -B` și `sys.dont_write_bytecode=True` înainte de import nu creează pyc; **3 controale, exit0, ad-hoc**, nu o nouă QA live sau schimbarea verdictului istoric. Expiry în interiorul FS, un crash producer fizic și încă un boot nou care adoptă starea unui close eșuat sunt NOT_RUN în aceste QA; probele source/PG/crash și denials de consumator rămân separate.

### Gate canonic final și readback

`proc_30c53ccef430`, pe HEAD înghețat `dfc549a`, a executat comanda reală, nu o țintă focalizată redenumită:

```text
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u XDG_DATA_HOME -u UV_PYTHON_INSTALL_DIR -u UV_PYTHON -u UV_CACHE_DIR HOME=/home/kali/.hermes/cache/scratch/b05f6ad/home2 TMPDIR=/home/kali/.hermes/cache/scratch/b05fdfc PATH=/home/kali/.hermes/cache/scratch/b05-resume-tools-09eed94/bin:/usr/local/bin:/usr/bin:/bin make check UV=/home/kali/.hermes/cache/scratch/b05-resume-tools-09eed94/bin/uv
```

**Exit0, `{"schema_version":1,"code":0,"family_drained":true}`**:490 API,22 migrare,74 web unit,9 E2E browser/API/PG,134 Hermes runtime+6 AST;62 docs/42 development, CLI284+284,wheel API1,release61 și lint/type/build/contracte. Sunt rezultate per componentă, nu un total unic. Log SHA `a85cddcda404ec0fc861078543be4846e90720414edae48c8664a1f5187ab3b0`; warningurile shell `can't change option: zle` sunt păstrate, fără eroare de gate.

Parent cleanup nominal:8 runtime+1 PG, apoi suplimentar:6 runtime+1 PG, apoi gate:1 PG. **Toate17 CIDs proprii absente**, rețele/socketuri/IPC proprii absente, all13 foreign CIDs/states neschimbate; state trees/bytes/inodes/PGDATA/DBs/imagini/receipturi păstrate. Cleanupul nominal a avut exit1 **după efectele retragerii**, la readbackul presupus `data/PG_VERSION`; readback READ_ONLY pe pathul real PG18 `data/18/docker/PG_VERSION` a trecut, fără replay al cleanupului. Cleanupul suplimentar exit0 păstrează lease-ul expirat, ACTIVE/COMMITTED_RESTORE și incertitudinea scenariului; nu acordă reuse.

SHA cleanup nominal `0a89aa5b866a9ef79eb8d4c80a4f26f5312080232ce4dbf16e563b9b40705b9f`; suplimentar `1003c5781414bb7c1ef0f36154623d55be613b983bfbe1eb1a96c95479270d9f`. Cele13 containere străine sunt oprite la readback; P1/r1 nu a fost repornit/adoptat după reboot și **READY istoric nu este revendicat drept stare live actuală**. Fără secrete/loguri private brute în Git; raportul versionat păstrează comenzi, hashuri, scope și limite.

### Predare și ce nu este închis

**Rezultatul cerut stock slot/bootstrap există și este acceptat scoped.** Închidem numai acest perimetru al E-B05-03, nu întreg SL07/B05, P2 sau G02-inert/live; B06 nu a fost început și nu primește autorizare implicită. H03–H08/task/copil/model/dispatch, Settings, target effects, calificarea globală și CI remote rămân la felia/gate-ul lor. Nicio probă nouă universală de syscall/zero I/O nu este inventată pentru a amâna nominalul; limitele reale rămân explicit NOT_RUN.
