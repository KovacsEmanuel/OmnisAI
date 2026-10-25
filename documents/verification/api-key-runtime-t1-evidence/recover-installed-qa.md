# QA independentă — rezultat real

**Produs: PASS_EMPTY_MODEL_STORE_SCOPED. QA integrală: NOT_CLEAN_QA_PASS_OBSERVER_FAILURES_RETAINED.**

Pe aceeași instalare nouă: Start READY gen1/epoch1 → recover sănătos refuzat exit4/SUPERVISOR_NOT_DEAD, fără schimbări → un singur SIGKILL ACK/exit137/pidfd exit al supervisorului atestat → lease expirat → recover exit0/STOPPED gen3/epoch2 → Start explicit exit0/READY gen4/epoch3 → Stop final exit0/STOPPED gen5.

Source `e1b01a32b278b2368a2855083731f6273c70ba14`, tree `0665ae0d9616677d22d06996c36e1f4f4e5ac6a8`; release `d340a58a8e9912304613086f644b4f9c5f32aac50e4bd3ce8aa3b7c9d9bae177`. Profil normal t1-provider-settings/schema0015_model_test_v2. API113/CLI27 module exacte; payloaduri10 și sursă înainte/după identice. Root `/home/kali/.hermes/cache/scratch/rq-bn8ic9on`.

## Comenzi originale

| Consumer | Exit | Stare |
|---|---:|---|
| dead-recover | 0 | STOPPED |
| healthy-recover | 4 | UNCERTAIN |
| install-image | 0 | completed |
| install | 0 | completed |
| start-after-recovery | 0 | READY |
| start-initial | 0 | READY |
| stop-final | 0 | STOPPED |

Argv, stdout/stderr privat, durate și SHA-uri sunt în qa-result.json/evidence. Limitele produsului180/180/100 nemodificate. Outer 662.01s ≤1800s. Nicio reinstalare, rebuild de wheel/web, reluare SOURCE/review/canonical, Pair/browser/Save/Test sau apel provider.

## Eșecuri QA păstrate — nu devin PASS retrospectiv

1. Wrapperul inițial a ieșit1 după Start0/READY: oracle-ul QA cerea eronat toate tabelele domeniului goale, inclusiv pairing_challenge. Migrarea0002:21 inserează obligatoriu singletonul gol. Corectat numai readerul: count1 și digest/expiry nule/attempts0, fără citirea secretelor; model/provider zero rămâne obligatoriu. `install-failure.json`, `census-correction.json`, driverul original și logs private sunt păstrate.
2. Preflightul fault a ieșit1 înainte de fault.claim/efect: helperul de proces pentru forwarder încerca resolve(strict=True) pe executabilul containerului, inexistent ca path host. Corectat driverul la pidfd+start_ticks+UID+argv exact+inode kernel/readlink, cu aceeași atestare CID/image/daemon. `fault-failure.json` și `pid-preflight-correction.json` păstrează diagnosticul. Grantul a fost consumat o singură dată după corecție.

Acestea sunt două erori ale readerului QA, nu defecte produs demonstrate. Continuarea pe aceeași instalare și rezultatele ulterioare nu șterg exiturile1. Părintele adjudecă această limită; nu revendic QA curată sau T1 închis.

## Scenarii

| Scenariu | Rezultat |
|---|---|
| artifact_preflight | PASS |
| new_normal_installation | PASS |
| initial_start | PASS |
| original_qa_census | FAIL |
| corrected_schema_readback | PASS |
| healthy_recover_denial | PASS |
| original_fault_preflight | FAIL |
| single_authorized_supervisor_sigkill | PASS |
| expired_lease_readback | PASS |
| dead_owner_recover | PASS |
| recovery_shutdown_finalize_sql | PASS |
| explicit_restart | PASS |
| historical_open_and_data_retention | PASS |
| final_normal_stop | PASS |
| all_owned_resource_cleanup | PASS |
| model_provider_store_empty | PASS |
| consumed_inputs_unchanged | PASS |
| pending_SENT_crash | NOT_RUN |
| provider_calls_or_target_traffic | NOT_RUN |
| SOURCE_reviews_canonical_rerun | NOT_RUN |
| operator_installation_access | NOT_RUN |
| T1_closure_rollout | NOT_RUN |

## Persistență și cleanup

Instanță `22102af5-a9db-4c33-a174-4074fb98b6e0`, system_id `7700703568560332843`. Owner original `5d543981-0385-46ca-9504-59c10d189482`, owner recovery `5ac10d7f-4536-4050-ba47-3964b512ebb6`, owner restart `21210677-4d6b-4dba-b2d1-cea1cfb99201`. OPEN original păstrat byte-equivalent în SQL; SHUTDOWN/FINALIZE recovery autentice verificate după restart, împreună cu granturile/completionurile reale și noul owner/epoch/generation.

Daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`, endpoint `unix:///run/docker.sock`, proiect `omnis-local-c5d996e0d85c4181891d216f1182f480`. Readback final: toate6CID-uri ale celor două porniri și ambele2networkuri absente, zeroCID proiect, ambii forwarderi absenți, API/control UDS și cap absente, niciun listener pe127.0.0.1:41175. Directorii postgres/vault/vault-key păstrează dev/inode/UID/GID/mode. Datele/releaseul și imaginea `sha256:761b643665d730913f8df7889d0c75703f1cbfef8ecc91f9b0379d3b3eb6c949` sunt păstrate; nicio ștergere/prune/global. Identitățile complete sunt în `evidence/final-cleanup-readback.json`.

Grant consumat: `/home/kali/.hermes/cache/scratch/rq-bn8ic9on/fault.claim`, SHA256 `491661b31ae990619ddfaa3f9b8ebc761ce55692603cddfe9cd3a6ac9ceb8abc`. Receipturi autentice: `/home/kali/.hermes/cache/scratch/rq-bn8ic9on/s/omnis/stop-2c2a9ca9-4623-44e7-9698-7c053b4612b3.json` și `/home/kali/.hermes/cache/scratch/rq-bn8ic9on/s/omnis/stop-d3675ce6-17fb-49b1-8b65-d77b075bb937.json`.

## Limite

Empty model store, nu pending-SENT, Cancel/provider-live sau R2-NEW-01 final; nu închide T1 și nu aprobă rollout. Zero provider/model records și lipsa comenzilor sunt dovezi scoped, nu monitorizare universală a traficului. Instalarea operatorului și HTML-ul protejat nu au fost accesate; niciun fișier repo/commit modificat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
