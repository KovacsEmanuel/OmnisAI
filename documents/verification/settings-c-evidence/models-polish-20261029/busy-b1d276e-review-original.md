# Review independent — busy/readback, b1d276e

**Verdict: APPROVED_SCOPED. Findings blocante: niciunul în delta revizuită. Clearance de cod pentru proba reală afectată, sub admiterea/preflight-ul părintelui; nu integrare, acceptare vizuală sau închidere T1.**

## Identitate și limită

- Worktree: `/home/kali/.hermes/cache/scratch/settings-inline-feedback-20261029`.
- Base: `dbf3a13738b728c93b537578679693e61e5bedd3`.
- HEAD: `b1d276e66455dca0939cfcb42eeca5af7b1fe515`; tree: `347be9def5348a680017d141155c938b95e6d65c`.
- Exact două căi: `web/src/features/engagement/SettingsModelsPage.tsx`, blob `ff6e4a65e259199ecfedd6b4eb702f0e61d1bc78`; `web/src/app/SettingsWizard.test.tsx`, blob `2258225fa1f15a5ef14ea8368f934b37f688e1d4`.
- Tree/blobs/SHA256 verificate față de FREEZE. Tracked/index curate înainte și după review; patru dependency links preexistente păstrate. `git diff --check base HEAD`: exit0.

## Cerință → consumer → risc → decizie

1. **Save să nu pară disponibil când citirea locală îl refuză.** Parent `SettingsModelsPage.tsx:101,188,399` → `SettingsModelWizard.tsx:50,116–123,162`. `working={busy}` propagă exact `sending || reading || current.isFetching` către mecanismul transient existent. Acoperă atât query refetch, cât și Reload manual; guardul parent rămâne intact. Remediul de o linie este suficient, fără mecanism nou sau auto-retry.
2. **Consimțământ/focus păstrate, fără efecte în busy.** Testele `SettingsWizard.test.tsx:29–74` țin numai GET-ul bibliotecii după catalog, discriminează cele două canale prin `isFetching` 1/0, verifică lipsa consimțământului inițial, apoi apasă ambele Save cu consimțământ. Cer zero scrieri noi, zero entries, chei neschimbate, checkbox și focus păstrate, `aria-disabled/aria-busy=true`, fără native disabled. Child-ul nu resetează consimțământul pentru transient; guardul save împiedică efectele. Aprob scoped.
3. **După citire, numai Save local explicit.** Testele verifică lipsa trimiterii automate după release, apoi un singur `save_models`, model/revision/cap corecte și închiderea wizardului. Receipt/readback/CAS și ordinea înainte de dispatch (`SettingsModelsPage.tsx:187–210,330–341`), precum și Stop, sunt neschimbate. Nu se transferă din SOURCE o dovadă PG/provider.

## Dovezi citite, nu rerulate

- Originalele corrected RED și GREEN au SHA256 conforme FREEZE. Numărare programatică: RED **2 FAIL / 8 PASS / 92 skipped**, ambele defecte la `aria-disabled=false`; GREEN **10 PASS / 92 skipped**, exit0. Selecția include no-dispatch pentru cancel/unmount/wrong-receipt/changed-revision și secvența terminal/latest.
- Rezultatele originale noi `settings-save-busy-typefix-dbf3a13/{typecheck,build,lint}-result.json`: toate exit0; nu am executat din nou aceste comenzi.
- Singura diferență test față de bytes GREEN este `return undefined` explicit în interceptor. Eliminarea exact a acelei linii din candidatul citit reproduce SHA256-ul GREEN din manifest; return/timing runtime identice. Blobul GREEN intermediar nu era stocat în Git (`cat-file` a eșuat); verificarea alternativă prin SHA256 a reușit. Produsul este identic cu produsul GREEN.

## Predare

Părintele poate trece la QA reală bounded a read-barrier/Save pe bytes curenți, fără replay al UI neschimbate. Persistența și comportamentul native/browser rămân de probat acolo; reviewul nu autorizează singur efecte și nu atribuie cauza FAIL-urilor PG istorice.

Am creat numai acest raport scratch; nicio modificare de produs/test/documentație versionată, niciun commit. Fără PG/browser/operator/provider/servicii, credentiale, citire mediu sau fișiere protejate; fără SOURCE rerun ori audit general. Reticle NOT_APPLICABLE pentru acest review static; Chisel BLOCKED_NO_GO. Riscul rezidual este proba reală afectată încă neexecutată, nu un finding demonstrat în delta de cod.
