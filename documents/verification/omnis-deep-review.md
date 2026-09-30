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

**În curs:** acest checkpoint consemnează analiza/adjudecarea înaintea modificărilor. Rezultatele finale, remedierile aplicate, re-review-ul și commiturile se adaugă după execuția verificărilor. Gate-ul complet `make check`/`make test` rămâne BLOCKED de fixture-ul DB WIP neintegrat; CI remote/live providers/assessment NOT-RUN, G00 deschis. Nu pornesc servicii sau un nou harness pentru acest review.
