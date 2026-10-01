# P0.4 / SL02 — audit aprofundat înainte de continuare

## Contract și snapshot inițial

Cererea operatorului: verificare mai profundă a implementării, gap-urilor și calității codului înainte de continuare, cu evaluarea explicită Reticle/Chisel în fiecare review. **Stare la deschiderea contractului: audit în curs, fără verdict nou. Rezultatul adjudecat este mai jos.** Bază `b7cc556752bce03d0591655b176f590d85ee41b4`, branch `p04-control-topology-wip`, produs `b8217cb`. Tracked/index curate; numai `documents/Omnis_Notite_Originale.html` untracked/protejat. Nu se schimbă AGENTS.

Autoritate: plan §4.2/§5/§19.2, arhitectură §4.1–4.5, [registrul SC01/SC02](p04-start-remediation.md) și [harta](implementation-status.md). **Nu confundăm:** SL02 are acceptare delimitată; G00 cere inclusiv livrabilele SL03/SL04 și nu este o precondiție circulară pentru a începe SL03. Auditul poate găsi un blocker nou; acesta cere reproducer și adjudecare, nu simpla redenumire a unui PARTIAL ca bug sau a unui PASS vechi ca PASS nou.

### Direcții și criterii de închidere a auditului

1. Review independent adversarial pe lifecycle/ownership/procese/semnale/reap/incertitudine/cleanup, cu probe safe pe copii locali proprii. Separăm efectele daemon substituite de real Docker; nicio oprire a DB incerte sau a resurselor operatorului.
2. Review independent al celor șase PARTIAL M03/M09/M18/M20/M21/M22 și al calității codului/contractelor. Pentru fiecare: defect confirmat, probă absentă, scope ulterior sau datorie de mentenanță; owner/gate și test de închidere, dacă blochează SL03 ori numai G00.
3. Părintele verifică actualitatea dovezilor și reproduce constatările importante; inspectează uneltele și readbackul operațional. Nicio afirmație universală «nu există buguri». Repetarea unor smoke-uri nu dovedește exhaustivitatea produsului.
4. Livrare: concluzii adjudecate, matrice de pași prioritizați legată de planul existent, comenzi/exit/limite reale, skill de review actualizat cu cerința operatorului și commituri locale separate. Fără push sau implementare SL03/SL04.

### Perimetru și efecte

Produsul rămâne read-only în această analiză. Probe/scripts numai în `/home/kali/.hermes/cache/scratch/omnis-deep-readiness/`, cu deadline și cleanup propriu. Fișierele versionate permise: acest registru, procedura locală `omnis-review-qa` și numai proiecțiile de status afectate de constatări confirmate. Nu refactor general, gate slăbit, DB/owner harness nou, instalări globale, conturi/LLM/provider/ținte sau modificate profile personale. Orice remediere de produs rezultată va avea contract și RED→GREEN separat, nu va fi confundată cu această cercetare.

Reticle este instrument de observație UI, nu reviewer de cod; Chisel este adaptor de fișiere, nu agent care emite o opinie. Reviewurile trebuie să numească pentru ambele `EXECUTED`/`NOT_APPLICABLE`/`BLOCKED` și motivul. Reticle poate rula numai fixture-ul inert admis până la instrumentare dev-only a aplicației. Chisel rămâne NO-GO pe repo; reevaluarea ar cere artefact pin-uit și fixture OS-izolat fără home/secrete. Nu se fabrică perspective sau verdict din disponibilitatea unui tool.

Readback inițial read-only: DB incertă `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0` este running, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, attempt `f8e93e10-1c04-4c2d-a43b-f6ad3167fd51`, conform locatorului anterior. Nu este adoptată ca DB de test și nu se recuperează prin semnalizarea PID-urilor numerice. Recuperarea necesită o probă/decizie proprie, nu un PASS nou pe alt proiect.

Rollback documentar: revert al fiecărui commit coerent după verificarea dependențelor. Auditul nu inversează și nu modifică datele/serviciile externe; resursele/probele proprii trebuie citite înapoi separat.


## Verdict adjudecat: CHANGES_REQUESTED înainte de continuarea SL03

**Patru defecte confirmate și încă neremediate: două P1 de lifecycle și două P2 de validare.** Părintele a inspectat reproducerile și le-a executat separat; nu preia doar rezumatele subagenților. Începerea unei noi felii de produs se pune în așteptare pentru corectarea P1-urilor în SL02. Motivul nu este circularul «SL03 trebuie deja livrat» și nici simpla existență a șase PARTIAL: sunt contraexemple noi asupra produsului curent.

Review independent `deleg_02eee67a`: task 1 lifecycle (RT-*), task 2 acceptare/date/calitate (AR-*). Snapshot `b7cc556`; produs `b8217cb`; sursele/testele/ops nu s-au schimbat în audit. SC01/SC02 și faza VERIFYING rămân remediate **în scenariile lor probate**, iar make check/OCI PASS din registrul anterior sunt reale, dar nu acoperă aceste frontiere noi. Niciun remediu de produs nu este livrat de acest document.

### RT-F01 / P1 — ownership pierdut la finalizarea lansării forwarderului

- **Loc la snapshot:** `cli/src/omnis_cli/start.py:244–251`, caller `:612,666–686`; vecinătatea spawn/log close `:196–215` trebuie inclusă în remediu, dar nu o prezentăm ca a doua reproducere executată.
- **Cauză:** `launch_forwarder` returnează tuple din try, dar stdout close din finally poate ridica înainte de livrarea tuplei. Excepția nu mai devine `ForwarderStartError(process,pidfd)`. Callerul rămâne cu `process=None,pidfd=-1`.
- **Reproducere părinte:** `cli/.venv/bin/python -I -B <scratch>/omnis-deep-readiness/probe_runtime.py` → exit **1**, măsurare a defectului. Startup/launch/cleanup/jurnal și codul forwarderului sunt reale; numai pregătirea API/DB și inventarul/efectele Docker sunt substituite. La close, wrapperul închide pipe-ul real și trimite SIGTERM real launcherului. Childul propriu are alarm(12) ca plasă a probei, nu modificare de produs.
- **Observat:** CLI exit 3 / FAILED; jurnal **FAILED_CLEANED, cleanup=[]**, deși forwarderul propriu și listenerul său verificat prin inode/proc sunt **vii**. Cleanup primește handle-uri absente. Fake-ul înregistrează stop și remove DB; nu s-a oprit DB reală.
- **Control:** fără semnal la close, un eșec ulterior primește handle-urile și cleanupul elimină procesul/listenerul. Rescue-ul probei folosește pidfd capturat independent, reap și readback listener absent; fixture-ul este eliminat. Nu se fabrică CLEANED prin rescue: starea fals curată este măsurată înaintea lui.
- **Închidere necesară:** ownership disponibil callerului sau boundary-ului de cleanup pe întreg intervalul spawn→log/pipe close→handoff. Regresii safe la fiecare frontieră critică, inclusiv semnal real, cu zero CLEANED sub listener viu și DB păstrată dacă ownerul nu e reconciliat. Remediu local, nu supervisor nou.

### RT-F02 / P1 condițional — auto-reap înainte de WNOWAIT

- **Loc:** `cli/src/omnis_cli/start_runtime.py:145–164`.
- **Cauză:** `SIGCHLD=SIG_IGN` se poate moșteni prin exec. Kernelul auto-reap-uiește copilul; `waitid(WNOWAIT)` ridică ECHILD când `reaping=False`. Exceptul încearcă apoi SIGTERM și SIGKILL pe PGID numeric eliberat.
- **Reproducere părinte:** `cli/.venv/bin/python -I -B <scratch>/omnis-deep-readiness/probe_sigchld.py` și aceeași probă exec-lansată după `signal.signal(SIGCHLD,SIG_IGN)` → **exit 1 fiecare**, defect măsurat. Copil real cu lifespan 50ms; argv Docker substituit. În fiecare tentativă, observatorul confirmă ECHILD. **Toate tentativele killpg sunt interceptate; zero semnale numerice după reap executate.** Nu s-a indus PID reuse/victimă străină.
- **Control:** SIGCHLD default → copil exit 0, zero tentative killpg, flags normale. Cazul ignored păstrează uncertainty/family conservative pentru DB, dar acestea nu scuză tentativa de semnalizare numerică.
- **Închidere necesară:** impune înainte de spawn o politică compatibilă de ownership SIGCHLD (refuz sau normalizare explicită pentru CLI standalone) și tratează ECHILD ca pierdere a autorității numerice. Nu este suficient un catch în calea normală dacă timeoutul poate încă semnaliza după auto-reap. Regresii default/ignored-inherited-through-exec, semnale suspecte interceptate, fără owner framework nou.

### AR01 / P2 — egalitatea Python nu validează booleenele readiness

- **Loc:** `cli/src/omnis_cli/health.py:135–143`; producător API `api/src/omnis/api.py:115–120`.
- **Părinte, sursă și wheel existent:** peer UDS real, control IPC substituit numai pentru izolare. Baseline valid → ACCEPTED; individual `api_ready:1`, `dashboard_ready:1.0`, `assessment_ready:0` → **ACCEPTED**; `dashboard_ready:false` → `DASHBOARD_NOT_READY`. Comenzile E13/E14 rerulate au exit 0 al măsurării, **nu PASS al validării stricte**.
- **Limită:** API-ul actual emite booluri corecte; nu avem demonstrație de false-ready în producție sau peer străin adoptat. Este un defect al consumatorului, relevant înainte de acceptarea `open` din SL03.
- **Închidere:** tipuri exacte și set exact de câmpuri; valid/boolean opus/int/float/string/null/missing/extra pe același canal. Fără schimbarea producătorului pentru a ascunde validatorul permisiv.

### AR02 / P2 — installed pointer acceptă bool/float drept versiune

- **Loc:** `cli/src/omnis_cli/release.py:212–221`.
- **Părinte, fișiere private reale, sursă/wheel:** `format:1`, `true`, `1.0` acceptate; `false` și `2` refuzate cu ReleaseError. E11/E12 → exit 0 al măsurării; schema dorită rămâne **FAIL**.
- **Limită:** nu este checksum bypass sau release străin executat; celelalte verificări se păstrează. Manifestul SC02 este altă frontieră și nu este redeschis doar pentru acest pointer.
- **Închidere:** versiune exact `int` + câmpuri exacte, controale bool/float/string/null/missing/extra și control int1 permis; refuz sanitizat la consumatori. Commit separat de readiness.

### Gap-uri de probă și calitate, nu alte defecte demonstrate

| ID | Constatare și efect asupra dovezii | Acțiune delimitată |
|---|---|---|
| RT-PG01 / P2 dovadă | `cli/integration/installed_start.py:46–52` verifică Docker/IPC, nu forwarder/listener. Părintele a rerulat helperul real pe cazul RT-F01: acceptă absența de resurse cu forwarder încă viu și fără identity transferată în jurnal. Oracle OCI curent semnalizează înainte de forwarder și rămâne valid numai acolo. | În regresia RT-F01, readback independent al procesului/listenerului, nu numai datele pe care handofful ar fi trebuit să le publice. Nu pretindem că gate-ul OCI istoric a dat false PASS în propriul scenariu. |
| AR03 / P2 dovadă | `test_control_topology.py:266–313` mută mounts/caps/rootfs dar apelează `_owned_container` al harnessului, nu `ControlRuntime.attest`. Inspecție părinte confirmată. | Negative tabelare pe validatorii reali `ControlRuntime.attest` și `validate_config`, plus cazuri instalate reprezentative înainte G00. Păstrează observatorul independent; nu transfera verdictul lui asupra altui cod. |
| RT-M01 / P3 mentenanță | Două launchere învecinate tratează diferit ownership/finally, iar `reaping` ascunde precondiția fără auto-reap. Defectele de mai sus demonstrează consecința, nu numai stil nepreferat. | Invariante explicite, helper mic numai dacă remediul îl cere, regresii permanente pentru tranziții; fără refactor general sau owner WIP promovat. |

Măsurare AST auxiliară: 12 module CLI și 89 funcții incluzând locale; `start_instance` ocupă 253 linii, cu 31 noduri structurale if/for/while/try/ifexp. Acestea **nu sunt complexitate ciclomatică, nici verdict «cod prost»**. Arată unde costul de review este mare; problemele concrete sunt ownershipul și validarea, nu numărul de linii. Pygount nu este instalat; nu s-a făcut instalare globală pentru aceste măsurători stdlib.

## Ce rămâne din cele șase PARTIAL și când trebuie închis

Etichetele inițiale nu sunt singurele criterii. M20 este promovat acum din PARTIAL la GAP din cauza RT-F01; restul obligațiilor sale de probă rămân. Niciun G00 lipsă nu este transformat în prerequisite circular pentru scrierea SL03.

| ID / owner | Înainte de continuarea SL03 | Înainte de G00 / probă de închidere |
|---|---|---|
| M03 — B01f CLI/release | Gap-ul de matrice singur nu blochează; defects confirmate se repară separat | Matrice de suport și negative pe validatorul produsului: platformă/UID/Compose/socket/daemon/image, mounts/security/network/command; control valid + zero efecte la refuz. Nu toate distribuțiile imaginabile. |
| M09 — B01f startup/DB readiness | Nu este bug demonstrat prin absența testului | First-start DB reală nu devine healthy/iese; fără migrare/API/supervisor/OPEN, deadline, flags false, cleanup real înainte rescue și date păstrate; control pozitiv. |
| M18 — B01f lifecycle | Bugetele finite există; RT-F02 se repară acum ca defect, nu prin redesign | Expirări instalate reprezentative înainte efect, după creație și în HTTP, măsurate până la verdict incluzând allowance cleanup; zero READY sub timeout. Configurabilitatea este M22 separat. |
| M20 — B01f SL02 cleanup / SL04 recovery | **RT-F01 blochează continuarea**; oracle RT-PG01 se corectează odată cu proba remediului | Faulturi inventory/removal/journal, cleanupul independent sigur continuă; zero DB teardown sub incertitudine și zero CLEANED cu resurse vii. DB veche se recuperează separat, nu se adoptă ca fixture. |
| M21 — B01f SL04; consumatori pair/open SL03 | SL03 trebuie să refuze neREADY/admission închis; nu cere recovery deja implementat | SL04: crash în ferestrele creație/ACK OPEN/publicare READY, retry/recovery fără duplicate/redeschidere neautorizată, persistență și readback; L08-core și limite rețea. |
| M22 — B01f CLI, alocare explicită lipsă | Port/receipt existente permit SL03; nu blocker safety demonstrat | Alocă în planul existent config.toml XDG și bugete configurabile înainte G00, sau aprobă explicit o deferire normativă. Precedență/range/unknown-secret-field refusal și same-origin au nevoie de contract/test, nu doar eticheta PARTIAL. |

Layoutul runtime/catalog/evidence/vault/exports/backups este legitim la primul consumator (SL07/SL08/SL15/SL17/SL24/SL36), nu directoare goale obligatorii în P0. Propunerea pentru M22 nu modifică tacit planul; ownerul și acceptarea trebuie adjudecate înainte implementării. Nu este justificată amânarea unui P1 de cleanup curent în SL04.

## Ordinea minimă de remediere propusă, nu cod deja reparat

1. **RT-F01 în SL02:** RED pe handoff/close și readback independent al listenerului → remediu minimal cu ownership păstrat → GREEN și review. Include vecinătatea log close/spawn, nu doar un try mutat care lasă aceeași fereastră în alt loc.
2. **RT-F02 separat:** RED inherited SIGCHLD/auto-reap → politică explicită înainte de efecte și no numeric signal după ECHILD → controls default/timeout/reap; review separat.
3. **AR01 și AR02, fiecare commit:** tipuri stricte în validatorul actual și regresii pozitive/negative. AR01 obligatoriu înainte de acceptarea `open`; rezolvarea ambelor acum evită propagarea inconsistențelor.
4. **Reacceptare SL02:** regresii sursă, wheel nou/cwd extern, review pe bytes finali; secvențial make check și installed-start actual, cu proba forwarderului extinsă fără slăbirea oracle-ului. Fără DB veche folosită la test și fără rescue sub incertitudine pentru PASS.
5. După remedierea blockerelor curente, **SL03** poate începe. Probe M03/M09/M18/M20 și alocarea M22 au owner explicit în B01f/G00; SL04 închide recovery/stop și restul G00. B02/P1-data abia după G00.

Acest audit **nu a executat pașii de remediere** și nu a rulat din nou make check/OCI: aceștia ar repeta gate-uri ale căror scenarii nu detectează încă noile contraexemple. Comenzile noi au verificat frontierele relevante; nu se declară «suite green» din reușita reproducerului. Un script care măsoară bugul și iese intenționat cu 1 nu este regresia permanentă a comportamentului sigur; înainte de fix trebuie o aserțiune care trece numai când defectul nu mai există.

## Dovezi actuale, controale și unelte

Root scratch: `/home/kali/.hermes/cache/scratch/omnis-deep-readiness/`. Părintele a verificat codul celor patru scripturi de proces înainte de execuție; comenzi reale, nu output fabricat:

| Comandă / canal | Rezultat părinte | Limită |
|---|---|---|
| `cli/.venv/bin/python -I -B <root>/probe_runtime.py` | exit 1, RT-F01 și RT-PG01 confirmate; 12 combinații sticky flags trecute | Cod forwarder/proces/semnal/jurnal reale, pregătire Docker/DB substituită; rescue independent după măsurarea bugului |
| `.../probe_sigchld.py`, apoi exec cu SIGCHLD ignorat și `--inherited` | exit 1 fiecare, RT-F02 confirmat; zero semnale suspecte executate | Kernel auto-reap real; killpg recorder, fără victimă indusă |
| `.../probe_runtime_extra.py` | exit 0; nonzero/-9 real în remove API, continuă cleanup supervisor, zero DB effects | Fake daemon, producător și consumator reale; metadata decoder control |
| `.../probe_process_controls.py` | exit 0; timeout/EOF/decode/post-reap controls, proprii copii reaped | Nu detached-family/daemon-delay exhaustiv |
| E11/E12 din acceptance-matrix, rerulate de părinte source/wheel | int1/booltrue/float1 acceptate; false/2 refuzate | AR02 măsurat, nu validare strictă PASS |
| E13/E14, source/wheel | valid și 3 variante numerice acceptate, false-ready refuzat | UDS real, IPC substituit; AR01, nu OCI false-ready dovedit |
| `check_metadata_refusal.py`, interpreter wheel extern | exit 0, patru refuzuri JSON corecte, fără state change/traceback | Ipoteza array-nesting metadata respinsă: instance 4095/4096 bytes și journal 16383/16384; nu universal fuzz certification |
| Reticle `run_probe.py --browser /home/kali/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell` | exit 0, `verified=yes`, state count1, HTTP200/500 controls, listener-ele 14400/14401 închise | **TOOLING_ONLY**. Root `omnis-reticle-2j_ztw21`, Playwright1.60.0/headless148.0.7778.96. Nu instrumentarea aplicației |
| Chisel pin v0.1.7 / binary-reported0.1.6 | **BLOCKED / reevaluare NOT_RUN** | Auditul versionat, re-numărat: 53 checks, 7 SECURITY_FAIL în 4 clase; nu rezultat nou de execuție. Locația vechiului runner nu există, executabilul nu este în PATH; căutarea largă scratch a eșuat și nu este dovadă de absență globală. Fără activare sau fallback nesandboxat |

Metadatele Python3.13.15: parserul real a acceptat depth8191, a ridicat RecursionError la10000/15000. Asta explică de ce ipoteza că toate cititoarele fără catch RecursionError sunt defecte a fost respinsă pentru payloadurile probate. Nu adăugăm catch-uri generale fără reproducer.

**Reticle/Chisel la fiecare review:** ambele skilluri încărcate de părinte și revieweri; RT/AR includ explicit aplicabilitatea. Reticle este NOT_APPLICABLE proprietăților CLI/procese și NOT_INTEGRATED UI-ului de produs; smoke-ul separat este real, dar nu o opinie despre cod. Chisel rămâne NO-GO. Cerința operatorului este versionată în `omnis-review-qa` prin `631ddc6`; lecțiile concrete sunt în referința release-ops prin `c8ffcc7`. Nu pretindem că simpla procedură este enforcement automat.

Artefacte: `parent-runtime-adjudication.json`, `parent-validation-adjudication.json`, logurile `parent-*`, rapoartele `review-runtime.md`/`acceptance-review.md` și matricile JSON. Scratch poate expira: scenariile, aserțiunile relevante și limitele sunt păstrate aici. Verificarea ad-hoc suplimentară a scriptului metadata a trecut și verifierul `hermes-verify-*` a fost șters; este bookkeeping al probei, nu acceptare de produs.

## Matricea actuală a celor 26 de cerințe

Numărare programatică după adjudecare: **13 COVERED, 4 GAP, 5 PARTIAL, 4 DEFERRED_BY_SCOPE**. Tranziții: M02/AR02, M13/AR01, M19/RT-F02 și M20/RT-F01. Criteriile COVERED păstrează numai dovezile și limitele anterioare; «wheel nou/OCI final» din rândurile păstrate se referă la execuția versionată pe `b8217cb`, nu la un gate rerulat în acest audit. Nu s-a promovat vreun PARTIAL în COVERED.

| ID | Clasificare actuală | Dovadă / limită |
|---|---|---|
| M01 | COVERED | Wheel nou/cwd extern/omnis.serve și OCI final |
| M02 | GAP | AR02: pointer format bool/float acceptat; manifestul SC02 reparat rămâne distinct. |
| M03 | PARTIAL | Atestări/preflight; nu toate incompatibilitățile probate OCI |
| M04 | COVERED | No implicit pull/build/install; argv/env/cwd fixe, capcane instalate |
| M05 | COVERED | XDG/căi/UID/mode private; nu toate FS/distribuțiile |
| M06 | COVERED | Lock/nonce/intent, concurență reală; cross-state componentă |
| M07 | COVERED | Reuse fără restart/migrare/OPEN nou; nu restart operațional |
| M08 | COVERED | Port listener/bound-only/bind race; nu toate cursele OCI |
| M09 | PARTIAL | PG18 pozitiv; lipsă proba installed DB-readiness failure first-start completă |
| M10 | COVERED | Migrare/cluster/lock/empty-only, 17 teste; nu catalog exhaustiv |
| M11 | COVERED | API + supervisor inert, fără owner WIP/runtime promoted |
| M12 | COVERED | Detached și citire după launcher exit; nu reboot/autostart |
| M13 | GAP | AR01: readiness numeric acceptat ca boolean; API-ul actual emite booluri corecte. |
| M14 | COVERED | Deadline total/byte caps/no redirect/proxy; nu peer OCI ostil peste tot |
| M15 | COVERED | Status read-only și fără lease refresh; nu zero atime/syscall |
| M16 | COVERED | READY atomic verificat, flags false; nu fault la fiecare fsync |
| M17 | COVERED | Bootstrap inert/canale sintetice fără secrete; nu tracing exhaustiv |
| M18 | PARTIAL | Timeout/flood/EOF/reap componente; nu toate etapele instalate |
| M19 | GAP | RT-F02: auto-reap SIGCHLD ignorat permite tentative numerice după ECHILD; nu invalidează controalele default. |
| M20 | GAP | RT-F01: forwarder viu + FAILED_CLEANED; RT-PG01 cere readback independent de jurnal. Datele vechi rămân păstrate. |
| M21 | PARTIAL | SIGTERM VERIFYING real + sticky intent; nu crash în fiecare etapă |
| M22 | PARTIAL | Port CLI/bundle, nu config.toml XDG/toate bugetele țintă |
| D01 | DEFERRED_BY_SCOPE | SL03 pair TTY/open/browser implicit |
| D02 | DEFERRED_BY_SCOPE | SL04 stop/recovery operațional și G00 complet |
| D03 | DEFERRED_BY_SCOPE | Hermes runtime/assessment/target effects ulterioare |
| D04 | DEFERRED_BY_SCOPE | Vault/catalog/backup/update/restore/doctor și CI remote ulterioare |

**Resurse:** copiii/listener-ele sintetice proprii au fost reaped/eliminate/read-back înaintea verdictului probelor. DB veche UNCERTAIN a fost numai inspectată read-only, nu oprită/adoptată; rămâne RECOVERY_PENDING separat. Nu s-a creat DB/container/proiect Docker nou în audit. Fără conturi/LLM/ținte, global tooling/profile/daemon/firewall edits sau push.

## Verificarea publicării auditului

`python scripts/render_docs.py`, apoi `--check`: PASS. `python -m unittest discover -s tests/documentation -v`: **62 teste PASS, exit 0**. Chromium offline `browser_check.py --include-documents`: **116 checks PASS**, zero erori JS/cereri externe, raport `audit-docs-browser.json`. Plan §19.2 și statusul readiness au fost inspectate vizual la 1440×1000 în `audit-plan.png`/`audit-readiness.png`: text/linkuri lizibile fără suprapuneri în paragrafele inspectate; nu aprobare estetică/runtime. Matricea actuală are programatic 26 IDs unice și total 13/4/5/4; planul/harta păstrează 36 SL și 4 E. Diff-ul produsului/testelor/ops/Make/AGENTS față de snapshotul auditat este gol. Aceste verificări certifică publicarea și contabilizarea constatărilor, **nu remedierea celor patru defecte**.
