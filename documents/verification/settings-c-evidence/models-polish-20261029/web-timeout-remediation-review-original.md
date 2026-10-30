# Review independent — remediu Wizard test-only

## Verdict

**APPROVED_SCOPED**, fără findings concrete care cer remediere, exclusiv pentru înlocuirea celei de-a doua secvențe `clear/type` din testul parametrizat POST/PUT. Cerința 413 → retenție → re-editare → salvare rămâne verificată. Remediul elimină mecanismul demonstrat al tastelor întârziate provenite din această re-editare; nu repară timeoutul inițiator și nu certifică izolarea generală a suitei.

## FREEZE verificat

- Repo: `/home/kali/OmnisAI`.
- HEAD: `9122a34d4449212b6271ebed504f1f7ffde3e924`.
- Singurul fișier tracked modificat: `web/src/app/Wizard.test.tsx`; două linii înlocuite cu un comentariu și `fireEvent.change`.
- Blob: `7799f370ecca9bc3c4051a3a78d1d0f69fbf45ad`.
- SHA256: `df18b83b8f30a4d40a3bc8771588d3b3b3f693e0c3d67501addbbe19eddcb2c1`.
- Bytes identici cu fișierul din `/home/kali/.hermes/cache/scratch/settings-remediation-web-20261030/web/src/app/Wizard.test.tsx`; diff identic cu `candidate.patch` din directorul de dovezi. HEAD/blob/starea au fost recitite la încheiere; indexul fără schimbări.
- Cele două căi untracked protejate au fost numai observate în status, nu citite, hash-uite sau modificate. Niciun edit/commit/stage în checkout; raportul acesta este singurul fișier creat de reviewer.

## Cerință → cod → evaluare

Consumerul afectat este testul Vitest existent, nu UI/browserul de produs. Scope: testul POST/PUT și citirea handlerului/formularului pe care îl exercită. Nu sunt necesare schimbări în callers, fixtures, config, exports sau dependențe.

| Obligație | Linii în `web/src/app/Wizard.test.tsx` | Evaluare |
|---|---|---|
| Refuz cert 413 la prima scriere | 38–50 | Ambele metode și răspunsul `BODY_TOO_LARGE` sunt neschimbate. |
| Editarea inițială și retenția exactă | 55–70 | `user.clear/type`, click Save, mesajul de refuz, valoarea exactă și o singură scriere sunt păstrate. |
| Acțiuni disponibile după refuz | 71–73 | Save/Next enabled și absența stării uncertain sunt păstrate. |
| Re-editare fără autosave, apoi salvarea noului conținut | 74–80 | Evenimentul este trimis nodului `name` capturat, apoi se verifică o singură scriere înainte de click, revizia salvată, două scrieri și payloadul exact `Corrected and retained`. Nu se injectează direct state/cache/stored. |

`web/src/features/engagement/Wizard.tsx:168–169` readuce refuzul 413 în idle; `:227–229` păstrează inputul controlat și handlerul real `onChange`. Fieldsetul și Save/Next folosesc același `lock` (`:199`, `:227`, `:295–296`), verificat indirect de aserțiunile enabled existente. Nu există modificare de produs, timeout, worker sau teardown.

## Baza cauzală și reproducerul inspectat

Dovezi originale citite din `/home/kali/.hermes/cache/scratch/settings-remediation-web-evidence-20261030/`: contract, sursele diagnostic RED/GREEN, loguri și exituri, contoare, patch, regresie și typecheck. Comanda efectivă în ambele loguri de diagnostic: `NODE_ENV=test vitest run src/app/Wizard.test.tsx -t 'SOURCE typing ownership' --reporter=verbose`, prin scriptul npm existent, în worktree-ul separat.

- **RED:** `diagnostic-red.Wizard.test.tsx:39–136` atribuie originea cu AsyncLocalStorage la începutul corpului testului și recipientul prin WeakMap; fără fallback la testul curent. POST este suspendat în re-editare după `Corrected ` până la timeoutul real de 5000ms. PUT ajunge la `R`, confirmă nodul vechi deconectat/noul nod focalizat și eliberează POST. Logul arată 12 keydowns POST→PUT, sufixul `and retained`, UNKNOWN=0 și valoarea `Rand retainedetain my local edits`; aserțiunea originală de retenție eșuează. Controlul settled POST/PUT trece, cu zero contaminare. Rezultat: 2 FAIL / 2 PASS / 22 skipped, exit1, 8.34s.
- **GREEN pe țintă, nu pe întreaga diagnostică:** sursa GREEN păstrează handofful și timeoutul, dar mută bariera imediat înainte de schimbarea sincronă, deoarece aceasta nu are un yield intern. `SOURCE_REEDIT` confirmă executarea pe nodul vechi deconectat și valoarea PUT focalizată încă `R`; detectorul are zero cross/UNKNOWN și keydowns proprii pozitive. PUT și ambele controale settled trec. POST forțat rămâne FAIL: 1 FAIL / 3 PASS / 22 skipped, exit1, 7.40s. Returnul timpuriu al POST contaminat este numai în diagnostic; salvarea este verificată de controalele settled și de candidatul final fără instrumentare.
- Reviewerul a recalculat contoarele din JSON-ul brut `SOURCE_DETECTOR` și a confirmat egalitatea cu `detector-counts.jsonl`; nu a dedus absența contaminării doar dintr-un test verde.

Această diferență verifică sursa contaminării în intercalarea controlată, nu cauza duratei POST istorice. Excerptul istoric păstrează separat timeoutul POST și valoarea PUT `and rReettaaiinne dmy local edits`; nu este aceeași cronologie capturată și nu îi atribuim retrospectiv toate cauzele.

## Verificări și predare

Dovezi autor, inspectate și reutilizate, **nu rerulate de reviewer**:
- `NODE_ENV=test vitest run src/app/Wizard.test.tsx --reporter=verbose`: 24/24 PASS, 7.06s, `test_exit=0`; numărul cazurilor a fost recalculat din log.
- Scriptul npm `typecheck` → `tsc --noEmit`: `typecheck_exit=0`.

Verificări proprii read-only: Git snapshot/diff/blob/SHA256, egalitate worktree/patch, recalculare detector și `git diff --check -- web/src/app/Wizard.test.tsx` exit0. Nu a apărut un defect concret care să justifice încă o rulare diagnostică. Lintul și execuția afectată post-review pe checkoutul integrat rămân la părinte, urmate de decizia de integrare/commit.

Delta propusă: acest test-only candidat este APPROVED_SCOPED; CURRENT/harta nu au fost editate. T1_BLOCKED/T2_NOT_READY și gate-ul canonic NOT_RUN nu se promovează. Cauza timeoutului POST, ProviderKeySettings și SettingsWizard rămâne UNKNOWN/deschisă; nu se transferă PASS la full-web sau la istoricul eșuat.

Nu am executat browser, full-web, canonical, servicii, provider/model sau auditul Python separat. Reticle NOT_APPLICABLE pentru acest remediu test-only; Chisel BLOCKED_NO_GO. `fireEvent.change` acoperă tranziția de formular/salvare, nu o secvență nativă de taste/focus după 413; tastarea inițială rămâne, iar alte operații asincrone întârziate nu sunt remediate sau certificate de acest patch.
