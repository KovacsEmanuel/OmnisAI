# R1 — current-reader SOURCE root fix

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: niciunul.** Nu este aprobare de integrare, calificare nativă sau CI green.

## Snapshot și scope

- Repo: `/home/kali/OmnisAI`.
- Bază: `34aebfbee5073186cde1724089e2bf5fe56818e0`.
- Freeze verificat înainte și după probă: `0cba4760eb4495fceaf29846843d18c1a41fe6b8`.
- Unicul fișier schimbat: `api/tests/test_contract_method_pg.py`, 19+/7-.
- Blob freeze = blob autor `461f9904f2d7fba6cc8486bea7d52670e24b57b1`: `ab5f129371162af6c27a118314dbf0c09fae02c0`.
- SHA256 fișier: `e79f9d136bb051e57a203a844d04d91cbd8f7db3cc103022b28175e8e6b3c4a6`.
- Cerință → consumer → risc → decizie: portabilitatea fixture-ului finit SOURCE → `batch2_current_reader` → refuz pozitiv prematur sau negativ verde înaintea inventarului → aprobarea numai a acestei remedieri.
- R1 acoperă fluxul efectiv pozitiv/refuz, limitele, inventarul și stale/no-origin. Inventarul complet de calleri/literali/native authority rămâne scope R2.

## Dovezi independente

Preflight fără efecte: Python `3.13.15`, pytest `9.1.1`, mediul fixat `api/.venv/bin/python`; collect-only exact 25 cazuri, fără marker legacy_native sau fixtures DB. Importul runtime-ului nativ, subprocess, connect/bind și os.system au guard de refuz; nicio tentativă observată. Plugin-ul observă funcțiile reale fără să înlocuiască readerul/inventarul. Singura simulare suplimentară este containment=false pentru rădăcina istorică fixă, pentru topologia foreign. Originea procesului rămâne double-ul existent al testului, nu import instalat real.

Comenzi, din repo (ambele exit0):

```sh
S=/home/kali/.hermes/cache/scratch/h4r1-VCIXgJ
env -i PATH=/usr/bin:/bin HOME="$S" TMPDIR="$S" LANG=C.UTF-8 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/kali/OmnisAI/api/.venv/bin/python -I -B "$S/review_probe.py" collect
env -i PATH=/usr/bin:/bin HOME="$S" TMPDIR="$S" LANG=C.UTF-8 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/kali/OmnisAI/api/.venv/bin/python -I -B "$S/review_probe.py" foreign
```

`pytest.main` folosește `-c api/pyproject.toml -p pytest_asyncio.plugin -p no:cacheprovider -q --tb=short` și numai cele trei funcții numite în probe. Rezultat: **25 PASS în 1.63s**, 25 cazuri distincte, nu adunate cu probele autorului.

- `None`, `wheel-max` și `aggregate-max`: readerul returnează exact `current`, inventarul real este apelat o dată, origin double o dată (`7468–7470`, `7887`, `7945`).
- Wheel 327680 acceptat; 327681 refuzat prin cititorul bounded la `7845`. Aggregate 1179648 acceptat; 1179649 refuzat la `7875`. Ambele negative au zero origin calls.
- `outside-root`: refuzul primar este `ValueError` la `7822`, înainte de inventar/origin, apoi exact `BATCH2_CURRENT_READER_REFUSED`.
- Cele 21 cazuri de refuz ajung la aserțiunea exactă și au zero origin calls. Mutațiile bytes/inventar/descriptor/ZIP nu au fost înlocuite cu un refuz generic de root.
- Stale sintetic: inventarul real și wrapperul lui sunt apelate o dată; apoi comparația inventarului checkoutului curent refuză la `7895`, zero origin calls. Stale-byte separat refuză la `7906`.
- Guardul default trece după fixture-uri; rootul istoric este restaurat la final.
- Comparație AST a parametrilor: toate cele 22 valori originale și ordinea lor sunt păstrate; numai `outside-root` este adăugat, rezultând 23.

Inspecția diff-ului și a consumerului confirmă păstrarea verificărilor descriptor/pin, tip/format commit, root rezolvat, confinement al materialelor, ownership/no-follow, egalitate între cele patru inventare și bytes, interpreter/pyvenv, refuz origin și normalizare. Limitele 327680/1179648/131072/128 sunt neschimbate. Predicate-ul root folosește constanta existentă; cele două teste finite optează explicit în fixture-ul existent (`1981–1985`, `7304`, `7627`), fără environment backdoor.

Dovezi autor citite, nu rerulate: `h4e/probe.py`, `control-red-plain.log` (outside-root 1FAIL/24PASS), `control-red-foreign.log` (3 pozitive + stale prematur: 4FAIL/21PASS), `control-green-foreign.log` (25PASS), `direct-pytest.log` (25PASS) și `inventory-proof.log`. Acestea rămân dovezi distincte de execuția R1.

## Originale și limite

În același director propriu:
- `review_probe.py`: SHA256 `4357a0441c586bcdd5ddd2504c225c66338db7cfbaab2d44754eec0bd0ff5ec5`.
- `collect.json`: SHA256 `e05b0f16af859a6f5e050361f8464fdbd26dd08f99dd7095c63331c3f8465775`.
- `collect.log`: SHA256 `ec50c151bfdffc06832adf7880b7e74150dac501156d0d6b9336796ccdb4f793`.
- `foreign.json`: SHA256 `783ed322a1dcebb41b948514adc21d893443bc2357b8e0d92b69fa1d49cb512a` (trace-uri și fixtures).
- `foreign.log`: SHA256 `485c38648782d779667ece6ac9fe6233c9723ddfb781b5229cb9ffaa07ade802`.

Numai scratch propriu creat; nicio editare/stage/commit/push în repo. Tracked diff/index goale înainte și după; cele două căi untracked preexistente protejate nu au fost citite/modificate. Fixture-urile și dovezile proprii sunt păstrate în directorul raportului.

Neexecutate: full module/API, PG, native Hermes, Docker, browser, provider, retained-private descriptor și origin subprocess real. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Nu am rerulat quality gates sau restul celor 100 SOURCE ale autorului.

FAIL-ul remote `41264838263` / job `124725365821` rămâne FAIL-ul raportat în mandat, neverificat din nou aici. Acest SHA nou nu reînnoiește calificarea nativă. Părintele adjudecă R1/R2 și orice nouă execuție remote; nu se transferă acest PASS SOURCE în runtime/CI.
