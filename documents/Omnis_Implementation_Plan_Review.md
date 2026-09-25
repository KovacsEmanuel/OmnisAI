# Omnis — review critic al planului de implementare

**25 septembrie 2026 · Review pentru decizie, nu revizie aprobată a planului**

## Verdict

**Direcția este bună pentru MVP-ul local convenit. Aș începe fundația, engagementul persistent și probele Hermes, dar nu aș îngheța încă dependențele și criteriile întregului plan.** Riscul principal nu este stackul. Este să demonstrăm târziu utilitatea pentestului, după multă administrare, și să tratăm câteva intenții corecte de securitate drept contracte suficient de precise pentru implementare.

Păstrăm fluxul complet: web → recon HTTP/browser/JS → hartă → ipoteze → copii nativi Hermes cu skills → validare separată → bucle post-auth → raport. Nu reducem MVP-ul la un GET și nu îl extindem acum la SaaS sau pentest general. Prima felie HTTP rămâne o probă de integrare, nu dovada eficacității produsului.

**Recomandarea centrală:** mutăm mai devreme o probă browser/auth și prima familie de vulnerabilități cap-coadă; scoatem editorul complet de Skills și al doilea provider de pe drumul critic al acestei probe, fără să le eliminăm din livrarea finală promisă.

## 1. Baza efectivă a review-ului

Au fost citite planul Markdown și reprezentarea HTML, propunerea de integrare locală și propunerea inițială. Din v7 au fost consultate nota de statut, structura și pasaje relevante, nu întregul document ca specificație obligatorie.

Ancorele locale de mai jos se referă la fișierele de la commitul Omnis `27a1bbfdece25cba96184fba9ef99757daf3e653`:

- **Plan:** `documents/Omnis_Implementation_Plan.md`.
- **Integrare:** `documents/Omnis_Hermes_Local_MVP_Integration_Proposal.md`.
- **Inițial:** `documents/Omnis_Hermes_MVP_Architecture_Proposal.md`.

A fost consultat istoricul sesiunilor relevante din 24–25 septembrie, inclusiv mesajele despre reutilizarea Hermes, graful/matricea de engagement și acceptarea direcției Skills. Unele rezultate istorice sunt ferestre sau rezumate comprimate; nu pretind că am recitit fiecare turn original. Documentele curente și mesajele originale recuperate sunt baza, nu afirmațiile istorice despre alt workspace.

Consecințe pentru acest review:

- Referința v7 nu este o arhitectură impusă. Utilizatorul a precizat explicit acest lucru.
- Direcția curentă este local-first, pentru laboratoare/aplicații proprii autorizate, nu serviciul public pentru echipă imaginat inițial.
- Browserul, reconul JS, post-auth, harta, feedbackul și validatorul sunt în MVP; nu le putem amâna pe toate sub pretextul simplificării.
- Stackul și ordinea concretă sunt propuneri. Repo-ul curent conține documentație, nu aplicația funcțională.
- „Lipsă în planul curent” nu înseamnă neapărat „idee niciodată discutată”. De exemplu, comparația cu baseline și unele elemente de raportare existau mai explicit în propunerea inițială.

Citările publice au un registru cu data accesării și extrase verificabile în [fișierul de surse](Omnis_Implementation_Plan_Review.sources.json). Recomandările și deducțiile review-ului sunt distincte de afirmațiile atribuite furnizorilor.

Documentația Hermes a fost verificată pornind de la indexul oficial. Inspecția statică locală a fost reverificată pe checkoutul curat `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. **Nicio integrare live, inferență, autentificare de provider sau scanare nu a fost executată pentru acest review.** Testele recomandate mai jos sunt viitoare criterii de acceptare, nu rezultate obținute.

## 2. Ce este deja bine și nu trebuie reinventat

1. **UI și integrare progresivă:** P1/P2 în paralel și primul flux persistent evită atât frontendul decorativ, cât și infrastructura fără feedback.
2. **Separarea autorității:** skill = metodologie; tool = execuție; Omnis = permisiune și stare canonică. Modelul nu confirmă singur findingul.
3. **Date probatorii reale:** scope revision, task/attempt, evidence, evenimente durabile și snapshot; SSE/chat nu sunt baza de adevăr.
4. **Scope și Stop devreme:** sunt deja în P2/P3. Ar fi incorect să spunem că planul le-a uitat sau le lasă complet pentru P7.
5. **Validare serioasă:** candidat/confirmat/respins/neconcludent distincte, copil nou, controale sigure, teste vulnerabil/remediat și măsurarea ratărilor.
6. **Ambiție limitată onest:** puține familii executabile, fără „100% din aplicație”, zero FP/FN garantate sau zeci de skills superficiale.
7. **Stack proporționat:** React/TypeScript/Vite, FastAPI și PostgreSQL sunt o alegere rezonabilă pentru această structură. Nu există în materialul analizat un motiv de a introduce microservicii, Redis sau Neo4j înaintea unei nevoi măsurate.

## 3. Ce rezultă concret din documentația publică

Acestea sunt descrieri ale furnizorilor, nu audituri independente ale produselor lor. Nu deducem arhitectura internă completă, precizia sau costul Omnis din ele.

| Sursă | Ce declară documentația | Consecință pentru Omnis |
|---|---|---|
| XBOW Platform | Hartă vie, coordonator, workeri scurți și validatori care verifică reproductibilitatea.[9] | Susține direcția generală a planului; nu justifică mii de agenți sau promisiunea „zero false positives”. |
| XBOW Scope configuration | Separă `Attackable`, `Allow Visit` și `Blocked`; domeniile neincluse sunt blocate.[29] | Dependențele de login/CDN trebuie modelate separat de permisiunea de atac. Principiul există deja în Omnis; trebuie contract și teste. |
| XBOW Asset context | Acceptă precondiții de endpoint, specificații și informații despre structura autorizării.[30] | Contextul aplicației nu poate fi redus la URL, scope și credențiale. |
| XBOW Canary validation | Coordonatorul primește locația și hashul canary-ului, nu valoarea lui în clar; recomandă evitarea scurgerilor prin surse/loguri și rotirea tokenului.[31] | Separarea evaluatorului și a răspunsului așteptat este o condiție pentru probe credibile. Canary-ul nu trebuie să fie în skill sau prompt. |
| XBOW Protecting assets | Descrie conturi dedicate, protejarea endpointurilor și throttling/pauză când sănătatea țintei se degradează.[28] | Rate-limitul fix nu este singurul control de impact; trebuie și reacție la degradare. |
| Aikido Test users | Documentează personas multiple și un eșec concret când agenții partajează tokenuri de refresh rotative.[14] | Concurența autentificată este un risc real de proiectare, nu doar un test de „cookies diferite”. |
| Aikido Code/documentation | Folosește definiții de roluri, restricții, workflowuri și reguli business ca informații de testare.[15] | Pentru BOLA trebuie definit cine ar trebui să poată accesa ce, nu numai cine deține obiectul. |
| Aikido Testing environment | Avertizează că și un preview poate folosi DB/chei de producție și că cleanupul nu este întotdeauna posibil.[16] | „Țintă locală/de test” nu dovedește izolarea efectelor asupra emailului, plăților, webhookurilor sau joburilor serverului. |
| Aikido Coverage | Definește coverage pe endpointuri descoperite și spune explicit că nu este scor de calitate.[21] | Omnis face bine că propune o matrice mai precisă; trebuie să îi protejeze și stările negative de afirmații fără dovezi. |
| Hermes | JSON-RPC este interfață pentru hosturi proprii; delegarea are contexte noi; observer hooks sunt telemetrie, cu căi fail-open.[10][11][12] | Integrarea este plauzibilă, dar autorizarea și completarea taskurilor trebuie demonstrate în Omnis, nu deduse dintr-un callback. |

### Ce NU aș copia de la competitori

- Aikido recomandă, pentru mecanismul său de sesiune partajată, refresh tokens reutilizabile și dezactivarea rotației care invalidează tokenul anterior.[14] **Nu aș transforma asta în cerință Omnis.** Aș serializa refreshul sau aș limita concurența per identitate; dacă o schemă nu este suportată, o declarăm ca atare.
- XBOW publică rate de pornire orientative pentru propriul produs.[28] Nu le transferăm laboratorului nostru. Un default trebuie stabilit conservator pentru fixture și apoi măsurat, nu copiat numeric din marketing/documentație.
- Aikido documentează excepții de acces automat pentru unele resurse statice/platforme de dezvoltare.[6] Nu preluăm asemenea excepții generic: în Omnis pot crea ieșiri necontrolate sau scurgeri.
- Nu preluăm exemple de parole în instrucțiuni ca model de secret handling. Referințele opace și injectarea în executor rămân regula Omnis.
- Nu preluăm afirmația comercială că un validator sau un canary rezolvă orice clasă de vulnerabilitate. Un canary dovedește o observație numai cu proveniență, identitate și regulă de acces corecte.

## 4. Constatări prioritizate

**Severitatea** indică riscul pentru livrare/corectitudine/siguranță, nu severitatea unei vulnerabilități exploatate. „Ridicată înainte de P5” nu înseamnă că P0/P1 trebuie blocate. Fiecare constatare distinge ce există deja de ce trebuie adăugat.

### R01 — P4 este prea mare și prea devreme pe drumul critic

**Medie · problemă de secvențiere · Plan:82–88, 153–163.**

**Există:** P2 validează un provider, copilul și un skill; P4 finalizează ambii provideri și administrarea Skills.

**Gap:** diagrama P3 → P4 → P5 → P6 face prima demonstrație de securitate dependentă de editorul de pachete și eligibilitatea celui de-al doilea cont. Aceasta nu este o dependență tehnică necesară. Riscăm să construim un panou de administrare bun înainte să știm dacă reconul și investigația găsesc ceva util.

**Amendament minim:** P4a = readiness, selecție, catalog read-only și pachete aprobate/pin-uite; P4b = editor, diff, draft/review/publicare și completarea celui de-al doilea provider. P4b merge în paralel cu reconul/primele capabilități, dar rămâne în criteriile MVP-ului final.

**Acceptare:** prima investigație cap-coadă rulează cu un provider validat și skill publicat fără să depindă de editor sau de loginul la celălalt provider. Cel indisponibil rămâne `BLOCKED`, nu „testat”.

### R02 — P2 are un risc recunoscut, dar îi lipsesc câteva probe decisive

**Ridicată · detaliere a unui risc deja identificat · Plan:120–134; Integrare:290–296.**

**Există:** home separat, inventar restrâns, task–copil legat sigur, refuz cross-task și posibilitate de patch minimal dacă pluginul nu ajunge.

**Gap confirmat static:**

- Un env allowlist și alt `HERMES_HOME` nu exclud singure `.env` din checkoutul runtime-ului; există și politici de adoptare a loginurilor externe.
- Handlerul de tool poate primi identitate contextuală de la runtime, separat de argumentele LLM. Dar taskul tehnic Hermes nu este taskul Omnis.
- `subagent_start` nu furnizează de la sine un identificator Omnis imuabil, iar eșecul observerului nu trebuie să autorizeze copilul.
- Compresia poate schimba `agent.session_id`. Un mapping care presupune că ID-ul copilului rămâne neschimbat poate pierde continuitatea sau o poate reconstitui nesigur.

Ancorele exacte și limitele inspecției sunt în §6. Nu am demonstrat aici o scurgere efectivă și nici că este obligatoriu un fork.

**Acceptare B05/B06:** surse simulate de credențiale cu canary, două taskuri cu același goal, copil care falsifică taskul fratelui, observer întârziat/defect și compresie între două apeluri inerte. Primul efect este interzis până la mapping verificat și persistat. Continuitatea după compresie se dovedește prin lineage de încredere sau apelul este refuzat. Nu asociem după textul goalului ori după ordinea presupusă a evenimentelor.

**Simplificare:** o instalare/pachet runtime controlat, fără fișierele personale accesibile, este mai clară decât reutilizarea arbitrară a mediului personal cu multe excepții.

### R03 — Editarea scope-ului activ și oprirea au nevoie de o regulă de autoritate în timp

**Ridicată · insuficient specificat · Plan:112–114, 145–149, 191–195, 254–256; Integrare:458–467.**

**Există:** snapshot imuabil, scope revision, approvals exacte, Stop și interdicția retryului orb.

**Gap:** un task și un approval perfect consistente cu revizia veche nu dovedesc că acțiunea mai este permisă după o restrângere nouă. De asemenea, „zero acțiuni noi pe țintă” și „zero inferențe noi nepermise” sunt proprietăți distincte: brokerul poate opri prima, iar un wake nativ poate încă încerca a doua.

**Amendament minim pentru primul MVP:** scope-ul/risk policy nu se editează în timpul execuției. Modificarea cere oprire verificată și o nouă revizie/încercare. Dacă ulterior permitem restrângeri live, revocăm autoritatea veche înainte de următoarea expediere. Nu avem nevoie din prima de un sistem sofisticat de migrare live a permisiunilor.

**Acceptare:** o cerere în coadă, cu approval vechi, nu este expediată după revocare; Stop în timpul aprobării/finalizării copilului nu permite acțiuni noi. Pierderea control plane-ului duce la expirarea/revocarea lease-ului executorului, nu la execuție nelimitată. Separat măsurăm dacă mai pornesc inferențe, cât durează quiescența și cum se reconciliază rezultatele deja expediate. Nu promitem anularea efectelor deja produse de server.

### R04 — „Acțiune permisă și limitată” nu definește încă efectul necunoscut

**Ridicată · contract operațional incomplet · Plan:24, 138–151, 167–173, 256; Integrare:452–467.**

**Există:** clasificare de risc, aprobări pentru modificări și precizarea că metoda HTTP nu garantează lipsa efectelor.

**Gap:** nu este explicit cine stabilește clasa de efect pentru un endpoint încă necunoscut și ce face browserul cu mutații automate. Un GET, o navigare sau un click poate schimba starea; un server autorizat poate trimite apoi email/plăți/webhookuri în afara rețelei controlate de Omnis.

**Amendament minim:** clase tipizate de efect și proveniența clasificării; `UNKNOWN` nu devine read-only din declarația LLM. Primele fixture-uri declară operațiile permise. Pentru acțiuni necunoscute cu posibil efect, solicităm decizie sau păstrăm suprafața blocată. Preflightul mediului verifică date sintetice și servicii secundare mock/sink, nu numai URL-ul.

Adăugăm un jurnal simplu pentru obiectele de test create, obligații de cleanup și rezultat `cleanup_incomplete`; nu lăsăm agentul să facă ștergeri nelimitate în numele curățării. Adăugăm oprire/throttling la degradare de health și backoff la rate limiting. XBOW descrie monitorizare de health și throttling/pauză, iar Aikido explică limitele cleanupului și riscul stagingului conectat la producție.[28][16]

**Acceptare:** fixture cu GET mutator și mutație automată SPA, plus email/webhook către un sink de test. Sub politică read-only starea nu se schimbă prin operații neaprobate. Un semnal controlat de degradare oprește expedierea conform pragului configurat; un cleanup eșuat apare în raport. Verificăm și starea țintei, nu numai logul brokerului.

### R05 — Prima familie BOLA cere o regulă business explicită, nu numai două conturi

**Ridicată · insuficient specificat · Plan:169, 181–187; Integrare:375, 408.**

**Există:** roluri, ownership, identități separate și avertismentul că HTTP 200 nu dovedește IDOR.

**Gap:** nu există contractul prin care operatorul/fixture-ul declară și versionează accesul așteptat. Un obiect al utilizatorului B poate fi legitim partajat cu A. Modelul nu trebuie să transforme „non-owner” în „neautorizat”.

**Amendament minim:** formular/fișier de context cu `principal/rol/tenant`, obiecte de test, acțiune, acces așteptat `permis/interzis/necunoscut`, sursă și revizie. Pentru catalogul inițial, matricea poate fi mică și introdusă de operator; nu cerem un motor general de politici business.

OWASP WSTG recomandă utilizatori multipli și cere ca obiectul testat să nu fie accesibil conform logicii aplicației.[27] Aikido și XBOW documentează explicit definiții de roluri și context de autorizare.[15][28]

**Acceptare:** caz privat, caz partajat legitim, acces al ownerului și acces cross-tenant; aceeași observație 200 nu produce același verdict în toate cazurile. Lipsa regulii business blochează confirmarea și produce o întrebare/limitare, nu o presupunere.

### R06 — Identități separate nu rezolvă concurența în aceeași identitate

**Ridicată · insuficient specificat și parțial prea târziu · Plan:169–173, 191–195; Integrare:387–391.**

**Există:** cookie jars/browser contexts, login pozitiv, `auth_epoch`, tratarea expirării și recunoașterea diferenței browser–HTTP.

**Gap:** doi workeri care folosesc aceeași identitate pot invalida tokenul de refresh, consuma tokenuri CSRF, altera același obiect de test sau face logout unul altuia. Aikido descrie public exact eșecul tokenului rotativ într-o sesiune partajată.[14]

**Amendament minim:** pentru început serializare per identitate/sesiune și, unde este cazul, per obiect de test; concurență numai pe contexte demonstrat independente. Refreshul are un singur proprietar; generația sesiunii și invalidarea taskurilor dependente se persistă. Nu dezactivăm securitatea țintei ca să evităm proiectarea concurenței.

Pentru replay definim precondițiile, pașii de setup și refacerea tokenurilor volatile. Reproducerea nu înseamnă retrimiterea byte-for-byte a unei cereri cu CSRF expirat. Workflowurile simple necesare autentificării/obținerii obiectelor nu sunt „chains avansate” și nu pot dispărea din MVP.

**Acceptare P5:** refresh rotativ sub două cereri concurente, login expirat între baseline și probă, CSRF consumabil și validator pe obiect resetat. Niciunul nu produce negativ sau finding fals. O variantă de auth nesuportată este raportată explicit și nu blochează reconul anonim.

### R07 — Și rezultatul negativ trebuie să aibă o poartă probatorie

**Ridicată · gap de corectitudine · Plan:185–187, 261; Integrare:446–448.**

**Există:** controale negative, validare strictă a candidaților și separarea blocajelor de rezultate negative.

**Gap:** nu este definită execuția minimă care permite `tested_no_issue`. Un worker care spune „n-am găsit” poate umfla coverage fără să execute verificarea relevantă; validatorul primește în principal candidați pozitivi și nu vede această ratare.

**Amendament minim:** fiecare familie declară ce acțiuni/controale și precondiții justifică negativul pe o celulă exactă a matricei. Schema validă a rezultatului nu înlocuiește evidence. Nu validăm fiecare negativ prin încă un LLM; verificăm determinist completitudinea probelor și audităm ratările pe corpus.

**Acceptare:** un rezultat negativ fără acțiunea necesară sau cu identity/epoch greșit nu crește `tested` coverage; rămâne netestat/neconcludent. O celulă validă înseamnă „această procedură nu a demonstrat problema în acest context”, nu „endpoint sigur”. Coverage nu este scor de calitate, distincție prezentă și în documentația Aikido.[21]

### R08 — Evidence în filesystem și stare în PostgreSQL au două frontiere de commit

**Ridicată înaintea verdictelor · insuficient specificat · Plan:37, 148–149, 199, 258–263.**

**Există:** fișiere locale, hash, metadate DB, eveniment atomic cu starea și recuperarea efectelor incerte.

**Gap:** atomicitatea DB + eveniment nu include automat fișierul de evidence. După crash putem avea referință la bytes inexistenți, fișier incomplet sau artefact orfan. Hashul nu dovedește că proveniența este autentică și nici că artefactul mai există.

**Amendament minim:** protocol staged → finalizat/durabil → disponibil, cu verificare digest și reconciliere; numai artefactele disponibile și complete pentru oracle pot susține verdictul. Stări distincte pentru lipsă/trunchiere/redactare. Limite pentru body, decomprimare, download, browser trace, disk și prompt; nu așteptăm P8 pentru limitele primei capturi.

**Acceptare P3/P6:** crash injectat înainte/după scrierea fișierului și commitul DB, disc plin, body prea mare și fișier lipsă. Niciun caz nu produce `CONFIRMED` pe dovezi absente sau trunchiate incompatibil cu oracle-ul. Raportul vechi rămâne identificabil după retenție/ștergere, dar declară indisponibilitatea probelor; nu promite replay când bytes au fost șterși.

### R09 — Evaluarea este bine intenționată, dar nu închide încă demonstrația utilității

**Ridicată pentru poarta de MVP · lipsă de criterii operaționale · Plan:185–201, 293; Inițial:38, 187.**

**Există:** variante de evaluare separate, fixture vulnerabil/remediat, FP, ratări, replay, timp/cost/intervenții. Comparația cu alternative apărea în propunerea inițială, dar nu are un ticket/poartă explicită în planul curent.

**Gap:** un validator poate trece dacă îi dăm endpointul și ipoteza corecte, în timp ce produsul nu le descoperă niciodată. Nici măsurarea ratărilor fără un prag fixat înaintea rulării nu decide dacă livrarea este acceptabilă.

**Amendament minim:** separăm trei probe:

1. integrare/runtime — ajunge acțiunea corect la fixture;
2. capabilitate — procedura investighează și validează corect cazul indicat;
3. descoperire E2E — pornim fără endpointul vulnerabil sau soluția furnizate și obținem findingul prin recon și planificare.

În evaluarea E2E, evaluatorul păstrează adevărul de referință și canary-urile; agentul nu are acces la soluții, scorer, seed DB sau fixture-source privilegiat. Contextul autorizat din scenariu este explicit; o probă grey-box nu se raportează ca black-box. XBOW documentează separarea valorii canary-ului de informația transmisă coordonatorului.[31]

**Acceptare:** definim înaintea rulării scenariile obligatorii, bugetele și repetările, cazurile sigure și nivelul de detecție cerut. Scenariile pozitive obligatorii trebuie găsite cap-coadă, iar controalele sigure nu trebuie confirmate. Pentru setul mai larg publicăm rezultate per rulare și ratări atribuite etapelor discovery/planificare/test/validare, nu un singur procent agregat. Comparația cu un baseline determinist simplu, la același profil de informație și limite comparabile, măsoară valoarea adăugată; nu pretindem anticipat că Omnis îl depășește.

Nu cer un benchmark gigantic înaintea primului ecran. Cer un corpus mic, separat și un criteriu de trecere stabilit înainte de a vedea scorul.

### R10 — „Recon complet pentru MVP” și graful trebuie transformate în scenarii concrete

**Medie · specificație de produs incompletă · Plan:60, 167–173, 229, 257–261; Integrare:368–393.**

**Există:** crawl, browser SPA, JS static, parametri, inferat/observat, relații, API de interogare a hărții și coverage multidimensională.

**Gap:** expresiile „recon complet” și „Web/API” pot ascunde volume foarte diferite. Nu este clar ce subset de API/protocoale, importuri și workflowuri este efectiv livrat. Nici harta navigabilă nu garantează că Brainul primește context suficient și proaspăt fără un prompt enorm.

**Amendament minim:** o matrice de suport: HTTP(S), formulare și REST/JSON, SPA ales pentru probă, import OpenAPI local/revizionat și comportamentul pentru GraphQL/WebSocket/gRPC/OAST. Ce nu implementăm apare `unsupported/not_tested`; observarea traficului nu devine certificare de testare a protocolului. Importurile nu rezolvă automat `$ref` externe și nu lărgesc scope-ul.

În contextul aplicației includem seed URLs, obiective și workflowuri prioritare. Pachetul pentru Brain are snapshot/cursor, vecinătate relevantă, contradicții, precondiții lipsă și buget; la trunchiere lipsurile sunt explicite. UI poate rămâne tree + tabel + inspector de relații; nu avem nevoie acum de un graf animat sau de o bază graph separată. Matricea `suprafață × identitate × familie` trebuie însă să fie inspectabilă, cu trecere din celulă la test și evidence, nu numai un procent în Overview.

**Acceptare:** rută fără link public, descoperită din JS ori specificație; API post-login; soft-404; parametri în body; paginare și buget de context mic; același endpoint sub identități distincte. Un indiciu nou și o contradicție schimbă taskul următor justificat, fără rerulare globală. O familie nesuportată apare ca limită, nu ca test negativ.

**Probă anticipată:** un browser autentificat restrâns trebuie încercat imediat după HTTP, nu după întreg P4. Playwright documentează cereri care pot fi invizibile rutării în prezența Service Workers; simpla folosire a `page.route()` nu este dovada confinării.[18]

### R11 — Politica datelor trebuie verificată pe toate copiile, nu numai în Omnis DB

**Ridicată înaintea datelor de țintă către provider · detaliere și secvențiere · Plan:105, 120, 199, 246, 313; Integrare:29, 257–259.**

**Există:** secrete separate, redactare, politică înaintea probelor live, fără date runtime în Git și retenție la P8.

**Gap:** evidența poate exista și în history/compaction, logul copilului, dumpul unei erori provider, cache browser, screenshot, export și backup. Un profil dedicat produsului, reutilizat între engagementuri, nu este automat o graniță de memorie între ținte.

**Amendament minim:** inventar de date și de procesoare, cu minimizarea fragmentelor trimise modelelor, tratarea PII/business data și acces la raw evidence separat de preview. Nu confundăm redactarea cheilor cunoscute cu filtrarea tuturor datelor sensibile. Memoria globală/auto-learningul nu primesc date de engagement; read APIs validează și evidence refs/snapshot/identitate, nu numai target requests.

Hermes documentează shared metrics opt-in și distinge exporturile suplimentare ale pluginurilor de această cale.[23] Nu există bază pentru acuzația că trimite implicit tot traficul; cerința este să verificăm configurația și traseele efective ale runtime-ului Omnis.

**Acceptare:** un secret și un marker sensibil sintetic trec prin request/response, eroare provider, compresie, export și restart. Inventariem ce rămâne unde și ce părăsește sistemul; engagementul B nu poate recupera datele lui A. HTML/SVG și exporturile nu execută scripturi și nu încarcă resurse ostile în browserul operatorului. Ștergerea urmărește și derivatele, cu limitele backupurilor declarate.

### R12 — Raportul trebuie să închidă și remedierea, nu doar investigația

**Medie · sub-specificat în backlog · Plan:187, 199–201, 259; Integrare:381; Inițial:129–130.**

**Există:** raport din findings confirmate, dovezi, snapshot, identități și teste neefectuate. Retestul și impactul sunt menționate în documentele de bază.

**Gap:** nu sunt livrabile explicite pentru deduplicare, severitate justificată, remediere și starea după fix. Un raport cu mai multe simptome ale aceleiași cauze sau fără condițiile reproducerii este greu de folosit, chiar dacă dovada este reală.

**Amendament minim:** finding stabil + occurrences, CWE, impact demonstrat versus potențial, precondiții, severitate motivată distinct de încredere, remediere propusă și pași de retest. Dacă există CVSS numeric, vectorul trebuie păstrat și calculat determinist. Operatorul poate adnota/contesta verdictul cu audit, fără să rescrie evidence.

**Acceptare:** fixture vulnerabil → finding → fixture remediat → retest țintit cu probe noi și raport nou; raportul anterior rămâne neschimbat. Reproducerea nereușită din cauza expirării auth este `INCONCLUSIVE`, nu `FIXED`. Fără sistem de ticketing sau retest continuu obligatoriu acum. XBOW documentează separat retestul și versionarea rapoartelor după remediere.[32]

## 5. Cum aș modifica ordinea fără să schimb obiectivul MVP

| Moment | Livrabil | Ce demonstrează |
|---|---|---|
| P0 restrâns | Contractele primului flux, threat model, matrice minimă de autorizare/efecte și scenarii de acceptare | Știm ce testăm și ce refuzăm; nu proiectăm tot produsul în avans |
| P1 ∥ P2 | Engagement persistent + probe native Hermes, identitate, contaminare de mediu, compresie și wake | Web utilizabil și risc de integrare atacat devreme |
| P3a | Prima cerere HTTP brokered, evidence durabil, UI și Stop | Plumbăria funcționează; nu încă eficacitatea pentestului |
| P3b, probă nouă propusă | Browser + login simplu + API post-auth + expirare + trafic secundar controlat | Cel mai riscant transport nu este amânat după tot Settings |
| P4a + prima felie P5/P6 | Provider validat, skills imutabile/read-only, recon necesar și BOLA cu regulă business cunoscută, validator și raport minimal | Primul rezultat de securitate util, nu doar management de agenți |
| P4b în paralel | Ambii provideri, editor/catalog complet și publicare | Funcțiile promise rămân în MVP, dar nu blochează învățarea tehnică |
| Extindere P5/P6 | Reconul din matricea de suport, XSS reflectat și traversal-canary | Fiecare familie are oracle, control sigur și evaluare proprie |
| P7 | Bucle și concurență extinse, fault injection și recuperare integrate | Nucleul de stări/lease/revocare există deja; P7 îl extinde |
| P8 | Evaluare sigilată, raport/retest, backup/restore, retenție și pornire/oprire documentate | Livrare locală reproductibilă, cu limite publicate |

B01–B04 pot începe în forma propusă, cu reguli clare pentru editarea engagementului activ. B05–B06 primesc probele R02; B07 include protocolul de evidence și efecte incerte; B08 rămâne prima dovadă în UI. Adăugarea probei browser nu autorizează o țintă externă: rămâne fixture propriu izolat.

**Nu aș adăuga acum:** multi-tenancy, colaborare, SSO autonom, un framework nou de agenți, fork masiv Hermes, marketplace de skills, compilator general de workflowuri, Neo4j, sute de workeri, OAST/SSRF sau alte familii doar pentru paritate de marketing.

## 6. Verificări statice Hermes care schimbă probele P2/P7

Ancore la SHA `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`, relative la `/home/kali/.hermes/hermes-agent`. Ele descriu cod citit, nu comportament demonstrat live.

| Mecanism citit | Ancore | Ce putem afirma / ce rămâne de testat |
|---|---|---|
| Identitate contextuală în tool dispatch | `agent/tool_executor.py:1673–1688`; `model_tools.py:822–838`; `tools/registry.py:887–903` | `session_id`/`task_id` sunt transmise separat de argumentele modelului, dacă handlerul le acceptă. Autorizarea taskului Omnis nu vine automat. |
| Hook înainte de rularea copilului | `tools/delegate_tool.py:285–297, 383–415`; `tools/delegate_tool_child_run.py:854–862` | Hookul primește parent/child IDs și goal; nu este un mapping Omnis. `delegation_id` se atașează ulterior pe acest traseu. Testăm goaluri identice, ordine, retry și erori. |
| Compresie cu schimbare de identitate | `agent/conversation_compression.py:3340–3373` | Codul poate publica o sesiune nouă și actualiza `agent.session_id`. Nu presupunem ID stabil pe durata attemptului. |
| Încărcare dotenv din checkout | `tui_gateway/server.py:50–51`; `run_agent.py:121–122`; `hermes_cli/env_loader.py:423–447` | Entrypointurile dau loaderului calea `.env` din checkout. Un home gol nu dovedește izolarea credentialelor. Niciun fișier secret real nu a fost citit. |
| Root și loginuri externe | `hermes_constants.py:217–234`; `hermes_cli/config_defaults.py:1718–1724` | Rootul depinde de poziția home-ului; adoptarea loginurilor externe este implicit permisă în configurația inspectată. Testăm sursele simulate, nu folosim conturile personale. |
| ACK al continuării | `tui_gateway/session_notifications.py:161–168, 459–483`; `tui_gateway/prompt_turn.py:994–1001` | `_run_prompt_submit` poate returna `False`; `_notif_submit` nu propagă acel rezultat, iar dispatcherul finalizează delivery în lipsa unei excepții. Un ACK nu demonstrează procesarea rezultatului de Brain. Reproducerea dinamică a acestui caz rămâne de făcut. |

Ultimul punct nu justifică implementarea unui al doilea wake pentru fiecare copil. Cerința este reconciliere după task/attempt/rezultat consumat, cu un singur proprietar al continuării, fără pierdere și fără duplicarea efectelor. Planul are deja principiul; proba trebuie să includă și acest failure path.

Hermes oferă documentație și mecanisme de egress isolation reutilizabile.[24] Aș evalua reutilizarea lor, nu aș construi automat totul de la zero. Nici ele nu demonstrează singure politica Omnis pe path, identitate, efect, approval și task; aceasta rămâne condiția brokerului.

## 7. Praguri de decizie

### Ce trebuie clarificat înainte de efecte pe fixture

- Boundary-ul runtime-ului, sursele de credențiale, tool inventory și mappingul copil–task.
- Politica editării scope-ului activ și revocarea la Stop/crash.
- Operațiile fixture-ului și efectele lor, inclusiv servicii downstream.
- Protocolul de persistență a acțiunii și evidence; limite de trafic, durată și stocare.

### Ce trebuie clarificat înainte de prima familie confirmată

- Regula de acces/ownership, obiectele și identitățile de test.
- Oracle pozitiv și criterii pentru negativ/neconcludent, cu precondiții verificabile.
- Corpusul independent, informația permisă agentului și scenariile obligatorii de detecție.
- Reproducerea și resetarea stării, fără acces al agentului la soluție/scorer.

### Ce poate merge în paralel fără să blocheze primele probe

- Editorul avansat de Skills și al doilea provider.
- Polizarea navigării/vizualizării relațiilor.
- Extinderea catalogului, fără a declara capabilități neevaluate.

**Concluzie:** nu este necesară altă arhitectură. Este necesar un amendament al dependențelor și al porților, concentrat pe identitate, efecte, regulile de autorizare, dovezile rezultatelor negative și evaluare E2E. Astfel, Omnis poate rămâne un MVP ambițios și coerent, fără să devină nici un dashboard peste Hermes, nici un proiect de infrastructură care nu ajunge să demonstreze un finding.

## Limitele acestui review

Cercetarea publică a fost read-only. Unele căutări/extrageri prin backendul web au eșuat sau au returnat text incomplet; paginile relevante au fost recuperate direct din sursele oficiale. Pentru WSTG s-a folosit sursa versionată v4.2 din repository-ul OWASP, după eroarea paginii web. Nu au fost obținute conturi de test XBOW/Aikido și nu există comparație de performanță executată. Nu au fost schimbate planul original, profilul Hermes, credențiale sau executori. Review-ul propune criterii; nu le marchează artificial drept trecute.

## Sources

[6] https://help.aikido.dev/pentests/safety-measures — Safety Measures | Aikido
[9] https://xbow.com/platform — AI Penetration Testing Platform | Continuous Offensive Security &amp; Testing | XBOW
[10] https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration — Programmatic Integration | Hermes Agent
[11] https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks — Observer Hooks | Hermes Agent
[12] https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation — Subagent Delegation | Hermes Agent
[14] https://help.aikido.dev/pentests/configure-a-pentest/setting-up-authenticated-testing — Setting Up Test Users
[15] https://help.aikido.dev/pentests/configure-a-pentest/leveraging-code-and-documentation — Leveraging Code and Documentation
[16] https://help.aikido.dev/pentests/prepare-a-pentest/why-use-a-testing-environment — Why Use a Testing Environment
[18] https://playwright.dev/python/docs/network — Network | Playwright Python
[21] https://help.aikido.dev/pentests/coverage-and-findings/understanding-pentest-coverage — Understanding Pentest Coverage
[23] https://hermes-agent.nousresearch.com/docs/developer-guide/relay-shared-metrics — Relay Shared Metrics | Hermes Agent
[24] https://hermes-agent.nousresearch.com/docs/user-guide/egress/network-isolation — Network Egress Isolation (Docker) | Hermes Agent
[27] https://raw.githubusercontent.com/OWASP/wstg/v4.2/document/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References.md — https://raw.githubusercontent.com/OWASP/wstg/v4.2/document/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References.md
[28] https://docs.xbow.com/console/guidance/protecting-assets — XBOW docs - Protecting assets during XBOW testing
[29] https://docs.xbow.com/console/reference/scope-configuration — XBOW docs - Scope configuration
[30] https://docs.xbow.com/console/how-to/provide-asset-context — XBOW docs - Provide XBOW with context to guide testing
[31] https://docs.xbow.com/console/how-to/validate-with-canaries — XBOW docs - Validate results with canary tokens
[32] https://docs.xbow.com/console/how-to/explore-and-fix-results — XBOW docs - Explore and fix XBOW results
