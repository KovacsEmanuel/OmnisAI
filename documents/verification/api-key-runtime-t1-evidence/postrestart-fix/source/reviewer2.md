# R2 — LIVE-POST-RESTART-01

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: `[]`.** Review independent read-only pentru authority/epoch/Stop și evitarea resuscitării ownerului închis; nu acceptare installed/live sau închidere T1. Nu am identificat un defect introdus de această deltă. Integrarea/adjudecarea rămân la părinte.

## Identitate și limită

- Worktree: `/home/kali/.hermes/cache/scratch/t1-pr-ct0vinu2/src`, curat înainte/după verificare.
- Base: `083e6f6407ecf0adf0de6545b013851dac5098dc`; HEAD: `8c527a0694465f8470b91ad7f014764e29385f64`.
- `api/src/omnis/supervisor/__main__.py`: blob `44dc21f65947b40dad28a2cf5eb5cacfa27510c3`; SHA256 `1c821dd0d0a99496e6d4245fe9b82939495d48c850165413bc0d87baf82da82a`.
- `api/tests/test_runtime_supervisor.py`: blob `aba6ab88e87f4b0973ee18fce2ee7f1535c25648`; SHA256 `c1b04fcad06357cebaaf61e6a23a22b728f4af0579c7066b1920038b8f4d93e5`.
- Diff `--full-index` base→HEAD identic cu `candidate.patch`: SHA256 `829026023583004ea28889cff4fe5b976b7d2ebb51ad0ed31a651597db6a9f74`. Diferența inițială față de hashul diff-ului implicit era exclusiv abrevierea celor două linii `index`, nu cod diferit. Handoff/freeze descriu faza precommit; HEAD-ul de mai sus este candidatul revizuit.

Contract citit: CONTRIBUTING/team-slice și arhitectură §4.3, plus callerii afectați `LocalControl`, `InstanceService`, `ApiKeyModelTest`, `ProviderSettingsOwner`, `NativeTaskOwner`. Fără audit universal/istoric sau modificări de produs.

## Cerință → cod → concluzie R2

- **Startup moștenit:** `__main__.py:105–116,160–165,219–225` capturează generation după acquire; reconcile/quiesce inițiale preced controlul. Skip-ul privește numai generația deja drenată. Resetul existent `closing=False` rămâne fresh/pre-control, niciodată heartbeat/OPEN.
- **OPEN/Stop nou, înainte sau după OPEN:** `service.py:434–460,478–547` incrementează generation; startup rămâne fix. Stop nou este deci drenat. OPEN nu resetează ownerul. Dacă SHUTDOWN comite după citirea pentru skip, bariera DB refuză imediat admission, iar următorul tick vede noua generație.
- **Authority/recovery:** `_require_owner`, lease/expiry, fence și generation rămân în heartbeat/owned_status/admission (`service.py:305–367,464–476,1005–1009`). Takeover/recovery nu schimbă semantica: noul SHUTDOWN explicit incrementează generația; FINALIZE/RESTART_REQUIRED nu sunt ocolite.
- **Închidere/failure/finally:** latch-urile `closing`/`settlement_failed` refuză lucru nou (`model_test_runtime.py:50–72,241–259`). Finally drenează; drain incert împiedică release, dispose rămâne garantat (`__main__.py:266–295`). Lease pierdut iese din loop; release real revalidează ownerul, nu îl recâștigă.
- **Familii/settings-only:** guardul legacy este păstrat; legacy montează close_model_test după drainul inițial, API-key folosește resetul fresh existent. Fără task_owner/model_owner, quiesce periodic rămâne necondiționat. ProviderSettingsOwner nu are latch closing și scrierile păstrează admission.
- **SENT/seif/dispatch:** reconcile moștenit rămâne drain/settle, nu scheduling (`model_test_runtime.py:74–143`). run/SENT/write_guard, replay/read receive-only și seiful sunt neschimbate; nu rezultă o probă installed nouă de no-resend.

## Probe și comenzi

Cerință→consumer→risc→decizie: prima admitere prin callbackul real după ticks pre-OPEN, plus Stop/failure→`supervisor.run`→închidere prematură ori redeschidere nesigură→aprobarea/refuzul SOURCE. Un singur rerun bounded al regresiilor existente; fără alt harness.

Din worktree-ul de mai sus am executat comanda următoare, întâi cu `--collect-only -q` în loc de `-vv --tb=short`, apoi integral:

```sh
timeout 45s env -i PATH=/usr/bin:/bin HOME=/home/kali LANG=C.UTF-8 TMPDIR=/home/kali/.hermes/cache/scratch PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src/api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml api/tests/test_runtime_supervisor.py::test_api_key_owner_admits_after_preopen_heartbeats api/tests/test_runtime_supervisor.py::test_fresh_model_owner_survives_historical_quiescence -vv --tb=short
```

**R2: 12 collected / exit0; 12 PASS în 1.07s / exit0.** API-key verifică pozitivul exact `REVISION_CONFLICT` la selecție absentă, atins în admission real după două ticks, nu succes de inferență. Stop nou anulează/join-uiește taskul și refuză repetat lucru nou; settlement failure refuză și împiedică release; fault LEASE_LOST refuză și închide ownerul la ieșire. Legacy: Stop/startup-failure/early-close, cu/fără shutdown moștenit.

Citite, nu revendicate ca execuții R2: `red.log` 3 FAIL istorice `CONTROL_UNAVAILABLE` / 3 PASS fresh; `final-regressions.log` 57 PASS / exit0; `final-quality.log` + exit file: API quality exit0. Identitatea a fost verificată prin `git status --short --branch`, `git rev-parse HEAD`, `git hash-object`/`sha256sum` pe cele două fișiere, `git diff --full-index BASE..HEAD` și `git diff --check BASE..HEAD` (exit0); indexul și worktree-ul au rămas curate.

## Limite / predare

DB/storage/transport/lease sunt doubles explicite; OPEN/SHUTDOWN proiectează manual starea după metodele reale. Testul nu probează locking/expiry/fence PostgreSQL, release real după LEASE_LOST, operații SENT moștenite sau settlement de rețea. Nici cauza internă a incidentului live, nici remedierea instalată nu sunt demonstrate; lipsa QA instalate nu blochează artificial acest verdict SOURCE.

Am creat numai acest raport; fără commit/push, product writes, provider/Refresh/Start, PG/Docker/build/rollout/canonical, acces la instanța8773/alte instanțe ori credentiale/fișiere protejate. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. **AICI: remediu SOURCE verificat / R2 APPROVED_SOURCE_SCOPED; T1 PARTIAL/NOT_ACCEPTED.** Părintele păstrează reviewul complementar și QA autorizată separate.
