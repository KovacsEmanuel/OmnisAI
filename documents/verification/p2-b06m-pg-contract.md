# B06m — continuare PG contabilă serială

## Mandat și frontieră

Continuare explicită în aceeași sesiune `20261010_185056_95cc16`, bază de reluare `e4bf202dc77e4de8690c948d57866df734eef48e`, worktree/branch b06m neschimbate. Coordonatorul a predat `effects.holder=b06m` cu SID exact și grantul `b06m/fixture-grant.json`, SHA256 `0bb4ce21192e69b558345713cb75499670b1833cf44948ca8ff4410fb8b3c736`. Scope: biblioteca contabilă reală în PostgreSQL și QA independentă source, nu admission/send/turn/model. Sursa contabilă și testele de la `b46391f` nu sunt schimbate; cele două reviewuri anterioare rămân scoped la acei bytes.

B06c este acum FROZEN la `3c1c15a7b95565a6ef51295ab02fb436c5ef5400`, curat; diff-ul `api/`, `integrations/hermes/`, `Makefile` față de snapshotul QA/review `d1b8e01a5509e08ad36d831fd2886f1f22c3224f` este gol. Interface/handoff/drain au fost citite ca dependență autentică. Nu este necesar importul pentru proba contabilă independentă; nu se recertifică B06c și nu se importă WIP. Targetul B06c trebuie păstrat la merge-ul serial ulterior. Consumerul nativ/full SDK și faza2 nu sunt închise de această predare.

## Configurare și verificări înaintea efectelor

Transfer limitat aplicat în `23f835c`: doar targetul `test-model-budget-pg`, guardul Make al flagurilor și opțiunea aferentă din runner. Nicio semantică lifecycle/security a `ops/run_test_db_gate.py` nu este modificată. RED: target inexistent, exit2; după patch: fixture lipsă refuză exit2, `-n/-t/-q/-i` fiecare refuză exit2 cu motivul explicit, help afișează targetul, exit0. Nu se execută canonical/browser.

Toolchain: UV0.12.19 și Node24.21.0/npm11.19.0 în `r3-5gjabhuw/tools`, API venv owned deja existent Python3.13.15. Preflightul a detectat Node/npm ambient nepotrivite; nu au fost folosite la gate. CLI-ul nu este consumer aici: runnerul cere numai interpreterul CLI3.13.15 la preflight; venv nou `parent/cli-venv`, link owned `cli/.venv`, fără instalare/upgrade operator. Nu revendică probă CLI sau installed package.

## Resurse, execuție și cleanup

Registru înainte de orice lansare: `/home/kali/.hermes/run/omnis-p2-critical-20261010/b06m/pg-resources.json`. Root nou `/home/kali/.hermes/cache/scratch/p6m-a95cc16`, subrooturi `parent` și `qa`, fiecare HOME/TMPDIR/log/manifest propriu. Mediul este `env -i`, PATH pinned, fără auth/profile/credenciale/provider discovery. Manifestul îngheață numai inputurile reale ale gate-ului: sursele API, cele două teste/conftest, migrarea/config/lock și Makefile/runner/Compose; exclude originalul protejat și orice secret.

Runnerul original produce random project/root în `DISPOSABLE_INTENT` înainte de Docker create/up și CID în `DISPOSABLE_CREATED` înainte de gate. Un recorder stdout sincron, în scratch owned, persistă acele evenimente în registru înainte să returneze controlul runnerului; nu substituie funcții DB/Docker/cleanup, nu inventează rezultate și nu este verificator de produs. Source hash al recorderului și manifestul consumat se înregistrează înainte de launch. CID-ul nu poate fi cunoscut înainte de alocarea Docker; intenția exactă proiect/root precede create, CID-ul real se leagă imediat după.

Execuție: runnerul existent `--check --target test-model-budget-pg --timeout-seconds 240`, PostgreSQL18.6 pinned, UDS privat/network none, fără port publicat. Testele existente folosesc `migrated_database_url`: bazele per-test nou generate pot fi șterse de conftest; baza baseline proprie runnerului nu se șterge. PGDATA/receipts/logurile sunt păstrate; nu se pretinde că toate bazele temporare de test rămân populate. Restartul probat este reader nou în proces nou, nu reboot fizic PostgreSQL/restore.

Părintele termină și citește cleanupul propriu înainte de fixture QA nouă. QA independentă rulează aceeași bibliotecă/aceiași bytes, fără dubluri SQL/ledger/projection și fără importuri native. Se păstrează fiecare eșec real, cu distingerea defectelor produsului de cele ale driverului; fix minimal/RED-GREEN/re-review numai dacă apare blocker. Lipsurile native nu țin fixture-ul deschis. Readback final exact: CID absent, inventar proiect/networks gol, UDS/lock absente, gate family_drained, PGDATA reținut. Effects.json nu se modifică; predare explicită READY_FOR_NEXT_HOLDER_INTEGRATION după drenare.

## Limite fixe

Metadata contabilă sintetică din teste nu este native-turn/projection-admission/grant. FullSDK/native pre-send/InstanceControl-Stop/Settings rămân NOT_INTEGRATED; P2-live/G02-live/G04a NOT_RUN fără acord separat cont/provider/model/date/buget. Nu main, profil r1, global config, alt model, push, sesiune sau cron nou.
