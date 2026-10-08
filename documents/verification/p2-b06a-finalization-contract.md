# B06a — contract bounded de finalizare

## Bază și autorizare

Bază verificată: `19f4e63c1b7df2e5af7e4fdb104e4761b32e004c`, branch `p04-control-topology-wip`, tracked/staged clean. Singurul untracked este HTML-ul original protejat, necitit/necopiat/nehashuit/neadoptat. Worktree-urile istorice sunt identificate, nu baze de implementare. Canonicalul `proc_d7959ebd95a8` rămâne settled/PASS istoric; nu se relansează fără schimbare de produs.

Autoritate: plan §4.2/SL08, §7/B06a, §19; arhitectură §9.3–9.4/§9.8–9.9. Acesta este contractul aceleiași SL08, nu un plan sau audit concurent. Mandatul operatorului permite material sintetic, migrații necesare, PostgreSQL disposable și procese locale proprii STATIC/PURE. Nu permite Publish, seed selectabil, B06b/Task/Attempt/copil/model/provider/target/r1/rollout/global config/push.

## Reconciliere cerință → cod → probă → review

| Cerință | Cod la bază | Probe/review la bază | Dispoziție bounded |
|---|---|---|---|
| Capture/source refs/rezervări/material read-only separat | IMPLEMENTED: candidate_catalog/store/material, schema0009 | PG/readback/restart și reviewuri scoped istorice | Nu reimplementăm; extindem probele afectate |
| RELEASE calificat nevid și closure tranzitivă | NOT_IMPLEMENTED: toate RELEASE refuzate; closure impusă goală | Negative source numai; fără pozitiv RELEASE | Blocker real B06a: loader read-only și index/dependencies exacte |
| Identități și index complet | PARTIAL: refs calificate source și rezervări durabile | Hash/index/fingerprints bounded | Legăm refs calificate de IDs/revizii/digests rezervate și external closure |
| LOCAL/profile/slots/StepOutput | IMPLEMENTED seed subset | Source controls bounded; alpha/beta probează schema, nu procedure IDs | Matrice pozitivă/negativă durabilă; bindingul runtime/case/attempt este B06b, nu stub aici |
| STATIC/PURE/input BLOCKED/receipts/replay | IMPLEMENTED pe closure goală | PG și restart fresh-process; review findings scoped | Verificare pe aceeași closure nevidă și bytes finali |
| Concurrency/failure windows | Implementare de lock/fsync/rename/commit existentă | Capture overlap și freeze exception seams, breadth PARTIAL | Overlap real PG pentru freeze/reject/review/eval; rollback și response-drop produs real |
| Installed durable consumer | Consumator CLI existent | Wheel import/CLI status nu sunt journey; installed B06a-1 istoric | QA independentă completă în afara checkoutului pe artefact final |
| Schema/gates | 0009 aliniată/upgrade demonstrat | Canonical settled exit0/drained istoric | Fără rerun neschimbat; make check după ultimul produs schimbat |

Arhitectul read-only a inspectat snapshotul exact; concluziile statice au fost comparate de părinte cu codul. Raportul scratch `b06a-architect-19f4e63-84ba4887/report.json` nu este probă runtime sau aprobare. Depășirea bugetului strict de subapeluri al arhitectului rămâne limită procedurală, nu execuție declarată conformă.

## Decizia de fixture și frontiera de autoritate

În mandatul de material sintetic, părintele admite **numai în fixture-ul PostgreSQL nou, privat, test-only** artefacte externe sintetice immutable, calificate prin checkerul STATIC/PURE real. Nu redenumim CandidateSnapshot nepublicat ca RELEASE, nu publicăm seed-ul și nu implementăm Publish. Fixture producerul este în teste, în afara CLI-ului/runtime-ului de produs; nu autoritate din YAML/request, nu latest și nu adopție DB. Loaderul de produs este exclusiv read-only, verifică bindingurile/bytes/refs/calificarea backend existente și refuză când inventarul lipsește. Această probă califică mecanica rezoluției RELEASE/closure, nu Publish/selectabilitatea care aparțin B06b.

## Ownership și acceptare

- Dev A: settings compiler/model/index/catalog/store/material și helper read-only îngust dacă necesar; fără seed/profil/web/CLI/Hermes/istorice.
- Dev B: teste/fixtures B06a independente și probe PG bounded; fără api/src. Worktree-uri noi explicit din HEAD local verificat. Părintele integrează exact, verifică/comite și deține runnerul/cleanupul.
- Pozitive RELEASE prin pachet și profil; negative unknown/kind/id/revision/digest/package/compatibility/shadow/path/cycle. Closure deterministică, tranzitivă și deduplicată, fără selectors source rămași în index; slot/StepOutput rămân template-uri explicite, nu dispatch fictiv.
- Review → freeze → STATIC/PURE → input/receipt persistent → replay → proces nou/readback păstrează bytes/material/index/closure/identități; workspace mutat/eliminat nu afectează frozen material. NO_MODEL/effective=null/assessment_selectable=false.
- Overlap se observă prin backend PID și pg_blocking_pids, nu două apeluri succesive. Failure seams disting înainte/după fsync/rename/INSERT/commit; rollback fără succes și orfani inerți neadoptați. Response-drop după commit trebuie produs efectiv, apoi replay fresh-process exact.
- Două reviewuri independente complementare pe snapshot integrat exact; blockers reproduși RED→fix minimal→GREEN și re-review focalizat. QA independentă installed după blockers, canonical final și cleanup readback exact.

## Limite și predare

Physical power-loss/crash fizic rămân NOT_RUN dacă nu sunt executate; excepțiile/cancellation nu le demonstrează. Protocolul blob/target IO B07, runtime case binding/MethodPlan B06b, model/admission B06m/P4a și SECURITY fixture qualification B11/B12 nu sunt obligații implementabile prin extinderea acestei felii. Reticle NOT_APPLICABLE pentru CLI/backend; Chisel BLOCKED_NO_GO, neinvocat. Nu inventăm Settings UI pentru consumatorul CLI-only; QA browser a unei schimbări UI ar fi obligatorie dacă apare.

P0/G00, P1/G01, B05-inert și B04 hydration rămân acceptări istorice distincte. FAIL/UNCERTAIN/CHANGES_REQUESTED/NOT_PASS, incidentul NOT_PASS_PROTOCOL și helperul UNVERIFIED/NOT_PASS se păstrează. B06a/G-MODULE-core/G02 rămân NOT_CLOSED până la adjudecarea criteriilor; G02 nu se închide automat.

Rollback: revert granular al codului/testelor/documentelor; nu șterge/reclamă rezervări, artefacte private, PGDATA/loguri/imagini sau istoric. Numai resursele create și atestate în execuția curentă se retrag prin runnerul existent; fără DB adoptată/TCP fallback/supervisor paralel.
