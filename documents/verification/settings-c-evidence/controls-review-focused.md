# Re-review focalizat QA overlay — APPROVED_SOURCE_SCOPED

**Verdict: APPROVED_SOURCE_SCOPED.** Cele două findings originale sunt închise SOURCE-only pe `fdfc79ac54d22ded656aaa801ba44f8d73f67815`. Niciun blocker identificat în cele cinci editări. Verdictul admite, din perspectiva acestor două remedii, **o singură călătorie reală remaining-controls**, pe targetul existent `test-settings-models-ui-pg`; părintele păstrează condiția separată ca procesul canonical2 să se fi încheiat înaintea lansării. Nu este live PASS, aprobare globală sau închidere Settings C.

## Identitate și limită

- Worktree: `/home/kali/.hermes/cache/scratch/settings-controls-d37b4a54`, branch `qa/settings-controls-d37b4a54`; HEAD verificat exact.
- Snapshot original: `a369430beea8e25b358f118243ef4326767fb983`; produs/main de bază: `37baf0c421b3d10f6e47adc2d0df7fb75c8ea172`.
- `api/tests/test_model_test_v2.py` SHA256: `db913fbb80423526fde3a91c0f8c585fb0c4077515912c54c7516ddd221da86f`.
- `web/tests/e2e/settings-models.mjs` SHA256: `5b2ea2bd93ecafacf270259cf4cef9466e71a98c36e462f4e9cfc0566297ffd6`.
- Delta `git diff --binary a369430beea8e25b358f118243ef4326767fb983 fdfc79ac54d22ded656aaa801ba44f8d73f67815` SHA256: `67962cb4c4d7e8af10199c89b5cd8a2fb782bb3b10a5f7580475340f2f74b951`.
- Raport original păstrat nemodificat: `/home/kali/.hermes/cache/scratch/settings-controls-a369430-focused-review.md`, SHA256 verificat `5db497a63efe1327169a7f3d5d1de5ebef9f17e7bc05c286e279ea22a946f1d6`.

## Dispoziția celor două findings originale

1. **Provider exact-label — CLOSED_SOURCE_SCOPED.** La `web/tests/e2e/settings-models.mjs:109,110,112,114`, toate cele patru `getByLabel('Provider', { exact: true })` au devenit exact `getByRole('combobox', { name: 'Provider', exact: true })`. Numele și rolul nativ corespund remediului din raportul original. Reconstrucția programatică prin numai aceste patru substituții produce întregul fișier final byte-exact, fără alte modificări. Dovada selector-engine din raportul original și reproducerea offline Chromium/Node24 comunicată de părinte rămân dovezi distincte, nu o nouă execuție a reviewerului.
2. **Shared command-store total — CLOSED_SOURCE_SCOPED.** La `api/tests/test_model_test_v2.py:656-658`, SQL rămâne nefiltrat `SELECT count(*) FROM model_command_v2`, iar egalitatea exactă este acum `== 8`, nu lower bound și nu filtrare pe operație. Cele cinci Refresh catalog + un Cancel catalog + un Start entry + un Cancel entry dau 8; aritmetica a fost executată. Producerul comun și `operation_id=NULL` pentru catalog sunt stabilite în findingul original și readbackul părintelui, fără re-auditarea producerilor. O singură substituție `2` → `8` pe această expresie reconstruiește întregul fișier final byte-exact.

## Dovezi efectiv executate

- Citire raport original, Git status/HEAD/delta și contextul procedural aplicabil.
- Verificare programatică a celor două SHA de fișier, SHA delta, SHA raport original, egalității fișiere worktree/blob și reconstrucției exclusive a celor cinci editări: `IDENTITY_AND_EXACT_DELTA_PASS`, exit0.
- Census Git: exact cele două fișiere QA de mai sus diferă atât original→final, cât și produs/main→final. Nicio schimbare de produs, runner, config sau schemă; indexul și fișierele tracked sunt curate. Symlinkul preexistent neversionat `api/.venv` a rămas neatins.
- `git diff --check a369430beea8e25b358f118243ef4326767fb983 fdfc79ac54d22ded656aaa801ba44f8d73f67815`: exit0.
- `git diff --check 37baf0c421b3d10f6e47adc2d0df7fb75c8ea172 fdfc79ac54d22ded656aaa801ba44f8d73f67815`: exit0.
- Prima comandă de verificare a identității a eșuat la quoting shell înaintea execuției Python, exit2; reluată cu quoting standard `shell_quote`, exit0. Nu este eșec de produs și nu a produs efecte externe.

## Scope neschimbat și limite

Restul celor două fișiere este byte-exact față de snapshotul original după eliminarea celor cinci substituții. Prin urmare, calificarea SOURCE din secțiunea «Other reviewed boundaries» a raportului original rămâne moștenită numai în scope-ul ei: JSON response-loss/recovery fără resend, bariere native, keys/actions, census I/O, security, deadline-uri, restart și cleanup. Acestea **nu au fost re-auditate sau certificate runtime din nou**. Dovezile originale de produs/main rămân la reviziile și limitele lor.

Nu am pornit/polled canonical2, PG, API, browser journey, rețea, provider sau spending; fără instalări, agenți, credențiale, staging/commit ori modificări de produs. Nu am citit fișierele protejate sau fixture-uri/traces private. Ruff/format și `node --check` comunicate de părinte nu au fost rerulate; nici mypy/full SOURCE/build. Reticle: NOT_RUN/source-only; Chisel: BLOCKED_NO_GO.

**Rămâne la părinte:** adjudecarea/integritatea integrării și singura QA reală admisă pe runnerul/fixture-ul existent, după încheierea canonicalului; fără harness/owner nou sau extindere de scope. Risc rămas: comportamentul live al remaining-controls nu este încă demonstrat de acest review.
