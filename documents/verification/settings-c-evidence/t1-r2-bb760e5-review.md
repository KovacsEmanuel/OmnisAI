# R2 — focused independent re-review bb760e5

## Verdict

**APPROVED_SOURCE_SCOPED pentru remediile R2; R2-4044-F01 și R2-4044-F02 CLOSED_SCOPED.** Nu am găsit un blocker nou în delta și callerii afectați. Acest verdict se compune cu aprobarea R2 la4044fa9 numai pe scope-ul neschimbat. Nu aprob integrarea, rolloutul operatorului, QA instalată ori închiderea T1.

**R2 admite următoarea QA bounded, fără a cere ca aceasta să fi trecut deja:** cei doi selectori existenți de upgrade populat și rollback pre-OPEN. Lansarea rămâne decizia părintelui după verdictul complementar R1 pe același FREEZE și prerechizitele normale. În acest review nu au fost executate efecte OCI/PG/operator.

## Identitate și scope

- Candidat `/home/kali/.hermes/cache/scratch/t1-upgrade-20261029`, HEAD `bb760e5b9bf9256f1ca31036d8a395590f2c0507`, tree `724d5cb1736cc0def5e0d3eb25eaef18b1d848ec`; continuare față de4044fa9.
- FREEZE `/home/kali/.hermes/cache/scratch/t1-upgrade-complete-freeze-bb760e5-final.json`, SHA256 `7f560b785f037e0fcee24a0368eab599e7fdca41669e23ba3121e6dcb163a625`.
- Verificat independent: **33/33 paths SHA/blob,22/22 artefacte,10/10 payloaduri bundle,29/29 module CLI wheel byte-identice cu sursa**. Parserii old0016/new0017 și preflightul inputurilor reale trec fără daemon.
- Citite mandatul MAIN `documents/verification/settings-finalization-prompt.md`, CURRENT/status afectat, arhitectură§5.5/plan§8, CONTRIBUTING/team-slice, originalul R2 și originalul R1 relevant, skills review/status/release/Ponytail.
- Focus: fence sub data lifecycle lock în public cold backup/restore, Start/Stop/verified; admiterea internă upgrade→backup/restore; păstrarea selecției DEVELOPMENT și următorul Start. Delta oracle/history a fost citită pentru admiterea scenariului, dar adjudecarea R1-02/R1-03 rămâne R1/părintelui.
- `git diff --quiet 4044fa9 HEAD -- api cli/src/omnis_cli/upgrade.py cli/src/omnis_cli/start_runtime.py cli/src/omnis_cli/compose.py` **exit0**. Aprobările anterioare pentru migrare/bariera DB, grant/completion, intent-before-effect, rollback finit, UNKNOWN/no-resend și limitele bundle se păstrează la scope-ul lor; nu un audit nou al întregului produs.

## Dispoziția findingurilor

### R2-4044-F01 — CLOSED_SCOPED

**Remediu:** `cli/src/omnis_cli/backup.py:599–608` verifică din nou `refuse_upgrade` după dobândirea lockului data și înaintea intrării în backup/restore. Aceeași frontieră este acum în `start.py:1212–1216`, `stop.py:657–659`, `verified.py:39–42`.

**Repro independent adaptat:** pe perechea veche0.1.0/schema0016, B este admis; U ia lockul data real, persistă `IMAGE_PENDING` și îl eliberează; B ia apoi lockul real. Pentru **ambele** comenzi backup/restore rezultă **exit4 / UPGRADE_RECOVERY_REQUIRED**, înainte chiar de intrarea în funcția internă backup/restore, cu destinația absentă. Ordinea observată exactă: `B-admit → U-intent → U-release → B-lock`. Nici helperul/effect path nu este admis. Testul candidat pentru Start/Stop/verified trece cu aceeași intercalare legală; constructorul anterior lockului nu mai acordă autoritate perpetuă.

**Control pozitiv și fără bypass:** cu intentul propriu `BACKUP_PENDING` păstrat și lockurile data→root ținute, funcțiile interne native `backup`/`restore` reușesc în fixture SOURCE; numai cold identity/arhivarea OCI sunt doubles. Snapshotul și markerul restore sunt publicate în scratch, apoi șterse de fixture. Fence-ul public rămâne activ. `upgrade.py:335–339` refolosește direct aceste funcții sub lock, nu callerul public; verificarea nouă nu îi interzice propriul backup și nu introduce flag de bypass extern.

**Siguranță afectată:** testul `_View` păstrează0016 și refuză schema greșită; testele restart/reconcile-before-OPEN, lost-ACK/no-resend și rollback OPEN/unknown rămân GREEN. Nu am observat regresie de siguranță în aceste frontiere SOURCE.

### R2-4044-F02 — CLOSED_SCOPED

**Remediu:** `cli/src/omnis_cli/start.py:1144–1150` nu mai substituie configurația cu `development_workspace=None` doar pentru upgrade. Se păstrează configurația reală; selecția se validează prin traseul existent `:1263–1270`, se persistă în noul journal `:1326–1327` și se aplică runtimeului la `:1365`. Nu se scrie implicit RELEASE și nu se refuză o selecție DEVELOPMENT validă doar pentru existența ei.

**Probă:** `test_upgrade_preserves_development_config_and_next_start_reuses_same_workspace` trece pe callerul real Start cu persistență reală și frontiere OCI/PG doubled: upgradeul întoarce DEVELOPMENT, journalul reține workspaceul, configurația rămâne byte-exact; după intent COMPLETE, următorul Start reutilizează aceeași selecție și nu repetă efectele. Au trecut și tranzițiile explicite DEVELOPMENT↔RELEASE după STOPPED, plus reconcile nou înainte de OPEN și lost-ACK/no-resend.

Vechiul reproducer construia manual un READY RELEASE plus config DEVELOPMENT; acel conflict rămâne legitim pentru acea combinație, dar **nu mai este forma produsă de upgradeul remediat**. Închiderea se bazează pe producer→journal→următorul Start, nu pe eliminarea validatorului conflictului.

**QA pozitivă existentă:** `cli/integration/installed_stop.py:702–742` copiază sursa candidat și webul frozen în workspace privat numai după Stop-ul vechi0016; setează config DEVELOPMENT, verifică upgradeul/development_workspace/config neschimbată și următorul `start --no-open --json` reused. Acesta este scenariul instalat de executat, nu o probă deja trecută. Pentru operator rămâne obligatoriu: Stop verificat înaintea integrării Python0017 montat; fără hotpatch API0016 sau Start vechi pe sursele noi.

## Execuții reale și limite

1. `/home/kali/.hermes/cache/scratch/t1-cli-r1r2-bb760e5-venv/bin/python -I -B /home/kali/.hermes/cache/scratch/t1-r2-bb760e5-rereview.py` — **exit0**, **9 teste PASS /0.562s**, plus controalele independente cold queued și backup/restore intern descrise mai sus. Importuri explicit din sursa candidat, nu revendicare de QA instalată. Audit hook respinge subprocess/socket/network; rezervarea de socket a fixtureului este inertă. Fără instalări sau builduri.
2. Interpreterul privat real, `-I -B`, importând `cli/integration`: `upgrade_preflight` cu cele patru inputuri FREEZE — **PASS_NO_EFFECTS/exit0**; originea modulului instalat verificată. `OMNIS_T1_UPGRADE_PROBE` scos explicit: **2 selectori colectați /2SKIP /0 execuții instalate**, nu runtime PASS.
3. Snapshot final: HEAD/tree/FREEZE identice; main `06040a97e1066e5faf8807c7410a9315d40b1811`, tracked/index curate. În candidat doar cele3 symlinkuri preexistente declarate. `git diff --check` exit0. Cele două untracked protejate din main au fost observate numai prin status, nici citite, nici hash-uite.

## Admiterea etapei următoare

R2 **ADMITTED_BOUNDED_QA** pentru aceiași selectori, pe bundleul și interpreterul din FREEZE, fixture fresh și limitele/cleanupul existente:

- `test_release.ReleaseBundleTest.test_t1_populated0016_upgrade_installed`
- `test_release.ReleaseBundleTest.test_t1_upgrade_known_preopen_failure_restores_installed_snapshot`

Păstrează oracle-ul populat, ID/rezultat/usage/receipt și proiecția0016, completion byte-exact, UUID/origin/project/systemID/PGDATA/seif, refuzurile concurente, readback/Stop și rollback pre-OPEN în root absent/cu carantină. UNKNOWN/migrare/reconcile/OPEN incert rămâne stop-and-preserve, fără retry/rollback automat. Nu cer alt harness, altă suită largă sau QA prealabilă circulară. R1 trebuie să dispună explicit propriile findinguri; acest raport nu le închide prin delegare implicită.

Stare propusă: cod candidat neintegrat; probe SOURCE scoped PASS; review R2 APPROVED_SOURCE_SCOPED; installed upgrade/rollback NOT_RUN; operator neatinș și T1 neînchis. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

**Create numai în scratch:** acest raport și `t1-r2-bb760e5-rereview.py`. Niciun fișier repo/canon/produs/config/skill modificat, niciun commit/integrare.

Omise: Docker/PG/browser/provider/build/operator/canonical și auditul general al codului neschimbat.
Risc: SOURCE nu certifică migrarea și DEVELOPMENT instalate; QA bounded rămâne necesară, iar supervisorul UNKNOWN este blocker separat pentru operator/finalizarea T1.
