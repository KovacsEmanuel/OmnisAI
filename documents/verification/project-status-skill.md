# Skill de orientare și predare: contract de schimbare

## Contract înainte de editări

Bază inspectată: `4113c785ae8cacccb44ba8db79e1805d271c21dd`, branch `p04-control-topology-wip`, tracked curat. Singurul untracked preexistent este `documents/Omnis_Notite_Originale.html`; nu se modifică și nu se stage-uiește.

**Obiectiv:** un skill de dezvoltare `omnis-project-status`, utilizabil read-only pentru orientare și la închiderea fiecărei felii/subfaze/faze sau sesiuni de review. Predarea include statusul global derivat din Git și memoria versionată a proiectului: implementare, probe, review, blocante, următoarea felie și perspectiva MVP/post-MVP. Harta este o proiecție a planului, nu un plan concurent.

**Fișiere:** noul skill și template-ul său; `documents/verification/implementation-status.md`; teste documentare de acoperire/contract; legături în README, CONTRIBUTING, indexul verification și skill-urile delivery/review. O regulă scurtă de predare în AGENTS numai dacă mecanismul de protecție permite editarea; statusul vizual istoric protejat nu face parte din schimbare.

**Acceptare:** toate ID-urile SL și E ale planului apar exact o dată în hartă; fundațiile, milestone-urile, ramurile MVP și capabilitățile execution-unscheduled sunt distincte; implementat/PASS/review aprobat nu sunt confundate. Skill-ul cere Git real, dovezi pe revizie/scope și adjudecare de către părinte, tratează notificările vechi fără a redeschide automat review-ul și actualizează numai diferențele justificate. Orientarea fără schimbări nu produce scrieri/commituri goale. Se verifică descoperirea într-un proces Hermes proaspăt legat de repo, fără model/provider.

**Non-goals:** modificări de produs, noi faze, procente/termene inventate, un motor de project management, auto-commit/cron/hooks, reevaluare live Docker/DB/LLM/ținte sau schimbarea profilului personal. Un skill este o procedură încărcată de agent, nu enforcement ori garanție de execuție automată. Cererea anterioară de retrospectivă globală Hermes nu este declarată închisă prin acest skill suplimentar.

**Verificare:** teste RED→GREEN ale contractului documentar; suite documentation/development și renderer `--check`; review al diff-ului și al acoperirii; exercițiu read-only pe Git real. Nu transferăm aceste rezultate către `make check` sau G00. Nu se modifică UI/cititoare normative și nu se revendică un nou control vizual.

**Efecte / rollback:** numai fișiere de dezvoltare/documentare și commituri locale intenționate. Fără push, servicii sau date modificate. Revert al commitului coerent și rerularea testelor documentare; nu se ocolește o aprobare refuzată. Rezultatele reale sunt separate mai jos de contract.

## Verificări executate pe schimbarea de dezvoltare

Baza produsului rămâne `4113c78`; sursele/configurația/testele de produs nu au fost editate. Aceste rezultate privesc skillul, harta și contractele documentare, nu sunt o nouă rulare `make check` sau acceptare SL02/G00.

| Probă | Rezultat efectiv / limită |
|---|---|
| Harta, înainte de creare | RED: 4 teste eșuate cu `Missing versioned project-wide status map`, nu import/dependință lipsă |
| Harta după creare | GREEN: 4 teste; 36 ID-uri SL și 4 E unice, faze identice cu planul, axe separate, links existente și breadth neprogramat păstrat |
| Skill/rutare înainte de implementare | RED: 7 teste executate, 5 eșecuri pentru skill/rutare absente (3 subcazuri de rutare); nu eroare de mediu |
| Suite documentare | `python -m unittest discover -s tests/documentation -v`: 61 teste, exit 0, inclusiv cele 7 noi |
| Suite development | `python -m unittest discover -s tests/development -v`: 35 teste, exit 0 |
| Cititoare normative / diff | `python scripts/render_docs.py --check` și `git diff --check`: exit 0; nicio sursă/cititoare normativă schimbată, deci fără regenerare sau nou verdict vizual |
| Descoperire Hermes proaspătă | `TERMINAL_CWD=<repo> hermes skills list --source local`: skillul nou apare local/enabled, exit 0 |
| Loader nativ proaspăt | `tools.skills_tool.skill_view(..., preprocess=False)` într-un proces Python Hermes izolat, cwd/TERMINAL_CWD pe repo: SKILL.md și `templates/handoff.md` încărcate din calea exactă a checkoutului, exit 0; fără pornirea unei sesiuni de model |
| Loaderul sesiunii curente | `skill_view` a răspuns not-found în contextul existent; nu am creat copie globală sau pretins reîncărcare automată. Descoperirea repo-bound de mai sus este proba separată |
| Snapshot de orientare | Git branch/HEAD/diff/log/worktrees/refs locale citite; un singur worktree, referințele remote sunt locale/cached, nu verificare remote proaspătă |
| Fișiere protejate | AGENTS.md neschimbat; HTML original untracked/nestaged cu SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f` |

**INSTRUCTIONS_UPDATE_BLOCKED:** adăugarea unei reguli de încărcare în AGENTS.md a fost refuzată deoarece aprobarea a expirat. Nu s-a reîncercat și nu s-a folosit alt writer. Legăturile deja introduse în delivery/review/CONTRIBUTING sunt integrarea procedurală livrată; nu pretindem că regula protejată a fost instalată. Corectarea statusului vizual istoric din AGENTS nu a fost încercată.

**Limite:** testele verifică acoperirea și contractul textual, nu garantează comportamentul viitor al modelului sau adevărul unui verdict runtime. Skill-ul nu este hook/serviciu. Review-ul de completitudine SL02 este separat și încă fără adjudecare finală în acest checkpoint; harta îl arată în review, păstrând aprobările istorice delimitate. Retrospectiva globală/profilul personal Hermes nu au fost modificate prin această felie. Fără push, Docker/DB/ținte/providere sau resurse externe noi de retras.
