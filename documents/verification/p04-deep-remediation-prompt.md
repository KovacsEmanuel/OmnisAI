# Prompt de execuție — remedierea auditului aprofundat SL02

**Rol:** handoff executabil derivat din audit și plan, nu plan concurent. **Stare la pregătire: NOT_EXECUTED.** Scrierea/verificarea acestui prompt nu repară produsul și nu schimbă CHANGES_REQUESTED. Ultimul HEAD inspectat la pregătire: `13ad7f427a3f708eef3b07e5aac81a07d9d22cfb`; codul auditat este cel din `b8217cb`. Citește HEAD real, nu reveni la aceste revizii.

---

Lucrează în `/home/kali/OmnisAI` și răspunde în română. Execută remedierea constatărilor din `documents/verification/p04-pre-sl03-deep-review.md`, apoi review independent și probe reale pentru reacceptarea SL02 și pregătirea SL03. **Nu te opri la un plan, un reproducer care confirmă bugul sau un test verde al harnessului.** Livrează modificări mici, regresii permanente, review adjudecat, artefact instalat și dovezi pe codul final. Dacă o precondiție sau o decizie necesară lipsește, raportează precis BLOCKED, fără să fabrici PASS.

## 1. Baseline, autoritate și limite

1. Execută `git status --short --branch`, `git rev-parse HEAD`, `git diff`, `git diff --cached`, `git ls-files --others --exclude-standard`, `git worktree list --porcelain`. Inventariază separat munca preexistentă; nu o include în commiturile tale. `documents/Omnis_Notite_Originale.html` este untracked/protejat; nu modifica/stage-ui. AGENTS este protejat, fără bypass.
2. Citește AGENTS, README, CONTRIBUTING; auditul aprofundat și `documents/verification/implementation-status.md`; plan §4.2/§5/§19.2 și arhitectură §4.1–4.5; `cli/README.md`, Makefile și sursele/testele relevante înainte de editare. Registrele SC01/SC02 și installed-start sunt dovezi istorice cu limite, nu PASS transferabil codului nou.
3. Încarcă skill-urile locale `omnis-delivery`, `omnis-release-ops` + `references/startup-failure-boundaries.md`, `omnis-review-qa`, `omnis-project-status` (ORIENT la intrare, CLOSE la predare), **`omnis-reticle` și `omnis-chisel` la fiecare review**. Dacă loaderul nu le descoperă, citește `.hermes/skills/<nume>/SKILL.md`; nu crea duplicate globale. Completează cu `test-driven-development`, `systematic-debugging`, `local-service-lifecycle`. Încarcă `omnis-api-data` numai dacă o probă justifică atingerea frontierei DB, nu pentru a reface fixture-ul.
4. Înaintea fiecărei schimbări coerente consemnează: cerință, comportament observabil pozitiv/negativ, fișiere, efecte externe, test și rollback. Ordine obligatorie: **RED → remediu minimal → GREEN/regresii → review independent adecvat → commit local separat → readback Git**.
5. Perimetru inițial: `cli/src/omnis_cli/start.py`, `start_runtime.py`, `health.py`, `release.py`, testele CLI aferente și observatorul instalat existent pentru probele strict necesare. `main.py`/`lifecycle.py` numai dacă alegerea demonstrată a frontierei de ownership o cere. Extinderea cere motiv/reproducer, nu refactor oportunist.
6. Păstrează `omnis.serve`, migrațiile 0001–0004, runnerul DB comun, topologia UDS fără porturi Docker publicate și corecția backpressure. **Nu promova ownerul exec WIP, nu introduce alt supervisor/harness generic și nu implementa SL03/SL04 pe ascuns.** Fără reset/stash/clean/amend/rebase/push, autostart, conturi/LLM/provider/ținte, configurare globală Hermes/daemon/firewall/toolchain sau upgrade latest.

## 2. Registrul obligatoriu de lucru — nimic omis

Transformă rândurile în checklist urmărit și în cerință→cod→probă→review→commit. IDs se păstrează exact. O dispoziție pentru G00/SL04 sau o recuperare BLOCKED **nu este CLOSED/PASS**; apare separat în verdict.

| ID | Livrabil / dispoziție cerută |
|---|---|
| RT-F01 | Remediu ownership forwarder de la spawn până la handoff, cu regresii reale |
| RT-F02 | Remediu auto-reap/SIGCHLD moștenit și ECHILD, fără semnale numerice după pierderea ownershipului |
| AR01 | Tipuri exacte pentru proiecția readiness, control pozitiv și negative pe același canal |
| AR02 | Tip integer exact pentru versiunea pointerului instalării; validare strictă păstrată |
| RT-PG01 | Oracle de cleanup capabil să detecteze forwarder/listener viu fără identitate publicată în jurnal |
| AR03 | Negative pe validatorii reali ai produsului, nu doar pe `_owned_container` al harnessului |
| RT-M01 | Invariante de ownership/ACK/handoff explicite și testate în remedii, fără rescriere generală |
| M03 | Matrice de suport/preflight și atestare a produsului; acoperire efectivă și limite explicite |
| M09 | Probă instalată first-start DB-readiness failure, fără efecte ulterioare și cu date păstrate |
| M18 | Expirări instalate reprezentative și buget total măsurat, separat de configurabilitate |
| M20 | Cleanup parțial/faulturi relevante, zero verdict curat fals, zero DB teardown sub incertitudine |
| M21 | Refuz neREADY păstrat; crash/recovery operațional rămâne la SL04, cu owner/test de închidere |
| M22 | Închiderea lacunei de alocare config.toml/budgets prin contract/owner/gate explicit în planul existent |
| RECOVERY_PENDING | Readback și dispoziție sigură pentru vechea DB; fără cleanup automat sub incertitudine |

Matricea baseline are 26 cerințe: **13 COVERED, 4 GAP, 5 PARTIAL, 4 DEFERRED_BY_SCOPE**. Auditul analizează și cele șase PARTIAL originare, dintre care M20 este acum GAP. Re-numără matricea după rezultate; nu ținti mecanic un total și nu promova rânduri fără probe. D01–D04 și toate SL/E rămân în plan.

## 3. RT-F01 + RT-PG01 — repară ownershipul, nu doar verdictul

Fapt confirmat: SIGTERM la `process.stdout.close()` din `launch_forwarder` anulează returnul tuplei. Callerul păstrează `process=None,pidfd=-1`; cleanupul poate publica `FAILED_CLEANED, cleanup=[]` în timp ce forwarderul/listenerul propriu rămân vii. În reproducer, stop/remove DB sunt substituite, nu DB reală oprită.

1. Scrie regresia permanentă care **afirmă comportamentul sigur**, apoi ruleaz-o pe codul vechi. Refolosește fixture-urile existente și forwarderul real. Nu lua exit 1 hardcodat al scriptului de audit drept regresie care va deveni automat GREEN.
2. Acoperă distinct: spawn → închiderea logului; obținerea/păstrarea pidfd; handshake/atestarea listenerului; închiderea stdout/finally; transferul către apelant; eșec imediat după handoff. Verifică lipsa pidfd și erorile de close fără pierderea procesului. Dacă folosești mascare de semnale, justifică modelul de threaduri, intervalul protejat și restaurarea; nu presupune că un nume de flag face transferul atomic.
3. Ownershipul trebuie să fie accesibil cleanupului pe orice ieșire post-spawn. **Nu** rezolva prin ignorarea SIGTERM, catch gol, schimbarea unui reason sau simpla mutare a ferestrei vulnerabile. Nu restaura false-safe flags dacă finalizarea nu s-a încheiat.
4. Criteriu: fie procesul/listenerul propriu sunt opriți și reap/readback confirmate, fie **UNCERTAIN/exit 4 și diagnostic/locator păstrat**. Niciodată CLEANED cu listener viu. Sub ownership/writers nereconciliate, zero stop/remove DB.
5. **RT-PG01:** observatorul de test deține independent handle/pidfd și identitatea listenerului înainte de injectarea faultului, nu se bazează exclusiv pe jurnalul produsului care poate să nu primească identitatea. Control pozitiv fără fault; control negativ cu proces viu dar jurnal fără handle. Helperul trebuie să respingă acel negativ din motivul potrivit, nu din import/prerechizit lipsă.
6. În proba instalată extinsă exercită frontiera de după spawn/FORWARDING, nu doar SIGTERM în VERIFYING. Folosește observatorul existent extins minimal; nu `run_probe` în locul `omnis start --no-open`. Citește absența procesului/listenerului/IPC/containere/rețea **înainte de rescue**. Rescue-ul propriu este plasă de siguranță și nu schimbă verdictul eșuat al produsului în PASS.
7. Păstrează controlul instalat VERIFYING și ordinea corectată în `b8217cb`; o fază ratată trebuie să eșueze onest, nu să fie acceptată drept cleanup verificat.

## 4. RT-F02 — precondiția ownershipului trebuie impusă

Fapt confirmat: un interpreter nou moștenește `SIGCHLD=SIG_IGN`; kernelul auto-reap-uiește copilul înainte de `waitid(WNOWAIT)`. ECHILD apare când `reaping=False`, iar exceptul încearcă killpg pe identitate eliberată. În audit tentativele au fost interceptate, fără victimă/PID reuse provocat.

1. Regresie RED cu copil real, control SIGCHLD default și caz **exec-inherited SIG_IGN**, nu doar flag injectat ori mock de wait. Interceptează tentativele periculoase și confirmă ECHILD; nu semnaliza efectiv PGID-uri eliberate.
2. Alege și documentează refuzul unei dispoziții incompatibile înainte de spawn/efecte sau normalizarea explicită la frontiera CLI standalone. Nu modifica tacit politica de semnale a unui caller de bibliotecă; delimitează și testează frontiera aleasă. Examinează și existența unui handler/reaper incompatibil, nu doar valoarea None a returncode.
3. ECHILD/pierderea ownershipului revocă autoritatea numerică indiferent dacă ai intrat deja în `process.wait`. Soluția trebuie să acopere **timeoutul și output floodul**, nu numai eroarea din waitid. Un check de existență urmat de killpg nu este dovadă atomică de identitate.
4. Criteriu: zero tentative numerice post-reap în probe, verdict sanitizat/refuz sau incertitudine adecvată, fără DB effects sub incertitudine. Păstrează succesul normal, ordinary read refusal, `success=False`, signal exit, nonzero mutant/lost ACK, decoding și semnale repetate în fereastra kernel reap→returncode.
5. Permanentizează controalele sticky flags și cleanup continuat după non-DB removal: un succes ulterior nu șterge uncertain și nu promovează familia nedrenată. Nu confunda reapul liderului cu drenarea tuturor descendenților sau terminarea efectului daemon.

## 5. AR01 și AR02 — două remedii mici, separate

### AR01: readiness strict tipizat

- RED pe parserul real și peer UDS/HTTP propriu: booluri valide acceptate; fiecare variantă numerică `1`, `1.0`, `0` refuzată în câmpul relevant. Include boolean opus, string, null, missing și extra; control pozitiv pe **același canal**.
- Verifică setul exact de câmpuri, tipurile exacte și valorile contractuale, inclusiv reason/dashboard_reason. Egalitatea dict Python nu este schemă, iar `isinstance(x, int)` admite bool.
- Nu schimba API-ul care deja produce booluri corecte și nu relaxa identitatea peer/origin/assets. Păstrează răspunsul sanitizat, readiness false și lipsa promovării READY pentru payload invalid.
- Rulează regresia pe modulul nou instalat din cwd extern. Numește separarea IPC substituit/peer real; nu afirma false-ready live al API-ului existent dacă nu l-ai demonstrat.

### AR02: pointer de instalare

- RED pe fișiere private reale: `format=1` integer admis, `true`/`1.0` refuzate; controale false/2/string/null/missing/extra și duplicate keys.
- Remediu în ownerul existent al pointerului; păstrează canonical path/owner/mode/no-follow/linkcount, byte cap, release/checksum și manifest strict.
- Probează consumatorii CLI relevanți pentru refuz sanitizat înainte de efecte. Fără traceback sau reflectarea payloadului. Wheel nou/cwd extern obligatoriu.
- Nu redeschide SC02 ca și cum remediul nestingului nu ar exista: rulează și regresia lui pozitivă ca protecție împotriva regresiei.

## 6. AR03 și obligațiile M03/M09/M18/M20 — probe ale produsului

Închide gap-urile de dovadă identificate prin teste permanente și probe reprezentative, nu prin redenumirea lor COVERED. Înaintea fiecărei probe instalate scrie frontiera/faultul/oracle-ul și efectele permise. Dacă execuția este blocată, rândul rămâne BLOCKED/PARTIAL cu motiv; nu pretinde că «tot auditul este PASS».

- **AR03/M03:** tabel de negative care apelează `ControlRuntime.attest` și `validate_config` reale. Control valid, apoi mutații separate pentru extra/missing bind, read-only rootfs, caps/no-new-privileges, UID, ports/network, image/command/attempt/project și env critic. Substituie numai canalul inspect/config unde este necesar, nu validatorul. Păstrează observatorul independent al harnessului. Preflightul suportat verifică platformă/UID, Compose absent/v1, socket/daemon și imagine/receipt greșite, fără efecte la refuz. Selectează și probe instalate reprezentative, fără a modifica daemonul/firewallul sau containerele operatorului.
- **M09:** prima pornire din wheel/release actuale, pe proiect nou propriu: DB reală nu devine healthy sau iese înainte de readiness. Demonstrează că nu apar migrator/API/supervisor/OPEN/pair, flags false, termen finit, date/diagnostic păstrate. FAILED_CLEANED cere absență exactă înainte rescue; dacă readbackul este incert, exit 4 și DB păstrată. Un release corupt refuzat mai devreme nu reproduce DB-readiness failure.
- **M18:** expirări reprezentative înainte de efect și după creația resurselor, plus HTTP/control trickle unde este relevant. Măsoară wall clock până la JSON final, cu allowance de cleanup explicit separat. Păstrează byte caps/no redirects/proxy, deadline înainte de spawn și EOF înainte de exit. Nu doar un timeout al verifierului exterior. Nu cere test la fiecare syscall; justifică selecția frontierelor.
- **M20:** faulturi inventory/readback/removal/journal și control cu resursă vie nereconciliată. Încearcă toate cleanupurile independente sigure, păstrează DB sub incertitudine și diagnosticul dacă jurnalul eșuează. Readback al tuturor resurselor proprii; un `any(...)` care scurtcircuitează nu certifică fiecare handle. Nu down -v/prune/reset și nu adopta proiect străin.

Orice nou seam de fault injection este numai test/dev, cu justificare și review; nu introduce opțiuni ascunse de produs care permit bypassul preflightului sau al ownershipului. Refolosește runnerul DB/observatorul existent; nu crea o a doua infrastructură de lifecycle. Nu extinde scope-ul la un audit general DB/owner după fiecare remediu.

## 7. M21, M22, RT-M01 și recuperarea — dispoziții explicite

- **M21:** păstrează și testează refuzul neREADY, intentul/starea stale și nereînceperea automată. Crash/restart/recovery operațional, bariera concurentă și probele LAN/IPv6 ale SL04 **nu sunt implementate aici și nu primesc PASS**. Leagă obligațiile de SL04/B01f/L08-core; viitorul pair/open va refuza starea neREADY.
- **M22:** închide lacuna de ownership și acceptare în **planul canonic existent**, nu într-un backlog concurent. Propune explicit unde în B01f, înainte G00, intră `XDG_CONFIG_HOME/omnis/config.toml` și bugetele configurabile; definește consumatorul, precedența, intervalele finite, refuzul câmpurilor necunoscute/secrete și consistența origin/Host/receipt. Dacă baseline-ul nu decide comportamentul, cere decizia operatorului, nu inventa o aprobare. O alocare documentată închide numai lacuna de planificare, **nu implementarea parserului**; M22 rămâne PARTIAL până la propria probă. Nu crea acum directoarele runtime/catalog/evidence/vault/backup fără consumatori.
- **RT-M01:** remediile trebuie să facă explicit când identitatea este deținută, când autoritatea de semnalizare este pierdută, când handofful este complet și când rezultatul daemonului rămâne incert. Funcția lungă nu justifică rescriere generală; acceptarea este dată de invariante/teste și reviewul soluției minimale.
- **RECOVERY_PENDING:** readback inițial, fără mutații, al locatorului `/home/kali/.hermes/cache/scratch/s2i-841796q5/probe-receipt.json`. DB cunoscută: CID `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0`, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, attempt `f8e93e10-1c04-4c2d-a43b-f6ad3167fd51`; nu presupune că încă există sau că identitatea neschimbată înseamnă familie drenată. Nu o folosi ca fixture și nu o opri numai pentru a curăța un tabel. O recuperare separată cere ownership/daemon/mount/IPC/writer readback, plan de păstrare a datelor și autorizația necesară; dacă reconcilierea lipsește, păstrează resursa și raportează BLOCKED/RECOVERY_PENDING. Git revert și un PASS pe o probă nouă nu rezolvă vechea incertitudine. Nu declara ALL_CLEAN cât aceasta rămâne deschisă.

## 8. Review independent după remedii, nu opinii inventate ale uneltelor

Pentru fiecare defect: reviewer read-only legat de commit sau snapshot/diff/hash exact, criterii și fișiere, **nu verdict dorit**. Cere findings severity/file:line/scenariu/criteriu/remediu minimal și lista comenzilor executate separat de recomandări. Niciun copil nu scrie/comite în checkoutul comun. Maximum trei workstreamuri simultane; worktrees de implementare numai explicit din HEAD local, cu medii/importuri proprii.

Reviewul final are direcții distincte:

1. **Lifecycle:** RT-F01, RT-F02, RT-PG01, RT-M01 și interacțiunile lor; birth-to-handoff, auto-reap, semnale repetate, DB gate, cleanup și diagnostice.
2. **Validare/atestare:** verdict individual AR01 și AR02, AR03/M03 pe validatorii produsului și păstrarea strictă a contractelor.
3. **Completitudine/acceptare:** toate cele 26 de rânduri, M09/M18/M20, dispozițiile M21/M22 și resursele vechi/noi. Confruntă cu planul până la stadiul actual; nu aproba doar ultimul diff sau ultimele două teste.

Un reviewer poate acoperi mai multe direcții dacă verdictele sunt distincte și bugetul realist. Părintele reproduce constatări relevante și adjudecă; re-reviewul se limitează la corecții/interacțiuni/noi reproduceri, fără buclă de audit infinită. După două încercări nereușite ale aceleiași reparații, oprește editările speculative, restrânge mecanismul și revede contractul; nu fabrica GREEN.

La **fiecare review**, încarcă Reticle/Chisel și include rânduri cu scope/artefact/comandă/result/limită:

- **Reticle:** rulează numai proba instrumentată admisă și relevantă; aplicația actuală nu are instrumentare Reticle certificată. CLI/procese = NOT_APPLICABLE; aplicație neinstrumentată = NOT_INTEGRATED; smoke sintetic separat = TOOLING_ONLY. Nu îl prezenta drept reviewer de Python sau dovadă a cleanupului Docker. Dacă rulezi smoke, păstrează controale state + HTTP200/500 și readback listener cleanup, fresh HOME și rețea izolată. Fără instrumentation production, cloud/model/telemetry implicită.
- **Chisel:** pinul auditat este NO-GO pe repo/home/profil. Nu are voie să primească acces pentru a satisface formal această cerință. Binar/runner absent = NOT_RUN/BLOCKED, nu rezultat inventat. Reevaluarea necesită acord/scop distinct, artefact exact, licență/control review și fixture OS-izolat, fără fallback nesandboxat sau MCP global. Folosește uneltele native cât gate-ul nu este trecut.
- Reticle/Chisel nu emit o «perspectivă independentă» prin simpla lor existență. Reviewerii independenți și execuțiile reale sunt canale distincte.

## 9. Toolchain, wheel curent și gate-uri secvențiale

Inspectează Makefile/lockurile actuale. Pinuri documentate: Python3.13.15, uv0.12.19, Node24.21.0/npm11.19.0, PostgreSQL18.6. Verifică executabilele/importurile; dacă mediile au expirat, recreează izolat din lockuri, nu latest/global. Căi istorice de verificat, nu presupus valide:

```text
/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv
/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin
```

Ordinea verificărilor:

1. RED și GREEN pe fiecare defect/frontieră, apoi controalele apropiate și testele oracle-urilor. Testul trebuie să eșueze pe implementarea veche din cauza defectului, nu a unui import/path/tool lipsă; folosește copie/worktree izolată sau substituție bounded pentru baseline, fără resetarea checkoutului comun.
2. `make test-cli`, Ruff/format/mypy în configurația existentă. Nu chema direct `test-cli-live` cu un DSN ambiental pentru a ocoli runnerul privat.
3. `make check-cli-wheel UV=<uv verificat>` construiește și instalează wheelul nou; rulează din cwd extern și confirmă identitatea modulelor cu sursa remediată. Execută regresiile noi pe modulele instalate și console scriptul unde este frontiera contractuală. Fără vechiul wheel folosit ca dovadă a noului cod.
4. După ultimele editări și review/commituri, cu PATH pin-uit și produsul stabil, rulează **secvențial**:

```sh
make check UV=<calea absolută verificată>
make check-installed-start UV=<aceeași cale>
```

5. Rulează noile probe instalate reprezentative din §6 prin comenzile reale integrate ale testelor; înregistrează-le distinct dacă nu fac parte din gate-ul existent. Nu presupune că o țintă veche selectează automat noile teste și nu numi o suită parțială `make check`. Dacă extinzi un target, păstrează toate aserțiunile vechi și propagarea exit code-ului; fără skip/alias fals-verde.
6. Runnerul comun creează DB UDS/no-network nouă. OCI pregătește explicit release/imagine din artefactele curente și invocă **comanda instalată**, nu un substitut. La pozitiv păstrează HTTP/assets/control, reuse/concurență, status read-only, supraviețuirea launcherului, bootstrap inert și datele.
7. Gates care împart venvuri/artefacte nu rulează în paralel; nici reviewerul nu folosește un wheel pe care alt proces îl reconstruiește. Joburi lungi urmărite cu notificare; citește exact process ID/exit/log/receipt. Timeoutul uneltei sau heartbeat-ul întârziat nu este verdictul jobului; nu relansa doar pentru un nudge de bookkeeping.
8. Pentru probe externe: root/proiect/nonce înainte de creație, resurse strict proprii, deadline/rescue independent, readback exact CID/rețea/tag/IPC/proces/listener și date păstrate. Numerele de PID/port și textul jurnalului nu sunt singure autoritate. Listele trebuie numărate/deduplicate programatic; separă locatoarele mock din unit teste de cele ale invocării OCI reale.
9. Actualizează registre/README/plan/readiness/hartă **după rezultate reale**, cu SHA/scope/comandă/exit/review/limite. Păstrează RED-urile. Documente normative schimbate: renderer + `--check`, teste documentation și Chromium/inspecție vizuală a readerelor relevante. Nu transfera PASS documentar asupra produsului.

## 10. Commituri, verdict final și predare

Commit local după fiecare schimbare coerentă: defectul și regresia aferentă împreună; remedii independente, oracle-uri independente, decizii de contract și documentare în commituri separate. Stage numai căile/hunk-urile intenționate. Mesajul include cauză, RED/GREEN, review efectiv, comenzi/exit, limite și rollback. Verifică `git show --stat --oneline HEAD` și status după commit. Fără push; fără schimbări intenționate necomise la predare.

Nu folosi o singură etichetă «totul PASS». Raportează distinct:

- **REMEDIATION_PASS / FAIL / BLOCKED:** RT-F01, RT-F02, AR01, AR02, RT-PG01, AR03 și RT-M01 au fiecare probe și verdict adecvat. Niciun P1/P2 confirmat în scope nu rămâne ascuns; lipsa probei unui oracle nu devine aprobare.
- **READY_FOR_SL03: YES/NO, motivat:** numai după remedii/regresii/review și gate-uri actuale verificate, fără constatări blocante nerezolvate. Toate obligațiile rămase au owner/felie/gate/test explicit și nu sunt redenumite CLOSED. M21/SL04 și implementarea încă nelivrată M22 nu capătă PASS doar din alocare.
- **G00:** rămâne deschis până la toate livrabilele/probele lui, inclusiv SL03/SL04. Nu începe aceste felii în această execuție și nu declara CI remote ori assessment_ready.
- **Resurse:** cleanupul ultimelor probe și RECOVERY_PENDING al încercării vechi au verdicte separate. Un YES pentru dezvoltarea SL03 nu înseamnă ALL_CLEAN sau autorizarea unei recuperări nesigure.

Încheie cu raport scurt în română: ce s-a remediat efectiv, probe reale și limite, verdicte distincte de review, commituri/Git, resurse/date/recuperări și următorul pas. **Ultimul element din răspuns este matricea globală Omnis direct în chat**, conform `omnis-project-status`: fundații, **AICI SL02**, SL03→SL04, G00/CI, rest MVP, post-MVP și recuperarea separată. Linkurile către documente nu înlocuiesc matricea. Dacă ai doar un reproducer al defectului, cod necomis, review restant sau gate nereușit, predarea rămâne FAIL/BLOCKED, nu «gata pentru etapa următoare».
