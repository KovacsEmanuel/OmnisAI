# R2 — review independent SOURCE al corecției controlled_dns

**Verdict: APPROVED_SOURCE_SCOPED. Niciun blocker în delta admisă.** Părintele poate executa regresia existentă `test-model-test-v2-pg`, apoi UI2 pe fixture izolată nouă, în limita existentă de600s. Aprobarea nu este runtime PASS și nu închide QA/UI.

## Identitate exactă

- Repo `/home/kali/OmnisAI`; HEAD început/final `ceddf1be10a90fb14674b30359b20ff7db27fda1`; correction-base `732ec1561b3aefc31da8e827d86e248d753c5e44`.
- Binding full33, verificat o singură dată: `/home/kali/.hermes/cache/scratch/uif7/final33-freeze.json`, SHA-256 `95e7a1566b3ca75c0c446f31f507f334793219aeab1b9084c39c429febacf70d`; candidate `2ce7c4c1255ae9697ae3d7fbe605d7964e3d1e5d2b2dd53d27a27918fa82c71e`, base `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Recalculate independent:33/33 hashuri, sizes și blobs Git; identitatea canonică identică. Unica delta este `api/tests/test_model_test_v2.py`,16 inserții/1 ștergere, SHA-256 `41d21df9a86edc64447ed824f9670ba05dbf98754e012d947d02d0d130247487`, blob `d9d65e726316a9407d850e6db58a05cec64388cd`. Cele32 surse, manifestul build și cele4 fișiere build sunt neschimbate; fără rebuild. Metadata precommit din freeze nu este verdict.

## Verificarea focalizată

- `api/tests/test_model_test_v2.py:394–409`: semnătura standard acceptă2/4/6 argumente poziționale și kwargs reale; admite numai family0/AF_INET, type0/SOCK_STREAM, proto0/IPPROTO_TCP și flags0. Excepția locală este exclusiv scenariul `settings_ui`, host literal `127.0.0.1`, port în1–65535. Readiness furnizează portul int din listener.getsockname(), nu un hostname arbitrar.
- Lanțul real citit: `settings_models_browser` → `asyncio.to_thread(wait_api)` (`api/tests/test_web_e2e.py:263–275,315–326`) → HTTPX sync/HTTPcore `SyncBackend.connect_tcp:208` → Python3.13.15 `socket.create_connection` → `getaddrinfo(host, port, 0, SOCK_STREAM)`. Am executat expresia AST reală cu callbackul nou, fără a crea socket: PASS. AST-ul vechi reproduce TypeError pentru4argumente și AssertionError pentru loopback cu2argumente.
- Am executat și expresiile AST reale din `cli/src/omnis_cli/model_relay.py:143` și `cli/src/omnis_cli/forwarder.py:364`: `type=SOCK_STREAM, proto=IPPROTO_TCP`, fără family/flags explicite. Ambele păstrează mappingul exact `openrouter.ai:443` → `8.8.8.8:443`. IPv4/TCP/flags0 nu rup acești calleri. Asyncio standard folosește parametrii standard, iar sockaddr numeric al peerului evită o rezolvare secundară.
- `:410–423` este byte-identic cu baza: niciun resolver real/fallback; numai mappingul provider existent. Bariera fizică DNS păstrează Event și deadline2s/OSError. Loopback nu consumă bariera providerului. Tot ce este în afara callbackului este byte-identic, inclusiv controlled_connect care admite numai sentinelul și redirecționează spre peerul TLS deținut, send/RPC, cuts, receipt, census/restart și timeouturi.
- Oracolele exact4GET+1POST/1SENT/8write attempts sunt păstrate, nu exercitate aici ca rezultate runtime.

## Dovezi și limite

Execuție proprie bounded: `timeout --signal=TERM --kill-after=5s 30s api/.venv/bin/python -I -B -c <control inline de identitate/AST/calleri>` în repo; exit0, HEAD stabil, diff/index goale, `git diff --check 732ec1561b3aefc31da8e827d86e248d753c5e44 HEAD` exit0. Controlul a compilat modulul în memorie, verificat identitățile de mai sus, reprodus cele2RED vechi și executat callerii reali enumerați.

În aceeași execuție, `runpy.run_path('/home/kali/.hermes/cache/scratch/uif7/dns-source-check.py', run_name='__main__')`, script SHA-256 `fc5e650e9170f908224580423e594c995af2470928aff3a65109b873dff0aa11`: **PASS_SOURCE_ONLY,22refuzuri, barieră/deadline DNS păstrate, zero evenimente socket auditate**. Auditul independent a interzis orice eveniment socket; nu am rulat corpul complet create_connection sau resolverul real. Hashurile dovezilor autorului din freeze sunt identice; Ruff/format/mypy0 și collect-only2nodes0 se preiau scoped, fără rerulare.

Compoziția anterioară se păstrează numai în scope-ul ei: raportul C04 `/home/kali/.hermes/cache/scratch/r2-c04-focused-o_wx7dut/R2-C04-focused-review.md`, hash verificat `309d06daebf4c10a6c9b52b296c1688bb2e9ee738783cd4822b839dbe04f660c`, menține închise R1-F01/F02/F03 și R2-C01/C02/C03/C04. N01 LOW/copy și zero-gap cosmetic rămân amânate, neblocante. Nu am redeschis full33/full196.

Continuitate preluată de la părinte, fără reset: C04 harness-cycle1; UI1 eșuat înainte de driver în3.78s din aritatea DNS, nu test UI de produs; tentativa rămâne în istoric. Progresul real separat Settings guard54PASS/40.03s/outer0/drained pe732ec15 rămâne scoped și neschimbat; nu l-am rerulat. UI2 este încă NOT_RUN. Reticle NOT_APPLICABLE acestei verificări SOURCE; Chisel BLOCKED_NO_GO.

Numai acest raport a fost creat în scratch privat0700; zero editări repo/docs/index/skills, commituri sau delegări. Cele două fișiere untracked protejate au fost observate numai ca nume, niciodată deschise. Fără PG/browser/provider/network/auth/operator/global/push/deps effects.

Nu am rulat regresia PG, UI2, installed, build, full196 sau gates globale. Riscul de integrare/timing real rămâne pentru regresia și UI2 admise, nu devine PASS din această aprobare SOURCE.
