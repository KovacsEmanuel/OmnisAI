# R1 — APPROVED_TEST_SOURCE_SCOPED

## Decizie și identitate

**APPROVED_TEST_SOURCE_SCOPED**: nu am identificat un blocker în delta test-only care să împiedice admiterea QA SOURCE bounded afectate, după reviewul complementar și decizia părintelui. Nu este rezultat QA, acceptare canonical5, runtime sau T1.

- BASE: `bed2ba1dfd7355d15cf7ef56f07e33771eb0dbbe`.
- HEAD revizuit: `f26beb4e9f7611dbec0b0c1a15f03e1761fc8317`.
- Tree citit din Git: `539364a3d9bee80bab5e2398f65c2c7ead03b870`.
- Checkout: `/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src`, branch `impl/t1-integrated`; status curat la citirea inițială și la ultima verificare Git.
- Diff exact: opt fișiere, 88 inserări / 45 ștergeri. Nicio schimbare de produs, runner, manifest, dependențe sau migrare în acest diff.

**Cerință → consumer → risc → decizie:** callerii SOURCE canonici trebuie să ajungă la pozitivul/refuzul/lifetime/readerul intenționat; riscul este verde pe validare incidentală ori confundarea V1 cu decoderul public V2; verdictul admite numai QA SOURCE afectată, nu frontiera PG/native/live. Contorul harness-only transmis rămâne 2/2; reviewul nu îl resetează și nu creează o procedură nouă.

## Fișiere schimbate revizuite

Toate sub `api/tests/`:

1. `test_contract_denominator.py`
2. `test_result_qualification.py`
3. `test_model_sender.py`
4. `test_model_test_operation.py`
5. `test_model_test_prepare_source.py`
6. `test_model_test_routes.py`
7. `test_runtime_supervisor.py`
8. `test_stop_schema.py`

Am citit diff-ul integral și definițiile/callerii relevanți; am păstrat scope-ul anterior neafectat, fără reauditarea runtimeului general.

## Verificarea cauzală producer / oracle / caller

| Remediu | Readback source și predicat păstrat |
|---|---|
| Material SOURCE / HOME | `test_contract_denominator.py:36–64` și `test_result_qualification.py:62–114`: se schimbă exclusiv rădăcina `TemporaryDirectory` la `os.environ["TMPDIR"]`, prerechizit deja folosit de `conftest.py:23–25`. Aceiași producători `records_seed`, DTO/material/capture/build; context managerul elimină fixture-ul după capturarea datelor în memorie. Nicio relaxare a oracle-ului. Denominator pornește pozitiv prin CLI înainte de atac și verifică reason/exit (`:198–208,295–304`); qualification păstrează create/read/replay, lineage și snapshot/no-write (`:422–448`), foreign-owner înainte de lookup (`:751–778`) și rollbackul ambelor înregistrări (`:787–795`). |
| Broker absent, nu path UDS prea lung | `test_model_sender.py:202–217`: fixture-ul IPC existent, path absent și lungime bytes `<108` sunt afirmate înainte de `ModelSender`. Se păstrează reason-ul exact `RELAY_CONTROL_UNCERTAIN` pentru metadata/send și `finally: close`. `supervisor/model_relay.py:140–145` și `model_sender.py:282–285,393–396` confirmă clasificarea control-channel, nu provider outage. Nu se introduce broker/dublură nouă. |
| DTO valid înainte de lifetime/refuz | `test_model_test_operation.py:151–157,218–235` și `test_runtime_supervisor.py:142–151`: revision/consent satisfac validatorul real (`model_test_models.py:50–94`); `selection_ref`/prompt rămân negative izolate într-un request altfel valid. Refuzul ownerului închis este `CatalogError(TASK_UNAVAILABLE)`, nu `ValidationError` pentru câmpuri lipsă; `model_test_operation.py:151–162` confirmă frontiera efectivă. |
| V1 lifetime pe transport privat păstrat | `test_model_test_operation.py:159–210` folosește helperul existent `test_local_control.request` (`:119–136`), cu socket/envelope/capability și închidere în `finally`, apoi validare explicită prin V1 `model_test_models.ModelTestView`. `LocalControl` validează frame/capability/UID și cheamă callbackul (`local_control.py:295–325,171–184`); callbackul este ownerul real, nu o replică a răspunsului. Nu mai folosește decoderul public V2 (`model_test_routes.py:77`). Rămân PENDING, client închis înaintea taskului, >4 secunde, single-consumption/no-refill, Stop, owner replacement, terminal-write failure/UNKNOWN și no-resend. Producătorul V1 creează taskul separat și persistă terminalul în `finally` (`model_test_operation.py:229–269`); testul nu îl înlocuiește cu un native/provider real. |
| Closure stock owner / watchdog | `test_model_test_prepare_source.py:243–270,371–427`: se păstrează extracția corpului existent `maintain_owner` din `test_contract_method_pg.py:9103–9116` și heartbeat→quiesce→renew din supervisor `__main__.py:207–232`. `NativeTaskOwner` real inert, `startup_generation=0`, `probe=None` și `owned_status(generation=0)` completează closure-ul cerut, fără schimbarea algoritmului. Ramura stock trebuie să efectueze cele 12 citiri owned_status și zero quiesce. Ceasul/deadline-ul 4,5 secunde, controlul heartbeat-only care expiră, READY/MANAGEMENT, Stop/expiry, dovezile close și socket/watchdog cleanup rămân. Ownerul este închis în `finally`, apoi runtime clientul. AIAgent/signal/storage sunt în continuare doubles SOURCE. |
| ASGI actual, V2 actual | `test_model_test_routes.py`: importă V2 `model_test_contract.ModelTestView`, aceeași clasă folosită de router. Requestul pozitiv include revision/consent; PUT verifică 202, GET 200, egalitate completă a proiecției, action/consent/revision și no-store. Negativele păstrează Host, sesiune, Origin/CSRF, extra fields, tipuri stricte, missing/false consent, missing/invalid revision, duplicate JSON și body-limit. `exchange.assert_not_awaited()` înainte de pozitiv împiedică verde pe un dispatch neautorizat. Ordinea reală Host/Origin/body/session/CSRF este în `host_origin.py:104–112,157–208`; duplicate JSON este verificat de `model_test_routes.py:93–104`, iar start transmite câmpurile la `:194–205`. Engagement readerul este interzis în controlul pozitiv dedicat. Nu se pretinde că dublura control_exchange demonstrează dispatch/provider real. |
| CURRENT schema vs istoric | `test_stop_schema.py:65–71` păstrează egalitatea independentă Alembic head = `SCHEMA_REVISION` = literal CURRENT `0015_model_test_v2`; nu transformă verificarea în tautologie. `core/db.py:16` și `migrations/versions/0015_model_test_v2.py:5–6` confirmă CURRENT și părintele 0014. Parametrizarea upgrade-ului istoric din `test_model_test_v2_migration.py:27` și readerii istorici 0014 din `test_contract_method_pg.py` rămân nemodificați. |

Nu am identificat eliminări de teste/decoratori, opt-in native nou, slăbirea defaultului SOURCE/V1 receive-only ori înlocuirea efectelor neadmise cu o afirmație de runtime PASS.

## Dovezi și limite

- Execuție proprie: numai citiri source/public freeze, `git status`, `git rev-parse`, `git diff --stat`, diff integral și `git diff --check BASE HEAD` — ultima comandă exit 0. Nu am rulat pytest/lint/mypy sau vreun consumer cu efecte.
- Am citit `logs/c4fix-integrated-freeze.json`. Identitatea tree din Git corespunde freeze-ului. Maparea bijectivă a celor 81 FAIL originale la cele 308 PASS și rezultatul autorului 308 PASS/0 fail/0 skip, 138,89 s, plus static checks sunt dovezi furnizate de părinte/autor; nu le prezint ca rerulare independentă R1. Manifestul integrat păstrează explicit `parent_source_qa=NOT_RUN` și `canonical5=NOT_RUN_NOT_ADMITTED`.
- Probleme de lookup fără impact asupra verdictului: o interogare de căutare a fost reluată cu formatul real al rezultatului; unele căi de definiții presupuse nu existau, iar definițiile relevante au fost localizate în `api/src/omnis/supervisor/`. Manifestul companion al autorului nu a fost găsit la calea încercată `logs/authorc4fix-freeze.json`; nu am folosit presupusa lui existență ca dovadă.
- Nicio citire de mediu, credentiale, profil privat sau log canonical4 brut. Niciun test, PG, Docker, native child, browser, build, serviciu, provider/network, download sau Git write. Singurul fișier creat este acest raport.
- Reticle **NOT_APPLICABLE**; Chisel **BLOCKED_NO_GO**.

**Limita finală:** verdict de conformitate statică al testelor, suficient din perspectiva R1 pentru QA SOURCE afectată pe exact acești bytes. Parent QA rămâne de executat; T1 rămâne PARTIAL / NOT_ACCEPTED, canonical5 neadmis, iar source/distribution/installed/Model Test/live rămân axe separate. Nu am verificat din nou probele vechi neafectate; riscurile runtime și sender installed/outcome/usage/crash-SENT/no-resend/R2NEW01 rămân deschise.
