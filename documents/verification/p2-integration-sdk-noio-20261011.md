# SDK-only — 11 octombrie 2026: descărcare/install PASS, serializer BLOCKED

## Mandat și rezultat

Owner `20261011_085807_f90ba6`, ramura `p04-control-topology-wip`, sursa `0018d448ada0d0697e09477b6713f8e25407957a`. Operatorul a autorizat explicit descărcările fixate, instalarea SDK offline într-un venv nou și proba serializerului fără IO extern, apoi promptul de continuare pentru analiza coordonatorului. Nu implementare de produs în această sesiune. Cererea P03 istorică SHA256 `717b225e753c3d4b700b455ef8b6ad7126e57413d797b276a188c8ffce91a38b` este numai INPUT; nonce/deadline/grants vechi nu au fost reutilizate. P03 nu este faza3.

[Receipt complet](p2-integration-sdk-noio-20261011.json): **DOWNLOAD + OFFLINE_INSTALL PASS; SDK BLOCKED_NOT_RUN_PRELAUNCH**. Nu există HTTP body/model/messages efectiv capturate de SDK, equality măsurată sau caracterizare dinamică extra_body. Aceste valori sunt null/NOT_RUN, nu output inventat. G-DATA-EARLY/G-MODEL/G02/faza2 rămân NOT_CLOSED.

## Bytes și instalare reale

Root nou, înregistrat înainte de creare: `/home/kali/.hermes/cache/scratch/p2-sdk-20261011-f90ba6-702b22fd`, uid1000/mode0700, intent/marker exclusiv înaintea efectelor. Controlul și logurile durabile ale etapei sunt sub `/home/kali/.hermes/run/omnis-p2-sol-20261011`; mission/coordonatorul paused nu au fost modificate.

16 GET-uri originale, numai URL-urile fixate files.pythonhosted.org, TLS verificat, proxy dezactivat, redirect refuzat, dimensiune bounded și SHA verificat înainte de scriere/utilizare. **16/16, 4.742.943 bytes**; manifestul păstrează fiecare URL/filename/size/SHA din lock, nu hashes ale cache-ului extras. Closure exactă din `integrations/hermes/runtime-override/uv.lock`, SHA256 `a7b8c05fc3657b305ce9a21421fc891ac1fb3c88ce266d0a187ee338ee3f5b20`:

- openai2.24.0; anyio4.14.2; annotated-types0.7.0; certifi2026.5.20; distro1.9.0; h11 0.16.0; httpcore1.0.9; httpx0.28.1;
- idna3.18; jiter0.13.0; pydantic2.13.4; pydantic-core2.46.4; sniffio1.3.1; tqdm4.67.3; typing-extensions4.15.0; typing-inspection0.4.2.

Python3.13.15, uv0.12.19 fixate/hash-checked. Venv nou, HOME/TMPDIR/XDG/UV cache private, fără credentials/config operator în mediul SDK. Instalare din wheelhouse cu `uv pip sync --offline --no-index --find-links <root>/wheels --only-binary :all: --require-hashes --link-mode copy <root>/inputs/requirements-sdk.txt`, numai closure existentă; fără latest/update/override nou/sdist/keyring/global/Hermes upgrade. Logul uv spune Resolved16/Prepared16/Installed16; nu revendic absența oricărei rezolvări interne a uv. Metadata reader `venv/bin/python -I -B`, fără import openai, a confirmat exact cele16 distribuții și sursele SDK copy/single-link cu cele trei hashes din cererea fixată, exit0/joined.

## Execuții finite și corecții QA

Comanda exterioară pentru fiecare pas: `<python3.13.15> -I -B /home/kali/.hermes/run/omnis-p2-sol-20261011/run-sdk-step.py <step>`. Argv complete/intenții sunt în receipt. Se reutilizează numai `ops/run_test_db_gate.py:run_gate`, nu DB main/prove_private_fixture. Bugetul propriu900s, deadline original al acestei execuții păstrat; per-comandă bounded, serial.

| Pas | Outer exit | Receipt familie | Rezultat |
|---|---:|---|---|
| acquire inițial | 1 | code1/drained=true | Locatorul din înregistrarea mea era stringul unui obiect lock din cauza shadowingului variabilei; FileNotFoundError înainte de opener/GET. Zero wheeluri. Înregistrare/intent/marker originale păstrate, corecție append-only. |
| acquire-after-request-locator-fix | 0 | code0/drained=true |16/16 wheeluri originale verificate; fără redownload/retry HTTP. |
| new-private-python-venv | 0 | code0/drained=true | Mediu nou creat. |
| hash-checked-copy-install-no-source-build | 2 | code2/drained=true | Comanda istorică pregătită `uv pip sync -r` este invalidă; refuz înainte de instalare, metadata=[]. |
| hash-checked-copy-install-positional-input | 0 | code0/drained=true | Numai `-r` eliminat, SRC_FILE pozițional; pins/opțiuni/private env neschimbate;16 instalate. |
| real-sdk-serializer-noio | 1 | MISSING/UNCERTAIN, nu falsificat | Runnerul nu produce log/receipt. Serializerul/sandboxul nu au proba de execuție. |

Probe-source istoric SHA256 `974557755dd843f55fc7616515beb390a36db4432bdab2fb7b50a992abf8f96f` păstrat. O singură linie de observație a fost extinsă pentru full HTTP UTF8/body/extensions/kwargs, deoarece originalul păstra numai hash/dimensiune/nume de câmpuri. RED/GREEN pe funcția capture extrasă AST folosesc stub sintetic explicit: **QA_DRIVER_SOURCE_ONLY, nu SDK**. Probe revizuit SHA256 `6fa0560bdb59e368df7adce674762e8659f8a0e466c2f5ff9f8f588976862502`; bypass standalone neschimbat SHA256 `6887046105bd5e666631aa9a0d0a81488392ba8978ede650ae4e31abc36ccbd6`.

Reviewuri independente read-only, primul `20261011_090510_59368e`, re-review focalizat `20261011_090751_e19c20`: **APPROVED_SCOPED_QA_DRIVER_ONLY** pe hashes exacte. Model gpt-6.1-sol-900k/provider openai-codex/xhigh/service_tier=priority/YOLO au fost citite din obiectul reviewerului și verificate înaintea primei cereri, fără modificare globală. Nu s-a presupus moștenirea Fast în delegate_task. Un launcher de review inițial a ieșit1 înaintea agentului deoarece `python -m runpy` tratează argumentul drept modul; outputul este păstrat, iar lansarea corectă a folosit runpy.run_path în procesul finit de dezvoltare. Reviewul nu este QA de produs și contactul modelului de dezvoltare nu este inferență Omnis.

## Blocker concret și limită de oprire

`ops/run_test_db_gate.py:1018–1067` folosește argparse.REMAINDER pentru gate-command; separatorul standalone `--` din argv bwrap este interpretat de parser, care refuză restul cu „unrecognized arguments: -- <venv-python> -I -B <probe> <root>”. Reproducerea pe **numai parserul extras din sursa existentă**, fără lansarea helperului/SDK, a ieșit2 cu exact acel diagnostic. `run_gate:759–817` suprimă stderrul workerului și apoi ridică GateCleanupUncertain când receiptul lipsește. Nu există gate exit/drain original verificabil pentru acest pas; censusul ulterior nu îl înlocuiește.

După două cicluri care au corectat QA/instalarea fără răspunsul SDK, **STOP/BLOCKED, fără al treilea fix sau replay în această sesiune**. Mecanismul minim propus pentru sesiunea separată: testează SOURCE-only framingul argv; trece exact argv bwrap printr-un singur exec-only wrapper ca argument `-c` al interpreterului fixat în runnerul existent, astfel încât separatorul să nu mai fie token al parserului exterior. Nu schimba runnerul de produs, sandboxul, seccompul, bypassul sau oracolele și nu crea alt supervisor. Acesta este un remediu propus, **nu executat sau aprobat ca rezultat SDK**. După review focalizat pe snapshot exact, proba reală rămâne prerechizită înainte de alegerea reprezentării DTO finale.

## Retenție, gates și predare

Census read-only ulterior: zero procese readable same-UID care folosesc rootul owned, observerul și părintele său excluși; cinci procese same-UID inaccesibile sunt consemnate, fără revendicare globală. Download/venv/install au receipturi drained=true proprii; SDK failed-family rămâne UNCERTAIN. Nicio ștergere/cleanup replay. Wheelhouse/venv/cache/inputuri/date sintetice/loguri/receipturi/marker păstrate. Scratchul poate fi pruned după24h idle; nu promitem retenție durabilă a wheelurilor prin simpla păstrare în cache. Manifestul, concluziile și scriptul probei revizuite sunt copiate în controlul etapei; concluziile sunt versionate aici. Pentru arhivarea bytes wheel/venv înainte de expirare coordonatorul trebuie să înregistreze destinația owned, nu să adopte cacheuri istorice.

DB/OCI/product native lifecycle/browser/canonical/inference/target/account adoption/r1/global/push/faza3 NOT_RUN; veto-ul managed rămâne byte-unchanged. Acceptările P0/P1/B05/B06a/C03 și reviewurile I1/I2 rămân la frontierele lor. Download/install PASS nu închide SDK sau G-DATA-EARLY; SDK-only eventual PASS nu va închide DTO enforcement, turn/config autentice, owner reserve→commit→SENT, Stop/lease/first-byte/caps, G02-live ori faza2.

Handoff și promptul complet sunt salvate în controlul etapei pentru analiza coordonatorului, apoi prezentarea operatorului. [Copia versionată a promptului](p2-sdk-continuation-prompt-20261011.txt) este o propunere: începe cu deblocarea exactă a lansării SDK, nu presupune rezultatul serializerului și nu este grant sau implementare. Nu a fost pornită implementarea, sesiune succesoare sau cron și nu au fost modificate autoritățile coordonatorului. Continuarea rămâne numai faza2, cu P4a-minim canonic înainte de live; acordul live cont/provider/model/date/buget nu este prerechizit artificial al implementării inerte.
