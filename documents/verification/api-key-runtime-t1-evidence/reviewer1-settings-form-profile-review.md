# Reviewer1 — Settings/release T1, review independent exact-snapshot

**Verdict: APPROVED_SCOPED — SOURCE/distribuție statică, numai delta lifecycle/release.**

- HEAD: `91bb74849eb1e628a264c3c0df18d652b9fabd6f`.
- Tree: `a39b1485a497c8c158122286110448d88a312cb3`.
- Bază: `c19440a357866c162672be5400e08df4636b585f`.
- FREEZE: `logs/settings-form-freeze.json`, SHA256 `407f64b24d4903d145b8e41f8248e0dd91fbedd707eedcd6c874040dc1f2aa8a`.
- Bundle: `t1-settings-artifacts/bundle-final`, manifest SHA256 `f1c5a58446db9e7d86d9904728e568a33f7f64f270022904f20dbe33de6338fe`.

## Findings concrete

`[]` — niciun finding nou confirmat în acest scope. Nu redeschid R1-F01–03/R2-F01–02 sau codul API/seif/0014 deja aprobat; `git diff --exit-code c19440a..HEAD -- api/src api/tests api/pyproject.toml api/uv.lock` a trecut.

## Cerință → consumer → dovadă/limită

| Cerință | Consumer examinat | Rezultat scoped |
|---|---|---|
| Profil finit, fără native/Hermes/egress | `release._manifest`, builder, `compose.install_control_image`, `ControlRuntime` | Manifest format3 numai `t1-provider-settings`; bundle real cu10payloaduri, fără native/model-test assets. `native=False`, `model_test=False`; numai API/supervisor/DB pe rețeaua internal, fără runtime peer sau auth forwarder. Refuzul profilului greșit/runtime metadata este explicit. |
| Seif + master key separate, numai supervisor | `provider_settings_overlay`, `start.validate_config`, `ControlRuntime.attest` | Numai supervisor primește `/vault` și `/vault-key`, env exact. Config/inspect pozitive; key mount pe API și mount lipsă sunt refuzate. Setul exact de mounturi/env, UID/GID și confinementul existent rămân în attestor. |
| Owner/mode/inode și receipts stricte | `private_identity`, `vault_fields`, `_pgdata_receipt`, `_bound_instance`; Start/Status/Pair/Open/Stop | Format5 cere ambele identități `[dev,ino,uid,gid,0700]`, tipuri int exacte și setul de câmpuri specific fazei. Bindingul instance/project/release/image/daemon este păstrat. Refuzuri SOURCE prin entrypointurile reale pentru inode diferit, bool în identity, câmp native suplimentar și mode0750, înaintea runtime/control/browser. |
| Identitate nouă, fără adopție operator | installer, image producer, `start_instance` | Release existent diferit este refuzat; image project nou; state cu postgres/instance/vault/vault-key fără journal nu este adoptat. Restart cere STOPPED exact și readbackul autorității existente. |
| Boot fără master-key bootstrap/provider IO | Start înainte de primul create; supervisor bootstrap | Proba taie Start după persistarea directoarelor/journalului, înainte de OCI: key/vault goale și fără native paths. Callerul supervisor construiește ownerul existent; constructorul `ProviderVault` doar reține paths/identity, nu bootstrap-ează cheia. Fără executare supervisor/provider aici. |
| Stop/restart conservă seif/master/pending | `stop_instance`, `readback_stopped`, Stop owner `_static`/`_View.attest`, restart | Format5 trece prin aceleași receipt/grant/resource validators, cu mount fingerprint complet. Cleanup IPC nu include seiful/pending. Positive SOURCE STOPPED Stop/Status/Start și restart READY păstrează inode+bytes pentru ciphertext/master/pending; driftul paths este refuzat. Nu este teardown fizic instalat. |

## Execuție independentă

1. Integritate FREEZE: exact17căi, dimensiuni/SHA256/blob egale cu Git și discul. `_manifest(bundle-final)` admis; toate10payloadurile egale cu manifestul. Wheel API105module și CLI23module byte-identice cu sursa. Rezultate: `reviewer1-profile-source.log`, liniile1–108.
2. Suită afectată `test_provider_settings_profile` + `test_restart_wiring`, prin `cli/.venv/bin/python -I -B`, import explicit din acest checkout: **32teste PASS,1.512s,exit0**. Include17installer preexistente importate de noul modul, nu32teste noi. Log: `reviewer1-profile-source-short.log`, SHA256 `e23aef07fd6921b5b2ce13a78b57091f493e4aa791c9aec21becb755755edef2`.
3. Probe suplimentare finite pe callerii reali, fără instalare: `cli/.venv/bin/python -I -B ../logs/reviewer1-profile-entrypoints.py` → **2PASS,0.217s,exit0**. Start READY reuse/Status/Pair/Open pozitive; cele patru mutații sunt refuzate de toate cinci entrypointurile fără constructor runtime/contact/issuer/opener/attest, fără marker și fără journal write. Stop/Status STOPPED + Start explicit sunt exercitate cu format5 și păstrarea celor trei fișiere. OCI/DB/HTTP/TTY/browser sunt doubles explicit enumerați în script. Log final SHA256 `3198992f239f329f8d3db5e9c810cdeb91348f71793f6a1ad09e20bd3654659e`; script SHA256 `1f177a1e1cb0a1fb9d656a747a939b3f388585bfbdc54eb19820a7c0bb082aa8`.
4. Export production real, offline: `/home/kali/.local/share/omnis-toolchains/uv-0.12.19 export --locked --offline --no-config --directory api --no-dev --no-emit-project --no-header --no-annotate --format requirements-txt`; comparație bytes cu requirements din bundle → **exit0**, SHA256 `32e876eb454b08881ad55cca5bd1a602011faaef26f51671022827a99cb3c8f6`, crypto50.0.1 prezent.
5. `git diff --check`, diff API neschimbat și Git status final → **exit0/worktree curat**, HEAD/tree identice.

Încercările nereușite rămân: primul TMPDIR al reviewerului era prea adânc pentru limita AF_UNIX și a provocat `PRIVATE_PATH_INVALID`; aceeași sursă a trecut cu TMPDIR owned scurt. Prima probă suplimentară presupunea greșit exit4 universal pentru mode invalid; callerii existenți Start/Pair/Open returnează3, Status/Stop4. Am corectat numai expected-ul probei după citirea callerilor, nu produsul sau aserțiunile no-effects. Logurile inițiale sunt păstrate: `reviewer1-profile-source.log`, `reviewer1-profile-entrypoints.log`.

## Ownership și limite

Nu am modificat cod/teste/manifeste sau indexul Git. Am creat numai acest raport, scriptul și cele patru loguri `reviewer1-profile-*` sub `logs/`, plus directoare scratch de probe/config. Niciun DB, Docker build, serviciu, instalare, browser sau provider executat; fără secrete/ambient credentials/profil operator/r1/global/push/HTML protejat.

UI/privacy/decoder aparțin Reviewer2. Installed Start→Settings→Save/readback→Stop→restart, browser, backup/restore, provider și canonical rămân NOT_RUN în această revizie de review. Restul T1 SystemOperation/sender nu este implementat sau revendicat în delta și nu constituie finding aici. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Verdictul nu închide poarta T1 și nu aprobă integrarea proprie; adjudecarea și QA reală aparțin părintelui.
