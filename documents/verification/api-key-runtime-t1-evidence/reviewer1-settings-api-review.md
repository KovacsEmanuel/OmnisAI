# Reviewer 1 — CHANGES_REQUESTED, numai prerechizitul Settings API

Snapshot exact: base `b35c4de9aa968a48c7565e5685eefd0aa6b09f70`; HEAD `686d342a1e5887e5b40ae97bc122f162a2faaa0d`; tree `b2aa3f828740fc29be903e60cf6b8308971de037`; branch `impl/api-key-runtime-t1`.
Manifest: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/logs/candidate-freeze.json`, SHA256 `806fb3361bf99a2e2af1303cdbe8db44e8b9e01774c1b0b5bf296c2c68b25b0b`. Cele 42 de căi/SHA256, identitatea HEAD/tree și migrațiile istorice neschimbate au fost verificate programatic; worktree curat la final. Review read-only, fără commit sau modificare de produs.

## R1-F01

- **severity:** HIGH / BLOCANT.
- **file:line:** `api/src/omnis/modules/settings/provider_key_service.py:215–220`; `api/src/omnis/modules/settings/provider_vault.py:211–238`.
- **reproducer:** Instanță configurată, cu connection revision 1 păstrată în DB; ambele fișiere `vault.json` și `master.key` lipsesc, de exemplu după restaurarea/montarea unor directoare goale. GET proiectează LOCKED din referința existentă, dar Save/rotate apelează necondiționat `bootstrap()` înainte să citească headurile. `_bootstrap()` vede numai absența fișierelor și creează alt master key și un seif gol. Reproducer SOURCE pe callerul real `owner.handle`, cu headul existent furnizat prin double și publicarea DB oprită explicit, a observat `existing_head_revision=1; missing_both_files_causes_new_master_before_DB_publish=True`. Reproducerul direct confirmă `both_missing_bootstrap_created_different_key=True`, vechea referință absentă; controlul cu numai cheia lipsă refuză corect `VAULT_LOCKED`. Nu s-a executat DB în această reproducere.
- **violated criterion:** Arhitectură §8.1: bootstrap numai la prima configurare; datele/cheia lipsă ale unei configurații existente rămân LOCKED, fără regenerare implicită și fără pierderea asocierilor istorice. Un nou master pentru aceeași instanță face restaurarea ulterioară a vechiului ciphertext incompatibilă cu cheia nouă.
- **minimal remedy:** Distinge prima configurare folosind istoricul DB înainte de bootstrap. Cu referințe existente și seif lipsă/incoerent, refuză Save/rotate ca LOCKED fără a crea fișiere; păstrează revocarea locală. Extinde testul existent cu ambele fișiere lipsă, nu numai cheia lipsă.

## R1-F02

- **severity:** HIGH / BLOCANT.
- **file:line:** `api/src/omnis/modules/settings/provider_vault.py:168–177` și `:39–47`; caller `api/src/omnis/modules/settings/provider_key_service.py:295`.
- **reproducer:** Într-un seif sintetic valid, schimbă numai `entries[0].ref.secret_id` în numărul JSON `123`. `vault.status` și callerul real `owner.view` ridică `AttributeError: 'int' object has no attribute 'replace'`, nu LOCKED. `UUID(value)` este apelat înaintea verificării tipului; `_load()` nu transformă această excepție în `VaultLocked`. Revocarea inserează revizia în tranzacție, apoi apelează același `view()` înaintea receiptului/commitului; această excepție determină rollback, deci nu poate revoca local configurația deteriorată.
- **violated criterion:** Arhitectură §8.1: ciphertext/ref invalid → LOCKED; metadatele rămân citibile și revocarea locală este posibilă inclusiv când seiful este LOCKED.
- **minimal remedy:** Validează strict tipurile UUID înainte de `UUID(...)`, astfel încât orice asociere invalidă să devină `VaultLocked` în loader. Adaugă cazul numeric/listă în testul de tamper și verifică readback LOCKED plus revoke comis fără cheie/ciphertext utilizabil.

## R1-F03

- **severity:** MEDIUM / BLOCANT pentru coerența bumpului de schemă și a verificărilor afectate.
- **file:line:** `cli/integration/control_topology.py:918–922`; `cli/integration/installed_start.py:623`.
- **reproducer:** Alembic pe snapshotul exact produce `0014_provider_settings`; verificarea instalată încă cere literal `0013_mission_revisions`, deci migrarea corectă ajunge inevitabil la `Installed migration revision mismatch`. În proba installed-start, `finally` de după controlul negativ restaurează tot `0013_mission_revisions`, nu schema curentă, lăsând DB nouă incompatibilă cu API/CLI. Reproducerul SOURCE a extras expresiile din AST și headul real din ScriptDirectory: `actual_alembic_head=0014_provider_settings`, `topology_expected=0013_mission_revisions`, comparație False; restore-ul extras este exact `UPDATE alembic_version SET version_num='0013_mission_revisions'`. Nu s-au lansat aceste probe instalate.
- **violated criterion:** Charter: bumpurile CLI/release/readiness și callerii lor trebuie să fie coerente cu migrarea aditivă 0014; arhitectură §5.5 și comenzile de distribuție din registrul T1. Acesta este un caller existent omis la bump, nu o cerere de implementare a componentelor T1 viitoare.
- **minimal remedy:** Actualizează comparația și restaurarea la schema curentă sau restaurează exact valoarea citită înaintea controlului negativ; păstrează aserțiunile stricte și testează deriva SOURCE fără infrastructură nouă.

**CHANGES_REQUESTED — exclusiv prerechizitul Settings API pe snapshotul de mai sus.**

Probe SOURCE executate: cele 18 teste selectate de vault/DTO au trecut, două teste PG excluse explicit; reproducerii focalizați de mai sus au rulat fără DB/provider. Logul PG existent și fixture-urile concrete au fost citite, nu promovate la restart/installed proof. Cele două FAIL-uri CLI comunicate de părinte sunt preexistente pe BASE și nu sunt findings noi aici; nu le-am rerulat.

Neexecutat: PG nou, instalare/restart de proces, browser sau provider live; nu am evaluat componentele T1 neînghețate. Riscul rămas este explicit în cele trei reproduceri; acest verdict nu închide T1 sau vreo poartă globală.
