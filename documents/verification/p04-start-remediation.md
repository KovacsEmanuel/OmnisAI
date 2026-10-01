# SL02 — remedierea SC01/SC02 și acceptarea delimitată

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

Rollback: inspectare dependențe și `git revert <commit>` pentru fiecare schimbare coerentă, rebuild și revalidare. Git nu inversează efecte Docker/DB; acestea cer reatestarea ownershipului exact și păstrarea datelor. Fără privilegii/modificări daemon/firewall/toolchain global. Logurile sunt private în `/home/kali/.hermes/cache/scratch/omnis-sc-remediation/`; concluziile sanitizate vor fi persistate aici după rezultate reale.
