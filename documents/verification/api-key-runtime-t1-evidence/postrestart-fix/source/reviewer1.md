# R1 — lifecycle și primul consumer după restart

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: `[]`.** Remediul elimină mecanismul SOURCE reprodus fără relaxarea noului Stop sau resetarea unui owner eșuat. Aprobarea privește numai delta și frontiera de admitere de mai jos; nu este acceptare T1, ProviderSuccess ori dovada remedierii instalării8773. Cauza internă a incidentului live rămâne **UNKNOWN/NOT_OBSERVED**, distinctă de mecanismul SOURCE demonstrat.

## Identitate și contract

Review read-only în `/home/kali/.hermes/cache/scratch/t1-pr-ct0vinu2/src`, HEAD **`8c527a0694465f8470b91ad7f014764e29385f64`**, bază `083e6f6407ecf0adf0de6545b013851dac5098dc`. Worktree curat înainte/după; numai două fișiere în delta. `freeze.json`/handoff sunt anterioare commitului candidat; bloburile și hashurile lor coincid cu HEAD verificat. Principalul și CURRENT-ul live sunt context, nu produsul reviewuit.

| Fișier | Blob Git | SHA256 |
|---|---|---|
| `api/src/omnis/supervisor/__main__.py` | `44dc21f65947b40dad28a2cf5eb5cacfa27510c3` | `1c821dd0d0a99496e6d4245fe9b82939495d48c850165413bc0d87baf82da82a` |
| `api/tests/test_runtime_supervisor.py` | `aba6ab88e87f4b0973ee18fce2ee7f1535c25648` | `c1b04fcad06357cebaaf61e6a23a22b728f4af0579c7066b1920038b8f4d93e5` |

Criterii: **plan `documents/Omnis_Implementation_Plan.md` §7**, L243, L258–262 (admitere/Stop/reconciliere/no-resend), **§8**, L266–272 (consumer real, test nou explicit după reconciliere, simulare distinctă de live). Arhitectură §4.2–4.3, L138/L161–163 și §5, L229–235: OPEN explicit într-o generație nouă, barieră durabilă, owner-loss fail-closed și istoric receive-only. Aplicate delivery/team-slice/review-QA; fără redeschiderea întregului T1.

## Cerință → cod → probă și dispoziție

- **Startup și ordinea expunerii:** `__main__.py:96–116,160–191` păstrează pregătirea inertă → acquire → owned_status/captură generation → owner → reconcile → quiesce inițial → unicul reset `closing=False` înainte de LocalControl/callback. Un quiesce eșuat nu ajunge la reset sau expunere. Nu apare OPEN implicit, autoritate ori owner nou alternativ.
- **Istoric + două heartbeat-uri pre-OPEN:** `__main__.py:219–225` extinde guardul existent numai la `model_owner`; aceeași generație deja drenată nu mai închide ownerul proaspăt. Calea legacy și Settings fără model owner își păstrează comportamentul. Testul `test_runtime_supervisor.py:248–459` verifică exact două heartbeat-uri înainte de OPEN și `sender.drain` o dată pentru shutdown istoric, zero pentru fresh, până la primul callback.
- **Primul consumer:** callbackul instalat de supervisor este metoda reală `ApiKeyModelTest.handle`; `model_test_runtime.py:249–299` trece prin `InstanceService.admission` (`service.py:464–476`) și lookupul real `ProviderSettingsOwner.selection`. După resetarea istoricului SQL al double-ului, testul cere SELECT-ul `provider_selection_revision` și exact `REVISION_CONFLICT` pentru selecția absentă. Aceasta dovedește depășirea refuzului prematur `CONTROL_UNAVAILABLE`, **nu** operație persistentă/dispatch/răspuns provider.
- **Stop nou și eșecuri:** OPEN și SHUTDOWN reale cresc generation (`service.py:434–461,478–517`); noul Stop nu satisface guardul startup. Quiesce/drain reale anulează și join-uiesc taskul, iar callbackul refuză în tickurile următoare. Settlement failure setează latch-ul real și rămâne refuzat, inclusiv drain final incert fără release. Owner-loss este injectat în guard/heartbeat: refuz `LEASE_LOST`, ieșire și owner închis, nu recuperare automată. Niciun reset nou în loop/finally.
- **Istoric/no-resend:** delta nu schimbă reconcile, replay/read, InstanceService, fence, lease sau sender. Fixture-ul are zero operații moștenite; nu atribui acestei probe acoperire SENT/crash/no-resend ori citire de istoric persistent. Regresia legacy existentă este nemodificată.

## Execuție și limite

Am verificat originile importurilor supervisor/model_test_runtime în worktree (Python `-I -B`, exit0), apoi am executat **o singură probă bounded existentă**, cwd de mai sus, timeout90s:

```sh
env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u OMNIS_TEST_DATABASE_URL PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TMPDIR=/home/kali/.hermes/cache/scratch /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src/api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_runtime_supervisor.py::test_api_key_owner_admits_after_preopen_heartbeats -vv --tb=short
```

**R1: 6 PASS, 0.75s, exit0.** Fresh/istoric × Stop/settlement-failure/owner-loss. DB, lease, fence, storage, transport și LocalControl sunt doubles declarate; OPEN/SHUTDOWN sunt proiectate manual în InstanceRecord după metodele reale. Nu este restart de proces instalat sau persistență PG.

Readback al dovezilor autorului: `red.log` **3 FAIL istorice/3 PASS fresh, exit1**; hashul supervisorului RED coincide cu baza Git, iar testul RED are exact hashul final. `final-regressions.log` **57 PASS, exit0** (numărări verificate programatic); `final-quality-exit.txt` exit0, comanda full API Ruff/format/mypy în `handoff.md:40–42`. Nu am rerulat aceste gates. `git diff --check <base>..HEAD`, `git ls-tree`, `sha256sum`, status/HEAD: exit0, identitate stabilă.

**Predare:** SOURCE implementat/probat, R1 aprobat scoped; reviewul complementar, adjudecarea și QA instalată autorizată rămân ale părintelui, nu prerequisite circular al acestui verdict. T1 rămâne PARTIAL/NOT_ACCEPTED. Singurul fișier creat de R1: acest raport; fără product writes, commit/push sau modificări în checkout.

Neexecutate: provider/metadata, Docker/PG, rollout/canonical, UI și proba instalată; HTML-urile protejate și `tempkey.txt` nu au fost citite. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Riscul rămas: corecția SOURCE nu stabilește retrospectiv cauza live și nu certifică primul Test complet pe instalarea afectată.
