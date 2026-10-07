# P2-inert / SL07-B05 — consumator de slot și inventar bootstrap

## Contractul continuării E-B05-03

**ÎN LUCRU; implementare/QA NOT_RUN la înregistrarea contractului.** Continuă numai restul B05 autorizat, nu B06, Task/Attempt, Brain/copil, Settings, model/provider/țintă sau rollout P0/P1. Autoritate: arhitectură §5, plan §7/§19 și [registrul B05](p2-b05.md). [H02/authority](p2-b05-h02.md) și receipturile sale rămân istorice la bytes/probe declarate; nu transferăm gate-ul produsului `e5edb25` asupra acestei implementări noi.

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
