# R2 — APPROVED_SCOPED (SOURCE scratch-root portability)

## Identitate și limită

- Repository: `/home/kali/OmnisAI`.
- Base: `a5704061bf631e0875be959a4b0ea44784b9f7a5`.
- Snapshot reviewed: `e175b065c6415886c3cf6856f74c4d093399d148`, verificat identic înainte/după.
- `api/tests/test_contract_method_pg.py`: blob `5e158784bcc200df1013dfe8f1606c954a6f3215`; SHA256 `156f8b59dd7aa2de82e4fc11a88f757acae7da5cbf430322bc3442ff0cdaf9a3`.
- `.github/workflows/ci.yml`: blob `2a75489f4e18944c69198319fd1d3b544c0c2aab`; SHA256 `8e5b934af04e127b93c933e960a0e4041d0f6ef8ae9cf8c305ff55fc79391023`.
- R2 verifică izolarea SOURCE, predicatele de containment, barierele review-before-effects, sibling/finalizer și restaurarea fixture-ului. R1 deține proba shallow/full-history; aici doar confirmat diff-ul workflow `fetch-depth: 0`, fără alte schimbări.
- Verdictul nu califică native, nu transferă aprobări pe vechiul digest, nu declară CI remote/global GREEN și nu integrează nimic.

## Findings

**Niciun finding blocant în scope-ul R2. APPROVED_SCOPED.**

### Criteriu → cod → probă

1. **Implicit nativ neschimbat, fără backdoor de mediu.** `:54` definește exact vechiul literal `/home/kali/.hermes/cache/scratch`; utilizările noi sunt numai plannerul `:5007` și predicatele de admission `:8527–8529`. Nicio variabilă de mediu nu selectează acest default. Verificarea AST a întregului fișier, după inversarea exclusivă a deltei declarate (constantă, fixture, nouă decorators, operandul negativ și substituțiile literalului), este identică cu baza. Astfel sunt păstrate assertions, opt-in, grants, source-digest, UID/FD/mount și lifecycle semantics, nu doar câteva linii inspectate.
2. **Fixture explicit, nu autouse.** `:1981–1985` folosește monkeypatch function-scoped pentru constantă și TMPDIR. Nouă familii explicit marcate; datele full-collection ale autorului arată 33 cazuri native fără `source_scratch_root`. La rularea independentă, după pytest.main, assertions pentru default restaurat, TMPDIR restaurat și zero evenimente interzise au trecut înainte de eroarea de readback descrisă mai jos.
3. **Callerii afectați și namespaces sunt complet acoperiți.** Folosirile lui `h03_container_argv` și ale noului nume au fost inventariate AST/text. Lifecycle SOURCE creează namespace din `dict(globals())` (`:4212`), păstrează helperul real și substituie exclusiv daemon/Host seams; nu execută native. Callerii direcți finalizer `:4538–4540` și startup cleanup `:5931–5935` au propriile marcaje, deoarece un apel Python direct nu activează decoratorul pytest al callee-ului. Siblingii alias și batch2-review sunt de asemenea expliciți.
4. **Refuzul review este refuzul intenționat, nu eroarea de root anterioară.** SOURCE historical `:1988–2015`, H03 `:3927–3942`, batch2 `:5064–5093` au trecut cu motivele existente `HISTORICAL_EXACT_REVIEW_REQUIRED` / `H03_EXACT_TWO_REVIEWS_REQUIRED`; sentinelele dinamice `DATABASE_ACQUIRED_BEFORE_REVIEW`, `H03_EFFECT_BEFORE_REVIEW`, `BATCH2_EFFECT_BEFORE_REVIEW` nu au fost atinse. Review gate-urile reale `:1603–1604` și `:7950–7956` rămân înainte de DB/artifact/container effects.
5. **Negativul foreign-root rămâne discriminant.** În `:3995–4008`, pozitivul real întoarce argv strict, iar `tmp_path.parent` este refuzat exact cu `H03_CONTAINER_PLAN_REFUSED`. Readback independent al resurselor acestei rulări confirmă parent/state absolute, canonice, directoare, UID1000 și mode0700; parent este distinct și în afara rootului patch-uit. Celelalte predicate sunt admisibile; refuzul nu poate fi atribuit ownership/mode/symlink. Plannerul `:5008–5061` nu a pierdut predicate ori opțiuni. Controalele QA read-only mount și physical-alias au trecut.
6. **Finalizer și cleanup păstrate.** Toate cele42 lifecycle SOURCE,15 finalizer și4 startup-cleanup cases au trecut, incluzând return/failure/cancel/pre-acquire. Sunt probe ale codului actual extras cu seams substituite, nu Docker/Host/native QA.

## Probe independente

Prereflight: citite manifestul pytest, conftest, callerii selectați și callee-urile până la bariere; fără opt-in. Mediul subprocess a fost curățat (`env -i`), plugin autoload dezactivat, bytecode/cache pytest dezactivate. Interpreterul folosit: `/home/kali/OmnisAI/api/.venv/bin/python -B`. TMPDIR și basetemp sunt exclusiv în scratch-ul propriu.

Selecția reală a fost derivată din cele nouă marcaje explicite și verificată după collection:

| Familie | Cazuri |
|---|---:|
| historical_review_gate_precedes_database_fixture | 1 |
| stock_site_mount_is_single_ro_outside_rw_roots | 1 |
| h03_review_gate_precedes_database_and_container | 2 |
| h03_stock_container_plan_is_owned_and_contained | 1 |
| h03_actual_lifecycle_source_seams | 42 |
| host_diagnostic_actual_finalizer | 15 |
| h03_mount_roots_refuse_physical_alias | 1 |
| batch2_installed_route_before_fixture | 8 |
| startup_primary_shared_cleanup | 4 |
| **Total unic** | **75** |

Comanda pytest, cu fiecare familie prefixată `api/tests/test_contract_method_pg.py::`, a folosit:

`-c api/pyproject.toml -p pytest_asyncio.plugin -p no:cacheprovider -m 'not legacy_native' --tb=short -q -s --basetemp=<owned>/run --junitxml=<owned>/selected.xml <cele 9 familii>`

- `collect.log`: collect-only exit0,75 IDs unice; import/collection fără evenimente interzise.
- `selected.log` + `selected.xml`: **75 PASS în5.84s**, zero errors/failures/skips. Un audit hook a refuzat subprocess/fork/exec, socket connect/bind/DNS, accesul la fișierele private nominalizate și file writes în afara scratch-ului propriu.
- **Incident al reviewerului păstrat:** wrapperul a terminat exit1 DUPĂ cele75 PASS și DUPĂ assertions de restaurare/zero effects, fiindcă readbackul căuta greșit prefixul numelui temporar trunchiat de pytest (`StopIteration`). Nu este un FAIL al testelor și nu a fost ascuns prin rerularea suitei.
- `readback.log`: verificare separată exit0 a JUnit și a directorului real `test_h03_stock_container_plan_0`;75 cazuri și predicatele negativului confirmate. Nicio rerulare native sau SOURCE pentru cosmetizarea exitului wrapperului.
- `integrity.log`: whole-file inverse AST equality; exact snapshot/hash; agregare programatică a probelor autorului.
- `git diff --check <base> <snapshot> -- <cele două fișiere>` exit0. HEAD și status final neschimbate; doar cele două untracked preexistente protejate, fără citirea conținutului.

## Probe ale autorului reutilizate numai în scope

Din `/home/kali/.hermes/cache/scratch/ciroot-proof-pmrk288x/{collect,red,green,plain,guards,full-collection}.json`:

- Aceleași75 node IDs, ordine exactă verificată; fixtures diferă legitim între RED și GREEN.
- RED **SIMULATED foreign topology**:44fail/31pass; cele șase familii nominalizate62cazuri:33fail/29pass.
- GREEN SIMULATED75pass și plain75pass; zero forbidden_effects în rapoarte.
- Full collection:33native cases fără SOURCE fixture; nouă familii SOURCE/75cazuri.
- Nu deduc că toate parametrizările remote au eșuat sau că au aceeași cauză. Nu promovez SOURCE/simularea în native qualification.

`quality-final.log` conține doar `[][]`; nu îl folosesc ca probă independentă pentru lint/typecheck ori quality global.

## Fișiere, efecte și handoff

Niciun fișier din repo editat, niciun commit/push, nicio instalare/service/PG/Docker/browser/provider/target pornit. Au fost create numai logurile/JUnit, scratch-ul fixture-urilor SOURCE și acest raport în `/home/kali/.hermes/cache/scratch/r2-jjfxia64/`. Resursele sunt fișiere temporare proprii, nu servicii persistente.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Părintele adjudecă și deține consumerul remote după reviews. Source digest schimbat înseamnă că vechile native qualifications nu sunt aprobate de acest raport.

Neexecutat: native/PG/Docker/browser/provider/target, suita integrală API, canonical și remote CI; proba history/shallow aparține R1. Riscul rămas este integrarea remote pe bytes finali, nu un finding SOURCE demonstrat aici.
