# SL02 — execuția remedierii auditului aprofundat

Bază reală: `9dd45ea31370c0e35fe79fa62431fce45c13d0f7`, branch `p04-control-topology-wip`. Munca preexistentă: numai `documents/Omnis_Notite_Originale.html` untracked/protejat; AGENTS neatins. Fără push, SL03/SL04, owner WIP, upgrade global sau recuperare DB incertă. Gate-urile existente nu se slăbesc.

## Contract RT-F01 / RT-M01

Cerință: orice ieșire după spawn păstrează handle-ul forwarderului pentru cleanup, inclusiv finalizarea logului/stdout și handofful. Pozitiv: forwarder real verificat, oprit/reaped și listener absent înainte rescue. Negativ: lipsa pidfd ori cleanup nereconciliat produce UNCERTAIN și păstrează DB/locatorul; niciodată FAILED_CLEANED cu listener viu.

Fișiere: `cli/src/omnis_cli/start.py`, `cli/tests/test_forwarder_handoff.py`, test de integrare a callerului dacă necesar. Efecte permise: copii forwarder proprii, socketuri loopback/UDS private în scratch; Docker/DB substituite în regresii, etichetate explicit. Fără semnale pe PID-uri din metadate. Test: `cli/.venv/bin/python -I -m unittest discover -s cli/tests -p test_forwarder_handoff.py -v`, apoi controale caller/cleanup și suita CLI. Rollback: revert commit remediu + rebuild/retest; Git nu recuperează DB.

Model ownership: callerul deține un holder înainte de spawn; publicarea procesului/pidfd precedă toate close/finally și rămâne accesibilă la excepții. Semnalele de stop ale frontierei CLI sunt amânate, nu ignorate, numai peste spawn/publicarea handle-urilor; după publicare stopul intră în cleanup. Nu se presupune că tuple return sau returncode=None constituie handoff atomic. Nu se normalizează politica de semnale a unui caller de bibliotecă.

## Inventar și readback inițial

`make test-cli`: exit 0 pe baseline; log scratch `omnis-remediation-baseline-cli.log`. Python din venvurile API/CLI este 3.13.15; uv verificat 0.12.19 și Node 24.21.0 în toolchainul scratch istoric. Python global 3.13.12 nu este folosit drept pin de produs. Docker 27.5.1 și Compose 2.32.4 disponibile; topologia UDS/fără porturi publicate se păstrează.

RECOVERY_PENDING: receiptul vechi `/home/kali/.hermes/cache/scratch/s2i-841796q5/probe-receipt.json` există și declară UNCERTAIN. Readback Docker exact CID `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0`: running/healthy, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, attempt `f8e93e10-1c04-4c2d-a43b-f6ad3167fd51`, bind PG18 în state rootul vechi. Identitatea neschimbată nu dovedește drenarea familiei/daemonului. Fără mutații/stop/adopție/rescue; recuperarea rămâne separată BLOCKED/RECOVERY_PENDING, nu ALL_CLEAN.

## Registru obligatoriu

RT-F01, RT-F02, AR01, AR02, RT-PG01, AR03, RT-M01, M03, M09, M18, M20, M21, M22 și RECOVERY_PENDING sunt urmărite separat. Stare inițială: ÎN LUCRU, fără PASS nou. Matricea celor 26 și verdictele finale se vor completa numai după execuții și review adjudecat.

## Integrarea corecțiilor — checkpoint ÎN LUCRU

Snapshot de produs: `c51faf5baae000a23eba9a7a0fce1623ce5a605a`; commitul procedural ulterior `0c315c6` nu schimbă bytes de produs. Nu există încă verdict global nou sau acceptare instalată finală; probele suplimentare și reviewurile finale sunt în curs, înainte de gate-urile secvențiale și CLOSE. README/harta păstrează verdictul istoric până la adjudecarea finală.

| ID | Cod/commit și dovadă reală | Review/adjudecare și limită |
|---|---|---|
| AR01 | `63e6415`, tipuri/set de câmpuri exacte; regresie UDS HTTP reală, booluri contractuale pozitive și numeric/opposite/string/null/missing/extra/reasons negative | `review-ar01-ar02.md`: REVIEW_PASS_SCOPED individual, patch SHA `3a1edd0d81f1835c13e59c4608e011e51e84ae38a8886a4dccf43116044b24ad`. Reviewerul a construit snapshoturi independente HEAD/AR01/AR02/combinat și a executat RED/GREEN în wheel/cwd extern; parent a aplicat patchul verificat. Nu false-ready live al API-ului, producător nemodificat. |
| AR02 | `2002fc0`, pointer format integer exact; private files și consumatori reali, strict manifest/SC02 păstrate | Același raport, REVIEW_PASS_SCOPED separat; patch SHA `e0d24c67e43217329fe288f3421ff4bfc3e9cc0ee47426d0c8ca4d88300d0fd0`. Synthetic checksum-bound bundle pentru parser, nu startup OCI. |
| RT-F02 | `3f67ad1`, refuz SIGCHLD incompatibil înainte spawn, pidfd-only stop, ACK/WNOWAIT și flags conservatoare; 22 teste GREEN; parent a executat cele cinci boundary probes exit 0 | `review-rtf02-rtm01.md`: defectul inițial GREEN. F-R02-01 adjudecat **numai owner standalone exclusiv continuu spawn→pin→reap**, documentat în `9ea94f3`; arbitrary concurrent embedded reaper/producer/policy replacement UNSUPPORTED. Reap înainte pin real refuză sigur; reuse lookup era modelat, nu PID reuse kernel/victimă reală. Nu pretindem exclusivitate impusă callerilor arbitrari. |
| RT-M01 client | `9ea94f3` explică ACK din exit0 observat, nu detectarea universală ECHILD; controlul permanent exit0 adăugat lângă exit1/-9 pe același seam, GREEN | F-R02-02 INFO adjudecat fără false ACK demonstrat. F-R02-03: leader-only stop poate lăsa descendent viu, dar uncertain/family_drained=false păstrează DB; nu family drainage sau daemon completion pretinse. |
| RT-F01 / RT-M01 handoff | `c51faf5`, holder caller-owned înainte spawn, proces/pidfd păstrate peste log/pipe close/finally și handoff; baseline RED în logurile RT-F01; source și wheel GREEN | `omnis-frev02-final-review.md` APPROVED_SCOPED pe SHA start `4a7197fadb1dd1f9f4b23f802a93171b5974f1bf8d3bbd0eccf3bfc452f853e8`, caller/handoff/stop-boundary hashuri identice la integrare. Docker/DB substituite în regresiile de componentă, copii/listener/pidfd reale. OCI final încă restant. |
| F-REV01 / F-REV02 | Repeated-stop cleanup RED reparat; primul-stop în retry recuperabil RED reprodus și permanentizat pentru SIGTERM/SIGINT, controlul fără stop păstrat | Re-review independent verifică și eroare generică propagată înainte de except-binding. Mutant types-only eșuează cu cleanup absent/listener viu; parent a executat provenance actual exit 0. `sys.exception()!=None` singur nu dovedește cancellation. |
| RT-PG01 | Oracle independent de jurnal, pin copil direct verificat + inodes/LISTEN; control real fără identitate publicată RED→GREEN; FORWARDING integrat ca probă instalată | Review inițial aprobă detectorul scoped, dar P2-PG-RESCUE cere păstrarea rescue-ului după FAIL. Corecție în probe, nu flag/bypass în produs; review final în curs și commit/gate restante. |
| AR03 / M03 | `ControlRuntime.attest` și `validate_config` reale: 3 runtime controls + 40 mutații refuzate; config control + 8 refuzuri. Preflight actual: platformă/arch/root UID/GID/ambient/socket/daemon/image/tag/receipt/Compose absent/v1, zero resource effects | Review inițial aprobă AR03 scoped; config nu validează mounts/command/env, coverage-ul runtime nu se transferă. No-effects suport extins unit, numai inspect/config/receipt/platform seams substituite. Review final/commit și probe instalate finale restante. |
| M20 | Actual cleanup predicate cu faults inventory/identity/non-DB removal și controale valide; jurnal failed chiar cu result resources-clean trebuie exit 4; testele GREEN | Docker inventory/resource ops substituite explicit; producătorii uncertainty real-child sunt acoperiți separat RT-F02. Review/commit suplimentar restant. Vechea DB nu este fixture. |
| M09 / M18 | Probe instalate integrate: DB-only first-start exit înainte health, API readiness expiry și lock startup 180s înainte efect | **NOT_RUN pe snapshotul final.** Date/diagnostic păstrate, exact resource readback înainte rescue, wall-clock + cleanup allowance separat; nu se acordă COVERED din design. |
| M21 | Refuz neREADY/stale păstrat; retry instalat cere RECOVERY_REQUIRED fără mutația jurnalului/resurselor | Crash/stop/recovery și bariera concurentă rămân owner B01f/SL04/L08-core; SL03 pair/open viitoare trebuie să refuze neREADY. Nu implementare SL03/SL04. |
| M22 | `a967f0b`, contract aprobat în planul canonic B01f înainte G00 | Port 1024–65535, CLI explicit > config.toml > defaults, origin existent invariant; startup 30–300s, shutdown 15–180s, cleanup 30–180s integer finite. Numai lacuna de alocare închisă; parser/probe **nelivrate, PARTIAL**. |

### Corecțiile oracle-urilor instalate

Contract delimitat: `installed_start.py`, `installed_start_failures.py`, `start_oracle_probe.py`, `test_installed_start_failure_controls.py`; copii/listenere proprii și seam-uri Docker substituite numai în regresii, fără mutații asupra DB vechi. Negativul trebuie să păstreze FAIL-ul procesului/listenerului înainte rescue, apoi să dovedească rescue independent prin pidfd și absența listenerului; zero DB teardown sub incertitudine, receipt FAIL/UNCERTAIN. Lockul refuzat trebuie să lase HOME/state/runtime noi goale, pe același canal cu un control fără efecte. Rollback: revert corecția probei și rerun; niciun rescue nu promovează eșecul produsului în PASS.

Parent a reprodus ambele findings în `omnis-probes-permanent-red-valid.log`: 3 metode, controlul pozitiv trece, două failure semantice (diagnostic mascat/rescue lipsă și runtime-write acceptat). Prima fixture era invalidă prin `NoDocker.inspect` absent; corectată înainte de RED valid. După remediul minimal, `omnis-probes-permanent-green.log`: exit 0. Clock sintetic al controlului lockului verifică **oracle-ul**, nu execuția instalată de 180s. Readiness expiry se măsoară de la faza observată și separat de CONT; pauza nu suspendă deadline-ul monotonic.

### Verificări executate de părinte, fără transfer de verdict

- `make test-cli`: **119 teste, exit 0**, `omnis-remediation-all-source.log`.
- Ruff check/format pe surse/teste/integration, mypy strict pe 12 module: exit 0; `git diff --check`: exit 0.
- `make check-cli-wheel UV=<uv pin-uit>`: **119 teste din cwd extern, exit 0**, `omnis-remediation-final-wheel.log`; wheel SHA256 `381492d04293d5b7177f69ad6f02281bc08f75e6ce416ea02322282807c45a22`. Installed `start.py/start_runtime.py/health.py/release.py` comparate byte-for-byte cu sursa remediată, toate identice, în afara checkoutului.
- Gate-uri intermediare `proc_96f81016aea9` și `proc_9b71b401e6ea`: make check exit 0, snapshoturi **anterioare** corecțiilor/integrărilor finale. Nu sunt gate-ul final.
- Verificare explicit **ad-hoc**, nu suite green: verifier tempfile `hermes-verify-*` a executat 8 comenzi / 69 execuții de teste, toate exit 0, hashes de scope neschimbate; verifierul șters. Include și candidatul scratch și repetări, nu 69 teste unice. Prima versiune a verifierului a avut SyntaxError de escaping, corectată înaintea rulării citate; niciun defect de produs inferat.
- Readback nou read-only al receipt/CID vechi: FAIL/UNCERTAIN, DB running/healthy, project/attempt identice, `postgres/` și pathname API socket prezente. **RECOVERY_PENDING** rămâne deschis separat; zero rescue/stop/adopție, nu ALL_CLEAN.

### Rapoarte întârziate și unelte

Notificarea `deleg_b3489cf2` privește autorii izolați pe baseline `9dd45ea`, necomiși conform contractului delegării. Blocajul make check din worktree-ul AR (api/.venv absent, exit 2, runner DB nepornit) și interdicția Docker din workstreamul RT sunt limite ale acelor delegări, **nu** rezultate ale gate-ului principal sau regresii ale commiturilor integrate. Nu reintroducem necomis/NOT_REVIEWED peste reviewurile și commiturile actuale.

Reticle: CLI/procese **NOT_APPLICABLE**, UI Omnis **NOT_INTEGRATED**, smoke istoric TOOLING_ONLY netransferat; nicio execuție nouă. Chisel pin auditat NO-GO, **BLOCKED/NOT_RUN**, fără repo/home/profile access sau fallback. Reviewerii independenți, nu aceste unelte, emit concluziile delimitate.

**Rest înainte CLOSE:** trei direcții de review final și adjudecare; commituri granulare ale probelor suplimentare; make check apoi check-installed-start secvențial pe bytes finali; matrice 26/26 renumărată după rezultate; proiecții documentare și Git verificate. REMEDIATION_PASS și READY_FOR_SL03 nu sunt acordate în acest checkpoint.
