# T0 — amendamentul API-key-only și predarea către T1

## Stare și mandat

**IN_PROGRESS / candidat documentar, nu acceptare.** Bază: `9eda496061604fbbbe60f3c980a5c4636cf827c5`, branch `checkpoint/p2-batch2-pause-20261015`. Cele cinci contracte au fost discutate și aprobate de operator înaintea editării. Mandatul curent autorizează amendarea documentelor/testelor lor, trackingul existent și un prompt de implementare; **nu implementarea T1 și nu lansarea developerilor de produs**.

Autor documentar: orchestratorul/părintele, fără writer concurent. Review independent obligatoriu pe snapshotul complet, înaintea acceptării; commiturile intermediare sunt candidate. Scope: cele cinci documente canonice și HTML generate, registry de versiuni, teste/renderer documentar strict afectate, AGENTS/README/CONTRIBUTING numai pointere/stare afectate, harta/indexul verification și acest registru/promptul T1. Fără API/CLI/web de produs, migrații efectuate, installs/DB/Docker/chei/providere/target/global/push. HTML-ul preexistent `documents/Omnis_Notite_Originale.html` este protejat: necitit și neatins.

## Decizii și limite

Canonul de comportament este [arhitectura](../Omnis_MVP_Architecture.md), ordinea este în [plan](../Omnis_Implementation_Plan.md), nu în acest registru. [Analiza migrării](api-key-runtime-migration-analysis.md) rămâne proveniență/diagnostic, nu plan concurent.

- Owner unic, SystemOperationV1 fără engagement/catalog/nativ, ModelDispatchV2 cu admitere reală, no-resend și Stop la sender.
- Seif AEAD comun, persistent, autounlock prin master key locală privată; LOCKED fără cheie, backup separat și consistență DB–filesystem. Nu protejează de root/same-UID ori copia care include cheia master.
- Default + override BRAIN/INVESTIGATOR/VALIDATOR; MONITOR fără plafon total LLM de dolari/apeluri/durată. Rămân limitele per operație, DATA, ROE și target. HOLD global la credit/quota, Resume manual; nici refill contabil, nici fallback ascuns. Rezerva financiară LLM pentru validator este retrasă, prioritatea validării și limitele target rămân.
- Outcome/operație/provider/usage separate; partial/UNKNOWN/TRUNCATED și requested/observed fără succes fals sau dublă contabilizare.
- Distribuție nouă în instanță separată, cititori/migrații/date/licențe păstrate. Hermes executabil retras numai după înlocuitori/consumeri instalați verificați; toolingul de dezvoltare nu se elimină.
- Workerii pot primi shell/scripturi/workspace **în sandbox**, în execuția engagementului, cu G-TOOLS/G-NET/Stop înainte de folosire; nu drepturi prin prompt sau acces la host.
- M-LAB: IDOR/BOLA + triage al candidatului (skill al orchestratorului inițial) + validator/replay/oracle. `skills/bug-bounty-triage/SKILL.md` rămâne original QUARANTINED; instrucțiunile «never redact»/evidence-as-authority/tool grants nu intră în policy. Validatorul extern menționat nu a fost furnizat/identificat: CANDIDATE_SOURCE_PENDING. Adoptare numai după sursă/licență/revizie/review/eval; metodologia first-party evaluată este fallbackul de conținut, nu ocolirea validării.

## Dovezi ale autorului — încă fără acceptare finală

Cerință → consumer → risc → decizie: contractele aprobate → implementatorul T1 și cititorul canonului → păstrarea unui prerequisite Hermes, grant fals ori contabilizare/cost fals → corectare înainte de autorizarea implementării.

- RED: `python -B -m unittest discover -s tests/documentation -p test_api_key_contracts.py -v`, exit 1, 4 teste, 3 failures + 1 error pentru contracte/registry absente în canonul vechi. Log privat: `/home/kali/.hermes/cache/scratch/omnis-t0-fsUkdEIa/contracts-red.log`.
- O comandă intermediară nu a pornit testele: variabila shell T0_WORK nu a fost disponibilă în apelul paralel, redirecționarea a refuzat `/architecture-docs.log`. Corectat folosind calea absolută owned; fără sudo, efecte produs sau retry de consumer. NOT_RUN, nu FAIL de produs.
- Primul GREEN: renderer + `--check` exit 0; `python -B -m unittest discover -s tests/documentation -v`, 84 PASS/exit 0. După delta de titlu/triage: **85 PASS/exit 0**, renderer/check și `git diff --check` exit 0. Acoperire documentară numai; nu runtime/crypto/egress/SDK live. Plan/UI/readiness și reviewul integrat urmează înainte de acceptarea T0.

Reviewurile, verificările finale și dispozițiile findingurilor se completează pe snapshotul înghețat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Guvernanța 9eda496/4e2d8d6 rămâne evidență istorică scoped; nu relansăm loaderul skillurilor nemodificate.

## Recovery și următorul consumer

Cicluri harness-only pe acceptance row T0: 0; RED documentar și corectarea canonului sunt progresul cerut, nu probe de produs. Recuperare: Git status/HEAD → unicul CURRENT → acest registru + secțiunile modificate. Nu relua joburile vechi Codex/openfix/P2. T0 se închide numai cu reviewurile și verificările documentare aplicabile pe bytes curenți, commituri locale și prompt T1 verificat; T1 rămâne NOT_STARTED.

Rollback: revert al commiturilor documentare în ordinea dependențelor, regenerarea HTML și rerularea testelor docs. Nu există efecte DB/credentiale/servicii de restaurat în acest mandat.
