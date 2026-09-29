# HF01–HF10 — verificarea amendamentului canonic

**Dovadă de livrare documentară, nu plan alternativ, certificare runtime sau rezultat pentest.** Bază locală `3fc3d46298720a1529a922247781fab435cda483`, ramură `p04-control-topology-wip`; fără fetch/push/reset/stash/rescriere de istorie. Remote-ul nu a fost folosit ca bază și starea lui curentă nu este certificată. WIP-ul inițial este exclus din staging; readbackul final îl verifică separat.

## Ce guvernează implementarea

- Arhitectură §5/§6/§9: bucla Brain, Jev, compoziție modulară/research/maintenance, misiune generală/focalizată, package/technique/procedure, brief/result și tool invocation; policy/evidence/Stop rămân deterministe.
- Plan §4/§15/§16/§17/§19: DAG, prima BOLA separată de MVP/extensii, protocol Omnis–Strix, UI01–UI23, HF01–HF10 și contradicții adjudecate, matrice P0.4 și următoarea felie.
- UI/UX: controalele noi sunt specificate, nu implementate în web/prototip; navigația/cockpitul acceptat și Stop rămân. DESIGN are numai calificări de prose; tokenurile nu s-au schimbat.
- Stack §10: U01–U14 + toate cele 34 unități S/M/R/HM și pinurile/testele/destinațiile/adaptările; fără import/install/admission pretins. Manifestele de cercetare originale rămân dovezi, nu runtime activ.
- README/CONTRIBUTING/readiness/component READMEs și dosarele istorice disting statusul actual de probele vechi. AGENTS protejat nu este modificat.

## Impact de cod

**Nicio schimbare în codul de produs API/CLI/web/DB.** P0.4 rămâne fundația de păstrat; nu au fost create module, migrații sau endpointuri/stuburi pentru MVP. Matricea PĂSTRĂM / CORECTĂM ACUM / EXTINDEM ÎN FELIA VIITOARE este în plan §19.1.

Cod de documentare schimbat:
- `tests/documentation/test_amendment_contracts.py`: checks pentru contracte/trasabilitate/source counts/tabele UI randate și extragerea secțiunilor reale, nu exemple fenced/quoted; nu validează schema runtime sau eficacitatea.
- `test_baseline_contracts.py`: DAG și rânduri UI extinse fără a relaxa dependențele de siguranță.
- `scripts/render_docs.py`: bannerul global nu mai pretinde că orice aplicație este neimplementată; starea autoritativă este în fiecare document. Regresie în `test_render_docs.py`.

## Verificări executate

| Stare | Comandă / probă | Rezultat și limită |
|---|---|---|
| PASS | Baseline: `python scripts/render_docs.py --check`; `python -m unittest discover -s tests/documentation -v` | 5 readers sincronizate, 28 teste înainte de editare |
| PASS | `python scripts/render_docs.py` | 5 cititoare generate din Markdown trusted, fără editare manuală HTML |
| PASS | `python scripts/render_docs.py --check` | exit 0 după regenerare |
| PASS | `python -m unittest discover -s tests/documentation -v` | Ultimul snapshot: 39 teste, exit 0; include regresii ale testelor documentare/rendererului, nu produs |
| PASS | `git diff --check` | exit 0 după corectarea whitespace-ului găsit în timpul editării |
| PASS | `python tests/documentation/browser_check.py --include-documents --output "$TMPDIR/omnis-amendment/browser-check.json"` | 116 verificări Chromium offline, zero failures/JS errors/unexpected network; nu backend E2E sau aprobare vizuală |
| PASS | Inspecție reală browser: architecture §9.4 la 1280px și plan la 390px | Cuprins/pachet/metodologie și banner lizibile, fără overflow global; DOM plan conține 23 UI rows și 10 HF rows; nu demonstrează controalele viitoare |
| PASS | Manifestele JSON procesate integral | 34 unități = 26 cod/conținut/date + 8 native; 98 referințe source/test; 75 ghiduri Strix + README, 29 vulnerability guides; IDs/pins/destinații legate de stack. Nu rerulare suites upstream |
| BLOCKED | `make check` / `make test` | Nu lansate: lipsesc variabilele DB dedicate; WIP Compose UDS/no-network, conftest/CI TCP și runner probe-only neintegrate. Nu pornim DB/servicii sau încă un harness pentru reminderul verify-on-stop |
| PASS | Conservare WIP/prototip/pinuri | 6 fișiere WIP cu SHA-256 identic început/final; prototipul/assets/tokenurile/AGENTS și manifestele sursă neschimbate. Linkuri locale și diff fără flags de secret în liniile adăugate; nu audit exhaustiv |
| NOT-RUN | API/DB/launcher/G00, modele/Jev, assessment/comparație Strix, CI remote | Nicio autorizare nouă folosită pentru live; documentația nu închide aceste gates |

Eșecuri intermediare păstrate: teste noi RED pe contract absent; helper inițial a dat IndexError și a fost făcut assertion explicit; label case-sensitive al testului tools corectat; review-ul a dovedit false-green când întregul contract era fenced, apoi parent a reprodus RED pe fenced/quoted/duplicate/terminare prematură și a verificat GREEN; testul bannerului reader a eșuat înaintea schimbării de o linie; trailing whitespace a fost găsit și eliminat. Niciunul nu a fost ascuns prin skip, mock de produs sau modificarea Makefile.

## Review independent și limite

Primul review al §9.3–9.6 a fost **NO-GO**: outcomes uppercase incompatibile cu Key; template/case bindings absente; criteriu→task→result nelegat; Ref/digest/result identity insuficient definite; SERVICE fără alternativă de atestare; helperul testelor accepta exemple drept contracte. Au fost aplicate remedii normative și regresii, fără schema scaffold de produs.

**Re-review final: PASS**, independent și bounded pe cele șase remedieri, maparea LOCAL key→path, profilul nullable în draft și formularul HTTP-auth înaintea Chromium. Reviewerul a executat 20 teste țintite și controale negative în memorie pe vechile implementări, cu exit 0 pe remedieri, fără scrieri în checkout; suita completă de 39 este proba părintelui, nu atribuită reviewerului. Review-ul cross-document anterior a identificat cele două cicluri de bootstrap corectate, nu a fost raportat retrospectiv PASS. Review-ul separat al bannerului reader este PASS. Raportul complet final este la `/home/kali/.hermes/cache/scratch/omnis-amendment/final-review.txt`; concluziile durabile sunt consemnate aici. Un PASS documentar nu este validator de securitate, sandbox semantic, performanță măsurată sau dovadă de import OSS.

## Commituri locale

| Commit | Schimbare |
|---|---|
| `8275aa2` | docs(mission): adopt explicit full and focused assessment contracts |
| `5c1fad9` | docs(catalog): specify revisioned procedures and child briefing contracts |
| `733cbe4` | docs(tools): adopt attributed adapters and pinned OSS reuse units |
| `dba6ae3` | docs(flow): adopt adaptive investigation, modular work and Jev gates |
| `aedc2f0` | docs(evaluation): define matched Strix protocol and amendment traceability |
| `7640dff` | fix(docs): let each document declare implementation readiness |
| `0c51958` | docs(contracts): resolve review gaps in bindings and revision identity |
| `32b5f79` | docs(reuse): resolve source paths and qualify copyleft admission |

Alinierea statusului P0.4, marcarea dosarelor istorice și acest registru sunt în commitul care conține această versiune a fișierului; SHA-ul se citește din Git, fără hash autoreferențial. Nu s-a făcut push. Revert pe commituri și regenerare readers; nu există efecte DB/servicii de inversat în această sesiune.

## WIP și blocaje rămase

Căi păstrate separat: `api/src/omnis/core/db.py`, `api/tests/test_fixture_ownership.py`, `ops/compose.test.yaml`, `api/tests/test_database_url.py`, `ops/run_test_db_gate.py`, `tests/development/test_test_db_gate.py`.

Rămân: integrarea fixture-ului cu acordul autorului/operatorului și DB disposable atestat; lifecycle launcher P0.4, Stop/deadline și owner WIP înainte de promovare; proxyul respins și binding/confinare înainte de target effects; cont/model/data policy/buget înainte de live; compatibilitatea distribuției/notices înainte de importurile copyleft (nu numai Shannon); acceptarea vizuală a extensiilor noi; protocol/calibrare și măsurare înainte de claim comparativ. Următoarea felie și criteriul observabil sunt exclusiv în plan §19.2.
