# T1 — Settings/seif/Test model

## Mandat și snapshot

**ÎN LUCRU; NOT_ACCEPTED.** Operatorul a activat explicit [promptul T1](api-key-runtime-t1-prompt.md) după [T0 CLOSED_SCOPED](api-key-runtime-t0.md). Bază verificată: `585eaeb0bb028aaa9c7348a5f48b3c8d0860ba38`, branch `checkpoint/p2-batch2-pause-20261015`; fără modificări tracked preexistente. `documents/Omnis_Notite_Originale.html` este untracked protejat, necitit și neatins.

Plafonul mandatului: **T1**, nu T2–T6/M-LAB. Arhitectura §5–5.5/§8.1 și plan §7–8 rămân canonul. Acest registru consemnează implementarea/probele, nu introduce alt plan. Ownerul produsului este supervisorul existent; orchestratorul admite/integrează, un developer desemnat scrie și remediază produsul, două reviewuri independente complementare examinează aceiași bytes, apoi QA independentă exercită consumerul real.

## Acceptance row și traseu

**T1-A1:** operator Settings → API paired/Host/Origin/CSRF → control privat autentificat → supervisor/seif și snapshot immutable → system_operation/permit/SENT → sender finit → outcome/usage → același operation ID în API/decoder/web, cu Cancel/Stop și readback după reload/restart. Save/read/boot fără provider IO. Primul transport real poate fi OpenRouter; OrcaRouter și default/override BRAIN/INVESTIGATOR/VALIDATOR trebuie reprezentabile. Nu catalog/Publish, engagement, managed-run fictiv, native preparation, Hermes runtime, tools sau ținte.

Risc → decizie: secret expus, autoritate stale, resend sau succes/consum inventat → blochează acceptarea. Pozitivul și refuzul sunt pe același caller. SOURCE/protocol fixture/PG/installed/browser/provider live sunt probe distincte. Minimum SOURCE și reviewurile obligatorii preced prima QA bounded a consumerului instalat; apoi numai breadth/regresii necesare și canonical la integrare. Cicluri harness-only T1-A1: **0**; niciun consumer executat la admitere.

## Input și dimensiuni înainte de developer

Producerul intenției este formularul Settings; producerul identity/config/authority este supervisorul. Primul consumer al credentialului este seiful, apoi senderul; readbackul este API/decoderul web. Nu folosim context RUN în T1.

- Păstrăm requestul existent de control **4096 bytes cu newline**, JSON unic/conexiune; fără creștere sau fragmentare. Plafon agregat de **3600 bytes pentru întregul command privat**, verificat după serializare/escaping; verificare finală și pentru frame. HTTP mutation rămâne bounded la 4096 bytes. Readbackul de output ModelTest poate folosi limita separată existentă de răspuns; nu mărește requestul.
- Comenzi semantice separate, fiecare cu UUID propriu și expected revision: salvare/rotație conexiune; revocare conexiune; salvare selecție; Start test; Cancel test. Nu fragmentăm aceeași mutație. Citirile/receipturile sunt receive-only; replay exact precede verificarea headului curent, conflict 409 pentru payload diferit.
- Contractul minim de conexiune: connection UUID stabil, provider OpenRouter/OrcaRouter, revision, enabled/revoked și credential ref/revision private. Secret write-only **1–512 bytes ASCII imprimabil fără whitespace/control**; `repr`/validation/error/log nu îl expun. Endpointul este ales de release, nu primit de la browser. Maximum două conexiuni curente (una/provider), cu istoric păstrat.
- Selecție completă: default și trei override-uri nullable, fiecare cu connection UUID/revision, model ID exact **1–256 bytes ASCII fără whitespace/control**, `output_tokens` integer **1–65536** și numai parametri tipizați admiși/capability-checked. Nu `extra_body`/headers/URL arbitrare, effort neverificat ori compatibilitate inventată. Snapshotul intern fixează și credential revision/DATA/capabilities, fără raw secret.
- Sizing stdlib efectiv, cu UUID-uri, revisions bigint maxime, cheie de 512 și patru modele de 256: comanda conexiunii **754 bytes**, frame **859**; selecția **1832**, frame **1937**. Acesta este buget de proiectare, nu validare DTO de produs; testul developerului trebuie să verifice forma finală/maximele și refuzul overflowului. Forma publică exactă este generată numai din endpointurile implementate.
- Model input sintetic fix afișat, serializat ≤32768 bytes; text reținut ≤8192 bytes și trunchiere explicită. Un apel, deadline absolut 300s de la admitere; `output_tokens` explicit ales. Admission/readback, nu așteptare provider de 300s pe controlul de 2/4s.

## Scope și ownership fișiere

Developer: `api/src/omnis/modules/settings/provider_*`, noile module strict necesare de conexiune/seif; `modules/runs/model_test*` și modulele V2/operație/outcome strict necesare; `supervisor/__main__.py` și senderul/execution owner nou pe supervisorul existent; `modules/instance/{service,schemas}.py`, `transport/local_control.py`, `core/{db,schema}.py` și migrare aditivă **după 0013**; policy/ledger V2 separat fără reinterpretarea V1; API/tests afectate; `web/src/features/engagement/{ProviderSettings,ModelTest,Settings,Engagement}*`, callerii/decoderii/testele/CSS strict afectate; OpenAPI și tipurile generate; manifest/lock/export production; `cli/src/omnis_cli/{release,compose,start,start_runtime,status,stop,forwarder}.py`, bundle/build/Compose/Makefile/runner și teste numai pentru noul artefact și porțile afectate. Modulele suplimentare din aceste directoare sunt admise numai când definițiile/usages arată dependența inseparabilă; fără refactor oportunist sau retragere după numele fișierului.

Orchestrator: acest registru, CURRENT/README și rândurile afectate din harta existentă; integrare Git/acceptare/cleanup. Developerul nu modifică AGENTS/CONTRIBUTING, canonul, trackingul sau HTML-ul protejat. V1, 0001–0013, date/licențe/notices/readeri sunt păstrate; categoriile istorice neprobate rămân explicit NOT_RUN. Nu alt owner, framework, harness generic, SDK Agent/Runner, shell/sandbox ori infrastructură T2–T6.

## Efecte autorizate și preflight

Operatorul a aprobat explicit în această sesiune instalări/builduri și verificări locale T1 pe resurse noi, inclusiv descărcarea dependențelor fixate și PostgreSQL/Docker disposable, **fără inferență live sau atingerea instanțelor existente**. Root nou owned: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th`; rădăcinile testelor și releaseurilor sunt copii private sub acesta. PATH-ul hostului observat are uv/Node/npm nepotrivite; selectăm sau instalăm pinurile numai privat, fără schimbare globală. Python API/CLI 3.13.15 este disponibil. `openai` era dev-only, `cryptography` absent: production manifest/lock/advisory/licențe/import/installed proof sunt prerequisite, nu PASS din cercetare.

Comenzi reale de bază, cu TMPDIR owned și căi toolchain exacte verificate înainte de execuție:

- SOURCE: `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml <teste-afectate> -q`; `make lint-api typecheck-api`.
- PG/migrare: `api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --uv <uv-0.12.19> --target test-migrations --timeout-seconds 600`; targetul T1 se adaugă numai pentru consumerul nou, pe același owner disposable.
- Web/contracte: `make generate-contracts` explicit; `make test-contracts lint-web typecheck-web test-web build-web`.
- Distribuție: `make check-release-install UV=<uv-0.12.19>`, `make check-installed-start UV=<uv-0.12.19>`, `make check-installed-stop UV=<uv-0.12.19>`; acestea construiesc/instalează copii și pot folosi Docker. Nu sunt aliases pentru probe T1 inexistente.
- Canonical la integrare: `make check UV=<uv-0.12.19>`; adaptarea scoped a prerechizitului Hermes mort nu slăbește gate-uri sau ascunde teste istorice.
- Docs după editări: `python -B scripts/render_docs.py --check`, `python -B -m unittest discover -s tests/documentation -v`, `git diff --check`.

Înainte de fiecare efect: argv/choice/source/library/access/producer-oracle/cleanup verificate fără efecte. Relay-ul host existent poate fi adaptat finit pentru endpointul allowlisted; API/DB/supervisor rămân pe control internal, fără proxy general. Master key/seif sunt montate numai ownerului; fără granturi ambientale. Noile DB-uri și imaginile au identități proprii; stop/remove numai inventarul atestat, fără prune/down-v/date șterse. PGDATA/logurile și FAIL/UNKNOWN se păstrează. Backup/restore minim se probează în root nou cu writers opriți și cheia master separată; nu modifică DB de operator.

## Probe/review/acceptare

**NOT_RUN / NOT_REVIEWED** la admitere. Pozitive și negative obligatorii sunt în prompt §Livrare: persistence/autounlock/LOCKED/no echo, duplicate/conflict/stale/foreign/revoke, Stop la sink/conexiuni reutilizate, categorii provider, incomplete/UNKNOWN/lost reply/no resend, crash file–DB și ledger fără dublare. Cel puțin două reviewuri read-only pe FREEZE identic pentru authority/secret/Stop și QA independentă pe artefact real afectat. Nici commitul candidat, nici source green nu sunt acceptare.

**Provider live: NOT_RUN, acord separat restant.** Operatorul introduce cheia numai în web după reviewurile/guardurile necesare și aprobă conexiunea/modelul/parametrii/inputul sintetic/testul finit. Nu acceptăm chei în chat/argv, nu fabricăm răspuns. Reticle: NOT_INTEGRATED până la o probă UI instrumentată admisă; Chisel: BLOCKED_NO_GO.

## Prerechizit Settings — integrat SOURCE scoped, T1 încă în lucru

Istoric inițial: candidat `686d342a1e5887e5b40ae97bc122f162a2faaa0d`, peste baza `b35c4de9aa968a48c7565e5685eefd0aa6b09f70`, cu 42 de căi verificate și CHANGES_REQUESTED. Remediile au ajuns la **`c19440a357866c162672be5400e08df4636b585f`**, tree `71ca72ca0da70844f0d690096322352b8f54aaaa`; 44 de căi candidat, cu delta finală de două fișiere verificată. Părintele a integrat cele opt commituri granulare ca `2169a3d`, `021c6ba`, `2b690af`, `3b29401`, `24a772e`, `7ce46f3`, `8b9fb59`, **`cea2aea367277d63ac28d3bb9b51fb71ea0b572f`** și a verificat scope-ul produs byte-identic cu snapshotul revizuit. 0001–0013 sunt neschimbate. **PARTIAL / SOURCE_REVIEW_APPROVED_SCOPED**, nu acceptare installed sau închidere T1.

Consumer SOURCE real: `/api/v1/settings/providers` → control privat → supervisor → seif/DB și receipt/readback; fără UI nouă, sender sau apel model. Ultima probă proprie a developerului, citită direct: targetul `test-provider-settings-pg` prin runnerul existent, **21 PASS/10.68s/exit0/family_drained=true**. Autounlock/reload aici folosesc obiect/app noi, nu restart instalat. Părintele a citit receipturile și confirmat absența celor **8 CID-uri proprii**, cu PGDATA păstrate. Primele unitare au folosit scratch implicit, apoi TMPDIR owned explicit; abaterea rămâne consemnată. Auditul a cerut înlocuirea certifi afectat cu versiunea fixată în lockul candidatului; nu este o admitere a clientului model de produs.

Două reviewuri independente pe același FREEZE au cerut remedii. [Original R1](api-key-runtime-t1-evidence/reviewer1-settings-api-review.md), [reproducer original R2](api-key-runtime-t1-evidence/reviewer2-source-probe.txt); copii byte-exact. Părintele a reprodus SOURCE F01/F02 și defectul R2, fără DB nouă/provider; a confirmat și callerii F03 din sursă. Aceste reproduceri nu sunt probe installed sau takeover PG.

| Finding | Dispoziție și remediu necesar |
|---|---|
| R1-F01 HIGH | CLOSED_SCOPED pe 3f7b4d3: bootstrap numai cu istoric DB gol; heads revoked rămân istoric. Ambele fișiere lipsă → LOCKED fără regenerare; revoke păstrat. |
| R1-F02 HIGH | CLOSED_SCOPED pe 3f7b4d3: tipurile se validează înainte de UUID; numeric/listă → LOCKED, metadata și revoke comis. |
| R1-F03 MEDIUM | CLOSED_SCOPED pe 3f7b4d3: comparație cu schema curentă și restore/readback al valorii originale în finally, fără aserțiuni slăbite. |
| R2-F01 MEDIUM / siguranță | CLOSED_SCOPED pe 3f7b4d3: rezervare cross-process înainte de programarea FS, păstrată până la final; drain refuză writer activ și queued, inclusiv takeover PG. |
| R2-F02 MEDIUM / cleanup | CLOSED_SCOPED pe c19440a: submit refuzat lăsa rezervare fără writer. Claim Future atomic eliberează numai jobul încă nepornit; callbackul rămas în coadă devine inert, workerul activ rămâne rezervat. |

Remedii minimale de același rol developer, cu RED→GREEN reale; [R1 re-review APPROVED_SCOPED](api-key-runtime-t1-evidence/reviewer1-settings-repair-review.md), [R2 re-review inițial cu findingul nou](api-key-runtime-t1-evidence/reviewer2-settings-repair-review.md), [R2 final APPROVED_SCOPED](api-key-runtime-t1-evidence/reviewer2-r2f02-review.md). Părintele a citit/adjudecat rapoartele și reprodus noul F02 înaintea remedierii; nu există finding deschis în acest scope. Finalul PG pe 3f7b4d3: **33 PASS/24.33s/exit0/drained**, inclusiv takeover1→2 și refuzul quiescenței premature; cele **5 CID-uri suplimentare** sunt absente/data păstrate la readbackul părintelui. Ultima delta c19440a: autor **5 SOURCE PASS/exit0**, API Ruff/mypy exit0, reviewer independent **5 PASS/2.40s/exit0**. Dovada PG este reutilizată strict pentru DB/admission/drain neschimbate, nu declarată execuție a noului scheduler. În checkoutul integrat, `uv sync --locked --no-config --no-python-downloads --directory api --python <3.13.15>` și `uv pip check` au trecut; importul seifului/crypto50.0.1/certifi2026.10.19 este real, nu installed QA.

**Continuare admisă, același developer:** formularul web Settings + decoder/client și release nou cu mounturi private numai supervisorului, pentru primul consumer instalat Save/readback înainte de alte helpers. Nu T2, nu model/sender în această subatribuire; restul T1 continuă după review/QA bounded. Ciclul harness-only pentru driverul SOURCE de schemă este **1**; eșecurile CLI largi rămân, fără rerun orb. Părintele a reprodus pe baza b35c4de cele două FAIL-uri ReadyJournal/Status (14 teste, 2 FAIL, exit1); sunt preexistente, nu regresii noi ale bumpului, dar nu devin green sau dispensă de canonical.

Rest T1: SystemOperation/Dispatch/Outcome V2, sender/relay, usage/Cancel/restart/no-resend, web/decoder, backup/restore/reactivare și distribuție; toate probele installed/browser/provider/canonical încă NOT_RUN. Readerii istorici instalați pentru drafturi/revizii, catalog/proveniență/publications, task/result/check/qualification/inbox și ledger/ModelTest V1 sunt **NOT_RUN**, nu incompatibilitate sau compatibilitate demonstrată. Nu s-a pornit T2.

## Recovery și rollback

La admitere rootul scratch era gol; efectele proprii ulterioare sunt consemnate mai sus. Git revert pentru commituri în ordinea dependențelor; acesta nu restaurează DB/seif/chei. Se păstrează datele/logurile private și identitățile before/after. Recuperare: CURRENT → acest registru → Git/status și predarea developerului din `ot1-0zxf62th/logs/developer-handoff.md`; nu relua toate probele. Următorul pas admis: continuarea Settings web/release în T1, review delta și prima QA instalată; nu T2 sau predare automată după fiecare commit.
