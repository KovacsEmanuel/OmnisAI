# Reviewer 1 — Settings A–D, exact-snapshot SOURCE review

**Verdict: CHANGES_REQUESTED.** Două blocante concrete, reproduse prin App/callerii existenți. Nu este verdict de QA runtime ori de acceptare vizuală.

What this change does: Mută detaliile reale ale testului sub rândul modelului, separă Test de expandare și păstrează recuperarea în context. Compactează confirmările/catalogul și distinge testul salvat de metadata curente și eligibilitatea pentru assignments.

## Identitate și limită

- Bază: `1f47183b0a3a055a80a5cf57ffbdff5271b58d4b`; snapshot primar: **`a488b2611b96fbb6edc4d4c4bbd0c2de21a45b90`**. Reviewul include contractul `f1a845f`, D `9fc2969` și A–C `a488b26`; metadata `fd0b557` nu devine audit global.
- Cele opt blobs/SHA din `/home/kali/.hermes/cache/scratch/settings-finalization-freeze.json` corespund HEAD și checkoutului. SHA256 manifest: `2c987656006294bf83173f3f618d7366504c05aa9e15d5244cbe436100faa8fd`. Helperul D, citit din același HEAD: `web/src/features/engagement/SettingsModels.ts`, blob `f574cdf378bce672ae526c5519a0773f4b9f8628`.
- Citite mandatul/canonul UI afectat, AGENTS/CONTRIBUTING/team-slice, CURRENT/status și registrul existent; cele cinci fișiere UI, cele trei teste Settings afectate, callerul E2E și definițiile/consumatorii API relevanți. Pentru F01 am urmărit numai proiecția backend FINISHED/UNKNOWN, fără audit sau editare backend.
- Repo tracked/index curat la început și la sfârșit; același HEAD. Cele două untracked protejate au rămas necitite/neatinse. Fără build, web/dist, browser, PG, operator, provider/model I/O, servicii, commit sau push.

## Must fix

### R1-F01 — MEDIUM — Un rezultat remote UNKNOWN, deja terminal local, blochează permanent orice test nou

**Loc:** `web/src/features/engagement/SettingsModelsPage.tsx:92–103`, consumat la `:356–364` și `:405`.

**Reproducer:** Latest-entry și GET al aceleiași operații întorc o proiecție validă `state=FINISHED`, `result_state=UNKNOWN`, `finish_reason=OWNER_LOST`, cu reviziile actuale și catalog/capabilități valide. La intrare, noua hidratare selectează această operație. Apasă `Read test status`: readbackul confirmă din nou FINISHED/UNKNOWN. Rândul nu mai oferă Test, nu oferă Cancel, ci numai Read; toate celelalte teste/consimțământul Save & connect rămân blocate de `activeTest`. Un nou tab repetă selecția din latest.

**Rezultat real SOURCE:** `terminal: FINISHED, result: UNKNOWN, cancelVisible: false, testVisible: false, readVisible: true`. Reproducerul R1-F01 eșuează după readbackul explicit, cu zero writes. Controlul FINISHED/COMPLETED permite consimțământ nou nebifat; controlul NEEDS_RECONCILIATION rămâne corect blocat și are recuperare/Cancel.

**Criteriu încălcat:** arhitectură §5, `documents/Omnis_MVP_Architecture.md:231`: după reconcilierea locală este permis un test nou explicit chiar dacă outcome-ul remote rămâne UNKNOWN, păstrând istoricul/consumul incert. FINISHED este diferit de NEEDS_RECONCILIATION. Backendul chiar produce această combinație: `model_test_runtime.py:138–143`, `:877`, `:914–923`. Delta adaugă `observed.result_state === 'UNKNOWN'` la blocarea lifecycle și recuperează orice astfel de rezultat drept operație activă; readbackul nu poate înlătura blocajul.

**Remediu minim:** separă incertitudinea rezultatului remote, care rămâne vizibilă/persistentă, de operația locală încă activă/neconfirmată. Un FINISHED confirmat trebuie să permită un Test nou cu acord nou, fără reluarea secvenței vechi, ștergerea UNKNOWN ori relaxarea blocării NEEDS_RECONCILIATION/erorii de readback. Adaugă cazul în testul Settings existent; nu schimba backendul sau autoritatea.

### R1-F02 — MEDIUM — După schimbarea providerului, feedbackul altui catalog ascunde eroarea listei curente

**Loc:** `web/src/features/engagement/SettingsModelsPage.tsx:335`, `:388–389`; consumer `SettingsModelWizard.tsx:25`, `:69–72`, `:120–127`.

**Reproducer:** Ambele conexiuni au chei salvate. Deschide Add models implicit pe OpenRouter; Continue admite un catalog OpenRouter PENDING. După răspunsul inițial, Back → schimbă Provider la OrcaRouter → Continue. Citirea locală OrcaRouter răspunde valid FAILED/SCHEMA_UNSUPPORTED. `catalogFeedback` rămâne calculat după `wizard.provider` al deschiderii (OpenRouter), nu după providerul curent intern. Ramura `catalogFeedback || ...` suprimă complet eroarea/cauza OrcaRouter și afișează `Loading models…` plus controalele operației OpenRouter în lista OrcaRouter. List aria-busy este deja false. Guardul existent nu trimite un al doilea refresh, dar nici nu explică acest fapt în noul context.

**Rezultat real SOURCE:** `currentProvider: orcarouter, actualRead: FAILED/SCHEMA_UNSUPPORTED, visibleStatus: Loading models…`; eroarea și cauza curente lipsesc. Un singur write, refreshul inițial OpenRouter; niciun efect provider real. Înainte de schimbare, recuperarea operației OpenRouter este corect vizibilă în propriul wizard.

**Criteriu încălcat:** mandat §3.C și §5, cazul 3 — progres/eroare corecte lângă lista afectată, fără blocare aparent inexplicabilă, inclusiv schimbarea conexiunii. UI/UX `:161–163` cere stări curente coerente și cauza inspectabilă. Identitatea feedbackului și suprimarea lui în cardurile exterioare folosesc providerul inițial, în timp ce query key/API au deja noua conexiune/revizie.

**Remediu minim:** leagă alegerea feedbackului și suprimarea duplicatelor de conexiunea/revizia curentă a wizardului, nu de providerul de la deschidere. Păstrează recuperarea operației vechi separat, explicit contextualizată; nu o folosi pentru a înlocui statusul listei noi. Păstrează guardul fără resend și selecțiile. Regresie în callerul Settings existent pentru pending provider A → provider B cu catalog failure.

## Dovezi și acoperire scoped

- Proba proprie: fișiere doar în `/home/kali/.hermes/cache/scratch/settings-review1-a488b26/`. Comandă:
  ```sh
  NODE_ENV=test /home/kali/.local/share/omnis-toolchains/bin/node /home/kali/OmnisAI/web/node_modules/vitest/vitest.mjs run --config /home/kali/.hermes/cache/scratch/settings-review1-a488b26/vitest.config.ts --reporter=verbose
  ```
  **Exit 1; 2 PASS controale, 2 FAIL reproducers, 1.97s**, log original `repro.log`. Sunt HTTP doubles SOURCE pe App, componente și decodere reale, nu QA API/PG/provider. Prima invocare fără NODE_ENV=test a eșuat înaintea produsului cu React.act; păstrată separat în `preflight-node-env-failed.log`, apoi corectată conform manifestului npm existent.
- Probele existente 109 afectate/27.58s și lint/types au fost citite, nu rerulate. Nu certifică cele două scenarii lipsă. Nu am duplicat suita web a părintelui sau canonicalul.
- A: expandarea este un buton nativ distinct de Test, fără apeluri în handler; dovezile existente verifică tastatură, multi-model și ținta Cancel. F01 blochează acceptarea recuperării complete.
- B: confirmări compacte temporare, erori/pending inline persistente și măsură anti-suprapunere sunt prezente în SOURCE; nu emit verdict estetic/geometrie reală.
- C: placeholderul este limitat la aceeași conexiune/revizie/catalog, selecțiile rămân pin-uite, iar callbackul terminal validează identitatea operației înainte de invalidarea citirilor locale. F02 este ruptura concretă de context din caller.
- D: explicația catalogului păstrează rezultatul exact, capabilitățile/reviziile, caps și assignments; nu am găsit relaxare a eligibilității sau refresh/retest implicit în această deltă. FAILED/METADATA_UNAVAILABLE și cauza upstream UNKNOWN rămân fapte distincte; acest review nu certifică remedierea upstream sau incidentul supervisorului.

**Decizie:** CHANGES_REQUESTED pe exact snapshotul de mai sus. Developerul desemnat remediază minimal cele două cazuri, părintele reproduce/adjudecă, urmează affected checks și re-review focalizat înainte de build/QA reală. Niciun fișier din repo modificat; doar config/probă/loguri/raport în scratch și un symlink scratch către dependențele existente.

Neexecutat: build/QA browser–API–PG, screenshoturi/acceptare vizuală, canonical și efecte operator/provider; Reticle NOT_INTEGRATED, Chisel BLOCKED_NO_GO.
Risc rămas: blocajul de retest după UNKNOWN și feedbackul catalogului legat de providerul greșit; cauzele upstream/supervisor rămân UNKNOWN, nu remediate aici.
