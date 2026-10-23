# SOURCE fixes — candidate, not acceptance

Worktree: /home/kali/.hermes/cache/scratch/ot1-0zxf62th/runtime-src
Branch: impl/api-key-runtime-t1-model
Base: 80c3ecd7d4618bf998cc573bf4a7c36834283e91
Base tree: 02045ec990426bc1ed7e08d69f69ebcae733951b
Final commit: fb54beace973b7c49422b197404f04c8baa6a9dd
Final tree: d112d081cb7b3b8a34a6ab6f00f24db87685d249
Final git status: clean. Delta: 7 files, 284 insertions, 15 deletions.

## Granular commits

1. 57bd0497e00b7f17a81a0ef2f9d9f0078b6a2efb — ordinary empty/error DNS closes OPEN, UPSTREAM_UNAVAILABLE, explicit new OPEN allowed. Tree 2c4ac3e908e9e16ef715583261708b339dcea66a.
2. e60b9b7028e7c1a4a50e698c9a8219332dd94077 — raw stream retained until public TLS wrap succeeds; unsuccessful handshake closes through existing FENCE/DRAIN. Expected transport errors normalize; cancellation/control/cleanup errors stay fatal. Tree 2d9d9260b142aa8f638d1f60b77cdf191360f757.
3. 37915d576950c5136583ecdbb059a65484d01fe4 — bounded strict ACK version/sequence/Scope.parse before correlation. Tree bc8b48438581c049b990eb456ceb8b143558e1a8.
4. fb54beace973b7c49422b197404f04c8baa6a9dd — only XDG_CONFIG_HOME line in existing StartTest.setUp. No product config changes.

## Exact selected source and pins

All commands below run from the worktree above. API pytest uses -c api/pyproject.toml, whose pythonpath selects current api/src. CLI commands explicitly insert current cli/src before import. Provenance was read from module.__file__: current api/src/omnis/supervisor/model_sender.py, current api/src/omnis/supervisor/model_relay.py, current cli/src/omnis_cli/model_relay.py and current cli/src/omnis_cli/start.py.

Python 3.13.15; httpcore 1.0.9; HTTPX 0.28.1; OpenAI 2.24.0; AnyIO 4.15.1; pytest 9.1.1; pytest-asyncio 1.4.0; Ruff 0.16.9; mypy 2.3.1. Existing api/.venv and cli/.venv only; no install or changed pins.

## RED/GREEN exact commands and raw outputs

Common API prefix (literal argv/environment, no implicit effects):

`env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml`

Append these exact arguments to that prefix:

- DNS RED: `api/tests/test_model_relay_scopes.py -k dns_failure -q --tb=short` — exit1, 2 failed/2 passed/1 deselected; source-dns-red.txt.
- DNS GREEN: `api/tests/test_model_relay_scopes.py -q --tb=short` — exit0, 5 passed; source-dns-green.txt.
- TLS RED: `api/tests/test_model_sender.py -k tls_ -q --tb=short` — exit1, 11 failed/22 deselected; source-tls-red.txt. Includes actual ClientHello cut through production broker/public TLS, plus public wrap fault controls.
- TLS GREEN: same TLS argv — exit0, 11 passed/22 deselected; source-tls-green.txt. After final type-narrowing assertion, same argv passed again: source-tls-green-final.txt. Focused mypy source+test also exit0.
- ACK RED: `api/tests/test_model_relay_protocol.py -k scoped_ack -q --tb=short` — exit1, 3 failed/3 passed/23 deselected; source-ack-red.txt. Each boolean ACK was wrongly accepted before fix.
- ACK GREEN: `api/tests/test_model_relay_protocol.py -q --tb=short` — exit0, 29 passed; source-ack-green.txt. Valid, missing and non-OK paths preserved.

All raw files are in this same logs directory. RED test edits were followed by their independent product fix and coherent GREEN commit; no source bug was replaced with a harness change.

## Final verification after LAST source/test edit

API prefix above plus:

`api/tests/test_model_relay_protocol.py api/tests/test_model_relay_scopes.py api/tests/test_model_sender.py api/tests/test_model_test_v2_contract.py -k 'not original_usage and not redacts_before and not usage_bounds' -q --tb=short`

Exit0: 52 passed, 20 deselected, 1.88s; source-final-affected-tests.txt. Unchanged usage/redaction checks deliberately excluded. Actual ModelSender.metadata uses verified public AnyIO TLS over the real broker to owned TCP: handshake cut => sanitized METADATA_UNAVAILABLE; one connect/no HTTP/no implicit retry; scoped DRAIN ACK => OK; explicit fresh operation => verified healthy TLS GET/models success. Wrap-double controls preserve exact cancellation/RelayFailure/control exceptions and fatal cleanup failure. Existing SDK streaming outage controls execute real AsyncOpenAI over MockTransport, not provider integration.

CLI Start command (manifest stdlib CLI interpreter, exact source prefix):

`private=$(mktemp -d "$TMPDIR/source-cli-XXXXXX"); trap 'rmdir "$private"' EXIT; XDG_CONFIG_HOME="$private/config" TMPDIR="$private" cli/.venv/bin/python -I -B -c 'import pathlib,sys,unittest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root/"cli/src")); import omnis_cli.start as s; print("SELECTED",s.__file__,flush=True); unittest.main(module=None,argv=["unittest","discover","-s","cli/tests","-p","test_start.py","-v"])'`

Exit0: all 8 existing tests passed, 0.228s; source-cli-start-green.txt. Parent pre-edit frozen80 private-config result remains parent-cli-80-isolated-start.log; ambient predicate not established. No personal config read, no broad CLI suite.

CLI physical-fence command:

`private=$(mktemp -d "$TMPDIR/source-fence-XXXXXX"); trap 'rmdir "$private"' EXIT; XDG_CONFIG_HOME="$private/config" TMPDIR="$private" cli/.venv/bin/python -I -B -c 'import pathlib,sys,unittest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root/"cli/src")); import omnis_cli.model_relay as s; print("SELECTED",s.__file__,flush=True); unittest.main(module=None,argv=["unittest","discover","-s","cli/tests","-p","test_model_relay_fence.py","-v"])'`

Exit0: 1 passed, 0.072s; source-final-cli-fence.txt.

Actual final quality commands from Makefile:

- `make --no-print-directory lint-api typecheck-api` — exit0; source-final-api-quality.txt. Includes Ruff check/format and strict mypy over all api/src and api/tests, no gate weakening. JSON diagnostics empty (`[][]`).
- `api/.venv/bin/python -I -m ruff check --config api/pyproject.toml --no-fix cli/src cli/tests` — exit0.
- `api/.venv/bin/python -I -m ruff format --config api/pyproject.toml --check cli/src cli/tests` — exit0, 77 files already formatted.
- `env -u PYTHONPATH -u MYPYPATH api/.venv/bin/python -I -m mypy --config-file api/pyproject.toml --no-incremental --output=json cli/src` — exit0.
- Combined CLI raw output: source-final-cli-quality.txt.
- `git diff 80c3ecd7d4618bf998cc573bf4a7c36834283e91 --check` — exit0; source diff reviewed. Only synthetic fixture secrets/certificates, no actual credentials added.

## Exact delta blobs (base -> final)

- api/src/omnis/supervisor/model_relay.py: 80558e289b4dbb1beb69fcb15f5b1575ac813ddf -> 6118e04b4fc09146f4066387285fac46c311789c
- api/src/omnis/supervisor/model_sender.py: a46634f18a42b4f4007cfc82dc051b31fef991c8 -> b1bd97ba39898135619c9dcdec4a4c54df528ab8
- api/tests/test_model_relay_protocol.py: c3a01247d8fbf7822a033acb1f96f5bee380f847 -> 0cb46f19001b194a1d6a0001854b4d8ea58c2e30
- api/tests/test_model_relay_scopes.py: d0c346c4639b3e4511c76e65279c97feed72f3f4 -> 488881037fdb8640c77e97cedf74bdf7d071fee1
- api/tests/test_model_sender.py: 12b91f6e06835961daa1bcfa659c976baccbec5d -> 3925c976a48d528a65213d39e58d956c46dfe558
- cli/src/omnis_cli/model_relay.py: e76b39e8930cc06d24476d846f0762d628b66288 -> 0d072a045f57e71fa048f383d94a55136c988ff8
- cli/tests/test_start.py: e72f9def8e4d2b07307efd73d0111d83391fc745 -> 1174ad0f66e330375125e48c40922daa310db2a1

## Cleanup / limits / next decision

Owned private UDS/loopback servers closed and wait_closed awaited; TLS peer tasks joined, broker FENCE/DRAIN asserted, resolver completed; TemporaryDirectory roots (including synthetic TLS certificate/key) removed. CLI private shell roots removed by trap; unittest fixture roots cleaned. No service/process was left running by these checks. Original roots and prior data/logs retained.

SOURCE implementations complete; independent focused review on these final bytes remains parent-owned. No R2 HIGH closure, T1 acceptance, integration, installed format5, native, real provider or full canonical claim. No PG was provisioned or touched. Exhausted two-cycle connect/write frontier remains BLOCKED, Cancel409 attribution unchanged; metadata owner-loss2 separately unattributed. No new harness/rewrite/observer/framework, immutable bundle, install, dependency change, docs/Main/profile/secret/operator config edit, target traffic or push. Existing seven NONRELAY029 approvals were not reopened. Next: parent focused independent re-review; real consumer only if its safety prerequisites/row are separately admitted.
