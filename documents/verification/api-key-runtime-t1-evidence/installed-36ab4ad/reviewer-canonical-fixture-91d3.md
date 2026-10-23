# Review independent — APPROVED_TEST_SOURCE_SCOPED

## Verdict și limită

**APPROVED_TEST_SOURCE_SCOPED. Fără findings concrete în delta cerută.** Admit QA PG îngustă, serială, prin runnerul existent, după preflightul părintelui și pe fixtures fresh owned: întâi `--target test-provider-settings-pg`, apoi `--target test-b06b-pure-probe-pg`. Nu este canonical PASS, acceptare runtime, închidere T1 sau aprobare de lucru nativ nou.

Schimbarea corectează așteptarea schemei DB live la head0015 și face accesibile cele două cazuri SQL restore/restart în targetul Settings existent. Nu schimbă produsul, istoricul fixture-urilor sau politica de atestare.

## Snapshot verificat

- Checkout: `/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/canonical-fixture-review`, detached și curat la început și la ultimul readback.
- Bază: `fd1459b2edd0fa4f6cb895f964ff0d027f5b9dce`.
- HEAD: `91d3e4ead63430eb59b4e028a00197a84526e786`.
- Tree: `0cb2e229c56e16c31f5e0133fd0c03ae9b62e335`.
- Exact două substituții de linie în două fișiere; restul arborelui este neschimbat față de bază.
- `Makefile`: blob `923dae1ff111c74778cc3903bd7ad929f1792801`.
- `api/tests/fixtures/b06a_durable/releases.py`: blob `5dc3d7fd493622c3c4273fda7a25301330c36575`.
- SHA256-urile ambelor fișiere coincid cu `canonical-fixture-integrated-freeze.json`; comparație executată independent.

## Cerință → consumer → risc → decizie

| Cerință și consumer real | Verificare și risc acoperit | Decizie |
|---|---|---|
| Atestare strictă a DB curent migrat: `migrated_database_url` → `install_fixture` → `fixture_connection` | `conftest.py:138–156` migrează la `head`; ScriptDirectory real din `api/alembic.ini` are unicul head `0015_model_test_v2`. La `releases.py:347–349` rămâne egalitate exactă `fetchall() == [("0015_model_test_v2",)]`, nu apartenență, tolerarea mai multor heads sau fallback. Elimină prerequisite-ul fals0014 înaintea consumerului. | Pin corect pentru DB live curent; admisă reproducerea PG îngustă a regresiei. |
| Reactivare SQL restore și restart normal accesibile prin Settings | `Makefile:43` adaugă exclusiv `api/tests/test_cold_restore_pg.py`, păstrând cele trei fișiere precedente, ordinea lor, flags și guardul. Testul existent `test_cold_restore_pg.py:14–64` exercită `restore=False/True`, istoric/ref-uri păstrate și replay idempotent. | Admisă QA reală a ambelor ramuri; collect-only nu le dovedește comportamentul SQL. |

## Calleri și invarianti

- Am căutat definiția și toate apelurile `fixture_connection`/`install_fixture` în testele API. Callerii direcți sunt helperul însuși, `test_candidate_tracer_release_pg.py` și `test_b06b_pure_probe_release_pg.py`; scenariile PG folosesc DB-ul curent migrat. Valoarea schimbată nu reprezintă o revizie istorică stocată într-un artifact/receipt.
- Regresia concretă `test_b06b_pure_probe_release_pg.py:30–73` instalează dependența prin helper, apoi verifică refuzul exact `RELEASE_DEPENDENCY_NOT_SUPPORTED`, zero apeluri PURE și ledger neschimbat. Niciunul dintre acești controli negativi nu este relaxat.
- `releases.py:291–346,351–352` păstrează interdicția override-urilor, project/socket/UUID/DSN bounds, receipt cu chei exacte, CID/system identifier, atestarea prin runner, timeouturile și refuzul SQL. `yield` rămâne după comparația singleton.
- `ops/run_test_db_gate.py` și `conftest.py` sunt byte-identice bazei. Am citit traseul de atestare: ownership UID/moduri/căi, socket privat, identități container/daemon și SQL cluster identity rămân obligatorii. Nicio modificare a runnerului, inclusiv mecanismelor sale existente de ownership/FD, nu intră în această aprobare.
- Guardul de fixture Settings (`Makefile:42`) și refuzul flags Make nesigure (`Makefile:11–17`) sunt identice. Ambele targeturi sunt deja în choices ale runnerului (`ops/run_test_db_gate.py:1035,1049`); targetul pure-probe nu este modificat. Nu este necesar target, wrapper, abstracție sau unit test nou pentru cele două substituții triviale.
- Produsul core/backup/restore și aprobările SOURCE anterioare rămân în scope-ul lor neschimbat; nu le-am reauditat și nu le promovez la dovadă runtime.

## Dovezi și rezultate

Executat independent, read-only, în snapshotul înghețat:

1. `git status --short --branch`, `git rev-parse HEAD HEAD^{tree}`, diff/staged stat, `git diff <base> <head> --`, `git ls-tree HEAD ...`: exit0; snapshot și blobs exacte, checkout curat.
2. Comparație programatică a fișierelor cu baza: fixture-ul este exact o substituție0014→0015; Makefile este exact append-ul unui filename, fără alte bytes schimbate. Ambele asserts PASS; SHA256-urile fișierelor coincid cu freeze.
3. `git diff --check <base> HEAD`: exit0.
4. `/home/kali/OmnisAI/api/.venv/bin/python -I -B -c ...` cu `Config(<snapshot>/api/alembic.ini)` și `ScriptDirectory.from_config(...).get_heads()`: exit0; rezultat real `['0015_model_test_v2']`. Fără conexiune DB.

Citite ca dovezi ale autorului, nu prezentate drept rerulare proprie:

- `canonical-fixture-schema.log:28–35`: verificarea AST a egalității SQL singleton/head și quality scoped, exit0.
- `canonical-fixture-settings.log:443–446`: lint/typecheck scoped după ultima editare, exit0.
- Același log: Settings collect-only38 și pure-probe collect-only37, exit0; ambele `[False]`/`[True]` și regresia originală sunt enumerate. Corecția inițialului numărător37 Settings este explicită la503–505, din același raw, fără rerulare.
- RED-ul real al părintelui, conform contextului delegat și referinței păstrate în schema log: `../cg/db-fb6706d674b84aad/gate.log:205–306`, eșec înaintea consumerului din cauza pinului0014 pe DB0015; 1FAIL/526PASS, apoi întrerupere țintită, canonical exit2. Nu am recitit logul privat și nu schimb acest FAIL în PASS.

## Predare

Nu există blocker SOURCE în cele două linii. Părintele poate admite cele două probe PG înguste pe bytes curenți, cu preflight/deadline/cleanup owned și readback; păstrează failul canonical original. GREEN PG trebuie stabilit prin execuția reală, nu dedus din acest review. Eventuala reluare canonical și acceptarea T1 rămân decizii separate ale părintelui.

Creat exclusiv acest raport, în afara checkoutului; fără editări de produs/teste/config, commit, servicii, Docker, DB, provider, browser sau credențiale. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Neexecutat: PG/OCI/canonical/T1 și runtime instalat; nu am cerut probe sau abstracții noi pentru literal/recipe.
Risc rămas: comportamentul SQL nou și regresia pure-probe sunt încă NOT_RUN pe snapshotul reparat; aprobarea de față admite QA, nu îi anticipează rezultatul.
