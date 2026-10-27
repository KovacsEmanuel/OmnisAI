# R1 — CHANGES_REQUESTED_SOURCE_SCOPED

Review independent read-only, limitat la recuperarea Wizard și adevărul readback-ului hidratat. Parentul adjudecă findings; acest raport nu este acceptare sau runtime PASS.

## Findings concrete

### R1-F01 — MEDIUM — eroarea veche rămâne autoritară după reconciliere reușită și acceptare explicită

- **Loc:** `web/src/features/engagement/Wizard.tsx:219–220`; traseu `177–197`, `278–279`.
- **Reproducer:** Setup hidratat la revizia 1 → editare locală → PUT pierde răspunsul înainte de stocare → Refresh are GET de proiecție reușit și GET de editor 503 → serviciul revine → noul **Compare server revision** primește prin decoderul real revizia 1 → **Discard local edits and load server revision**. Formularul revine corect la payload-ul serverului; un singur PUT în total. Totuși outputul rămâne **Unconfirmed readback**, lipsește **Saved · revision 1**, iar alerta **The database or control plane is unavailable. No success was confirmed.** rămâne vizibilă.
- **Cauză:** GET-ul direct din `reconcile()` actualizează `server`, iar discard actualizează `saved/form/phase`, dar niciunul nu retrage eroarea query-ului de editor. Noile condiții `query.isError` afișează astfel eșecul istoric ca stare curentă chiar după un readback acceptat. Interacțiune între cele două commituri, nu audit backend.
- **Criteriu încălcat:** status/readback truthful după recuperarea explicită, păstrând local edits până la alegerea operatorului. Nu s-a observat pierdere de date ori replay; defectul este starea falsă de eșec după succes.
- **Remediu minim:** sincronizează eroarea/datele query-ului cu readback-ul valid acceptat la discard/rebase, fără rehidratare automată peste formular; nu retrage eroarea pe GET eșuat. Adaugă cazul compus ca regresie.
- **Probă:** un test scratch SOURCE/jsdom pe bytes finali, **1 FAIL / exit 1**, trei aserțiuni ale aceluiași defect; toate precondițiile, GET-ul reușit, payload-ul restaurat și write-count=1 au trecut. Logul nu este gate de produs.

### R1-F02 — LOW / neblocant separat — afirmație falsă de diferență pe same-revision

- **Loc:** `web/src/features/engagement/Wizard.tsx:191`, accesibil acum prin `285`.
- **Reproducer:** același PUT fără receipt, nestocat, apoi **Compare server revision**; GET întoarce exact revizia 1/digestul salvat inițial. Se afișează **Server revision differs. Choose explicitly whether to discard or keep your local edits.** deși identitatea/revizia/digestul serverului nu s-au schimbat. Testul scratch verifică explicit atât revizia 1/digestul inițial, cât și această notificare. Alegerea explicită rămâne corectă; afirmația despre server nu este.
- **Criteriu încălcat:** statuscopy truthful pe ramura same-revision cerută.
- **Remediu minim:** text neutru, de exemplu **Server revision loaded. Choose explicitly whether to discard or keep your local edits.**; nu introduce alt flow/state.

## Identitate exactă

- Bază: `9e51d108382bcfad9b6f0b88dee410113a8eb40a`.
- Commit 1: `78decf37c3b879593173f6451894e3be5e0ba012` (părinte = baza).
- Commit 2 / HEAD revizuit: `4bbb774a791230c851597f876edff88abb1dd1d9` (părinte = commit 1).
- SHA256 al diff-ului binar Git pentru cele trei căi, bază→HEAD: `9d96de031a9fc98aa2fa3bdf85696419d9ef189ef62fcedd69273c74aba751f1`.

| Cale | SHA256 final / working tree |
|---|---|
| `web/src/features/engagement/Wizard.tsx` | `479690a5249759123f4287a64a46d5a75705762aacde6507437075991780848d` |
| `web/src/app/ReceiptRecovery.test.tsx` | `f7e5e9cc258e59046f841c029c774caed7f56a60f37b63d029035e6bc332ac8e` |
| `web/src/app/Wizard.test.tsx` | `a67138616702f0eb82819a0d42a7b678470763889578eaf3a6151000ec1b9e0f` |

Hărțile intermediare și finale au fost verificate față de bloburile ambelor commituri și handoff-ul autorului. Handoff: `/home/kali/.hermes/cache/scratch/wizard-recovery-v9d58eg_/handoff.json`, SHA256 `18179d7c600fd67f8f952f21cb3feec8cbc36902405bb2d0b2d372d075ce6125`.

## Dovezi și limite

- Reproducer: `/home/kali/.hermes/cache/scratch/wizard-r1-review-gfrhci8m/src/ReconcileReadback.test.tsx`, SHA256 `8eaafc85a7908a774067b489aaa7aedcbf76c967c2cb0f1cdc7134d36083dc2e`.
- Log original: `/home/kali/.hermes/cache/scratch/wizard-r1-review-gfrhci8m/reproducer.log`, SHA256 `ab73b22a8738b53af233d34516372390696d9cba7a16bbebb6057ac909c4a21e`.
- Comandă executată din `/home/kali/OmnisAI`: `PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin NODE_ENV=test /home/kali/OmnisAI/web/node_modules/.bin/vitest run --config /home/kali/OmnisAI/web/vitest.config.ts --root /home/kali/.hermes/cache/scratch/wizard-r1-review-gfrhci8m --reporter=verbose src/ReconcileReadback.test.tsx`. Exit **1**; fără servicii/rețea reală. Scratch folosește numai symlinkuri spre dependențele/setup-ul existente, nu configurare produs nouă.
- Dovezi autor citite, SHA-urile tuturor celor opt logs verificate față de handoff: RED1 **2FAIL25PASS** → **27PASS**; RED2 **4FAIL27PASS** → **31PASS**. Nu sunt execuții R1 proprii și nu închid cazul compus de mai sus.
- **Default `make check-web` rămâne FAIL, exit 2 / 4FAIL199PASS; cauza UNKNOWN.** Rularea distinctă `VITEST_MAX_WORKERS=2 make check-web` are **203PASS + 6tooling**, contracts/types/lint/build/audit0. Nu am repetat gate-ul și nu am schimbat selecția, deadline-urile, configul sau dependențele.
- HEAD/status recontrolate după reproducere: același commit; fără diff tracked/staged. Fișierele protejate preexistente nu au fost citite sau modificate. Niciun commit, serviciu, profil, provider/target/model/spend sau instalare efectuată.
- Verificarea R1 este source/jsdom și semantică HTML, nu tastatură/browser/visual/screen-reader/installed API/PG QA. Reticle NOT_APPLICABLE acestei execuții SOURCE; Chisel BLOCKED_NO_GO. R2 și QA instalată rămân la parent; lipsa lor nu este un finding nou în acest raport.
