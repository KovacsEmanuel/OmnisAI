# Prompt de execuție — închiderea SC01/SC02 în SL02

**Rol:** handoff pentru agentul de implementare, derivat din plan și audit, nu plan alternativ și nu probă de remediere. **Stare la pregătire: NOT_EXECUTED; SC01/SC02 rămân deschise.** Pregătirea acestui prompt nu execută comenzile de mai jos. Se folosește la cererea operatorului pentru sesiunea de remediere.

---

Lucrează în `/home/kali/OmnisAI`. Răspunde în română. Remediază cele două defecte confirmate **SC01/P1 și SC02/P2** din SL02 / P0.4b / B01f-start. Livrează cod real, regresii RED→GREEN, review independent și probe pe wheelul curent instalat. Nu începe SL03, SL04 sau altă fază și nu înlocui comanda de produs cu un harness.

## 1. Baseline și contract

Context inspectat: branch `p04-control-topology-wip`; `87e9017fc6eaeedd916f3808d23042ade00a24f0` conține adjudecarea și lecțiile; `ee7380c` clarifică matricea finală din chat. Codul de produs auditat este încă cel din `4113c78`, identic cu revizia probată istoric `1dfa022`; commiturile de mai sus sunt documentare/dezvoltare. **Verifică HEAD real și orice muncă nouă; nu reveni la aceste SHA-uri.**

Începe cu `git status --short --branch`, `git rev-parse HEAD`, `git diff`, `git diff --cached` și inventarul untracked. Păstrează separat munca preexistentă. `documents/Omnis_Notite_Originale.html` este untracked/protejat: nu îl modifica/stage-ui. Fără reset, stash, clean, amend, rebase sau push. AGENTS.md rămâne protejat; nu reîncerca/bypassa modificările de instrucțiuni anterior refuzate.

Citește AGENTS.md, README/CONTRIBUTING și numai sursele relevante:
- `documents/verification/p04-start-completeness-review.md` — defecte, reproducerea părintelui, limite și matricea celor 26 cerințe;
- `documents/verification/p04-installed-start.md` — pozitive și gate-uri istorice, nu PASS transferabil remediilor;
- plan §4.2/§19.2, arhitectură §4.1–4.5; `cli/README.md`, Makefile și codul real înainte de editare.

Încarcă skill-urile proiectului:
1. `omnis-delivery` — contract, TDD, felie minimală și commituri;
2. `omnis-release-ops` **plus** `references/startup-failure-boundaries.md` — ownership, incertitudine, artefact instalat și cleanup;
3. `omnis-review-qa` — cerință→cod→probă, review independent și adjudecare;
4. `omnis-project-status` — ORIENT la intrare, CLOSE și matrice direct în chat la final.

Dacă loaderul sesiunii nu descoperă skill-urile locale, citește fișierele lor din `.hermes/skills/`; nu crea duplicate globale. Completează cu `test-driven-development`, `systematic-debugging`, `local-service-lifecycle`. `omnis-api-data` este necesar numai dacă un reproducer nou justifică atingerea frontierei DB; nu redeschide migrarea/fixture-ul pentru aceste defecte CLI.

Înaintea codului consemnează contractul scurt, fișierele, controalele pozitive/negative, efectele și rollbackul. Scope inițial: `cli/src/omnis_cli/start_runtime.py`, `release.py`; `start.py` numai dacă un test demonstrează că este necesar; testele CLI relevante și integrarea instalată existentă. Documentele afectate se actualizează după rezultate. Orice extindere cere cauză/reproducer și justificare, nu refactor general.

## 2. SC01 — repară producătorul incertitudinii, apoi verifică cleanupul

Fapt reprodus: `ControlRuntime.run(effect=True)` cu copil real terminat prin SIGKILL (`returncode=-9`) ridică `LOCAL_SERVICE_COMMAND_FAILED`, dar lasă `uncertain=false`, `family_drained=true`. `cleanup_attempt` poate apoi autoriza stop/remove DB. În reproducerea anterioară efectele Docker au fost substituite; **nu a fost oprită o DB reală**.

- Scrie întâi regresia care eșuează pe ramura reală de wait/returncode, nu doar un test pornit cu `uncertain=true`. Refolosește fixture-ul/procedurile din `cli/tests/test_start_process.py`; un copil local propriu poate reproduce terminarea fără Docker.
- Verifică și apelantul: starea produsă de acea ramură trebuie să împiedice **orice stop/remove DB** sub incertitudine, să păstreze diagnosticul/locatorul și să ajungă la `UNCERTAIN`/exit 4 pe frontiera de startup relevantă. Exit 4 după oprirea nesigură a DB nu este acceptare.
- Tratează returncode-ul negativ independent de opțiunea `success`; nu lăsa `success=False` să piardă incertitudinea. Examinează separat succesul normal, refuzul cunoscut, eroarea neclasificată/pierderea ACK, timeoutul și decodingul rezultatului. Nu presupune că orice nonzero dovedește anularea efectului daemon.
- Păstrează conservator starea familiei dacă nu există dovadă de drenare. Nu semnaliza PID/PGID după reap și nu confunda reap-ul liderului cu toți descendenții. Dacă probezi descendenți, folosește numai procese proprii identificabile, deadline/rescue sigur și readback.
- Aplică remediul minimal în ownerul existent. Nu promova ownerul exec WIP, nu construi alt supervisor/harness și nu implementează `omnis stop` pe ascuns.
- Include control pozitiv pe aceeași frontieră: succesul cunoscut nu devine fals incert; păstrează negativele timeout/flood/journal/remove și regula de continuare a celorlalte operații de cleanup sigure.

O probă real-child + daemon substituit este dovadă de componentă, nu de efect Docker întârziat. Nu pretinde această a doua probă dacă nu a rulat. Orice probă suplimentară Docker trebuie să rămână opt-in, proprie, bounded și să păstreze DB când rezultatul daemonului nu poate fi reconciliat; nu folosi rescue ca să fabrici cleanup PASS.

## 3. SC02 — refuz sanitizat al manifestului profund imbricat

Fapt reprodus: `b'[' * 15000 + b'0' + b']' * 15000` are 30001 bytes, sub limita 32768. `_manifest()` ridică `RecursionError`; console scriptul instalat `omnis start --no-open --json`, din alt cwd, iese cu 1/stdout gol/traceback în loc de refuzul contractual.

- Test RED prin decoderul real, în limita de bytes, plus frontiera CLI. Un refuz pentru oversized file, import lipsă sau release absent nu reproduce acest defect.
- Convertește îngust excepția de frontieră în `ReleaseError` sanitizat ori aplică o limită structurală justificată; fără catch general care ascunde erori de programare. Păstrează schema strictă, unique keys, limitele, path/owner și checksum checks.
- GREEN necesar: `omnis start --no-open --json` instalat din cwd extern → **exit 2**, JSON valid `state=REFUSED`, diagnostic acționabil `RELEASE_OR_IMAGE_INVALID`, toate readiness/browser flags false; fără traceback, payload brut, secrete sau state/runtime create.
- Păstrează controalele de release valid și invalid obișnuit. Refuzul nu trebuie să depindă de Docker funcțional și nu are voie să pornească servicii.

Scratch poate dispărea: reconstruiește regresia din registrul versionat dacă vechiul reproducer lipsește. Nu transforma un verifier care se așteaptă la bug/exit 1 într-un test GREEN al produsului. Regresiile permanente trebuie să afirme comportamentul sigur dorit și să eșueze pe codul vechi.

## 4. Verificare reală, în ordinea costului

Inspectează Makefile-ul actual și pinurile. Ultimele versiuni documentate: Python 3.13.15, uv 0.12.19, Node 24.21.0/npm 11.19.0, PostgreSQL 18.6. Verifică existența toolchainului; dacă lipsește, recreează mediu izolat din lockuri, nu latest/global.

Căi folosite anterior, de verificat înainte de reutilizare:
- `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`
- `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin`

1. Rulează fiecare regresie RED, remediu GREEN și controalele apropiate.
2. Rulează `make test-cli`; lint/format/mypy folosesc comenzile/configurația existente. Nu lansa direct `test-cli-live` cu un DSN ambiental pentru a ocoli runnerul DB.
3. Construiește explicit wheelul nou prin `make check-cli-wheel UV=<uv-verificat>` și verifică noua regresie instalată din cwd extern. Confirmă revizia/modulele importate; nu reutiliza vechiul wheel din scratch ca dovadă pentru sursa reparată.
4. Pe codul final execută **secvențial**, cu PATH pin-uit, `make check UV=<uv-verificat>` și **separat** `make check-installed-start UV=<uv-verificat>`. Runnerul comun creează propria DB UDS/no-network; nu readopta clustere vechi. Nu rula gate-uri care împart artefacte/venvuri în paralel.
5. Proba OCI execută `omnis start --no-open` real din wheel/release curente: readiness HTTP/assets/control, reuse/concurență, status, supraviețuirea launcherului și cleanup/date păstrate. Nu `run_probe` în locul comenzii. Construirea/pregătirea imaginilor rămâne explicită, separată de startup.
6. Pentru joburi lungi folosește execuție urmărită cu notificare și verifică exact ID/exit/log/readback; un timeout al toolului ori heartbeat întârziat nu este verdictul procesului. Nu rerula suite doar pentru un nudge „unverified” și nu redenumi verificări parțiale în `make check`.
7. Documente normative schimbate: renderer + `--check`, teste documentation, iar la readers relevanți Chromium/inspecție vizuală. Nu transfera aceste PASS-uri asupra runtime-ului.

Probele folosesc numai procese/containere noi și proprii, XDG privat sub scratch și secrete sintetice. Fără conturi, LLM/OAuth/Jev, trafic target, profil Hermes personal, daemon/firewall/global toolchain changes sau autostart. Nu adopta/opri resursele operatorului. Prerechizitul privilegiat ori noul efect extern neautorizat cere acord; lipsa sa rămâne BLOCKED, nu simulare prezentată live.

## 5. Review delimitat și commituri

Pentru fiecare remediu cere review independent **read-only**, legat de commit sau snapshot exact al diff-ului:
- **SC01:** cauza→flaguri→cleanup→verdict, zero efecte DB sub incertitudine, family/daemon boundaries, semnale/reap, controale pozitive și limitele mockurilor;
- **SC02:** decoder→ReleaseError→console script, diagnosticul/exit/JSON, validarea strictă păstrată și lipsa efectelor la refuz.

Reviewerul primește criteriile și fișierele, nu verdictul dorit. Cere severitate, fișier:linie, scenariu, criteriu încălcat și remediu minimal; comenzile executate separat de cele recomandate. Părintele reproduce constatările relevante și adjudecă. Niciun agent secundar nu editează/comite în checkoutul comun.

Un review care acoperă ambele remedii poate fi suficient dacă are verdict distinct pentru fiecare. Re-review suplimentar este necesar numai pentru remedii noi, interacțiuni sau constatări concrete neînchise; nu relansa audit general DB/owner/MVP după fiecare fix. La final confruntă delta cu matricea celor 26 cerințe: păstrează PARTIAL/DEFERRED unde probele nu s-au extins, nu redenumi totul COVERED.

Fiecare defect: RED→GREEN→review adecvat→commit local separat, cu motiv/verificări/limite/rollback. Documentarea finală poate avea commit distinct. Stage numai căile intenționate și verifică `git show`/status după commit. Fără push. Nu declara gata cu schimbări intenționate necomise sau blocante neadresate.

## 6. Acceptare și predare

Poți închide **SC01/SC02**, nu întregul G00, numai când:
- regresiile detectează codul vechi și trec pe remediu, inclusiv frontiera instalată cerută;
- review-ul independent este adjudecat fără blocante rămase;
- gate-ul comun și proba instalată au rezultate reale pe codul nou, cu ownership/cleanup/readback și date păstrate;
- nu sunt modificate `omnis.serve`, migrațiile 0001–0004, infrastructura DB integrată, topologia fără port Docker publicat sau corecția backpressure din `bd06bcd` ca artificiu pentru GREEN;
- registrele, README/plan/readiness și harta primesc verdictul justificat, păstrând RED-urile istorice, reviziile și limitele. G00, SL03/SL04 și CI remote nu primesc PASS implicit.

Raport final scurt: remedii, probe reale și limite, review-uri, commituri, Git și resurse/date/recuperări. **Încheie direct în chat cu matricea statusului global Omnis**, conform `omnis-project-status`: AICI, implementare, probe, review, pas imediat, rest MVP și post-MVP. Documentele sunt pentru continuitatea agenților; linkul către ele nu înlocuiește matricea vizibilă.
