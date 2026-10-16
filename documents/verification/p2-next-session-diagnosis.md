# Sesiune fresh — decizie și diagnostic înaintea altui remediu P2

## Mandatul actual: ANALYSIS_ONLY

Lucrează în `/home/kali/OmnisAI`. Operatorul a oprit continuarea implementării și cere întâi o analiză verificabilă: de ce nu este închis P2-inert, ce verificări sunt realmente necesare, ce este deja dovedit și ce defect concret trebuie reparat. **Nu începe cu un nou run de teste, un retry nativ, alt review neschimbat sau cod.** Acest mandat înlocuiește continuarea executabilă din `p2-next-session-implementation.md`; acel fișier rămâne istoric.

Livrează analiza și propunerea precisă, apoi oprește-te pentru acordul operatorului asupra intervenției. În această etapă nu implementezi, nu execuți revert, nu schimbi planul/oracolele și nu lansezi QA PostgreSQL/native/browser/inferență. Nu transforma pregătirea promptului sau aprobarea unei ipoteze în permisiune pentru etapa următoare.

## 1. Starea de recuperare — verifică, nu relansa

- Branch: `checkpoint/p2-batch2-pause-20261015`. Ultimul snapshot integrat de produs/teste/documentare înaintea acestui handoff: **`62948d00b80a9c7baa281f0b0e09468b2cf01cef`**. HEAD real va include și commitul documentar al predării; citește `git status`, HEAD, diff și istoricul real. Nu inventa auto-referința commitului curent.
- Zero subagenți/autori activi la predare. Cele patru worktree-uri proprii sunt curate și checkpointuite, cu heads în `p2-canonical-handoff-interrupted.json`. Nu reintegra și nu reactiva implicit aceste ramuri.
- **Admission ACCEPTED_SCOPED:** QA129 pe `35c7cd5`, acceptată în `8acfd93`: **129 PASS / 408.44s / exit0 / family_drained=true**,104SOURCE+25PG. Caps/Stop/failure după write/late accounting/DATA și cleanup exact au dovezi. Nu le relansa separat.
- **Primul canonical pe `8acfd93`:**2452PASS/3FAIL/62SKIP2759.57s, exit2/drained. Cele trei eșecuri erau fixture SOURCE: `ContractAdmission.batch_index` lipsă și perechea checker/composer pre-M2 nepotrivită.
- **Remedii comise:** `c048808` și `327fd26`, doar două teste, fără produs/native/helper comun sau aserțiuni relaxate. Review independent APPROVED_SCOPED; autor222SOURCE PASS, părinte4SOURCE PASS0.64s. Reseal-ul testului pre-M2 este SOURCE sintetic, nu proveniență de producer istoric instalat.
- **Canonicalul post-fix pe `62948d0`:** suita API a terminat cu **2455 PASS / 62 SKIP / 2969.29s**, apoi a început migrarea. La cererea de handoff, ownerul existent a primit SIGTERM prin pidfd după verificarea identității/handlerului; procesul `proc_3e34f85b4fed` a terminat. Receipt strict **`{"schema_version":1,"code":130,"family_drained":true}`**; make exterior exit2. Este **INTERRUPTED_FOR_HANDOFF**, nu un nou FAIL de produs și nu canonical complet PASS. Migrations STARTED_BUT_INTERRUPTED; wheel/web/E2E/CLI/release/runtime NOT_RUN în această tentativă. Niciun job nu trebuie așteptat sau relansat implicit.
- Cleanup post-oprire verificat: CID/proiect/rețea/socket proprii absente,10identități PID fixate absente, daemon/imagine identice, directoare PGDATA originale păstrate.50hashuri/index/HEAD neschimbate până la scrierea documentelor predării. DROP per-test nu este pretins pentru migrarea întreruptă.
- `documents/Omnis_Notite_Originale.html` este untracked preexistent **PROTEJAT: nu citi, hash, edita, stage sau șterge**. Fără push, profil r1, date/operator credentials, schimbări globale sau inferență/provider/target.

## 2. Citește doar intrările necesare

Încarcă `omnis-project-status` ORIENT, `omnis-delivery`, `omnis-review-qa`, `systematic-debugging`; pentru traseul nativ folosește `omnis-hermes-runtime` și `hermes-agent`. Citește AGENTS/CONTRIBUTING și CURRENT din README/implementation-status, nu întregul istoric ca backlog nou.

Sursele prioritare:

1. `documents/Omnis_Implementation_Plan.md` §7/§7.1: definițiile H04/H05 și **exact opt** criterii de ieșire P2-inert; secțiunile relevante din arhitectură despre mapping pre-access/lineage și refuz. Separă cerințele P2-inert, P2-live și interdicția de a începe P3. Nu considera automat că întreaga listă de scenarii H04/H05 este obligatorie acum.
2. `documents/verification/p2-integration-b06cm.md`: matricea celor opt criterii, acceptările scoped și limitele. Este registru derivat, nu autoritate care justifică singură un test nou.
3. `documents/verification/p2-h04-installed-qa-partial.json` și `p2-h04-pre-ready-causality.json`: tentativa originală și analiza deja făcută. Nu reface aceeași analiză pentru încă un raport identic.
4. `p2-integration-failure-pg-qa-pass.json`, `p2-integration-canonical-fail.json`, `p2-canonical-source-fixtures-author.json`, `p2-canonical-source-fixtures-review.json`, **`p2-canonical-handoff-interrupted.json`**: dovezile/refuzurile/încercările păstrate. Nu transfera un PASS la alt consumer/snapshot.
5. Codul efectiv al traseului: `api/tests/test_contract_method_pg.py`, selectorul existent `documents/verification/p2-bound-predicates-evidence/h03-process-fixed-pg-selection.py`, `api/src/omnis/supervisor/runtime_client.py`, `integrations/hermes/src/omnis_hermes/runtime_host.py`/`runtime_protocol.py` și numai funcțiile/callerii necesari.

Logurile originale sunt private, nu se afișează brut în chat:

- H04: `/home/kali/.hermes/cache/scratch/h4q2-c0xcc087/`; raportul de cauzalitate fixează căile cazurilor c0/c1/c2 și hashurile observerului/artefactului.
- Native original: `/home/kali/.hermes/cache/scratch/p2-batch2-cdbfa74/installed-c6eac5f5a13440ffa6bcb35a6e853ab0/native-artifact.json`; sursa atestată în `context/runtime-source/`, inclusiv `tui_gateway/server.py`.
- Canonical întrerupt: `/home/kali/.hermes/cache/scratch/cp3-6j5owjl8/`: `preflight.json`, `handoff-stop-request.json`, `handoff-cleanup.json`, `outer.log`, `db-b9ecbd30ec284b2b/gate.log` și receiptul asociat.
- QA129: `/home/kali/.hermes/cache/scratch/p2q129-bj4tow05/`; primul canonical: `/home/kali/.hermes/cache/scratch/cp2-hadi00yn/`.

Parsează privat și returnează numai câmpuri allowlist: test/cod/status/fază/timing/număr/reason sanitizat/hash. Nu folosi dump/read_file/context grep pe tracebackuri PG, receipts private, capability/DSN/env/frame/stderr. Citește secvența completă necesară diagnosticului în procesul local, nu doar ultimul mesaj normalizat. Dacă scratch a expirat, marchează exact dovada lipsă; nu o inventa, nu adopta DB vechi și nu face rebuild/rerun implicit.

## 3. Mai întâi decide ce este necesar, nu presupune că toate testele sunt obligatorii

Pentru fiecare rest real din matricea P2 și cele cinci scenarii ale probei H04, dă într-un singur tabel scurt:

`cerință normativă exactă → consumer real → dovadă existentă/revizie → lipsă/risc concret → decizie`.

Deciziile trebuie discriminate:

- **OBLIGATORIU_NEACOPERIT:** cerință P2-inert care nu are încă dovadă adecvată.
- **DEJA_ACOPERIT / REDUNDANT:** există dovadă la același comportament și bytes relevanți; citează de ce se poate reutiliza. Numele diferit al testului nu creează o cerință nouă.
- **ÎN_AFARA_P2_INERT:** aparține live/compresiei model-facing/P3 ori altei faze; citează delimitarea, nu doar preferința.
- **PROBĂ_DEFECTĂ / NECONCLUDENTĂ:** setup/observer/artefact/runner împiedică exercitarea proprietății; nu o numi automat defect de produs.

Examinează dovezile batch2/H03/guard pre-access deja acceptate numai cât este necesar pentru a stabili dacă acoperă vreun rest pretins. Nu reaudita sau relansa acele acceptări. Deosebește H04 (asociere/identitate înainte de acces), H05 (lineage păstrat ori refuz, inclusiv după compresie) și inventarul callable; raportarea anterioară le-a grupat imprecis. Nu inventa un modul sau un nou catalog de scenarii.

Poți recomanda că o probă se elimină/înlocuiește din lista de lucru numai cu dovadă de redundanță ori delimitare normativă. Dacă propui schimbarea contractului de acceptare, arată modificarea și riscul și cere decizia operatorului. Nu șterge testul, nu schimba expected în UNKNOWN/skip și nu închide un guard obligatoriu prin presupunere.

## 4. Pentru orice rest obligatoriu: diagnostic cauzal, logs și Git înainte de remediu

Faptele H04 existente, nu concluzii de extins:

- Inventory și wrong-root au PASS pe native instalat. Child-lineage a eșuat **înainte de READY și înainte de fault injection**; guardFalse/exception nu au fost lansate. Acesta nu demonstrează ocolirea guardului.
- Ultima frontieră terminată: importul `rpc_dispatch`; importul grupat `tui_gateway/server.py:3363–3386` nu are completare observată. Nu sunt identificate modulul intern, syscallul, așteptarea ori costul care au consumat bugetul.
- `RuntimeUnavailable` este normalizare, nu cauză-rădăcină. EOF observat după timeout nu este automat evenimentul inițiator.8017/8018ms sunt offset Host, nu grant8s; startup are maximum5s, iar bugetul rămas efectiv trebuie urmărit la producer și consumer. Nu scădea ceasuri cu origini diferite.
- Observerele c0/c1/c2 diferă numai prin numele cazului după normalizarea declarată; prefixul de19evenimente coincide. Nu atribui exclusiv CPU/cache/observer/import fără discriminant. Originalul UNCERTAIN nu este rescris de cleanupul extern.

Trasează apelul și datele până la primul producer defect, nu modifica doar exception wrapperul. Compară explicit un caz trecut și cel eșuat, surse/artefacte/config/autoritate/deadline/observer. Separă **fapt demonstrat**, **ipoteză falsificabilă**, **informație lipsă**.

Inspectează `git log`, diffuri relevante și, unde ajută, blame pe simbolul efectiv. Puncte de orientare, nu vinovați prezumați: batch2 `94de21a`, baza H04 `d0504e4`, remediul T2 `35efc3f`, integrarea test/reader H04 `b4135c5`, QA H04 `4a4553e`, diagnosticul `12be37e`, Admission final `35c7cd5`/`8acfd93`, fixture fixes `c048808`/`327fd26`. Verifică dacă o schimbare atinge într-adevăr callerul eșuat; simpla vecinătate în istoric nu este cauzalitate. Native image/source și reader/API sunt distribuții diferite.

Dacă există regresie, identifică primul commit/hunk demonstrabil și dependențele lui. Spune dacă preferi fix minimal sau revert al unui commit precis și ce comportament s-ar pierde. **Nu executa revert/reset/clean/stash/rebase și nu reveni în bloc peste acceptări valide.** Dacă primul commit rău nu poate fi stabilit, spune asta; nu inventa un bisect și nu porni zeci de native launches.

Dacă logurile nu pot decide cauza, specifică **un singur** discriminant minim de obținut: ce valoare/eveniment lipsește, unde se observă, ce ipoteze separă, prin ce comandă existentă, pe ce bytes/resurse și cu ce limită. Propune-l, nu îl executa în mandatul ANALYSIS_ONLY. Un rerun orb, prewarm, deadline/grant mărit ori încă un framework de observare nu sunt diagnostice.

## 5. Livrabilul cerut înaintea oricărei implementări

Un raport concis în chat; nu un nou backlog sau o serie de rapoarte/verificatoare. Include:

1. **Verdict de necesitate:** ce este obligatoriu pentru P2-inert, deja acoperit/redundant și în afara fazei; cerințe și dovezi precise, fără concluzie impusă.
2. **Diagnosticul:** prima frontieră defectă, lanțul cauzal demonstrat și cauza dacă este stabilită; loguri/cod/commituri care o susțin. Ce rămâne necunoscut este etichetat.
3. **Intervenția recomandată:** nimic de schimbat / corecție de probă / fix de produs / revert precis / observație minimă înainte de fix. Pentru fiecare modificare necesară: fișier+simbol/hunk, ce se schimbă, de ce, ce NU se schimbă și riscuri/dependențe.
4. **Proba exactă viitoare:** comanda RED care surprinde cauza, oracolul pozitiv/negativ, GREEN și numai regresiile afectate. Nicio comandă fabricată: verifică manifestul/argv/prerechizitele fără efecte. Păstrează gate-ul integral obligatoriu la integrarea finală, nu după fiecare ajustare.
5. **Lista finită de închidere P2:** numai resturile justificate de audit, în ordine; ce rezultat schimbă decizia pentru fiecare. Nu reintroduce verificări neafectate și nu numi full canonical PASS din API2455 sau din suita focalizată.

**Apoi STOP pentru acord.** Doar după aprobarea planului concret: un autor pe fișierele delimitate, reproducere RED, fix/revert minimal și granular, verificări afectate, review independent pe bytes finale și QA reală cerută de consumer. Nu începe această etapă din sesiunea de analiză. Fără inferență live sau bugete/deadline-uri mărite pentru a obține verde.
