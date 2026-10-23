# R1 — oracle378 — CHANGES_REQUESTED_ORACLE_SCOPED

**Verdict propriu: două lacune P2 de discriminare temporală în oracle, nu defecte noi demonstrate ale produsului.** Delimitarea fixture/autoritate este corectă; predicatele încă permit expirarea între observația „live” și ACK. Remediile sunt aserțiuni locale, nu un alt harness. Nu cer PostgreSQL deja PASS pentru admiterea primei QA; părintele adjudecă aceste limite înainte de a credita o probă izolată de fence/held-connect Cancel.

## Identitate și limite

Read-only pe `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-378`: HEAD `37877c83ac2525f5480c5e5db091ea429eeec43b`, tree `b17bab44ab0eabd4cff4dc010e23383b6ff73499`, base `878895d3a4dda1f50c394dd01a711ac79acd1586`. Singura deltă: `api/tests/test_model_test_v2.py`, +49/−17, blob `9c583a60116b5cd1868900bd1dee8a8448d69481`, SHA-256 `cc359f0aafb287b033bef96608ecb6a617e74c21b1c4bf5aad23b04e4f6633ee`. Comparate cu manifestul părintelui: MATCH; checkout frozen clean; `git diff --check BASE HEAD` exit 0.

Reutilizez cele două `APPROVED_SOURCE_SCOPED` din `reviewer{1,2}-878-review.md` pentru produsul neschimbat; nu reauditez cele nouă fișiere. Am citit numai delta, fixture-ul și predicatele/callerii direct necesari.

## Findings concrete și remedii minime

### R1-378-F01 — P2 / proof gap: WRITE poate fi DENIED pentru expiry la recepție

`api/tests/test_model_test_v2.py:843–865` verifică prospețimea înainte de `writer.write`, dar după aceea există `await writer.drain()` și un read cu timeout de 1s, mai lung decât fereastra de cel mult 0.4s. Brokerul verifică timpul la procesare (`cli/src/omnis_cli/model_relay.py:115–123`).

**Contraexemplu static:** frame valid trimis înainte de deadline, procesat după deadline din cauza schedulingului; chiar fără fence/closed, brokerul poate răspunde exact DENIED/size=0, iar toate predicatele actuale trec. Nu afirm că s-a întâmplat; nu am executat un reproducer în această misiune fără efecte. `validate(late)` validează schema/UTC, nu prospețimea la procesare.

**Remediu minim:** imediat după citirea ACK-ului, cere și `datetime.now(UTC) < late_deadline`. Acesta exclude conservator expiry drept motiv suficient al unui rezultat creditat. Păstrează scope/connection reale, next sequence, deadline-ul fixture-only, ACK-ul exact și contoarele; fără autoritate DB nouă sau slăbirea expirării.

### R1-378-F02 — P2 / proof gap: Cancel poate câștiga settlement-ul după expirarea connectului

`api/tests/test_model_test_v2.py:711–717,735–768` demonstrează RUNNING și fereastră live **înainte de lansarea** Cancel. Apoi permite până la 3s pentru ACK, fără să mai verifice deadline-ul OPEN. `physical_release.is_set() == False` nu înseamnă că acel connect încă așteaptă: timeoutul brokerului poate anula `controlled_connect` fără release (`cli/src/omnis_cli/model_relay.py:160–175`).

**Contraexemplu static:** connect expiră; înainte de settlement terminal, Cancel cu revizia RUNNING câștigă lockul și persistă STOPPING, apoi obține FINISHED/CANCELLED + FENCE/DRAIN. Aserțiunile actuale pot trece, deși Cancel nu a întrerupt un connect încă live. Acesta nu este cazul terminal-wins/409: Cancel poate câștiga după expiry, dar înainte de settlement. Nu este o acuzație de regresie în produsul aprobat.

**Remediu minim conservator:** după ACK-ul Cancel și înainte de release, cere timpul încă anterior `min(utc(connect_scope.deadline), utc(connect_deadline))`. Astfel, succesul creditat nu poate proveni din expirarea naturală anterioară ACK-ului. Nu solicit o rulare PG pentru a valida acest review și nu propun instrumentare/framework nou.

## Ce este corect în deltă

- `model_rpc:353–358` capturează numai WRITE real cu reply OK, după RPC. Headerul din dispatchul al doilea parcurge producătorul real; pausa de body este înainte de `Stream.write` original. Scope/connection nu sunt reconstruite din DB; secvența +1 nu mai este replay-ul secvenței deja consumate. READ-urile TLS anterioare headerului sunt deja reflectate în secvența streamului.
- Frame-ul raw păstrează scope/connection, folosește request UUID nou, size/body concordante, capability-ul canalului propriu și `validate(late) == captured_scope`. Deadline-ul este limitat de scope și de now+0.4s; comentariul spune explicit mutație adversarială de fixture, **nu grant DB nou după Cancel**.
- Held-connect este chiar apelul `sock_connect` al brokerului OPEN: non-AF_UNIX, interceptat înainte de connectul loopback real (`:299–312`). Primul consumer este încheiat, transportul se închide explicit, iar al doilea start produce singurul OPEN model nou capturat. RUNNING/op ID, revizia citită pentru Cancel, ACK 202, FINISHED/CANCELLED, readback identic și FENCE/DRAIN pe scope-ul OPEN sunt cerute înainte de release. Callerul neschimbat `model_sender.py:120–126` părăsește guardul SQL înainte de OPEN; nu transfer această inspecție în dovadă PG executată.
- Baseline-ul contoarelor este luat după ACK; după release se cer zero connect/handoff/request noi și lipsa settlement_failed (`:769–781`). Body cases compară după raw WRITE și release cu același baseline (`:840,883–895`).
- DNS păstrează așteptarea threadului și absența terminalului înainte de release. Expiry-connect/write nu rulează Cancel și cer FINISHED/UNKNOWN, usage/cost necunoscute și zero efecte tardive. Terminal-wins cere separat exact 409/REVISION_CONFLICT și readback neschimbat (`:619–630`). Aceste scenarii nu au fost slăbite.

## Dovezi și handoff

Citite, nu rerulate: `oracle-final-collect.log` — 28 collected/exit0, fără PG; `oracle-final-quality.log` — affected lint/typecheck exit0; `oracle-final-diff.log`; `oracle-commit-readback.log`. Verificările proprii au fost numai citiri și Git read-only/identity/diff-check. Nicio execuție de teste, PG, rețea, servicii, browser, credentiale ori modificare Git/produs. Counterul istoric 2 rămâne neschimbat; reviewul nu admite un al treilea harness orb, T1 complet sau runtime PASS. Numai acest raport a fost creat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Omis: reaudit sursă neschimbată și execuție consumer/PG. Risc: fără cele două predicate temporale, un PASS ulterior nu izolează complet fence-ul de expiry sau anularea connectului de settlement-ul ulterior expirării.
