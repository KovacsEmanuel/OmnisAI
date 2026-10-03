# P0 — mandat de închidere integrală pentru sesiunea fresh

## Scop și autoritate

Cererea operatorului este închiderea **întregii faze P0**, nu încă o felie de cod, o reanaliză generală sau un nou handoff care lasă aceleași restanțe. Acest document consolidează starea și ordinea de lucru; nu schimbă [arhitectura](../Omnis_MVP_Architecture.md), [planul](../Omnis_Implementation_Plan.md), criteriile [U01–U26/C01–C17](p00-closure-matrix.md) ori limitele aprobărilor.

Ținta finală: niciun criteriu obligatoriu P0 rămas PARTIAL/FAIL/BLOCKED/NOT_RUN, niciun blocker de review rămas în scope, cod/teste/documente comise, dovezi reale pentru artefactul final și verdict CI real. **BLOCKED este o escaladare intermediară, nu finalizarea fazei.** Dacă o decizie sau dovadă externă este indispensabilă și indisponibilă, descrie exact condiția și cere decizia necesară; nu inventa succesul și nu extinde singur autorizația.

## 1. Punctul de plecare verificat

- Repo: `/home/kali/OmnisAI`, branch `p04-control-topology-wip`.
- Baseline verificat înaintea acestui handoff: **`89b702968628e8b6f09d9a11c928fdeeab84dde0`**. Acest handoff este o modificare documentară ulterioară; citește HEAD-ul real, nu face reset la baseline.
- Ultimul cod de harness integrat: **`41335c4028e240bb7222bd8d477f93e0391346c5`**. Ultimele editări de predare au fost numai documentare.
- Tracked/index curate la predare; `documents/Omnis_Notite_Originale.html` este intenționat neversionat și protejat.
- Fence fără TTL, owner Stop-only, arm/reconcile/schema0006, Start DB-only/reconcile, M03 și M22 sunt integrate. Nu le rescrie și nu reface cherry-pick-uri deja integrate.
- Integrarea produsului `bd5ee23`, M03, Mounts și remedierile componentelor au acceptări **scoped**. K-S-ARGV este integrat în `79acc76`; S-IMAGE-RETENTION în `41335c4`, ambele cu review independent și RED/GREEN. Nu sunt certificarea P0/G00.
- `make check-release-install` pe `41335c4`: **exit0, 272 teste wheel și 57 release non-OCI**; build web/static trecute,21 module instalate identice sursei. Wheel SHA256 `f06254f9135378daf79b14887cf1f0b1cd472b9136a1c878d9a3c0b241dfcd55`.
- `make check` pe **`e336b7b`** a trecut, cu API358/migrări20/E2E7/CLI272 sursă+wheel și cleanup propriu. Nominalul instalat Stop/repetat→Start DB-only/reconcile/sentinel→Stop și emergency au trecut separat pe acel snapshot.
- Secvența ulterioară **F→S** pe `e336b7b` s-a oprit cu **S exit2/FAIL**. P/O nu au fost rulate în acea secvență. Remediile oracolelor ulterioare nu promovează retroactiv eșecul și nu substituie noul F→S→P→O.

## 2. Citire minimă, în ordinea potrivită

1. `AGENTS.md`, `CONTRIBUTING.md`, Git real și [harta curentă](implementation-status.md).
2. Acest handoff; apoi ultimele secțiuni ale [registrului SL04](p04-stop-recovery.md), în special recovery S, aprobările și verificarea non-OCI finală.
3. [Matricea U01–U26/C01–C17](p00-closure-matrix.md): **definițiile criteriilor rămân active; statusurile ei inițiale sunt istorice**, nu descriu codul actual. [Handofful anterior](p00-completion-handoff.md) păstrează obligațiile, nu verdictul curent.
4. Numai secțiunile relevante: arhitectură §4.1–4.5; plan §4.2/§5/§19; registrele [M22](p00-m22-config.md), [SL02](p04-installed-start.md), [SL03](p04-pair-open.md) și migrare/fence la nevoie.
5. Încarcă skill-urile proiectului `omnis-project-status`, `omnis-delivery`, `omnis-review-qa`, `omnis-release-ops`, plus `omnis-lifecycle-receipt-review`, `local-service-lifecycle`, `systematic-debugging` și TDD. Dacă skill-urile proiectului nu apar în catalog, citește-le din `.hermes/skills/`, fără schimbarea profilului global.

Nu reciti toată istoria MVP ca prerechizit și nu reporni auditul general. Nu redeschide o constatare închisă fără diferență relevantă sau un nou scenariu reproductibil. Git și registrele versionate sunt autoritatea probelor; scratch-ul poate expira și o cale lipsă nu autorizează recrearea unei dovezi istorice.

## 3. Prerechizitul care trebuie rezolvat primul

### Fixture-ul S blocat

Ținta: `/home/kali/.hermes/cache/scratch/fs-jzo1p7d7/s2i-d3nrt1c_`.

- Proiect: `omnis-local-afd8f4c8ceb14dd3ac2d55bb616c6f69`.
- Attempt: `1f38dfcd-b1e5-4efc-8174-901857989b3a`.
- DB CID: `6d92114df57bc93abf3b8a3491847fe95b866311397cde233235dd3450775e7d`.
- Rețea observată: `10eda168a083b5f10c90a1e0844c64c71c4bed07d8507186b9c62b0641fa31e2`.
- Ultimul readback: DB running; startup/probe UNCERTAIN/FAIL. Snapshotul DB este pre-OPEN, generation0/admission=false, owner NULL, commands goale/fences0. Acest readback nu certifică familia originală ori toate cererile vechi.
- Control-image/tag lipsesc după vechiul finalizer; manifestul și image.json sunt păstrate. Nu reconstrui imaginea și nu modifica receiptul doar ca un constructor să treacă.
- Reviewul `deleg_fe81260f` a refuzat retirement-ul: lipsește dovada atribuită familiei launcherului/forwarderului originale și confinării cererilor. PID/pathname/listener absent, sursa fără fork, flagurile reconstruite și dovada modulelor actuale **nu** refac singure această dovadă.
- Scriptul `preopen-retirement.py` are modul `--retire` **dezactivat explicit**; SHA256 al variantei blocate: `4a82484859443e4009fb349cf04bafffaef372311a5b7e1692d03e0889aded66`. Nu executa varianta arhivată a35a04d2 și nu elimina gardul pentru a obține PASS.

**Sarcina de deschidere:** rezolvă acest prerechizit printr-o dispoziție operațională verificabilă, nu prin încă o comparație identică a PID-urilor. Fă o singură investigație bounded asupra dovezilor noi/existente relevante; nu petrece peste15 minute repetând auditul deja consemnat. Dacă dovada istorică nu există, nu o fabrica: definește o procedură externă sigură care ar putea stabili o autoritate/contenire nouă, cu scope, resurse afectate, protecția datelor, verificări pozitive/negative și limite explicite. Supune procedura reviewului independent și cere aprobarea operatorului pentru orice operație nouă în afara acordului existent. Nu presupune că o permisiune generică ține loc de dovadă.

Dacă soluția propusă implică un mediu/daemon nou complet separat sau separarea unei datorii operaționale de certificarea produsului, demonstrează izolarea, citează criteriul canonic aplicabil și cere decizia necesară înainte de a modifica politica de reluare. Nu transforma această opțiune într-o scurtătură pentru a ignora cleanupul obligatoriu ori a marca vechiul FAIL drept PASS. Până la o dispoziție acceptată și verificată, politica de la predare rămâne: **fără gate-uri fizice noi în acest mediu**.

### Resurse care nu se confundă cu S

- `os-setkniau/s4-5m_x9ywv`: runtime retras extern cu6 ACK-uri noi204 și readback separat; date/imagine/fence și receipturile originale păstrate. Vechiul api.rm rămâne UNKNOWN, fără STOPPED/reuse. **Nu rerula** scriptul one-shot `confined-retirement-preflight.py --retire` și nu reporni DB-ul pentru a verifica o operație deja consumată.
- `ps-7ipgwosk/s4-yp1zqk46`: retragere separată după refuz pre-ADMIT demonstrat; original FAIL și fence păstrate. Nu reexecuta procedura consumată.
- `s2i-841796q5`, `s2db-3od0cvym` și proiectele P01 fără proveniență din matrice rămân protejate/neoperate. Niciun cleanup după prefix sau ALL_CLEAN global.

## 4. Tot ce trebuie închis din P0

Construiește **o singură listă de închidere derivată din matricea existentă**, nu alt plan. Pentru fiecare U/C/S/M/L obligatoriu: criteriu, cod/consumator real, dovadă existentă reutilizabilă și snapshotul ei, probă exactă lipsă, pozitiv/negativ, locator/cleanup, review și verdict. Verifică programatic că toate U01–U26 și C01–C17 sunt contabilizate. Un rând fără dovadă rămâne deschis; nu dispare din tabel.

| Grup | Obligația de închidere, nu doar de documentare |
|---|---|
| SL04 S01–S03 / U03–U07 | Start/admission-first și Stop-first instalate, concurență reală/lock-wait, expiry/takeover, identități și generații, replay exact, ACK pierdut/malformat/trickle, fence fără TTL care împiedică acquire/OPEN. |
| SL04 S04–S05 / U08–U16 | Owner/FD-uri originale/handshake, ACK/readback/drain și persistență, Stop repetat/concurent, Start explicit DB-only/reconcile înainte de acquire/OPEN, date/sentinel păstrate; API, supervisor și DB indisponibile separat; persistare locală dublu imposibilă; receipturi/identități/PGDATA străine și refuz înainte de efect. |
| SL04 S06 / U17 / C01–C17 | Toate frontierele definite, înainte și după commit/request/ACK/fsync/publicare. Moartea launcherului și ownerului separat, no-op și control ținut viu, pierderea completion și reconcile ACK, no-replay/no-autoresume, resurse străine neatinse. Cut-ul trebuie observat pe canalul fizic cerut, nu doar modelat cu un peer sintetic. |
| S07 / M03 / U18–U20 | Config pozitiv real și negative complete; atestare runtime pentru DB/API/supervisor/migrator/reconcile; UID, mounts/env/entrypoint/confinement, network/porturi, peer alt UID, LAN/IPv6 sigur, observabilitate pentru absența provider/target/refresh IO. Lipsa unui peer sigur este o condiție de rezolvat, nu PASS din inspect static. |
| M22 / U21–U23 | Config valid/invalid la toți consumatorii instalați, precedență și origin fără rebind, Host/Origin, TTY; startup/shutdown/cleanup configurate sub stall pe căile **actuale**. `test_config_deadlines.py` numește normal o ramură care apelează legacy `_resume_owned`: completează proba pentru ownerul integrat, nu îi transfera creditul. |
| Regresii P0 / U01–U02/U24–U25 | Instalare externă checkoutului, reuse/concurență/port străin, release/schema/migrare reală/date, dashboard/assets/status, pairing one-use/expiry, sesiuni/Host/Origin/CSRF, pair/open/default și refuzurile lor în stările Stop/recovery. Nu confunda opener acceptat cu fereastră GUI. |
| U26 / G00 / CI | Artefactul final, matrice completă, review consolidat, secvență canonică reală, cleanup propriu verificat, toate schimbările comise și verdict CI pentru revizia corectă. |

Implementează strict lipsurile demonstrate și instrumentarea minimă necesară probelor; refolosește `cli/integration`, testele API și runnerul DB. Nu livra doar specificația unei probe, un stub, un nou framework de ownership sau un raport despre cum ar putea fi testată.

## 5. Execuție fără o nouă buclă de harness

- Maximum3 workstreamuri simultane implicit; un singur autor pe fișiere comune, worktrees din HEAD local. Numai părintele operează Docker/PG, **serial**, pe fixture-uri autorizate, cu readback exact înainte de următorul gate.
- Înaintea unui fault: owner/descendenți pinuiți și proveniență capturate independent, phase/ACK/fsync observabile, plan de cleanup/recovery verificat, artefacte păstrate. Nu crea încă o încercare imposibil de adjudecat pentru că observerul nu și-a capturat autoritatea.
- RED specific → fix minim → verificările afectate → commit mic → review independent pe exact acei bytes. Parent reproduce blockerul; un finding nou reproductibil nu este ignorat pentru termenul de închidere.
- După două iterații consecutive care repară doar instrumentarea fără a avansa criteriul de produs: oprește acea rută, identifică ipoteza greșită și decide o alternativă verificabilă. Nu adăuga încă un supervisor/tracer/verifier generic.
- Nu schimba arhitectura IPC, fence-ul fără TTL sau threat model-ul pentru a face un test verde. Orice amendament indispensabil trebuie justificat și aprobat explicit, nu introdus ca refactor.
- Nu relansa suite/probe/retirement pentru notificări întârziate ori remindere automate. Citează execuția pe bytes neschimbați; verifică readbackul exact. Un verifier al raportului nu este dovadă de produs. `NO TESTS RAN`, excepția de fixture și falsul succes nu contează drept control negativ valid.
- Nu fragmenta finalizarea în noi prompturi generale. Fiecare etapă produce o cerință închisă sau o decizie precisă necesară; raportează progresul material, nu fiecare comandă și nu doar numărul de teste.

## 6. Reviewul final și secvența de acceptare

Îngheață candidata după ultimele schimbări relevante de produs/oracle. Acoperă toate perspectivele deja cerute în matrice, eventual grupate în3 revieweri read-only:

1. Completitudine arhitectură/plan/U/C/S/M/L și validitatea oracolelor/dovezilor G00.
2. PostgreSQL/API: tranzacții, identități, concurență, fence, shutdown/finalize/reconcile.
3. CLI/owner/procese/daemon/ACK/fsync, M03/M22, artefact instalat, consumatori și izolare.

Nu porni un nou audit nelimitat după fiecare remediu. Re-review focalizat pentru defectele reparate; aprobarea finală cere însă ca toate perspectivele și obligațiile să fie contabilizate pe candidata finală. Părintele adjudecă; copiii nu închid trackerele.

După verificările țintite/wheel/docs și numai când mediul este admis, execută serial pe aceeași candidată:

```text
make check
make check-installed-start
make check-installed-pair-open
make check-installed-stop
```

Folosește argumentul `UV=<uv-pinuit>` și mediile cerute de Makefile. Leagă separat fiecare probă lipsă din matrice de o execuție reală: cele patru targeturi nu acoperă automat toate C01–C17. Dacă apar editări relevante, invalidează/rerulează ce este afectat și asigură secvența finală pe bytes finali; nu repetă totul pentru Markdown fără impact, demonstrat prin diff.

Pinuri cunoscute: Python3.13.15, uv0.12.19, Node24.21.0, npm11.19.0, PG18.6. Verifică prezența și versiunile în procesul real de gate. Căile folosite anterior pot expira:

- uv: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`;
- Node: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin`;
- docs Python: `/home/kali/.hermes/cache/scratch/p0tools-k39nr13l/docs/bin/python`;
- managed Python: `/home/kali/.local/share/uv/python`.

HOME, toate XDG și TMPDIR private/noi/scurte; fără aliasuri sau surse ambientale. DB reală numai prin runnerul atestat `ops/run_test_db_gate.py`, nu o adresă aleasă manual. Nu instala global pentru a repara un mediu lipsă. Păstrează SHA/comenzi/exits/importuri/hashuri/receipts și limite; fără secrete în rapoarte.

CI remote este parte explicită a închiderii, nu un checkbox local. **Nu există acord nou pentru push în acest handoff.** Identifică devreme aprobarea lipsă și cere o singură decizie concretă pentru branch/revizie/workflow; după acord, execută și verifică remote SHA și verdictul real. Un workflow pe commit vechi sau doar unit green nu validează candidata.

## 7. Limite care rămân obligatorii

- Fără P1, runtime Hermes de produs, provideri, proxy, assessment ori trafic către ținte; o închidere P0 nu pornește implicit P1.
- Fără push implicit, reset/clean/rebase/squash/force-push ori cherry-pick repetat; stage numai fișierele intenționate. Commit granular și mesaje cu motiv/verificare/limite/revert.
- HTML-ul original neversionat rămâne neatins. Nicio ștergere de date, `down -v`, prune, cleanup după prefix sau semnalizare după PID/port neasumat.
- Nu atinge recuperările istorice protejate ori alt profil Hermes. Fără restart/schimbare globală daemon/firewall/UID fără un nou plan de impact și acord explicit.
- Nu rescrie FAIL/UNCERTAIN, nu elimina fence-ul prin TTL, nu deduce ACK sau STOPPED din absență și nu transforma raportul unui subagent în dovadă executată.

## 8. Ieșirea cerută

**Raport de închidere P0, nu încă un handoff exploratoriu:** matrice completă cu toate obligațiile închise, comenzi/exit/SHA/artifact/cleanup, reviewurile adjudecate, verdict CI și Git verificat. Declară `P0/G00 CLOSED` numai dacă toate condițiile obligatorii sunt îndeplinite.

Dacă este indispensabilă o intervenție sau decizie externă, cere exact acea decizie și păstrează sarcina deschisă; nu prezenta BLOCKED drept livrarea cerută. Dacă operatorul refuză ori dovada/procedura sigură rămâne indisponibilă, raportează factual BLOCKED și condiția de ridicare, fără certificare fictivă. Solicitarea „să fie ultima sesiune” nu autorizează micșorarea criteriilor sau operații nesigure.
