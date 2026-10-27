# R2 — re-review focalizat Settings C / ae722

**Verdict: CHANGES_REQUESTED_SOURCE_SCOPED.** R2-C01/C02/C03 sunt închise în scope SOURCE pe bytes curenți. Un blocker nou de oracle, **R2-C04**, confirmă suspiciunea părintelui: contorul global nu atribuie I/O comenzii locale. Nu este un FAIL runtime observat și nici un defect demonstrat al ownerului de produs.

## Binding exact și compoziție

- Repo `/home/kali/OmnisAI`; HEAD verificat la început/final: `a2eb7f50440dade4c66e13acd4c59a4d39862a77`.
- Base: `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Candidate ID: `ae722e7508ee8b348c93bdeea3cbcef33279acad0224fe7de710ab84b7e18319`.
- Manifest `/home/kali/.hermes/cache/scratch/uif5/final33-freeze.json`, SHA-256 `1a6b4251233a351bfb54333e6983f83a79eb0d8d9c5a1b890516b35155555d81`. Toate cele **33** hashuri recalculate direct, zero mismatch; candidate ID canonical recalculat identic. `integration_head=9b6a55b...` este momentul precommit F03, nu o discrepanță a bytes.
- Raportul original compus, nu înlocuit: `/home/kali/.hermes/cache/scratch/r2-settings-57ae-4p36wfno/R2-original-review.md`, SHA-256 `ebc66d7b0311c86ef25f145ef73b0aa4ab6972b941a55f343a6a840bd1ce16ac`, neschimbat. Raportul R1 original rămâne neschimbat: SHA-256 `fcb4cee7f7ffb71c3a25cf23f29e210c7e854f984f258be93faea7bea9f3bfb9`.
- Scope: remediile celor trei findings originale și noile frontiere F03 de concurență/eșec/secrete/capture/restart/ownership. Nu reiau auditul tuturor celor33 sau breadth-ul funcțional/estetic R1. Cerințele R2 originale neafectate păstrează numai acoperirea și limitele raportului original. R1-F01/F03 nu sunt închise de acest raport.

## Dispoziția fiecărui finding original

| Finding | Dispoziție | Motiv / dovadă |
|---|---|---|
| **R2-C01 HIGH/P1** — grant A→B | **CLOSED_SOURCE_SCOPED** prin `e8d86f8ddd5332548cb85cfaa8194e35a9a93847` | `ProviderSettings.tsx:7–22` acceptă scope numai când grantul capturat coincide cu grantul curent; renderul B nu poate păstra pagina A până la digest. Cleanup-ul efectului interzice publicarea unui rezultat superseded. Wizardul vechi se demontează, iar cleanup-ul existent șterge și nodul secret detașat. CSRF brut rămâne numai în context/binding in-memory, nu în query keys/storage. Am rerulat cele3 scenarii originale și cele2 regresii promovate curente: **5PASS/0FAIL**, inclusiv digest B întârziat, input detașat șters și neadoptarea UNKNOWN_A. Dovada autorului48PASS pentru recovery în aceeași sesiune/Cancel/StrictMode se reutilizează scoped, nu se rerulează integral. Auth/bootstrap/local_control sunt neschimbate față de base. |
| **R2-C02 MEDIUM/P2** — unsafe Make | **CLOSED_SOURCE_SCOPED** prin `9b6a55bf64e3bb131bd403fd19ccfc8edd8db2c8` | Doar targetul adăugat în filterul existent și tuple-ul testului negativ extins. Testul existent rerulat independent: **1PASS**, toate combinațiile celor3 targeturi ×4 flags păstrează exit2/mesaj/no-recipe; missing-fixture control rămâne. Nicio rețetă PG reală. Cele6 B023 opționale documentate sunt baseline neafectat, în afara API lint manifest; fără ignores sau gate slăbit. |
| **R2-C03 MEDIUM/P2** — census installed SENT | **CLOSED_SOURCE_SCOPED** prin `b8e93e062b1021e396b8297de4be824ded95b43f` | Setul exact before→cut adaugă numai `provider_model_registry_revision`, `provider_model_entry`, `provider_model_entry_revision`, `provider_model_command`; egalitate exactă, nu subset. Control AST/SQL pe producerul real confirmă cele4 INSERT tables. Eliminarea doar a celor4 linii reconstituie byte-exact întreaga funcție installed de dinaintea fixului, inclusiv cut→after→final, replay/no-resend și census complet. PROBE compilat fără execuție. **PG/installed NOT_RUN**, nu inventez runtime GREEN. |

## Finding nou — R2-C04 / MEDIUM / P2

**Fișier/linie:** `api/tests/test_model_test_v2.py:524,531–546`, în special `finally: assert len(received) == before_io`.

**Criteriu încălcat:** CONTRIBUTING preflight cere oracle corect față de producer și ordinea tranzacțiilor; team-slice cere linearization points și rezultate legale. Un contor de trafic global pe durata unui await nu demonstrează că acel reader local a produs trafic. O probă reală nu trebuie respinsă numai pentru progresul legitim al unei operații explicite deja admise.

**Ordine legală inspectată:**

1. `provider_catalog_runtime.py:196–203` pornește `refresh` ca task al ownerului și răspunde fără a aștepta tot catalogul; refresh-ul parcurge paginile la `:206–239`.
2. `SettingsModelsPage.tsx:119–129` primește PENDING și pune `sending=false`; query-ul curent `:43–61` poate relua GET providers/readLibrary în timp ce catalogul lucrează. Wizardul folosește în paralel citiri cache `SettingsModelWizard.tsx:47–51,85–87`.
3. Callback-ul de test capturează `before_io` **înainte de** `settings.handle`. Readerul real intră în `ProviderSettingsOwner.handle`, care poate aștepta lock-ul existent (`provider_key_service.py:242–255`). Același lock poate fi deținut de metadata_guard (`model_test_runtime.py:529–569`) în timpul unui ciphertext handoff (`model_relay.py:179–203`).
4. Peerul TLS poate primi și înscrie în `received` GET-ul catalogului la `test_model_test_v2.py:225–235` în timp ce readerul așteaptă. După eliberarea lock-ului, read-ul local reușește fără provider I/O, dar `finally` îl respinge pentru creșterea contorului global. Așteptările DB oferă și alte puncte de intercalare; lock-ul produsului nu corelează acel snapshot exterior.

**Repro SOURCE executat, bounded, fără DB/socket/browser/provider:** `counter-source-repro.py` din directorul acestui raport extrage prin AST callback-ul **nemodificat** din sursa exactă și execută `ProviderSettingsOwner.handle` real cu DTO real; doar engine/view sunt doubles locale fără I/O. Control quiet: read reușit. Două intercalări controlate, contor inițial0/1: un GET independent modelat în contor în timp ce readerul așteaptă lock-ul → read local executat, provider I/O local0, apoi exact `AssertionError: Local save/read must not contact provider`. Scriptul exit0 înseamnă că a demonstrat cele2 false positives și controlul, nu că gate-ul real a trecut. Rezultat: `counter-source-result.json`, SHA-256 `6b54bcac7e9ff3b31c4c97fb42361f5b277a15341b0921f746c102a588e59936`.

**Remediu minim:** elimină/narrow acea corelație per-command neatribuită. Păstrează contorul pentru cuts și păstrează **integral** secvența finală exactă4GET metadata+1POST/1SENT, refresh cuts `[0,2,5]`, start cuts `[4,5]`, cele8 încercări locale de scriere inclusiv CAS refuzat, receipt barrier, readbackurile de fază/restart/census și refuzurile exacte fără extra tests/resend. Dacă se păstrează o aserțiune no-I/O globală, folosește numai frontierele deja stabile/quiescent, fără a pretinde cauzalitate universală. **Nu** aștepta catalog task în owner.read, nu ține un lock nou, nu adăuga supervisor/context framework și nu relaxa politica produsului pentru oracle.

**Decizie:** părintelui îi revine reproducerea/adjudecarea și atribuirea remedierii autorului. Acest defect SOURCE de preflight se corectează înaintea primei QA effectful; nu cere un rerun al întregii suite sau un al treilea strat de harness. Nu afirm că scenariul real a eșuat deja ori că intercalarea apare la fiecare execuție.

## Celelalte frontiere F03 verificate focalizat

- New-key marker: driverul înregistrează numai cheia sintetică proprie prin canalul privat existent înainte de fill (`settings-models.mjs:104–107`); capturile sunt înainte de fill sau după Continue/wipe (`:102,120–121`). Request observer reține numai path/action, nu corpul secret. `secretChecks` inspectează DOM/live values/storage și allowlistul secretless existent. Nicio citire de credentiale/control.cap/DSN în acest review.
- Headerul peerului nu este o eroare de redacție: construcția requestului HTTPX GET și SDK POST instalat păstrează headerul brut exact așteptat. Controlul fără send raportează numai două booleene `true`; nicio valoare secretă imprimată. `structural-source-result.json` include această probă.
- Helperul existent `test_web_e2e.py:278–383` păstrează două procese API secvențiale, același fixture, census exact13tabele,120s/stage, finally cleanup_all/engine.dispose; testul exterior rămâne300s și gate-ul planificat600s. Așteptarea driverului prin to_thread permite progresul ownerului/catalogului — nu serializează și nu rezolvă C04.
- Capturile sunt29 **planificate**, nu observate; cele27 capturi SOURCE/synthetic ale autorului nu sunt promovate la consumer API/PG real sau estetică. Testele stale Continue409/CONNECTION_UNAVAILABLE și entry test ulterior409 păstrează același canal HTTP, fără bypass/retry/policy nou. Clasificarea UI/recovery și breadth-ul F03 rămân la R1.

## Execuții proprii și artefacte

Toate căile de mai jos sunt în `/home/kali/.hermes/cache/scratch/r2-ae722-focused-qyn4o7wt/`.

- `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH TMPDIR=<dir> NODE_ENV=test timeout --signal=TERM --kill-after=5s 60s web/node_modules/.bin/vitest run --config <dir>/vitest.config.mjs -t 'R2 |authenticated grant rotation' --reporter=json --outputFile=<dir>/grant-focused-result.json` → exit0, **5PASS/18SKIP (filtru explicit)/0FAIL**, nu full196. JSON SHA-256 `0e3d99c556b2a6a5049528bba3f26b31e6d69fb57a18ca5beafef8574cebf61e`.
- `TMPDIR=<dir> timeout --signal=TERM --kill-after=5s 60s env -u PYTHONPATH -u MYPYPATH -u PYTEST_ADDOPTS -u PYTEST_PLUGINS -u MAKEFLAGS -u MFLAGS api/.venv/bin/python -I -B -m unittest discover -s tests/development -p test_test_db_gate.py -k test_model_test_pg_refuses_unsafe_make_flags_before_recipes -v` → exit0,1PASS; `make-focused.log` SHA-256 `c4e30221722c8bf0b0f198ac68743c87529363caae61b8b21c7729cb71883f53`.
- `TMPDIR=<dir> timeout --signal=TERM --kill-after=5s 30s api/.venv/bin/python -I -B <dir>/counter-source-repro.py` → exit0,1quiet control+2false-positive reproductions; script SHA-256 `1b0feb31258099aa290e709c92d6971c4496d4a70aa9f53c8df7c99eb4e28135`.
- Aceeași comandă30s pentru `structural-source-checks.py` → exit0, census/bytes/PROBE/header checks; `structural-source-result.json` SHA-256 `f7ad7b072fbebb3df0bd47ff1649057ed4021c80ca79690269f06cc4bd3085f2`.
- Hash readback33/manifest/candidate/originals la început/final; `git diff --check` exit0, index gol. Numai cele2 nume untracked protejate preexistente; nu au fost deschise. Nicio editare în repository/docs/index/skills, nici commit/delegare/dependență/serviciu/adopție/operator/provider/network/auth/push. Artefactele noi sunt numai raportul/probele SOURCE și cache-ul lor privat; probele originale rămân intacte.

## Handoff / limite

| AICI | Cod / pregătire | Dovezi | Review |
|---|---|---|---|
| Settings C, snapshot ae722/33 | Remediile originale implementate; F03 preparat | SOURCE focalizat de mai sus; real QA0attempts / NOT_RUN | R2 original compus + C01/C02/C03 CLOSED_SOURCE_SCOPED; **C04 CHANGES_REQUESTED** |

Nu am executat PG/installed/API/browser-consumer/canonical, trafic provider, screen-reader sau acceptare vizuală și nu am repetat full196/build. Reticle NOT_INTEGRATED în verificarea SOURCE; Chisel BLOCKED_NO_GO.
Riscul rămas demonstrat este un false failure de harness la progres catalog legitim; produsul/runtime/estetica nu sunt aprobate. După remediul minimal și re-review afectat, QA reală pending nu este ea însăși un blocker circular pentru admiterea acelei QA.
