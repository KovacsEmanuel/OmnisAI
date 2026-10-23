# R2 — 378 oracle delta

**Verdict: CHANGES_REQUESTED_ORACLE_SOURCE_SCOPED — un singur finding de atribuire temporală, nu defect nou de produs.** Aprobările SOURCE ale produsului neschimbat din `reviewer{1,2}-878-review.md` rămân la scope-ul lor. Lipsa execuției PG nu este motivul acestui verdict și nu este prerequisite circular pentru QA.

## Snapshot verificat

- Frozen checkout: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/model-review-378`.
- Base: `878895d3a4dda1f50c394dd01a711ac79acd1586`.
- HEAD: `37877c83ac2525f5480c5e5db091ea429eeec43b`; tree: `b17bab44ab0eabd4cff4dc010e23383b6ff73499`.
- Unicul delta: `api/tests/test_model_test_v2.py`, +49/-17; blob `9c583a60116b5cd1868900bd1dee8a8448d69481`; SHA-256 `cc359f0aafb287b033bef96608ecb6a617e74c21b1c4bf5aad23b04e4f6633ee`.
- Manifestul `parent-oracle-378-freeze.json`, lista delta Git, HEAD/tree/blob și SHA-256 verificate programatic: MATCH; frozen checkout clean; `git diff --check BASE HEAD`: exit0. Produsul nu are delta.
- Checkoutul principal observat la `de7a3705a53154a9234f31126167670a07d2200e`, numai HTML-ul protejat preexistent untracked; neatins.

## Must fix — F1 / P2: prospețimea verificată numai înaintea așteptării nu exclude expiry ca explicație a succesului oracle-ului

**Locații:** `api/tests/test_model_test_v2.py:715-717,753-768,843-865`.

**Scenariu concret:** la raw WRITE, `late_deadline` este corect construit și încă viitor la linia862. Totuși, după această verificare există `writer.drain()` și așteptarea răspunsului, cu timeout1s. Dacă brokerul este programat după cele0.4s, ramura `cli/src/omnis_cli/model_relay.py:120-123` poate returna exact același DENIED pentru expirare, chiar dacă mecanismul de fence/closure testat ar fi defect. Identitatea răspunsului și contoarele rămân corecte, deci testul poate trece. `validate(late)` validează forma, nu prospețimea la procesare.

Aceeași lacună de atribuire există pentru held CONNECT: OPEN este valid la snapshotul RUNNING, dar `await action` permite3s, peste fereastra OPEN de cel mult0.5s. Expirarea OPEN în timpul procesării Cancel poate elimina connectul suspendat înaintea FENCE/DRAIN. FINISHED/CANCELLED și ACK-urile scoped ulterioare nu demonstrează singure că taskul încă avea o fereastră fizică validă când a fost drenat. Acesta este un posibil fals pozitiv al testului, nu o afirmație că interleavingul a fost observat în PG.

**Remediu minim:** păstrează toate verificările existente și adaugă verificarea termenului la capătul observat al fiecărei probe:

1. Imediat după citirea răspunsului raw (`:865`), cere `datetime.now(UTC) < late_deadline`. Astfel un DENIED recepționat după expirare nu poate conta drept proba dorită. Scope deadline este deja limita superioară a `late_deadline`.
2. În ramura CONNECT după răspunsul Cancel și ACK-urile scoped, înaintea release, cere încă `datetime.now(UTC) < min(utc(connect_scope.deadline), utc(connect_deadline))`. Dacă DB/IPC nu încap în autoritatea existentă, proba eșuează/neconcludentă în loc să crediteze expiry drept cancellation fizic. Nu mări deadline-ul și nu fabrica grant DB nou.

Sunt două aserțiuni pentru aceeași proprietate: fereastra fizică trebuie să rămână validă până la observația care îi atribuie refuzul/anularea. Nu este cerut un framework, un alt runner sau reluarea celor86 teste neschimbate.

## Ce este corect în deltă

- **Secvență și canal:** captura WRITE se face acum numai după ACK `OK` (`:356-358`). Pausa body este înainte de `original_write` (`:788-794`), iar headerul precedent a parcurs canalul real. `captured_sequence + 1` nu mai este replayul secvenței deja consumate. `CipherStream.send` avansează secvența la fiecare ciphertext WRITE; `receive` o avansează separat, dar în fluxul inspectat nu există READ între headerul cererii și pausa pre-body. Controlul SOURCE `test_model_relay_scopes.py:183-202` păstrează WRITE pozitive/negative pe aceeași conexiune, fără a-i transfera autoritate PG.
- **Scope/owner:** scope-ul nu este reconstruit din HTTP ori inventat din DB. Callback-ul CURRENT folosește `write_guard(identity)`; acesta verifică operația RUNNING, owner/epoch/generation, dispatch/cancel_epoch/config/deadline și produce scope-ul dispatchului (`model_test_runtime.py:598-706`). ID-ul scope-ului este dispatch_attempt_id, nu operation_id; nu trebuie comparat greșit cu `second_id`. Captura OPEN precede exact RPC-ul care ajunge în hookul connect; închiderea transportului anterior forțează noul OPEN, iar metadata este exclusă de filtrul MODEL_DISPATCH.
- **Held CONNECT:** hookul `:299-312` este o așteptare asyncio anulabilă, înaintea apelului original către listenerul loopback deținut. Snapshotul real RUNNING furnizează expected_state_revision. Testul cere202, FINISHED/CANCELLED, readback egal și FENCE/DRAIN `OK` pe scope-ul capturat înaintea physical_release; după release cere contoare neschimbate și zero connect/handoff nou. Nu transferă așteptarea threadului DNS: numai DNS cere acțiune încă pending până la release. Rămâne lacuna temporală F1.
- **Late WRITE:** scope/connection/capability sunt cele reale, request_id nou, next sequence, fereastră adversarială explicită <=0.5s și limitată de scope; comentariul nu o prezintă drept grant DB post-Cancel. Răspunsul DENIED trebuie să aibă exact identitatea cererii. Contoarele sunt luate după ACK și comparate după raw/release; acestea nu sunt doar totaluri pre-operație.
- **Controale păstrate:** Cancel strict202/FINISHED/CANCELLED/readback; settlement-before-Cancel strict409/REVISION_CONFLICT/readback terminal neschimbat (`:619-630`); expirările CONNECT/WRITE fără Cancel concurent și UNKNOWN/usage/cost necunoscute; lipsa resend și consumul secvenței înaintea efectului nu au fost slăbite.

## Dovezi și limite

Citiri read-only: README CURRENT, CONTRIBUTING (product-first/preflight/counter), statusul afectat, manifestul, ambele rapoarte878, delta și ramurile producător/protocol/broker necesare atribuirii. Comenzile Git și verificarea stdlib au terminat exit0. Un output inițial prea mare a fost trunchiat; fragmentele necesare au fost ulterior citite explicit, fără a deduce verdictul din porțiunea omisă.

Loguri existente citite, nu rerulate: `oracle-final-collect.log` —28 colectate/1.39s, numai collect; `oracle-final-quality.log` — comanda scoped lint-api/typecheck-api, exit0. Nu le creditez ca probă de concurență PG. Nu am inspectat mutable runtime-src.

Nu am executat teste, cele86 neschimbate, PG, servicii, trafic, provider, browser, instalări ori acces la secrete; nu am modificat surse, Git, counterul2 sau logurile istorice. Singurul fișier creat este acest raport. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

După remediul minimal și re-reviewul exact al oracle-ului, următorul obiectiv legitim rămâne consumerul PG bounded, nu obținerea anticipată a PASS-ului pe care QA trebuie să-l producă. SOURCE approval nu închide P1 physical proof, PG sau T1 și nu autorizează T2/succesor. Counterul2 și atribuirea istorică UNATTRIBUTED se păstrează.

Omis: auditul produsului neschimbat și orice probă efectuală. Risc: oracle-ul curent poate încă atribui expiry drept refuz/anulare post-fence; concurența PG rămâne NOT_RUN.
