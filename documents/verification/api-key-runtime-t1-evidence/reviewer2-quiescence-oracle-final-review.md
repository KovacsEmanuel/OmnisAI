# R2 — re-review exclusiv al oracle-ului de fază

**APPROVED_ORACLE_SOURCE_SCOPED. Findings concrete: `[]`.** Limita de atribuire din raportul R2 anterior este rezolvată la nivel SOURCE. Nu este acceptare T1, aprobare de integrare sau PASS PostgreSQL independent.

Cerință → consumer → risc → decizie: oracle-ul expirării după precheck-ul tranzacției a doua → regresia existentă `test_quiesce_owner_expiry_during_update_lock_wait_rolls_back` → un refuz înainte de UPDATE confundat cu rollback post-UPDATE → remediul minimal este aprobat pentru următoarea probă PG independentă a părintelui.

## Snapshot exact, verificat read-only

- Checkout: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/runtime-src`.
- Bază: `1dce3cd38a4555be221826c43bc2f22e6a830c17`.
- HEAD: `b25e7992ddf83c832db9a574c5505948d7a34950`; tree: `aec4329dc61573ad5c7e5a2a11b237bb4ffa99be`.
- Branch: `impl/api-key-runtime-t1-model`; working tree și index curate la început și la verificarea finală, inclusiv inventarul untracked.
- Delta completă: numai `api/tests/test_control_regressions.py`, **+5/-1**.
- Blob nou, identic pe disc și în HEAD: `74f6932ddfceb9d329aae6c5f81d77eaa0de2cad`; SHA256 fișier: `bacdbaffa51e7cf9fc32412ddfa88e3153bdd5b19f20c8f80820526da250ce79`.
- SHA256 `git diff --binary 1dce3cd38a4555be221826c43bc2f22e6a830c17 b25e7992ddf83c832db9a574c5505948d7a34950`: `fea5a56a4cc53a91a13fb47e2d5162df290bffbff48f69e0d2ba37284251c9d9`.

Aprobările SOURCE anterioare R1/R2 din `reviewer{1,2}-quiescence-unlocked-review.md` sunt reutilizate explicit, numai în scope-ul lor, pentru cele patru bloburi neschimbate. Am verificat identitatea bază = HEAD = fișier pe disc:

| Fișier | Blob neschimbat |
|---|---|
| `Makefile` | `cdd1803fa674695ea4da2946ce02994b2a7d1832` |
| `api/src/omnis/modules/instance/service.py` | `df0d3b4437d13fc800cef32d730011ff622f608f` |
| `api/tests/test_instance.py` | `9ff7a9239869645432c798b899d27c1becc5ec27` |
| `ops/run_test_db_gate.py` | `f13121588fddfbc13449bc10bbabac07c766dca9` |

## Dispoziția limitei R2 anterioare

- `api/tests/test_control_regressions.py:227–230`: acquire/open/shutdown se încheie **înainte** de instalarea monkeypatch-ului pe această instanță de serviciu. Verificările setup-ului nu pot consuma contorul.
- `:212,219–224`: contorul avansează numai după întoarcerea cu succes din `original(...)` **și** executarea cu succes a `SET LOCAL statement_timeout = 10000`. Prima verificare reușită nu semnalizează; numai valoarea exactă `2` setează evenimentul.
- Ordinea necesară din `service.py:489–517` este explicită: primul `_require_owner` la `:491`, ieșire din prima tranzacție, apoi al doilea `_require_owner` la `:506`, validări sincrone de generation/shutdown și UPDATE la `:510–515`; a treia verificare este după UPDATE, la `:517`. `_locked:270–295` nu adaugă alte apeluri `_require_owner`. Prin urmare, al doilea apel reușit observat aparține fazei a doua, înainte de UPDATE.
- Un refuz de owner/expiry la precheck-ul fazei a doua nu mai poate satisface oracle-ul: contorul rămâne `1`, evenimentul nu se setează, iar așteptarea bounded a testului eșuează. Acesta închide exact scenariul de atribuire prematură descris anterior, fără a pretinde că fusese un defect de produs reprodus.
- SHARE blocker-ul este deja luat înaintea taskului (`test_control_regressions.py:231–234`); expirarea rămâne citită cu `clock_timestamp()` în DB (`:236–250`). Refuzul `ControlConflict`/`LEASE_LOST`, așteptarea bounded și readback-ul `quiesced_generation is None` rămân la `:252–254`. SET LOCAL, cleanup/cancel și rollback-ul tranzacțional din produs sunt neschimbate.

Evenimentul confirmă faza de pre-UPDATE, nu o măsurătoare directă din `pg_stat_activity`. Această distincție nu păstrează vechea ambiguitate între cele două tranzacții. Nu am executat mutation testing și nu afirm un rezultat de acest tip.

## Dovezi citite, fără rerulare

- Original `core-oracle-tmp/db-4a0b1d76f3d94b89/gate.log`: selecția exactă existentă `api/tests/test_instance.py` plus regresia numită, **10 passed in 26.70s**. `gate.log.result.json`: `code=0`, `family_drained=true`. Este execuția autorului, nu QA independentă a reviewerului.
- `core-evidence/oracle-quality.log`: comenzi reale și rezultate pentru Ruff check, Ruff format --check, mypy --no-incremental pe fișierul schimbat și `git diff --check`; fiecare exit0. Citite, nu rerulate de mine.
- `core-evidence/oracle-cleanup-freeze.log`: cleanup-ul propriu este dovadă reținută a autorului, nu census live al reviewerului. Starea `M` din acel log precedă commitul; verificările Git actuale de mai sus confirmă freeze-ul curat, fără contradicție.
- Comenzi proprii read-only: `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, `git rev-parse`, delta raw/numstat/binary, `git hash-object`, SHA256 și comparația programatică a celor cinci fișiere: exit0, `EXACT_ORACLE_FREEZE_OK`. `git diff --check <bază> <HEAD>`: exit0. Snapshotul final este neschimbat.

## Predare și limite

Singurul fișier creat este acest raport original; niciun fișier de produs/test/config, metadata Git sau skill nu a fost modificat; niciun commit. Nicio problemă de execuție întâlnită. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Omise intenționat: PG/teste/mutation, harness nou și re-auditul produsului/callerilor neschimbați; zero operații OCI/servicii/provider, citiri de chei/env sau efecte pe rădăcini QA/profiluri/HTML protejat.
Risc rămas: aprobarea este exclusiv SOURCE pentru acest oracle; părintele trebuie să execute primul consumer PG independent pe bytes curenți înainte de integrare. T1 rămâne neacceptat prin acest raport.
