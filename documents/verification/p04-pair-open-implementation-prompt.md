# SL03 / P0.4c — prompt de implementare pair/open

## Rol și punct de plecare

Acesta este un handoff executabil derivat din plan, nu un plan concurent sau o dovadă de implementare. **SL03 este NOT_IMPLEMENTED / NOT_RUN / NOT_REVIEWED la pregătirea promptului.** Executarea începe numai când operatorul transmite promptul pentru implementare.

- Repo de lucru: OmnisAI; fixează la intrare HEAD-ul și branch-ul locale reale, nu remote-ul sau un SHA presupus din conversație.
- Baza documentară de pregătire: `e6adbfc`, după corectarea statusului CLI și a explicației pentru operator; citește revizia completă din Git.
- SL02 este `REMEDIATION_PASS` în scope / `READY_FOR_SL03: YES` numai pentru dezvoltare. Dovada canonică de produs rămâne pe `c914fda`: `make check` → `make check-installed-start`, exit0/exit0, 308 intrări versionate stabile și readback al resurselor proprii. Promptul și commiturile documentare nu transferă acel PASS la cod viitor.
- G00 deschis, CI remote NOT_RUN, assessment_ready=false. M03/config, M21/crash-recovery și M22/parser păstrează obligațiile din matrice înainte G00.
- Păstrează fișierele și worktreeurile preexistente. `documents/Omnis_Notite_Originale.html` este originalul protejat, nu parte din livrare. Cele două recuperări istorice RECOVERY_PENDING rămân separate; nu le adopta, opri, șterge sau folosi ca fixture.

## Autoritate și lecturi țintite

Citește AGENTS.md, README.md, CONTRIBUTING.md și skill-urile proiectului `omnis-delivery`, `omnis-project-status`, `omnis-review-qa`, `omnis-release-ops`; pentru cod aplică TDD și review independent. Citește numai secțiunile relevante:

- [Plan §4.2, §5, §19.2](../Omnis_Implementation_Plan.md): SL03, B01f, L05-control și succesiunea SL03 → SL04 → G00 → B02.
- [Arhitectură §4.1–4.5](../Omnis_MVP_Architecture.md): launcher instalat, TTY, origin/Host, readiness, browser și zero efecte provider/target.
- [Harta actuală](implementation-status.md), [închiderea SL02](p04-deep-remediation.md) și [matricea restanțelor](p04-deep-remediation-matrix.json). Auditul anterior rămâne istoric, nu un blocker neremediat implicit.
- `cli/README.md`, `cli/src/omnis_cli/{main,start,status,health,release,lifecycle}.py`, consumatorii și probele instalate existente; `api/src/omnis/security/`, `api/src/omnis/transport/local_control.py` și pairing/session/logout din web.

Arhitectura decide comportamentul, planul ordinea și gates. La contradicții reale fixează problema și decizia necesară înainte să extinzi scope-ul; nu inventa API-uri, câmpuri de protocol sau aprobări.

## Rezultat observabil cerut

Livrează **SL03 / P0.4c / B01f pair/open**, ca extensie funcțională a produsului instalat, nu ca stub sau harness substitut.

1. **`omnis pair`:** pe o instanță verificată și ready, emite prin controlul local privat un cod nou one-use/expirabil folosind pairingul P0.2–P0.3. Afișează codul numai într-un terminal interactiv; nu îl emite în non-TTY, redirecționare, JSON, URL, argv, loguri, Git sau diagnostice. Verifică precondiția TTY înaintea emiterii; orice format machine-readable refuză divulgarea. Nu crea endpoint public/admin ori al doilea issuer/session store.
2. **`omnis open`:** deschide browserul numai pentru originul unei instanțe deja pornite, identificată și verificată prin contractele existente. Nu pornește servicii, run sau assessment; un port HTTP care răspunde nu este dovadă suficientă. Nu folosi un origin din cwd, un receipt neverificat sau un port/config nou pentru a rebinda instanța existentă.
3. **`omnis` implicit:** reutilizează startupul idempotent SL02, așteaptă dashboard readiness și oferă deschiderea browserului conform arhitecturii. La pairing păstrează limita TTY. Cu sesiune web validă shellul existent rămâne direct utilizabil; cu sesiune absentă se folosește formularul pairing deja livrat. Nu inspecta profilul browserului personal și nu reconstrui autentificarea.
4. **Browser absent sau opener eșuat:** rezultat și diagnostic sanitizate, fără succes inventat. Distinge startup/readiness de rezultatul openerului. Un apel acceptat de opener nu probează singur fereastra afișată ori sesiunea paired; probează separat proprietățile revendicate.
5. **Compatibilitate:** `omnis start --no-open [--json]`, status, install și install-image rămân funcționale. Headless nu emite cod și nu invocă browserul. Nu relaxa validarea manifest/receipt, SC01/SC02, ownership/pidfd, cleanup sau protocolul strict.
6. **Readiness și M21:** pair/open refuză instanțe neREADY, stale sau cu identitate/origin necorelate. Nu redeschide admiterea, nu promovează ownership WIP și nu implementează recovery automat pentru a trece aceste refuzuri.
7. **Inert:** startup/status/pair/open nu fac validate/discovery/pricing/OAuth refresh/inferență provider și nici trafic target. Browserul operatorului către originul local nu este worker browser de assessment; assessment_ready=false și capabilitățile nelivrate rămân UNAVAILABLE.

Definește înaintea primei modificări contractul exact de output/erori și fișierele necesare în registrul feliei. Cheile sau exit codes noi trebuie justificate și testate, nu pretinse deja canonice.

## Limită de modificări și non-obiective

Extinde prioritar `cli/` (`main.py`, helper-ele `pairing.py`/`browser.py` dacă necesare, teste și probe instalate). Schimbări minime în API/security/control numai dacă integrarea reală le cere, cu contract/test/review. Refolosește shellul, protocolul privat și oracolele existente; fără framework sau supervisor de teste nou.

- Nu începe SL04, B02/P1, runtime-host, model/provider, proxy target, SSE/B08 sau un redesign UI.
- Nu livrează aici parserul M22/config.toml ori certificarea integrală M03. Păstrează aceste obligații înainte G00 și verifică originul existent din receiptul atestat, fără a transforma amânarea parserului în bypass.
- Nu modifica AGENTS.md prin bypass, profilele personale Hermes, firewallul global, conturi sau servicii de boot. Fără sudo/instalări/pull/upgrade implicit la pornire.
- Fără push, reset/clean/stash distructiv, pierdere de date, kill/adopție pe PID numeric din jurnal sau intervenții asupra recuperărilor istorice.

## Implementare, probe și acceptare

Lucrează în schimbări mici coerente, RED → GREEN → refactor → review/adjudecare → commit, fără refactor oportunist. Reviewerul verifică un diff/snapshot exact, read-only; execuțiile autorului nu sunt execuțiile reviewerului. Înainte de fiecare commit păstrează soluția KISS/DRY, stilul local, diff fără secrete și stage numai fișierele intenționate.

Matricea cerință → cod → dovadă trebuie să acopere pozitiv și negativ pe același canal:

- CLI real instalat din wheel/bundle actual, cwd extern și XDG privat propriu; `omnis` nou și reuse, pair și open pe instanță validă. Nu presupune importul sursei drept execuție instalată.
- PTY real pentru emiterea TTY; pipe/redirecționare/non-TTY/format machine-readable refuzate **înainte de emitere**, fără cod în outputurile persistate. Valorile sintetice sensibile rămân private; rapoartele publică numai rezultate sanitizate.
- Cod acceptat o singură dată, al doilea consum și expirarea refuzate; pairing real în shellul existent și readback sesiune/logout. Etichetează explicit dacă ceasul sau alte seams sunt substituite.
- Instanță absentă, neREADY, stale, origin/Host/receipt inconsistent și serviciu străin pe port: fără emitere cod/deschidere de pagină străină/mutație de lifecycle.
- Opener reușit/eșuat/indisponibil și URL exact fără cod, cu argumente sigure. Mockul openerului probează doar consumerul; pentru orice revendicare de browser/sesiune reală folosește browser/profil de laborator propriu și dovadă independentă.
- Regresii headless/start/status și zero provider/target pe boundary-urile reale disponibile. Absența dovezii nu devine zero apeluri.

Integrează probele SL03 în verificarea reală a artefactului; nu inventa un target PASS sau o copie care evită comenzile produsului. Rulează întâi verificările țintite CLI/API/web afectate și docs, apoi **secvențial**, fără concurență pe aceleași venvuri/artefacte, `make check` → `make check-installed-start`. Păstrează toolchain-ul fixat și verifică identitatea bytes înainte/între/după; reconstruiește artefactele afectate. Noua acoperire L05-control trebuie executată și identificată explicit; trecerea vechiului installed-start nu o certifică singură.

Citește orice FAIL, repară cu reproducer, rerulează după ultima modificare relevantă. Dacă o verificare nu este posibilă, raportează comanda și blockerul concret ca BLOCKED/NOT_RUN; fără fallback mock/SQLite/skip prezentat drept PASS și fără rerulări identice numai pentru bookkeeping. Reviewul raportează și aplicabilitatea Reticle/Chisel conform skill-urilor curente, fără instalare sau instrumentare neautorizată.

Cleanup numai pentru resursele proprii atestate: readback exact, date păstrate, rescue distinct de succesul produsului. Incertitudinea se păstrează în diagnostic/dispoziție; nu pretinde ALL_CLEAN. Închiderea browserului/terminalului nu ține loc de `omnis stop` durabil.

## Predare și condiție de oprire

Persistă deciziile, probele reale, încercările eșuate relevante, snapshoturile și verdictul/adjudecarea în `documents/verification/p04-pair-open.md` la executarea feliei; actualizează numai faptele schimbate în harta existentă și README/plan dacă este necesar. Documentarea și configurația au commituri coerente separate; toate modificările intenționate trebuie comise și verificate prin Git readback, fără push.

Încheie cu: comportamente livrate, comenzi/exit și limite, review independent, commituri, cleanup/dispoziții și restanțe. Explică simplu poziția în P0 înaintea matricei globale compacte în română. **SL03 acceptat nu închide P0/G00:** pasul nou următor rămâne SL04, cu M03/M22 și probele restante înainte G00. Nu continua automat SL04 în această rundă; nu declara SL03 complet dacă un criteriu cerut este neexecutat sau blocat.
