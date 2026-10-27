# R1 — review independent Settings C / assignment guard

**Report ID:** SETTINGS-C-R1-57ae4967-lsn50i8c
**Verdict:** CHANGES_REQUESTED_SOURCE; nu APPROVED_SOURCE_SCOPED și nu runtime PASS.
**Dispoziție:** F01/F02 necesită remedii minimale și re-review focalizat; F03 blochează completitudinea QA pregătite, nu cere ca QA interzisă în acest review să fi trecut deja.

## Binding și limite

- Repo: `/home/kali/OmnisAI`; HEAD/base `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Manifest original nemodificat: `/home/kali/.hermes/cache/scratch/uic/frozen-candidate.json`, SHA256 `e48cee247a16a8197bef3c44d885ac78dd7954494c24302890499cb8d59afc27`.
- Candidate ID recalculat conform algoritmului manifestului: `57ae496709f00413e31fd8741fd0d41f6c6b6733bb04be0b6ddfe97d36a15f39`.
- 32/32 hashes verificate, inclusiv cele9 fișiere owned untracked; zero mismatch. Tracked diff SHA256 `6d1d516258195fe15513311685eacdf84bb5f73ef5767455d26dfc3d4224e3c0`; index gol. Reverificarea finală a celor32 hashes: identice.
- Review SOURCE read-only, ownership R1 cerințe/ordine/persistență/calleri/oracle real. R2 păstrează frontierele complementare secrets/auth/concurrency/Stop. Nu am modificat surse/docs/index/Git, nu am delegat și nu am pornit DB/browser-consumer/provider/network/operator instance. Fișierele private protejate nu au fost citite.
- Registry/catalog/exact-entry backend deja acceptate sunt reutilizate numai în scope-ul istoric declarat; nu redeschid schema0016 sau backend neschimbat.

## Findings concrete

### R1-F01 — MEDIUM / blocant funcțional: primul model eligibil păstrează patru selectoare redundante

**Loc:** `web/src/features/engagement/SettingsAssignments.tsx:30–33,52–56`; caller `SettingsModelWizard.tsx:130` și `SettingsModelsPage.tsx:167–176`. Testul candidat `web/src/app/SettingsModels.test.tsx:40–47` fixează explicit lipsa mesajului All roles use, dar nu verifică obligația de simplificare.

**Repro:** connection curent/enabled, exact o intrare salvată cu metadata/cap valid, `selection=null`, zero referințe explicite stale. Este starea reală după primul Save models: înregistrarea nu scrie assignments. Randarea componentei reale produce Default/Brain/Investigator/Validator și mesajul Save assignments separately. Nu există Default persistent până la confirmarea separată. Nu afirm că modelul nu poate fi testat separat; defectul este UX-ul redundant impus în cazul unic cerut explicit.

**Dovadă executată:** scratch Vitest pe componenta reală: **1 FAIL / 2 PASS, exit1, 1.31s**. Log `repro.log:11–34` raportează cele4 selectoare și `saveCalls=0`; eșuează aserțiunea de absență a Default selector. Controalele pozitive pentru selecție deja persistentă/cap Brain37 și negativul referinței stale trec.

**Criteriu:** Prompt A `web/design/settings-delivery-prompt.md:92–96`, `settings-final.md:35–47`, UI/UX `documents/Omnis_UI_UX_Spec.md:161`. Absența auto-write la boot este corectă, dar nu suspendă criteriul one-model/no redundant selectors.

**Remediu minim:** în starea exact-unul eligibil + fără selecție/referințe stale, afișează identitatea unică și confirmarea explicită a Defaultului prin salvarea existentă, fără cele4 selectoare. Înainte de commit spune ce *va* folosi configurația, nu pretinde un Default deja persistent. După receipt/readback afișează All roles use. Fără auto-write la boot, fără ștergerea override-urilor/capurilor sau fallback pentru referințe stale. Adaugă regresia la testul existent și păstrează controalele deja verzi.

### R1-F02 — HIGH / blocant de regresie: installed-SENT census nu include noile scrieri obligatorii ale fixture-ului

**Loc:** `api/tests/installed_sent_probe.py:175–181`; oracle afectat `api/tests/test_model_test_v2.py:1672–1685`.

**Repro:** `test_installed_sent_crash_reconciles_without_resend` pe fixture fresh migrată. Noul PROBE execută SaveModels înainte de SaveSelection pentru membership guard. Handlerul real `provider_model_service.py:176–221` comite patru tabele noi: `provider_model_registry_revision`, `provider_model_entry`, `provider_model_entry_revision`, `provider_model_command`. Censusul anterior este înainte de produce, iar cel cut este după SIGKILL/SENT. Totuși egalitatea exactă a setului de tabele schimbate nu conține niciunul dintre cele4. Chiar cu produsul corect, oracle-ul nu poate trece. Testul este inclus în `test-model-test-v2-pg` (`Makefile:41–43`) și rămâne în gate-ul API canonic.

**Dovadă fără efecte:** compile(PROBE) PASS; extragerea AST a setului exact din test și aserțiunea includerii celor4 scrieri obligatorii produce **exit1**, lista exactă lipsă în `installed-census-source.log:6–7`. Aceasta este constatare deterministă SOURCE; nu pretind că am executat un eșec PostgreSQL.

**Criteriu:** caller/fixture closure la noul SaveSelection guard, Prompt A `178–195`, team-slice exact current consumer și păstrarea canonical gate neschimbat.

**Remediu minim:** adaugă exact cele4 tabele la setul schimbărilor legitime în produce/cut și păstrează strictă egalitatea, census-ul integral și verificările de nemodificare din recover/readback. Nu înlocui cu subset, nu omite testul și nu relaxa guardul. După remediu, probează targetul existent pe fixture admisă, nu un harness nou.

### R1-F03 — MEDIUM / gap de readiness: oracle-ul real pregătit nu acoperă primul setup/single-model, stale wizard/CAS și capturile cerute

**Loc:** `api/tests/test_model_test_v2.py:143–157`, `web/tests/e2e/settings-models.mjs:17–81`.

**Ce este deja real în designul probei:** registrul NU este preseedat. Browserul începe cu No models configured, adaugă32 intrări pe două pagini, salvează Default00/Brain01 cap37, testează exact intrarea02 fără schimbarea assignments, dezactivează, cere același intent cu un ID nou și verifică409 CONNECTION_UNAVAILABLE, apoi reload/API-process restart/readback. Python verifică2 GET metadata/1 POST și1 SENT; census13 tabele protejează restartul. Canalul este built App → paired HTTP API → LocalControl → owner → PG → peer TLS propriu, nu HTML mockup și nu HTTP stand-in.

**Ce nu poate dovedi actualul target:** Python pre-salvează conexiunea, iar browserul verifică Saved key și absența API-key field; nu există primul new-key Save→exact receipt→catalog prin UI. Se trece direct la32 modele, fără starea unui singur model. Refuzul real după Disable nu lasă un wizard stale deschis și nu exercită UI la CAS409. Capturile sunt saved1440, disabled390 și restart la viewport implicit; lipsesc loaded search/results, Review, one/many/assignments/failure la1280/1440/320/390. Stale/focus și cele27 capturi din `provider-settings-focus.mjs` sunt SOURCE/synthetic HTTP, nu închid aceste rânduri real API/PG. Targeturile API existente aduc controale reale complementare, dar nu execută wizardul React lipsă.

**Criteriu:** Prompt A `178–190`, în special180–181/186–190, plus92–96 pentru cazul unic.

**Remediu minim:** adaptează același scenariu settings_ui: nu pre-salva conexiunea numai în acest caz; tastează cheia exclusiv sintetică prin UI/canalul privat de marker existent; salvează întâi un model și confirmă explicit Defaultul simplificat, apoi re-intră cu Saved key și adaugă restul. Include o schimbare reală de revizie în fixture/callerul existent și verifică refuzul wizardului/assignment stale fără efect nou, nu route.fulfill409. Folosește screenshot helper-ul existent și un mic loop la cele4 viewporturi pentru stările loaded relevante. Păstrează 120s/driver,300s/caz,600s/gate și cleanupul existent; dacă nu încape, marchează limita, nu mări timeoutul pentru a masca eroarea. Nu este cerut alt framework/owner sau rerun pentru backendul neschimbat.

## Cerință → cod → dovadă / dispoziție

| Cerință | Cod/caller | Dovadă și dispoziție R1 |
|---|---|---|
| Connection save + exact receipt înainte de catalog; Saved key; Cancel ulterior | Page92–129,202–208; Wizard73–88 | Structura SOURCE este corectă; tests ProviderKeySettings13–47 și SettingsWizard25–37 sunt sintetice. Prim setup real lipsește: F03. |
| Catalog search local/paginat, partial/error/manual UNVERIFIED, chips/Back/provider confirm | Wizard47–127; client providerCatalog; backend deja acceptat | Search trimite numai operația locală search; refresh este explicit. UNIT/SOURCE și backend accepted scoped sunt complementare. Nu provider IO la tastare/reentry; manual nu obține test consent fără metadata. |
| Registru64/pagini16/total și identități exacte | SettingsModels23–36; providerModels9–31 | Patru pagini maxime, revision-bound decoder, count/dedup/order verificate; SOURCE64 și backend accepted scoped. Nu am relansat suitele neschimbate. |
| Save models local / test un singur entry fără Default swap | Page141–176; Wizard98–105; client74–80 | Targetul real pregătit testează02 și verifică assignments neschimbate; nu este încă executat. Save & test cu registry receipt rămâne SOURCE/unit, nu runtime PASS. |
| Assignments separate, capuri și override-uri păstrate; stale vizibil | Assignments15–47,65–72 | Default change păstrează draft brain/investigator/validator și capuri. Existing unit și cele2 controale R1 trec; first-setup single-entry este F01. |
| SaveSelection membership și toți callerii afectați | owner207–229,330–355; routes/errors/contract/generated | Guard exact current connection/model în tranzacția existentă, înainte de INSERT. SOURCE membership1PASS. Fixture-urile pozitive API/model-test/installed înregistrează modelele înainte de SaveSelection; fixture-ul installed are regresia census F02. Serializer-only SaveSelection și schema-upgrade SQL direct nu sunt calleri de guard. |
| Reload/restart/upgrade/receipts | Page80–115; settings_models_browser; existing API schema/restart tests | Readback/API-process restart pregătite; owner/vault restart și schema0016 au dovadă anterioară scoped. Nu supervisor restart/installed UI actual și nu transfer de PASS. |
| C vizual / English / axe / mobile | SettingsModels.module.css + Settings/copy/ModelTest/Wizard | Referințele și SOURCE loaded1440/390/320 inspectate. Direcția/axa900 și familia de controale păstrate. Zero-gap Reload→panel este polish minor, nu blocker nou de temă. Numele upstream Current model nu este status Default; fără finding din acea etichetă. F03 păstrează frontiera capturilor reale. |

## Execuții R1 și artefacte

1. `git status --short --branch; git rev-parse HEAD; git diff --stat; git diff --check` — exit0. Identificare preexisting WIP, fără adoptare; index empty verificat separat.
2. Recalculare SHA256 manifest/32fișiere/canonical candidate/diff — exit0, identitățile de mai sus. Hashurile32 și manifestul reverificate la final, exit0.
3. `make -n test-settings-models-ui-pg` — exit0, doar argv/build recipe/explicit node+opt-in. Nu build și nu QA. Node live v24.21.0.
4. `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH TMPDIR=/home/kali/.hermes/cache/scratch/settings-r1-57ae4967-lsn50i8c timeout --signal=TERM --kill-after=5s 60s npm --prefix web test -- --config /home/kali/.hermes/cache/scratch/settings-r1-57ae4967-lsn50i8c/vitest.config.ts --reporter=verbose` — exit1,1FAIL/2PASS; `repro.log`. Config/test în scratch importă componentele reale nemodificate, nu copii de produs. Warning Vite pentru config scratch CommonJS este neblocant; cele3 teste au rulat.
5. `env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS TMPDIR=/home/kali/.hermes/cache/scratch/settings-r1-57ae4967-lsn50i8c timeout --signal=TERM --kill-after=5s 45s api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_key_settings.py -q -k assignment_membership` — exit0,1PASS/33deselected,0.24s; `membership-source.log`. DB mocked explicit în test, fără PostgreSQL.
6. `python -B -c <AST extraction + compile(PROBE) + strict census assertion>` — exit1 pentruF02; one-liner exact păstrat integral în `installed-census-source.log:3`. Nu execută PROBE, nu procese instalate/DB/network.
7. Inspecție imagini existente: reference models1440/connection1440 și SOURCE assignments1440/390, models-results320/connection1440. Nu am lansat browserul.

Fișiere create numai în scratch: `R1-original.md`, `vitest.config.ts`, `r1-assignments.test.tsx`, cele3 loguri și symlink node_modules către dependențele existente. Nicio schimbare de produs. Originalul raportului se predă byte-exact la această cale; hashul se returnează separat.

**Omise intenționat:** full193/lint/build/contract/API suites deja raportate de autor nu au fost relansate; cauza timeoutului Shell istoric rămâne UNKNOWN. Nicio QA PG/browser-consumer/installed/provider/canonical nouă, nicio aprobare estetică sau T2/auth/Prompt B. Reticle NOT_INTEGRATED pentru acest UI; Chisel BLOCKED_NO_GO.
**Risc rămas:** candidatul nu poate fi acceptat cuF01/F02 deschise; după fix și re-review, QA admisă trebuie să execute rândurile reale completate dinF03 și targeturile afectate, păstrând limitele și FAIL-urile originale.
