# OmnisAI

Platformă web locală pentru evaluări Web/API autorizate, cu Brain/copii nativi Hermes și skills versionate.

**Stare: P0.3_IMPLEMENTED_LOCAL / bootstrap web real; adjudecarea finală a harnessului în curs; CI remote NOT-RUN.** Fundațiile `P0.1_IMPLEMENTED_LOCAL` și `P0.2_IMPLEMENTED_LOCAL` sunt păstrate. Există build React servit same-origin de API, pairing/sesiune/logout cu readback și stare reală a instanței. `dashboard_ready` cere DB/schemă/assets/API/control sănătoase; `assessment_ready=false`. Funcțiile viitoare sunt UNAVAILABLE/NOT_RUN, nu date DEMO. [Dovezile și limitele P0.3](documents/verification/p03-local-bootstrap.md) separă verificarea locală de porțile încă deschise. Launcherul `omnis`, experiența P1, runtime-ul Hermes și execuția țintelor nu sunt implementate. Nu au fost efectuate scanări sau apeluri LLM de produs.

## Reguli de dezvoltare

**Restanțe pentru P0.3: închise local.** Ruff/mypy sunt fixate, lint/format/typecheck acoperă sursele și testele API, OpenAPI corespunde erorilor reale, iar gate-ul a fost reprodus din checkout curat. [Dovezi și review](documents/verification/p02-python-quality.md): 41 de fișiere verificate static, 128 teste API/control/tooling și 10 de migrare/livrare. Aceasta permite începutul local P0.3, nu închide G00 și nu reprezintă CI remote.

[AGENTS.md](AGENTS.md) fixează istoricul granular, verificarea, review-ul și rollbackul. **VISUAL_ACCEPTED:** utilizatorul a acceptat aspectul prototipului `df17a29` („arata bine. bravo”). [UI/UX §0](documents/Omnis_UI_UX_Spec.md) și DESIGN.md sunt baseline-ul vizual de portat, fără graph/council. Acceptarea vizuală nu transformă datele DEMO în cerințe de produs sau rezultate reale.

**INSTRUCTIONS_UPDATE_BLOCKED:** actualizarea exclusiv a stării vizuale din fișierul protejat `AGENTS.md` a fost refuzată după expirarea aprobării interactive. Fișierul a rămas nemodificat; formularea sa despre aprobarea încă absentă precedă feedbackul de mai sus. Regulile sale de siguranță, autorizare, istoric și verificare rămân neschimbate. Corectarea acelui status cere o aprobare separată, nu ocolirea protecției.

## Începe aici

Pentru lucru în repo: **[modul de dezvoltare și skill-urile](CONTRIBUTING.md)** · [uneltele auditate și starea lor](tools/development/README.md) · [operare API/control](api/README.md) · [build web, pairing și E2E](web/README.md). Pornire Hermes de dezvoltare: `python scripts/hermes_dev.py`; verificare locală: `make check UV=/cale/uv-0.12.19`, după setup-ul DB-ului de test și al mediilor web/browser documentate.

- **[Plan de implementare v2 — HTML](documents/Omnis_Implementation_Plan.html)** · [Markdown](documents/Omnis_Implementation_Plan.md)
- **[Arhitectura MVP v1 — HTML](documents/Omnis_MVP_Architecture.html)** · [Markdown](documents/Omnis_MVP_Architecture.md)
- **[Stack și versiuni — HTML](documents/Omnis_Stack_Baseline.html)** · [Markdown](documents/Omnis_Stack_Baseline.md) · [Registru JSON](documents/Omnis_Stack_Baseline.versions.json)
- **[UI/UX — HTML](documents/Omnis_UI_UX_Spec.html)** · [Markdown](documents/Omnis_UI_UX_Spec.md) · [DESIGN.md](DESIGN.md)
- **[Prototip UI navigabil — DEMO offline](documents/Omnis_UI_Prototype.html)** · Home/Dashboard → Overview · Brain stream · Findings · Coverage · Reports; Settings separat, findings expandabile și review/export DEMO din același model
- **[Re-review și readiness — HTML](documents/Omnis_Implementation_Readiness_Review.html)** · [Markdown](documents/Omnis_Implementation_Readiness_Review.md)
- **[Proba locală P0.1](documents/verification/p01-local-readiness.md)** · API/PostgreSQL, wheel, controale negative, limite și porți neexecutate
- **[Proba inițială P0.2 și comparația cu planul/arhitectura](documents/verification/p02-local-control.md)** · pairing/control/supervisor și remedieri de review; completată de gate-ul Python de mai sus
- **[P0.3 — bootstrap/pairing verificat local](documents/verification/p03-local-bootstrap.md)** · criterii, review/remedieri, rezultate E2E și screenshoturi reale

### Decizia de pornire

**G-DESIGN: VISUAL_ACCEPTED; P0.1/P0.2/P0.3 autorizate explicit.** Utilizatorul a confirmat structura `api/`, `web/`, `cli/` și contractul `omnis` din [arhitectură §4/§12](documents/Omnis_MVP_Architecture.md). `api/` și `web/` au fost introduse incremental; acordul nu autorizează conturi, modele sau trafic către ținte.

**Reluare după clear:** verifică întâi închiderea adjudecării P0.3 din [dovezi](documents/verification/p03-local-bootstrap.md). Următoarea implementare, numai la cerere separată, este **P0.4 — launcherul și instalarea control plane-ului**, conform [plan §19](documents/Omnis_Implementation_Plan.md); nu se refac P0.1/P0.2/P0.3 sau designul acceptat. Matricea UI→owner/API/migrare/ticket/probă rămâne în plan §16; [registrul PA01–PA09](documents/Omnis_Implementation_Readiness_Review.md) este auditul istoric preimplementare. **G00 rămâne deschis** până la launcherul/manifestul/topologia/UID și probele complete P0.4; integrarea runtime și execuția target rămân NEÎNCEPUTE/BLOCKED până la porțile lor.

**După G-DESIGN:** fundație, engagement persistent, web și probe Hermes inerte. **NO-GO pentru target effects:** până la rezolvarea gate-ului de dependențe proxy, bindingului task–copil și confinării. `mitmproxy 12.2.3` publicat este respins pentru trafic target din cauza dependențelor cu advisories; nu îl ascundem sub un dependency resolve reușit. Testele provider cer separat cont, model, acord și buget.

Planul include trasabilitatea tuturor celor 12 recomandări inițiale. `documents/` păstrează numai baseline-ul curent și suportul lui; nu conține propuneri alternative sau review-uri înlocuite. Contractele Hermes necesare implementării sunt în §5 din arhitectura curentă.

## Dovezi și întreținerea documentelor

- [Probe de stack și instrucțiuni de reproducere](documents/verification/README.md)
- [Output real al probelor de dependențe](documents/verification/stack-probe.json)
- [Surse publice și extrasele baseline-ului](documents/Omnis_Baseline.sources.json)
- [Tokenuri DTCG exportate](documents/Omnis_Design.tokens.json)

Markdown este sursa editabilă a documentelor; `python scripts/render_docs.py` regenerează cititoarele HTML, iar `--check` detectează drift. Dependența de documentare este în `documents/requirements-docs.txt`. Rendererul primește doar Markdown trusted al proiectului, niciodată evidence/importuri ale țintei.

HTML-urile și prototipul se deschid local, fără server sau resurse de afișare externe. Păstrează `documents/assets/` lângă prototip: fonturile, modelul sintetic și randarea sunt locale. Prototipul nu are backend, nu acceptă credentiale și nu execută trafic de țintă; exporturile HTML/JSON sunt marcate DEMO. Datele și acțiunile necesare viitoarei legături cu backendul sunt în [UI/UX §8](documents/Omnis_UI_UX_Spec.md). Probele din `documents/verification/stack-probe-inputs/` sunt teste de compatibilitate, nu aplicația Omnis.

## O singură bază de lucru

**Experiență de pornire propusă pentru MVP:** executabilul `omnis` va porni serviciile detached și va deschide dashboardul local, după readiness și pairing când este necesar. Pornirea aplicației nu pornește un assessment și nu consumă LLM. `omnis run stop` va opri runul, `omnis stop` și serviciile, fără ștergerea datelor. Contractul, erorile, structura stării și probele de acceptare sunt în [arhitectură §4.1–4.5](documents/Omnis_MVP_Architecture.md); **comenzile nu sunt încă implementate**.

Fișierele `.md` sunt sursele, iar perechile `.html` sunt cititoare generate, nu versiuni concurente. Registrele `.json`, tokenurile și `verification/` sunt suport tehnic pentru aceleași decizii și dovezi; nu reprezintă alte planuri.

Documentele istorice versionate rămân recuperabile din Git la commitul `b12e179`; nu păstrăm copii `archive/` în `documents/`, ca să nu fie confundate cu instrucțiuni curente.

Niciun document nu constituie autorizație de scanare, dovadă de eficacitate universală sau aprobare pentru folosirea credentialelor personale.
