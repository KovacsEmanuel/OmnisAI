# P2 — audit de scope, istoric și proporționalitate

## Concluzie și frontiera auditului

**P2 nu este terminată. Cauza nu este numai numărul de teste sau lipsa unui cont: lipsesc consumatori de produs.** Există progres real în catalog/publicare, assignment/binding/compoziție, inputuri persistente, proiecții și ledger. Totuși cold admission se termină în refuz, nu în metoda executată; contabilitatea nu este legată la `reserve → SENT → send`. Mai multe teste ale acelorași componente nu închid aceste două lipsuri.

Auditul cerut de operator acoperă commiturile accesibile din `33588142f136c3426fbd2ec0efb29bdebfccb5bc`, cu committer date în intervalul 8–11 octombrie 2026, fus +03:00. Trei investigații independente au comparat norma, codul și procesul; părintele a verificat constatările principale în surse și a reprodus defecțiunile de mai jos. Nu este audit exhaustiv sau acceptare a întregii implementări. Originalul HTML preexistent rămâne exclus, fără modificare/staging; alte ramuri nu sunt creditate ca integrate.

Autoritate: plan §4/§7/§8, arhitectură §5/§5.2/§6.3/§9.4–9.10. Criteriile finite sunt în **plan §7.1**, nu într-un backlog paralel. Acceptările istorice P0/P1/B05/B06a și subseturile B06b rămân la reviziile/frontierele lor; nu sunt redeschise numai pentru că a început acest audit.

## Ce arată Git — și ce nu arată

| Metrică | Rezultat |
|---|---:|
| Commituri accesibile în interval | 199 |
| După ziua commitului: 8 / 9 / 10 / 11 octombrie | 50 / 47 / 77 / 25 |
| Prefixe `docs` / `feat` / `fix` / `test` | 108 / 29 / 36 / 21 |
| Alte prefixe: `build` / `import` / `style` / `wip` | 2 / 1 / 1 / 1 |

Numărarea părintelui și auditul de proces coincid. Statistica normativă inițială de **153** nu este adoptată: frontiera sa Git era mai îngustă decât intervalul fixat. Datele de autor și de commit pot diferi la importurile seriale; nu deducem ore de muncă din distribuția zilelor. Prefixul `docs` nu măsoară timpul pierdut. JSON-urile capturate, screenshoturile și copiile integrale upstream/patch sunt artefacte/evidence, nu linii noi de produs sau progres procentual.

Reproducere read-only: `git log --format='%H %aI %cI %s' 3358814`, filtrare după committer date în intervalul de mai sus; `git diff-tree --root --no-commit-id --no-renames --numstat -r <sha>` pentru clasificarea după căi. Rezultatele se însumează programatic, nu din subiecte selectate manual. Git nu furnizează costul complet al modelelor, durata QA sau numărul tuturor rerulărilor scratch; **nu există un procent verificat de timp risipit**.

## Progres util versus overhead evitabil

| Exemplu concret | Adjudecare | Decizie |
|---|---|---|
| Catalog/closure durabile, Publish exact/CAS/replay și PURE persistent | Produs util, acceptat scoped; nu investigator SECURITY | Reutilizare, fără alte demo-uri de catalog înainte de consumerul complet |
| `23941e3`: refuz public înainte de import/framing; `d14c354`: inventar exact, nu tuple subclass care imită `()` | Remedieri reale de frontieră, nu teste cosmetice | Păstrarea regression/denials și a controlului stock |
| SDK real: `extra_body` poate suprascrie model/messages; guard final `c78dd50` | Măsurătoare utilă și guard DATA implementat | Nu relansăm serializarea neschimbată; legăm guardul la ownerul legitim |
| SDK: locator, `uv pip sync -r`, separator argparse/bwrap, source în afara mounturilor | Erori ale driverului descoperibile înainte de efecte | Un preflight pentru argv/import/mount map, nu runner/owner nou |
| Native QA: bytecode cu `-I` fără `-B`, FROM interpretat ca registry reference | Prerechizite/driver, nu defect DTO | Refolosim instalarea locală și verificăm referința/bytes; nu slăbim confinarea |
| Fixture preflight omite câmpuri obligatorii: două pozitive FAIL, nouă negative aparent verzi | False-green real al oracle-ului, remediat `cd6202c` | Fixture din producerul real; pozitiv și negativ pe aceeași frontieră |
| Records QA reutilizează un root fizic pentru RUN-uri distincte și așteaptă reconcile pe graph unstarted | Guardul ownership este util; topologia/oracle-ul QA erau greșite | Root/boot noi și readback receive-only; fără unicitate relaxată sau rezultat inventat |
| Browser larg/capturi pe records fără UI nouă; verificatori ai rapoartelor și echipă completă pe orice fix | Overhead evitabil, fără avans echivalent la cerința produsului | Browser numai la UI/call path afectat; review focalizat și echipă proporțională |

Surse: registrele `p2-b06b-c03-records.md`, `p2-b06b-c03-records-installed.json`, `p2-integration-sdk-noio-20261011.md`, `p2-sdk-execution-20261011.md`, `p2-final-dto-20261011.md`, `p2-native-cold-data-20261011.md`, `p2-fresh-open-findings-20261011.json`. Failures/incidentele lor rămân istorice; acest audit nu le rescrie în PASS și nu le transformă automat în gates actuale.

## Defectele checkpointului și remedierea minimă

| Constatare | Reproducer și rezultat | Schimbare și limită |
|---|---|---|
| F01: getterul owned refuză `_hostname_for`, cerut de `_max_tokens_param` | Regression pe corpurile native exacte: **2 failed / 5 passed, exit1** | `0b51b62`: permite numai helperul pur; turn/client rămân refuzate. SOURCE final **50 passed, exit0**, Ruff check/format0; patch reverse/reapply și hashes **14/14** originale/patched/pin PASS. SOURCE nu este constructor fizic |
| F02: inventarul exact al testului omite noul `agent/agent_init.py` | Testul existent **1 failed / 1 passed, exit1**; hashes reale erau coerente | `c0cac1e`: adaugă numai fișierul lipsă; **2 passed, exit0**, Ruff0. Egalitatea exactă și toate controalele sunt păstrate |
| F03: testul WIP de facade nu este formatat | Ruff format **exit1** | `c6fcaa1`: numai wrapping; owned SOURCE **8 passed, exit0**, Ruff check/format0 și mypy strict0 |

Comenzi: `api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml <fișierele afectate> -q --tb=line`, cu plugin autoload dezactivat și fără variabile Python/pytest ambientale; Ruff și mypy din același mediu fixat. Suita de 50 include cele 8; **nu se însumează drept 58 teste unice**. Cele 72 teste de documentare și renderer check au trecut pe baseline-ul auditului, nu reprezintă gate de produs și se rerulează după editările documentare.

Checkpointul `3358814` rămâne WIP neacceptat integral. Replay `STATUS` după CREATE pierdut poate rămâne `UNKNOWN`; aceasta este o limită fail-closed, nu mandat de resend. Registry32 reține markerii în același boot; prima probă bounded nu promite utilizare multi-run nelimitată. Nu se implementează release/retry/recovery suplimentar numai pentru un badge; dacă produsul oferă utilizare repetată, capacitatea/retirement devin criteriul consumerului respectiv.

**Adjudecare și execuție curentă:** [rezultatele scoped](p2-scope-audit-results-20261011.json) leagă cele două reviewuri APPROVED_SCOPED pe cele șapte fișiere `c6fcaa1`, reviewul typing/audit/metodologie pe cele zece fișiere `8b7529a` și lecția COPY pe `d7f1265`; părintele a comparat hashurile curente înainte de înregistrarea acestui rezultat. Nu este acceptare universală sau transfer al reviewului către cod schimbat.

Constructorul nativ real a trecut ulterior **o execuție directă a părintelui a probei independente neschimbate**, pe imagine izolată readonly/network-none/UID1000: un AIAgent/init_agent/configure_owned_core real, configurație/resurse reale, CREATE/STATUS/replay fără a doua alocare, refuz turn/client/unknown, mutație și closed core.29 hashes instalate (28 surse native/adaptor + proba), două controale observator, zero tentative reale pe canalul Python finit, exit0; CID propriu citit absent pe același daemon și imaginea de bază neschimbată. DATA/identitățile de authority din fixture sunt **manuale, sintetice și neîncrezute**, nu producer PostgreSQL/lease/Host grant. Este PASS_SCOPED al componentei pre-client, nu execuție independentă live, supervisor/stdio/PG end-to-end, client provider, tur sau închidere P2.

Cele două încercări QA anterioare rămân **BLOCKED/constructor NOT_RUN**: COPY root-owned0600 provoca Permission denied; după corecția exclusiv metadata, wrapperul cerea greșit UID1000 pe un director base root-owned0755, deși read/search efectiv trecea. Părintele a restrâns frontiera la consumerul real deja verificat, fără alt wrapper/verifier/rebuild sau modificare de produs. Cerința este accesul efectiv prin UID non-root, nu ownership uniform al părinților readonly moșteniți; nu am schimbat utilizatorul în root, rețeaua ori confinarea.

Primul canonical pe `f00deec` este **FAIL exit2/family_drained=true** la testul DTO netipat, cu resursa proprie absentă și date păstrate; remediul `8db3753` păstrează toate23 cazuri, mypy49→0/Ruff0. Canonicalul pe produsul/testele `8b7529a` s-a încheiat separat **FAIL exit2/drained**, cu **1387 API PASS /6 FAIL /1 skip**: toate cele șase regresii `test_native_task_control` primeau `data_approval:null` adăugat de extensia preflight pe comenzi legacy. CID/proiect/rețea proprii au fost citite absente și datele păstrate; nu mai există proces canonic activ din această execuție.

Părintele a reprodus exact **6 failed/8 passed**, apoi `8a353b8` exclude numai valoarea None din serializarea câmpului, asemenea celorlalte opționale; decizia non-null de preflight și refuzul ei pe release rămân probate. **57 teste afectate PASS, exit0**, inclusiv callback UDS autentic, Ruff check/format0 și mypy strict0, fără schimbarea testelor/gate-urilor. Ambele reviewuri complementare sunt **APPROVED_SCOPED** pe hashul exact al schemei `8a353b8`, comparat de părinte înainte de adjudecare: legacy/nonnull/caller/replay și strict input/auth/oracle. Reviewer1 a executat57 SOURCE/UDS +21 controale directe, reviewer2 a executat32 teste existente +33 controale de schemă; sunt frontiere/cazuri suprapuse, nu un total nou de teste unice. Receipturile și limitele sunt păstrate în JSON. **Full canonical pe acest ultim fix este NOT_RUN**, nu PASS derivat din57 sau din1387 de la revizia veche; nu se recertifică browserul/nativul neschimbat. `assessment_ready=false`, inferența HOLD, conturile/ținte/push neautorizate implicit. Acest fix al contractului IPC nu închide lipsurile de produs B06b/B06m.

## Lipsuri reale și ordinea de ieșire din buclă

1. **B06b:** `managed_contract.method_check` acceptă rezultatul rece `blocked_result` și returnează INCOMPLETE; `ManagedAdmission.reconcile` nu demonstrează o metodă nativă executată. Este necesar consumerul minim real de read/tool/result/check și compatibilitatea/replay/receive-only cerute de contract, nu al treilea tip de input. Refuzul explicit la lineage indisponibil este admis; compresia care cere model este probă live.
2. **B06m:** `budgets.reserve`/`mark_sent` există, dar nu au callerul de produs în model owner/sink. Următoarea integrare este ownerul existent → rezervă comisă → SENT durabil → transport inert declarat → receipt/UNKNOWN, cu Stop/caps/VALIDATION/retry/fallback la același consumer. Testul protocolului sintetic este legitim în P2-inert, dar nu se redenumește native turn sau provider inference.
3. **B06c:** proiecția/aprobarea/guardul integral DATA și SDK NO-IO au probe scoped. Proveniența/config/turn/purpose și requestul final legitim nu sunt implementate/probate prin simplul carrier. Guardul se consumă la integrarea precedentă; marker/DTO/ref nu acordă autoritate.
4. **P4a → P2-live:** Settings sigur, un provider/model explicit și save→readback, apoi un run/selection/manifest noi și un traseu nativ de inferență+skill fără ținte. Contul/modelul/datele/bugetul se aprobă separat. Nu cerem cont/live pentru închiderea inertă și nu „încălzim” un snapshot NO_MODEL.

Owned pre-client initialization este o pregătire pentru configurare, nu substitut al copilului/metodei sau admissionului și **nu devine o condiție circulară a G02-inert**. Continuarea acelui WIP se limitează la defectul concret și dovada consumerului afectat; nu extindem această ramură înainte de lipsurile canonice de mai sus. Confinarea, mappingul și safety core nu se mută la P7. Fault breadth integrat, editorul, catalogul larg, Jev/research/rework și alt provider nu blochează acest increment minim.

## Self-improvement și reguli de oprire

Metodologia se ajustează în skill-urile existente, nu prin cron/config global sau alt catalog:

- Autor + cel puțin un review independent pe bytes exacți implicit; arhitect/doi developeri numai când există decizie/interfețe ori livrabile independente. Două mandate complementare rămân obligatorii pentru authority/model/Stop/concurență/secrete/cross-runtime.
- Definește înainte un rând observabil, pozitiv/refuz pe același consumer, comenzi și limită. Fiecare test nou se leagă de cerința canonică sau de un defect reprodus. Nu promitem „zero gap” universal.
- După ultima editare: numai affected tests și re-review focalizat. QA pe consumerul real nou/afectat; browser numai UI afectată. Canonicalul real la limita integrării, niciodată alias pentru subset și nu rerun pentru Markdown/reminder.
- După două cicluri harness-only fără avans la același rând, păstrează WIP/BLOCKED și restrânge frontiera. Contorul nu se resetează printr-o sesiune nouă ori redenumirea probei. Un defect nou de safety se înregistrează ca blocker, nu se ignoră pentru buget.
- Un rezumat CURRENT, istoricul etichetat și trei axe cod/probe/review. Rapoartele scratch nu devin plan concurent; persistența de aici păstrează concluziile adjudecate, nu toate transcripturile/verificările auxiliare.

Reticle: **NOT_APPLICABLE** pentru auditul de cod/proces fără UI. Chisel: **BLOCKED_NO_GO** păstrat, utilizate uneltele native. Nici prezența skill-ului, nici numărul reviewerilor nu reprezintă o probă de produs.
