# Omnis — plan de implementare

**Plan propus · 25 septembrie 2026 · local-first, construit incremental**

Direcția de produs și recomandările despre skills au fost acceptate în discuție. Acest document propune ordinea concretă de implementare, stackul și criteriile de acceptare; nu afirmă că aplicația există deja și nu autorizează scanarea unei ținte. Toate etapele de mai jos sunt **neîncepute** la redactare.

## 1. Recomandarea: UI devreme, integrare reală devreme

**Da, începem cu partea web. Nu construim însă tot frontendul și abia apoi backendul.** Construim scheletul vizual și primul flux persistent, în paralel cu verificarea riscurilor Hermes. Apoi dezvoltăm felii verticale: fiecare adaugă UI, date, execuție și teste pentru un comportament complet.

Prima demonstrație utilă nu este un dashboard plin de numere. Este: **creezi un engagement → îl regăsești după refresh → pornești un task limitat → un copil Hermes încarcă un skill → cere o acțiune autorizată → rezultatul și dovada apar în UI → poți opri execuția**. Prima țintă este exclusiv un fixture local controlat.

Aceasta este o felie de integrare, nu întregul MVP. MVP-ul final păstrează reconul HTTP/browser/JS, identitățile opționale, remaparea post-login, workeri pe ipoteze, validator separat, findings confirmate și raportare.

**Evităm două extreme:** o machetă frumoasă fără motor funcțional și luni de infrastructură invizibilă înainte să existe ceva utilizabil. Nu amânăm testele, oprirea sau politica de scope până la final.

## 2. Baza de lucru și deciziile

### Ce păstrăm

- Web local pentru un operator, laboratoare/aplicații proprii de test, autorizate explicit.
- OpenRouter și ChatGPT/Codex; credențialele AI rămân administrate de Hermes.
- Identități de țintă opționale, separate de credențialele AI; autentificare simplă și browser asistat pentru fluxuri complexe.
- Efecte limitate în politica aprobată; aprobări specifice pentru modificări și operații mai intruzive.
- Brain și copii Hermes prin delegare nativă, fără rescrierea frameworkului de agenți.
- Skills native Hermes pentru metodologie; adaptoare de tooluri reutilizabile; autoritate verificată de Omnis.
- Hartă, taskuri, dovezi, coverage și raport persistate de Omnis, nu ascunse în conversații.
- Chains avansate, SaaS, colaborare multi-operator și SSO/MFA autonom rămân post-MVP.

### Alegeri tehnice propuse în acest plan

| Alegere | Recomandare | Motiv / limită |
|---|---|---|
| Frontend | React + TypeScript + Vite; componente accesibile, stiluri/tokenuri comune | Aplicație de operare, fără nevoie inițială de SSR sau motor de site public |
| Backend | Python + FastAPI + Pydantic; monolit modular | Contracte explicite și integrare cu ecosistemul Python; nu importăm întreg Hermes în API |
| Date | PostgreSQL + SQLAlchemy + Alembic | Tranzacții, migrații, taskuri și evenimente concurente; o singură bază canonică Omnis |
| Dovezi | Fișiere locale cu metadate și hash în DB | Stocarea brută separată de vizualizarea redactată; fără serviciu S3 inițial |
| UI live | SSE de la Omnis; comenzi prin API Omnis | Streamul UI vine din evenimente durabile, nu direct din pipe-ul Hermes |
| Runtime | Hermes fixat la versiunea auditată, proces separat, mediu Omnis dedicat | JSON-RPC stdio pentru control; REST privat pentru Settings |
| Execuție țintă | Broker + executori izolați, fără ieșire directă alternativă | HTTP, browser și scanere trebuie să respecte aceeași politică |
| Dezvoltare locală | Compose pentru DB/laborator/executori; procese web/API de dezvoltare separate | Lansare documentată și oprire completă; fără Kubernetes/Redis/Neo4j inițial |
| Teste | pytest, teste UI cu Vitest/Testing Library, E2E cu Playwright | Unitare, integrare și scenarii reale de browser, cu RED → GREEN pentru comportamente noi |

Nu sunt încă instalate aceste componente. Versiunile concrete și lockfile-urile se fixează în P0 după verificarea compatibilității. Nu alegem automat „latest” la fiecare pornire.

**Limite inițiale propuse:** un engagement activ; prima demonstrație cu un copil, apoi maximum doi copii concurenți; același provider/model pentru Brain și copii. Nu sunt estimări de performanță. Limitele se măresc numai după teste de atribuire, bugete și oprire.

**Starea repo-ului verificată:** proiectul conține documentație, nu o aplicație implementată. Propunerea de integrare este [documentul de bază](Omnis_Hermes_Local_MVP_Integration_Proposal.md). Planul de față îi actualizează ordinea de livrare și adaugă catalogul Skills; nu rescrie auditul istoric.

Contractele au fost auditate pe Hermes `0.21.5`, commit `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, reverificat la redactare. Indexul oficial și paginile Skills/Programmatic Integration au fost reconsultate.[1] Sistemul de skills încarcă metodologie la cerere,[2] iar JSON-RPC este o interfață de integrare pentru hosturi proprii.[3] **Fezabilitatea statică nu ține loc de probă runtime.**

## 3. Ce proiectăm în interfață de la început

Definim navigarea întregului produs, dar implementăm comportamente reale progresiv:

| Zonă | Ecrane și date | Prima livrare funcțională |
|---|---|---|
| Engagements | Listă, creare, scope/excluderi, identități, reguli, bugete | P1: creare/editare și persistență; secretele și execuția vin ulterior |
| Overview | Stare, preflight, evenimente, taskuri, aprobări, Stop | P3: evenimente și control pentru prima acțiune reală |
| Target map | Arbore + tabel; inspector de operație, parametri, surse, dovezi | P3: o observație; P5: reconul complet definit pentru MVP |
| Investigations | Ipoteză, worker, skill/revizie, verdict, blocaj | P6: investigație și validare |
| Findings | Confirmate implicit; dovezi și limite | P6: primele clase demonstrate |
| Reports | Snapshot, constatări, coverage, identități și limite | P6: export minimal; P8: raport complet de engagement |
| Settings / Providers | Stări distincte de configurare, autentificare și inferență | P2: minim pentru proba live; P4: fluxuri complete pentru ambii provideri |
| Settings / Skills | Catalog, detaliu, fișiere, readiness, versiuni și drafturi | P2: un pachet real; P4: administrare și publicare controlată |
| Settings / Runtime | Compatibilitate Hermes, inventar tooluri, executori disponibili | P2–P4 |

**Reguli pentru stări:** loading, empty, error, unavailable și not implemented se desenează explicit. „Necunoscut” nu se afișează ca zero. „Configurat” nu se afișează ca „testat”. Un buton Start rămâne blocat cu motiv până când preflightul real trece.

Datele sintetice sunt permise numai în Storybook/teste sau într-un mod vizibil **DEMO**, separat de baza reală, cu acțiuni de țintă dezactivate. Nu devin dovezi de integrare și nu umplu automat dashboardul real.

Pentru aplicație, direcția vizuală propusă este o **consolă de operare**: navigare laterală, tabele lizibile, tree și inspector, statusuri explicite, acces rapid la Stop. Nu un landing page cu carduri decorative și procente fără sursă.

## 4. Etape și dependențe

```text
P0 — fundație, contracte și scenarii de acceptare
 ├─ P1 — schelet web + engagement persistent
 └─ P2 — probe Hermes + un skill + corelare copil/task
          P1 + P2
             ↓
P3 — prima felie reală, broker și fixture local
             ↓
P4 — Settings complet: provideri, Skills și tool readiness
             ↓
P5 — recon HTTP/browser/JS + autentificare + hartă vie
             ↓
P6 — Brain, investigații, validator și primele clase
             ↓
P7 — bucle incrementale, concurență și recuperare
             ↓
P8 — evaluare integrată, raport și livrare locală
```

P1 și P2 pot avansa în paralel după P0. După stabilizarea contractelor, designul UI și autorarea drafturilor de skills pot continua în paralel cu backendul. Testele de integrare pentru un executor, o identitate sau o familie nu sar însă peste poarta lor de siguranță.

### P0 — fundație și contracte minime

**Construim:** structura repo-ului, configurarea dev, migrațiile, testele de bază și contractele primului flux. Separăm modulele engagement, runtime, skills, actions, evidence și events, fără infrastructură de microservicii.

- API/DTO pentru engagement și revizia scope-ului, task/attempt și eveniment cu cursor.
- Scheme de erori, readiness și rezultat; stări de stop/efect incert comune UI–API–worker.
- OpenAPI și tipuri frontend generate/verificate din contractul backend, nu două scheme scrise independent.
- Threat model scurt: browser operator, țintă ostilă, model, skills, executori, provider, control plane.
- `.gitignore` pentru secrete, runtime homes, cookie jars, DB, dumps și dovezi; fixture-urile sanitizate au locație separată.
- CI local/repo fără scanări, fără chei și fără apeluri LLM implicite.

**Poarta:** checkout curat poate rula comenzile documentate de test/build; migrațiile se aplică într-o DB de test; datele runtime nu sunt urmărite de Git. P0 nu pretinde că motorul Hermes este deja integrat.

### P1 — web utilizabil, cu date reale

**Construim:** shellul vizual, navigarea, lista engagementurilor și formularul scope/reguli/bugete. Salvarea, editarea și validarea se fac în API + DB. Ecranele viitoare au empty/unavailable states, nu rezultate simulate.

**Demonstrație:** creezi și editezi engagementul, închizi browserul/repornești API-ul și datele persistă. O excluziune invalidă produce o eroare utilă. Un engagement incomplet nu poate porni.

**Poarta:** E2E pentru create/edit/reload și erori; teste unitare pentru validare; origin/host checks și protecția operațiilor locale împotriva requesturilor cross-origin neautorizate. Loopback nu este considerat autentificare suficientă. Nu capturăm încă secrete de țintă într-un formular fără backend securizat.

### P2 — eliminăm riscurile Hermes înainte de a extinde UI-ul

**Construim:** supervisor privat, adaptor JSON-RPC, adaptor REST minim pentru provider și clientul pluginului. Nu schimbăm profilul Hermes personal. Alegem un `HERMES_HOME` Omnis și un mediu permis explicit, fără moștenire accidentală de credențiale sau MCP/toolsets personale.

Probe separate, cu verdict `VALIDATED`, `PARTIAL` sau `INVALIDATED` și output real sanitizat:

| Probă | Dat fiind / când | Rezultat necesar |
|---|---|---|
| Runtime și protocol | Mediu dedicat, când pornește hostul | Readiness, request/response și server→client requests gestionate; timeout/EOF tratate |
| Provider și izolare | Un provider configurat explicit, când cerem inferență | Starea și modelul efectiv sunt cunoscute; fără fallback personal sau provider nepermis |
| Delegare + skill | Brainul pregătește un task, apoi deleagă | Copil real, context proaspăt, încărcare a pachetului fixat, rezultat structurat și revenire la Brain |
| Autoritatea copilului | Un copil apelează pluginul cu referințe corecte sau falsificate | Backendul leagă sesiunea reală de task; accesul fără asociere și cross-task sunt refuzate |
| Controlul vieții | Stop, răspuns RPC pierdut ori finalizare detached | Fără retry orb al promptului, fără dublu wake, fără continuare nepermisă după stop |

În P2, uneltele de probă lucrează pe fixture-uri inerte/date locale și **nu contactează ținte**. Verificăm inventarul efectiv al Brainului și copilului, nu numai configurația intenționată. Testăm că un skill lipsă, dezactivat sau cu versiune nepotrivită produce eroare, nu o pretinsă încărcare reușită.

**Poarta:** cel puțin o execuție LLM reală cu acord și buget explicit; probele fără provider pot trece separat, dar nu justifică eticheta „Hermes live validat”. Dacă asocierea sigură task–copil nu funcționează, P3 rămâne blocat: evaluăm o extensie/plugin sau un patch minimal documentat, nu înlocuim tacit delegarea cu workeri falși.

### P3 — prima felie completă, cu o acțiune reală

**Construim:** brokerul minim HTTP, atribuirea acțiunilor, politica scope/identitate/buget, captură evidence, evenimente durabile și inspector UI. Ținta este un fixture propriu în rețea izolată, cu o observație HTTP deterministă; nu o aplicație aleasă automat din rețeaua utilizatorului.

Fluxul: **Start → preflight → Brain → copil + skill → plugin → broker → fixture → evidence → DB/event → hartă și rezultat în UI**. Nu cerem încă detectarea unei vulnerabilități pentru a dovedi această legătură.

**Poarta:**

- O cerere reală admisă produce dovadă și metadate atribuibile taskului/identității; aceeași dovadă este inspectabilă după refresh.
- Cereri în afara scope-ului, redirecturi interzise și identități nepermise sunt refuzate înaintea efectului.
- Inventarul și izolarea nu permit ocolirea brokerului prin terminal, cod, MCP sau trafic direct. Rețeaua modelului/providerului este separată de traseul către ținte și nu oferă acces la control plane.
- UI se reconectează la jurnalul Omnis fără dublarea numărătorilor.
- Stop revocă admiterea acțiunilor noi, cere întreruperea runtime-ului și verifică executorii; requesturile deja expediate rămân contabilizate.
- Un crash după expediere produce `UNKNOWN/NEEDS_RECONCILIATION`, nu retrimitere automată.

Dacă un transport nu poate fi observat și restricționat, nu îl activăm. Browserul și scanerele primesc ulterior aceeași obligație; trecerea probei HTTP nu le certifică implicit.

### P4 — Settings complet și catalog Skills real

**Construim:** OpenRouter salvare/test/ștergere; Codex device OAuth start/poll/cancel/logout; model selection; readback după mutații; readiness distinct de existența credentialului. Integrarea minimă P2 se extinde, nu se rescrie.

**Skills:** listă/căutare, categorii, enabled/disabled, detaliu `SKILL.md`, arbore de fișiere, versiune, sursă, dependențe și status de evaluare. Reutilizăm contractele Hermes deja inspectate pentru list/toggle/create/read/update `SKILL.md`; administrarea întregului pachet și guvernanța versiunilor sunt funcții Omnis.

Pachetele sunt versionate în repo. UI creează/modifică un **draft**, arată diff-ul și validează schema și referințele. Publicarea explicită creează o versiune imuabilă pentru rulări viitoare. Read-only în worker, fără acces generic la filesystem și fără instalări arbitrare din URL în MVP.

**Poarta:** fluxurile reale ale ambilor provideri, inclusiv erori/expirare/cancel/logout, au rezultate înregistrate fără secrete; un task păstrează vechea versiune de skill după publicarea uneia noi; un task nou primește versiunea publicată; fișierele din afara pachetului nu pot fi citite/scrise prin editor; lipsa unei unelte produce `UNAVAILABLE`.

Dacă un cont Codex eligibil sau accesul la OpenRouter lipsește, marcăm verificarea live respectivă **BLOCKED**, nu trecută pe baza mockurilor. Cheile/codurile se introduc numai prin fluxuri securizate, nu în chat, prompturi sau loguri. Nu activăm un provider ori un skill doar pentru că apare în catalog.

### P5 — recon util, autentificare și hartă vie

**Construim incremental:** HTTP crawl, formulare și parametri, robots/sitemap, headere, inventar/analiză statică JS, browser pentru SPA, descoperire bounded de directoare. Fiecare observație are sursă și diferențiază `inferred` de `observed`.

Adăugăm identități anonime și autentificate, referințe de secrete, cookie jars/browser contexts separate, verificarea pozitivă a loginului și `auth_epoch`. Loginul asistat se face în browserul engagementului, nu în browserul personal. IdP/CDN aprobate ca dependențe funcționale nu devin ținte autorizate pentru testare.

**Ordine a toolurilor:** HTTP și browser controlate, apoi adaptor Katana dacă aduce descoperire utilă. Nuclei intră ulterior numai cu template-uri selectate și verificate. Sqlmap nu este o dependență a primului MVP demonstrabil; devine executabil numai odată cu validarea capabilității SQLi și a politicii lui. Numele toolului într-un skill nu creează suport.

**Poarta:** fixture SPA cu rută/API disponibilă numai după login; anonimul nu primește cookies de la altă identitate; după login se adaugă suprafețe, fără rescanare globală inutilă. Expirarea produce `AUTH_BLOCKED/INCONCLUSIVE`, nu rezultat negativ. Redirecturi, DNS/IPv6, subresurse, WebSocket/service workers dacă sunt suportate și canale alternative nu depășesc politica; orice canal necontrolat este dezactivat. JS/HTML/SVG din evidence nu execută în Omnis.

### P6 — investigații, validator și primele capabilități demonstrate

**Construim:** taskuri înguste cu precondiții și ipoteză; Brain care folosește harta și catalogul; workeri Hermes; copil nou pentru validare; serviciu de verdict care verifică dovezile cerute. Facem întâi o familie cap-coadă, apoi următoarea, nu toate simultan.

**Ordine propusă pentru catalogul executabil inițial:**

1. Controlul accesului la obiecte, cu etichete IDOR/BOLA și identități/ownership cunoscute.
2. XSS reflectat, cu dovadă de execuție în browser izolat și control inert.
3. Traversal read-only numai către un fișier-canary explicit al laboratorului.

Pentru fiecare: fixture vulnerabil, fixture remediat, procedură de investigație, procedură de validare, controale și teste de regresie. Separăm cazurile folosite la dezvoltare de variantele de evaluare. Validatorul primește precondiții și evidence, nu verdictul investigatorului drept adevăr.

**Poarta:** `CONFIRMED` cere demonstrație verificabilă; controlul sigur nu este promovat; timeoutul/lipsa identității/bugetul consumat devin `INCONCLUSIVE`; rezultat LLM/schema runtime nu poate seta direct un finding confirmat. Exportul HTML/JSON minimal citează dovezile existente. Detectăm și ratări pe fixture-ul vulnerabil, nu doar false positives.

### P7 — bucle, concurență și recuperare

**Construim:** inbox durabil pentru delte, deduplicare, reprioritizare, task dependencies, checkpointuri, pause/resume și reconciliere. Completarea nativă a delegării și evenimentul de domeniu nu produc două continuări ale aceluiași lucru. Extindem testele P2/P3, nu introducem abia aici Stop.

**Demonstrații:** loginul deschide o suprafață nouă; un worker raportează o ipoteză pentru altă clasă; Brainul programează un task separat; doi copii nu pot folosi identitățile sau aprobările celuilalt; oprirea în timpul unei aprobări sau al unui wake este respectată.

**Poarta:** crashuri de API, Hermes, executor și reconectare browser; nicio reluare oarbă a efectelor incerte; metrica de coverage este aceeași în DB, UI și raport pentru același snapshot. Un cost AI necunoscut nu este zero, iar un cost estimat post-factum nu este vândut ca hard cap financiar. Limitele de durată/trafic/concurență sunt impuse tehnic; un hard cap AI cere control înaintea apelului ori limită la provider.

### P8 — evaluare integrată și livrare locală

**Construim:** raport complet din snapshot, export HTML/JSON, vizualizare imprimabilă, documentație de pornire/oprire, migrații, retenție/export/ștergere evidence, backup/restore și compatibilitate fixată. Nu schimbăm runtime-ul în mod automat sub un engagement activ.

**Poarta de MVP:** flux complet fără editare manuală a DB; toate porțile anterioare demonstrate; suita de scope și izolarea fără încălcări; niciun control sigur din suita obligatorie promovat ca finding; ratările, blocajele și limitele consemnate. Raportul arată snapshotul, identitățile, skill/tool versions, testele efectuate și neefectuate. Rezultatele pe laborator nu sunt prezentate ca precizie garantată pe orice aplicație.

## 5. Skills ca parte a produsului, nu ca listă de prompturi

**Skill = metodologie. Tool = operație executabilă. Politica engagementului = permisiune.** Folosim formatul nativ Hermes și încărcare progresivă.[2] Harta metodologiei trăiește în skill; harta țintei și dovezile trăiesc în DB Omnis.

Structură propusă pentru un pachet, încă necreată:

```text
skills/xss-reflected/
  SKILL.md
  references/methodology.md
  references/validation.md
  references/false-positives.md
  references/tool-usage.md
  templates/result.schema.json
  scripts/analyze_observations.py
  omnis.yaml
```

`omnis.yaml` este un manifest **propriu Omnis**, nu un contract Hermes existent. Definește ID, versiune, clase/tags, intrări/ieșiri, dependențe, compatibilitate și referința evaluării. Nu acordă singur drepturi. Scripturile incluse se verifică și rulează în mediu controlat; tool adapters comune nu se duplică în fiecare skill.

Conținutul standard: când se aplică, când nu, precondiții, arbore de decizie, unelte și limite, dovada necesară, control negativ, criterii de oprire, format de rezultat și trimiteri către referințe. Agentul poate propune experimente noi justificate, dar schimbarea ipotezei/impactului/identității trece prin task/politică, nu prin rescrierea skill-ului.

### Catalog inițial și etichete sincere

| Grup | Pachete/metodologii propuse | Statut de implementare urmărit |
|---|---|---|
| Recon | `web-mapping`, `js-analysis`, `api-schema-analysis` | Active progresiv în P3/P5, după testarea propriilor intrări/ieșiri |
| Control de acces | `object-authorization`, tags IDOR/BOLA | Familie executabilă și evaluată în P6; nu două scanări duplicate |
| XSS | `xss-reflected`, `xss-stored`, `xss-dom` | Reflected în catalogul P6; stored/DOM drafturi până la evaluare și politica efectelor |
| Traversal | `path-traversal-canary` | Familie P6, restrânsă la laborator/canary |
| Extindere | `authentication-assessment`, `clickjacking`, `sqli-assessment` | Drafturi metodologice; promovare separată, nu capabilități declarate doar din nume |

Nu creăm zeci de fișiere goale pentru a umple UI-ul. Primele pachete trebuie să fie complete și testabile. O metodologie disponibilă pentru consultare nu intră automat în numitorul testelor executabile.

### Stări independente în Settings

- **Lifecycle:** draft → reviewed → published → retired.
- **Disponibilitate:** instalat/activat și dependențe prezente/absente.
- **Aplicabilitate:** context suficient/insuficient; permis/interzis pentru engagement.
- **Validare:** methodology-only sau benchmark-validated, cu domeniul exact, revizie și rezultat.

La pornirea taskului fixăm conținutul întregului pachet, referințele și versiunile toolurilor/template-urilor. Dezactivarea ascunde/blochează utilizările noi; oprirea taskurilor active este o acțiune explicită de revocare în broker. Nu pretindem că instrucțiunile deja citite pot fi „șterse” din agent.

Pachetele publicate sunt read-only pentru runtime. Scopul efectiv al catalogului și regulile de precedență sunt verificate pentru a evita shadowing cu skills personale/project-local. Dezactivăm mecanismele necerute de modificare/execuție la încărcare. Agenții pot propune îmbunătățiri redactate, fără secrete sau date de țintă, numai ca draft pentru review și reevaluare.

## 6. Contracte interne care împiedică rescrierea UI-ului

Definim prima variantă în P0; completăm incremental câmpurile pe măsură ce le executăm. Nu proiectăm anticipat întregul pentest ca o schemă rigidă.

| Contract Omnis propus | Câmpuri / invariantă principală |
|---|---|
| Engagement snapshot | Scope revision, reguli, identități referite, bugete, model, catalog publicat; snapshot imuabil al unei încercări |
| Task / Attempt | Ipoteză, rol, suprafață, precondiții, skill revision, auth epoch, sesiune reală asociată, buget și stare |
| Action request | Task/attempt, operație tipizată, țintă/identitate, scope revision, approval exact dacă este necesar; task ID nu este credential |
| Observation | Operație/parametri/sursă, `inferred`/`observed`, identitate/stare și evidence refs |
| Evidence | Referință imutabilă, hash, captură, timestamp, proveniență, acces și versiune redactată |
| Candidate / Validation | Ipoteză, dovadă, control, reproducere și verdict distinct de succesul runtime-ului |
| Domain event | ID, cursor per engagement, tip, entitate/revizie, cauzalitate, payload redactat; scris atomic cu starea |
| Coverage snapshot | Mulțime cunoscută, aplicabilitate, numărător/numitor explicit, necunoscute/blocate separat |

Baza Omnis este sursa canonică. Streamul și chatul sunt proiecții. În caz de eveniment repetat, UI nu incrementează orbește un counter. La pierderea legăturii cu Hermes, brokerul și DB conservă efectele cunoscute; reconcilierile se fac din surse reale, nu din rezumate presupuse.

## 7. Primul lot de lucru, în ordine de commituri

Lotul inițial trebuie să livreze o bază web utilizabilă și răspunsuri la riscurile de integrare, nu toate ecranele finale. Fiecare rând poate necesita mai multe commituri mici; nu comprimăm artificial întreaga etapă într-un singur commit.

| Ticket propus | Rezultat concret | Dependență / verificare |
|---|---|---|
| B01 — foundation | Repo layout, comenzi dev/test, ignore rules, versiuni, threat model minim | P0; build/test de bază reproductibile |
| B02 — engagement persistence | Migrație + API create/read/edit + validare scope/config | B01; test RED → GREEN, DB reală de test, restart |
| B03 — web shell | Navigare, layout, stări goale și erori, componente comune | B01; test de randare/accesibilitate, build |
| B04 — first user flow | Formular conectat la API, listă și inspector engagement | B02+B03; Playwright create/edit/reload, Start blocat justificat |
| B05 — private Hermes host | Supervisor/adaptor RPC și management minimal, mediu dedicat | B01; handshake real, request invers, EOF și cleanup; fără ținte |
| B06 — skill and child binding | Un pachet real + copil nativ + identitate de task verificată | B05; încărcare demonstrată, cross-task refuzat, rezultat și wake |
| B07 — controlled action slice | Broker HTTP, fixture izolat, evidence/events/Stop | B02+B06 și poarta de izolare P3; efect real și refuz verificat |
| B08 — live proof in UI | Acțiunea B07 vizibilă, inspector evidence, reconnect și Stop | B04+B07; E2E fără metrici simulate |

**Primul punct de feedback vizual:** B04. **Primul punct de feedback funcțional cap-coadă:** B08. Nu trebuie să așteptăm finalul planului pentru a schimba interfața.

Frontul web și integrarea Hermes pot fi lucrate separat după B01, pe contracte comune și fișiere/worktree-uri distincte. Un singur responsabil integrează contractele și verifică fluxul. Nu lansăm agenți de implementare care modifică simultan aceleași fișiere sau propriul profil Hermes al utilizatorului.

## 8. Strategia de testare și dovezile de finalizare

| Nivel | Ce verifică | Ce nu dovedește |
|---|---|---|
| Unitare | Scope parsing, stări, bugete, validări, normalizare, verdict, redactare | Integrarea cu procese/browser/rețea |
| Contract | Schema RPC/REST și maparea stărilor; pinul Hermes; tipurile UI | Autentificare reală sau eficacitatea modelului |
| Integrare fără LLM | DB/migrații, evenimente, broker, fixture, izolarea, secrete de test | Delegare reală sau inferență |
| Hermes live | Provider/model efectiv, skill încărcat, copil, control și continuări | Descoperirea unei vulnerabilități reale |
| E2E browser | Fluxul operatorului, reconnect, approvals, evidence, accesibilitate | Calitatea catalogului de verificări în afara fixture-urilor |
| Evaluare capabilități | Vulnerabil vs remediat, miss/FP, replay, timp/trafic/cost și intervenții | Acoperire completă ori precizie universală |

Pentru comportamente noi: test care eșuează pentru motivul corect → implementare minimă → test trecut → refactor. Fixtures/fakes sunt acceptabile ca instrumente de test marcate, nu ca înlocuitor pentru proba live. CI implicit nu folosește conturile operatorului și nu consumă buget LLM. Testele live sunt opt-in, cu țintă/cont/buget explicite.

Fiecare livrare consemnează: ce funcționează, comanda/scenariul executat, rezultat real, versiuni, limitări și ce rămâne blocat. Readback după Settings sau alte mutații externe; outputul reușit al unui apel nu este suficient pentru a anunța salvarea.

**Git:** commituri mici și coerente inclusiv pentru configurație și documentație; mesaje cu decizie/motiv/verificare. Se stage-uiesc numai fișierele intenționate. Nu versionăm credentiale, OAuth grants, sesiuni, date reale de țintă ori loguri brute. Pushul și efectul lui se verifică înainte de a fi raportate.

## 9. Riscuri, opriri și alegeri de închis

| Risc | Cum îl tratăm înainte să investim prea mult |
|---|---|
| Contractele Hermes interne se schimbă | Pin exact; teste de contract; upgrade separat, nu update automat |
| Taskul nu poate fi legat sigur de copil | Probă B06 obligatorie; fără permisiune de țintă până la rezolvare |
| Un tool ocolește brokerul | Egress impus + inventar efectiv + test de bypass; transportul rămâne dezactivat dacă nu poate fi controlat |
| Browser/auth este mai complex decât HTTP | Fixture post-auth și expirare în P5; fără a amesteca cookie jars sau a echivala browserul cu un cookie copiat |
| Skill-urile devin conținut necontrolat | Pachete imutabile, draft/review, pin complet, teste per capabilitate |
| OAuth/modelul nu este disponibil contului | Stare explicită și probă live cu acord; fără fallback ascuns sau succes simulat |
| Costul produsului crește prin catalog prea larg | Nu reducem fluxul MVP; limităm familiile executabile demonstrate și promovăm altele separat |

Înaintea primelor probe live trebuie închise: acceptarea stackului propus, furnizorul/contul pentru proba inițială și bugetul permis, politica datelor trimise modelelor și mediul autorizat al laboratorului. Recomand fixtures proprii, resetabile, fără date sensibile; o aplicație-laborator suplimentară vine pentru evaluare, nu înlocuiește controalele deterministe.

Nu sunt blocante pentru P0/P1: alegerea tuturor viitoarelor skill-uri, toate modelele posibile, chains sau un calendar SaaS. Nu inventăm estimări în zile înainte de P2/P3; după probe putem estima pe rezultate și blocaje reale.

## 10. Definiția de final și limita acestei livrări

**MVP înseamnă:** un operator pornește un engagement autorizat din web; reconul produce hartă inspectabilă; Brainul folosește skills și deleagă investigații; validatorul produce verdicte cu dovezi; loginul și observațiile noi pot redeschide analiza; Stop/recuperarea funcționează; raportul reflectă exact snapshotul cunoscut și limitele lui.

**Nu înseamnă:** catalog nelimitat, zero FP/FN, scanarea automată a oricărei ținte, autonomie fără approvals sau un dashboard demonstrativ prezentat ca pentest real.

Livrarea de față este planul, în Markdown și HTML. Nu au fost instalate stackul, pornite servicii Hermes, conectate conturi sau executate scanări pentru redactarea lui. Verificarea documentului și randării HTML este separată de testele viitoarei aplicații.

**Recomandarea de pornire:** B01–B04 pentru prima experiență web reală, cu B05–B06 în paralel; apoi B07–B08 pentru primul traseu complet. Nu toate ecranele înaintea backendului și nu toate integrările înaintea primului ecran.

## Sources

[1] https://hermes-agent.nousresearch.com/docs/llms.txt
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
