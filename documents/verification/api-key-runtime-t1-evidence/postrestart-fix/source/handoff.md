# LIVE-POST-RESTART-01 — candidat frozen, necomis / NOT_ACCEPTED

## Rezultat

Cauză SOURCE reprodusă: startup_generation era populat doar pentru raw_runtime, iar skip-ul heartbeatului acoperea doar task_owner legacy. La API-key, două heartbeat-uri pre-OPEN redrenau shutdownul istoric și închideau ownerul proaspăt. READY/OPEN nu resetează closing. Cauza internă din execuția live originală rămâne neobservată; nu am relansat instalarea/operatorul.

Remediu: capturează generation din owned_status deja citit pentru API-key și include model_owner în protecția existentă de startup. Nicio resetare nouă, nicio schimbare la InstanceService/fence/lease/drain/reconcile/SENT. Un shutdown nou schimbă generation și păstrează drain-ul obligatoriu.

Doar două fișiere în ../src:
- api/src/omnis/supervisor/__main__.py — blob 44dc21f65947b40dad28a2cf5eb5cacfa27510c3
- api/tests/test_runtime_supervisor.py — blob aba6ab88e87f4b0973ee18fce2ee7f1535c25648

Base 083e6f6407ecf0adf0de6545b013851dac5098dc; branch impl/t1-postrestart-admission-20261026. Identitatea completă este în freeze.json; patch exact candidate.patch, SHA256 829026023583004ea28889cff4fe5b976b7d2ebb51ad0ed31a651597db6a9f74. 303 inputuri sursă/manifest hash-uite înaintea execuțiilor; zero drift după testele finale. Părintele comite candidatul, apoi organizează reviewurile complementare. Nu am stage-uit/comis/push-uit.

## Probe

| Cerință | Consumer/probă | Rezultat |
|---|---|---|
| Prima mutare după restart + două ticks pre-OPEN | supervisor.run → callback ModelTest real → InstanceService.admission → selection reală absentă | RED 3 FAIL/3 PASS; după fix REVISION_CONFLICT, nu CONTROL_UNAVAILABLE |
| Fără shutdown istoric | Același test/callback | PASS |
| Stop nou după OPEN | shutdown real/new generation → heartbeat quiesce/drain real → task anulat/joined → două ticks cu refuz new work | PASS |
| Settlement eșuat | Task real eșuează → finished setează settlement_failed → refuz repetat → final drain incert fără release | PASS |
| Owner pierdut | Fault explicit LEASE_LOST în guard/heartbeat → refuz, ieșire și owner închis, fără reset/retry | PASS |
| Familia legacy | Regresia existentă intactă: istoric/non-istoric, Stop/startup failure/early close; Settings UDS SOURCE | PASS |
| Calitate | Ruff check, Ruff format --check, mypy full api/src api/tests, conform Makefile | exit0 |

GREEN inițial: 53 PASS / 1.54s. Final după ultima editare: 57 PASS / 3.52s, exit0. git diff --check exit0. Prima execuție quality a refuzat exclusiv formatarea condiției; format reparat manual, rerun final complet exit0. Logul eșecului rămâne quality.log. Fără cicluri harness-only; primul reproducer a arătat defectul exact.

## Comenzi exacte

Cwd pentru toate: /home/kali/.hermes/cache/scratch/t1-pr-ct0vinu2/src
Interpreterul din mediul existent este Python3.13.15; dependențe pytest9.1.1, pytest-asyncio1.4.0, Ruff0.16.9, mypy2.3.1. preflight.json verifică originile modulelor din worktree-ul owned; pytest folosește pythonpath din api/pyproject.toml. Nicio instalare/dependență modificată.

RED (precedat de aceeași comandă cu --collect-only -q):
```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u OMNIS_TEST_DATABASE_URL PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src/api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_runtime_supervisor.py::test_api_key_owner_admits_after_preopen_heartbeats -vv --tb=short
```
Final regresii (precedat de aceeași selecție cu --collect-only -q):
```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u OMNIS_TEST_DATABASE_URL PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src/api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_runtime_supervisor.py api/tests/test_native_preparation_startup.py api/tests/test_provider_settings_source.py::test_normal_supervisor_settings_after_open_uses_its_single_client -vv --tb=short
make --no-print-directory lint-api typecheck-api API_PY='/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src/api/.venv/bin/python -B'
git diff --check
```

Loguri: red.log/red-exit.txt, collect-red.log, green.log/green-exit.txt, collect-final.log, final-regressions.log/final-regressions-exit.txt, quality.log/quality-exit.txt, final-quality.log/final-quality-exit.txt. Inputuri: red-inputs.json, green-inputs.json, final-inputs.json. GREEN inițial folosește comanda finală pytest numai cu api/tests/test_runtime_supervisor.py.

## Limite / următorul pas

SOURCE, nu installed/live: DB/lease/fence/storage/transport sunt doubles declarate; InstanceService.open/admission/shutdown/quiesce și ApiKeyModelTest.handle/drain/reconcile/finished sunt reale. OPEN/SHUTDOWN sunt proiectate manual în InstanceRecord după return-ul metodei reale, ca în testul legacy existent. Prima admitere ajunge până la validarea selecției absente, nu la dispatch/provider succes. No-resend pentru SENT moștenit nu este reprobat aici; codul respectiv rămâne neschimbat, iar fixture-ul are zero operații moștenite. Nu afirm persistență PG, active network settlement sau cauza internă live observată.

Zero provider IO, fără Docker/PG provisioning, build/release/canonical integral, rollout, credentiale ori acces la fișiere protejate. Instanța operatorului rămâne imuabilă; procesul pytest/subprocesele import sunt terminate, fixture-ul UDS existent se curăță prin contextul său. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Scope map: AICI remediu implementat/SOURCE PASS/NOT_REVIEWED; T1 rămâne PARTIAL/NOT_ACCEPTED. Părintele deține commitul, reviewurile complementare și eventuala QA instalată cu autorizarea necesară.
