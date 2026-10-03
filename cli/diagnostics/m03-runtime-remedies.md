# M03 runtime F01–F06 — remediere scoped, fără închidere de gate

## Revizie, autoritate și verdict

- Branch: `m03-runtime-remedies`; bază exactă `c87ed67ed37466bb662a46da586fcf33b3e51ec4`.
- Ultima revizie de cod/teste verificată: `eaea2d1bd83720d90ceaccf2a83d472519f80e8b`. Commitul acestei note este numai documentare.
- **Cod:** F01–F06 implementate în attestorul existent. **Probe:** PASS source/wheel și canale sintetice descrise mai jos. **Review independent:** NOT_RUN, predare pentru re-review; self-review nu este aprobare independentă.
- M03/G00 rămân deschise; nu există autoritate de close, integrare în principal sau push.
- Autoritate citită: `AGENTS.md`, README/CLI README, arhitectura §4.1–4.5, rândul M03 din matrice, Compose/Dockerfile și producătorii Start/reconcile, skillurile TDD/debugging/lifecycle/review și release-ops din repo. Auditul `/home/kali/.hermes/cache/scratch/m03-rti-oW9Sbe/report.md` a fost citit integral.
- Niciun contact cu Docker/Podman/PostgreSQL ori daemon existent, inclusiv inspect/info. Fixture-ul carantinat și recuperările istorice nu au fost folosite. Testele existente cu procese/UDS private rămân explicit sintetice. Fără provider/target/P1, profile sau skills globale.

## Cod livrat

| Categorie | Predicate și limite |
|---|---|
| F01 | Env complet, chei unice și stringuri valide, comparat cu `Config.Env` citit din imaginea identificată exact; numai overrides emise efectiv per rol. PGDATA/PATH/LANG/WEB_ROOT și alte defaults sunt moștenite din metadata, nu dintr-un pin inventat în fixture. `_View.inspect("image", id)` apelează exclusiv metoda tipizată existentă `StopEngine.image`; `run` rămâne interzis. |
| F02 | Cmd existent păstrat; entrypoint control `None`/`[]`, DB `['docker-entrypoint.sh']`. Constructorul control refuză entrypoint diferit. |
| F03 | `PublishAllPorts is False` inclusiv înainte de start. Fără PortBindings; valorile nested ale porturilor live admit numai null/listă goală, nu scalar/obiect falsy. EXPOSE fără publicație rămâne permis. |
| F04 | Restart exact `no`, retry integer exact zero; Tmpfs gol/null; Devices/DeviceRequests/DeviceCgroupRules/CapAdd goale/null; IPC private. Binduri cu propagation `rprivate` și RW boolean exact. Migrate/reconcile nu admit Binds/Volumes suplimentare. |
| F05 | Setul de rețele este verificat și în created; Name/Internal/Driver/Options/attempt/project/ID au o singură politică pură comună CLI–owner. NetworkID corelat cu obiectul atestat; DriverOpts/IPAMConfig/Links nested fără overrides. Aliasurile proprii sunt numele containerului observat, CID complet/scurt și aliasul de serviciu Compose pentru cele trei servicii; alias străin refuzat. |
| F06 | DB păstrează User din imagine, rootfs writable și CapDrop/SecurityOpt default null/listă goală; nu primește politica API. Constructorul PostgreSQL verifică suplimentar `Os=linux` și ID `sha256:<64 hex>`. |

Singurul helper nou de produs este `_network_identity`, pur și mic, necesar pentru a elimina politica duplicată din `_View.network`. Acesta nu expune un nou canal de comenzi. Self-review a prins schimbarea accidentală a diagnosticului ownerului produsă de extragere: un RED separat a precedat restaurarea `STOP_NETWORK_DRIFT`/exit 4 în adapter, fără duplicarea regulilor.

Verificarea structurală AST confirmă că s-au schimbat numai `ControlRuntime.__init__/attest/network`, helperul nou și `_View.inspect/network`. `ControlRuntime.run`, `stop.py`, `_ContainerFamily.drained`, arhitectura owner/IPC/cgroup, API/schema, grant/receipt și producătorii Start/restart sunt nemodificați. Nu interferează cu CW-CGROUP-02/CW-CANCEL-01 ale părintelui.

Fixture-uri: `runtime_inspect_fixture.py` și `test_runtime_completeness.py` noi; forma existentă din `test_start_attestation.py`, `stop_owner_fixture.py`, `test_start_preflight.py` corectată pentru metadata imaginii și câmpurile reale necesare. Niciun guard de produs nu este ocolit pentru un pozitiv al attestorului. Fixture-urile sunt sintetice, NU capturi OCI.

## Probe executate

Scratch propriu: `/home/kali/.hermes/cache/scratch/m3r-ysf6dep3` (`S` mai jos); worktree-ul acestei note este `R`.

Toolchain: uv `/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv`, versiune `0.12.19`; Python `3.13.15`; Ruff `0.16.9`; mypy `2.3.1`. API și CLI pregătite separat cu `uv sync --locked --no-config --offline --no-python-downloads --python 3.13.15 --directory api|cli`, exit 0; `uv pip check` pentru ambele, exit 0.

`S/gate.py` păstrează argv/cwd/exit/durată/log în `S/checks.jsonl`. Rulează din `S/cwd`, cu HOME și XDG_CONFIG/DATA/STATE/RUNTIME/CACHE private, fără PYTHONPATH/MYPYPATH/pytest overrides, DOCKER_/COMPOSE_/PG/OMNIS ambientale. Cache-ul de pachete uv existent este referit explicit numai pentru build offline.

| Verificare | Rezultat real final |
|---|---|
| Baseline CLI pe baza exactă | 245 teste, exit 0 (`logs/baseline.log`) |
| RED→GREEN pe fiecare F01–F06 | Loguri `f01-red/green` … `f06-red/green`; fiecare categorie a avut acceptări/refuzuri greșite reproduse înaintea codului. Fixul diagnostic owner are `owner-network-red/green`. |
| Full CLI source după ultima editare | 263 teste, exit 0, 54.312 s (`logs/source-final-v2.log`) |
| Wheel nou offline, venv separat, full CLI instalat | 263 teste, exit 0, 54.452 s (`logs/wheel-final-v2.log`) |
| Ruff check + format check CLI source/tests | exit 0/0; 62 fișiere formatate (`logs/ruff-final-v2.log`, `format-final-v2.log`) |
| mypy CLI source, no-incremental | exit 0; 21 module (`logs/mypy-final-v2.log`) |
| Console instalată `omnis status --json` în XDG gol | exit CLI 3, NOT_INSTALLED, dashboard_ready=false; verificator exit 0 și roots private nemodificate (`status-wheel-v2.log`) |
| Scope AST/diff + scan static adăugiri de produs | exit 0; numai definițiile permise, fără patternurile periculoase scanate (`scope-verification.json`); aceasta este self-review limitată |

Comenzile finale efective sunt în ledger; forma lor reproductibilă:

```sh
python3 "$S/gate.py" source-final-v2 "$R/cli/.venv/bin/python" -I -B -m unittest discover -s "$R/cli/tests" -v
python3 "$S/gate.py" wheel-build-v2 "$UV" build --no-config --offline --no-python-downloads --python "$R/cli/.venv/bin/python" --wheel "$R/cli" --out-dir "$S/wheel-v2"
python3 "$S/gate.py" wheel-venv-v2 "$UV" venv --no-config --offline --no-python-downloads --python "$R/cli/.venv/bin/python" "$S/installed-v2"
python3 "$S/gate.py" wheel-install-v2 "$UV" pip install --no-config --offline --no-deps --python "$S/installed-v2/bin/python" "$S/wheel-v2/omnis_cli-0.1.0-py3-none-any.whl"
python3 "$S/gate.py" wheel-final-v2 "$S/installed-v2/bin/python" -I -B -m unittest discover -s "$R/cli/tests" -v
```

Wheel final: `S/wheel-v2/omnis_cli-0.1.0-py3-none-any.whl`, SHA256 `7e01a4a8508463270e78ee8689c756221936d89c6cec0f6f1e1699a4093d4b82`. Importurile sunt din `S/installed-v2`; toate cele 21 module au bytes identici cu sursa verificată.

Cele 18 metode noi includ toate cinci rolurile și running/created/exited, defaults pozitive și negative la aceeași frontieră, snapshot bytes/mode/UID/GID/dev/inode/size/mtime și zero cereri de efect ale attestorului. Subprocess/connect au tripwire în matrice. Acoperirea consumatorilor: `service_ids`, Start/reuse real, `verify_running`, `_running_for_stop`, `_emergency_inventory`, `_View` și cele două roluri job. Observațiile auxiliare DB/HTTP/proces/socket sunt substituite explicit. Un test execută producătorii Python reali migrate/reconcile, capturează argv/env de create și le trece prin attestorul real; bootstrapul anterior și operația Docker însăși sunt substituite. Nu este probă de creare a unui container.

### Replay al auditului părintelui pe wheelul final

`python3 S/gate.py audit-wheel-v2 S/installed-v2/bin/python -I -B S/audit-v2/audit.py`: exit 0.

- Aceleași 400 chei de caz ca `/home/kali/.hermes/cache/scratch/pr-3betg831/m03/results.json`, comparate programatic: 21 controale pozitive acceptate; 378 negative refuzate; 0 erori; 147 acceptări negative anterioare devin refuzuri.
- Singura provocare negativă rămasă acceptată este `network/all/missing-running-member`: `network(allowed)` primește o mulțime maximă, nu inventar egal obligatoriu. Auditul inițial o adjudecase explicit ca non-bug izolat; criteriul nu a fost schimbat ca să dispară din ledger.
- Zero effect_attempts; state_unchanged=true pentru fiecare caz; socketul privat bound-only absent la final. Numerele inspect/info sunt citiri simulate, nu contacte Docker.
- Copia de audit a schimbat numai calea repo și forma/adaptoarele necesare: `Name` container, lookup PG și după image ID, `Engine.image` tipizat. Nicio mutație, așteptare sau criteriu al celor 400 cazuri nu a fost eliminat/slăbit.
- Dovezi: `S/audit-v2/results.json`, `fixture-shapes.json`, `existing-tests.txt`, `S/comparison-v2.json`. Auditul original are hash `7c4975f8b2f6699dcfa0b4c4bf244a0e20fbe90cfc788cbc9b87b1b6ce844229`; copia `adf5e23b5ebd76140f2e7488b514676278f15ec6b35ce2522cfafbd3bbf498d0`.

## Compatibilitate și NOT_RUN exact

1. **Docker/OCI/PostgreSQL fizic: NOT_RUN/PAUSED**, inclusiv build/capture imagini, Compose create→running→exited, full installed Start/Stop/restart/emergency, namespace/UID/cgroup/LAN/IPv6 și crash cuts. `make check`, `check-cli` agregat cu test-cli-live și gate-urile installed care ar contacta Docker/PG nu au fost rulate. Source/wheel nu certifică OCI.
2. Nu există capture confirmat al pinurilor Env/User/defaults, propagation pentru fiecare mount ori aliasurilor fiecărei versiuni Compose suportate. Valorile moștenite de produs se citesc din metadata runtime; fixture-ul nu fixează PATH/LANG/Python/PG_VERSION inventate în cod.
3. `NetworkID=""` este permis numai la created/exited cu Running exact false, key-set și NetworkMode exacte și un obiect de rețea independent atestat pe numele exact. Running cere ID egal, iar null/missing/divergent refuză. După exit se admite și setul gol; după remove containerul absent nu este atestat. Aceste tranziții au probe sintetice, **nu compatibilitate Docker măsurată**. O formă de daemon diferită, IPC neprivate, propagation diferită ori options/alias nedeclarat rămâne fail-closed, nu fallback permisiv.
4. Costul citirilor runtime suplimentare în deadline-ul instalat: NOT_RUN pe Docker. Nu se adaugă deadline, cache de autorizare sau promisiune fizică de readiness.
5. Re-review independent și integrarea cu modificările separate ale părintelui: NOT_RUN. Niciun credit pentru CW-CGROUP-02/CW-CANCEL-01, recuperări istorice sau gate-uri neexecutate.

## Istoric și rollback

Commituri de cod/teste: `a0c8f3b` F01, `0d400ff` F02, `47e57c1` F03, `68c7420` F04, `bfe7dc9` F05, `fb54e24` F06, `5cde486` consumatori/producători, `eaea2d1` diagnostic Stop. Incidentele intermediare au fost locale: corecții Ruff ale fixture-urilor și problema diagnostică găsită la self-review; toate gate-urile finale de mai sus au rulat după ultima editare de cod/teste. Probe anterioare v1 sunt păstrate, nu prezentate drept dovada ultimilor bytes.

Rollback numai de cod: inspectați dependențele, revert în ordine inversă, reconstruiți wheelul și rerulați testele. Nu există operație externă Docker/DB de inversat în această felie. Lecția reutilizabilă rămâne aici, fără modificarea skills globale: verificați defaults după tip și valorile nested, legați moștenirea de imaginea reală, testați producătorul efectiv și nu transferați un PASS source/wheel către OCI.
