# Dezvoltarea OmnisAI

Direcția noului produs și limita înainte de T0 sunt în AGENTS/README; Hermes/Codex sunt unelte de dezvoltare, nu dependențe ale noului runtime. Acest fișier descrie modul de lucru; arhitectura și planul din `documents/` rămân singurul baseline de produs. Regula obligatorie de istoric granular este în [AGENTS.md](AGENTS.md).

## Unelte de dezvoltare: Hermes/Codex, skill-uri la cerere

Skill-urile de dezvoltare trăiesc în `.hermes/skills/`, versionate împreună cu proiectul. Hermes le descoperă numai în proiectele trusted și numai când sesiunea este legată de checkout; în rest nu încarcă această metodologie peste alte proiecte.[1]

`AGENTS.md` este locul regulilor de proiect: reviewul independent pe bytes exacți duce la remediere, rerulare și re-review când apar blocante, până la acceptare scoped sau raportarea unui blocker real. `SOUL.md` rămâne identitatea globală și păstrează același principiu general, fără a pretinde absența absolută a gap-urilor. Istoric, loaderul instalat a fost verificat inclusiv din subdirectorul `tests/documentation`; citirea/scanarea bytes curenți rămâne NOT_RUN până la QA fresh descrisă în tools/development/README.md. Nu adăugăm o a doua sursă `.hermes.md`.[2]

După revizuirea skill-urilor, activarea pe un checkout nou se face cu:

```sh
hermes skills trust /cale/catre/OmnisAI
```

Dacă folosești Hermes pentru dezvoltare, după activare pornește o sesiune legată explicit de repo (Codex rămâne de asemenea tooling valid):

```sh
python scripts/hermes_dev.py
```

Launcherul păstrează profilul activ și fixează atât cwd, cât și `TERMINAL_CWD`; simplul `cd` al unui subprocess poate moșteni încă directorul sesiunii părinte. `python scripts/hermes_dev.py --check` afișează planul fără model; nu afișează mediul, dar **afișează argumentele integral**, deci nu îi da secrete în argv. `--version` verifică executabilul real fără chat. Sesiunea curentă nu este repornită și nu pretindem că indexul ei inițial s-a regenerat.

Profilul activ default are acum **`agent.verify_on_stop=false`**, conform cererii utilizatorului de a aplica global lecția despre overhead: reminderul automat opțional a produs verificatori/rerulări pentru rapoarte deja verificate. **Testele reale, reviewul independent, verificarea efectelor și porțile proiectului rămân obligatorii**; oprirea reminderului nu le certifică sau elimină.[6] Valorile nesensibile before/after, readbackul CLI/guardului nativ și inversa sunt în [hermes-settings.json](tools/development/hermes-settings.json). Nu ștergem ledgerul, nu schimbăm hookuri/approvals/security și nu versionăm configurația privată a profilului. SOUL și skill-urile globale default conțin stilul product-first; acestea nu garantează automat conformitatea viitoare.

Păstrăm modelul/providerul, politica de aprobări, limitele globale de delegare și checkpointurile existente. Nu activăm cron, auto-commit, memorie externă, servere publice sau zeci de MCP-uri la startup. Mai multe instrucțiuni nu sunt automat o configurație mai bună; contextul de proiect este scurt, procedurile se încarcă la nevoie.[1][3]

## Contractul unei felii

1. **Scop:** ticket, comportament observabil, non-obiective, fișiere și gate.
2. **Dovadă:** test RED/reproducer și control negativ; comenzi exacte pentru GREEN/regresii.
3. **Implementare minimă:** o felie verticală, fără refactor independent sau dependență oportunistă.
4. **Review:** conformitate, apoi corectitudine/securitate. Pentru cod relevant, reviewer independent read-only. Părintele reproduce constatările importante.
5. **Commit imediat:** schimbare coerentă + teste/documentație necesară, cu motiv, verificări, încercări eșuate relevante și rollback.
6. **Readback:** SHA/diff/status; raport scurt cu ce este implementat, verificat, neexecutat și blocat, cu status prin `omnis-project-status` la predarea relevantă.

Template-ul de sarcină și roluri este în [.hermes/skills/omnis-delivery/templates/task.md](.hermes/skills/omnis-delivery/templates/task.md). Nu folosim un prompt monolitic de „expert perfect”; lucrăm cu criterii falsificabile și rezultate măsurabile.

### Echipă proporțională cu felia de implementare

Aplică [team-slice](.hermes/skills/omnis-delivery/templates/team-slice.md), sursa pentru ownership, FREEZE, review și QA. Commitul candidat verificat nu este acceptare; părintele integrează și comite granular. Developerul desemnat remediază findings reproduse/adjudecate de părinte.

## Execuție orientată spre produs

Acest contract elimină munca auxiliară fără rezultat, nu probele obligatorii. Se aplică autorului, reviewerului și părintelui; nu schimbă porțile planului, autorizațiile, reviewurile complementare sau raportarea FAIL/BLOCKED. Instrucțiunile nu sunt enforcement automat al comportamentului agentului.

### Admiterea verificării

- Înaintea unui test, review, build sau verificări auxiliare, numește scurt **cerință → consumer → risc → decizie**: obligația canonică/defectul concret, callerul real, ce eroare poate detecta și ce acțiune schimbă PASS/FAIL. Folosește contractul existent/mesajul commitului, nu un raport nou pentru fiecare comandă. Dacă niciuna dintre decizii nu se schimbă și nu este o verificare obligatorie de integritate/cleanup, nu executa lucrarea.
- Livrează o felie verticală prin callerul existent până la persistență/readback/sink. Helpers, SOURCE și doubles sunt prerechizite, nu finalizarea consumerului. După minimum SOURCE și reviewurile obligatorii, execută prima probă reală bounded a feliei înainte să acumulezi alte componente sau breadth de fixture-uri. Codul, testele și documentația inseparabilă pot fi același commit coerent; remediile independente rămân separate.
- Nu porni un verifier pentru verifier, audit general, wrapper/owner/harness nou sau rescriere a probei fără defect concret și legătură cu acceptance row. Validarea JSON/hash și citirea resurselor proprii necesare predării rămân obligatorii; execută-le direct, fără strat auxiliar recursiv. Reviewerii păstrează findings reale, nu cer completitudine universală sau un inventar nou de scenarii fără obligație canonică.
- Pe bytes/call-sites neafectate reutilizează dovada scoped. După editare rulează affected checks și re-review delta; după fix admiterea unei probe fresh cere cauza identificată și controlul care o verifică, nu retry până verde. Canonicalul complet este la frontiera finală de integrare/fază; un FAIL concret permite remediu și rerun afectat, nu un PASS transferat sau un gate slăbit. Browser numai pentru UI/call path afectat. Reminderul repetat ori notificarea întârziată nu deschide muncă nouă.

### Preflight fără efecte

- Înainte de o tentativă PG/native/browser: verifică **comanda/argv** și choices/opt-in ale runnerului existent, collect-only dacă este disponibil, source/library/pin și accesul UID/căile/mounturile necesare. Verifică schema/oracle-ul pe producerul real: **pozitiv și negativ** pe același canal, reason/exit exacte, census al tuturor tabelelor modificate și ordinea tranzacțiilor. Label SOURCE/synthetic rămâne explicit; nu prewarm și nu provider/network/DB effects ca substitut pentru preflight.
- Pregătește înaintea lansării deadline-ul bounded, ownerul/fixture-ul fresh, settlementul/cleanupul exact și lista mică de câmpuri nesensibile care pot fi citite la eșec. Nu inventa expected fields, targeturi CLI, DSN-uri sau cauza unui FAIL neobservat. Pe un preflight FAIL nu lansa consumerul; repară numai prerechizitul demonstrat, apoi consemnează o tentativă distinctă.
- După primul eșec de harness, localizează mecanismul și restrânge proba înainte de încă un efect. După două cicluri numai harness fără progres pe aceeași acceptance row, oprește acea frontieră ca BLOCKED/NOT_RUN; fără al treilea verifier, buget resetat prin sesiune nouă sau abandonarea findingului. Nu trece cu felii dependente peste un blocker de siguranță.

În aceeași acceptance row din task se păstrează: ultimul progres de produs, cicluri harness-only 0/1/2 și următoarea decizie; acestea se transferă între sesiuni, fără registru sau infrastructură nouă.

### Continuitate și dovezi

- Un commit coerent nu încheie mandatul. Continuă următoarea felie admisă fără reaprobări cosmetice; predare numai la rezultatul cerut, blocker real, limita de autorizație, cererea utilizatorului ori imposibilitatea sigură de a continua în buget/context. Nu transforma fiecare fix/review/raport în checkpoint separat al conversației.
- Actualizează **în loc** CURRENT și rândurile afectate, nu încă un paragraf CURRENT repetând întreg istoricul. Păstrează snapshotul, findingurile, probele și limitele într-un singur registru existent al feliei; rapoartele originale obligatorii se transferă byte-exact o singură dată și se citează, nu se reconstruiesc sau se multiplică. Nu introduce raport ori serviciu pentru a valida alt raport. Git/context recovery rezolvă informația lipsă; nu relua acceptări doar pentru că s-a compactat conversația.
- Citirile/delegările sunt limitate la CURRENT, contractul activ și definițiile/usages afectate. Trimite copiilor fișierele/criteriul/prerechizitele și bugetul, nu istoricul integral. La predare: starea produsului, probe/review, commit, blocker și următoarea acțiune concretă; matricea globală rămâne compactă, nu este repetată după fiecare apel sau mesaj async duplicat.

## Status global la orientare și predare

[omnis-project-status](.hermes/skills/omnis-project-status/SKILL.md) definește ORIENT minim și CLOSE la predare reală/milestone/schimbare de status sau cerere. Matricea se afișează atunci direct în chat; nu la fiecare răspuns scurt. Harta păstrează cod/probe/review distincte și toate SL/E ca proiecție, nu backlog concurent. Read-only nu cere editări, teste docs sau commit gol. Notificările întârziate nu redeschid munca.

## Acoperirea implementării

| Activitate | Skill de încărcat |
|---|---|
| Orientare și status global la fiecare predare/review | `omnis-project-status` |
| Felie verticală, TDD, coordonare, reluare | `omnis-delivery` |
| API, PostgreSQL, migrații, evenimente/evidence | `omnis-api-data` |
| Runtime nou API-key-only | `omnis-delivery`, `omnis-api-data`, `omnis-review-qa` |
| Mentenanță istorică Hermes, numai la cerere explicită | `omnis-hermes-runtime` (LEGACY) |
| Scope/egress/auth, validatori, fault injection/evaluare | `omnis-safety-evaluation` |
| Review independent, regresii, QA și raportare sinceră | `omnis-review-qa` |
| Interfață de la referință, React și stări reale | `omnis-frontend` |
| Keyboard, focus, formulare, overlay-uri și contrast | `omnis-accessibility` |
| Măsurători de render, streaming, memorie și motion | `omnis-frontend-performance` |
| QA runtime local instrumentat, cu limite explicite | `omnis-reticle` |
| Reguli executabile împotriva casturilor fără dovezi | `omnis-anti-slop` |
| Reevaluare adaptor de fișiere — **NO-GO curent** | `omnis-chisel` |
| Pinning, CI, build, release, backup/restore | `omnis-release-ops` |

Nu încărca toate skill-urile în fiecare tură. Citește numai procedura necesară feliei. Skills existente precum `test-driven-development`, `systematic-debugging`, `hermes-agent` și `design-md` completează procedurile, nu înlocuiesc criteriile Omnis.

Reticle se încarcă numai pentru probe UI locale instrumentate și admise; CLI/docs sunt `NOT_APPLICABLE`, UI neinstrumentată `NOT_INTEGRATED`. Chisel rămâne **NO-GO / `BLOCKED_NO_GO`** pe repo/home/profil runtime; skill-ul se încarcă numai pentru reevaluare de adopție autorizată explicit, pe fixture disposable izolat OS, fără fallback nesandboxat/înregistrare automată. O etichetă de applicability în raport este suficientă când nu se aplică; nici încărcarea ceremonială, nici un smoke sintetic repetat nu sunt review sau PASS de produs.

## Paralelizare fără pierdere de context

Un orchestrator; implicit cel mult trei activități independente. Citirile, auditul și review-ul pot rula în paralel. Scrierea concurentă cere fișiere explicit disjuncte sau worktree separat; fără doi autori în același index Git.

Pentru un worktree de implementare pornim explicit din SHA-ul local verificat:

```sh
git worktree add -b <ramura> <cale-noua> HEAD
```

Nu folosim implicit baza remote: `hermes -w` poate porni din remote-ul proaspăt fetch-uit, iar commiturile locale Omnis pot să nu fie împinse încă.[5] Noul worktree are propria decizie de trust. Părintele integrează prin commituri păstrate și verificări, nu prin copii neatribuite de fișiere.

## Istoric și revert

Commit după fiecare schimbare coerentă, inclusiv o corecție independentă de o linie. Nu după fiecare citire sau comandă fără efect și nu un commit „tot ce am făcut azi”. Commiturile normale rămân verzi; RED și experimentele respinse sunt consemnate în corpul commitului sau pe ramura experimentală.

```text
<tip>: <schimbare coerentă>

Why: motiv și alternative relevante respinse.
Verification: comenzi, rezultate reale și control negativ.
Limits: ce nu s-a testat / ce rămâne blocat.
Rollback: revert și efecte externe care cer pași separați.
```

Pentru rollback inspectăm `git show <sha>` și dependențele, folosim `git revert <sha>`, apoi rerulăm criteriile. Nu rescriem istoria. Snapshoturile Hermes sunt doar o posibilă plasă locală suplimentară, nu înlocuitor al commiturilor și nici rollback pentru DB/servicii.[4]

## Verificări disponibile acum

**Prerechizit DB integrat cu acord explicit:** `make check`/`make test` folosesc runnerul comun UDS/no-network și un root/proiect nou per execuție, nu conftest TCP sau o DB aleasă manual. [Dovezile integrării](documents/verification/p04-test-db-integration.md) disting probele țintite, gate-ul complet și cleanup-ul familiei proprii. Medii/pinuri lipsă refuză provisioningul; G00 local este CLOSED_SCOPED; CI remote rămâne separat, conform [adjudecării SL04](documents/verification/p04-stop-recovery.md). Pentru documentare sunt suficiente comenzile docs/browser, fără promovare runtime. Contractele HF01–HF10/NS01–NS19 rămân specificații ale funcțiilor viitoare.

Comanda canonică este `make check` (alias `make test`); rulează documente/development/anti-slop, API/PostgreSQL/pairing/control/supervisor + wheel/procese instalate, Ruff/mypy strict și bootstrapul web P0.3: contracte/drift, lint/typecheck/unit/build, E2E cu backend real. Instalează întâi [uneltele de dezvoltare](tools/development/README.md), [DB-ul izolat](api/README.md) și [mediul web/browser fixat](web/README.md); lipsa lor eșuează, nu este skip. Nu este certificarea P0.4/G00, a assessmentului sau a Chisel. Proba Reticle este separată, cu rezultate proprii.

Comenzile individuale, pentru investigații țintite:

```sh
python scripts/render_docs.py --check
python -m unittest discover -s tests/documentation -v
python -m unittest discover -s tests/development -v
python tests/documentation/browser_check.py --include-documents --output <scratch>/browser-check.json
git diff --check
```

Comenzile se adaugă odată cu componentele: comenzile API de mai sus păstrează P0.1/P0.2; `make check-web`, `make lint-web`, `make typecheck-web`, `make test-web`, `make build-web`, `make test-contracts` și `make test-e2e` acoperă P0.3. `make generate-contracts` este explicit, nu reparare automată în check. Verificările nu instalează unelte și nu fac autofix; pinurile sunt fixate în medii separate. Testele selectează checkoutul curent, nu alt worktree din variabile ambientale. Probele sintetice nu fac scanări și nu consumă conturi LLM. `df17a29` este **VISUAL_ACCEPTED**, implementarea P0.1/P0.2/P0.3 a fost autorizată; `P0.3_IMPLEMENTED_LOCAL` nu închide G00; P0.4 are autorizare separată deja înregistrată, fără LLM/ținte sau integrare tacită a WIP. Vezi plan §19 și [dovezile P0.3](documents/verification/p03-local-bootstrap.md).

## Sources

[1] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
[3] https://hermes-agent.nousresearch.com/docs/guides/tips
[4] https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback
[5] https://hermes-agent.nousresearch.com/docs/user-guide/git-worktrees
[6] https://hermes-agent.nousresearch.com/docs/user-guide/configuration
