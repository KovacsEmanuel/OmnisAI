# C03 records — input structurat și consum nativ inert

## Închidere scoped

**CLOSED_SCOPED_C03_INERT_RECORDS_BINDING / IMPLEMENTED_SCOPED / PASS_LOCAL_RECORDED / APPROVED_SCOPED_COMPOSITE.** [Receiptul părintelui](p2-b06b-c03-records-close.json) leagă produsul `20611d1`, două reviewuri complementare și corecția test-only `c0261a7`, aprobată separat de ambii revieweri. Acceptarea este numai a inputului structurat records și consumului rece, nu C03 general, B06b, G02 sau faza2. C03 capture și acceptările anterioare nu sunt redeschise.

[Installed composite](p2-b06b-c03-records-installed.json): calificare reală cu cele două transformări → confirmare TTY/Publish → inputuri RUN ORDERED/EMPTY noi, distincte de PACKAGE_EVAL → valoare structurată în compoziție → native cold/binding comis înainte de release. Toate trei MethodRequirements sunt păstrate; base/rol și assignmentul vechi rămân stabile. Două boot/root-uri distincte,25 refuzuri instalate/no-write și replay/restart curent. Istoricul produs de wheel-ul baseline real are21checkpointuri PASS/0FAIL, exit0/drained, pentru v1/composition1/capture2 readback/replay și restart receive-only. Nu sunt21teste independente; egalitatea instalată nu este census independent de apeluri evaluator. Guards sursă/PG probează no-rerun în contractul fără dependențe. Metoda RUN nu este executată: NO_MODEL/BLOCKED/INCOMPLETE și consumed_input_refs=[] rămân.

[Browser reconciliat](p2-b06b-c03-records-evidence/browser-adjudication.json):59 IDs stabile,47PASS/8excluderi NOT_RUN/4NOT_IMPLEMENTED. Cele63capturi sunt inspectate și [arhivate](p2-b06b-c03-records-evidence/README.md); patru reinspecții ale părintelui. Save/readback/reload/restart, CAS/no overwrite, valid/invalid/limite, navigare/pairing/status/logout, keyboard/focus/Escape, desktop/mobile și observabilitate pe aplicația instalată. Followupul restrâns8/8 are exit0/drained. Controalele BOOT atribuie numai anulările readiness măsurate, nu ignoră erori arbitrare. Perechile viewport/full-page demonstrează artefactul de captură la stările cerute; o ilustrație nepereche rămâne INCONCLUSIVE_CAPTURE_ONLY, fără defect live blocant demonstrat sau aprobare estetică/WCAG. Nu s-a inventat UI CaseSlot/assessment și nu s-a modificat UI.

[Canonical final](p2-b06b-c03-records-canonical.json), `proc_e3c65fa0961c`: **make check neredus exit0/family_drained=true** pe `c0261a7`,727fișiere tracked neschimbate. Pe componente, nu total unic:72doc,43development,1219API,23migrare,82web,9E2E live,287CLI source+287wheel,1installed status,61release,377runtime+6AST; lint/format/type/contract/build/audit incluse. API wheel final `d1710551…`,71module API/8adaptor/6native conforme; pin Hermes neschimbat. Calificările au fost refăcute pe artefactul final după fixul R2-F01.

Defectul de produs R2-F01 (CR/CRLF eliminate de JSON înaintea guardului nativ) are RED4/GREEN116, PG33, runtime377 și re-reviewuri APPROVED_SCOPED; LF/TAB rămân valide, fără normalizare. [Canonicalul inițial](p2-b06b-c03-records-canonical-fail.json)1215PASS/1FAIL rămâne FAIL: oracle v3 necunoscut, remediat minimal prin v3 pozitiv/v4 refuzat,16teste și două aprobări. Eșecurile QA de root reutilizat, identity/TMPDIR, reconcile pe graf nestaged și observer/capture rămân în rapoartele originale. Primele stage-uri nereconciliate nu devin rezolvate din cleanup sau din reușita unor fixture-uri noi; acele DB-uri sunt non-reusable. Nici cele77checkpointuri din agregatele installed exit1 nu devin o suită exit0.

[Cleanup](p2-b06b-c03-records-cleanup.json):27CID-uri proprii exact absente la readbackul părintelui; family receipts, browsere/procese/socketuri/listener verificate în scope. PGDATA, imagini, wheels, loguri private și date publice sintetice păstrate; DB-urile per-test sunt eliminate de finalizerele declarate.112copii publice cu hashes, inclusiv63imagini, sunt în arhiva versionată; nu loguri brute/DSN/capabilities/runtime.boot. Două worktree-uri B06c/B06m au apărut extern la c0261a7 și nu au fost create/inspectate/adoptate aici; main a rămas stabil. Fără r1/global/provider/model/target/push sau increment următor pornit de această sesiune. Reticle NOT_INTEGRATED, Chisel BLOCKED_NO_GO.

## Mandat și bază

Stare inițială: IN_PROGRESS / NOT_RUN / NOT_REVIEWED. Bază verificată: `5ccf90af410e14abf5bf5d9e9807a44824323b9b`, branch `p04-control-topology-wip`, tracked/index curate. Writer unic în checkoutul principal; investigații/review/QA delegate numai read-only pentru produs și cu scratch propriu. Originalul HTML protejat este exclus înainte de orice inventar de material; worktree-urile istorice și raw `skills/bug-bounty-triage` nu sunt adoptate. C03 capture rămâne CLOSED_SCOPED la bytes/probele sale, fără reaudits ale acceptărilor neschimbate.

Autoritate: arhitectură §5/§5.2, §6.3, §9.3–9.10; plan §4.2/§7–8/§19.2 și registrele curente. Acest registru documentează mandatul existent, nu un plan concurent. Documentația oficială Hermes a fost consultată; compatibilitatea se probează pe pinul local `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, nu pe latest/profilul personal.

## Rezultat și contract înainte de editare

Un nou material first-party `skills/records-mapping-contract` și profil explicit publicabil prin catalogul privat: `map-records` are exact `contract.normalize-operations` → `contract.build-map`. Slotul obligatoriu `records`, expected_kind `contract-case-records`, cere exact un Ref. Valoarea acelui record este `{records:[...]}`; lista goală este validă, maximum128 elemente conform schemei existente și modelului Records. Ordinea și duplicatele se păstrează în input; numai evaluatorul PURE execută normalizarea. Niciun parse fictiv, receipt PURE atribuit copilului sau output de metodă din simplul binding.

Primul binding: `{name:records,source_ref:{kind:CASE_SLOT_REF,name:records},selector:records}`; al doilea este STEP_OUTPUT operations declarat de primul pas al aceleiași proceduri. Publicarea păstrează template-ul; assignmentul materializează BoundProcedure și toate MethodRequirements, apoi Brief. Metadata PromptBundle precede Brief, compoziția finală urmează Brief. Fără backrefs/self-digests sau date de caz în release.

Versionare explicită aleasă: comenzi RUN create-context/create-input schema2 pentru records (schema1 capture neschimbată); context payload version2 records; noul kind input `contract-case-records` payload version1/provenance backend `contract-case-records-v1`; material case-input version2; admit-evaluation-records/evaluate schema3 și protocol `c03-static-pure-records-v3`; prepare-composed schema3/composition_version3/wire `omnis-managed-admission-v3`. Read-context/read-input/readback/reconcile rămân receive-only schema1. Formele istorice native v1/v2 și capture rămân citibile/rejucabile fără rebinding sau reevaluare; hashes de composer istorice sunt admise numai pentru formele lor. Readback nu acordă eligibilitate nouă.

Adjudecarea discovery: recomandarea de a refolosi tacit toate versiunile capture a fost respinsă în favoarea mandatului de versionare explicită. Schema autoritativă este `skills/recon-mapping-contract/templates/schemas/records.schema.json`, care ARE enum/pattern/range/maxItems; observația despre schema mai slabă dintr-o fixture veche nu se aplică. Nu modificăm autoritatea semantică `module_registry.py` ori acea schemă.

## Traseu și paths permise

Definiții/apelanți: skill_catalog.build_procedure/evaluate_pure → CandidateCatalog admission/spec/material/readback/evaluate → PublicationCatalog.check_evaluations → execution_selection → ContractInputs.create_context/create_input/current_source → ManagedAdmission._build/_prepare → managed_contract.build_records/validate_assignment → managed_composition.stage_payload → RuntimeClient/runtime_host → managed_admission_contract/prompt_bundle native pre-constructor. Store/owner/tranzacțiile și cold lifecycle existente se reutilizează.

Paths de produs:
- `api/src/omnis/modules/tasks/contract_case_input.py`
- `api/src/omnis/modules/tasks/managed_contract.py`
- `api/src/omnis/modules/tasks/managed_composition.py`
- `api/src/omnis/modules/tasks/execution_selection.py`
- `api/src/omnis/modules/runs/contract_inputs.py`
- `api/src/omnis/modules/runs/managed_admission.py`
- `api/src/omnis/modules/settings/skill_catalog.py`
- `api/src/omnis/modules/settings/candidate_catalog.py`
- `api/src/omnis/modules/settings/catalog_publication.py`
- `api/src/omnis/supervisor/runtime_client.py` (numai allowlist wire v3)
- `integrations/hermes/src/omnis_hermes/prompt_bundle.py`
- `integrations/hermes/src/omnis_hermes/managed_admission_contract.py`
- `integrations/hermes/src/omnis_hermes/runtime_host.py` (numai discriminarea compoziției v3)
- `skills/records-mapping-contract/{SKILL.md,NOTICE.md,omnis.yaml,references/methodology.md,templates/procedures/map-records.yaml,templates/schemas/records.schema.json,templates/schemas/operations.schema.json,templates/schemas/surface_map.schema.json,templates/schemas/empty.schema.json}`
- `profiles/records-mapping-contract.yaml`

Probe/documente:
- `api/tests/fixtures/c03_records.py`, `api/tests/test_c03_records_contract.py`, `api/tests/test_c03_records_pg.py`
- `integrations/hermes/tests/test_c03_records.py`, `Makefile` numai includerea testului native în gate-ul existent
- `api/tests/test_candidate_tracer_fingerprints.py` numai dacă closure-ul adaugă o sursă trusted
- `api/README.md`, acest registru, `documents/verification/p2-b06b-c03-records-*.json`, `documents/verification/p2-b06b.md`, `documents/verification/implementation-status.md`; README root/plan numai dacă starea se schimbă.
- Receiptul build/atestării API→wheel→adaptor→native nou păstrează pinul upstream. Composerul este pinuit prin COMPOSER_REVISION SHA real; pin.json/overlay upstream nu se rescriu dacă acei bytes nu se schimbă.

Nicio migrare identificată: schema0011 și managed_record JSONB admit kindul nou. Dacă apare necesitate fizică, se oprește pentru decizie, nu se lărgește implicit schema/store/transport. Fără handler/oracle/caps noi, slots generale/multi-ref/opționale, UI CaseSlot, omnis run, scheduler sau model/target.

## Invariante, tranzacții și verificare

PACKAGE_EVAL are admitere/context/input persistente în owner/group-ul candidatului exact, separate de RUN. Transformările reale produc calificarea pe closure-ul final, apoi confirmarea operatorului și Publish exact. Callerul nu atribuie kind/provenance/grants. RUN context/input au tranzacții separate owner-locked și immutable. _prepare deține graphul all-or-nothing sub același lock; verificarea deterministă și overflow preced rezervarea/dispatchul. Mappingul se comite înainte de release. Aceeași cheie/payload este replay; payload diferit conflict. Nu TTL nou.

RED→GREEN tracer: calificare nouă reală → Publish → selection → context/input RUN diferit → assignment/compoziție → native cold preflight/binding/release. Două valori verifică schimbarea conținutului records, stabilitatea invariants/rol și bytes assignmentului vechi. Persist/readback/restart/replay fără rerulare/rebinding, rollback după INSERT real și regresii capture/istoric la frontierele schimbate. Lockul nu se schimbă; proba existentă de overlap nu devine automat probă records dacă nu este exercitată.

Refuzuri: slot necunoscut/lipsă/duplicat/zero/doi refs; ref absent/foreign/kind/revision/digest/bool; owner/context/namespace/provenance/schema incompatibile; PACKAGE_EVAL în RUN, capture↔records, substituție fără slot; material ineligibil/modificat; valori lipsă/extra/tip/method/path/status/129; schemă/bytes/path/hash/size/base64 incompatibile; UTF8/BOM/control/Unicode și limite agregate cu pozitive pereche; STEP_OUTPUT forward/global/cross-attempt/nedeclarat. Schema raw și envelope input ≤8192bytes, graph≤65536, frame≤32768 neschimbate. 128 elemente scurte pot încăpea; produsul refuză legal overflowul agregat chiar sub128. Fără normalizare/trunchiere/mărire limite.

Verificări: teste focalizate prin `test-c03-pg` în `ops/run_test_db_gate.py`, native tests/check-runtime, Ruff/format/mypy; doi revieweri complementari pe snapshot exact; QA installed independentă și browser live pe build nou; canonical final `make check` neredus exit0/family_drained=true; documente render check/unittest și diff-check. Reticle NOT_INTEGRATED în aplicația neinstrumentată, Chisel BLOCKED_NO_GO. Start assessment NOT_IMPLEMENTED, NO_MODEL/BLOCKED/INCOMPLETE nu sunt succes.

## Resurse și invers

Înainte de launch: numai roots scratch noi private, HOME nou, PG18.6 UDS/no-network prin runnerul existent, API/wheel/runtime/native/browser owned. Resursele noi nu există la intrare; paths/identități se înregistrează înaintea efectelor. Uneltele existente sunt verificate, nu adoptăm fixture-uri/DB/date/r1. Invers: ownerul existent drenează/reap și retrage numai procesele/CID/socket/listener proprii, cu readback exact; date/loguri/wheels/imagini rămân. DB-urile per-test eliminate de conftest sunt declarate separat. Git revert nu inversează DB/servicii. Fără push, cron, monitorizare/continuare ori sesiune următoare.

Închidere numai la toate criteriile mandatului; altfel BLOCKED/NOT_RUN precis. Restul C03/C04/C05 și C06–C12/G02 rămâne, apoi B06c → B06m → Settings minim → P2-live cu acord separat.

## Corecție focalizată de test după canonical

`proc_dde998df6b5d` a executat make check neredus pe `20611d1`: componenta API a avut1215PASS/1FAIL, exit2/family_drained=true,726fișiere stabile. Singurul eșec este `test_native_task_client.py::test_unknown_managed_version_never_requests_authority[omnis-managed-admission-v3]`: vechiul oracle numește v3 necunoscut, deși contractul nou îl admite explicit. RED focalizat:12PASS/1FAIL, refuzul așteptat payload denied versus Runtime disconnected după admiterea protocolului cunoscut. Extindere justificată a paths numai la `api/tests/test_native_task_client.py`: trei controale pozitive transport pentru v3 și refuzul viitorului v4, păstrând None/bool/listă, expired/no-resend și toate aserțiunile. Peerul rămâne sintetic, nu dovadă native live. Nicio schimbare de produs, pin, limite, gate ori selecție canonică; QA instalată/browser rămâne la aceiași bytes, iar canonicalul trebuie reluat după reviewul test-only. FAIL-ul original nu devine PASS.
