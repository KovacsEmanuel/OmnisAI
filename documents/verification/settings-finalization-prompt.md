# Mandat pentru sesiunea nouă — finalizare setup, Settings și acceptare T1

> Pregătirea acestui prompt NU lansează implementarea în sesiunea care l-a redactat.
> Operatorul a ales explicit continuarea într-o sesiune nouă și a aprobat **o singură rulare canonică de maximum 90 minute**, după corecțiile finale. Nu a aprobat noi inferențe de produs, T2 sau push.

## 1. Rezultatul și limita

Lucrează în `/home/kali/OmnisAI`. Activează `/ponytail:ponytail` **full**: cea mai mică schimbare completă prin codul existent, fără refactor oportunist, framework, installer, profil sau sistem paralel de rapoarte. Respectă AGENTS/CONTRIBUTING și ownershipul existent.

Finalizează cinci rezultate, nu doar un set de teste:
1. Settings și UI/UX-ul afectat, corectate după cerințele de mai jos și **acceptate vizual de operator pe aplicația reală**.
2. Dispoziție justificată pentru incidentul supervisorului: cauză/remediu verificat sau blocker explicit; fără remediu inventat ori risc acceptat în numele utilizatorului.
3. Verificarea canonică finală, în bugetul nou autorizat, fără eliminarea testelor ori slăbirea limitelor produsului.
4. Cleanup selectiv închis prin absențe verificate și retenție explicită pentru date unice/efecte incerte; set de recuperare clar.
5. Confruntarea cerințelor obligatorii **T1** din canon cu implementarea/probele/reviewurile pe versiunea curentă, fără obligații ascunse sau PASS transferat nejustificat.

**Nu implementa T2.** Nu redeschide întregul MVP/arhitectura, nu lansa mentenanță Hermes-runtime/OAuth, nu promite „zero bug-uri”. Un rezultat acceptabil este: cerințele obligatorii acoperite, UI acceptat de operator, gate-uri trecute, fără blocante cunoscute, limite declarate. Dacă rămâne un blocker, nu declara totul final sau pregătit pentru T2.

## 2. Recuperează numai starea necesară

Bază de produs la pregătire: `9da7648953ff7f477ad9b3cc0c8d29b77ed38ed4`, branch `checkpoint/p2-batch2-pause-20261015`, tracked/index curate, 60 commituri locale înaintea remote-ului. Commitul de predare adaugă numai acest mandat și metadata; identifică HEAD real, nu presupune că baza este încă HEAD.

Rulează read-only: `git status --short --branch`, `git rev-parse HEAD`, `git diff --stat`, `git diff --cached --stat`. Protejate untracked: **`tempkey.txt` și `documents/Omnis_Notite_Originale.html` — nu le citi, modifica, inventaria ca conținut, șterge sau comite.**

Citește minimal:
- `AGENTS.md`, `CONTRIBUTING.md`, unicul CURRENT din `README.md`;
- rândurile afectate din `documents/verification/implementation-status.md`;
- `documents/verification/settings-c-evidence/ui-result.json`, în special `finalization_handoff` și `maintenance.paused_followup.runtime_followup`;
- `web/design/settings-final.md` / `.html`, contractele afectate din UI/UX și arhitectură; vechiul baseline nu anulează feedbackul nou al operatorului;
- `cli/README.md`, `web/README.md` pentru editare/pornire/rollback;
- `documents/verification/api-key-runtime-t1.md` **Acceptare T1 locală scoped**, apoi numai obligațiile T1/T2-prerequisite relevante din plan/arhitectură. Secțiunile PARTIAL istorice nu sunt coadă de reluare.

### Instanța care trebuie păstrată

- Root: `/home/kali/.local/share/omnis-settings-c-9e51d10`.
- Instance UUID: `d694129b-a3e5-446d-9e5b-fe9bc19abed8`; origin `http://127.0.0.1:8780`; schema `0016_provider_models`.
- Ultimul status citit la pregătire: **READY DEVELOPMENT21 / epoch12**, nu STOPPED20. Verifică din nou, fără Start/Stop doar pentru orientare.
- `/home/kali/.local/bin/omnis` și `<root>/omnis` operează aceeași instalație; `omnis` / `omnis start` sunt traseele normale, `--no-open` doar opțional.
- CLI `639530e`; Settings `794cdc9`; diagnostic `7885c48`.
- Imagine păstrată: `sha256:321b7052a5af0f9dc340d3c89a3667833b054dedf38b8e58dfbf7a54af33d30b`.
- Release imuabil păstrat: `7673066`, digest `99409cd18adfd4545bbdb03f9edfc6bcc7cca95973f2e13342d2bd54062ef133`.

Un singur operator/date/profil. UI: Vite build local → `web/dist` montat read-only → refresh, fără rebuild API. Python: Stop verificat → editare → Start controlat, fără reinstalare. Nu modifica Python montat în timp ce rulează. Nu monta checkoutul întreg/home-ul; nu servi secrete/fișiere private. Rebuild numai pentru dependențe/bază/release.

Patru modele și rezultatele operatorului au fost citite anterior; configurația/capurile/operation IDs/costurile au rămas identice după Stop17→Start18/reload. **Nu repeta apeluri pentru badge verde și nu transforma datele operatorului în fixture.** Modelul DeepSeek datat ales de el nu se substituie cu alt alias.

## 3. Cerințele UI/UX ale operatorului — obligatorii

Acesta NU este „polish minor”: operatorul nu acceptă designul actual. Scopul concret este Settings și primitivele comune afectate de aceste fluxuri, nu redesenarea arbitrară a tuturor paginilor sau a funcțiilor viitoare.

### A. Detalii în model, nu un panou tehnic global

- Elimină din partea de sus panoul normal de operație/conectare și mesajele tehnice repetate pentru fiecare refresh/conectare.
- **Varianta finală cerută:** click/tap pe rândul/pastila modelului dezvăluie detaliile imediat dedesubt, în aceeași unitate vizuală. Nu adăuga o a treia pastilă/buton-săgeată separat.
- Codul de bază afișează în dreapta status, `Test`, `Read check`. Intenția este păstrarea celor două elemente utile din rând și mutarea accesului la detalii în expandarea rândului; verifică și captura reală înainte de autorat. Un indiciu vizual discret nu trebuie să devină încă un control redundant.
- Detaliile sunt numai date reale ale acelui model/acelei operații: rezultatul relevant, motivul acționabil, momentul dacă există în contract, identitatea cerută/observată și consumul cunoscut când sunt utile. Fără statistici decorative, valori inventate sau dumping de UUID/revizii în vederea normală. Informațiile tehnice necesare pot avea un nivel secundar închis.
- Expandarea/citirea NU pornește Test și NU retrimite operația. Butoanele de acțiune nu declanșează accidental expandarea și invers; tastatură/focus/aria corecte, fără controale interactive imbricate incorect.
- **Cancel/Stop și recuperarea unei stări incerte rămân accesibile și vizibile când sunt necesare**, chiar dacă detaliile sunt închise. Acțiunea din rând poate reflecta starea reală, nu trebuie adăugate controale redundante. Selectarea istoricului altui model nu schimbă ținta Cancel a operației active/pending.

### B. Notificări compacte, discrete, inspirate de Apple

- Operatorul cere „buline/pastile fine”, premium, în dreapta-jos: dimensiuni compacte, tipografie și spațiere precise, contur/umbră discrete, integrare cu tokenurile existente.
- Nu un panou mare de diagnostic plutitor; fără blocuri lungi, straturi inutile, glows/blur sau animații decorative ca substitut pentru design.
- O singură confirmare utilă pentru o acțiune, nu o notificare pentru fiecare pas intern. Confirmările necritice dispar discret; nu fură focusul și nu acoperă controale, inclusiv pe mobil.
- Erorile acționabile/UNKNOWN nu dispar fără urmă într-un toast temporar: rămân în contextul elementului afectat, cu recuperare clară și fără resend implicit. Stop global și avertismentele de siguranță nu se ascund pentru estetică.

### C. Add models / catalog fără zgomot de sistem

- Fără `Catalog loading`, `Catalog READY`, stări brute și explicații interne simultan sus, în wizard și în toast.
- Progres discret în controlul/lista afectată; fără salt de pagină, pierdere de selecții, butoane care clipesc ori blocare aparent inexplicabilă.
- Dacă lista modelelor nu poate fi citită, mesaj scurt în engleză, pe înțelesul utilizatorului, lângă lista respectivă și cu acțiunea corectă. Cauza exactă rămâne inspectabilă secundar; nu inventa că este cheia greșită.
- „Key saved” dovedește persistența, nu reușita catalogului sau validitatea upstream. Nu șterge cheia/reconfigura conexiunea ca răspuns generic la orice read failure.
- Păstrează un singur Add models, Connection → Models → Review, selecțiile și consimțământul pentru exact modelele/costul cerute; fără simplificări care introduc apeluri implicite.

### D. Connected versus Unavailable — problemă de investigat, nu de cosmetizat

Operatorul raportează: după refresh, un model apare Connected în listă, Unavailable la Assignments, urmat de eroare de catalog; a mai văzut citirea catalogului eșuând deși cheia era salvată.

Citirea SOURCE din pregătire a stabilit numai aceste diferențe:
- `SettingsModelsPage.tsx`, `load()` (~46–70), citește separat latest test și catalogul local; construiește `checks` și `evidence` distincte.
- `entryStatus()` (~320–330) poate returna Connected din testul exact FINISHED/COMPLETED fără a cere aceeași dovadă de catalog ca Assignments.
- `SettingsAssignments.tsx` (~14–36,65–72) și `SettingsModels.ts:24–26` folosesc `usable()`/capabilities pentru disponibilitate.
- `SettingsModelWizard.tsx` (~48–55,120–122) are propria interogare și suprafață de status; `SettingsModelsPage.tsx` (~276–287) duplică notificare/catalog recovery/operație globală.

**Aceasta explică posibilitatea afișării necoerente, NU cauza demonstrată a eșecului de catalog al operatorului.** Reproduce prin callerul real și urmărește răspunsurile/reviziile/capabilitățile/expiry și codul exact al erorii, fără chei/cookies în log.

Distingi: rezultat de test salvat pentru revizia exactă, metadata curente disponibile, eligibilitate pentru assignment și imposibilitate temporară de readback. UI trebuie să le comunice coerent. Nu forța toate badge-urile verzi, nu elimina validarea capabilities/reviziei, nu transforma o eroare de citire în revocare și nu schimba implicit assignmentul/capul. Nu adăuga alt owner/tabel de status dacă proiecțiile existente sunt suficiente. Modifică API/contract numai dacă defectul demonstrat cere asta, propagând producerul/callerii/limitele prin serializorii reali.

## 4. Folosește skillurile și documentarea UI, fără a schimba stackul

Încarcă `omnis-frontend`, `omnis-accessibility`, `omnis-review-qa` la etapa relevantă. Operatorul cere explicit skilluri frontend/UI disponibile în Codex; acestea au fost găsite și citite:
- `/home/kali/.codex/skills/frontend-design/SKILL.md`;
- `/home/kali/.codex/skills/ui-ux-pro-max/SKILL.md`.

Aplică selecția utilă de principii, nu preferințele lor generice care contrazic Omnis: **nu Tailwind/Next.js/Framer Motion noi, fonturi remote, palete/rebrand arbitrare, layout asimetric obligatoriu, framework de toast sau sistem nou de design**. Nu instala nimic doar pentru a rula un skill. React/TypeScript/Vite/Radix/CSS Modules și primitivele/tokenurile existente rămân baza. Skillul `uxui-principles` găsit este în principal un index de instalare, nu motiv de `npx skills add` sau API extern.

Surse consultate, utile pentru deciziile concrete:
- [Apple Feedback](https://developer.apple.com/design/human-interface-guidelines/feedback): feedback aproape de obiect, întrerupere proporțională cu importanța, confirmări doar când ajută;
- [Apple Progress indicators](https://developer.apple.com/design/human-interface-guidelines/progress-indicators): progres discret și corect, fără procente inventate sau etichete redundante;
- [Apple Disclosure controls](https://developer.apple.com/design/human-interface-guidelines/disclosure-controls): detalii la cerere, legate de obiect;
- [NNGroup: Indicators, Validations, Notifications](https://www.nngroup.com/articles/indicators-validations-notifications/): toast pasiv versus eroare persistentă/acționabilă.

HIG nu autorizează refresh provider automat, relaxarea Stop sau copierea unui UI nativ peste aplicație. „Apple-style” înseamnă aici rafinament și claritate, nu animație/efecte gratuite. Definește o singură soluție vizuală scurtă pe baza ecranului real, apoi implementeaz-o; nu inventa trei mockupuri sau încă o bibliotecă. **Aprobarea estetică aparține operatorului.**

## 5. Reproducere, review și QA reală

Un orchestrator; un developer desemnat pentru cod/teste/remedii; review independent pe bytes exacți. Două reviewuri complementare dacă atingi authority/Stop/secrete/concurrency/lifecycle. Orchestratorul nu devine un al doilea autor paralel. Codex este tooling de dezvoltare, nu runtime Omnis. Dacă îl lansezi, folosește skillul `codex`, verifică versiunea/auth status/sandbox fără a citi credentiale; niciun bypass de sandbox pentru a forța pornirea.

Înainte de autorat: inspectează aplicația reală, componentele/CSS/testele afectate, leagă producerul și primul consumer; declară criteriile și fișierele. Nu modifica designul din presupuneri. Dacă noua prezentare cere amendarea contractului UI canonic, fă delta minimă coerentă înainte de cod, nu rescrierea arhitecturii.

Manual și prin regresiile existente, acoperă cel puțin:
1. intrare în Settings, refresh normal/hard reload și tab nou, cu rezultate salvate și assignments existente;
2. expand/collapse pe mai multe modele, tastatură, Test separat, citirea exactă a rezultatului și identitatea Cancel;
3. Add models cu cheie deja salvată, catalog local prezent, citire lentă, catalog absent/stale/partial/failure, schimbare de conexiune; zero notificări de progres duplicate;
4. model testat cu metadata lipsă versus model netestat/disponibil — mesaje coerente și fără assignment implicit;
5. Save & connect cu mai multe modele: consent exact, UNKNOWN/eroare opresc continuarea; late success nu autorizează următorul apel; Stop→Start nu revalidează consimțământul vechi;
6. recuperare după răspuns pierdut/reload/session expiry fără re-send, fără pierderea draftului și fără a închide browserul operatorului;
7. notificări desktop/mobil, fără suprapuneri pe acțiuni/focus/Stop; statusurile importante accesibile, detaliile tehnice secundare;
8. pe artefactul final: persistență, surse/mounturi/identitate păstrate, Start/Status/Stop și refuzurile Host/Origin/CSRF/session relevante schimbării.

Folosește callerii existenți (`web/src/app/*Settings*.test.tsx`, `ProviderKeySettings.test.tsx`, `web/tests/e2e/settings-models.mjs`, testele API/catalog afectate), nu un framework nou de QA. Verifică înainte comenzile/colecția/pinurile/browserul/PG/limitele și oracle-ul. Scenele negative, secretele sintetice și dispatchurile se testează în fixture izolat existent, nu prin fault injection/rotații/revoke în profilul operatorului. Manual înseamnă interacțiune reală și capturi inspectate, nu doar selectori sau screenshot salvat fără citire.

Operator: folosește sesiunea normală; pairing manual dacă a expirat, fără export de cookie/cod/cheie. Nu naviga peste editări nesalvate. Citirile existente și inspecția sunt permise; pentru efect extern necesar reproducerii, verifică autorizația exactă. Nu consuma vechi acorduri de inferență și nu efectua apeluri model plătite fără acord nou. Un refresh local nu trebuie să devină refresh upstream/retest ascuns.

RED → GREEN minimal, regresii afectate, review/fix/re-review, apoi consumerul real. Reutilizează probele neschimbate. După două cicluri numai de harness pe aceeași acceptare, restrânge proba sau declară blockerul, nu adăuga observatori/verificatori. Nu muta întreaga finalizare într-un audit fără produs. Cere acceptarea vizuală pe buildul real înainte de a cheltui rularea canonică finală.

## 6. Runtime: nu confunda observația cu remedierea

Incidentul anterior: supervisorul generation18/epoch10 a ieșit3 cu `QUIESCE/CONTROL_CONFLICT`; API/DB au rămas pornite. Lease expirată, callerul exact și cauza întârzierii neînregistrate. Recovery normal → STOPPED20; diagnostic `7885c48` → Start21/epoch12. **900s fără recurență**, readback final total902.833s; nu este dovadă de remediere sau de defect permanent.

Dovezi private nesensibile: `<root>/evidence/operator-postrestart-supervisor-failure.json`, `operator-idle-supervisor-diagnosis.json`, `idle-diagnostics-7885c48/` (două reviewuri,80SOURCE,25PG/27.77s,observation-result.json). Colectorul este task-scoped/bounded, failure-only, maximum3613bytes din4096, fără date private. Nu reconstrui instrumentarea, nu mări lease-ul5s sau deadline-uri, nu introduce autorestart/watchers/cron.

Începe cu starea și diagnosticul existente. Dacă recidivează, păstrează trace-ul sanitizat **înainte** de recovery; salvează exit/stdout/stderr înaintea assertions. Reproduce/remediază numai cauza demonstrată, apoi review și probă relevantă. Nu injecta defecte în operator pentru diagnostic. Dacă nu există o cauză demonstrată, lasă UNKNOWN/BLOCKED sau cere explicit acceptarea riscului; nu inventa reparație și nu repeta ferestre de observație nelimitate.

## 7. Canonical: o rulare finală de maximum 90 minute este autorizată

- Autorizația nouă este pentru **o singură execuție canonică finală, maximum5400s**, după corecții/affected checks/review/acceptarea vizuală. Fără lansare în sesiunea de pregătire a promptului.
- Păstrează selecția completă și gate-urile. Nicio schimbare de lease/deadline de produs, timeout individual, worker count sau teste eliminate pentru verde.
- Folosește `Makefile` și `ops/run_test_db_gate.py` existente. Verifică parserul real și propagarea bugetului până la consumer înainte de efecte; dacă e necesar, adaptează minimal același traseu, cu regresie/review, nu al doilea runner.
- Pinuri: Node24.21.0, npm11.19.0, Python3.13.15, uv0.12.19. Nicio reinstalare de operator pentru teste.
- Măsurarea istorică:3168API PASS în3213.52s;23migrations67.68s;Settings47.81s;10webE2E117.90s;383CLI source109.996s/383wheel104.485s/status4.16s. Suma3665.551s provine din DOUĂ rulări și exclude alte etape; nu este predicție pentru versiunea curentă. API este componenta lungă cunoscută, profilul fiecărui test nu este stabilit.
- Nu rula încă o suită lungă doar pentru profilare. Dacă opțiunile existente permit, păstrează duratele din aceeași rulare pentru a explica costul; fără infrastructură de benchmark.
- 90minute nu garantează PASS. Păstrează FAIL/TIMEOUT/family-drain și cleanupul real. Un eșec cere diagnosticul/remediul afectat, nu retry orb; altă rulare canonică necesită buget nou explicit. PASS-urile delimitate nu se lipesc într-un PASS integral.

## 8. Cleanup și recuperare fără pierderea datelor

Nu relua ștergerile deja verificate:24worktrees și artefacte/imaginile QA dispensabile, fixture-urile CLI/PG/browser proprii au fost retrase; dovada este în registrul existent/private evidence. Reducerea netă istorică măsurată2.26GiB este doar o etapă, nu suma tuturor tagurilor/ștergerilor. Ultima citire a discului:83%ocupat; reverifică dacă devine relevant.

Pentru resursele încă existente: inventar mic `resursă exactă → owner/consumers → date unice/efecte incerte → retenție/backup → eliminare → verificare`. Descoperire prin roots Omnis, `git worktree list` și metadata Docker, nu comenzi de ștergere după prefix/vârstă/exited. Nu include laboratoarele `vulnappomnis-*`, alte proiecte, toolchainurile/interpreterele comune sau resursele instanței alese.

Instalația veche `omnis-t1-fixed-a5b8939` este deja retrasă STOPPED10, cu date/chei/release păstrate; nu o reactiva. Backupurile logice/cold/restaurările verificate sunt sub `/home/kali/.local/share/omnis-backups/maintenance-056cffd-s6navmih`. Citește metadata/validatori, **nu conținutul cheilor/dumpurilor în context**. Cold STOPPED5 este checkpoint istoric, nu backup al ultimelor configurații, grant actual sau acoperire pentru alte profiluri. Nu repeta backup/restaurare dacă inputurile relevante sunt neschimbate; dacă trebuie protejate date noi înainte de un efect ireversibil, folosește mecanismul existent cu consistență/restore plan corecte.

Fără `docker system prune`/`volume prune`, ștergere globală scratch/home, `reset --hard`, `clean -fd`, stash implicit ori worktree removal fără verificarea ignored/untracked/commiturilor unice. Sudo numai prin confirmare locală, niciodată parolă în chat, containere privilegiate sau schimbarea ownershipului datelor originale. Nu restaura launcherul P1/r1 ca rollback. Măsoară numai spațiul efectiv, verifică fiecare efect; retenția justificată nu este gunoi de șters.

## 9. Închidere și raport

Reutilizează acceptarea T1 istorică5d5bbfb/0b7d675 la scope-ul ei: conectivitate API-key-only/Settings/seif/SystemOperation/sender/outcome/readback/Stop. Nu relansa P2/Hermes ori loturi provider consumate. Reconcilează numai obligațiile T1 și schimbările actuale, folosind registrul existent; corectitudinea documentelor nu substituie runtime-ul. Limitele istorice OrcaRouter live/active-Stop-drain/readerii neprobați rămân explicite, nu se transformă în probe executate sau în obligații T2 inventate.

Actualizează CURRENT și rândurile afectate în loc. Commit după fiecare schimbare coerentă; stage numai căile intenționate, fără amend/squash/reset/push. Pentru documentare: `python -B scripts/render_docs.py --check` și `python -B -m unittest discover -s tests/documentation -v`; regenerează HTML numai când se modifică sursa canonică randată.

La final: aplicația reală în stare verificată, UI acceptat de utilizator, cod/teste/remedii revizuite, date/chei/istoric păstrate, cleanup/retention clare, canonical cu rezultat real, fără modificări intenționate necomise sau resurse QA/writeri uitați. Raport scurt în română: comenzile de folosire/editare/rollback, commituri și probe, ce a fost eliminat/păstrat, blocante/limite și verdictul de pregătire T2. **Nu declara „fără niciun bug”, nu porni T2 și nu confunda funcțional, vizual acceptat și integral verificat.**
