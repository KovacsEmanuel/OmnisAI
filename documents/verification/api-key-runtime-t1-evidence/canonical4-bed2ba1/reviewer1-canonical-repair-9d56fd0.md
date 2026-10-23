# R1 — remediere canonical CURRENT/SOURCE

**Verdict: APPROVED_TEST_SOURCE_SCOPED**, admis pentru QA independentă îngustă pe consumerul existent `test-contract-method-pg` (inventar 134). **Nicio constatare concretă blocantă în scope-ul R1.** Nu este acceptare PG/runtime, canonical PASS, T1/G00 CLOSED sau aprobare a integrării de către copil.

## Identitate și limită

- BASE `91d3e4ead63430eb59b4e028a00197a84526e786` → HEAD `9d56fd0729c94d17570720aab02943f2de6141b6`, tree `814b41d0ea4f544872797d1ef22a4cdde5a0adb3`; checkout curat la intrare și la ultimul readback.
- Diff exact: 10 fișiere, 248 inserări/59 ștergeri. Cele 10 SHA256 de fișiere corespund manifestului autorului; SHA256 `next-freeze.json` = `a4ebfad7c35eb248c30c7ba6396e23c1da939b34c31a90d56c2a6c9efed1cd21`. Nicio modificare în source-ul produsului API/CLI/integrări/web/DATA din căile comparate.
- R1: fixtures CURRENT, catalog fake/faza refuzului, seam-uri SOURCE, parser/cache, păstrarea readerilor. R2 deține auditul complementar al autorității/efectelor/selecției; acesta nu este duplicat universal aici.
- Citite AGENTS, CONTRIBUTING relevant, team-slice, CURRENT/rezumatul hărții, RCA sanitizată și diff-ul complet al celor 10 fișiere. Fără surse private/profile, vechi roots personale, log brut canonical sau HTML.

## Cerință → consumer → risc → decizie

| Cerință / consumer | Dovezi SOURCE și decizie |
|---|---|
| CURRENT head/CLI, migrații istorice | `test_contract_method_migration.py:20`, `test_mission_revision_schema.py:28`, `test_cli_status.py:45`: actualizează exclusiv așteptarea CURRENT la `0015_model_test_v2`; aserțiile istorice 0012/0013 și produsul rămân. Admis. |
| Catalog exact / `authority_schema_matches` | `test_mission_revision_schema.py:17–21,125–129,175–187,294–298`: OID distinct pentru fiecare tabel MODEL, index și triggere compatibile cu ramurile CURRENT; maparea `relation_oid` nu mai confundă toate tabelele cu mission. Pozitivul rămâne cerut; mutațiile de guard cer acum și interogarea attestation cu `p.prokind` pe OID mission. Negativele columns/constraints vizează din nou tabelul corect. Nu este probă a deparserului PostgreSQL. Admis pentru QA reală. |
| Readiness shape / `/health/ready` | `test_health.py:171–194`: RENAME în loc de DROP păstrează UNIQUE fizic/FK-urile, dar invalidează numele contractat. `core/db.py:122–125,156–165` compară exact nume/tip/definiție/flags; 503 + SCHEMA_INCOMPATIBLE rămân cerute. Nu am executat DDL. Admis. |
| SOURCE lifecycle și atribuirea refuzului | `test_contract_method_pg.py:2557+,4377+`: flagurile model false și applicability refac closure-ul fake fără activarea preparation/execute. `:1983+` furnizează prerequisite SOURCE inertă ca testul să atingă review guard, nu achiziția DB. `:8066–8073` adaugă codul `_exchange_locked` la observer, fără înlăturarea filtrului Task/CodeType, capului de evenimente sau taxonomiei. `:5165` schimbă numai inputul invalid la 10.0001; protocolul real `runtime_protocol.py:442–449` admite 0 < budget ≤ 10. Stderr/deadlines nu sunt relaxate; cauza stderr-ului istoric rămâne necunoscută. Admis. |
| Parser finit separat de CURRENT/cache | `test_contract_method_pg.py:7314–7452`: trei fișiere sintetice declarate, mutații bounded și origine substituită explicit SOURCE. Limitele reale ale `batch2_current_reader` nu se schimbă. `:7456–7580`: copiază pachetul API real din ROOT, nu înlocuiește API cu cele trei fișiere fake; execută codurile originale HISTORICAL_ORIGIN/RESTART_READER în fixturea autorului, cu inventory înainte de import, control UNCHECKED_HASH, marker absent și conservarea exactă a cache-ului necunoscut. Noua probă evită caps ale parserului finit numai în acest control separat, nu în ownerul real `batch2_current_reader`. `.pth` de dependențe rămâne seam SOURCE, nu instalare/release QA. Admis. |
| V1 receive-only și stale-reader | Git/AST confirmă neschimbate `batch2_current_reader`, `batch2_reader_inventory`, `batch2_reader_code`, `batch2_persisted_correspondence`, `historical_installed_journey`, constantele RESTART_READER/HISTORICAL_ORIGIN; niciun top-level existent eliminat. Decoding/readiness/migrații/read/replay/reconcile/no-redispatch/single-consume/post-Stop nu sunt înlocuite de fake-ul finit. Stale-inputul implicit este fresh, cu drift față de checkout înainte de origin; cazul autentic privat rămâne în legacy, cu corp AST identic, fără inventarea provenienței. Admis. |

## Verificare și dovezi delimitate

- Executat independent numai Git/hash/AST/JSON, fără import/executare cod de produs/test. Comenzile read-only și aserțiile au ieșit 0.
- Inventarul JSON verificat programatic: 3171 unique = 3164 default ∪ 7 legacy, disjunct; 134 narrow sunt subset default, fără legacy. Aceasta verifică manifestul furnizat, nu o nouă colectare pytest.
- Corpul AST al testului H04 native și al cazului autentic privat este identic cu BASE; numai markerul schimbă selecția. Diff-ul păstrează și cazul producer native în poarta legacy explicită. Nu sunt șterse corpuri sau ignorate fișiere întregi.
- Readback al dovezilor autorului: `next-source-final-isolated.log` declară SOURCE_ROOT al worktree-ului autorului și 221 PASS/15.37s; `next-development-final.log`: 30 SOURCE units/8.478s/OK. Nu le-am rerulat și nu le atribui reviewului meu. Cele trei teste Docker-config rămân NOT_RUN la leaf; lintul extins gate cu B023 preexistente nu este prezentat drept full lint GREEN.
- Canonical3 istoric rămâne 92 FAIL/1887 PASS/64 SKIP, 2362s, întrerupt exit2, conform RCA sanitizate; nu este rescris în PASS. Faptul că nu există defect de produs demonstrat de aceste eșecuri nu certifică absența defectelor.

## NOT_RUN / următoarea decizie

QA134 reală cu PostgreSQL deținut, probele canonical complete, runtime/native, installed ModelTest, crash/SENT și live/provider sunt **NOT_RUN de R1**. Lipsa QA134 nu blochează circular admiterea SOURCE: exact aceasta este proba următoare de stabilit de părinte după verdictul complementar și preflight. Proveniența nativă autentică rămâne BLOCKED_AUTHORIZATION dacă este cerută; nu se substituie cu fake sau vechi pin.

Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Nicio modificare a checkoutului/commiturilor/acceptării; singurul fișier creat este acest raport extern. Nicio cerere de stil, abstracție, framework sau lărgire a harness-ului.

Omis deliberat: audit general al harness-ului de 13k linii și rulări cu efecte. Riscul rămas: source review/logurile autorului nu dovedesc compatibilitatea PG sau închiderea T1; părintele adjudecă și execută QA134 pe bytes înghețați.
