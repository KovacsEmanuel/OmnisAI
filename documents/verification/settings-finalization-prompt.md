# Sesiune nouă — verifică și testul, închide T1, pregătește admiterea T2

> Mandat executabil numai când operatorul îl transmite explicit pentru execuție. Pregătirea/reviewul acestui prompt NU pornesc implementarea, QA sau efecte pe operator.
> Punct verificat înaintea acestei actualizări: main `a7b56374825708ffff0660c2590c32f078d11cf5`; candidat `baf592220415b7e5d199d77b71c1538e9dcec748`. Reverifică Git; nu trata snapshotul ca stare perpetuă. Mandatul anterior și rezultatele lui rămân în Git la acest main, nu sunt comenzi de repetat.

## 1. Rezultat și stil

Lucrează în `/home/kali/OmnisAI`, `/ponytail:ponytail full`, discuție în română/UI în engleză. Obiectivul operatorului este **finalizarea T1 pentru a putea începe T2 cât mai repede**, nu încă un audit sau un șir de checkpointuri. Nu promite un termen în locul dovezilor.

**Testează critic și testul.** Nu porni de la „aplicația este defectă fiindcă testul e roșu”. Ipoteza că scenariul/oracolul verificării este greșit este serioasă, dar trebuie demonstrată, nu aleasă pentru verde. Modifică produsul numai pentru un defect reprodus; corectează un test demonstrat greșit păstrând cerința reală, controalele negative și istoricul FAIL. Nu relaxa validarea, CAS, identitatea, rezultatul durabil, bugetele sau Stop.

În această sesiune finalizează diagnosticul restrâns, remediul necesar, QA, integrarea/instalarea rafinărilor și celelalte obligații T1 deja admise, până la rezultat verificat sau blocker concret. Nu opri după fiecare commit/review și nu cere din nou acord pentru activitățile izolate deja incluse. Din absența operatorului de la laptop nu deduce lipsă de pairing/confirmare: ultimele probe izolate erau paired și aveau deja admitere202. Cere intervenție numai pentru o limită reală, identificată explicit.

## 2. Citește minim și păstrează ce funcționează

Respectă AGENTS/CONTRIBUTING și unicul CURRENT din README. Încarcă skillurile relevante, nu întreg catalogul: `omnis-delivery`, `omnis-review-qa`, `systematic-debugging`, `omnis-project-status`; frontend/accessibility/release/storage la frontiera lor.

Surse actuale:
- `documents/verification/settings-c-evidence/models-polish-20261029/blocked-resume.md` — starea exactă și următoarea frontieră;
- `documents/verification/settings-c-evidence/ui-result.json` → `models_refinement_20261030`, apoi numai blocajele rămase din `finalization_handoff.execution.finalization_execution`;
- `documents/verification/api-key-runtime-t1.md` → „Finalizare Settings și Remove — instalat scoped, T1 neînchis”; rândurile afectate din harta implementării;
- `web/design/settings-final.md` și UI/UX numai pentru comportamentul afectat; planul §7/§8 pentru T1 și dependența T2.

Candidatul este în `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`, branch `feat/settings-inline-feedback-20261029`, HEAD `baf592220415b7e5d199d77b71c1538e9dcec748`, tree `aa53b50706e84ba494825a1581e4bdc6d9e75557`. Tracked/index erau curate; patru dependency links preexistente către main nu se adoptă, înlocuiesc sau șterg prin dereferențiere. Scratch poate expira: verifică existența și Git/refurile, nu reconstrui probe și nu rerula automat ce este acceptat.

**Nu reimplementa Remove sau tranziția0016→0017.** Remove/upgradeul anterior sunt deja integrate și instalate; rafinarea UI nouă este comisă, SOURCE aprobată, dar neintegrată/neinstalată. Reutilizează cele172 teste componente, patru scenarii native SOURCE și reviewurile compuse pe bytes neschimbați. Matricea58situri înseamnă21prefix real și37SOURCE, nu58controale native sau toate combinațiile stărilor.

## 3. Prima decizie: ce este greșit la Stop → Connected?

Ultima probă `proc_b9e5ca260a65`: outer2,1FAIL55.34s. În `web/tests/e2e/settings-models.mjs:203–240`, driverul ține răspunsul real202, verifică wizard închis/listă/Connecting, apasă **Stop remaining checks**, apoi așteaptă **Connected** la223 fără citirea explicită disponibilă în UI. Observat: `Connecting / Cancel test / Remaining checks stopped. Read the admitted check. / Read test status`.

**Nu este încă demonstrat dacă produsul sau așteptarea testului este greșită.** Nu avem răspuns terminal al aceleiași operații/latest, starea peerului/workerului ori martor visibility/poll pentru acest eșec. Nu presupune nici că un Stop trebuie să devină Connected automat, nici că orice Connecting după Stop este corect.

Înaintea altui traseu complet:
1. Citește semantica reală a Stop remaining, Cancel, `startTest`, `connectEntries`, `readTest`, polling și actualizare cache; urmărește definițiile/usages. Separă **fluxul sănătos fără Stop** de **abandonarea continuărilor cu readback explicit**.
2. Discriminează cu cel mai mic control existent: aceeași operation ID, requested/observed state și revision, latest-entry/current/exact identity, peer/worker terminat sau încă activ; dacă este necesar, starea visibility/focus care condiționează pollingul. Reține numai metadate nesensibile, înaintea aserțiunii și teardownului. Folosește read-only „Read test status” unde contractul îl cere; fără alt Start/retry/model call pentru a fabrica rezultat. Dacă lipsește martorul păstrat, orchestratorul poate admite o singură reproducere minimă nouă în fixture sintetică proprie, cu ipoteză/scenariu/apeluri/identitate/deadline/cleanup stabilite înainte; nu adopta vechea DB și nu folosi operațiile operatorului. Nu este acord pentru încă un replay complet.
3. Dacă operația este terminală iar UI rămâne stale contrar contractului, reproduce/fixează minimal produsul. Dacă oracolul confundă Stop cu finalizarea automată sănătoasă, corectează **scenariul**, fără schimbare de produs și fără omiterea probei terminal/current/latest pentru fluxul pozitiv. Dacă workerul/peerul nu termină, investighează acea frontieră reală, nu eticheta UI.
4. Demonstrează și controlul sănătos fără oprire, și proprietatea Stop: niciun model rămas nesent nu pornește; operația deja admisă rămâne contabilizată și citibilă, fără succes sau anulare remote inventate. Citează explicit ce dovedește fiecare control.

Sunt păstrate trei FAIL-uri refinement: Provider selector55.01s, cursă route cleanup45.69s, apoi Connected55.34s. Primele două au mecanisme demonstrate și remedii, nu motive de a modifica din nou produsul: rolul exact combobox repară selectorul; `unrouteAll({behavior:'wait'})` încheie cele două callbackuri după resolve, fără a elimina allowlistul global. Nu readopta `unroute(default)` și nu ignora excepții.

Contoarele legacy default-web2 și SOURCE observer2 rămân consumate, fără reset între sesiuni. **Nu relansa încă o dată întregul `entry_remove_ui` doar pe o presupunere.** Mai întâi model cauzal și probă îngustă admisă; apoi doar consumerul necesar pe delta revizuită. Nu un nou harness/supervisor, timeout crescut, suite repetate pentru număr sau ocolirea aserțiunilor. Orice schimbare de oracle explică cerința păstrată și de ce noul control nu poate trece din motiv greșit.

## 4. După clarificare, termină Models în produsul real

Un orchestrator admite scope/dependențe/efecte și integrează; un developer desemnat scrie/fixează în worktree; review independent pe FREEZE exact, apoi QA reală. Două reviewuri complementare pentru delta de autoritate/concurență/dispatch/Stop/secrete; review focalizat proporțional pentru test/presentation-only. Reutilizează aprobările neschimbate. Commituri mici, fără amend/rebase/squash/push și fără `git add .`/`-A`.

Reutilizează consumerul și runnerul existente, cu preflight fără efecte pentru argv/pins/library/schema/input-size/UID/acces/oracle și cleanup. Comanda de referință, **nu instrucțiune de rerun imediat**:

`PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-remove-ui-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600`

Închide probele reale lipsă: terminal/current/latest exact, Assignments și capuri/roluri independente, Save local fără panou sus, succes unic după receipt/readback, existing Replace/Disable/Reconnect fără secret pierdut, trafic/efecte atribuite și census/restart. Limitele actuale planificate sunt12mutații browser/8GET+2POST noi la peerul sintetic și13tabele; dacă scenariul trebuie corectat, deduce explicit delta necesară înainte de efecte, nu o excepție generală pentru apeluri/istoric. Nu cere toate58situri în API dacă au deja control real la nivelul declarat; nu lăsa o matrice verde să înlocuiască persistența lipsă.

Păstrează toate cerințele UI deja implementate: inline exact confirmations/Cancel/Escape/focus44; zero panouri normale sus; notificări scurte fără ocluzia labels/hints/provider/model/status, focus pause; approval singular/plural și hint cost fără Fixed input/technical clutter; Save & connect după Save confirmat închide wizardul și continuă numai în listă, cu un Cancel/Stop contextual. Erorile/UNKNOWN/receipt recovery rămân persistente și fără resend. Nu rebrand/reprototip/dependency nouă. Inspectează capturile reale desktop/mobil, nu doar PNG existente sau text DOM.

Integrează granular și livrează numai după clearance/QA. Operatorul este aceeași instanță UUID `d694129b-a3e5-446d-9e5b-fe9bc19abed8`, origin8780/root `/home/kali/.local/share/omnis-settings-c-9e51d10`, ultima citire READY27/epoch16, DEVELOPMENT,0.1.1/schema0017. Nu repeta recover/upgrade/Start pentru inventar. Pentru UI-only există backupul public `/home/kali/.local/share/omnis-settings-polish-20261029/rollback-web`; păstrează inode-ul `web/dist`, Docker îl montează ca director. Nu suprascrie releaseul imuabil. Verifică assets/build/servire și tabul executat fără editări nesalvate; pairing uman numai dacă sesiunea operatorului chiar a expirat. Fără Test/Refresh/ștergere modele reale. Acceptarea estetică umană este distinctă de QA; nu o inventa dacă operatorul nu răspunde.

## 5. Finalizează și restul T1, nu numai această aserțiune

- **Supervisor:** cauza pierderii lease rămâne UNKNOWN.5486ms COMMIT→TX_DONE nu separă server/driver/pool/scheduling. Diagnostic bounded pe dovezile existente și cel mai mic martor care schimbă decizia; remediu numai după cauză/reproducer și review/QA. Nici recovery/READY, nici o fereastră fără recurență nu închid cauza. Fără lease/deadline mai mari, autorestart/watchers sau fault injection în operator. Datele și authority sunt păstrate.
- **Default-web:** două FAIL-uri istorice neexplicate. Ia în calcul și fixture/oracle/observer greșit, dar demonstrează. Fără al treilea retry larg legacy32models+2Starts2Cancels, teste șterse, timeout/workers relaxate sau PASS izolat declarat gate complet. Cancel current-revision202→CANCELLED este deja acceptat scoped și nu se reexecută doar pentru încurajare.
- **Canonical:** numai după prerechizitele reale/review/QA, o singură rulare finală completă≤5400s,0din1 consumate la checkpoint; targetul existent `check-components` prin `ops/run_test_db_gate.py`, pinned uv, proces background urmărit și exact readback. Nu schimba selecția/limitele; alt canonical complet după FAIL cere buget explicit nou. Nu numi scoped PASS închidere T1.
- **Cleanup:** continuă numai delta selectivă necesară. Cele4imagini QA și checkoutul fqa au fost deja retrase. Păstrează instanța/datele, originale, efecte incerte, rollbackul/backupurile și refurile unice; owning-tool exact, consumatori/mounturi/symlinkuri verificați, absențe și spațiu măsurat. Fără prune/global scratch purge; nu relansa fixture-uri ca să le cureți. Nu declara cleanup complet din retenție parțială.

Dacă e nevoie de modificări lifecycle/DB/operator, stabilește before/after nesensibil, backup actual și restaurare verificată/inversa înainte de efecte. Backupurile T1 vechi nu autorizează downgrade după OPEN. Nu hot-edit Python montat cât API rulează. Nu cere/accesa chei/cookies/coduri/DSN/raw Docker Env. `tempkey.txt` și `documents/Omnis_Notite_Originale.html` sunt absolut protejate: nu citi/modifica/hash/stage/șterge. Nu șterge dependențe partajate sau date unice.

## 6. Poarta pentru T2 și raportul final

Prioritizează lucrul care permite **T2 cât mai repede**, nu rapoartele. După T1 verificat integral, aliniază CURRENT/SL12/SL33/registrul existent și dă verdict explicit `T1_CLOSED / T2_READY` cu baza reală. T2 este conform plan§7 **Agent/Runner/rol/task → tool inert cerut de model → rezultat persistat/consumat → următoarea decizie**, nu alt smoke. Identifică atunci prima felie/producer/consumer și autorizațiile ei efective; **implementarea T2 rămâne mandat separat**, nu extensie automată a finalizării T1. Nu începe T2 cât T1 este BLOCKED și nu considera dorința de a începe azi derogare de la gate-uri.

Fără push/fetch, provider/model/Refresh live ori buget nou, conturi/credentiale personale, trafic țintă/M-LAB, T2 sau purge prin acest mandat. Peerii sintetici izolați sunt permiși; inferența de dezvoltare este distinctă de efectele produsului. Cere numai limitele reale neacoperite, nu acord pentru fiecare remediu local deja admis.

La final: ce este efectiv disponibil în aplicația operatorului, dovezi/review/commituri, cleanup și limite, verdict T1/T2. Dacă există blocker real, păstrează un singur recovery point cu observația discriminantă lipsă, termină celelalte ramuri independente admise și nu spune „gata” din oboseala testelor. Rapoarte scurte în română; nu nararea fiecărui review/async rezultat. Pentru documente rulează renderer check, unittest documentation și diff check; HTML numai dacă sursa canonică randată s-a schimbat. Comite fiecare schimbare coerentă și verifică Git; niciun intended change necomis.
