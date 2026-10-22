# Reviewer 1 — APPROVED_SCOPED, numai prerechizitul Settings API

## Identitate și limită

Re-review focalizat pe delta `686d342a1e5887e5b40ae97bc122f162a2faaa0d` → `3f7b4d3944869246bc70ab0d38495f4f1ea7146b`, tree `00e68c602c6fa384394aa4f4252bbd71645b4028`, worktree `impl/api-key-runtime-t1` curat înainte/după probe. Manifest `settings-repair-freeze.json`, SHA256 `023545c659f87a4400ed2fb3c304c7c53b857fca6f3fbc9093e5e2932a1f42dc`; verificate programatic toate cele 7 căi delta și 44 căi candidat: SHA256/size/blob HEAD, count și unicitate, HEAD/tree. Checkoutul comun e7b8cb9 a rămas nemodificat; HTML-ul untracked protejat nu a fost citit.

Scope: numai închiderea R1-F01/F02/F03 și regresii concrete în remediile/callerii afectați. Aprobarea anterioară a scope-ului neschimbat rămâne la limita ei. R2-F01 cross-process drain aparține companionului; bytes comuni citiți numai pentru interacțiunea cu bootstrapul/LOCKED, fără verdict R2 independent aici.

## Dispoziții explicite

- **R1-F01 — CLOSED_SCOPED.** `api/src/omnis/modules/settings/provider_key_service.py:225–248`: istoricul se citește în admission înaintea bootstrapului; numai `not heads` îl permite. Query-ul :93–108 nu elimină headurile revoked. Cu istoric existent și ambele fișiere lipsă, `command_digest` → `_load` refuză ca `VaultLocked` înainte de put/publicare, fără regenerare. Reproducer SOURCE propriu pe callerul real `owner.handle`, cu DB/istoric double și publicarea oprită explicit, confirmă controlul pozitiv istoric gol și refuzul cu head enabled sau revoked; niciun fișier regenerat, metadata LOCKED. Criteriu: arhitectură §8.1, bootstrap numai la prima configurare. Testul PG concret `test_damaged_vault_stays_locked_with_committed_local_revoke` :341–391 verifică Save pozitiv, pierdere ambele fișiere, bytes neschimbați, refuz rotate, readback, revoke/replay/census și refuz după revoke. RED original citit în `db-151d845555e44d9b/gate.log`: DID NOT RAISE VaultLocked; finalul real PG este verde, citit, nu rerulat.
- **R1-F02 — CLOSED_SCOPED.** `api/src/omnis/modules/settings/provider_vault.py:39–49`: tipurile string exacte sunt verificate înainte de UUID; loaderul :175–196 convertește ValueError în VaultLocked. `owner.view` :133–159 produce LOCKED și credential_present=false, fără AttributeError; revoke :265–318 poate ajunge la receipt/commit. Testele SOURCE proprii și callerul real view confirmă numeric/listă în ambele câmpuri UUID. Cele patru variante PG concrete verifică revocarea locală, readback după tranzacție, replay și census două revizii/două receipts. RED original `logs/r1f02-red.log` arată excepția int/list.replace; finalul PG citit acoperă aceste variante. Criteriu: asocieri neîncrezătoare invalide → LOCKED, metadata/revoke disponibile (§8.1).
- **R1-F03 — CLOSED_SCOPED.** `cli/integration/control_topology.py:918–923` compară strict cu EXPECTED_SCHEMA; `cli/integration/installed_start.py:615–627` citește/validează schema originală, o restaurează în finally și verifică readback. Testele SOURCE execută blocurile AST reale, verifică headul migrărilor, admit 0014/refuză 0013 și valoarea incompatibilă și verifică restaurarea inclusiv la excepție. Cele patru teste focalizate au trecut în execuția proprie. RED original `logs/r1f03-red.log` păstrează cele două reproduceri 0013. Criteriu: coerența callerilor afectați de bumpul 0014; nu pretind installed QA din AST.

**Niciun blocker nou concret identificat în delta și callerii afectați.** Nu există reproducer original R1 rămas deschis în limita verificată. **APPROVED_SCOPED — exclusiv prerechizitul Settings API și cele trei remedii R1 pe snapshotul exact**, nu acceptare/integrate a candidatului, verdict pentru R2 ori T1 complet.

## Dovezi executate/citite

Director propriu: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/reviewer1-focused-lyii5vs6`.

- `source.log`: `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml api/tests/test_provider_vault.py api/tests/test_provider_key_settings.py -k 'not save_rotate_revoke and not damaged_vault and not cancelled_save and not successor_drain_accounts' -p no:cacheprovider --basetemp <director-propriu>/pytest -q` → **22 PASS, 10 deselected, 0.52s, exit0**. Excluse explicit 8 cazuri PG și 2 cazuri R2 spawn, nu mascate ca PASS.
- `schema.log`: `cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -p test_schema_compatibility.py -v` → **4 PASS, 0.028s, exit0**. Nu suită CLI largă.
- `caller-reproducer.log`: caller real handle/view, filesystem real privat și DB double/no DB IO → **exit0**; istoric gol permite bootstrap/put până la sentinelul de publicare, head enabled/revoked împiedică regenerarea, UUID numeric/listă proiectează LOCKED.
- Citite direct, fără relansare: `db-26a1ac67fab047ac/gate.log` (comanda completă celor trei fișiere API, **33 PASS/24.33s**), `logs/settings-repair-final-pg.log` (runner target exit0/readback cleanup), testele concrete :322–394 și logurile RED de mai sus. Aceasta este dovada PG a developerului pe final bytes, nu execuție independentă nouă sau installed/restart proof.

Fără cod/teste/shared docs modificate, commit, DB/instalare/browser/provider/cont/profil nou. Au fost create numai acest raport și dovezile SOURCE în scratchul propriu. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Integrarea/adjudecarea finală și companionul R2 aparțin părintelui.

Neexecutat: PG nou, R2 cross-process rerun, CLI larg, installed/browser/provider sau întreg T1. Risc rămas: aprobarea este SOURCE/focused, cu dovadă PG existentă citită; nu certifică distribuția/restartul și nu închide porți globale.
