# R1 — re-review independent focalizat, bb760e5

## Verdict și admitere

**APPROVED_SOURCE_SCOPED_COMPOSED (R1). R1-01, R1-02 și R1-03: CLOSED_SOURCE_SCOPED.** Niciun blocker R1 nou confirmat în remedii ori în callerii/oracle-ul afectați. Compun concluzia cu aprobarea R1 a scope-ului neschimbat din raportul original4044fa9; nu redeschid Remove/API/migratorul neschimbate și nu înlocuiesc reviewul complementar R2.

**Din partea R1 admit prima QA installed bounded**, pe cei doi selectori existenți, după verdictul complementar R2 pe același FREEZE și preflightul/ownershipul operațional al părintelui:
- `test_release.ReleaseBundleTest.test_t1_populated0016_upgrade_installed`
- `test_release.ReleaseBundleTest.test_t1_upgrade_known_preopen_failure_restores_installed_snapshot`

Lipsa unei QA installed deja trecute NU este finding și NU condiționează circular această admitere SOURCE. QA trebuie acum să stabilească rezultatul real upgrade/rollback/PG și cleanupul, nu să fie înlocuită cu alte probe SOURCE. Verdictul nu autorizează efecte pe operator, integrare, provider sau închidere T1.

## Identitate exactă

- Candidat: `/home/kali/.hermes/cache/scratch/t1-upgrade-20261029`.
- HEAD `bb760e5b9bf9256f1ca31036d8a395590f2c0507`; tree `724d5cb1736cc0def5e0d3eb25eaef18b1d848ec`.
- Bază de compoziție `4044fa952cadae8d491f215d62551b11e488065f`; baza inițială `ed611aa40c90f62f4f511cc1951a68970e2ba51b`.
- FREEZE `/home/kali/.hermes/cache/scratch/t1-upgrade-complete-freeze-bb760e5-final.json`, SHA256 `7f560b785f037e0fcee24a0368eab599e7fdca41669e23ba3121e6dcb163a625`.
- Verificate direct: toate cele33 path bindings blob/SHA, exact11 remedy paths față de4044fa9,22 artefacte SHA, ambele diff SHA și10 payloaduri ale bundleului. Setul de fișiere bundle este exact cele10 payloaduri plus `release.json`.
- Bundle `/home/kali/.hermes/cache/scratch/t1-upgrade-bundle-r1r2-bb760e5`; manifest SHA `f09766be6239f6eed62c0e22aed0b5acd6ee2a3658f239e6e78636ff99260262`.
- Interpreter `/home/kali/.hermes/cache/scratch/t1-cli-r1r2-bb760e5-venv/bin/python`; toate29 module CLI instalate sunt byte-identice cu SOURCE frozen. Manifestele noi/vechi sunt parsabile:0.1.1/0017 și0.1.0/0016.

## Dispoziția constatărilor originale

### R1-01 — HIGH inițial — CLOSED_SOURCE_SCOPED

`cli/src/omnis_cli/stop_owner.py:60–67` păstrează acum `runtime.schema` în `_View`; `_load_runtime:125–127` o obține din manifestul releaseului efectiv. `_static:174–177` continuă să utilizeze `_bound_instance`, fără relaxarea validatorului.

Reexecutat reproducerul original pe wheelul privat final, cu rezervarea de socket înlocuită inert: runtime0016 admis → view0016 admis; aceeași instanță cu `view.schema='0017_model_removal'` → exact `RECOVERY_REQUIRED`, code4. Testul permanent `cli/tests/test_upgrade.py:17–37` trece. Defectul original, pierderea schemei admise prin view, nu mai este prezent.

### R1-02 — HIGH inițial, oracle — CLOSED_SOURCE_SCOPED

`cli/integration/installed_stop.py:29–35` exclude **numai** `removed_registry_revision` din JSONB al `provider_model_entry`, atât pentru valoare cât și pentru ordonare. Celelalte tabele păstrează întreaga proiecție; numele tabelului este validat. Același helper este folosit înainte (`:469–472`), după rollback (`:686–693`) și după upgrade (`:766–773`). Noul câmp este verificat separat prin `count WHERE ... IS NOT NULL == 0` (`:759–765`).

DDL-ul0017 adaugă tocmai acel câmp nullable; astfel comparația nu mai respinge schimbarea de formă intenționată și nu ascunde modificarea unei coloane0016. Testul permanent `cli/integration/test_release.py:27–36` trece. Controlul inert suplimentar confirmă egalitatea proiecțiilor old/new-null și inegalitatea pentru mutația fiecărui câmp vechi; acesta este un model SOURCE, **nu execuție SQL/PostgreSQL**. Query/DDL citite direct; comparația efectivă PG este sarcina primei QA admise.

### R1-03 — MEDIUM inițial, istoric gol — CLOSED_SOURCE_SCOPED

`cli/integration/upgrade_history.py:31–188` refolosește DTO/store-ul și patternul arhivei tipate existente din `api/tests/test_provider_key_api.py:718–882`, fără sender/provider. Tranzacția `main:191–197` publică arhiva terminală ca unitate; nu lasă intenționat un PENDING vizibil între inserare și FINISHED.

`installed_stop.py:393–443` introduce istoric nenul înainte de snapshot și verifică operationID/commandID, FINISHED, dispatchID, receipt și outcome `UNKNOWN`, usage `KNOWN`, tokens9/7, cost `0.000016`. `:460–468` cere nonempty pentru toate cele6 tabele istorice. `:682–693` compară exact istoricul și censusul după rollback; `:755–773` face aceeași comparație după upgrade. Command payloads și evenimentele sunt acoperite de censusul integral; ele nu mai sunt tabele goale care ar trece vacuu.

Reexecutat independent helperul final cu **DTO/store din wheelul API vechi0016 efectiv** (`.../t1-upgrade-old-bundle-0016/api/omnis_api-0.1.0-py3-none-any.whl/.../model_test_store.py`) și un RecordingDB explicit în memorie. Rezultat exit0:18 scrieri capturate,9 records; RESERVED→SENT→SETTLED/sequence1–3; operation/command/dispatch IDs legate; receipt SETTLED egal cu outcome_ref; refs/digests și DTO JSON valide; FINISHED/UNKNOWN/SYNTHETIC_MIGRATION_INPUT/KNOWN9/7. Nu este PG, migrare sau apel live. Nu am presupus compatibilitatea fixture-ului doar din API nou.

Prima execuție a controlului propriu a eșuat exclusiv fiindcă am revalidat JSON-ul outcome prin `model_validate` Python în loc de `model_validate_json` (datetime strict). Am corectat numai comanda inertă de review, fără edit produs; reexecuția prin decoderul JSON real a trecut. Nu atribui acest eșec candidatului și nu îl ascund ca PASS inițial.

## Compoziție și affected consumer

Citite mandatul din main `documents/verification/settings-finalization-prompt.md`, arhitectura main§5.5, plan§8, CURRENT/SL12/SL33, regulile CONTRIBUTING/team-slice și rapoartele originale R1/R2. Remediile sunt commituri separate93d20e3/d8c5e5b/6079b3e/c17468a/bb760e5. Am comparat toate cele11 căi modificate și intersecțiile cu callerii aprobați la4044fa9.

R2 deține închiderea fence-urilor și a configurației DEVELOPMENT. În intersecția R1, consumatorul pozitiv `installed_stop.py:704–739` pregătește sursele numai după Stop0016, validează workspace-ul și cere DEVELOPMENT, aceeași configurație și Start ulterior reused fără rescrierea jurnalului. Controlul SOURCE al acestui caller a trecut; nu declar montarea/Start instalat probate aici. Cazul de eșec păstrează oracle-ul rollback0016, completionul byte-exact și verificarea istoriei restaurate. Nu am găsit alt mismatch determinist în oracle-ul afectat care să interzică prima QA.

## Execuții independente R1 și limite

1. Git status/diff/log/HEAD/tree și verificările exacte de identitate de mai sus: exit0. Nicio schimbare tracked/index în candidat sau main.
2. Interpreter privat `-I -B`, `XDG_CONFIG_HOME=/home/kali/.hermes/cache/scratch/t1-empty-config`, sys.path adaugă numai testele din candidat. Suite: `test_upgrade` (10), cele3 cazuri upgrade din `test_restart_wiring` (reconcile, lost-ACK, DEVELOPMENT+next Start), cele2 controale SOURCE/preflight din `test_release`: **15PASS,0.533s,exit0,0skip**. Rezervarea socketului fixture-ului a fost înlocuită inert; frontierele OCI/PG rămân doubles declarate.
3. Reproducerul original R1-01 cu reason/code exacte, modelul proiecției R1-02 și `upgrade_preflight` pe cele4 inputuri reale frozen cu `subprocess.run` interzis: exit0.
4. Helperul final de istoric executat pe wheelul vechi real cu RecordingDB, validări refs/digest/DTO/IDs/events/usage: exit0, după corecția controlului de review menționată mai sus.

Cele98 teste/private-wheel și40API-PG din handoff nu sunt execuții R1; nu le promovez la QA curentă. SOURCE approval compus privește exact cele33 căi din FREEZE, la scope-ul original plus remedii, nu un audit nou al produsului. Următoarea dovadă utilă este prima execuție fresh a celor2 selectori installed deja existenți, nu încă o matrice/harness.

## Predare și protecții

Creat numai acest raport original în scratch. Nicio modificare repo/config/canon, niciun commit, build, Docker, DB, browser, provider, serviciu sau efect operator. Fișierele protejate au fost văzute numai ca nume în git status, nici citite, nici hash-uite. Cele3 symlinkuri untracked preexistente din candidat sunt păstrate. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Neexecutate: QA installed/PG/upgrade/rollback reale, canonical, operator și reviewul complet al domeniului R2; Remove/API/migrator neschimbate nu au fost reaudit.
Risc rămas: SOURCE și RecordingDB nu probează efectele OCI/PG ori restaurarea reală; QA independentă bounded este următoarea poartă, iar integrarea/rollout/T1 rămân responsabilitatea părintelui.
