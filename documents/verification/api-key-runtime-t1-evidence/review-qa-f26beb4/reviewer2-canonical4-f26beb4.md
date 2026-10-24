# R2 independent — canonical4 test-only / documentary delta

## Verdict

**APPROVED_TEST_GATE_SOURCE_SCOPED** pentru delta SOURCE și **APPROVED_DOCUMENTARY_DELTA_SCOPED** pentru delta documentară. Niciun finding concret blocant în scope-ul R2. Poate fi admisă QA SOURCE afectată, bounded, după adjudecarea părintelui și verdictul complementar R1; acest review nu admite un canonical nou, integrarea în principal sau acceptarea T1.

Cerință → consumer → risc → decizie: remediile celor 81 de eșecuri trebuie să păstreze frontierele autentificării/inputului, lifecycle/Stop și originea SOURCE; testele ASGI/control/stock-owner și CURRENT/registrul sunt consumatorii afectați. R2 verifică dacă remediul ajunge la controlul intenționat fără a-l ocoli ori a promova dovada la runtime. Verdictul permite QA afectată, nu înlocuiește această QA.

## Identități exacte

- SOURCE: `/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src`, HEAD **f26beb4e9f7611dbec0b0c1a15f03e1761fc8317**, tree **539364a3d9bee80bab5e2398f65c2c7ead03b870**, bază **bed2ba1dfd7355d15cf7ef56f07e33771eb0dbbe**. Curat la început și la readback final. Întreg tree identic autorului **9353f271045fc871e25d0053e468afbb53c1173f**.
- Documente: `/home/kali/OmnisAI`, HEAD **b77ef607c06f2af6eff708f6c793a4737b8f3fb6**, tree **29eeb9ee70bbfc57bad017a10a482708f4f0635f**, bază **4e687eb2a9c6e6b98ae02ba487bfc6b17446dc32**. Fără modificări tracked/staged; singurul untracked observat este HTML-ul protejat, necitit/neatins.
- Scope SOURCE: exact `api/tests/test_{contract_denominator,result_qualification,model_sender,model_test_operation,model_test_prepare_source,model_test_routes,runtime_supervisor,stop_schema}.py`; 88 inserări/45 ștergeri. Nicio schimbare API/CLI produs, runner, manifest, migrare, schemă, dependență sau selecție.
- Scope documentar: delta README, `documents/verification/implementation-status.md`, `documents/verification/api-key-runtime-t1.md` și rezolvarea linkurilor noi către dovezile publice deja copiate. Nu audit recursiv al rapoartelor istorice ori reverificare a celor 16 originale.

## Constatări pe criterii

| Criteriu | Readback și concluzie scoped |
|---|---|
| Host/Origin/auth/CSRF/body | `api/tests/test_model_test_routes.py:74–134`: request pozitiv altfel valid; Host străin 400, lipsă cookie 401, CSRF/Origin străine 403, duplicate JSON 422 și body valid cu padding peste 4096 → 413 înainte de control. `exchange.assert_not_awaited()` precedă pozitivul. Răspuns V2 exact, 202/no-store, readback 200 și lipsa câmpurilor private păstrate. Doubles de sesiune/DB/control declarate, nu dovadă live. |
| Consimțământ/revision/negative autentice | Ruta refuză false, integer/missing consent, missing/zero/bool revision și câmpuri extra. `test_model_test_operation.py:213–235` furnizează revision/consent valide, astfel încât promptul și referința privată sunt faulturile testate, nu o lipsă unrelated. Validatorii reali `model_test_models.py:11–94` rămân neschimbați. |
| V1 privat ≠ V2 public | `test_model_test_operation.py:151–210` folosește helperul existent `test_local_control.request`, envelope cu capability și LocalControl real, verifică `ok` și decodează DTO V1. Disconnect/lifetime, Stop, terminal-write failure, replay și lipsa refill-ului rămân. Decoderul public V2 din `model_test_routes.control_exchange` nu este modificat sau făcut tolerant. Testele ASGI folosesc separat DTO V2. Niciun agent/provider autentic lansat de acest remediu. |
| Bounds/TMPDIR | Cele două fixture-uri material SOURCE folosesc TMPDIR explicit owned, nu HOME privat implicit. `test_model_sender.py:202–207` reutilizează fixture-ul IPC existent și cere path encoded <108 bytes și absent, pentru a ajunge la missing-broker real. Nu se măresc deadline-uri, timeout-uri sau capuri de produs. |
| Closure stock/Stop/expiry/finalizer | `test_model_test_prepare_source.py:243–430` păstrează extracția AST a tick-ului stock și folosește `NativeTaskOwner` real, inert, cu startup_generation=0/probe=None și `owned_status` async generation=0. Constructorul nu lansează lucru. Stock cere 12 owned_status și zero quiesce; renewal/expiry, intentional Stop, refuzul renew post-close și cleanup socket/watchdog rămân. Finalizerul cheamă `close_model_test()` real și verifică closing, apoi runtime.close. `test_runtime_supervisor.py:138–154` folosește un start valid ca să observe TASK_UNAVAILABLE după drain/join, nu un refuz de schemă anterior Stop. |
| Default/legacy/noexec | Comparația AST bază→HEAD confirmă exact aceleași 58 definiții de test și aceiași decoratori în toate cele 8 fișiere. Fără skip/ignore nou sau mutări. Selecția/markerii/helperul strict preflight sunt neatinse în această deltă; inventarul reținut 3171=3164 default +7 legacy nu a fost recollectat. Execuțiile native autentice și descriptorul privat rămân numai explicit legacy; SOURCE pur/V1 receive-only implicit, fără acces implicit la input privat introdus de remediu. |
| Schema | `test_stop_schema.py:66–71` aliniază numai așteptarea CURRENT la 0015_model_test_v2; păstrează autoritatea stop-reconciliation și owner_uuid. Nicio migrare sau istorie rescrisă. |

## Dovadă citită, nu executată din nou

Citire statică cu Python `-B`/stdlib și Git read-only, fiecare comandă Git cu HOME/XDG_CONFIG_HOME cerute; comenzile de inspecție au exit0. SHA256 pentru toate cele 8 fișiere coincid cu `c4fix-integrated-freeze.json`; test names/decorators comparate programatic cu baza, iar tree-ul autorului este identic integral.

`c4fix-commands.json` fixează interpretul API `integration-src/api/.venv/bin/python`, `-I -B`, sys.path explicit în **canonical4-repair-src** și aserțiuni de origine pentru omnis/omnis_hermes; `c4fix-all8-final.log` arată acele origini în rootul autorului. Nu pretind import fresh din integration-src: transferul se bazează pe identitatea bytes/tree. JUnit citit: **308 testcase-uri, 0 failure/error/skip, 138.887s**; logul autorului: **308 passed/138.89s**. Toate cele **81** mapări unice sunt programatic incluse în testcase-uri PASS. Ruff/format/mypy finale scoped au exit0 în command record; erorile/intermediarii anteriori nu sunt transformați în succes. Acestea sunt rezultate ale autorului, nu QA independentă executată de R2.

## Onestitatea documentară

Toate liniile modificate din cele trei documente au fost citite. Linkurile locale de pe liniile adăugate și ancorele Markdown vizate se rezolvă (README 1, status 16, registru 9). CURRENT, harta și registrul păstrează consistent:

- f26 candidat neintegrat în principal, review nou PENDING/QA părinte NOT_RUN la freeze, 308 numai SOURCE autor;
- canonical4 **FAIL**, API completă 81FAIL/3018PASS/65SKIP/7deselectate/3010.89s/exit2/drained, nu întrerupere și nu nou PASS; etapele ulterioare NOT_RUN;
- QA anterioară **134 mixed**, inclusiv wheel CLI, nu 134PG-only/native/provider/canonical; primul 133PASS/1FAIL și remediul prerequisite PATH rămân explicite;
- distribuția/Settings/restart/restore/reactivarea rămân dovezi scoped, nu ModelTest/outcome/usage installed, crash/SENT/no-resend, installed historical readers sau T1;
- R2-NEW-01 final și ambele counter2 deschise, recuperare fără readopție/reexecuție, provider metadata/live neautorizate și fără T2 automat.

Nicio promovare factuală blocantă identificată în delta frozen. Readbackul stării externe/cleanupului istoric este contextul furnizat părintelui, nu o măsurare proaspătă a reviewerului.

## Limite / predare

Reticle **NOT_APPLICABLE**; Chisel **BLOCKED_NO_GO**. Nu au fost rulate teste, collect-only, PG/Docker, native, servicii, browser, build, download, rețea sau provider. Niciun credential/env privat/profil/old root/raw canonical4 secret-bearing/protected HTML nu a fost citit. Nicio scriere în Git/produs/teste/documente; singurul fișier creat este acest raport.

Pasul următor aparține părintelui: adjudecare R1+R2 și affected SOURCE QA pe bytes înghețate, cu controalele și limitele existente. Lipsa viitoarei QA nu este finding circular. Canonical nou și integrarea/închiderea T1 necesită propriile decizii/porți; T1 rămâne **PARTIAL / NOT_ACCEPTED**, fără canonical/live PASS.
