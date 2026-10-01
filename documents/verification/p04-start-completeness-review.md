# SL02 — adjudecarea auditului de completitudine

## Verdict actual și auditul istoric

**Actualizare ulterioară: SC01/SC02 CLOSED / APPROVED_SCOPED**, conform [registrului remedierii](p04-start-remediation.md): cod `b8217cb`, review separat, gate comun și OCI curente PASS; 16 COVERED / 6 PARTIAL / 4 DEFERRED. O probă intermediară a păstrat corect DB sub incertitudine și rămâne RECOVERY_PENDING separat, fără rescrierea istoricului. **Restul acestui document este auditul istoric CHANGES_REQUESTED — SC01 și SC02 erau confirmate, neremediate la snapshotul de mai jos.** Calea principală instalată există și are PASS-uri reale în [registrul livrării](p04-installed-start.md), dar afirmația „SL02 complet fără omisiuni” nu este susținută. Nu anulăm execuțiile istorice; restrângem verdictul de acceptare pe baza a două contraexemple noi. Nu sunt notificările vechi F1/R1–R7/B1–B4 deja închise.

**Bază audit independent:** `4113c785ae8cacccb44ba8db79e1805d271c21dd`. **HEAD la reproducerea părintelui:** `15fc030ab2c23dc423a423714fac1271a444f6ee`. Diff-ul `4113c78..15fc030 -- cli/src cli/tests cli/integration` este gol; cele 12 module Python ale CLI-ului instalat păstrat au fost comparate byte-for-byte cu sursa curentă: identice. Schimbările intermediare sunt numai skill/status/documentare. Nicio constatare nu este declarată închisă prin această adjudecare.

Autoritate: [plan §4.2/§19.2](../Omnis_Implementation_Plan.md), [arhitectură §4.1–4.5](../Omnis_MVP_Architecture.md) și contractul SL02. Auditul a citit surse/teste fixate prin Git și dovezile păstrate; a folosit probe AST pure, fără Docker sau servicii. Părintele a verificat separat constatările de mai jos pe modulele instalate reale. Eficacitatea întregului MVP nu este obiectul acestor probe.

## Reproducere proprie a părintelui

Comandă efectivă:

```sh
/home/kali/.hermes/cache/scratch/omnis-p04-cli-check/bin/python -I /home/kali/.hermes/cache/scratch/omnis-post-sl02-review-4113c78/reproduce_current_gaps.py
```

**Exit 1 / RED pentru comportamentul sigur așteptat.** Nu a eșuat din import/dependință lipsă. Programul a verificat egalitatea celor 12 module instalate și a exercitat codul real, nu noduri AST.

### SC01 — P1: moartea subprocessului mutant pierde incertitudinea

- **Cod:** `cli/src/omnis_cli/start_runtime.py:138–164`, consumat de `cli/src/omnis_cli/start.py:277,303–305,334–343` la snapshotul auditat.
- **Scenariu:** Docker CLI a trimis o operație mutantă, apoi copilul CLI moare prin semnal înainte de ACK. Moartea clientului nu dovedește anularea efectului daemon. Returncode-ul negativ este verificat după blocul care setează incertitudinea la excepții; ramura respectivă păstrează `uncertain=false` și `family_drained=true`.
- **Reproducere reală îngustă:** `ControlRuntime.run(effect=True)` a executat un copil Python propriu real, înlocuind numai argv-ul Docker la spawn. Copilul s-a terminat prin SIGKILL, `returncode=-9`. Rezultat observat: `LOCAL_SERVICE_COMMAND_FAILED`, `uncertain=false`, `family_drained=true`.
- **Consumator:** `cleanup_attempt`, cu flagurile rezultate mai sus și numai inventarul/atestarea/efectele Docker substituite, a emis `container stop --time 15 db-owned` și `container rm db-owned`; `problems=[]`. Acestea sunt comenzi înregistrate de un fake, **nu o DB oprită efectiv**.
- **De ce probele vechi nu sunt suficiente:** timeoutul/floodul intrau în `except`; negativele cleanup porneau deja cu flagul corect. SIGTERM al launcherului în VERIFYING nu este terminarea copilului Docker înainte de ACK.
- **Remediu minimal propus, neaplicat:** propagarea conservatoare a incertitudinii la terminarea prin semnal a comenzii cu efect și la familia nereconciliată; păstrarea DB/jurnalului UNCERTAIN. Nu semnaliza PGID numeric după reap. Testează producătorul flagurilor și apoi consumatorul; un efect daemon întârziat cere probă autorizată distinctă. Nu este motiv să promovezi/refaci ownerul exec WIP.
- **Limită:** moartea copilului și metoda de produs au fost reale; nu am produs un efect Docker întârziat și nu am certificat o familie cu descendenți. Această limită nu elimină ramura fals sigură confirmată.

### SC02 — P2: manifest profund imbricat rupe JSON/exit

- **Cod:** `cli/src/omnis_cli/release.py:48–51`; propagare prin `start_runtime.py:35–41`, `start.py:442–447,701–716`.
- **Scenariu:** manifest sintetic `b'[' * 15000 + b'0' + b']' * 15000`, **30001 bytes**, sub limita **32768**. Decoderul ridică `RecursionError` înainte de verificarea formei. Excepția nu este convertită de această frontieră la refuzul de release.
- **Reproducere:** console scriptul instalat real `omnis start --no-open --json`, din cwd extern și XDG disposable, a ieșit cu **1**, stdout gol și `RecursionError` în stderr. State/runtime nu au fost create. Niciun mock pe comandă, loader sau protocolul JSON al acestei probe.
- **Impact:** releaseul corupt nu este acceptat și nu s-a demonstrat adopție ori scurgere de secrete, dar refuzul nu respectă JSON/exit 2 contractual. Lipsa Docker nu este cauza reproducerii.
- **Remediu minimal propus, neaplicat:** conversie îngustă `RecursionError` → `ReleaseError` sanitizat la decoder sau limită explicită de adâncime; regresie de loader și console command. Fără catch general care ascunde buguri de programare.

**Cleanup/readback al reproducerii:** ambii copii au fost reaped, rootul temporar propriu a fost eliminat; `own_temp_removed=true`, `children_reaped=true`. Nu s-au invocat Docker, DB, conturi, provideri, ținte sau servicii ale operatorului. Scriptul rămâne diagnostic scratch; datele de test nu au fost păstrate ca instalație operațională.

## Matricea istorică de completitudine adjudecată

Numărare programatică din raport: **26 cerințe — 14 COVERED, 6 PARTIAL, 2 GAP, 4 DEFERRED_BY_SCOPE**. COVERED este scoped, nu toate combinațiile posibile. PARTIAL este o limită de implementare/probă, nu automat alt bug. Source/test/evidence detaliate sunt în raportul independent; tabelul de aici păstrează durabil concluzia și limita relevantă.

| ID | Cerință | Clasificare | Dovadă / limită |
|---|---|---|---|
| M01 | Wheel instalat, cwd extern, omnis.serve | COVERED | Proba instalată reală; nu harness substituit comenzii |
| M02 | Release absent/corupt/incompatibil, refuz sanitizat | GAP | SC02; refuzurile obișnuite trec, nestingul excesiv rupe protocolul |
| M03 | OS/Compose/imagine/receipt/daemon | PARTIAL | Atestări și negative existente; matricea tuturor indisponibilităților/incompatibilităților nu este OCI completă |
| M04 | Fără pull/build/install/update implicit, cwd inert | COVERED | Config/argv/env fixe și capcane în cwd; ipoteza pull a migratorului a fost respinsă, vezi mai jos |
| M05 | XDG/căi/UID/mode private | COVERED | Cazuri de componentă și fresh XDG instalat; nu toate FS/distribuțiile/UID-urile |
| M06 | Lock/identity/intenție înainte de efecte | COVERED | Concurență reală; cross-state testat separat cu provisioning substituit, nu crash de alimentare |
| M07 | Reuse fără migrate/restart/OPEN nou | COVERED | CID/timestamps/restart count/epoch/generație neschimbate; nu restart operațional |
| M08 | Port străin/bound-only/race, fără adoptare | COVERED | Installed denials și bind race real la componentă; nu toate cursele OCI |
| M09 | DB proprie și readiness bounded | PARTIAL | PG18 real pe cale pozitivă; eșecul DB-readiness la prima pornire instalată nu are proba completă cleanup |
| M10 | Migrare dedicată, identitate/conexiune/lock/empty-only | COVERED | 17 probe migrări istorice; advisory lock real, nu două joburi OCI complete concurente; catalogul empty nu este certificat exhaustiv |
| M11 | API + un supervisor inert | COVERED | Topologie reală P0, fără runtime/proxy/executori |
| M12 | Detached și supraviețuirea launcherului | COVERED | Servicii citite după ieșirea CLI; nu reboot/autostart sau toate politicile OS de sesiune |
| M13 | DB/schema/API/assets/control aceeași identitate | COVERED | Bytes/assets și control reale; negativele HTTP stricate au IPC substituit în testele componentei |
| M14 | Deadline total HTTP/control, limite, no redirects/proxy | COVERED | TCP/UDS/control trickle și byte caps; nu peer OCI ostil în fiecare fază |
| M15 | Status read-only, fără lease refresh | COVERED | Receipturi/lease observate; nu afirmație de zero fsync/atime ori toate syscallurile |
| M16 | Metadata/READY atomic, fără pairing/assessment | COVERED | Flags/receipturi probate; nu fault la fiecare fsync/rename |
| M17 | Inert, secrete absente din canalele probate | COVERED | Sentinel/env/output/journal/log verificate; nu observator exhaustiv egress/secrete |
| M18 | Deadline startup/subprocess | PARTIAL | Timeout/flood reale; nu expirare instalată în fiecare etapă și nici toate bugetele configurabile |
| M19 | Incertitudine/familie înainte de teardown DB | GAP | SC01; timeouturile și flagurile injectate nu acoperă producătorul cu returncode negativ |
| M20 | Cleanup continuat și date păstrate | PARTIAL | Probe reale pozitive și fault-uri înguste; SC01 limitează garanția generală |
| M21 | Întrerupere/crash intent/admission închis | PARTIAL | SIGTERM VERIFYING și stare stale injectată; nu crash la fiecare etapă |
| M22 | Config non-secretă/layout țintă §4.4 | PARTIAL | Port CLI + bundle; config.toml XDG și toate bugetele țintă nu sunt consumate de SL02; nu nou blocker inventat |
| D01 | Pair TTY/open/browser implicit | DEFERRED_BY_SCOPE | SL03, nu stuburi în SL02 |
| D02 | Stop/restart/recovery operațional și G00 complet | DEFERRED_BY_SCOPE | SL04; nu justifică amânarea defectului SC01 din cleanupul curent |
| D03 | Runtime Hermes, assessment și efecte target | DEFERRED_BY_SCOPE | Feliile ulterioare; assessment_ready=false corect |
| D04 | Vault/catalog/backup/update/restore/doctor/CI | DEFERRED_BY_SCOPE | Consumatori și gates ulterioare; păstrarea PGDATA nu este backup/restore |

**Cele zece pozitive:** wheel/cwd extern; pregătire explicită/XDG nou; servicii reale; identitate/readiness comună; status read-only; reuse; concurență single instance; supraviețuirea launcherului; bootstrap inert; cleanup/date păstrate — toate au suport identificat în registrul SL02 și cod. Acceptarea acestor trasee nu repară contraexemplele de mai sus și nu extinde automat negativele de componentă la OCI.

**Ipoteză respinsă, nu al treilea defect:** omisiunea flagului explicit `--pull=never` la jobul dedicat nu demonstrează pull pe calea verificată. Referința impusă este image-ID `sha256:<64 hex>`; Docker CLI v27.5.1 intră în fallbackul missing numai pentru o referință numită, nu acest digestReference. Auditorul a verificat sursa `docker/cli/v27.5.1/cli/command/container/create.go` și `vendor/github.com/distribution/reference/normalize.go`. Nu s-a executat Docker/pull și nu s-a relaxat contractul de startup. O recomandare de claritate nu este promovată la GAP.

## Inventar global și decizie de continuare

Inventarul paralel a confirmat efectiv **36/36 rânduri SL unice**, nu numai totalul declarat în metadata. Setul a fost recitit din arrayul `slices` și comparat programatic cu planul de părinte. E1–E4, B21m și cele 13 ghiduri EXECUTION_UNSCHEDULED sunt separate. Nu rezultă un procent de finalizare.

Primitivele de stop/status existente nu închid livrabilul SL04; [harta globală](implementation-status.md) îl marchează NOT_IMPLEMENTED/NOT_RUN ca rezultat de produs, cu fundațiile reutilizabile păstrate separat. Inventarul este orientare, nu aprobare de corectitudine; verdictul lui despre existența comenzii nu contrazice SC01/SC02.

**Prioritate imediată:** remedierea SC01/SC02 în SL02, fiecare cu regresie, review și verificare adecvată. **Următoarea subfelie nouă din plan rămâne SL03**, după aceste corecții; apoi SL04 și G00. Nu transferăm defectul cleanupului curent în SL04 și nu inventăm o fază nouă. G00 deschis, CI remote NOT-RUN, assessment_ready=false.

Acest increment persistă review-ul și corectează statusul: **nu modifică produsul și nu pretinde remediile aplicate**. PASS-urile `make check` și OCI de la `1dfa022` rămân istorice și scoped; nu au fost rerulate în acest audit. Fără push/deploy și fără resurse externe noi rămase active.

## Verificarea publicării adjudecării

După actualizarea statusurilor, `python scripts/render_docs.py` și `--check` au trecut; `python -m unittest discover -s tests/documentation -v` a executat **61 teste PASS**, exit 0. `python tests/documentation/browser_check.py --include-documents --output <scratch>/completeness-browser.json` a raportat **116 checks PASS**, fără erori JavaScript/cereri externe. `git diff --check` PASS. Cititoarele plan §19.2 și readiness au fost inspectate vizual la 1440×1000: statusul și linkurile sunt lizibile, fără suprapuneri/clipping în blocurile inspectate; nu este o nouă aprobare estetică sau runtime.

Sursele/testele/configurația produsului și AGENTS.md au diff gol. Niciun gate de produs nu a fost redenumit ori slăbit ca să ascundă RED-ul. Aceste verificări validează publicarea corectă a constatărilor, **nu remedierea SC01/SC02**.

## Proveniență și limite

- Raport independent complet: `/home/kali/.hermes/cache/scratch/omnis-post-sl02-review-4113c78/sl02-completeness-review.md`, delegare `deleg_d5cf1b24`, snapshot fix `4113c78`.
- Inventar independent: `status-matrix.json` și `roadmap-review.md` în același root; surse la snapshot, nu stare live a serviciilor.
- Reproducer părinte: `reproduce_current_gaps.py` în același root, interpretorul wheelului instalat, cwd de probă extern.
- F1/F2 din acel audit au aici IDs **SC01/SC02**, pentru a nu fi confundate cu F1 al migrării și cu review-urile istorice închise.
- Scratch poate expira. Constatările, scenariile, ieșirile sanitizate, adjudecarea și limitele sunt păstrate în acest document și Git; nu depind numai de un transcript temporar.
