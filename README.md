# OmnisAI

**Review actual SL02: CHANGES_REQUESTED.** [Auditul aprofundat și reproducerile părintelui](documents/verification/p04-pre-sl03-deep-review.md) confirmă două P1 noi — handoff forwarder întrerupt cu FAILED_CLEANED fals și auto-reap SIGCHLD cu tentative de semnalizare numerică — plus două P2 de tipuri stricte. **Remedierea lor în SL02 precede continuarea SL03.** SC01/SC02 și gate-urile PASS anterioare rămân valide în scenariile lor, nu garanție de completitudine. Matrice actuală: 13 COVERED, 4 GAP, 5 PARTIAL, 4 DEFERRED. DB probei vechi rămâne RECOVERY_PENDING separat; G00 deschis.

Platformă web locală pentru evaluări Web/API autorizate, cu Brain/copii nativi Hermes și skills versionate.

**Stare: P0.4 parțial — SL02, `omnis start --no-open` instalat și status HTTP/assets/control real; SL03 pair/open și SL04 stop/recovery rămân ulterioare. CI remote NOT-RUN; G00 deschis.** Fundațiile `P0.1_IMPLEMENTED_LOCAL` / `P0.2_IMPLEMENTED_LOCAL` / `P0.3_IMPLEMENTED_LOCAL` și migrațiile 0001–0004 sunt păstrate. Comanda headless pornește numai PostgreSQL propriu, API `omnis.serve`, supervisor inert și forwarder host, fără porturi Docker publicate. Verifică identitățile/lease-ul/asseturile înainte de READY; repetarea reutilizează instanța sănătoasă. `assessment_ready=false`, `browser_opened=false`, fără pairing automat, provideri sau ținte. [Rezultatele SL02, reviziile, review-urile și limitele](documents/verification/p04-installed-start.md) sunt separate de [gate-ul baseline DB](documents/verification/p04-test-db-integration.md) și de [harnessul istoric de topologie](documents/verification/p04-host-uds.md). `install`/`install-image` rămân pregătire explicită; startupul nu descarcă, construiește sau upgradează. Experiența P1/runtime-ul Hermes/assessmenturile nu sunt implementate. Un PASS local nu închide G00 și nu certifică LAN/IPv6 sau stopul durabil.

**Adjudecare curentă P0.4:** integrarea DB autorizată este închisă: runner comun UDS/no-network, manifest/attestor, identitatea conexiunii înainte DDL și cleanup al familiei de teste înainte DB. [Registrul DB](documents/verification/p04-test-db-integration.md) păstrează eșecurile și gate-ul local; [auditul anterior](documents/verification/p04-loop-adjudication.md) rămâne istoric. [SL02](documents/verification/p04-installed-start.md) exercită acum comanda instalată, nu `run_probe`. SC01/SC02 sunt închise delimitat; noile RT-F01/RT-F02 și AR01/AR02 cer corecții SL02 înainte de SL03, apoi SL04 conform [plan §19.2](documents/Omnis_Implementation_Plan.md); fără promovarea ownerului exec WIP. CI remote și G00 rămân deschise.

**Baseline amendat cu acordul operatorului:** HF01–HF10 sunt incorporate în arhitectură/plan/UI/stack. Omnis rămâne independent, Hermes nativ, build-by-reuse. Fluxul este obiectiv → recon/mapping → ipoteze → specialiști → validare → replan/recon suplimentar/path → raport/retest; research opțional și improvement pentru versiuni viitoare. Setupul general/focused, contractele package/procedure/brief/tool, Jev shadow/advisory, gates dependente și protocolul Omnis–Strix sunt **specificate, nu implementate**. Nu există superioritate demonstrată față de Strix. Review-urile sunt dovezi/rațiuni istorice, nu planuri concurente; [plan §17](documents/Omnis_Implementation_Plan.md) adjudecă recomandările înlocuite.

**Deep review ulterior:** [constatări, adjudecare și limite](documents/verification/omnis-deep-review.md). Pentru lectura noii viziuni: plan **§2.1** (fluxul operațional), **§4.2** (subfeliile și locurile de modificare), **§4.3** (milestone-uri/gates) și arhitectură **§5.2/§6.3/§9.7–9.8** (admission, replan, checks și eval/publicare). Aceste clarificări pregătesc implementarea incrementală; nu mută modulele viitoare în P0 și nu închid G00.

**Pattern comun skills/copii din notițele originale:** arhitectură **§9.9–9.10** separă skillul, specializarea copilului, modelul/capabilitățile efective și reviewul de completitudine de validarea tehnică. **§11.1** aplică patternul la JS și wordlist/discovery; plan **§4.4** arată cum se livrează orice skill, în subfeliile existente. [Adjudecare și verificare NS01–NS19](documents/verification/omnis-skill-pattern-amendment.md). Contracte specificate, nu skills/adaptoare/runtime deja implementate; fără modificarea P0 sau a WIP-ului DB.

## Reguli de dezvoltare

**Fundația de calitate P0.2 — păstrată și extinsă.** Ruff/mypy rămân fixate, fără gate-uri slăbite. [Proba istorică înainte de P0.3](documents/verification/p02-python-quality.md) consemnează 41 de fișiere și 128+10 teste. [P0.3](documents/verification/p03-local-bootstrap.md) extinde verificarea la 52 de fișiere Python, 148+10 teste API/livrare, 20 teste web și 7 E2E reale, plus contracte/lint/build. Rezultatele sunt locale, nu CI remote sau închidere G00.

[AGENTS.md](AGENTS.md) fixează istoricul granular, verificarea, review-ul și rollbackul. **VISUAL_ACCEPTED:** utilizatorul a acceptat aspectul prototipului `df17a29` („arata bine. bravo”). [UI/UX §0](documents/Omnis_UI_UX_Spec.md) și DESIGN.md sunt baseline-ul vizual de portat, fără graph/council. Acceptarea vizuală nu transformă datele DEMO în cerințe de produs sau rezultate reale.

**INSTRUCTIONS_UPDATE_BLOCKED:** actualizarea exclusiv a stării vizuale din fișierul protejat `AGENTS.md` a fost refuzată după expirarea aprobării interactive. Fișierul a rămas nemodificat; formularea sa despre aprobarea încă absentă precedă feedbackul de mai sus. Regulile sale de siguranță, autorizare, istoric și verificare rămân neschimbate. Corectarea acelui status cere o aprobare separată, nu ocolirea protecției.

## Începe aici

- **[Harta globală de implementare și review — MVP/post-MVP](documents/verification/implementation-status.md)** · cod/probe/review separate, toate subfeliile SL și extensiile E; proiecție întreținută la predare prin `omnis-project-status`, nu un plan nou.

Pentru lucru în repo: **[modul de dezvoltare și skill-urile](CONTRIBUTING.md)** · [uneltele auditate și starea lor](tools/development/README.md) · [operare API/control](api/README.md) · [build web, pairing și E2E](web/README.md) · [CLI P0.4 parțial](cli/README.md). Pornire Hermes de dezvoltare: `python scripts/hermes_dev.py`; verificare locală: `make check UV=/cale/uv-0.12.19`, cu mediile/pinurile pregătite; runnerul creează și atestă automat numai o DB disposable nouă. Instrucțiunile vechi TCP sunt istorice; nu se folosește o DB existentă pentru a forța un green.

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

**Reluare după clear:** verifică HEAD/checkoutul, [auditul SC01/SC02](documents/verification/p04-start-completeness-review.md), [registrul SL02](documents/verification/p04-installed-start.md) și [verdictul DB](documents/verification/p04-test-db-integration.md), apoi plan §4.2/§19.1–19.2 și arhitectură §4/§12. Nu transfera rezultate între revizii și nu reintegra fixture-ul DB deja închis. Păstrează eșecurile istorice, limita TIME_WAIT, designul acceptat și sursa HTML originală protejată. După remedierea/adjudecarea constatărilor noi din auditul aprofundat, următoarea subfelie nouă este **SL03 / P0.4c — pairing TTY-only și open pe origin verificat**, apoi SL04 stop/recovery. Nu reface P0.1–P0.3; nu activa runtime/provider/ținte. G00 așteaptă întregul set de probe, nu numai startul headless.

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

**Experiență instalată parțială:** `omnis start --no-open` pornește detached control plane-ul P0 și verifică dashboardul fără GUI; `status`, `install --bundle` și `install-image` sunt disponibile. Pornirea aplicației nu pornește un assessment. **Nu sunt încă implementate:** comanda implicită `omnis` cu browser, `pair`, `open`, `run stop`, `stop` și recovery operațional. Contractul rămâne în [arhitectură §4.1–4.5](documents/Omnis_MVP_Architecture.md); [utilizare și limite](cli/README.md).

Fișierele `.md` sunt sursele, iar perechile `.html` sunt cititoare generate, nu versiuni concurente. Registrele `.json`, tokenurile și `verification/` sunt suport tehnic pentru aceleași decizii și dovezi; nu reprezintă alte planuri.

Documentele istorice versionate rămân recuperabile din Git la commitul `b12e179`; nu păstrăm copii `archive/` în `documents/`, ca să nu fie confundate cu instrucțiuni curente.

Niciun document nu constituie autorizație de scanare, dovadă de eficacitate universală sau aprobare pentru folosirea credentialelor personale.
