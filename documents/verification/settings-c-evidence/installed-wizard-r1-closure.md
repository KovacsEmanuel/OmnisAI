# R1 — APPROVED_SOURCE_SCOPED: F01/F02 închise pe bytes exacți

## Verdict focalizat

**R1-F01 CLOSED_SOURCE_SCOPED. R1-F02 CLOSED_SOURCE_SCOPED. Niciun finding nou în delta cerută.** Verdictul privește numai remediile celor două findings originale; nu este audit funcțional repetat, acceptare a candidatului sau QA instalată. Reviewul original neschimbat își păstrează numai scope-ul original.

Cerință → consumer → risc → decizie: readback valid acceptat explicit → Wizard/query privat de draft → eroare/notice istoric după succes ori rehidratare prematură peste editările locale → închiderea F01/F02 de sursă; acceptarea produsului rămâne separată.

- **F01 — `web/src/features/engagement/Wizard.tsx:278–285`:** ambele alegeri fac `setNotice(null)` și `client.setQueryData(['private', 'draft', server.engagement_id], server)`. Cheia este identitatea readback-ului, nu `id` opțional. Discard păstrează guardul `isFullDraft`, încarcă explicit payload-ul și actualizează baza. Keep actualizează baza, fără `setForm` și fără scriere API.
- **Fără rehidratare prematură — `Wizard.tsx:92–110,177–197`:** Compare din ramura de alegere doar setează `server/phase/notice`, nu cache/form. Până la alegere, editorul și query-error rămân nemodificate. După alegere, aceeași identitate observată oprește efectul de hidratare; pentru alt ID acceptat, `saved.id` coincide cu noul cache, deci ramura care ar rescrie formularul nu este parcursă. GET eșuat restabilește `priorPhase`; nu există sincronizare cache pe catch.
- **F02 — `Wizard.tsx:191`:** «Server revision loaded. Choose explicitly whether to discard or keep your local edits.» este neutru și adevărat pe same-revision. Notice-ul de alegere dispare la ambele acceptări explicite.
- Implementarea TanStack Query instalată, citită strict pentru cauză (`web/node_modules/@tanstack/query-core/src/query.ts:312–326,849–864,928–935`), confirmă că setData emite succes și retrage `error` chiar dacă payload-ul este structural egal; nu este refetch sau write backend.

## Regresia afectată

`web/src/app/ReceiptRecovery.test.tsx:124–193` verifică ambele alegeri pe scenariul compus original: hidratat rev1 → editare → PUT pierdut înainte de stocare → Refresh cu GET proiecție reușit/GET editor 503 → Compare încă eșuat → Compare reușit → acceptare explicită. Sunt asertate:

- eroarea/alerta și bariera Save/Next rămân după GET eșuat și înaintea alegerii, inclusiv după Compare reușit;
- editarea locală nu este înlocuită la Compare; revizia/digestul serverului sunt exact cele originale, cu copy Loaded;
- numai după alegere query-ul exact este `success/error:null/data:revision`, alertele obsolete dispar, Keep arată Unsaved changes, Discard arată Saved revision1;
- un singur PUT în total prin ambele acceptări, fără implicit write/replay.

`ReceiptRecovery.test.tsx:54–62` verifică separat cheia `stored.engagement_id`, absența datelor pe cheia cu undefined, notice retras și Save ulterior separat. Nu am lărgit scenariile sau harness-ul.

## Snapshot exact și proveniență

- Bază: `4bbb774a791230c851597f876edff88abb1dd1d9`.
- HEAD: `7673066a0497c1432f8a6fdb519a106eb481e3cd`.
- Delta: exclusiv `web/src/features/engagement/Wizard.tsx` și `web/src/app/ReceiptRecovery.test.tsx`.
- SHA256 diff binar bază→HEAD: `3b75da0ea95b7c5dd19b3242df17cf9c93342643264c31f62427fa4735c27abf`.
- Wizard.tsx SHA256: `152882fef0ae40b618b2e7e774a8f8a7636428de9a8bc99b79d09d44948f9bc4`.
- ReceiptRecovery.test.tsx SHA256: `5f44eaa86de9552c98e640e03610a11b8ac5b777a37d0ff97a6725af2306292d`.
- Wizard.test.tsx SHA256: `a67138616702f0eb82819a0d42a7b678470763889578eaf3a6151000ec1b9e0f`, neschimbat bază/HEAD/working tree.
- Cele două fișiere schimbate sunt identice working tree/blob HEAD; verificate și după incidentul de mai jos. Tracked/staged diff gol, numai cele două fișiere protejate untracked preexistente.
- Raport original citit și hash verificat: `/home/kali/.hermes/cache/scratch/wizard-r1-review-gfrhci8m/report.md`, SHA256 `1b9040297c91e51d35ac0bb4af152c13379c1e044eee088f748d5e1de6ae7411`.
- Handoff citit și hash verificat: `/home/kali/.hermes/cache/scratch/wizard-r1-fix-wf8p1lea/handoff.json`, SHA256 `2fbf8b8c7d44ab108cf12231274c97633e35e0e9e66d8c93abe6a3014e7d6b7f`. `UNCOMMITTED_NOT_STAGED` din acel handoff descrie momentul autorului; bytes sunt acum în HEAD-ul revizuit.

## Dovezi existente citite, nu rezultate noi inventate

SHA-urile acestor loguri au fost comparate cu handoff-ul și conținutul relevant a fost citit:

- Comandă autor: `npm --prefix web test -- src/app/ReceiptRecovery.test.tsx src/app/Wizard.test.tsx`.
- Strict RED confirmat **6FAIL/27PASS, exit1**, sursa veche/testele finale; `/home/kali/.hermes/cache/scratch/wizard-r1-fix-wf8p1lea/red-confirmed.log`, SHA256 `6f14778319c66cef9cc66a489e0d6a1adc1276d1be0ae17576135b0442b16e02`.
- GREEN autor **33PASS, exit0**, bytes finali; `/home/kali/.hermes/cache/scratch/wizard-r1-fix-wf8p1lea/green.log`, SHA256 `e671438652a62b1886f7d93727a77260543b298d668a8f14f422391f87e2010b`.
- `PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin VITEST_MAX_WORKERS=2 make check-web`: **205 web + 6 tooling PASS**, contracts/types/lint/build/audit0, exit0 conform handoff/log citit; `/home/kali/.hermes/cache/scratch/wizard-r1-fix-wf8p1lea/check-web-workers2.log`, SHA256 `f6cdfeda4841cdccdd8e59aa2784bbbbe2696e4f469c852e9afa84bf48081bf1`.
- Parentul a raportat separat reproducerea originală 1FAIL și actual33PASS în mandat; nu atribui acele execuții reviewerului.
- **Default make check-web păstrează FAIL-ul istoric, exit2/4FAIL199PASS, cauza UNKNOWN.** Workers2 PASS nu îl înlocuiește.

## Incident de execuție / abatere de la mandat

La prima tentativă de creare a raportului, textul Markdown a fost inclus greșit într-un `python -c` shell double-quoted. Backtick-urile au produs command substitution în shell, inclusiv tentative neintenționate de rulare a comenzii npm de mai sus și make check-web. Acesta este un eșec al disciplinei read-only/no-rerun cerute, nu o nouă probă autorizată. Tool-ul a returnat timeout **exit124 după60s**, cu `make: *** [Makefile:234: test-contracts] Terminated`; multe tokenuri Markdown au produs command-not-found/permission-denied. Python-ul de creare nu a ajuns să producă raportul. Nu pot atribui exit/test-count ori succes acestor tentative: stdout-ul command substitution nu a fost disponibil ca log de test. Nu pot exclude că o tentativă a avansat până la build/audit/rețea npm înainte de timeout. Nu folosesc tentativele ca evidence și nu le-am relansat intenționat.

O citire de containment ulterioară a confirmat același HEAD, toate cele trei SHA-uri și diff tracked/staged gol; `ps` pentru make/node/npm/vitest/tsc/eslint nu a găsit procese supraviețuitoare. Nu exista raport closure creat. O primă comandă de containment a eșuat cu SyntaxError înaintea execuției corpului Python, apoi a fost corectată doar pentru citire. Acest raport unic este creat folosind argument quoting sigur și sigilat 0444. Incidentul nu schimbă concluzia statică F01/F02, dar trebuie păstrat în handoff; nu se poate pretinde că misiunea a avut zero tentative de test/full-gate.

## Limite / decizie părinte

Nicio implementare sau schimbare de fișiere repo, niciun commit/stage, serviciu, browser, instalare/retire, acces la profil vechi ori provider/model/target executat intenționat. Fișierele protejate `tempkey.txt` și `documents/Omnis_Notite_Originale.html` nu au fost citite ori modificate. Singurul artifact creat deliberat: acest raport scratch original 0444; posibile efecte generated/build/npm ale incidentului nu sunt revendicate drept inexistente.

QA reală pe artefact instalat/browser/API/PostgreSQL rămâne PENDING; visual/keyboard/screen-reader nu au fost verificate. Reticle NOT_APPLICABLE acestei execuții SOURCE; Chisel BLOCKED_NO_GO. Candidatul nu este acceptat prin raport; parentul adjudecă închiderea F01/F02 și aprobă separat QA/integrarea. Scope-ul funcțional neschimbat nu a fost reauditat.
