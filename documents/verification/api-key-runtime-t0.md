# T0 — amendamentul API-key-only și predarea către T1

## Stare și mandat

**CLOSED_SCOPED documentar / APPROVED_SCOPED; T1 NOT_STARTED.** Bază: `9eda496061604fbbbe60f3c980a5c4636cf827c5`, branch `checkpoint/p2-batch2-pause-20261015`. Cele cinci contracte au fost discutate și aprobate de operator înaintea editării. Mandatul curent autorizează amendarea documentelor/testelor lor, trackingul existent și un prompt de implementare; **nu implementarea T1 și nu lansarea developerilor de produs**.

Autor documentar: orchestratorul/părintele, fără writer concurent. Reviewurile independente au aprobat snapshotul complet a5619d0; commiturile intermediare rămân candidate la momentul lor, iar acceptarea documentară este adjudecată mai jos. Scope: cele cinci documente canonice și HTML generate, registry de versiuni, teste/renderer documentar strict afectate, AGENTS/README/CONTRIBUTING numai pointere/stare afectate, harta/indexul verification și acest registru/promptul T1. Fără API/CLI/web de produs, migrații efectuate, installs/DB/Docker/chei/providere/target/global/push. HTML-ul preexistent `documents/Omnis_Notite_Originale.html` este protejat: necitit și neatins.

## Decizii și limite

Canonul de comportament este [arhitectura](../Omnis_MVP_Architecture.md), ordinea este în [plan](../Omnis_Implementation_Plan.md), nu în acest registru. [Analiza migrării](api-key-runtime-migration-analysis.md) rămâne proveniență/diagnostic, nu plan concurent.

- Owner unic, SystemOperationV1 fără engagement/catalog/nativ, ModelDispatchV2 cu admitere reală, no-resend și Stop la sender.
- Seif AEAD comun, persistent, autounlock prin master key locală privată; LOCKED fără cheie, backup separat și consistență DB–filesystem. Nu protejează de root/same-UID ori copia care include cheia master.
- Default + override BRAIN/INVESTIGATOR/VALIDATOR; MONITOR fără plafon total LLM de dolari/apeluri/durată. Rămân limitele per operație, DATA, ROE și target. HOLD global la credit/quota, Resume manual; nici refill contabil, nici fallback ascuns. Rezerva financiară LLM pentru validator este retrasă, prioritatea validării și limitele target rămân.
- Outcome/operație/provider/usage separate; partial/UNKNOWN/TRUNCATED și requested/observed fără succes fals sau dublă contabilizare.
- Distribuție nouă în instanță separată, cititori/migrații/date/licențe păstrate. Hermes executabil retras numai după înlocuitori/consumeri instalați verificați; toolingul de dezvoltare nu se elimină.
- Workerii pot primi shell/scripturi/workspace **în sandbox**, în execuția engagementului, cu G-TOOLS/G-NET/Stop înainte de folosire; nu drepturi prin prompt sau acces la host.
- M-LAB: IDOR/BOLA + triage al candidatului (skill al orchestratorului inițial) + validator/replay/oracle. `skills/bug-bounty-triage/SKILL.md` rămâne original QUARANTINED; instrucțiunile «never redact»/evidence-as-authority/tool grants nu intră în policy. Validatorul extern menționat nu a fost furnizat/identificat: CANDIDATE_SOURCE_PENDING. Adoptare numai după sursă/licență/revizie/review/eval; metodologia first-party evaluată este fallbackul de conținut, nu ocolirea validării.
- Steering ulterior al operatorului: migrarea nu închide produsul. Plan §15.1 și UI/UX §7.1 păstrează funcțiile/skills/toolurile și evoluția UI/grafică prin SL/E existente; polish neblocant cu funcția, direcție vizuală nouă numai cu acord. Promptul T1 păstrează această continuitate fără lansarea etapelor succesoare.

## Dovezi ale autorului și limitele acceptării

Cerință → consumer → risc → decizie: contractele aprobate → implementatorul T1 și cititorul canonului → păstrarea unui prerequisite Hermes, grant fals ori contabilizare/cost fals → corectare înainte de autorizarea implementării.

- RED: `python -B -m unittest discover -s tests/documentation -p test_api_key_contracts.py -v`, exit 1, 4 teste, 3 failures + 1 error pentru contracte/registry absente în canonul vechi. Log privat: `/home/kali/.hermes/cache/scratch/omnis-t0-fsUkdEIa/contracts-red.log`.
- O comandă intermediară nu a pornit testele: variabila shell T0_WORK nu a fost disponibilă în apelul paralel, redirecționarea a refuzat `/architecture-docs.log`. Corectat folosind calea absolută owned; fără sudo, efecte produs sau retry de consumer. NOT_RUN, nu FAIL de produs.
- Primul GREEN: renderer + `--check` exit 0; `python -B -m unittest discover -s tests/documentation -v`, 84 PASS/exit 0. După delta de titlu/triage: **85 PASS/exit 0**, renderer/check și `git diff --check` exit 0. Acoperire documentară numai; nu runtime/crypto/egress/SDK live. Plan/UI/readiness și reviewul integrat urmează înainte de acceptarea T0.
- Candidat arhitectură/stack: `6632b8b05197d9e05410b74fa02984b0a7dee467`, fără acceptare T0. RED al noii ordini de plan: 86 teste, 6 failures + 1 error/exit 1, pentru DAG/heading/consumer/gates încă vechi; `plan-red.log` în același scratch.
- Editarea protejată AGENTS a fost inițial refuzată prin timeout de aprobare, fără bypass sau modificări parțiale. Operatorul a răspuns ulterior explicit «Da, aprob explicit această modificare în AGENTS.md»; apelul normal patch a reușit. Celelalte reguli și skillurile calificate nu au fost schimbate.

Reviewurile și verificarea cititoarelor au fost încheiate pe snapshotul înghețat; dispozițiile sunt mai jos. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Guvernanța 9eda496/4e2d8d6 rămâne evidență istorică scoped; nu relansăm loaderul skillurilor nemodificate.

## Review independent și QA a cititoarelor

Snapshot revizuit: **a5619d0238976d75763bea4618d747ed62e7a377**, include **6632b8b05197d9e05410b74fa02984b0a7dee467**. Ambele procese Codex CLI 0.163.0 au fost configurate/verificate prin banner: model gpt-6.1-sol, provider openai, approval never, sandbox read-only, --ignore-user-config/--ephemeral/--no-daemon; fără config global modificat. Preflight sandbox `/usr/bin/true` exit 0. Avertismentul CLI despre limita scanării skillurilor a rămas explicit; scope-ul/prompturile au indicat fișierele canonice, iar rapoartele confirmă citirea snapshotului. Nu calificăm loaderul global prin aceste reviewuri.

| Review | Proces / sesiune / effort | Verdict / original |
|---|---|---|
| Contracte T1: root/refs/seif/Stop/outcome | proc_4f3c645f22d7 / 01a1649f-0023-7a43-8b1b-626d8b793651 / xhigh; exit 0 | APPROVED_SCOPED, zero findings; [original JSON](api-key-runtime-t0-evidence/review-contracts.json), SHA256 c46e813ece14f20e40c63d881caca122c80072ae7b80f5de39187a84462ccc33 |
| Ordine/SL/E/M-LAB/UI/tracking/prompt | proc_9b1b3a68c02c / 01a1649f-001f-7d03-9248-86287af5c80f / medium; exit 0 | APPROVED_SCOPED, zero findings; [original JSON](api-key-runtime-t0-evidence/review-delivery.json), SHA256 ce387efd2d60d33e6f9637d4aba5aae4d0f2715a5c385f98158d05692bcbf9e5 |

Părintele a citit integral ambele rapoarte, confirmat HEAD/checkout neschimbat și adjudecat verdictul numai pentru canonul/promptul din scope. Originalele sunt păstrate byte-exact, verificate cu cmp/SHA; nu există findings deschise în aceste scope-uri. Niciun reviewer nu a executat produsul sau declarat pin/live PASS.

**Regresii documentare:** după modificarea DAG/UI/tracking, o verificare a găsit numele G-WORDLIST-CORE omis din rândul de dependență (era prescurtat CORE); corectat în plan, fără slăbirea testului. Rezultat integrat: **87 PASS/exit 0**, renderer/check și diff check exit 0. Toate SL01–SL36 și E1–E4 au rânduri unice; DAG aciclic și negativele de eliminare a guardurilor sunt verificate. Acestea sunt teste de documente, nu verificator semantic universal.

**QA după review:** Chromium local pe exact cele cinci cititoare generate, fără prototip sau aplicație/DB. La 1440/390/320: **15 verificări PASS/exit 0**, un singur H1, fără ancore interne rupte/overflow de pagină, SL01–SL36 randate în ordine, zero erori JS și zero requesturi HTTP(S). [Receipt original](api-key-runtime-t0-evidence/documents-browser.json), SHA256 97970a9a5f2e0041769f23dfed56fb7d6e67851d13ab9965f5a4b6c14de0db7a. Comandă: Python -B cu Playwright sync, /usr/bin/chromium, navigare file:// numai către allowlistul de cinci nume din renderer; reguli HTTP/HTTPS abort și asserts pentru număr/rezultate. Nu este QA de produs, screen-reader/cross-browser sau acceptare vizuală nouă.

Capturile au fost inspectate vizual: [roadmap desktop](api-key-runtime-t0-evidence/Omnis_Implementation_Plan-1440.png), [roadmap mobil](api-key-runtime-t0-evidence/Omnis_Implementation_Plan-390.png), [contracte desktop](api-key-runtime-t0-evidence/Omnis_MVP_Architecture-1440.png), [contracte mobil](api-key-runtime-t0-evidence/Omnis_MVP_Architecture-390.png). Fără defecte vizibile concrete în zonele capturate; scrollul orizontal al tabelelor este intenționat. Receiptul original păstrează locatoarele scratch ale execuției; imaginile de aici sunt copii byte-exact pentru recuperare durabilă.

**Delta de închidere post-review:** numai statusul T0/receipturile și etichetarea explicită a două note vechi P0/G00 ca istoric, nu schimbări de contract, phase DAG, API, seif, sandbox sau prompt T1. Reviewul pe conținutul neschimbat este reutilizat scoped; nu pretindem că rapoartele au revizuit propriul commit de acceptare. Cititoarele afectate au fost regenerate; renderer/check, **87 teste documentare** și diff check au trecut exit 0 pe delta finală. [QA finală a celor trei cititoare schimbate](api-key-runtime-t0-evidence/documents-browser-final.json): **9 PASS/exit 0**, zero JS/network; probele UI/stack neschimbate sunt reutilizate după diff byte-exact față de a5619d0. Nu s-a rerulat prototipul sau aplicația.

## Adjudecare și criteriul de închidere

**T0 CLOSED_SCOPED / APPROVED_SCOPED**, numai documentar. Cele cinci contracte, M-LAB cu triage/validator, roadmap-ul post-migrare și toate SL/E sunt în canon; două reviewuri independente și probele documentare/cititoare sunt disponibile. [Promptul T1](api-key-runtime-t1-prompt.md) este pregătit/înghețat în snapshotul revizuit, **HANDOFF_ONLY / NOT_LAUNCHED**. Nu este mandat de instalare sau execuție a produsului în această sesiune.

Primul consumer ulterior: Settings → conexiune/seif → system_operation → sender → Test model finit → outcome/consum/readback/Cancel/Stop, după activarea explicită a promptului. Implementare/QA produs/provider/sandbox/crypto/restore/compatibility reale rămân NOT_RUN. Skillul validator extern rămâne de furnizat/admis la T4, nu blocker T1. Nu există promisiune de zero regresii sau MVP/phase2 închisă.

## Recovery și următorul consumer

Cicluri harness-only pe acceptance row T0: 0; RED documentar și corectarea canonului sunt progresul cerut, nu probe de produs. Recuperare: Git status/HEAD → unicul CURRENT → acest registru + secțiunile modificate. Nu relua joburile vechi Codex/openfix/P2. T0 este închis numai la frontiera documentară descrisă mai sus; T1 rămâne NOT_STARTED și necesită mandat separat. Commitul care conține acceptarea se identifică din Git, fără auto-referință imposibilă în propriul SHA.

Rollback: revert al commiturilor documentare în ordinea dependențelor, regenerarea HTML și rerularea testelor docs. Nu există efecte DB/credentiale/servicii de restaurat în acest mandat.
