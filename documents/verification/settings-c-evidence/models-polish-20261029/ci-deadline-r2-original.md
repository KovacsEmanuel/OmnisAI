# R2 — calibrare deadline canonical / Make→parser

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: niciunul în delta alocată.**

- Bază: `fab149c40c2702ca992d47933ce247c2eb2d5ba2`.
- FREEZE și checkout verificat: `d54e3522da85d5f3d9573075d9538774c07bd5ef`.
- Scope primar: `Makefile:19–24`, `tests/development/test_test_db_gate.py:48–89`; complementar R1, nu o a doua acceptare a comportamentului RecorderClaim.
- Cele trei căi schimbate față de bază sunt exact Makefile și cele două teste development declarate. Identitatea autor→integrare este egală pentru fixture `7a493d4→c55e7a7`, respectiv deadline `4e47cee→d54e352`, prin `git diff --quiet` scoped, exit0.

## Cerință → cod → dovadă

1. **Calibrare măsurată, nu relaxarea testelor.** Am citit `openapi-final-verification/result.json` și logul original `passed-fixture/gate.log` din `/home/kali/.local/share/omnis-t1-artifacts/postreboot-20261031/`. SHA256 log recalculat: `2786065d8473c2a43c9b041f3c766bacae2effdd293aa2acd06943d73f047ced`, egal manifestului. Cele 11 rezumate cu durate există literal în log. Suma Decimal, inclusiv docs/development, este **3729.458s**, cu **129.458s peste implicitul3600**, înaintea etapelor fără durate incluse. `4800 + 600 = 5400`; marja față de componentele măsurate este1070.542s, nu un timp de execuție garantat. PASS-ul istoric a folosit4660s explicit; nu pretind că a folosit noul Make sau că4800 produce deja un nou runtime PASS.
2. **Același gate integral.** Compararea byte-exact demonstrează că singura schimbare Make este sufixul `--timeout-seconds 4800` la rețeta existentă `$(API_PY) -I ops/run_test_db_gate.py --check --uv "$(UV)"`. `test: check`, lista completă `check-components`, selecțiile, assertions, timeouturile individuale și guardurile Make rămân neschimbate. Nici opțiune/config/framework nou, nici subset, skip sau limită de test relaxată.
3. **Caller real, parser real, owner fără efecte.** Testul nou copiază Makefile-ul real într-un director gol propriu și execută Make real, fără dry-run sau ignore-errors. Numai `API_PY` este substituit cu printf inert; mediul copilului conține doar PATH. Aserțiunea compară argv exact, apoi argv-ul capturat intră în `main()` al runnerului real; numai `prove_private_fixture` și înregistrarea semnalelor sunt substituite. Rezultatul cerut este `('check-components', '/pinned/uv', 4800)`. Nu există provision/PG/native/browser/model/target pe acest traseu de probă.
4. **Bounds/default/ownership păstrate.** Runnerul rămâne byte-identic. `ops/run_test_db_gate.py:1068,1097–1104` păstrează default3600 și intervalul1..7200. Controlul independent a acceptat default/1/4800/7200 și a refuzat0/7201/-1/non-int cu exit2, fără apel al stubului la refuz. Traseul nemodificat `prove_private_fixture→run_gate→_run_owned_gate` propagă deadline-ul; ownerul exclusiv, Stop, timeout124, verificarea `family_drained`, retenția DB sub incertitudine și cleanupul numai după drain rămân intacte (`684–818,981–1017`). Rezerva600s este bugetul declarat, nu un nou mecanism de enforcement introdus de patch.

## Verificări efectuate

- `env -i PATH=/usr/bin:/bin HOME=/home/kali/.hermes/cache/scratch/ci-fix-r2/h TMPDIR=/home/kali/.hermes/cache/scratch/ci-fix-r2/t /home/kali/OmnisAI/api/.venv/bin/python -I -B -m unittest discover -s tests/development -p test_test_db_gate.py -k test_full_make_check_forwards_measured_family_deadline -v`: **1PASS/0.033s/exit0**, output original `deadline-source.log`.
- Parser real cu owner inert, Python3.13.15: **8 controale/exit0**, `parser-bounds.json`. Execuție inline, fără helper nou.
- RED/GREEN originale ale autorului citite: `cf-iNx5dS/deadline-red.log` refuză exact absența opțiunii; `deadline-green.log` are1PASS. Nu le-am rescris.
- Identități, suma din log și comparația Ruff: `measurement-verified.json`, exit0. Cele **6 B023** au aceleași coduri/mesaje/coloane, doar deplasare+43 linii; nu sunt introduse de delta și nu au fost suprimate sau reparate oportunist.
- `git diff --check` pe FREEZE și worktree: exit0. `ops/`, `.github/` și recorderul istoric sunt neschimbate față de bază. HEAD a rămas FREEZE; fără modificări tracked/staged. Cele două fișiere untracked protejate au fost doar observate în status, niciodată deschise/hashedate.

## Identități ale sursei

| Cale | SHA256 la FREEZE |
|---|---|
| Makefile | `6cfc6a65056165c2ff679d1a86f18cfb9c5bec060bff1e73bdbe479abe4c795e` |
| tests/development/test_test_db_gate.py | `dc86b8902afd1cb173bcbcb52b3a16c431c9dfc6807c64c854ebae8b00ee1a7b` |
| tests/development/test_p02_recorder_claim.py | `2e6de19e2582df2deae1d243460299e546f5dba71635da56bde47315150c087e` |
| ops/run_test_db_gate.py | `625688d912faffa08a07970b81b6e254d35f2a5aa1b57c3d3fce87b29ba298aa` |
| documents/verification/p2-integration-p02-recorder.py | `b5f4f98ecd276d05641305418a351a607a98057ec3770f4433f35cf1a89fe30a` |

## Limite / incidente ale reviewului

Trei încercări preliminare de agregare read-only au eșuat înainte de rezultat: comparație brută a rezumatelor ANSI, lookup al unei căi de helper ghicite/inexistente, apoi excluderea eronată de către reviewer a docs/development din sumă. Proba finală folosește toate cele11 durate literale și identități existente; nicio sursă ori dovadă originală nu a fost modificată. Fișierele intermediare goale rămân în scratch; nu constituie PASS.

Fișiere create numai în `/home/kali/.hermes/cache/scratch/ci-fix-r2/`: acest raport, logul SOURCE, JSON parser/measurement și ieșirile intermediare. Nu am editat repo, comis, împins sau modificat starea operatorului. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

**Neexecutat:** full gate/PG/native/browser/provider/target, CI remote, rereview complet fixture și rerulări largi. Calibrarea nu explică cele trei erori rapide RecorderClaim; acestea sunt remediul separat al fixture-ului. Reviewul aprobă numai delta SOURCE; părintele adjudecă, integrează/push și verifică CI remote pe SHA-ul exact. Un runner mai lent poate în continuare depăși4800s; acest review nu transformă istoricul local sau testul inert în acceptare remote.
