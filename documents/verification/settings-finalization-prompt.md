# Sesiune nouă — finalizează T1, instalarea Remove și cleanupul selectiv

> Acesta este mandatul de execuție **numai când operatorul îl transmite explicit unei sesiuni noi pentru executare**. Redactarea, citirea pentru analiză sau reviewul acestui fișier nu pornesc implementarea ori efecte pe operator.
> Snapshot citit la 2026-10-29T19:29:30+02:00. Checkpoint înaintea actualizării acestui mandat: main `2879f3158bdc231b0e905d0e3948f9db64762097`; candidat Remove `ed611aa40c90f62f4f511cc1951a68970e2ba51b`. Reverifică Git și starea reală; nu trata snapshotul ca stare perpetuă.

## 1. Rezultatul cerut și autorizația delimitată

Lucrează în `/home/kali/OmnisAI`. Activează `/ponytail:ponytail full` și încarcă skillul. Vreau **finalizare funcțională, nu încă un plan, un audit general sau un șir de checkpointuri**. Cod minim complet prin producerii/callerii existenți; fără framework, owner, installer paralel, refactor oportunist ori opțiuni „pentru viitor”. Nu confunda minimul de cod cu omiterea validării, siguranței, accesibilității sau QA.

Prin transmiterea acestui prompt pentru execuție, autorizez în noua sesiune:
- implementarea, integrarea și validarea tranziției compatibile0016→0017 pentru **aceeași instanță/date**, inclusiv CLI/API/control/reconcile/release/lifecycle și backup/restaurare prin mecanismele existente;
- recuperare normală și Stop/Start controlate, necesare acestei tranziții, după diagnostic/baseline și prerechizitele de recuperare; fără resetarea profilului ori abandonarea efectelor incerte;
- diagnosticul bounded și remedierea minimă a unui defect demonstrat al supervisorului; recovery singur nu este remediu al cauzei;
- închiderea blocajelor T1 rămase, review/QA pe delta curentă și **o singură rulare canonică finală de maximum5400s**, după prerechizite;
- **ștergeri selective de resurse Omnis vechi/QA dispensabile**, numai după clasificare exactă, lipsa consumatorilor și păstrarea recuperării/datelor unice. Nu doar inventaria: execută eliminările admisibile și verifică efectele.

Nu mai cere acord pentru fiecare pas deja inclus aici. Cere numai la o limită reală: acces administrator, pairing/acceptare vizuală umană, resursă neclasificată ori efect din afara acestui scope. Timeoutul vechii întrebări nu a fost acord; acest mandat nou, dacă este transmis pentru execuție, este autorizația delimitată. Nu rescrie istoria acelei lipse de acord.

**Neautorizate:** T2 sau alte faze de produs, push/fetch, conturi noi, credentiale personale, export de chei/sesiuni, trafic țintă, provider live/LLM/Test/Refresh upstream sau buget de produs nou. Inferența agenților de dezvoltare este distinctă. Peerii sintetici locali din fixturele existente sunt permiși și etichetați ca atare. Nu șterge modele reale pentru QA și nu modifica assignments/capuri/chei pentru a obține verde. Unicul Refresh autorizat anterior este consumat.

## 2. Starea de pornire — nu reimplementa ce este verificat

- Checkout principal: branch `checkpoint/p2-batch2-pause-20261015`, checkpoint `2879f31` înaintea acestui prompt; tracked/index curate la citire. Două untracked **protejate absolut**: `tempkey.txt` și `documents/Omnis_Notite_Originale.html`. Nu le citi, modifica, șterge, hasha sau stage-ui.
- Remove: `/home/kali/.hermes/cache/scratch/remove-model-fa5451e`, branch `feat/settings-remove-model`, HEAD `ed611aa40c90f62f4f511cc1951a68970e2ba51b`, tree `38463d72bb4271bc11ec6f05074be4cf9d108ada`. Produsul este implementat și comis, **neintegrat/neinstalat** în operator. Untracked preexistente: `api/.venv`, `tools/development/anti-slop/node_modules`, `web/node_modules`; sunt dependențe partajate, nu fișiere de adoptat sau ținte de șters prin dereferențiere.
- Canon înainte de produs `0f4a8a7112026b33188683e8c614e2ca50d3556b`, produs `c4d465c072ebbd246bd882441a7465b55b0b2ab6`; proof checkpoint `190fae18e57e115a8a86559cec386b9ea147fd4b`; remedii separate `bf0320a3b825866ae1c25df441c8e7f7db1812f2` și `ed611aa...`. Păstrează commiturile și proveniența, fără squash/amend/rebase.
- Părinte și revieweri au verificat53 bindings blob/SHA; delta finală față de190 are5fișiere. Ultimele remedii nu schimbă API/CLI/storage/migrare/CSS: oracle de test atribuit corect, explicație in-use locală și focusfallback comun.
- Două re-reviewuri finale SOURCE aprobate și compuse cu scope-ul neschimbat. R1-P01/P02 și R2-P01/P02 închise scoped. **R2-R01 rămâne HIGH/BLOCKED pentru rollout: tranziția compatibilă lipsește**, nu defect al comenzii Remove.
- QA independentă pe exacted611aa: `test-settings-remove-pg` **4PASS23.67s**, `test-settings-remove-ui-pg` **1PASS45.66s**, code0/family_drained=true; history/retiredID/readd/concurență atribuită/receipt pierdut/noresend/APIrestart probate. Browser0externalRequests/0pageErrors. Cinci PNG viewport inspectate:320/390/1280/1440 și in-use1440; placement/focusoutline/context corecte. Native direct-success/moved-focus sunt component-only, nu probe native; tastele fizice ale dialogului OS nu au fost certificate.
- Procesele proprii `proc_7527cf873d6e` și `proc_e0c485193ebf` sunt EXITED0, nu trebuie relansate. Niciun subagent/writer activ la predare. Notificările lor întârziate sunt duplicate, nu cereri noi.

Remove înseamnă retirement persistent din utilizarea viitoare, nu ștergerea istoricului/testelor/costurilor/receipturilor/cheii/providerului/altor modele. Default/Brain/Investigator/Validator și operațiile nesettled blochează fără fallback; confirmare exactă, CAS/replay/readback; re-add are ID nou fără Connected moștenit, Save stale nu reactivează ID retras. UNKNOWN terminal rămâne istoric incert, nu reînnoirea acordului vechi. Nu relaxa generation pinning, NEEDS_RECONCILIATION, DATA/bugete, Stop/Cancel sau limitele trust-boundary.

## 3. Instanța și dovezile care trebuie păstrate

**Operatorul ales**, nu o instanță nouă:
- root `/home/kali/.local/share/omnis-settings-c-9e51d10`;
- UUID `d694129b-a3e5-446d-9e5b-fe9bc19abed8`, origin `http://127.0.0.1:8780`;
- `/home/kali/.local/bin/omnis`; ultimul `status --json` exit4: **UNAVAILABLE / RECOVERY_REQUIRED**, DEVELOPMENT, release0.1.0/schema`0016_provider_models`, dashboard/control false;
- patru modele reale și istoric/chei/configurații de păstrat. Nu pretinde că READY21/24 sau epoch14 sunt starea actuală. Baza vizuală77f9b58 a fost acceptată de operator; noul Remove nu este încă acceptare instalată.

Citește minimal AGENTS/CONTRIBUTING, unicul CURRENT din README, rândurile SL12/SL33 și obligațiile T1 din `documents/verification/implementation-status.md` și `api-key-runtime-t1.md`. Sursa detaliată unică este `documents/verification/settings-c-evidence/ui-result.json` → `finalization_handoff.execution.remove_model_delivery.final_candidate`, plus `default_web_gate`, `second_runtime_qa`, `runtime_recurrence_after_visual` și retenția maintenance. Nu încărca tot istoricul/MVP.

Originale în `documents/verification/settings-c-evidence/`: `remove-model-r1-c4d465c-original.md`, `remove-model-r2-c4d465c-original.md`, `remove-model-r1-190fae1-original.md`, `remove-model-r2-190fae1-original.md`, `remove-model-r1-ed611aa-original.md`, `remove-model-r2-ed611aa-original.md`. Citește ultimele două și numai R2-R01 din R2/c4 pentru tranziție; nu reaudit toate scope-urile acceptate. Ultimele SHA: R1`beff47c5e258e7ef68fea49d5df6e9d4f41b23f658c0f5c3962e923a70e2273c`, R2`3724ce4aee0409b27e435b2e53d2a6fdab6dd39169a3b96656c71db0ec464a10`. Nu rescrie FAIL-urile/originalele pentru verde.

Probe finale: `/home/kali/.hermes/cache/scratch/rpg-h3ZjpJ/db-414134b1d075489c`, `/home/kali/.hermes/cache/scratch/rui-N3LDQr/db-27420030ead44da1`; browser/capturi sub al doilea root QA, `pytest-of-kali/pytest-0/test_api_pg_sdk_protocol_and_r0/`. Freeze/checkpoint `remove-model-freeze-ed611aa.json` și `remove-model-checkpoint-ed611aa.md` în scratch. SHA freeze`663ba083b57e00dcee29471bf5aaf5a5b0e01594e0389e68d6892adf41b0047a`. Scratch poate expira: concluziile/hashurile sunt versionate; absența lui nu invalidează automat probele sau justifică rerun.

## 4. Execuție rapidă, cu ownership și porți reale

Încarcă la nevoie `omnis-delivery`, `omnis-project-status`, `omnis-release-ops`, `omnis-review-qa`, `systematic-debugging`; UI/accessibility/storage numai la etapa relevantă. Nu instala skilluri/MCP/watchers și nu adăuga proceduri globale ca substitut pentru produs.

Un orchestrator, **un developer desemnat** în worktree izolat pentru cod/teste/remedii. Poți paraleliza cu un diagnostic read-only al supervisorului sau clasificarea cleanupului, numai dacă rezultatul schimbă o decizie. Nu multiplica writerii/auditul/rapoartele. Înainte de dispatch stabilește producerul real, primul consumer, inputurile/dimensiunile, fișierele și acceptance row. Orchestratorul nu scrie produs în paralel cu developerul.

Pentru delta lifecycle/authority: **două reviewuri independente complementare pe același FREEZE exact** (commit/blob/diff/artifact). Reutilizează aprobările neschimbate. Finding concret → părinte reproduce/adjudecă → același developer fixează minimal → affected checks → focused re-review; apoi QA independentă a consumerului real. Developer GREEN nu este acceptare independentă. Nu cere QA deja trecută ca prerechizit circular pentru admiterea QA.

La fiecare schimbare coerentă: commit mic cu ce/de ce/comenzi/rezultate/limite/rollback; stage numai căile intenționate și verifică commit/status. Păstrează un singur registru/punct de recuperare. Nu opri mandatul după fiecare commit/review: continuă până la rezultat sau blocker real/limită de siguranță, nu până la încă un helper.

## 5. Prima felie: tranziție compatibilă, nu hot-patch

Verifică întâi read-only Git, identitatea/serviciile/mounturile reale și baseline-ul nesensibil al datelor. Citește R2-R01 și traseele existente: `cli/src/omnis_cli/{instance,release,start,restart,recover,backup}.py`, `ops/build_control_bundle.py`, `api/src/omnis/core/{db,schema}.py`, `api/src/omnis/modules/instance/service.py`, `cli/README.md`; apoi numai definițiile/usages afectate. Candidatul a schimbat deja CLI schema handling în instance/release/start/backup, dar **nu a livrat puntea instalată**.

CLI vechi cere0016; API candidat cere0017. CLI nou singur respinge locatorul/releaseul0016; joburile instalate nu provin automat din mountul development. Restartul vechi nu execută upgrade; slotul0.1.0 este imuabil, restore cere schema/digest compatibile. Nu inventa o comandă `upgrade` existentă și nu rezolva prin editarea manuală a schema/version/digest, restore cross-digest, suprascrierea releaseului ori profil gol.

Alege cea mai mică tranziție completă prin mecanismele existente: compatibilitatea vechi/nou, artefacte CLI/API/control/reconcile coerente, identitate nouă de release dacă este necesară, migrare0017 și rollback real. Orice contract lipsă primește delta canonică minimă înainte de cod, nu arhitectură nouă. Pregătește/probează în fixture izolată upgradeul de la release/schema vechi **populat**, pozitiv și refuzurile relevante, readback/identitate, eșec parțial și restaurarea admisă; fără secrete/LLM live. Review și QA înaintea efectelor operatorului.

Înaintea oricărei modificări de date/operator: consemnează before/after nesensibil și inversa, consistența backupului, disponibilitatea materialului criptat necesar și restaurarea verificată în copie izolată. Nu afișa/citi în context chei, cookies, coduri, dumpuri sau Docker Env; folosește mecanismul nativ de backup, nu export de secrete. Backupul vechi `.../omnis-backups/maintenance-056cffd-s6navmih` este istoric și nu acoperă automat configurația actuală sau0017; refolosește-l numai dacă inputurile/identitatea/schema/digest/stopped-state chiar se potrivesc. Nu consuma un grant STOPPED valid printr-un Start făcut doar pentru inventar.

**Nu modifica Python montat cât rulează API-ul operatorului.** Mai întâi starea/Stop normal verificate și prerechizitele de recovery, apoi integrare granulară a commiturilor revizuite și tranziție controlată. Păstrează metadata CURRENT mai nouă din main, nu readopta READY istoric din branchul candidat. Nu publica UI0017 singur peste API0016. După pornire verifică exact UUID/origin/release/schema/CLI/API/control/assets, starea reală și egalitatea configurațiilor/assignments/operation IDs/istoricului/cheilor prin proiecțiile existente, fără valorile secretelor.

## 6. Supervisor și cele două blocaje vechi — diagnostic țintit

**Supervisor:** recurența `e9a7f3bac7e9` exited3/LEASE_LOST este capturată în `<root>/evidence/remove-model-fa5451e-pre-recovery.json`, anterior `finalization-supervisor-recurrence.json`. Cauza este UNKNOWN:5486ms COMMIT→TX_DONE/492ms după expiry nu izolează server commit, CPU sau clock. Folosește colectorul/procedura bounded existentă; păstrează trace înainte de recovery. Nu reface instrumentarea, nu mări lease5s/deadline-uri, nu adăuga autorestart/cron/watchers. Fault injection/revoke/kill/lease mutations sunt permise numai în fixturele izolate admise, nu în operator. Diagnostic inițial timeboxed20min pe dovezile existente; dacă trebuie observație nouă, o singură fereastră bounded justificată, nu repetări900s „până pare stabil”. Un remediu cere cauză/reproducer, review și probă relevantă; fără acestea raportează BLOCKED/cauză necunoscută, nu „fixat prin restart” și nu accepta riscul în numele utilizatorului.

**Default-web:** două rulări FAIL —1FAIL292PASS37.65s și4FAIL289PASS46.38s. Simptome session/bootstrap/library delay; cauza necunoscută. Logurile și controlul baseline sunt în registru; nu deduce lipsa regresiei din109teste componente ori un pass izolat. Localizează callerul/bootstrapul exact, fără mărire timeout/workers sau îndepărtare teste.

**Cancel409:** oracle-ul HTTP greșit200 a fost corectat la202, cu JSON-first-once/diagnostic allowlisted; asta NU explică409 real. Următoarea probă trebuie să distingă status/error_code/operationID/requested-revision/observed-revision la frontiera pre-Cancel, nu să inventeze REVISION_CONFLICT. Folosește mecanismul existent și cel mai mic scenariu cu operația reală, peer local și Cancel/readback; fără noul owner/harness, fără a cere Cancel sub lockul pe care îl ții.

**Contorul vechi harness-only2 rămâne consumat între sesiuni.** Fără al treilea retry larg default-web/vechiul32models+2Starts2Cancels. Un model cauzal corectat și consumer mai îngust trebuie admise explicit înaintea altei probe; nu reseta contorul prin redenumire, sesiune nouă sau Remove. Repară numai defectul demonstrat; un scoped PASS nu șterge FAIL-ul istoric.

## 7. Aplicația operatorului și gate-ul final

Păstrează Settings C/77f9b58: paletă/fonturi existente,3coloane egale desktop/3rânduri mobile, înălțime intrinsecă, fără carduri și padding decorativ; Remove în dreapta/centrat desktop, sub metrici mobil, Test separat, min44/focus/English-only. Nu reimplementa sau redesena Remove. Refolosește QA53bindings/4PG+1UI și CLI101 privat la scope-ul neschimbat; rerulează numai call paths afectate de noua tranziție, apoi gate-ul obligatoriu la integrare.

Pe instanța instalată reală: navigare/reload, expand/tastatură, date și assignments, controlul Remove/context/confirmare anulată/focus; fără ștergerea unui model real sau Test/Refresh. Folosește sesiunea normală; dacă a expirat, pairing manual prin traseul normal, fără extragere cookie/cod/cheie, fără profil browser clonat. Inspectează capturile, nu doar salva PNG. Cere acceptarea vizuală a controlului nou pe aplicația reală când este posibil, fără a redeschide baza deja acceptată. Nu certifica screen-reader/all-browsers/OSdialogkeys din Chromium.

Înainte de orice probă: argv/choices/collect/import/pin/access/UID/căi/oracle fără efecte; apoi fixture fresh, deadline și cleanup proprie. Pinuri existente: Node24.21.0/npm11.19.0/Python3.13.15/uv0.12.19; binare în `/home/kali/.local/share/omnis-toolchains/bin`. Nu instala dependențe în Hermes global și nu arăta raw gate.log/DSN în context.

Canonicalul este **o singură rulare finală completă≤5400s**, încă neconsumată. După fixuri/review/QA și acceptare folosește traseul existent `ops/run_test_db_gate.py --check --target check-components --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 5400` prin interpreterul API fixat, env/fixture sigure. Verifică propagarea reală; nu schimba selecția, workers, timeouturi individuale sau guarduri pentru verde. Rulează ca proces background urmărit, cu ID exact și readback exit/family_drained/artefacte; nu timeout foreground420s și nu polling/subagenți pentru un simplu shell job. Păstrează duratele din aceeași rulare dacă suportate, nu altă suită pentru profilare. FAIL → remediu/review/affected check; **alt canonical complet cere buget explicit nou**, nu lipi PASS-uri parțiale.

## 8. Ștergeri selective, nu păstrarea tuturor copiilor și nu purge

Poți clasifica read-only în paralel, dar ștergerile dependente de noua instalare așteaptă validarea replacementului și rollbackului. Folosește `storage-maintenance` și `omnis-release-ops`; inventarul existent o singură dată plus delta necesară, nu rescanare globală home/root. Autorizația este pentru resurse Omnis identificate, nu laboratoare `vulnappomnis-*`, alte proiecte, toolchainuri comune sau fișierele protejate.

Pentru fiecare resursă: **cale/ID exact → producer/owner → consumatori cwd/openfiles/mount/restartpolicy/symlinks → date unice/efecte unsettled → recuperare/reconstrucție → KEEP/DELETE/BLOCKED cu motiv → comandă owning-tool → readback**. Retenție minimă: instanța curentă/date/istoric/chei, backup-restaurare și rollback actual probate, originale/evidence necesare pentru efecte incerte. Numele „scratch/cache/old/exited” nu dovedește dispensabilitatea; nici local-only nu obligă păstrarea oricărei copii regenerabile. Nu crea automat arhive OCI pentru fiecare build vechi dacă nu este cerut byte-exact rollback.

Candidatele de worktree păstrează HEAD/commituri unice într-un ref; verifică tracked/index **și ignored/untracked**, shared deps/consumers; `git worktree remove` exact, fără force, apoi absență cale/registration și ref păstrat. Elimină numai symlinkul admis, nu targetul comun. Branchul/istoricul nu se șterg ca economie de checkout. Legacy QA `/home/kali/.hermes/cache/scratch/fqa-a488b26` la`e56bc648848a0e2b88cf8de462f8c6cfba276243` este alt worktree decât candidatul Remove; clasifică-le separat. Nu șterge worktree-ul activ înaintea integrării/păstrării artefactelor necesare.

Noile fixture-uri parent/developer au deja containere/rețele/socketuri ABSENT și PGDATA/loguri păstrate; nu relansa pentru a le curăța. Decizia pentru datele vechi depinde de settlement/proveniență și retenție, nu de o probă fresh ulterioară. Instalația veche `omnis-t1-fixed-a5b8939` era retrasă STOPPED10, nu o porni/adopta pentru inventar. Nu folosi P1/r1 ca rollback improvizat. Inventarul istoric de procese/cwd a fost incomplet din permisiuni: nu declara lipsa universală a consumatorilor sau disk reconciliat complet.

Fără `docker system prune`/`volume prune`, ștergere globală scratch/home, `reset --hard`, `clean -fd`, stash implicit, ștergere DB/credentiale/backupuri neclasificate. Prima permisiune refuzată cere oprire pe ținta aceea și diagnostic owner/parent, nu retry recursiv, chown original sau container privilegiat. Admin necesar: cere acțiune locală exactă, niciodată parolă în chat. Măsoară df/allocated bytes înainte/după fără dublarea directoarelor/layerele comune. Raportează ce a fost efectiv eliminat, ce rămâne și prerechizitul concret; cleanup parțial nu devine complet prin redenumirea restului drept retenție.

## 9. Criterii de închidere — nu omite și nu extinde MVP

Bifează din cod/probe/review curente, nu din chat sau un număr de teste:
1. Remove integrat granular și instalat coerent; aceleași UUID/origin/date/chei/istoric/assignments/capuri, fără implicit provider/model effect.
2. Tranziție0016→0017 și backup/restaurare/rollback probate pe artefactele compatibile; noua instalație utilizabilă real, nu numai SOURCE/build.
3. Supervisor: remediu cauzal verificat sau blocker explicit; niciun risc acceptat tacit. Nu declara finalizare fără dispoziția cerută.
4. Blocajele default-web/Cancel rezolvate prin dovezi relevante, review și caller real; FAIL-urile/contorul rămân în istoric.
5. UI/UX/Stop/Cancel/focus/UNKNOWN păstrate, inspecție reală și acceptare operator delimitată; nu un nou mockup sau un badge verde.
6. Canonical complet real în buget și cleanup al familiei; limite/NOT_RUN separate, nu certitudine universală.
7. Ștergeri admise efectuate, absențe verificate, retenție/recuperare exacte; fără resurse QA/writeri uitați sau pierderea datelor unice.
8. Cerințele obligatorii T1 din canon reconciliate; dovezile istorice5d5bbfb/0b7d675 rămân scoped, nu relansa bugete live ori Hermes/P2. T2 este doar verdict/discuție ulterioară, **nu implementare automată**.

Actualizează CURRENT/SL12/SL33 și registrul existent în loc, cu snapshoturi/rezultate/limite; nu rapoarte repetitive pentru fiecare comandă. Pentru docuri: `python -B scripts/render_docs.py --check`, `python -B -m unittest discover -s tests/documentation -v`; regenerează HTML numai dacă sursa canonică randată se schimbă. Commit fiecare schimbare coerentă, readback git show/status; fără push sau intended changes necomise.

Continuă până la aceste rezultate ori un blocker real de autorizare/acces/siguranță/buget. Dacă blochează ceva, termină celelalte ramuri independente admise, nu ascunde problema și nu promite „gata tot”. Raport final scurt în română: ce funcționează pe operator, commituri/probe/review, ce s-a șters/păstrat, spațiu măsurat, backup/rollback/utilizare, limite/blocker și verdict T1/T2. Încheie în stil Ponytail: ce ai omis/neexecutat și riscul rămas.
