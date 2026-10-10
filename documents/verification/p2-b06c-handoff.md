# B06c — predare componentă ModelProjection v1, nu închidere SL10

## Verdict și snapshot

READY_FOR_INTEGRATION pentru componenta source/unit/carrier; READY_FOR_INSTALLED_QA în coada serială, fără execuție admisă încă. SL10/G-DATA-EARLY și faza2 rămân BLOCKED / NOT_CLOSED: consumerul B06m pre-send/full SDK este NOT_INTEGRATED; PG persistent/restart și QA installed/native sunt NOT_RUN. `effects.json` recitit la predare: holder=c03-records, targets=[], inference/target=false. Nu schimbăm holderul și nu atribuim PASS canonicalului C03.

Cod înghețat/revizuit: `77b4b01375d5585722e2334490b2d435e3525142`, baza `c0261a7ae2319b57a0a3154d3e79b2ed908418f8`, branch `p2/b06c-critical-20261010`. Commiturile locale ale feliei, în ordine: cca17ef, 0d4185b, e57c046, 60de008, aa52a77, 52c61e8, b1b2ea7, 77b4b01. Notele acestei predări sunt ulterioare și nu modifică cele șapte fișiere Python revizuite. Fără amend/squash/rebase/push.

## Producer, persistență și consumer efectiv

`managed_composition.project_model_input` validează compoziția C03 reală și aplică allowlist/clasificare trusted SYNTHETIC, bound owner/run/composition Ref. `runs/model_projection.py:ModelProjections.prepare/read` reutilizează tranzacția/conexiunea callerului, managed-owner lock, `_verify_graph`, `managed_store.get/graph/put`; produce sidecarul imuabil `model-projection` și reproduce bytes la readback. Nu introduce tabel, CLI, ledger ori native turn nou.

`omnis_hermes/model_projection.py:serialize_model_input/validate_serialized_input` este consumatorul implementat al întregului carrier canonical `messages/tools`. Traseul exercitat este seed/compiler/composition → serviciul de proiecție cu SQL doubles declarate → INSERT payload/readback/replay unit → serializer independent → sink inert fără provider. Nu este consumer SDK/nativ complet și nu dovedește persistență PostgreSQL.

`projection_ref.digest` este digestul RecordEnvelope; `projection_digest=SHA256(CanonicalJSON(model_input))` este digestul carrierului. Nu îl declarăm hash al requestului SDK complet. Policy/scope refs sunt probe-policy/probe-scope reale ale managed-run; clasificarea este backend-only, nu `approved:true` din model. Raw capture mandatory este refuzat în proiecție, fără a schimba capture/records/release cold sau NO_MODEL/BLOCKED/INCOMPLETE. Path este redactat integral; nici eficacitate metodologică, delegare sau inferență nu este atribuită proiecției.

## Probe și review independent

După ultima editare: aceeași comandă pytest focalizată din `p2-b06c-offline-evidence.json`, cu cele șapte fișiere test de acolo, a produs **206 PASS / 5 PG deselected / exit0**. Ruff0.16.9 check, format7 și mypy2.3.1 pe cele șapte căi Python: exit0 fiecare; git diff --check: exit0. Renderer check și documentare72 PASS/exit0 au rulat pe baseline/documentele normative neschimbate; nu sunt probe de integrare. make test/check integral NOT_RUN conform mandatului. Probe browser pe buildul integrat rămân NOT_RUN, UI neatinsă.

Review inițial `deleg_6dfeb76f` pe52c61e8: A static scoped aprobat, caveat de identitate; B CHANGES_REQUESTED/B-01. Părintele a verificat că avansul b1b2ea7 era numai note, apoi a reprodus **șase** Ref nested cu revision=true: RED6/exit1. Fixul minimal77b4b01 validează `reference()` înainte de egalitatea Python, în cele trei header și trei context refs; nu schimbă policy/schema/wire cold. Caveatul de snapshot este închis în execuția nouă, nu prin transfer de PASS istoric.

Re-reviewuri complementare `deleg_6f02b0dd`, exact77b4b01:

- A `sa-0-8445c7d5`, APPROVED_SCOPED,52 teste PASS/exit0 și șapte fișiere byte-identice cu Git înainte/după. Locator: `/home/kali/.hermes/cache/delegation/live/deleg_6f02b0dd/task-0.log`.
- B `sa-1-9d2f5397`, APPROVED_SCOPED/B-01 RESOLVED_VERIFIED,6 cazuri focalizate și53 proiecție PASS/exit0, probă carrier6720 bytes cu12/12 refuzuri, ruff/mypy/format7 exit0; HEAD/status/hash-uri stabile. Locator: `/home/kali/.hermes/cache/delegation/live/deleg_6f02b0dd/task-1.log`.

Părintele a verificat separat după review cele șapte fișiere contra bloburilor77b4b01: identice, repo curat. Reviewurile aprobă componenta, nu SL10/full SDK/PG/native. Istoricul RED și eroarea de count55 versus69 din60de008 rămân în evidence/commitul corector aa52a77. Defectele QA-driver shallow-copy/SUPPORT au primit doar corecție de fixture; nu remedieri inventate de produs.

## Dependența cross-worktree și minimul necesar

Interfața B06m recitită: PROPOSED, source ae22022, ledger ACCOUNTING_ONLY_REVIEW_PENDING, projection NOT_INTEGRATED, native BLOCKED_NATIVE_SEAM. Aceasta recunoaște digestul carrierului distinct de envelope; niciun WIP B06m nu a fost adoptat. B06m poate importa numai commiturile B06c înghețate și revizuite în worktree-ul său, nu în main.

Connectorul minim deținut de B06m: readerul calificat → serializer/gate carrier înaintea `reserve`, în aceeași disciplină owner/InstanceControl/Stop; apoi mapare/check al **întregului** request SDK la frontiera autentică pinned `agent/chat_completion_helpers.py:_dispatch_nonstreaming_api_request` → `request_client.chat.completions.create(**api_kwargs)`. Provider/model/caps/config și orice câmp/option label/tool/result/error/log suplimentar trebuie acoperite, nu doar messages. Carrier-only ori ledger metadata-only nu sunt G-MODEL/G-DATA-EARLY PASS. Lipsesc producerul trusted warm/native-turn și veto fizic terminal la acel sink. Nu inventăm turn IDs ori wrapper/hook care cade mai departe după eroare.

Nu există încă o semnătură de connector warm aprobată în baza cold pe care să aplicăm onest un patch de produs. Un diff upstream/pin pe methodă inventată ar încălca mandatul; connectorul este **NOT_INTEGRATED**, cu paths și minim de mai sus. Nu sunt necesare modificări în managed_admission/store/schema pentru producerul B06c. Integrarea stabilirii warm/seam și fixture-urile acordate trebuie predate explicit ownerului competent; nu lărgim B06c în SDK/admission.

## Resurse și reluare

Nicio resursă DB/OCI/serviciu/native/installed creată, adoptată sau curățată. Numai venv proprie și scratch unit; fără credențiale/r1/profile istorice/config globală/push. Date păstrate, originalul HTML protejat neatins. Registrele implementation-status/plan/README/HTML/Makefile rămân read-only ale integrării; aceasta trebuie să reconcilieze SL10 PARTIAL, probe offline scoped și gate NOT_CLOSED, fără a suprascrie acceptările vechi.

Interfață: `/home/kali/.hermes/run/omnis-p2-critical-20261010/b06c/interface.json`, FROZEN pentru componentă. Rezumatul machine-readable este `b06c/handoff.json` lângă aceasta. Prima probă autorizabilă după integrare este reader/persist/readback/restart și QA independentă a consumerului efectiv, prin runnerul existent și targete serial acordate; live cere acord separat. Nu lansăm sesiune/cron succesor și nu schimbăm politica de coordonare.
