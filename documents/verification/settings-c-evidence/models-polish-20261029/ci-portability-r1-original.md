# R1 — APPROVED_SCOPED

## Snapshot și limită
- Bază: `fab149c40c2702ca992d47933ce247c2eb2d5ba2`.
- FREEZE: `d54e3522da85d5f3d9573075d9538774c07bd5ef`.
- Scope aprobat: repararea portabilității fixture-ului în `tests/development/test_p02_recorder_claim.py`, împreună cu păstrarea controalelor SOURCE existente. Nicio constatare concretă blocantă.
- Delta totală conține exact trei căi: testul recorderului, `Makefile`, `tests/development/test_test_db_gate.py`. Ultimele două au fost citite în diff pentru separarea scope-ului; deadline/parser/buget aparțin R2, nu acestei aprobări.
- CURRENT rămâne T1 închis scoped/T2 neînceput. Nu există aprobare de integrare proprie, CI global verde sau reactivare P02.

## Constatări verificate
| Criteriu | Cod | Dovadă și concluzie |
|---|---|---|
| Fixture independent de checkoutul istoric | test:27–45 | REPO este legat de directorul temporar propriu; sursa este copiată byte-exact, iar manifestul folosește digestul SHA-256 real al copiei. Testele au trecut dintr-un snapshot scratch, distinct de `/home/kali/OmnisAI`. |
| Hash real, fără înlocuirea verificării | test:37–60,110–115; recorder:112–142 | Manifest/artifact/source folosesc funcția SHA reală; tamper-ul sursei produce `P02 source changed` înainte de claim, fără owner sau marker. |
| One-shot, concurență, write failure păstrate | test:97–101,117–164; recorder:143–159 | Cele trei metode originale sunt AST-identice cu baza. Main execută în continuare claim-ul real `O_EXCL|O_NOFOLLOW`, flush/fsync și persistența reală în fixture. Rezultatul pozitiv, replay-ul, cei doi readeri READY și nerearmarea după eroarea de registry trec. |
| Regresie foreign-root fiabilă chiar când sursa există local | test:81–95,103–108 | Guardul este instalat în setup pentru toate cazurile și refuză `Path.read_bytes` înaintea citirii în afara fixture-ului. Controlul negativ din candidat trece. O substituție exclusiv în memorie, după setup sigur, care restabilește REPO la rădăcina istorică existentă produce exact 2 errors + 1 failure în cele trei cazuri originale; zero owner calls și zero markere în toate trei. |
| Istoric/produs/grants nemodificate | diff complet; recorder | Recorderul are același blob Git la bază și FREEZE: `4b28e997283143ed1bc47695c22e2dc39eddda7e`. Nicio schimbare de produs/runtime/grants în delta. `require_grant`, signal și ownerul rămân doubles SOURCE; ownerul no-effect păstrează așteptarea `(TARGET, 900)`. |

Guardul de citire este un control de regresie al testului, nu o nouă promisiune de sandbox pentru runtime.

## Execuție independentă
Comandă wrapper stdlib, Python fixat 3.13.15:

`api/.venv/bin/python -I -B /home/kali/.hermes/cache/scratch/r1-lxOh4n/verify.py`

Comanda efectivă de test, cu TMPDIR propriu `/home/kali/.hermes/cache/scratch/r1-lxOh4n/tmp`:

`/home/kali/OmnisAI/api/.venv/bin/python -I -B -m unittest discover -s /home/kali/.hermes/cache/scratch/r1-lxOh4n/snapshot/tests/development -p test_p02_recorder_claim.py -v`

- Candidat exact: **5 teste PASS, exit 0**; `green.log`.
- Control deliberat wrong-root: **3 teste, 2 errors + 1 failure**, toate cele trei cu `owner_calls=[]` și `consumed=false`; `wrong-root.log`, `verification.json`. Wrapperul validează acest RED așteptat și se încheie cu exit 0; nu îl prezintă drept suită verde.
- Comparare AST a celor trei metode originale: identice.
- `git diff --check BASE FREEZE`: exit 0.
- Readback Git: HEAD FREEZE, fără diff tracked/staged; numai cele două fișiere untracked preexistente protejate. Conținutul lor nu a fost citit sau modificat.
- Cleanup: directorul TMPDIR propriu verificat gol. Snapshotul și probele proprii se păstrează în directorul acestui raport.
- Dovezile autorului `cf-iNx5dS/recorder-red.log` și `recorder-green.log` au fost citite, separat de execuția independentă de mai sus.

## SHA-256 ale scope-ului
- `tests/development/test_p02_recorder_claim.py`: `2e6de19e2582df2deae1d243460299e546f5dba71635da56bde47315150c087e`
- `documents/verification/p2-integration-p02-recorder.py`: `b5f4f98ecd276d05641305418a351a607a98057ec3770f4433f35cf1a89fe30a`
- `Makefile`: `6cfc6a65056165c2ff679d1a86f18cfb9c5bec060bff1e73bdbe479abe4c795e`
- `tests/development/test_test_db_gate.py`: `dc86b8902afd1cb173bcbcb52b3a16c431c9dfc6807c64c854ebae8b00ee1a7b`

## Fișiere și limite
Nicio editare de repo, commit, push, configurație, date operator sau resurse runtime. Numai probe/raport/snapshot în scratch-ul propriu. Nicio remediere cerută și nicio problemă de execuție blocantă.

Neexecutat: full canonical/CI remote, native/PG/browser/provider/target; deadline-ul separat rămâne în scope R2. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
Risc rezidual: acestea sunt teste SOURCE cu owner no-effect și grant mock, nu validare de runtime sau CI global; acceptarea finală și rerularea CI aparțin părintelui.
