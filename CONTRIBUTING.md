# Dezvoltarea OmnisAI

Acest fișier descrie modul de lucru; arhitectura și planul din `documents/` rămân singurul baseline de produs. Regula obligatorie de istoric granular este în [AGENTS.md](AGENTS.md).

## Hermes: configurare mică, skill-uri la cerere

Skill-urile de dezvoltare trăiesc în `.hermes/skills/`, versionate împreună cu proiectul. Hermes le descoperă numai în proiectele trusted și numai când sesiunea este legată de checkout; în rest nu încarcă această metodologie peste alte proiecte.[1]

`AGENTS.md` este locul regulilor de proiect; `SOUL.md` este identitatea globală și nu a fost modificat. Loaderul instalat a fost verificat direct: încarcă regula inclusiv din subdirectorul `tests/documentation`. Nu adăugăm o a doua sursă `.hermes.md`.[2]

După revizuirea skill-urilor, activarea pe un checkout nou se face cu:

```sh
hermes skills trust /cale/catre/OmnisAI
```

După activare, pornește o sesiune legată explicit de repo:

```sh
python scripts/hermes_dev.py
```

Launcherul păstrează profilul activ și fixează atât cwd, cât și `TERMINAL_CWD`; simplul `cd` al unui subprocess poate moșteni încă directorul sesiunii părinte. `python scripts/hermes_dev.py --check` afișează planul fără model; nu afișează mediul, dar **afișează argumentele integral**, deci nu îi da secrete în argv. `--version` verifică executabilul real fără chat. Sesiunea curentă nu este repornită și nu pretindem că indexul ei inițial s-a regenerat.

Profilul activ default are `agent.verify_on_stop=true`: un reminder bounded când codul editat nu are dovadă proaspătă de verificare, **nu** un executor de teste sau enforcement al commiturilor.[6] Modificările, valorile precedente nesensibile și comenzile inverse sunt în [hermes-settings.json](tools/development/hermes-settings.json). Nu versionăm configurația privată a profilului.

Păstrăm modelul/providerul, politica de aprobări, limitele globale de delegare și checkpointurile existente. Nu activăm cron, auto-commit, memorie externă, servere publice sau zeci de MCP-uri la startup. Mai multe instrucțiuni nu sunt automat o configurație mai bună; contextul de proiect este scurt, procedurile se încarcă la nevoie.[1][3]

## Contractul unei felii

1. **Scop:** ticket, comportament observabil, non-obiective, fișiere și gate.
2. **Dovadă:** test RED/reproducer și control negativ; comenzi exacte pentru GREEN/regresii.
3. **Implementare minimă:** o felie verticală, fără refactor independent sau dependență oportunistă.
4. **Review:** conformitate, apoi corectitudine/securitate. Pentru cod relevant, reviewer independent read-only. Părintele reproduce constatările importante.
5. **Commit imediat:** schimbare coerentă + teste/documentație necesară, cu motiv, verificări, încercări eșuate relevante și rollback.
6. **Readback:** SHA/diff/status; raport scurt cu ce este implementat, verificat, neexecutat și blocat.

Template-ul de sarcină și roluri este în [.hermes/skills/omnis-delivery/templates/task.md](.hermes/skills/omnis-delivery/templates/task.md). Nu folosim un prompt monolitic de „expert perfect”; lucrăm cu criterii falsificabile și rezultate măsurabile.

## Acoperirea implementării

| Activitate | Skill de încărcat |
|---|---|
| Felie verticală, TDD, coordonare, reluare | `omnis-delivery` |
| API, PostgreSQL, migrații, evenimente/evidence | `omnis-api-data` |
| Hermes nativ, copii, Settings, skills per run, recuperare | `omnis-hermes-runtime` |
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

Comanda canonică este `make check` (alias `make test`); rulează documente/development/anti-slop, API/PostgreSQL/pairing/control/supervisor + wheel/procese instalate, Ruff/mypy strict și bootstrapul web P0.3: contracte/drift, lint/typecheck/unit/build, E2E cu backend real. Instalează întâi [uneltele de dezvoltare](tools/development/README.md), [DB-ul izolat](api/README.md) și [mediul web/browser fixat](web/README.md); lipsa lor eșuează, nu este skip. Nu este certificarea P0.4/G00, a assessmentului sau a Chisel. Proba Reticle este separată, cu rezultate proprii.

Comenzile individuale, pentru investigații țintite:

```sh
python scripts/render_docs.py --check
python -m unittest discover -s tests/documentation -v
python -m unittest discover -s tests/development -v
python tests/documentation/browser_check.py --include-documents --output <scratch>/browser-check.json
git diff --check
```

Comenzile se adaugă odată cu componentele: comenzile API de mai sus păstrează P0.1/P0.2; `make check-web`, `make lint-web`, `make typecheck-web`, `make test-web`, `make build-web`, `make test-contracts` și `make test-e2e` acoperă P0.3. `make generate-contracts` este explicit, nu reparare automată în check. Verificările nu instalează unelte și nu fac autofix; pinurile sunt fixate în medii separate. Testele selectează checkoutul curent, nu alt worktree din variabile ambientale. Probele sintetice nu fac scanări și nu consumă conturi LLM. `df17a29` este **VISUAL_ACCEPTED**, implementarea P0.1/P0.2/P0.3 a fost autorizată; `P0.3_IMPLEMENTED_LOCAL` nu închide G00 sau autorizează P0.4/LLM/ținte. Vezi plan §19 și [dovezile P0.3](documents/verification/p03-local-bootstrap.md).

## Sources

[1] https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
[3] https://hermes-agent.nousresearch.com/docs/guides/tips
[4] https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback
[5] https://hermes-agent.nousresearch.com/docs/user-guide/git-worktrees
[6] https://hermes-agent.nousresearch.com/docs/user-guide/configuration
