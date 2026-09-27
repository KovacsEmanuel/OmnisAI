# P0.2 — închiderea restanței de calitate Python înainte de P0.3

**Stare: ÎN LUCRU.** Bază curată `6c40083184fd89698518a25877c1dc7757407465`. Utilizatorul a cerut remedierea restanțelor necesare următoarei faze. Acesta este contractul feliei B01a pentru codul deja introdus, nu un plan nou și nu pornirea P0.3/P0.4.

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

Surse: [Ruff exact PyPI](https://pypi.org/pypi/ruff/0.16.9/json), [mypy exact PyPI](https://pypi.org/pypi/mypy/2.3.1/json), [config Ruff](https://docs.astral.sh/ruff/configuration/), [config mypy](https://mypy.readthedocs.io/en/stable/config_file.html). Pinurile au fost confirmate și prin `--version` pe Python 3.13.15; nu folosim instalare `latest`. Regulile Ruff propuse sunt E4/E7/E9/F/I/B și formatterul stabil, fără preview sau unsafe fixes. Lungime 100, Python 3.13.

Pluginul oficial `pydantic.mypy`, din Pydantic deja fixat, este necesar cu `init_typed=true` și `init_forbid_extra=true`: fără el, metodele sintetizate pentru modele produc 11 diagnostice `explicit-any`. Nu am dezactivat verificarea `Any`; proba cu plugin a eliminat acele diagnostice prin constructori tipizați, nu prin ignores. Configurația/source-ul pluginului de la pinul instalat au fost inspectate.

## Baseline real, încă necorectat

- Ruff: exit 1; importuri neordonate, importuri nefolosite, fixtures importate și apoi mascate de parametrii pytest, plus excepție ridicată fără chain explicit.
- mypy strict: inițial **250 erori / 35 fișiere**; cu pluginul Pydantic corect **239 erori / 35 fișiere**. Majoritatea sunt adnotări/call-uri netipizate; există și valori DB dinamice returnate drept tipuri concrete, opționale în lifecycle și rezultate `BaseException` tratate insuficient în teste.
- Controalele scratch au executat uneltele reale: valid exit 0; Ruff `F821`, formatter `unformatted` și mypy `return-value` au dat exit 1 cu diagnosticul așteptat. Nu sunt încă gate-ul integrat al aplicației.
- Verificarea automată de threat intelligence a instalării a expirat parțial; nu este verdict de securitate. Auditul grafului final locked este obligatoriu înainte de acceptare.

## Verificare și rollback

**Adoptarea uneltelor:** pinurile sunt acum numai în grupul dev, cu lock regenerat. `uv sync --locked` și auditul OSV al celor 37 de pachete au trecut fără advisories/status advers cunoscut. Cele 7 controale versionate din `api/tests/test_python_quality.py` au eșuat înainte de integrare și trec după instalare/configurare; propriul fișier trece Ruff și mypy. Acest checkpoint nu pretinde încă aplicația fără diagnostice: normalizarea, tipizarea tuturor surselor/testelor și legarea gate-urilor rămân următoarea parte a aceleiași felii.

Acceptarea cere gate-uri reale fără erori, controale negative valide, lock/audit, suită completă existentă plus regresiile noi, artifact instalat și review. CI remote rămâne NOT-RUN fără push cerut separat; rulează aceleași comenzi versionate, dar nu inventăm o execuție GitHub.

Experimentele și venv-ul candidat trăiesc în scratch. Mediul API va primi numai uneltele de dezvoltare fixate; mediul Hermes rămâne neatins. Revert pe commiturile relevante și `uv sync --locked --group dev --directory api` din revizia restaurată pentru mediul de dezvoltare; nu este nevoie de migrare de date doar pentru lint/typing. Dacă o remediere schimbă schema/comportamentul, va avea contract și rollback propriu. Probele DB folosesc numai proiecte/volume test atestate; cleanup fără ștergerea volumelor.
