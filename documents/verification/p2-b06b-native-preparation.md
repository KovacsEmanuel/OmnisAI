# B06b — pregătire prin loaderul Hermes instalat

## Contractul feliei

Bază `f9f921319fb88eab5ffa222ed39102e95d3b46b7`; tracked curate, originalul HTML neversionat exclus. Operatorul a cerut continuarea după închiderea PURE. C01/PURE rămân acceptate scoped; nu se reauditează. Arhitect read-only `deleg_f7da7964` a verificat contractul implementabil; raportul de suport este `native-prep-contract-v2.json` în scratch. Acest registru consemnează decizia, nu un plan paralel.

**Rezultat:** publicație exactă → selection NO_MODEL existentă → bundle imutabil → supervisorul și RuntimeClient unic existente → RuntimeHost.prepare → worker finit în interpreterul Hermes instalat → `tools.skills_tool.skill_view(..., preprocess=False)` real → receipt PostgreSQL și readback din proces nou. Nu AIAgent, client provider, conversație, TaskResult, completare tur sau inventar efectiv al unui agent. Nu închide C05/H03–H08/G02; aceste componente se reutilizează ulterior fără a pretinde acel rezultat acum.

**Rută:** CLI privat `omnis.modules.runs.native_preparation prepare --request <json> --control-dir <privat>` folosește numai control.sock; callback injectat din supervisor către RuntimeClient deja conectat. `readback --request <json>` folosește DB privat și nu atinge runtime. Nu client concurent către runtime.sock, scheduler, RPC nativ nou ori schimbarea allowlistului NativePeer. Loader worker este copil finit al RuntimeHost PID1, nu copil AI Hermes.

Opt-in nou explicit: `OMNIS_NATIVE_PREPARATION_CATALOG_ROOT` numai împreună cu runtime-dir și `OMNIS_RUNTIME_INERT_PROBE=1`; root existent, privat, canonic. Absența lui refuză pregătirea, fără adoptarea profilului r1/operatorului.

## Interfețe și tranzacții

- Cerere prepare: exact `schema_version:1, owner_id, command_id, instance_id, expected_generation, expected_epoch, selection_ref`; control command adaugă `op:native_prepare`. Catalog owner este distinct de supervisor lease owner. Readback cere numai schema_version/owner_id/command_id. Tipurile/refs/unknown fields sunt validate înainte de replay.
- T1: validate publication→selection→material și bugete; persistă `native-preparation-bundle` și comanda namespaced `native-prepare` cu result={bundle_ref}. Commit înainte de worker. Nu se ține lock DB peste IPC.
- Doar creatorul T1 poate trimite workerul. Comandă identică cu receipt complet → replay fără spawn. T1 fără receipt → `PREPARATION_INDETERMINATE`, fără relansare automată; payload diferit → conflict.
- Runtime prepare păstrează boot/capability/generation/epoch ale conexiunii existente, primește deadline proaspăt din authority și payload={bundle_ref,bundle}; nu path/home/argv din payload. Refuz înainte/după worker pentru grant expirat sau runtime non-READY.
- WorkerResult exact: schema_version/status=PREPARED/bundle_ref/loader=`tools.skills_tool.skill_view`/preprocess=false/loaded/native. Fiecare loaded file conține package_ref/native_name/path/size/sha256/content_b64; native conține base_commit/patch_sha256/skills_tool_sha256/worker_revision ale codului instalat.
- T2: guard tranzacțional în InstanceService cu ordinea instance→lease→stop fence→catalog owner; verifică generation/owner/epoch/no-shutdown și timpul DB după scrieri. Receiptul determinist uuid5(bundle.id, `native-preparation-receipt-v1`) citează bundle_ref, selection_ref, status, loader_result și fence autentic. Readback separat după commit; receiptul este istoric și poate fi citit după oprire. Ordine aciclică snapshot→selection→bundle→receipt. Nu exactly-once distribuit sau lease valid la momentul fizic al commitului.

Bundle-ul fixează protocolul `omnis-native-preparation-v1`, owner/selection/snapshot/publication/candidate refs, recipe, digests material/index, NO_MODEL/effective=null/preprocess=false, limitele și toate fișierele declarate ale pachetelor selectate. Mapping prin refs și source prefixes validate, nu prin paths de la CLI. Sortare stabilă, fără trunchiere sau lookup latest.

**Amendamente ale părintelui înainte de cod:** propunerea de8 fișiere nu admite seed-ul existent: măsurat10 fișiere/9703 bytes. Plafonul este **16 fișiere**, cel mult2 pachete,8192 bytes/fișier și16384 bytes raw total; envelope32768/request49152/response65536 rămân. Nu se elimină fișiere obligatorii pentru a încăpea. Frontmatter acceptă name/description și metadate descriptive bounded version/provenance/author/license plus tags/related_skills/platforms; metadata/requirements/credential/setup/preprocessing directives sunt refuzate. Seed-ul existent are version/provenance, nu sunt capabilități. UTF-8 strict, fără BOM/CR/NUL/binar; native loader normalizează asemenea bytes, deci nu pretindem readback identic dacă îi acceptăm.

## Izolare, ownership și probe

Workerul primește HOME/HERMES_HOME/cwd/XDG/CODEX_HOME/managed/tmp noi sub `/state/tmp/native-prep-<UUID>` înainte de import. Nu atinge `active/skills`; politica CaseSlot nu se relaxează. Fișierele se validează/stage read-only, rădăcinile native trebuie să fie exclusiv cele proprii. `preprocess=False` tot invocă readiness/load_env și încearcă `.env` **absent** în home-ul nou; nu se pretinde că readerul nu este apelat și nu se citește un store real. Outputul trebuie să coincidă byte-exact cu bundle-ul, iar workerul/familia și scratchul propriu trebuie retrase înainte de PREPARED.

**Corecție explicită de fezabilitate înaintea integrării:** propunerea worker1.2s a fost invalidată de proba instalată cold: cele10 fișiere ale seed-ului s-au încărcat byte-exact în1.7652916609949898s, fără tentative socket/subprocess/system observate și fără modulele `run_agent`/`agent.agent_init` în sys.modules. Receipt: `/home/kali/.hermes/cache/scratch/native-prep-latency-2884471bfe/receipt.json`; containerul confinat propriu a ieșit0 și a fost retras exact. Aceasta probează numai loaderul instalat și latența observată, nu consumerul durabil sau absența universală a efectelor.

Pentru **noua operație prepare**, bugetul devine explicit2.5s worker +0.4s cleanup, iar RuntimeClient prepare are cel mult3.2s, limitat în continuare de grantul curent/proaspăt. Celelalte operații păstrează2s, controlul local4s, iar grantul InstanceService4.5s nu se mărește. Nu prewarming al profilului, schimbare globală, retry ori prelungire tacită de lease. Ambele echipe au primit corecția înainte de finalizarea codului/probelor. Dacă acest traseu nu încape în grantul real, se refuză și se raportează blockerul, fără noi extensii automate.

Dev A (worktree separat din HEAD): API consumer nou, schemas/service guard/local_control/supervisor wiring/runtime_client și teste API proprii. Dev B: runtime_host, worker nou și teste runtime proprii. Părintele: integrare, manifests/gates/evidence, build și QA. Fără modificări la compiler BEHAVIOR_FILES/candidate_store/PURE consumer/case_slot/native source/patch/pins/migrations; dacă apar prerechizite noi, se consemnează înainte de extindere.

TDD: cerere validă refuzată de seamul lipsă → cod minim → pozitiv/negative pe calea reală. Probe: exacte refs și bytes, owner/fence/RELEASE/overflow/shadowing/preprocessing/secret requirements, T1/T2/replay/no-respawn, Stop/timeout și cleanup. Două reviewuri complementare pe snapshot exact și QA installed independentă; fără model/provider/ținte/global/r1/push.

Sursa instalată folosită pentru dezvoltare: imaginea exactă `sha256:0c2d1599d0f0fd720fa3c5197c782d91871625b24e6035f4303ecaed0d9ae5a4`; export static verificat3184/3184 fișiere/pin/patch manifest/Python3.13.15 și override-urile deja aprobate. Exportul a creat numai un container oprit, niciodată pornit, apoi retras cu readback exact; datele sunt în scratch `native-prep-source-afc374402d`. Imaginea nu este modificată în loc. Probe viitoare: o imagine derivată etichetată nou, runtime nou confinat/no-network și PG nou UDS, serial; cleanup numai resurse proprii, păstrare date/loguri. Before: fără resurse runtime ale feliei. Invers: drain supervisor, stop/rm CID propriu verificat, păstrează datele; fără prune/down-v/adopție. Git revert nu anulează scrieri DB.

## Stare

Contract adjudecat, implementare NOT_RUN. Nu aprobare nativă ori închidere anticipată.
