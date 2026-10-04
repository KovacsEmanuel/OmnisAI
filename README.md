# OmnisAI

**P0/G00 local — `P0_LOCAL_USABLE` PASS_LOCAL_RECORDED pe această VM single-user.** `omnis` instalat pornește control plane-ul inert; `start --no-open`, `status`, `pair`, `open`, `stop` repetat și Start nou explicit au probe reale, cu DB/schemă/assets/control, sentinel și PGDATA păstrate. [Adjudecarea și limitele](documents/verification/p04-stop-recovery.md) leagă O exit0 pe `ccd9a1c`, Pair/Open exit0 pe consumatori neschimbați și readbackul cleanupului; [statusul global](documents/verification/implementation-status.md) separă implementarea/probele/reviewul. Nu este deployment persistent, release distribuit, CI remote ori aprobare pentru model/ținte; FAIL/UNCERTAIN istorice rămân.

Platformă web locală pentru evaluări Web/API autorizate, cu Brain/copii nativi Hermes și skills versionate.

**Stare P0:** `P0.1_IMPLEMENTED_LOCAL` / `P0.2_IMPLEMENTED_LOCAL` / `P0.3_IMPLEMENTED_LOCAL` și SL02–SL04 implementate pentru utilizarea locală inertă. API-ul servește bootstrapul web, pairing/session/logout și status real; `assessment_ready=false`. `omnis install`/`install-image` sunt explicite, startupul nu instalează/upgradează implicit, iar browser openerul OS nu a confirmat o fereastră în laborator (URL local disponibil manual). `omnis stop` păstrează datele și nu pretinde STOPPED pe efect incert. Pause/Resume și `omnis run stop` vin odată cu runurile reale, nu sunt comenzi P0. [SL02](documents/verification/p04-installed-start.md), [SL03](documents/verification/p04-pair-open.md), [SL04](documents/verification/p04-stop-recovery.md).

**Dovezi locale:** O instalat pe `ccd9a1c` a trecut exit0 cu Stop→Start/sentinel→Stop și emergency `UNCERTAIN`; P instalat pe `d1be1d1` a trecut exit0 pentru TTY implicit/configurat și non-TTY. Doar verificarea SHUTDOWN din `control.py` s-a schimbat între P și O; consumatorii Pair/Open au rămas identici. Readbackul independent confirmă resursele proprii absente, datele păstrate și inventarul străin neschimbat. [Registrul](documents/verification/p04-stop-recovery.md) păstrează și eșecurile, fără a le promova. Fundația DB și topologia internă sunt în [registrul DB](documents/verification/p04-test-db-integration.md) și [topologie](documents/verification/p04-host-uds.md). CI remote și peerul extern sunt gates separate de distribuire, nu folosirea locală pe VM.

**Baseline amendat cu acordul operatorului:** HF01–HF10 sunt incorporate în arhitectură/plan/UI/stack. Omnis rămâne independent, Hermes nativ, build-by-reuse. Fluxul este obiectiv → recon/mapping → ipoteze → specialiști → validare → replan/recon suplimentar/path → raport/retest; research opțional și improvement pentru versiuni viitoare. Setupul general/focused, contractele package/procedure/brief/tool, Jev shadow/advisory, gates dependente și protocolul Omnis–Strix sunt **specificate, nu implementate**. Nu există superioritate demonstrată față de Strix. Review-urile sunt dovezi/rațiuni istorice, nu planuri concurente; [plan §17](documents/Omnis_Implementation_Plan.md) adjudecă recomandările înlocuite.

**Deep review ulterior:** [constatări, adjudecare și limite](documents/verification/omnis-deep-review.md). Pentru lectura noii viziuni: plan **§2.1** (fluxul operațional), **§4.2** (subfeliile și locurile de modificare), **§4.3** (milestone-uri/gates) și arhitectură **§5.2/§6.3/§9.7–9.8** (admission, replan, checks și eval/publicare). Aceste clarificări pregătesc implementarea incrementală; nu mută modulele viitoare în P0 și nu au fost ele însele dovada de închidere G00.

**Pattern comun skills/copii din notițele originale:** arhitectură **§9.9–9.10** separă skillul, specializarea copilului, modelul/capabilitățile efective și reviewul de completitudine de validarea tehnică. **§11.1** aplică patternul la JS și wordlist/discovery; plan **§4.4** arată cum se livrează orice skill, în subfeliile existente. [Adjudecare și verificare NS01–NS19](documents/verification/omnis-skill-pattern-amendment.md). Contracte specificate, nu skills/adaptoare/runtime deja implementate; fără modificarea P0 sau a WIP-ului DB.

## Reguli de dezvoltare

**Fundația de calitate P0.2 — păstrată și extinsă.** Ruff/mypy rămân fixate, fără gate-uri slăbite. [Proba istorică înainte de P0.3](documents/verification/p02-python-quality.md) consemnează 41 de fișiere și 128+10 teste. [P0.3](documents/verification/p03-local-bootstrap.md) extinde verificarea la 52 de fișiere Python, 148+10 teste API/livrare, 20 teste web și 7 E2E reale, plus contracte/lint/build. Rezultatele acestei felii au fost locale, nu CI remote și nu constituiau singure acceptarea ulterioară G00.

[AGENTS.md](AGENTS.md) fixează istoricul granular, verificarea, review-ul și rollbackul. **VISUAL_ACCEPTED:** utilizatorul a acceptat aspectul prototipului `df17a29` („arata bine. bravo”). [UI/UX §0](documents/Omnis_UI_UX_Spec.md) și DESIGN.md sunt baseline-ul vizual de portat, fără graph/council. Acceptarea vizuală nu transformă datele DEMO în cerințe de produs sau rezultate reale.

**INSTRUCTIONS_UPDATE_BLOCKED:** actualizarea exclusiv a stării vizuale din fișierul protejat `AGENTS.md` a fost refuzată după expirarea aprobării interactive. Fișierul a rămas nemodificat; formularea sa despre aprobarea încă absentă precedă feedbackul de mai sus. Regulile sale de siguranță, autorizare, istoric și verificare rămân neschimbate. Corectarea acelui status cere o aprobare separată, nu ocolirea protecției.

## Începe aici

- **[Harta globală de implementare și review — MVP/post-MVP](documents/verification/implementation-status.md)** · cod/probe/review separate, toate subfeliile SL și extensiile E; proiecție întreținută la predare prin `omnis-project-status`, nu un plan nou.

Pentru lucru în repo: **[modul de dezvoltare și skill-urile](CONTRIBUTING.md)** · [uneltele auditate și starea lor](tools/development/README.md) · [operare API/control](api/README.md) · [build web, pairing și E2E](web/README.md) · [CLI P0.4 local](cli/README.md). Pornire Hermes de dezvoltare: `python scripts/hermes_dev.py`; verificare locală: `make check UV=/cale/uv-0.12.19`, cu mediile/pinurile pregătite; runnerul creează și atestă automat numai o DB disposable nouă. Instrucțiunile vechi TCP sunt istorice; nu se folosește o DB existentă pentru a forța un green.

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

**G-DESIGN: VISUAL_ACCEPTED; P0.1–P0.4 autorizate explicit.** Utilizatorul a confirmat structura `api/`, `web/`, `cli/` și contractul `omnis` din [arhitectură §4/§12](documents/Omnis_MVP_Architecture.md). `api/`, `web/` și primul increment `cli/` au fost introduse incremental; acordul nu autorizează conturi, modele sau trafic către ținte.

**Reluare după clear:** verifică HEAD/checkoutul, [auditul SC01/SC02](documents/verification/p04-start-completeness-review.md), [registrul SL02](documents/verification/p04-installed-start.md), [registrul SL03](documents/verification/p04-pair-open.md) și [verdictul DB](documents/verification/p04-test-db-integration.md), apoi plan §4.2/§19.1–19.2 și arhitectură §4/§12. Nu transfera rezultate între revizii și nu reintegra fixture-ul DB deja închis. Păstrează eșecurile istorice, limita TIME_WAIT, designul acceptat și sursa HTML originală protejată. După SL03, următoarea subfelie nouă este **SL04 / P0.4d — stop/recovery durabil**, nu parserul M22 în această rundă. Nu reface P0.1–P0.3; nu activa runtime/provider/ținte. G00 așteaptă întregul set de probe, nu numai pair/open.

**După G-DESIGN:** fundație, engagement persistent, web și probe Hermes inerte. **NO-GO pentru target effects:** până la rezolvarea gate-ului de dependențe proxy, bindingului task–copil și confinării. `mitmproxy 12.2.3` publicat este respins pentru trafic target din cauza dependențelor cu advisories; nu îl ascundem sub un dependency resolve reușit. Testele provider cer separat cont, model, acord și buget.

Planul include trasabilitatea R01–R12 și HF01–HF10. `documents/` păstrează baseline-ul curent și suportul lui; dosarele review/handoff din verification sunt explicit istorice după incorporare, nu autoritate de implementare concurentă. Contractele Hermes necesare implementării sunt în §5 din arhitectura curentă.

## Dovezi și întreținerea documentelor

- [Amendamentul HF01–HF10: verificări și limite](documents/verification/omnis-amendment-verification.md)
- [Probe de stack și instrucțiuni de reproducere](documents/verification/README.md)
- [Output real al probelor de dependențe](documents/verification/stack-probe.json)
- [Surse publice și extrasele baseline-ului](documents/Omnis_Baseline.sources.json)
- [Tokenuri DTCG exportate](documents/Omnis_Design.tokens.json)

Markdown este sursa editabilă a documentelor; `python scripts/render_docs.py` regenerează cititoarele HTML, iar `--check` detectează drift. Dependența de documentare este în `documents/requirements-docs.txt`. Rendererul primește doar Markdown trusted al proiectului, niciodată evidence/importuri ale țintei.

HTML-urile și prototipul se deschid local, fără server sau resurse de afișare externe. Păstrează `documents/assets/` lângă prototip: fonturile, modelul sintetic și randarea sunt locale. Prototipul nu are backend, nu acceptă credentiale și nu execută trafic de țintă; exporturile HTML/JSON sunt marcate DEMO. Datele și acțiunile necesare viitoarei legături cu backendul sunt în [UI/UX §8](documents/Omnis_UI_UX_Spec.md). Probele din `documents/verification/stack-probe-inputs/` sunt teste de compatibilitate, nu aplicația Omnis.

## O singură bază de lucru

**Experiență instalată parțială:** `omnis start --no-open` pornește detached control plane-ul P0 și verifică dashboardul fără GUI; `status`, `install --bundle` și `install-image` sunt disponibile. `omnis pair` emite numai în TTY după atestare, `omnis open` verifică instanța înaintea browserului, iar `omnis` implicit pornește/reutilizează, emite cod inițial numai pentru o instanță nouă în TTY și încearcă deschiderea. `omnis stop` are traseul P0 normal + urgență nereconciliată, cu Start nou explicit și date păstrate, dar **SL04 nu este încă acceptat integral**: crash-cut-urile, retry-ul fizic după teardown parțial și negativele de topologie rămân deschise în pofida gate-urilor locale verzi. Pornirea aplicației nu pornește un assessment. `omnis run stop` nu este implementat; acceptarea de către opener nu certifică fereastra. Contractul rămâne în [arhitectură §4.1–4.5](documents/Omnis_MVP_Architecture.md); [utilizare și limite](cli/README.md).

Fișierele `.md` sunt sursele, iar perechile `.html` sunt cititoare generate, nu versiuni concurente. Registrele `.json`, tokenurile și `verification/` sunt suport tehnic pentru aceleași decizii și dovezi; nu reprezintă alte planuri.

Documentele istorice versionate rămân recuperabile din Git la commitul `b12e179`; nu păstrăm copii `archive/` în `documents/`, ca să nu fie confundate cu instrucțiuni curente.

Niciun document nu constituie autorizație de scanare, dovadă de eficacitate universală sau aprobare pentru folosirea credentialelor personale.
