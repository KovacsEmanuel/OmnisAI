# QA instalată — prefix ModelTest după restart

**PASS_SCOPED, runner final exit 0. T1 nu este închis; adjudecarea aparține părintelui.**

## Artefact și fixture

- Candidat sursă: `5d5bbfb35b3833ef6d8be0f2e2651cf235a515a2`; bundle normal `a5b89393716f31868e97d7f5201249ab1de76f6395300cecc5d657890e34dba4`, profil `t1-provider-settings`, schema `0015_model_test_v2`.
- Fixture unic nou: `/home/kali/.hermes/cache/scratch/ip8-gxpeuz9_`; port `42997`; HOME/c/d/s/r/TMPDIR private. CLI instalat offline din wheel `9f73d9944676f812f2f23c3a79814d8b2323fa721c0386dd54953e112116eb24`, Python 3.13.15, uv 0.12.19.
- Imagine păstrată: `sha256:0daabbeb8a18e433418418d86c417620eefa8f09c37fd3cf344c261dfe4113ee`.
- Proiect: `omnis-local-46647e1d898d4d6e8f586d377f6c84d4`; daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`, `unix:///run/docker.sock`. Trei roluri reale, DB atestată cu imaginea PostgreSQL proprie, nu cu labelul API.
- Modulul instalat `omnis/supervisor/__main__.py`: SHA256 `1c821dd0d0a99496e6d4245fe9b82939495d48c850165413bc0d87baf82da82a`, verificat în ambii supervisori fără instrumentarea entrypointului.

## Rezultat real

| Observație | Initial | După Stop → Start explicit |
|---|---|---|
| CLI | READY, generation 1, epoch 1 | READY, generation 3, epoch 2 |
| Primul `PUT /api/v1/model-test` autorizat | **409 REVISION_CONFLICT** | **409 REVISION_CONFLICT** |
| Operation ID nou | `c9c6066f-e3e2-472d-bcc3-8df0c4d56a12` | `ba9a76a1-f21a-4e48-bde1-59657a37fa3e` |
| Selecție / conexiuni / vault | null / [] / UNCONFIGURED | null / [] / UNCONFIGURED |
| Metadata | NOT_REQUESTED | NOT_REQUESTED |
| Supervisor PID / start_ticks | 2928342 / 43934809 | 2949604 / 43960952 |
| Execuție owner | `5dad6044-fd10-4fcf-9b87-366d470feecd` | `2fdc38ad-5bc7-46ce-815c-5c31a8e961c9` |

Corpul real a avut `expected_selection_revision=1`, `consent=true`; Pair normal PTY/HTTP, fără coduri/cookies/CSRF persistate. După restart primul callback ModelTest a fost mutația, înaintea readerului ModelTest. Fără Refresh, secretSave sau metadata fabricată.

Toate cele opt tabele din census sunt zero: trei tabele provider, `system_operation`, `model_command_v2`, `model_dispatch_v2`, `model_dispatch_event_v2`, `model_record_v2`. Refuzul real este lookupul selecției absente, anterior bindingului și dispatchului provider. Zero provider IO pentru această cale este probă compusă din refuzul real, census și topologia normală internă, **nu observație universală de syscalls**.

DB păstrată: instance `fd5453f6-f980-4d2b-ae34-5ae221835f3b`, system ID `7700880445257678891`, bind-root dev/inode `[2049,10390704]`. Kernel boot ID este același, corect pentru același host; CID/PID/start_ticks și owner/epoch noi dovedesc restartul procesului, nu doar înlocuirea unui obiect.

## Cleanup și erori păstrate

- Ambele `omnis stop --json`: exit 0, STOPPED; statusurile ulterioare exit 0/STOPPED.
- Readback final exit 0: toate cele șase CID-uri și ambele rețele exacte absente, ambii supervisori și forwarderi absenți; listenerul și socketurile proprii absente. PGDATA `/postgres/18/docker` și bind inode păstrate. Imaginea reparată și bundleul rămân disponibile.
- Înaintea restartului, helperul instalat fără SO_REUSE a refuzat inițial `PORT_CONFLICT`; s-a observat disponibilitatea după 54.032 s în limita finită, fără Start repetat. Prima refuzare rămâne în fișier; cauza TIME_WAIT nu este atribuită fără captură directă.
- Prima execuție a runnerului: exit 1 **după primul ModelTest corect**. `process_identity` destinat hostului încerca `resolve` pentru `/usr/local/bin/python3.13` din namespace-ul containerului. Corecție exclusiv QA, un singur ciclu: PID/start_ticks din `/proc`, readlink executabil numai metadata, CID/labels/daemon atestate. Produsul nu a fost modificat.
- Continuare pe același fixture, fără reinstalare, fără repetarea primului Start sau ModelTest. O nouă sesiune Pair a permis numai refacerea readerilor după pierderea sesiunii în memorie; baseline-ul inițial zero trecuse înaintea cererii, proiecția detaliată reținută a fost recitită ulterior. Prima eroare și runnerul original sunt păstrate.

## Comenzi și dovezi

Comenzi instalate: `install --bundle <bundle>`, `install-image`, două `start --no-open --json`, Pair normal, două `stop --json`, statusuri. Toate comenzile produsului reținute au exit 0. Configurație explicită 180/180/100 s; limitele produsului model/metadata nu au fost schimbate.

- `preflight.json`: argv, roots, schema/query/producer/error/cleanup/sinks, hashuri înaintea efectelor.
- `journey-v1.py`: runner inițial SHA256 `0fa25cd42ddef9be642e472c29e7db30ffe71599f3fd1855dcbdddc8fab49617`; `result-v1-failed.json`, `first-failure.json`.
- `journey.py`: runner corectat SHA256 `a9a9b9777cd3895200b59f1e216b016a25c50ccf222b75f3f2823ebde3276d82`; `repair-preflight.json` verifică înaintea continuării.
- Invocare finală: `/home/kali/.hermes/cache/scratch/ip8-gxpeuz9_/v/bin/python -I -B /home/kali/.hermes/cache/scratch/t1-pr-ct0vinu2/evidence/installed-prefix/journey.py resume` → **exit 0**.
- `initial-first-model-test.json`, `post-restart-first-model-test.json`: diagnosticele originale înainte de cleanup.
- `result.json`: toate valorile/callerii/cleanup; `final-readback.json`: observație exactă independentă post-Stop; `report.json`: raport structurat. Inputurile de produs și cele două versiuni ale runnerului sunt legate de hashurile reținute.

## Limite

Nu este PROVIDER_SUCCESS, dispatch sau model completat. Nu s-au reluat SOURCE/canonical/QA veche, nu s-a injectat timing/fault și nu s-au atins instalările/datele/cheile operatorului. Proba SOURCE deterministă cu două tickuri înainte de OPEN rămâne separată. UI neschimbată, fără click/accesibilitate; Reticle NOT_APPLICABLE, Chisel BLOCKED_NO_GO. Nicio modificare de produs, commit sau push; următoarea decizie aparține părintelui.
