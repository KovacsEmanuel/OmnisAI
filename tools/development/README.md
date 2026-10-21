# Unelte pentru dezvoltarea Omnis

Aceste unelte sunt separate de aplicație și de catalogul runtime de pentest. Nu înlocuiesc planul din `documents/` și nu sunt MCP-uri globale pornite automat.

| Sursă cerută | Integrare și stare | Dovadă / procedură |
|---|---|---|
| [Reticle](https://github.com/reticlehq/reticle) | Helper local izolat, pin `@reticlehq/server@3.2.0`; MCP direct verificat pe fixture. Nu este încă instrumentarea aplicației. | [Setup, licență și limite](reticle/README.md); [rezultat MCP](reticle/verification/mcp-smoke.json); [CLI reload nereușit](reticle/verification/cli-reload-failure.json) |
| [Chisel](https://github.com/ckanthony/Chisel/tree/main) | **NO-GO**, skill de evaluare prezent, server dezactivat/neînregistrat. Folosim uneltele native de fișiere. | [Motive și criterii de reevaluare](chisel/README.md); [probe reale individuale](chisel/audit.json) |
| [ui-skills](https://github.com/ibelick/ui-skills) | Trei skill-uri adaptate pentru frontend, accesibilitate și performanță; surse/MIT fixate, fără CLI/registry live. | `.hermes/skills/omnis-frontend`, `omnis-accessibility`, `omnis-frontend-performance`, fiecare cu `references/upstream.json` |
| [anti-slop](https://github.com/dmmulroy/anti-slop) | Trei reguli Oxlint selectate și executabile; fără politici care interzic validarea la boundary. | [Setup, policy și regresii](anti-slop/README.md); [proveniență](anti-slop/upstream.json) |
| [Ponytail](https://github.com/DietrichGebert/ponytail) | Pluginul nativ Hermes v5.3.1, pin `6f1c2bfff0c837d268929a7c4e490918eb4fab29`, instalat și activat în profilul `default`; mod implicit `full`, șase skills și șase comenzi. | [Instalare, probe, limite și rollback](ponytail.json) |

## Intrarea standard

[Inventarul curent al celor 13 skill-uri](skills-manifest.json) enumeră versiunile și SHA-256 ale bytes verificați. [QA nativă fără inferență](../../documents/verification/api-key-migration-evidence/governance-native-load.json) a citit toate cele 13 skill-uri și 20 de fișiere de suport; AGENTS a fost încărcat integral din root și subdirector. Scannerul a returnat 12 `safe` și un `caution`: avertismentul `/proc/self/fd` este păstrat și adjudecat ca lecție de observare a FD-urilor, nu ascuns prin rescriere. Snapshotul vechi cu12intrări și calificările sale rămân istorice în Git. Proba actuală nu certifică produsul sau comportamentul viitor al modelelor.

Hermes/Codex rămân unelte de dezvoltare; noul produs API-key-only nu cere Hermes runtime. Launcherul `python -B scripts/hermes_dev.py --check` proiectează cwd/argv fără model; nu îi da secrete în argv. În candidatul exportat fără Git, verificarea repo-bound reală revine integrării.

Pentru editări ale instrucțiunilor:

```sh
python -B -m unittest discover -s tests/documentation -v
python -B scripts/render_docs.py --check
```

Acestea sunt verificări de drift/integritate documentară, nu acceptare de produs sau dovadă că modelele vor respecta instrucțiunile. `make check` actual include consumatori API/DB/web/runtime și efecte disposable; folosește-l numai la frontiera relevantă cu autorizația/prerechizitele sale, nu pentru metadata. Anti-slop se instalează din lock numai când mediul necesar lipsește; smoke-ul se repetă la schimbarea uneltei/configurației ori defect concret. Reticle este opt-in pentru UI instrumentată afectată; Chisel rămâne NO-GO. Browserul se folosește pentru UI afectată, nu pentru această editare de proceduri.

### QA nativă după integrare — procedură

Folosește un proces fresh legat explicit de checkoutul integrat și un HOME/HERMES_HOME temporar gol, cu trust configurat prin setterul nativ numai în fixture: readiness-ul `skill_view` citește `.env` al profilului chiar și fără cerințe de credentiale. Fără chat/inferență, verifică descoperirea exactă a celor13nume, citirea bytes fiecărui `SKILL.md` și scannerul instalat. Include AGENTS/contextul din root și subdirector. Citește schema/API-ul și forma rezultatului înainte de execuție: `_read_context_file` elimină whitespace-ul marginal prin `strip()`, nu conținutul intern. Păstrează comparația integrală și refuzul conținutului gol/blocat; o nepotrivire de formatare a observatorului nu este defect al instrucțiunilor. Nu activa skills de produs/importate și nu crea alt framework de verificare.

Înregistrează HEAD, identitatea loaderului/scannerului, comanda reală/exit, rezultatele per skill și limitele. Compară SHA manifestului cu fișierele integrate înainte și după. Numai după proba efectivă actualizează `native_read` (`PASS`/`NOT_RUN`), `scanner_verdict` (`safe`/`caution`/`BLOCKED`/`NOT_RUN`), `tested_sha256`, `checked_at_utc`, `evidence` și calificarea scoped; `caution` păstrează constatarea și adjudecarea, nu devine `safe`. Nu promova o parte neexercitată. Recalculează count/path/version/SHA dacă se schimbă instrucțiunile; schimbarea unui fișier de suport invalidează scanarea acelei revizii chiar dacă SKILL.md rămâne identic. Refolosește proba neschimbată când se adaugă doar metadata/readback; nu rerula loaderul pentru un raport nou. QA a folosit profiluri disposable, fără mutații în SOUL/configul global; procesul TUI deja deschis nu este reîncărcat implicit.

## Actualizare și rollback

- Nu instala întregul catalog, nu rula scripturi remote și nu înlocui stackul după preferințele unui skill importat.
- Păstrează SHA-uri, lockfiles, licențe și override-uri; testează controlul pozitiv și negativ înainte de a avansa o versiune.
- Corectează procedura pe baza eșecurilor reale și păstrează remedierea în commit separat când modifică independent comportamentul.
- [Setările Hermes și inversele lor](hermes-settings.json) sunt distincte de revert Git. Modelul/providerul și SOUL nu au fost schimbate. Skill-urile de dezvoltare sunt încărcate la cerere în checkoutul trusted.
- Ponytail este excepția autorizată de context automat: hookul nativ aplică modul activ la tururile agentului de dezvoltare, în toate sesiunile profilului `default`, nu în runtime-ul Omnis. Nu duplicăm regulile sale în `omnis-delivery`. După instalare repornește Hermes; `/ponytail` arată nivelul, iar `/ponytail lite|full|ultra|off` îl schimbă în procesul curent. Skills originale sunt `ponytail:ponytail`, `ponytail:ponytail-review`, `ponytail:ponytail-audit`, `ponytail:ponytail-debt`, `ponytail:ponytail-gain` și `ponytail:ponytail-help`. Probele sunt de loader/hook/cozi CLI, fără inferență sau validarea interfeței Ink TUI după restart; scannerul și regulile Omnis rămân active.
