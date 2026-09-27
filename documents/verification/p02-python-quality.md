# P0.2 — închiderea restanței de calitate Python înainte de P0.3

**Stare: QUALITY_GATE_VERIFIED_LOCAL / restanțele identificate înainte de P0.3 sunt închise local.** Bază curată `6c40083184fd89698518a25877c1dc7757407465`. Utilizatorul a cerut remedierea restanțelor necesare următoarei faze. Acesta este contractul feliei B01a pentru codul deja introdus, nu un plan nou și nu pornirea P0.3/P0.4.

## Rezultat observabil și perimetru

- Ruff pentru lint și verificarea formatării, mypy strict pentru **toate fișierele Python din `api/src` și `api/tests`**, inclusiv migrări și harnessuri. Nu ascundem erori prin `Any`, casturi fără validare, ignore global, excluderea fișierelor dificile sau teste slăbite.
- Configurație explicită, pinuri exacte în grupul dev și `api/uv.lock`; fără dependențe runtime noi sau instalare implicită în comenzile de verificare. Comenzile individuale intră în `make check` și în același workflow CI existent.
- Fiecare unealtă are control pozitiv și negativ pe diagnostic structurat: sursă exactă, cod și severitate; dependență lipsă/config invalid/timeout nu țin locul negativului.
- Remedieri de comportament cu RED→GREEN separat; normalizarea mecanică și adnotările păstrează comportamentul, cu regresii reale PostgreSQL/IPC/HTTP/procese/wheel după integrare. Review independent și commituri mici.
- Perimetru: API surse/teste/manifest/lock, Makefile, CI și ignore pentru artefacte generate, baseline-ul/documentele relevante și procedurile care primesc o lecție demonstrată. Nu atingem `AGENTS.md` protejat, profile personale, web/CLI, provideri, runtime sau ținte.

## Alegerea verificată a uneltelor

Candidați verificați în registrul PyPI și instalați **numai în venv scratch** înainte de adoptare:

| Unealtă | Pin | Licență upstream | Referință exactă |
|---|---|---|---|
| Ruff | `0.16.9` | MIT; notice-urile componentelor upstream rămân în distribuție | tag `0.16.9`, `0be08a206f9c3180afd3e93bcc792ed5cb1f4db1` |
| mypy | `2.3.1` | MIT, cu notice-uri PSF pentru componentele indicate în LICENSE | tag `v2.3.1`, `d642c4478e9e3acbe9233edbe17ffc569a1a778c` |

Surse: [Ruff exact PyPI](https://pypi.org/pypi/ruff/0.16.9/json), [mypy exact PyPI](https://pypi.org/pypi/mypy/2.3.1/json), [config Ruff](https://docs.astral.sh/ruff/configuration/), [config mypy](https://mypy.readthedocs.io/en/stable/config_file.html). Pinurile au fost confirmate și prin `--version` pe Python 3.13.15; nu folosim instalare `latest`. Regulile Ruff adoptate sunt E4/E7/E9/F/I/B și formatterul stabil, fără preview sau unsafe fixes. Lungime 100, Python 3.13.

Pluginul oficial `pydantic.mypy`, din Pydantic deja fixat, este necesar cu `init_typed=true` și `init_forbid_extra=true`: fără el, metodele sintetizate pentru modele produc 11 diagnostice `explicit-any`. Nu am dezactivat verificarea `Any`; proba cu plugin a eliminat acele diagnostice prin constructori tipizați, nu prin ignores. Configurația/source-ul pluginului de la pinul instalat au fost inspectate.

## Baseline real înainte de integrare

- Ruff: exit 1; importuri neordonate, importuri nefolosite, fixtures importate și apoi mascate de parametrii pytest, plus excepție ridicată fără chain explicit.
- mypy strict: inițial **250 erori / 35 fișiere**; cu pluginul Pydantic corect **239 erori / 35 fișiere**. Majoritatea sunt adnotări/call-uri netipizate; există și valori DB dinamice returnate drept tipuri concrete, opționale în lifecycle și rezultate `BaseException` tratate insuficient în teste.
- Controalele scratch au executat uneltele reale: valid exit 0; Ruff `F821`, formatter `unformatted` și mypy `return-value` au dat exit 1 cu diagnosticul așteptat. Aceste controale au fost ulterior integrate în testele aplicației.
- Verificarea automată de threat intelligence a instalării a expirat parțial; nu este verdict de securitate. Auditul ulterior al grafului final locked a trecut; nu confundăm cele două rezultate.

## Verificare și rollback

**Rezultat integrat la `4c5a645`:** pinurile sunt numai în grupul dev, cu lock regenerat; dependențele runtime și versiunile lor existente nu au fost schimbate. `make lint-api` verifică lint și format fără autofix; `make typecheck-api` rulează mypy strict. Ambele intră în `make check-api`/`make check` și în workflow-ul CI, fără instalare la verificare. Toate cele **41 de fișiere** API și teste trec, fără casts, `Any` explicit, ignore global sau excluderi de surse. Protocolul ASGI folosește tipurile oficiale ale frameworkului; acestea nu sunt o promisiune că orice tip din librăriile terțe este lipsit de `Any`.

**Controale ale gate-ului:** 12 cazuri în `test_python_quality.py` verifică pinurile dev-only, sursa importată, valid/invalid pentru lint/format/tipuri și propagarea reală prin Make. Verificarea ar fi falsă dacă o dependență lipsă sau orice exit nenul ar ține locul diagnosticului; controalele cer exact fișier/cod/severitate în JSON. Check mode nu modifică fixture-urile. `API_CHECK_PATHS` are implicit ambele directoare; override-ul explicit este folosit numai pentru controalele cu fișiere temporare, nu de CI.

**Regresii după integrare:** 128 teste API/control/tooling și 10 de migrare/livrare au trecut pe PostgreSQL 18.6 deținut. Auditul locked OSV al celor 37 de pachete nu a raportat advisories/status advers cunoscut. 28 teste documentare, 11 development, 4 controale Oxlint și wheelul instalat au trecut în gate-ul complet. Auditul nu este garanție exhaustivă de securitate.

**Reproducere curată:** worktree detached din HEAD local `4c5a645`, venv API nou prin `uv sync --locked --no-config`, venv documentar nou cu `Markdown==3.10.2`, Node 24.21.0/npm 11.19.0 și `npm ci --include=dev --ignore-scripts` pentru unealta existentă. `make -C <worktree-curat> check UV=<uv-0.12.19>` a trecut integral, inclusiv 128+10 și gate-urile statice. Proiect test `omnis-p01-p02-9e30636958d3e3c3`, apoi cleanup verificat fără ștergerea volumului. Nu este rulare remote GitHub.

## Remedieri și încercări relevante

- `aaf3039`: formatare mecanică izolată; 22 fișiere schimbate, AST identic înainte/după pentru toate cele 36 de fișiere existente atunci. Nu am amestecat logica cu formatterul.
- `fa6616a`: fixture IPC mutată în conftest; importurile mascate de parametrii pytest nu au fost șterse orbește sau ignorate. `fd84b83` separă explicit eroarea de schemă de timeoutul normal al buclei.
- `2441801`: un challenge cu digest și expiry NULL producea TypeError; RED PostgreSQL, apoi refuz fără sesiune și cu încercarea contabilizată.
- `05405f5`: rezultate SQL validate în recorduri/scalari stricți, nu casturi. Prima integrare a refuzat `RowMapping`; diagnosticul a identificat cerința Pydantic strict pentru dict concret. Se normalizează numai containerul Mapping, nu valorile; controalele resping coercițiile și păstrează erorile DB sanitizate.
- `136e61b`/`c18dedb`: tipizare producție și teste, inclusiv lifecycle parțial inițializat. Au fost păstrate programatic toate cele 222 de aserțiuni inițiale din fișierele de test delegate. Decoderul tipizat păstrează câmpurile necunoscute, ca să nu ascundă eventuale scurgeri de date.
- `f54082d`: o rulare a importat alt worktree prin PYTHONPATH și a eșuat pe modulul nou absent. Controlul de ownership a reprodus cauza; comenzile izolează Python și elimină căile/opțiunile pytest ambientale. Suita completă a trecut inclusiv cu `PYTEST_ADDOPTS=-k test_live` injectat; nu acceptăm un subset accidental drept gate complet.
- `2b341b8`: `return` din cleanup putea înghiți anularea când și închiderea peer-ului eșua. RED pe socket real, apoi propagare păstrată, fără schimbarea autorității DB.
- `9204108`: auditul de prerechizite a reprodus 422 `ErrorEnvelope` versus `HTTPValidationError` în OpenAPI. Răspunsurile declarate reflectă acum payloadurile reale; health503 păstrează `HealthReady`. Exportul și tipurile TS rămân P0.3.

**Review-uri finale independente:** nu au identificat blocante în perimetrul revizuit `6c40083..4c5a645`. Review-ul de producție a executat 8 teste noDB, 5 probe suplimentare și lint/typecheck pe toate cele 24 de surse; proba challengeului cu driver substituit nu a fost prezentată drept commit PostgreSQL. Review-ul de toolchain a confirmat enumerarea efectivă 41/41, cele 12 controale de gate, cele 5 controale de decoder, păstrarea celor 222 de aserțiuni și legarea CI fără mascare de erori. PostgreSQL/wheel/checkoutul curat au fost exercitate de părinte, nu atribuite reviewerilor.

Auditul prerechizitelor separă explicit lucrul viitor: export OpenAPI/tipuri TS/build/pairing vizual în P0.3; launcher/manifest/topologie/UID și probele complete ale instalării în P0.4. Nu există un blocker cunoscut rămas în această felie care să împiedice începutul local P0.3. Aceasta nu este închiderea G00 și nu garantează absența oricărui defect nedescoperit.

`uv` global din PATH rămâne 0.11.7 și este refuzat corect de gate; verificările de acceptare au transmis explicit executabilul uv 0.12.19. Nu am făcut upgrade implicit al uneltelor personale. Pentru un mediu nou se urmează setup-ul cu pinul cerut, nu se dezactivează verificarea versiunii.

Acceptarea cere gate-uri reale fără erori, controale negative valide, lock/audit, suită completă existentă plus regresiile noi, artifact instalat și review. CI remote rămâne NOT-RUN fără push cerut separat; rulează aceleași comenzi versionate, dar nu inventăm o execuție GitHub.

Experimentele și venv-ul candidat trăiesc în scratch. Mediul API a primit numai uneltele de dezvoltare fixate; mediul Hermes rămâne neatins. Revert pe commiturile relevante și `uv sync --locked --group dev --directory api` din revizia restaurată pentru mediul de dezvoltare; nu este nevoie de migrare de date doar pentru lint/typing. Dacă o remediere schimbă schema/comportamentul, va avea contract și rollback propriu. Probele DB folosesc numai proiecte/volume test atestate; cleanup fără ștergerea volumelor.
