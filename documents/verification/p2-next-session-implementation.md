# Predare — prima QA DATA/admission acceptată scoped; STOP

**DOAR ÎN SESIUNEA FRESH — o sesiune, un rezultat verificabil.** Mandatul review/remedii/prima QA de mai jos a fost activat și executat; este acum **HANDOFF_ONLY / STOP**, nu comandă de rerulare. Nu relua batch2 sau nominal/Stop-first/send-first acceptate pe bytes neafectați. Notificările întârziate nu reactivează implementarea. Orice felie următoare cere acord explicit nou.

## CURRENT — ACCEPTED_SCOPED pe produsul75c6fab, fără închiderea DATA/P2

- Repo `/home/kali/OmnisAI`; branch `checkpoint/p2-batch2-pause-20261015`. Citește HEAD/status real; nu checkout/reset/stash implicit.
- Baza inițială `e521d92`, checkpoints `1c77676`/`1a36558` păstrate. Remedii granulare: `a2ddead` abort frozen înainte detach/A unlock; `c888ee2` corelare usage; `75c6fab` semantică receipt configurație. Commiturile ulterioare de documentare nu modifică snapshotul produsului.
- Manifestul final exact al celor **nouă fișiere** este în [raportul remedierilor](p2-integration-data-fixes-author.json), SHA256 `890d120a4c45b3840f5b665b9cfd8e145519188d8c51d1036b37e2ec3a0b319c`. Rapoartele inițiale și RED-urile sunt păstrate, nu înlocuite.
- **92SOURCE PASS/quality0**, două re-reviewuri [normativ](p2-integration-data-rereview-norm.json)/[safety](p2-integration-data-rereview-safety.json) APPROVED_SCOPED,6+4teste independente. DATA-SAFETY-F01 și DATA-NORM-F01/F02 CLOSED_SOURCE_SCOPED; [registrul](p2-integration-b06cm.md) păstrează dispozițiile exacte.
- **Prima QA PostgreSQL/UDS PASS_SCOPED:** [raport original](p2-integration-data-first-pg-qa.json), SHA256 `b5cffc401e3f56e591c1ea761e027d175c6ac6b182ba5c6e1b04672ccd74d3cf`; o singură tentativă,72PASS143.40s/exit0/drained. Nominal/Stop-first/send-first cu C-before-write și overlap PG observat; identități/preparation/peer sintetice, nu installed/native/live. Părinte a confirmat9SHA/receipt/rezultate/cleanup. **DATA/B06c/B06m/P2-inert NOT_CLOSED**, canonicalul integral NOT_RUN.
- Batch2 B01–B03 ACCEPTED_SCOPED în `94de21a`; release-first și Stop-first reale, cleanup verificat, roots consumate și selector închis. Nu repeta startup/batch2/H03/qualification pe bytes neafectați.
- Arhiva [fezabilității batch2](p2-bound-predicates-evidence/finite2-coherent-factory-feasibility.json) este păstrată pentru trasabilitate, **nu este lectură sau execuție necesară în această felie**.
- La predare nu există subagenți activi. Familia QA exited0/drained; CID/proiect/rețele/UDS/lockuri/postmaster proprii absente. PGDATA/loguri/imagine păstrate în rootul exact din registru; bazele per-test au fost eliminate conform fixture-ului, rândurile lor nu sunt declarate păstrate. HTML-ul preexistent `documents/Omnis_Notite_Originale.html` este **PROTEJAT: NU citi/hash/edit/stage/șterge**.
- **Următoarea singură felie propusă, NEAUTORIZATĂ/NEÎNCEPUTĂ:** duplicate concurente ale aceluiași protocol_id și conflict pe același owner/consumer; un singur send, fără grant/reserve dublu, overlap PG observat. Nu include automat caps/VALIDATION/UNKNOWN/canonical/Settings/live. Restul§4 rămâne deschis, fără waiver.

## 1. Contractul executat — istoric, nu instrucțiune de rerulare

Obține reviewurile și prima probă reală a verticalei existente:

`DATA/config calificată → reserve COMMIT → SENT COMMIT vizibil separat înainte de write → UDS NO_MODEL → receipt/accounting/readback`.

Probează **nominal, Stop-first și send-first** pe PostgreSQL și UDS reale, cu identitățile/preparation/peerul sintetic etichetate. Stop/send trebuie să aibă overlap PostgreSQL observat, nu numai ordine asyncio. Nu pretinde nativ installed, inferență, token enforcement live sau închiderea integrală DATA din aceste trei cazuri.

**Plafon de fază:** nu începe extinderea caps/duplicate/ACK-loss, Settings, canonicalul integral, P2-live ori P3 în această sesiune. Restanțele rămân în §4, fără waiver. Un finding de siguranță care blochează chiar primul consumer se remediază; nu se ascunde ca „felie viitoare”.

## 2. Ordinea de execuție

Roluri: **orchestrator** pentru scope/adjudecare/integrat/commit, un **dezvoltator** pentru cod, **reviewer** read-only pentru fiecare review complementar și **QA** pentru consumerul real. Nu crea procese numai pentru etichete. Admiterea fiecărei verificări: **cerință → consumer → risc → decizie**. **Nu porni un verifier pentru verifier. Nu preda după fiecare fix** din felia activă; predarea planificată este la rezultatul ei sau la un blocker/limită sigură, nu la fiecare raport.

1. **Intrare scurtă:** Git/status; verifică nouă hashes din raport și diff-ul lor față de baza reviewului. Păstrează modificările străine. Citește regulile repo, CURRENT/D1–D3 din [registrul integrării](p2-integration-b06cm.md), plan §7.1 și arhitectură §5.2/consumatorii afectați. Încarcă skill-urile relevante rolului; nu reciti baseline-ul, registrele sau logurile istorice integral. Rapoartele se filtrează la manifest/verdict/rezultate finale/obligații, nu se varsă integral în context.
2. **Două reviewuri complementare, același snapshot:** conformitate/ordine/persistență și safety/autoritate/concurență/input/cleanup. Reviewerii sunt read-only. Refolosește SOURCE neschimbat; rulează numai controalele care schimbă o decizie. Orchestratorul adjudecă; un singur dezvoltator reproduce/remediază findings cu RED→GREEN și affected checks. Re-review focalizat după ultima editare. Nu redesena D1–D3 fără defect concret sau contradicție normativă demonstrată.
3. **Prima QA, numai după blocante eliminate:** preflight fără efecte pentru argv/selecție, toolchain/sursă/acces și oracle. Folosește `test_model_admission_pg.py` și ownerul/runnerul existente; fără harness nou. Runnerul existent poate fi apelat prin `api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-model-admission-pg --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 600`. **`--check` este efectful, nu dry-run.** Targetul include regresii existente; nu îl slăbi pentru a selecta un pozitiv convenabil. Nu executa literal înaintea preflightului și a admiterii QA.
4. **Oracle:** reserve și SENT comise/corelate văzute de conexiunea C înainte de `writer.write`; bytes/request-id/digests/caps exacte. Stop-first după reserve: refuz înainte send/SENT nou și release numai cu no-send demonstrat. Send-first: Stop waiter real până la încheierea transportului finit. Runtime/frameurile private rămân fără expunere în rapoarte. QA verifică familia/resursele exacte și păstrează datele; outer exit0 singur nu este cleanup.
5. **Închide felia și OPREȘTE:** acceptare scoped sau BLOCKED/NOT_RUN precis. Comituri granulare, status/readback, raport original nesensibil păstrat durabil și un singur CURRENT actualizat în loc. Raport final scurt: ce a funcționat real, limitele, commiturile, resursele și următoarea singură felie. Nu continua automat la §4 chiar dacă mai este timp.

## 3. Frontieră încheiată și delimitarea istoricului

**Reviewul și prima execuție PG ale noului consumer sunt acceptate scoped; mandatul s-a oprit aici.** Nu există blocker deschis în această felie, dar restanțele§4 nu sunt acceptate. SOURCE/storage/lease/native-identity doubles nu devin probe native/installed. Pentru orice felie autorizată ulterior: după FAIL păstrează tentativa și izolează cauza, fără retry orb; după două cicluri numai harness fără progres la același criteriu, oprește ca BLOCKED și restrânge reproducerul. O sesiune nouă nu resetează contorul.

Nu promite zero compresii. Dacă nu mai poți păstra sigur contractul/snapshotul ori contextul devine insuficient, oprește și verifică writerii/familiile proprii, păstrează checkpointul neaprobat și predă înainte de a lansa alt ciclu. Nu lăsa starea de recuperare numai în chat/scratch și nu începe successorul ca să eviți o predare legitimă.

## 4. DATA → admission — următoarea verticală, același owner

**Backlog finit pentru sesiuni ulterioare, NU mandatul acestei sesiuni:**

- Duplicate concurente/conflict, caps calls/output, rezerva VALIDATION, buget imuabil și deadline expirat în așteptarea B.
- EOF/timeout/cancel după write cu SENT/UNKNOWN durabil, fără refund/resend; receipt întârziat după Stop, duplicate/conflict și accounting receive-only fără grant nou.
- Negativele dedicate DATA/owner/config/projection/ref/digest/receipt și canalele input/result/error/log încă neacoperite. Nu transfera automat probele helperelor la noul consumer.
- Reconcilierea exactă a celor opt criterii din plan §7.1 și canonicalul real pe bytes finali, cu cleanup/date păstrate. Refolosește acceptările neafectate; fără audit general sau număr nou de gates.

Ordinea globală rămâne **P2-inert → P4a-minim/Settings și browser afectat → acord separat P2-live → P3**. Fiecare sesiune următoare primește un rezultat observabil, acceptare și plafon propriu; nu un mandat implicit „termină tot”.

## Limite comune, neschimbate

Fără provider/model/target/r1/profiluri/global/push; fără conturi sau inferență. Nu mări grants/TTL/timeouts/caps, nu prewarm, nu fabrica native-turn/config/grant/rezultat. Full RPC frame conține capability: memory-only, fără log/persistare. Cost necunoscut rămâne null/UNKNOWN, nu zero. `FinalModelRequest` și NO_MODEL rămân stricte. Nu reutiliza roots consumate și nu adopta resurse străine. Secretele și logurile brute private nu intră în Git/chat.
