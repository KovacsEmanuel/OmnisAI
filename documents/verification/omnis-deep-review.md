# Omnis — deep review de flux și livrare după HF01–HF10

**Review de specificație pe `adc849ed85d4996bdf66a71faa804367711d4bbb`, nu rezultat runtime sau plan alternativ.** Arhitectura decide comportamentul, planul decide ordinea. Cererea operatorului este o relectură de fond și detalierea fazelor înainte de terminarea P0, nu rescrierea implementării existente. Codul API/CLI/web/DB, cele șase căi WIP, prototipul/tokenurile și pinurile rămân în afara modificărilor acestei felii.

## Metodă și verdict inițial

Părintele a recitit integral handofful final, cele patru documente canonice, README/CONTRIBUTING/DESIGN și sursele modulare relevante; a urmărit independent scenarii bootstrap, full/focused, replan, Stop și publication. Subagentul independent a citit paginat aceleași documente plus review-urile OSS și a produs `/home/kali/.hermes/cache/scratch/omnis-deep-review/independent-review.md`. Constatările au fost confruntate înaintea primei editări canonice.

**Niciun HF01–HF10 nu lipsește integral.** Graful explicit are 19 noduri/27 muchii și este aciclic; acest lucru nu detectează singur dependențele implicite sau incompatibilitatea dintre contracte. Testele existente au trecut la bază (`make check-docs`: 39 teste, 5 readers sincronizate), dar nu dovedesc implementabilitatea tuturor fluxurilor.

Verdict inițial: direcția este coerentă, cu **patru blocante documentare înaintea consumatorilor lor**, plus clarificări utile. Acestea nu blochează fundația pentru a construi tot MVP-ul acum și nu sunt buguri runtime reproduse.

## Adjudecare înainte de editare

| ID | Constatare acceptată | Remediu canonic și moment |
|---|---|---|
| F01 | Eval cere material evaluat/publicat, dar candidatul nepublicat nu are traseu admis | CandidateSnapshot immutable + resolver înainte Publish, admitere PACKAGE_EVAL strict lab-only; seed PURE în B06/P4a, primele fixtures B11/B12, editor B14b. Fără publicare prematură sau runtime paralel |
| F02 | Verify login pre-Start nu are run/copil/MissionSpec obligatorii în ToolInvocation | Context OPERATOR_CHECK trusted, command/receipt/lease/Stop și același broker; numai login/health allowlisted, B07/B09h. Root Brain primește binding propriu pentru PREPARE/context, nu copil fictiv |
| F03 | „Orice revision stale refuzată” poate pierde rezultate legitime M1 după extindere M2 | Separă ingesta istorică, calificarea curentă și dreptul la lucru nou; compatibilitate de precondiții, duplicate și post-Stop fără wake. B06 apoi B10f/B18a/B19 |
| F04 | P2-live precede ownerul admission/budget declarat la B07 | Subfelie B06m: model dispatch/reservations/receipts și caps înainte G02-live; B07 adaugă target accounting pe același owner. Lipsa seam-ului fail-closed la pin blochează live, nu inventează API Hermes |
| C01 | Autorul unic uman poate fi blocat de interdicția generică self-approve | Separă operatorul de autorul AI și de evaluator; confirmare umană explicită după review/eval tehnic, fără autopublish AI și fără al doilea cont inventat |
| C02 | Dedup ipoteză/suprafață/familie omite procedură/input/context | Obligație semantică separată de redelivery key și attempt execution key; nu pierde taskuri legitime sau occurrences |
| C03 | Bootstrap focused poate primi un nou buget la fiecare envelope revision | Counter/reservation/deadline cumulativ per misiune, fără reset la re-entry/restart; suport separat dar contorizat |
| C04 | Clarificarea din G-FOCUS presupune STEER livrat numai la G-LOOP | P-FOCUS depinde explicit de P-LOOP/seam B18a; nu cere G-PATH și nu mută focused în prima BOLA |
| C05 | Research cere G-DATA final; maintenance boundary vine după worker | Subporți early/core înaintea primului apel/job, apoi extindere recovery/retention și cron opțional ulterior |
| C06 | Step refs nu pot lega outputuri viitoare/valori volatile | Binding tipizat StepOutputRef către pași anteriori, DAG/capability checks; fără expresii/DSL. Controls calificate cu bound procedure pentru rezultate multiple |
| C07 | Catalog enabled poate șterge promisiunea de coverage la disable | CoveragePromiseRevision/closure în snapshot, independentă de dispatch selection; disabled/unsupported rămân gaps |
| C08 | UI cere phase/subphase/instance dar RunProgress nu le enumeră | Câmpuri și prioritate în proiecția autoritativă, cu control state înaintea fazei; B08/B10/B18a |

Detalierea planului completează aceste remedii: traseu operațional și tabel de subfelii cu owner, consumator, ce păstrăm/modificăm/introducem, căi, intrare/ieșire, dependențe și gate. Nu mutăm B06/B07 în P0 și nu creăm încă directoarele sau tabelele respective.

## Riscuri păstrate pentru probele reale

Binding/lineage Hermes, fiecare request scanner/browser la sink, Stop sub I/O suspendat, rotația auth și coverage pe epoch, proiecția datelor/focusul semantic, eficacitatea Jev, fsync/retention/export concurent și admiterea exactă a surselor OSS cer implementare/teste reale. În special, SHADOW exclude influența recomandării, nu overheadul de timp/cost; auth refresh nu transferă implicit coverage și poate produce LIMITED. Aceste limite trebuie explicate în canon, nu ascunse printr-un PASS Markdown.

## Verificare și închidere

**Remedii aplicate în canon:** F04 în §5.2/B06m; F02 în §9.7 și UI08; F01/C01/C06 în §9.4/§9.8 și B06a/b→B11/B12→B14b; F03/C02–C04/C07–C08 în §6.3; C05 prin gates early/core înaintea auxiliarelor. Planul include acum RF01–RF12 în §2.1, SL01–SL36 în §4.2 și închiderea milestone-urilor în §4.3, cu căile/ownerii canonici sincronizați.

**Re-review independent al contractelor: PASS bounded.** Raport: `/home/kali/.hermes/cache/scratch/omnis-deep-review/contracts-rereview.md`. Reviewerul a reconstruit ordinea refs și scenariile F01–F04/C01–C03/C06–C08 fără un nou blocker. A notat corect limita testelor lexicale: prezența markerelor nu demonstrează enforcement sau state machines. Precizările neblocante despre check PENDING concurent cu Start și digestul material al ExecutionKey au fost incorporate; nu sunt prezentate ca buguri runtime reparate. Review-ul separat al planului detaliat/C05 a confirmat restul secvențierii și a găsit D01: poarta wordlist integrată era cerută înaintea propriului consumator. D01 este corectat prin G-WORDLIST-CORE înainte B15 și G-WORDLIST complet cu B15; re-review-ul punctual este PASS, inclusiv controale negative de recombinare a gate-urilor. Rapoarte: `delivery-rereview.md` și `wordlist-rereview.md` în același director scratch; concluziile durabile sunt păstrate aici. N01 de precizie a fost corectat: instance.py existent se extinde, iar uow.py nu este pretins deja creat.

Verificări finale ale părintelui după integrarea detaliilor și D01: 46 teste documentare PASS; DAG explicit 22 noduri/35 muchii, aciclic, prima BOLA fără strămoși browser/editor/Jev/paths/focused/research/wordlist/maintenance; 12 rânduri de flow și 36 de subfelii numărate programatic; 116 verificări Chromium PASS, zero JS errors/unexpected network. Inspecție reală a planului la 1440px și 390px: flow și tabel cu șase coloane lizibile, scroll local al tabelului, fără overflow global. Aceste probe sunt documentare/offline, nu aplicația sau aprobare vizuală nouă.

**Verdict final documentar:** F01–F04/C01–C08 și D01 sunt adjudecate și remediate în baseline. Nicio constatare documentară blocantă nu rămâne deschisă în aria acestor review-uri. Baza este pregătită pentru implementare incrementală și discuție pe §2.1/§4.2–4.3 ale planului, **nu o garanție de zero buguri și nu o certificare runtime**. P0 nu este declarat terminat, iar următoarea felie rămâne prerechizitul WIP/DB cu acord, apoi launcherul instalat din plan §19.2.

| Stare | Probă finală / limită |
|---|---|
| PASS | `python scripts/render_docs.py`, `python scripts/render_docs.py --check`, `python -m unittest discover -s tests/documentation -v`, `git diff --check`; 5 cititoare, 46 teste, exit 0 |
| PASS | `python tests/documentation/browser_check.py --include-documents --output "$TMPDIR/omnis-deep-review/browser-check.json"`; 116 checks, zero failures/JS errors/unexpected network; inspecție desktop/mobil a noilor secțiuni |
| PASS | Review independent core, review delivery cu D01 corectat și re-review D01; teste țintite ale reviewerilor, fără atribuire falsă a întregii suite |
| FAIL intermediar, remediat | Teste noi RED pe contract/ghid lipsă și pe gate wordlist recombinat; diagnostic OptionalMemberAccess inițial în test eliminat, fără ignore; nu eșec runtime pretins |
| BLOCKED | Preflight read-only pentru make check, exit 2: OMNIS_TEST_DATABASE_URL/OMNIS_TEST_PROJECT absente și contract UDS–TCP incompatibil; make check nu a fost lansat |
| NOT-RUN | API/DB/E2E/launcher, modele/Jev/target/eficacitate comparativă și CI remote; nicio declarație nouă G00/G02/G03/G08 |

Conservare: cele 6 hashuri WIP coincid cu snapshotul inițial; AGENTS/DESIGN/prototipul/tokenurile/handofful și manifestele de surse sunt neschimbate. Linkurile locale au fost verificate și nu există modificări intenționate ale codului de produs. Comiturile sunt locale, fără push/reset/stash sau rescriere de istorie.

Gate-ul complet `make check`/`make test` rămâne BLOCKED de fixture-ul DB WIP neintegrat; CI remote/live providers/assessment NOT-RUN, G00 deschis. Nu pornesc servicii sau un nou harness pentru acest review.

## Commituri ale acestei relecturi

| Commit | Schimbare |
|---|---|
| `4208b31` | docs(review): record deep flow findings before canonical edits |
| `47106ec` | docs(admission): deliver model reservations before P2 live |
| `52826e4` | docs(preflight): bind explicit checks without fictitious agent tasks |
| `01b122b` | docs(catalog): make pre-publication evaluation and procedure dataflow executable |
| `036ee02` | docs(replan): preserve valid history across adaptive revisions |
| `603e8fb` | docs(probes): distinguish provider-inert from target-inert execution |
| `39d5155` | docs(auxiliary): admit research and maintenance before first use |
| `9963213` | docs(flow): clarify pending checks and semantic dedup inputs |
| `2741ca0` | docs(plan): map the operating loop to concrete implementation slices |

Commitul care finalizează acest registru/readiness se identifică prin Git, fără hash autoreferențial. Toate remediile sunt documentare/test tooling; Git revert nu este prezentat ca rollback DB deoarece nicio DB nu a fost modificată aici.
