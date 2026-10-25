# Predare developer — FREEZE, nu acceptare T1

## Identitate
- Worktree exclusiv: `/home/kali/.hermes/cache/scratch/t1-explicit-recovery-u4ipsfl1/src`.
- Base `dd4f8747287496d1bb589de277455354d122892a`.
- Candidat local `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`, tree `9d0a3a1e9e5a45ffcf31cf76eea879d68b52063c`, clean.
- `freeze.json`: cele 10 changed paths, blobs/SHA256, diff hash, wheeluri și probe. Un singur commit coerent vertical cu cod/teste/doc inseparabile; fără push/amend/rebase/squash.

## Comportament și consumer
`main(recover --json)` → aceeași funcție Stop și aceleași lifecycle locks/OFD aliases → preflight READY5/T1 și exact CID mort → lease expirată și OPEN original în DB → intent original-bound durabil + journal RECOVERING → revalidare → un singur `ControlRuntime.run('start', CID, effect=True)` → status de la PID-ul supervisorului și noul epoch/quiescence CLOSED → STOPPING autentic → SHUTDOWN/FINALIZE/ARM_STOP → owner/completion existente → STOPPED.

Nu se scrie READY nou, nu există OPEN intermediar. `InstanceService.acquire` reține numai identitatea barierei implicite produse de acel takeover comis; opt-in doar din supervisorul normal T1. SHUTDOWN existent validează owner/epoch/generation/bariera/quiescența/absența receiptului implicit și a fence-ului; produce comandă/generație/receipt nou. Replay-ul wire existent rămâne neschimbat, payload suplimentar nu a fost introdus. Nicio migrare, public HTTP ori command-kind nou.

Un intent întrerupt blochează Start/Stop/recover; nu reia nici startul daemon, nici teardown-ul. Nu s-a implementat recovery generic/emergency repair. STOPPED necesită completion autentic, verificarea resurselor absente și date păstrate. Guardul cap-ului vechi este pre-effect; LocalControl rămâne singurul owner al înlocuirii cap/socketului.

## Probe și comenzi (cwd = worktree)
Toolchain: uv0.12.19, Python3.13.15; `.venv` API/CLI proprii create offline din lock. Înaintea lor, interpreter API împrumutat read-only cu `sys.path` explicit și origin verificat către worktree; nu a fost modificat.

### RED păstrat
- `red-api.txt`: pytest `api/tests/test_instance.py::test_owner_loss_new_shutdown_source`, exit1, acquire/quiesce reale cu double SQL → SHUTDOWN refuzat COMMAND_CONFLICT.
- `red-cli.txt`, `red-cli-vertical2.txt`: unittest `test_recover.py`, exit1, parserul nu cunoaște recover. Verticala testată folosește Stop-ownerul existent, nu un owner substitut.
- `red-drift.txt`: test `test_journal_drift_before_start_has_no_daemon_effect`, exit1, effect start atins după drift.
- `red-cap.txt`: test `test_denials_before_intent_preserve_resources_and_journal`, exit1, cap malformat primea incorect exit0.

### GREEN / regresii
- `XDG_CONFIG_HOME=<evidence>/empty-config cli/.venv/bin/python -I -B -m unittest discover -s cli/tests -v` → **380 PASS, exit0**, `cli-source-regression.txt` (înaintea ultimului guard cap).
- Aceeași comandă cu `-p test_recover.py` după guardul cap → **7 metode PASS, exit0**, `green-cli-final.txt`; controale pe healthy/live lease/CID/daemon/storage/profile/socket/cap/unreconciled/malformed, ACK/exception/epoch/generation/owner/drain, retry și concurență prin lockurile reale. Stop inventory/grant/frame/handoff la generații maximale prin serializerii reali; oversize refuzat.
- API: pytest `test_instance.py test_control_regressions.py test_local_control.py test_stop_fence.py test_supervisor.py`, plugin de selecție read-only elimină exclusiv itemii cu fixtures `migrated_database_url`/`empty_database_url`, `-p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml -q --tb=short` → **25 SOURCE PASS, 119 deselectate, exit0**, `api-source-regression.txt`. Nu este un gate PG mascat.
- `api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-instance-drain-pg --uv /home/kali/.local/share/omnis-toolchains/uv-0.12.19 --timeout-seconds 240` → **exit0, 25 PASS33.15s = 14 SOURCE + 11 PG**, o singură tentativă. `pg-preflight.txt`, `pg-collect.txt`, `pg-run.txt`, copii byte-exact `pg-gate.log`, `pg-gate-result.json`. Nou: caller CLI request real → UDS LocalControl real → PostgreSQL real, live-lease denial, takeover, quiescence/drain failure, SHUTDOWN nou, replay exact/refuz schimbat, FINALIZE/ARM_STOP, census al celor cinci tabele de autoritate și refuz fence. `family_drained=true`; CID `48cd95b124414f8d0a2a7c9089a1020c1548c74cb02c10b24258199b9c16611b`, network și socket proprii absente; PGDATA păstrată în `/home/kali/.hermes/cache/scratch/db-a49179af44cb4d30`. Targetul existent include testele noi fără Makefile/runner schimbat. `_owner` SQL este byte-exact neschimbat după această probă; API source neschimbat. Ultimul guard cap afectează numai preflight-ul CLI, nu tranzacția PG.
- Ruff `check --no-fix`, `format --check` pe întreg `cli/src cli/tests` și cele trei fișiere API afectate; mypy `--no-incremental --output=json` strict pe CLI și API afectat → toate **exit0**. Config `api/pyproject.toml`, interpreter API propriu. Fișiere `ruff*.txt`, `format*.txt`, `mypy*.jsonl` păstrează și iterațiile anterioare.
- Venv docs propriu, instalare offline `documents/requirements-docs.txt`; `python -B scripts/render_docs.py --check`, `python -B -m unittest discover -s tests/documentation -v` → **exit0**. Niciun HTML regenerat.

### Artefacte
- `uv build --no-config --offline --wheel api --out-dir <evidence>/api-wheel` → exit0. API SHA256 `26e403514e6d98d21d4b5f2100dae2ab4a36f2eab98fb3a84c256d73dfcc3987`, **113 module Python verificate byte-exact**.
- Echivalent CLI în `<evidence>/cli-wheel-final` → exit0. CLI SHA256 `71b6937a5a4196dda06e7aa3a3ce984b44e099de94fec29d391a04cfe0bc2274`, **27 module verificate byte-exact**.
- CLI final instalat offline/no-deps în `<evidence>/cli-wheel-env`; origin real verificat. `.../bin/python -I -B -m unittest discover -s cli/tests -v` cu XDG config gol → **380 PASS, exit0**, `cli-wheel-regression.txt` după ultima editare de produs. Fixture-ul Stop-owner existent selectează explicit SOURCE în copil și substituie doar familia-container sintetică: acest rezultat nu este installed Docker recovery.
- `<evidence>/cli-wheel` este buildul intermediar pre-guard-cap, **nu candidatul final**; folosit numai pentru verificarea neschimbării SQL `_owner` față de proba PG.

## Încercări nereușite / limite
- `red-cli-vertical.txt`: prima adaptare a fixture-ului a încercat `_put_record` peste receiptul sintetic deja existent; FileExistsError și timeout runner124. Remediat numai fixture-ul: cleanup înregistrat înainte de pregătire și înlocuire explicită a receiptului SINTETIC. Nicio resursă Docker în acea probă.
- `green-cli1.txt`: primul negativ nu fixa XDG_CONFIG_HOME; a observat exit2 în preflight, nu refuzul așteptat4. Fixture-ul a fost izolat explicit ulterior. Configurație ambientală non-secretă posibil citită de testul inițial; nu s-au cerut/citit chei și nu s-a executat daemon/provider IO pe acea cale. Nu declar retroactiv că acel test era izolat.
- `green-cli3.txt`: controlul concurent Start a refuzat layoutul sintetic `root/c` înainte de lock (IPC_LAYOUT_INVALID), nu intentul; fixture-ul mută acum controlul în path extern valid. Nicio relaxare a validatorului de produs; 380 SOURCE și 380 wheel au trecut ulterior.
- Nu sunt probe fizice: daemon start/OCI și SQL/control din testul CLI sunt doubles declarate. Receipt/locking/handoff/Stop-owner/completion sunt consumate real cu familia-container sintetică existentă. PG verifică separat tranzacția și wire-ul real. Reconcile/drain runtime model rămâne implementarea neschimbată apelată de supervisor; crashul instalat integral trebuie verificat după reviews.
- Fără alte targeturi PG, canonical/check-components, build web, instalare/fault Docker T1, provider IO, target IO, chei, upgrade/restore cross-digest sau rollout. Canonical8 neschimbat reutilizat scoped. `cli/integration/installed_stop.py` neschimbat; n-am introdus harness nou.
- Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

## Stop boundary / pasul părintelui
FREEZE pentru două reviewuri independente pe același manifest: R1 ordine/persistență/readback, R2 authority/input/concurență/uncertitudine. Candidatul nu este acceptare; sursa nu închide proba fizică instalată și T1 nu se închide.

Decizia nouă de livrare este incorporată în CLI README: după gates se poate construi bundle NORMAL T1 cu ambele wheeluri și instala într-un root durabil NOU; instalarea actuală se păstrează integral. API-ul vechi nu are noua tranzacție; CLI nou singur nu este rollout admis. Release0.1.0 rămâne immutable și restore cere digest exact; fără workaround. Pregătirea bundleului, QA fizică și deploymentul rămân la părinte/operator.

Lecție pentru eventuala actualizare procedurală de către părinte: păstrează distinct owner-loss implicit versus SHUTDOWN comandat; acordă noua comandă numai barierei create de takeoverul curent și nu credita absența daemon ACK drept retry. Nu am modificat skilluri/profiluri în afara ownershipului.
