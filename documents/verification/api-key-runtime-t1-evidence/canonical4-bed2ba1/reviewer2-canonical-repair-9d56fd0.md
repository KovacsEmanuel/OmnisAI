# R2 — APPROVED_TEST_GATE_SOURCE_SCOPED

## Identitate și mandat

- Review independent, read-only, pe `/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/integration-src`.
- HEAD `9d56fd0729c94d17570720aab02943f2de6141b6`; tree `814b41d0ea4f544872797d1ef22a4cdde5a0adb3`; bază `91d3e4ead63430eb59b4e028a00197a84526e786`.
- Status Git curat la început și la ultima verificare. Delta exactă are cele 10 căi test/gate declarate; nu modifică produsul, migrațiile, limitele ori pinurile istorice. SHA256 pentru `next-freeze.json`: `a4ebfad7c35eb248c30c7ba6396e23c1da939b34c31a90d56c2a6c9efed1cd21`.
- Cerință → consumer → risc → decizie: poarta API-key-only nu trebuie să execute implicit probe Hermes/native sau să citească descriptorul privat vechi → `test-api` / `check-components` / targetul PG existent → efecte neautorizate, acoperire ascunsă ori refuz în faza greșită → admiterea SOURCE pentru preflight și QA PG134 ale părintelui, nu acceptare T1.

**Findings blocante confirmate: niciunul în acest scope.** Nu propun modificări de produs/teste sau un owner nou.

## Cerință → cod → concluzie

1. **Selecție precisă, fără eliminarea acoperirii.** `Makefile:23,174–177,210–214`, `api/pyproject.toml:45`, `api/tests/test_contract_method_pg.py:6353,7582`, `api/tests/test_contract_method_producer.py:262`.
   - Defaultul păstrează cele trei ignore-uri preexistente și adaugă numai `-m 'not legacy_native'`. Nu există ignore de fișier nou, ștergere de corp sau blanket skip nou în delta acestei separări.
   - Cele șapte noduri legacy sunt exact cinci variante H04 real-AIAgent, un producer nativ și un control autentic cu descriptor privat reținut. Comparația AST cu baza confirmă corpurile celor două teste native și ale controlului privat neschimbate; clasificarea nu le înlocuiește cu doubles.
   - Am validat programatic inventarul real deja colectat în `next-selection.json`: 3171 total = 3164 default ∪ 7 legacy, fără intersecție sau duplicate; cele 134 narrow-PG sunt subset default și nu intersectează legacy. Nu am recollectat/executat pytest.
   - Toate șapte rămân explicit în `check-runtime`. Comanda strictă `test_native_build.py` este înaintea lor, iar eșecul ei oprește rețeta normală; prerechizitul MANAGEMENT/OAuth original este păstrat, fără prepare/setup automat. `check-components` păstrează lista completă de componente API-key-only și nu depinde de `check-runtime`.

2. **Fără acces implicit la vechiul privat/nativ pe callerii afectați.** `test_contract_method_pg.py:1980–2005,3918–3930,5062–5076,7000–7005,7428–7452,7582–7602,7703–7753,7933–7939,8430–8433`.
   - Stale-reader default construiește un descriptor SOURCE fresh și modifică numai bytes din checkoutul fixture-ului; refuzul cere zero apeluri de origin. Pathul privat autentic este numai în testul legacy explicit.
   - Am urmărit referințele și callerii reali ai `PIN`/`LIBRARIES` și ai readerului, nu doar constantele: observerul real este marcat legacy; journey-ul nativ mare păstrează opt-in-ul preexistent; cele trei controale default care îl apelează direct fie substituie prerequisitele în `tmp_path`, fie refuză înaintea lookupului de artefact/fixture prin review gate. Helperul dependent de artefact rămâne explicit opt-in și sare înaintea citirii când acesta lipsește.
   - Accessorul real importat de `batch2_reader_material` este `omnis.modules.settings.skill_catalog.read_file`, nu `agent`/AIAgent. Am citit implementarea și importurile directe ale accessorului/schema: deschidere FD no-follow, limită max+1, regular/nlink/stability fences; fără bootstrap nativ. Constantele sau stringurile SOURCE istorice nu sunt confundate cu executarea lor.

3. **Parser finit ≠ atestare integrală; cache proof autentic separat.** `test_contract_method_pg.py:7314–7452,7456–7579,7703–7926`.
   - Fixture-ul de trei fișiere este etichetat explicit sintetic și substituie originul numai pentru controlul parserului. Pozitivele și max+1 păstrează wheel327680 / aggregate1179648 / member131072 / count128; construirea controalelor menține valide limitele nețintite. Parserul și funcțiile de material/inventar/cod sunt AST-identice cu baza: nu s-au mărit limitele pentru GREEN.
   - Controlul separat copiază întregul API curent real în export și site-packages; `.pth` rămâne numai seam SOURCE de dependențe. Rulează codul real `HISTORICAL_ORIGIN` și `RESTART_READER` (assignments neschimbate față de bază), verificând bytes wheel/export/checkout/installed. Nu pretinde că wheel-ul integral a trecut parserul finit sau că aceasta este QA de distribuție instalată.
   - UNCHECKED_HASH `.pyc` este respins fie înainte de origin, fie în prefixul fresh-reader înaintea importurilor API; se cer marker absent, audit gol în cazul refuzului, reason/exit exacte, sursa și cache bytes neschimbate. Calea pozitivă cere evenimentele ORIGIN/READY/EXIT. Nu există ștergere de cache pentru GREEN.

4. **Owner PG existent, neschimbat.** `Makefile:11–17,123–125`; `ops/run_test_db_gate.py:825–849,876–882,974–1017,1048,1092–1099`.
   - Delta runnerului adaugă numai choice-ul targetului existent `test-contract-method-pg`; nu modifică provisioningul, attest/auth/readback, deadline-ul, family-drain sau cleanupul.
   - Targetul cere fixture-ul dedicat și păstrează migration/producer, adăugând health/mission-schema/catalog-compat și aceeași excludere legacy. Guardurile Make `-n/-t/-q/-i` rămân pre-effect; testele lor includ acum și targetul narrow. Nu există owner/harness nou sau autoritate native nouă.

## Dovezi și limite

Am executat numai citiri Git/source, parsare AST/JSON, comparații structurale și hashuri cu Python stdlib; verificările finite de identitate/selecție/corpuri păstrate au ieșit 0. Nu am importat modulele repo și nu am rulat teste, runner, Make, servicii, PG, Docker, provider, browser ori native.

Dovezi fresh existente, citite și reutilizate, nu revendicate ca execuție proprie: `next-source-final-isolated.log` — 221 PASS/15.37s; `next-development-final.log` — 30 teste/8.478s/OK; metadatele freeze consemnează exit0 și API Ruff/format/mypy0. Cele trei teste Docker-config rămân NOT_RUN în această dovadă. Istoricul canonical FAIL și stderr istoric necunoscut nu sunt reinterpretate ca zero efecte ori PASS.

**Decizie:** SOURCE admis în acest scope pentru preflight-ul real existent al părintelui (`--check --target test-contract-method-pg --timeout-seconds 600 --uv <PIN>`), apoi QA owned PG134 după rezolvarea prerechizitelor. Nu certific runtime PG/native/CLI, canonical final sau închiderea T1. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Singurul fișier creat de reviewer este acest raport, în afara checkoutului. Nu am modificat produsul/testele/Git/statusul proiectului.

Omise deliberat: PG/Docker/native/browser/live și reauditul istoric general. Riscul rămas este execuția reală încă neprobată pe această frontieră; verdictul SOURCE nu o înlocuiește.
