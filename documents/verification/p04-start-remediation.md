# SL02 — remedierea SC01/SC02 și acceptarea delimitată

**Audit ulterior: CHANGES_REQUESTED pentru SL02**, vezi [RT-F01/RT-F02 și AR01/AR02](p04-pre-sl03-deep-review.md), confirmate și neremediate. SC01/SC02 și corecția VERIFYING din acest registru rămân închise în scenariile probate; acceptarea și matricea 16/6/4 de mai jos sunt checkpointul istoric înaintea noilor contraexemple. Matricea actuală este 13 COVERED / 4 GAP / 5 PARTIAL / 4 DEFERRED. Nu relansa un gate vechi ca substitut pentru noile regresii.

## Contract înainte de cod

Bază reală: `d940864c5ec9db56bfdc96237c71ef4f68d7aa81`, branch `p04-control-topology-wip`; index și tracked curate. `documents/Omnis_Notite_Originale.html` rămâne untracked/protejat, SHA-256 `783c5b8dc3f4c00b0e3d3267560bc9a5abedeb4fab44f96eb07718a545b9c79f`. AGENTS nemodificat. Referințe: [prompt](p04-start-remediation-prompt.md), [audit/26 cerințe](p04-start-completeness-review.md), plan §4.2/§19.2, arhitectură §4.1–4.5. **La acest checkpoint remediile și gate-urile noi sunt NOT_EXECUTED.**

- **SC01:** copil propriu real terminat prin semnal → starea producătorului `ControlRuntime.run` → cleanup real cu efecte/inventar Docker substituite → zero stop/remove DB și `UNCERTAIN`/exit 4/jurnal păstrat. Returncode negativ independent de `success`; diferențiere succes, refuz read-only cunoscut, nonzero mutant nereconciliat, timeout și decoding. Fără semnale PID/PGID după reap; familia necunoscută nu devine drenată din simplul reap al liderului.
- **SC02:** decoder JSON real pe manifest profund imbricat sub 32768 bytes; conversie îngustă la `ReleaseError`. Console script din wheelul nou, cwd extern, XDG privat: exit 2, JSON `REFUSED`/`RELEASE_OR_IMAGE_INVALID`, flags false, fără traceback/payload/secrete/stare nouă. Păstrăm release valid și refuzurile obișnuite.
- **Fișiere:** `cli/src/omnis_cli/start_runtime.py`, `release.py`, testele CLI relevante; `start.py` numai dacă regresia o cere. Integrarea instalată existentă și documentele/statusurile numai după probe. Nicio modificare a DB/migrărilor 0001–0004, `omnis.serve`, runnerului DB/owner WIP sau gate-urilor pentru a fabrica GREEN.
- **Ordine:** pentru fiecare defect RED → minim GREEN → review independent read-only pe snapshot exact → commit local. Apoi `make test-cli`, lint/format/mypy existente, `make check-cli-wheel`, console script extern; secvențial `make check` și `make check-installed-start` pe codul final, fără gates concurente pe artefacte/venvuri.
- **Review final:** direcție SC01, direcție SC02/26 cerințe și inventar independent plan până la P0.4/SL02. Defect, probă parțială și scope deferred rămân distincte; fără „tot MVP implementat”. Nu SL03/SL04, push, conturi, model calls sau target traffic.
- **Unelte:** skill-urile locale delivery/release-ops/failure-boundaries/review-qa/project-status/Reticle/Chisel citite. Chisel este NO-GO și nu primește acces la repo. Reticle poate verifica numai fixture-ul instrumentat separat; nu certifică defecte CLI și nu este cablat implicit în produs.

## Prerechizite și efecte externe

Verificat înaintea editărilor: API/CLI Python 3.13.15, uv 0.12.19, Node 24.21.0/npm 11.19.0; import CLI din checkoutul curent. Docker client/server 27.5.1+dfsg4, endpoint Unix `/var/run/docker.sock`; imaginile PG18.6 și Python3.13.15 din pinurile Makefile există amd64. Fără overrides ambientale Docker/Compose/PG/test DB. PATH pin-uit folosește tools din `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/`.

Baseline extern read-only: două containere active preexistente `8143ec40ecabf29d13c78d9114206732b56a550796548d478f594c240eb9ceb6` și `dabab333533ba7010ffd623bbf2fe94cb7ce2f04cb5a9c04c2edb2e82914ad27`; plus containere oprite preexistente, neatinse. Probele creează numai roots/proiecte/resurse proprii noi în scratch. Nicio adopție a DB-urilor vechi. Cleanup/readback exact prin runnerul existent; date/diagnostic păstrate, fără down -v/prune. Dacă daemonul/familia rămân incerte, păstrăm resursele și locatorul, nu rescue pentru PASS.

## Probe și adjudecare înainte de gate-urile finale

### SC01 — commit `0c2a373`

- RED al părintelui, `cli/.venv/bin/python -I -m unittest discover -s cli/tests -p test_start_process.py -k test_signal -v`: 2 metode, 3 failures/subteste; copil real `returncode=-9`, `uncertain=false`, două efecte DB substituite. RED suplimentar: nonzero mutant, UnicodeError după exit, timeout/family și excepție post-reap.
- Primul review independent `deleg_e9184a74` a găsit două P1 reale în remediul intermediar: SIGTERM la close/finally ocolea flagurile; două SIGTERM între kernel reap și publicarea returncode permiteau semnale numerice după reap. Părintele le-a reprodus: `-k interrupt` → 2 failures, înainte de corecție. Tentativele killpg post-reap au fost interceptate, nu executate.
- Remediu final: starea conservatoare începe înainte de spawn și durează până după wait/close/decode; nonzero mutant nu dovedește refuzul efectului. `waitid(WNOWAIT)` păstrează identitatea până la revocarea autorității numerice înainte de wait. EOF înainte de ieșire are deadline; excepțiile păstrează familia incertă. Succesul/refuzul read-only ordinar păstrează flagurile anterioare; nu se promovează ownerul WIP și nu se schimbă `start.py`.
- GREEN: 30 teste startup și apoi `make test-cli` **73 PASS**, Ruff/format/mypy CLI exit 0. Re-review `deleg_d03af3c7`: **APPROVED_SCOPED SC01/R1/R2**, 14 teste proces rulate independent; părinte adjudecat fără blocante. Snapshot diff SHA-256 `3e2607984d2cb0630f66cd5dfc73765f90bd107026a23d98776d38e0cfdaddca` este comis în `0c2a373`. C1 neblocant: flagurile anterioare sticky sunt verificate static, fără subtest dedicat în acel snapshot.
- Limite: copil/semnal/kernel reap/main/cleanup/jurnal reale, daemon/inventar/atestare DB substituite. Nu s-a oprit DB reală în reproducer, nu s-a măsurat delayed Docker ACK sau drenarea tuturor descendenților detached. Exit 4 fără zero efecte DB nu a fost acceptat.

### SC02 — probe înainte de review/commit

- Manifestul sintetic are 30001 bytes, sub limita 32768. Testele permanente `cli/tests/test_manifest_boundary.py` au dat RED: RecursionError real din decoder și exit 1 al console scriptului, nu import/dependință absentă. Wheelul pre-remediu, proaspăt construit cu `make check-cli-wheel`, a reprodus exit 1/stdout gol/traceback din cwd extern; 12 module instalate identice cu sursa.
- Conversie îngustă numai `RecursionError` la decoder → `ReleaseError("Invalid release manifest") from None`; schema/checksum/path/unique keys și frontiera startup existente sunt neschimbate.
- GREEN: `make test-cli` **75 PASS**, `make check-cli-wheel UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv` **75 teste instalate PASS** din cwd scratch. Ruff/format/mypy exit 0.
- Console script instalat real: `omnis start --no-open --json` → **exit 2**, JSON exact `state=REFUSED`, `reason=RELEASE_OR_IMAGE_INVALID`, `dashboard_ready=false`, `assessment_ready=false`, `browser_opened=false`; stderr gol, state/runtime absente, manifest nemodificat și niciun lock/receipt nou. Toate cele 12 module wheel coincid byte-for-byte cu sursa; SHA release.py `af962c411958d0d2c3f0a6973b4f2c203b743d36bf93fbc1e8af9aad0fa05142`. Script verificator `check_installed_sc02.py` în scratch; regresiile permanente afirmă contractul sigur, nu defectul vechi.
- La acest checkpoint review-ul SC02 și review-ul matricei 26 sunt **IN_REVIEW** (`deleg_1eb4728a`); `make check` și OCI final sunt **NOT_RUN**. Niciun PASS istoric nu este transferat.

### Review de plan și unelte de dezvoltare

Audit independent read-only `deleg_3d365048` la `d940864`: 36/36 SL, E1–E4, B21m și 13 EXECUTION_UNSCHEDULED concordante cu planul; niciun defect de produs nou confirmat. Părintele a comparat programatic cele 36 de ID-uri unice cu planul canonic, nu numai totalul declarat în JSON. Fundațiile P0.1–P0.3/SL01 sunt păstrate; SL03/SL04 și restul MVP rămân nelivrate la nivelul livrabilelor de produs. Ramura `chore/p02-test-typing` are un commit exclusiv; nu este integrată sau creditată implicit. Nu s-au făcut merge/switch/fetch/push.

DOC-R01, formularea Reticle «no app», este adjudecată și corectată separat în `f19de18`: aplicația P0.3 există, instrumentarea Reticle a ei nu. Smoke Reticle real rulat în namespace loopback-only cu Node22.22.0/Playwright1.60.0/headless148.0.7778.96: exit 0, state `verified=yes`, controale HTTP200/500 corecte, count=1, listener-ele 14400/14401 absente după cleanup. Root `/home/kali/.hermes/cache/scratch/omnis-reticle-l54fneqt`; dovadă sintetică separată, nu certificat UI produs sau SC01/SC02. Chisel rămâne NO-GO/neactivat, fără reevaluare sau bypass.

Lecțiile R1/R2 sunt păstrate în referința skillului local release-ops, commit `9f3d32a`; 35 teste development PASS. Nicio configurație/profil Hermes global schimbată.

## Gate final inițial și extindere justificată a scope-ului

Pe codul comis `7c223744e5752116a79bff71e09f0a48c8b9cea6`, `make check` a trecut, exit 0 (`proc_933ad9411647`): 62 docs, 35 development, 218 API, 17 migrări, 20 web +7 E2E, 75 CLI sursă +75 wheel +1 live CLI/DB, 37 release/observer; checks/audits/build trecute. Fixture `db-7fa41c503fd04cda`, proiect `omnis-p01-875854fd27d643aaab61f0e62950d835`, CID `d9a9f3a56681fe5d7fba35d1c3277e2b08e7cf1baf2b1e2f282830573e8bae36`; receipt exact `{schema_version:1,code:0,family_drained:true}`. Readback părinte: CID/proiect/rețele/socket absente, `data/18/docker/PG_VERSION=18` păstrat.

**`make check-installed-start` ulterior: FAIL/exit 2**, proces `proc_15b738955ddc`, nu PASS transferat. Calea pozitivă reală a trecut: `/home/kali/.hermes/cache/scratch/s2-esct8v8b/probe-receipt.json` are `probe=PASS,cleanup=VERIFIED`. Întreruperea separată `/home/kali/.hermes/cache/scratch/s2i-841796q5/probe-receipt.json` are `probe=FAIL,cleanup=UNCERTAIN`, `failed_phase=VERIFYING`, `CLI descendants uncertain`; DB a fost păstrată corect, nu recuperată artificial pentru verdict.

Resursă păstrată: DB CID `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0`, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, root `s2i-841796q5/s/omnis`, data home `omnis-bundle-00k_mea_/data`. Nu adoptăm/oprim această DB incertă pentru rerulare; istoricul/jurnalul rămân neschimbate. Noua probă va avea alt proiect/root.

Cauză verificată în cod: `start.py` publica `VERIFYING`, apoi executa `api_process`/atestări Docker, apoi începea `wait_dashboard` HTTP. Oracle-ul instalat așteaptă VERIFYING pentru întreruperea read-only fără subprocess, dar markerul precede frontiera reală. Aceasta este interacțiunea PROOF-GATE anticipată în reviewul de completitudine, acum reprodusă. **Extindere permisă de contract:** atingem minimal `cli/src/omnis_cli/start.py` și un test startup pentru a publica VERIFYING după atestarea API, înainte de wait_dashboard; aceeași ordine a efectelor, aceleași aserțiuni OCI și cleanup conservator. RED→GREEN pe jurnal la ambele frontiere, review independent punctual, commit separat și rerulare secvențială a gate-urilor pe noul cod. Nu refacem harness DB/owner, nu schimbăm oracle-ul ca să accepte exit 4 drept cleanup PASS.

## Acceptare finală delimitată — cod `b8217cb`

**SC01 și SC02 CLOSED / APPROVED_SCOPED; SL02 acceptat în perimetrul documentat, nu «fără orice omisiune».** SC01 este comis în `0c2a373`, SC02 în `7c22374`, corecția de fază în `b8217cb631e567df496b1e128d14ae202fe0afa9`. Reviewuri distincte: SC01/R1/R2 `deleg_d03af3c7` (14 teste independente), SC02 `deleg_1eb4728a` task 1 (13 teste focalizate +6 controale suplimentare în sursă și wheel), fază `deleg_d041bd94` (3 teste). Părintele a verificat hashurile și adjudecat fără blocante în aceste delte; C1 sticky flags rămâne limită automată neblocantă, verificată static. Nu s-a rescris vreun verdict RED istoric.

Reordonarea fazei a avut RED real în test: subprocess observa VERIFYING, în loc de SERVICES; apoi GREEN **31 startup / 76 CLI**, Ruff/format/mypy. Reviewul aprobă numai ordinea markerului; pollingul poate încă rata fereastra și trebuie să eșueze onest. Oracle-ul OCI și predicatele conservative sunt nemodificate.

### Gate-uri finale, secvențiale

PATH pin-uit: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/node-v24.21.0-linux-x64/bin`, apoi `.../dependency-probe/tools`, `/usr/bin:/bin`. UV exact: `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`.

| Comandă / proces | Rezultat real | Frontieră |
|---|---|---|
| `make check UV=<calea exactă de mai sus>` / `proc_b759e3662b3d` | **exit 0** | 62 docs, 35 development, anti-slop, 218 API, 17 migrări/wheel API, 6 web tooling +20 web unit +7 E2E, 76 CLI sursă +76 wheel extern +1 live CLI/DB, 37 release/observer; locks/audits/Ruff/format/mypy/TS/contracts/build PASS |
| `make check-installed-start UV=<aceeași cale>` / `proc_7c363bef2aa5` | **exit 0**, după primul proces | Wheel nou, 76 teste instalate, 37 release/observer, apoi 1 probă OCI reală a console scriptului; fără `run_probe` în locul comenzii |
| Console script din ultimul wheel, cwd extern | **exit 2 / REFUSED**, verifier exit 0 | Manifest 30001 bytes, `RELEASE_OR_IMAGE_INVALID`, toate flags false, stderr gol, state/runtime absente; 12 module instalate identice cu sursa finală |

Primul gate a început la `16a39c9` + diff-ul de fază fixat prin hash; aceiași bytes au fost comiși ca `b8217cb` în timpul execuției, **fără editări de fișiere**. Hashurile înainte/după coincid: start.py `bb29bf2141705b1139503504cfbd7375542fe905be1b8cf64b16ffce656797ff`, test_start.py `046998204112727b099af7b6dc36e656ac40f92ac97814e02a6c13a6514c5a18`. Nu pretind checkout comis încă de la lansare; atribuirea este byte-bound. OCI a rulat ulterior pe commitul curat.

Loguri private: `phase-final-make-check.log`, `phase-final-installed-start.log`, `final-sc02-installed.log` în rootul scratch al remedierii. Exit-urile au fost citite din procesele exacte, nu din heartbeat. Readbackul ad-hoc a selectat inițial și două locatoare mock din prerechizitele unitare și a refuzat totalul; selecția a fost corectată la secțiunea invocării OCI reale, cu exact două locatoare, fără schimbarea produsului/oracle-ului. O comandă Git anexată ulterior probei externe a eșuat din cwd scratch (128); verifierul console scriptului terminase cu exit 0. Git a fost recitit din repo, nu tratat ca regresie a CLI-ului.

### Readback resurse/date

- **Gate DB final:** root `/home/kali/.hermes/cache/scratch/db-517bada8ff384c3b`, proiect `omnis-p01-297e0735e0d94ed9978c65e42d0ef3d4`, CID `08978e94d6478b5a5539dd6a14e7ec6d189e5cb0ad420a867e16bbf255f54804`, system ID `7691575294029750302`. Receipt `{schema_version:1,code:0,family_drained:true}`; readback exact al daemonului și absenței CID/inventar/rețea/socket, PG_VERSION 18 păstrat. `final-db-readback.json`.
- **OCI final:** proiect `omnis-local-a6c462b79ddb4a91808b749ed16715b7`, image ID `sha256:9adbee79d9baf571752e30fd6beeea2b7cd3c313be89bb49a00d5810cb7a1636`. Start/reuse/concurență: `s2-7m7ayuos`, instance `972a2e4a-36df-483a-8263-5a9a505963b2`; întrerupere: `s2i-7i54r1v1`, instance `8ff2c551-9048-423d-9eb2-869e14fd7fbb`, `FAILED_CLEANED`/exit 3, retry exit 4 fără efect nou. Ambele receipturi `probe=PASS,cleanup=VERIFIED`. Readback părinte: toate CID-urile/inventarul proiectului, rețeaua, tagul imaginii, IPC și forwarder/listener propriu absente; directoarele PostgreSQL18 păstrate. `final-oci-readback.json`. Nu este backup/restore ori stop operațional.
- **Încercarea OCI veche rămâne UNCERTAIN:** DB `7bc89950…` din `s2i-841796q5` este încă running, atestată prin CID/project/attempt/daemon; API/supervisor acelei încercări sunt absente. Locatorul complet și CID sunt în secțiunea de eșec de mai sus. **RECOVERY_PENDING separat**: nu avem dovadă retrospectivă de drenare a familiei acelui launcher; nu semnalizăm PID-uri/nu oprim DB și nu rescriem jurnalul ca PASS. O recuperare distinctă cere reconciliere/autorizație; datele și diagnosticul rămân private. Această resursă nu este folosită de gate-urile noi și nu este confundată cu cleanupul lor.
- Containerele preexistente ale operatorului nu au fost adoptate/oprite; fără down -v/prune, autostart, daemon/firewall/profile changes, conturi/provider/ținte sau push. Scratchul nu este backup permanent.

### Matrice finală a celor 26 de cerințe

Review de completitudine `deleg_1eb4728a` task 2 a reconciliat 26/26 și a păstrat cele șase PARTIAL și patru DEFERRED. Reviewul separat SC02 este adjudecat ulterior aici. Numărare programatică a părintelui: **16 COVERED, 6 PARTIAL, 4 DEFERRED_BY_SCOPE**, zero IDs lipsă/duplicate. COVERED este scoped; gate-ul final nu extinde automat fiecare negativ de componentă la OCI.

| ID | Clasificare actuală | Dovadă / limită păstrată |
|---|---|---|
| M01 | COVERED | Wheel nou/cwd extern/omnis.serve și OCI final |
| M02 | COVERED | SC02 decoder și console script; validări stricte păstrate |
| M03 | PARTIAL | Atestări/preflight; nu toate incompatibilitățile probate OCI |
| M04 | COVERED | No implicit pull/build/install; argv/env/cwd fixe, capcane instalate |
| M05 | COVERED | XDG/căi/UID/mode private; nu toate FS/distribuțiile |
| M06 | COVERED | Lock/nonce/intent, concurență reală; cross-state componentă |
| M07 | COVERED | Reuse fără restart/migrare/OPEN nou; nu restart operațional |
| M08 | COVERED | Port listener/bound-only/bind race; nu toate cursele OCI |
| M09 | PARTIAL | PG18 pozitiv; lipsă proba installed DB-readiness failure first-start completă |
| M10 | COVERED | Migrare/cluster/lock/empty-only, 17 teste; nu catalog exhaustiv |
| M11 | COVERED | API + supervisor inert, fără owner WIP/runtime promoted |
| M12 | COVERED | Detached și citire după launcher exit; nu reboot/autostart |
| M13 | COVERED | HTTP/assets/control/identitate comună; IPC substituit în unele negative |
| M14 | COVERED | Deadline total/byte caps/no redirect/proxy; nu peer OCI ostil peste tot |
| M15 | COVERED | Status read-only și fără lease refresh; nu zero atime/syscall |
| M16 | COVERED | READY atomic verificat, flags false; nu fault la fiecare fsync |
| M17 | COVERED | Bootstrap inert/canale sintetice fără secrete; nu tracing exhaustiv |
| M18 | PARTIAL | Timeout/flood/EOF/reap componente; nu toate etapele instalate |
| M19 | COVERED | SC01/R1/R2 producător→cleanup/zero DB effects; nu delayed Docker ACK sau familie exhaustivă |
| M20 | PARTIAL | Cleanup final și date păstrate; nu toate faulturile; vechea DB incertă păstrată separat |
| M21 | PARTIAL | SIGTERM VERIFYING real + sticky intent; nu crash în fiecare etapă |
| M22 | PARTIAL | Port CLI/bundle, nu config.toml XDG/toate bugetele țintă |
| D01 | DEFERRED_BY_SCOPE | SL03 pair TTY/open/browser implicit |
| D02 | DEFERRED_BY_SCOPE | SL04 stop/recovery operațional și G00 complet |
| D03 | DEFERRED_BY_SCOPE | Hermes runtime/assessment/target effects ulterioare |
| D04 | DEFERRED_BY_SCOPE | Vault/catalog/backup/update/restore/doctor și CI remote ulterioare |

**Concordanța cu planul până aici:** fundațiile P0.1–P0.3 și SL01 sunt păstrate; SL02 are acceptare delimitată și limitele de mai sus, nu implementarea întregii arhitecturi §4. Auditul independent a verificat cod/test/evidence și inventarul global; nu a găsit alt defect confirmat în scope. Nu putem spune «toate lucrurile fără omisiuni»: cele șase PARTIAL sunt explicite, iar G00 rămâne deschis. Următoarea subfelie nouă: **SL03**, apoi SL04; B02/P1-data după G00. Restul SL05–SL36 și E1–E4 nu sunt implementate; B21m opțional/ulterior, metodologia execution-unscheduled nu este catalog executabil.

### Verificarea documentării finale

Rendererul a regenerat cititoarele plan/readiness, apoi `python scripts/render_docs.py --check` și `python -m unittest discover -s tests/documentation -v` au trecut: **62 teste, exit 0**. `python tests/documentation/browser_check.py --include-documents --output <scratch>/omnis-sc-remediation/final-docs-browser.json`: **116 checks PASS**, zero erori JavaScript sau cereri externe. Plan §19.2 și statusul readiness au fost inspectate vizual la 1440×1000 (`final-plan.png`, `final-readiness.png`): paragrafele inspectate și linkurile sunt lizibile, fără suprapuneri; nu este aprobare estetică sau runtime. Diff-ul de produs după `b8217cb` este gol; updateurile ulterioare sunt skill/documentare. HTML-ul original păstrează hashul baseline și rămâne untracked/nestaged; AGENTS și componentele protejate nu sunt schimbate.

Rollback: inspectare dependențe și `git revert <commit>` pentru fiecare schimbare coerentă, rebuild și revalidare. Git nu inversează efecte Docker/DB; acestea cer reatestarea ownershipului exact și păstrarea datelor. Fără privilegii/modificări daemon/firewall/toolchain global. Logurile sunt private în `/home/kali/.hermes/cache/scratch/omnis-sc-remediation/`; concluziile sanitizate și limitele sunt persistate aici din rezultatele reale.
