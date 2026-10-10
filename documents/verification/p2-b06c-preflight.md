# SL10 / B06c — preflight producer → consumer

Bază: `c0261a7ae2319b57a0a3154d3e79b2ed908418f8`, worktree `omnis-p2-b06c-20261010`, branch `p2/b06c-critical-20261010`. Autoritate: plan §7–8; arhitectură §5.2, §9.3–9.10, §10. Scope: date exclusiv sintetice autorizate, proiecție separată pentru B06m; fără provider/target/UI/warm. Originalul HTML protejat nu este citit sau inclus.

## Traseul existent și schimbarea minimă

`runs/managed_admission.py:BuildSource.build` → `tasks/managed_contract.py:build_records` → `tasks/managed_composition.py:compose` → `managed_record` prin `tasks/managed_store.py:put`. `ManagedAdmission.readback_manifest`, `load_manifest`, `_verify_graph` și `managed_store.get/graph` verifică owner/run/Ref/closure. `ManagedAdmission.stage_payload` → `supervisor/native_tasks.py` → `omnis_hermes/managed_admission_contract.py:validate_stage` → `prompt_bundle.py:validate_composition` este consumul cold existent, nu pre-send. Compoziția selectată conține bytes raw ai capture/records și texte aprobabile, deci nu este ModelProjection.

Se adaugă numai `policy/model_projection*.py`, `runs/model_projection*.py`, un producer separat în `managed_composition.py`, `omnis_hermes/model_projection*.py`, teste noi `*model_projection*` și aceste note. `ModelProjections.prepare` reutilizează aceeași conexiune/tranzacție, lock și store; nu modifică schema, manifestul, composer pinul, wire-ul ori release-ul cold. Produce/readback un sidecar imuabil; nu inserează proiecția în vechiul prompt-composition.

Primul caller cerut rămâne B06m trusted pre-send. Interfața B06m citită la preflight este PROPOSED, cere projection_ref/projection_digest și declară NOT_INTEGRATED. Nu există încă acel caller în baza locală. Connectorul aparține B06m; schimbarea locală nu închide SL10 înaintea integrării și QA consumerului real. Fără metode SDK/turn IDs inventate, fără adopție WIP B06m.

## DTO, digest și Ref

Se materializează tipul cerut ModelProjection v1 la primul consumer: noul sidecar `RecordEnvelope(kind="model-projection", revision=1)` este declarat și verificat explicit în modulele noi, nu presupus existent în baza C03. Nu se creează alte kinds pentru policy/turn/config. Ref-urile sursă sunt cele reale: launch-manifest, runtime-binding, prompt-composition, task-brief, bound-procedure, run-snapshot, execution-selection, mission, focus, probe-policy, probe-scope, contract-input-context și contract-case-records. Kinds/IDs/revision/digest se validează înainte de lookup; owner/run și relațiile assignmentului se verifică după lookup.

Payload v1 fixează owner/run, manifest/binding/composition/brief/snapshot/selection/mission/focus/policy/scope refs, approval_digest, provenance și model_input. `model_input={messages:[{role:system,content:Text},{role:user,content:Text}],tools:[]}` este carrier de date pentru adaptor, NU metodă SDK. `projection_digest=SHA256(CanonicalJSON(model_input))`; envelope.digest urmează §9.3 și este distinct. Serializerul Hermes verifică bytes canonicali efectivi ai întregului carrier și pins identice, nu doar un câmp. Requestul SDK complet cere mapare/check B06m separat; carrier PASS nu certifică full outbound.

Aprobarea este un obiect immutable trusted, injectat de callerul backend, legat de owner/run și Ref exact al compoziției. Clasifică explicit digests de text aprobate SYNTHETIC; nu se obține dintr-un `approved:true`, goal sau JSON model-facing și nu se auto-generează în producer. Secret patterns private nu sunt serializate. Lipsa aprobării/sursei/Ref/readbackului blochează. Persistarea aprobării/operator data-policy în viitorul run live este responsabilitatea integrării; nu inventăm un data-policy Ref disponibil acum.

## Allowlist și refuzuri

Instrucțiuni base/role, textele selectate ale skillului/metodei și summary/context din brief intră numai după clasificare exactă și limite. Metadatele model-facing sunt refs/IDs opace, rol și subsetul explicit al assignmentului; parametrii pașilor nu intră. Records sintetice admit numai method/status și path redactat conservator la `/[redacted]`; fără query/fragment/value. Capture brut nu se trimite și, când este mandatory, proiecția îl refuză (vechiul cold capture rămâne funcțional). Supporting bytes, headers/body/query values/cookies/storageState/stack/evidence/screenshot, tools/options/errors/history necunoscute nu intră implicit. Câmp suplimentar sau sensibil neclasificat produce refuz sanitizat. Textele cu cunoscut-secret sunt eliminate prin refuz înainte de serializare, inclusiv context/base/role/method/skill; fără promisiune DLP universal.

## Acceptare, probe și resurse

RED→GREEN pe noul producer pornind din graful real C03/composition, serializare independentă Hermes pe bytes și perechi pozitive/negative: input sintetic → proiecție/digest; marker raw-path/extra/unclassified/secret exclus; owner/foreign/stale refs și limits refuzate. Regresii ale callerilor schimbați, ruff/mypy pin-uite. PG real pentru sidecar/readback/restart și QA independentă consumer B06m numai când effects.holder=b06c cu targets explicite. Fără make check integral, runner nou, fake provider ori audit repetat al acceptărilor cold neschimbate.

Preflight independent: `deleg_81790197`, transcript `/home/kali/.hermes/cache/delegation/live/deleg_81790197/task-0.log`, snapshot c0261a7. Confirmă lipsa consumerului pre-send și conservarea wire-ului cold. effects.json holder=c03-records, targets=[]: DB/OCI/installed/native NOT_RUN. Baseline offline prima comandă: 135 PASS și 5 erori fixture PG neadmisă, exit1; niciun efect DB creat. Rerularea offline exclude explicit numai acele teste PG, nu slăbește gate-ul canonic. Venv proprie Python3.13.15/dependențe lock frozen; uv bootstrap0.11.7, nu credit pentru check-api pin0.12.19.

Rollback: revert commiturile B06c; sidecarurile sintetice persistate rămân date păstrate, nu cleanup implicit. Închiderea fazei2/SL10/G02 rămâne neautorizată/neprobată până la consumer/integrated gate și acord separat live.
