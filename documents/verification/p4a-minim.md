# P4a-minim → P2-live — registru curent

## Mandat și stare

Bază verificată: `a4367422ea84f67904451f1c8308c3a5991c08f3`, după checkpointul `d3580c4`. Delta concurentă este exclusiv tooling/documentație de dezvoltare; API/web/runtime/ops/Makefile sunt identice cu checkpointul. Schimbările altui autor și originalul `documents/Omnis_Notite_Originale.html` nu sunt preluate ori modificate. Nici `tools/development/ponytail.json` nu intră în această felie.

Operatorul a autorizat implementarea **P4a-minim, apoi P2-live**, un singur autor, reviewuri independente și QA pe consumerul real; **STOP înainte de P3**. P2-inert/G02-inert rămâne CLOSED_SCOPED la [dovezile sale](p2-integration-b06cm.md); probele neafectate se reutilizează, fără recertificare istorică. Acest registru nu este un plan concurent cu planul §7–8/§19.

**CURRENT:** primul increment local Settings este candidat SOURCE, **CHANGES_REQUESTED / NOT_ACCEPTED**, păstrat numai pe worktree-ul `work/p4a-169c9470b2`; nu este integrat în principal. P4a-minim IN_PROGRESS, native/PG/browser NOT_RUN. P2-live/faza2 integrală NOT_CLOSED. Analiza statică și testele SOURCE nu închid vreo poartă live.

## Autorizare pentru probele viitoare

- Provider `openai-codex`, model solicitat `gpt-6.1-sol`, effort solicitat `xhigh`; fără reducere tacită, schimbarea modelului sau fallback. Suportul efectiv se verifică la pin; REQUIRED nesuportat rămâne BLOCKED.
- Conectarea contului se face **de operator prin webul Omnis**, folosind fluxul OAuth nativ încapsulat; nici credentiale în chat/log/argv, nici adoptarea profilului personal Hermes/Codex. Contul concret este cel confirmat în acest flux, nu presupus din sesiunea de dezvoltare.
- Acord pentru conectare/verificări provider și inferență de produs cu date exclusiv sintetice, după controalele/reviewurile necesare. Acordul nu transformă config/readback în inferență validată.
- Operatorul nu cere plafon financiar strict. **30 USD este reper de monitorizare estimativă**, nu cap monetar garantat, preț de abonament sau cost zero. Usage observat, estimat și UNKNOWN rămân separate; un cost echivalent API, dacă poate fi calculat, este etichetat separat de debitul efectiv al contului Codex.
- Caps tehnice alese pentru campania P2-live: maximum **200 cereri model**, **32.768 output tokens per cerere**, **1.048.576 output tokens cumulat**, **300 s per cerere**, **3.600 s de execuție a campaniei**, maximum **un copil activ**. Sunt limite superioare, nu consum de urmărit; toate rolurile/auxiliarele/retryurile aparțin aceleiași contabilizări. Aplicarea efectivă la transportul Codex trebuie probată înainte de folosire; lipsa enforcementului este BLOCKED. Nu modifică limitele/granturile transportului inert ori testelor acceptate. Retry/fallback/auxiliare neadmise sunt interzise; rezerva VALIDATION se alocă prin ledgerul existent când este consumată de scenariul concret.
- Ținta oferită `http://0.0.0.0:5000/` este rezervată unei felii ulterioare de integrare/evaluare după accesul HTTP sigur din P3. **Nu este contactată în această felie**. OpenRouter și comparația de billing pe cheie sunt opționale, separat, nu al doilea provider obligatoriu.
- Fără rollout peste r1/P0, schimbări globale, push, upgrade Hermes/pin oportunist sau conectare de cont dintr-un test automat. Mediu nou, date/loguri private și cleanup exact al resurselor create.

## Produceri, consumatori și decizii înainte de cod

- UI existentă: `web/src/features/engagement/Settings.tsx`; Providers/Skills sunt placeholder, Runtime folosește Bootstrap. API-ul existent oferă session/Host/Origin/CSRF/no-store, nu rute provider. Reutilizăm shellul/clientul/contractele generate, nu admin Hermes în browser.
- API → LocalControl → supervisorul existent → **același RuntimeClient** → RuntimeHost este canalul de autoritate. DTO privat ≤3.600 bytes, frame control ≤4.096; canal Host ≤65.536. Browserul nu selectează URL, path sau profil Hermes arbitrar.
- RuntimeHost este actualmente inert. Settings cere mod management exclusiv față de execuție, acoperit de watchdog/lease/Stop/drain și fără inventar nativ READY fabricat. `CaseSlot` B05_INERT/hashul credential-free se păstrează; nu se relaxează ca bypass pentru contul live.
- Managementul nativ la pin oferă OAuth start/poll/cancel/logout și config save/readback. `model/set` main ignoră effort-ul; acesta se persistă/readback prin configurația nativă exactă. Nu se pretinde `xhigh` efectiv dintr-un HTTP200 sau din simpla salvare.
- `hermes serve --isolated` are și startup auxiliare (rooms/selftest/archive/local runtime/bootstrap). Este necesară o cale management-only minimală auditată, fără boot provider/model implicit. OAuth start poate dura peste exchange-ul local și poate produce504 cu worker încă activ: operație bounded asincronă pe ownerul existent, poll separat, fără deadline/grant mărit sau retry orb.
- Configurația DATA actuală și FinalModelRequest sunt Chat Completions-only. Codex nativ folosește `codex_responses`; este o extensie reală de contract/sink/serializer/admission, nu o schimbare de enum sau un bypass NO_MODEL. Se livrează după Settings local, pe snapshot/run nou.

## Primul increment admis

**Rezultat observabil:** operatorul salvează provider/model/effort explicit din Settings; API/control/RuntimeHost apelează managementul nativ privat și întorc readbackul exact, păstrat după reload/restart. Cele patru axe configured/authenticated/reachable/inference_ready sunt separate; înainte de OAuth/probă live nu se afișează autentificat sau inference_ready. Refolosim configul nativ ca sursă; orice persistență Omnis nouă trebuie justificată de primul consumer/recovery, nu migrare preventivă.

**Non-obiective ale incrementului:** login/inferență/target, catalog larg/editor, al doilea provider, live Responses, schimbarea probelor inerte. OAuth și catalogul read-only publicat urmează în aceeași felie P4a, nu sunt declarate livrate de acest increment.

**Perimetru:** Settings UI/client/DTO/OpenAPI, API settings route și handler supervisor/control, RuntimeClient/RuntimeHost și modulul management finit necesar, patch/manifest/pin/build nativ strict pentru management-only, testele afectate și comenzile existente. Fără framework, harness sau owner independent nou. Autorul poate propune restrângerea înainte de extindere; nu autorizează execuție nativă efectuală înainte de review.

**Acceptare:** RED→GREEN pentru save/readback și refuz invalid/oversized/foreign config; autentificare/CSRF; exclusivitate management/execuție și Stop/expiry; răspuns pierdut nu produce retry sau succes inventat; no personal fallback; max/max+1. Două reviewuri complementare pe snapshot exact, apoi prima probă reală bounded pe native instalat și UI/API/DB proprii. Fixture/SOURCE nu sunt native sau browser PASS. Canonical complet la frontiera finală, nu după fiecare helper.

**Rollback:** revert granular al codului; profilul/DB/credentialele externe nu sunt inversate de Git. Înainte de primul efect se fixează rooturile/identitățile proprii, before/after nesensibil și ownerul cleanup; datele păstrate, fără adopție a resurselor vechi.

## Dovezi

Discovery read-only pe baza indicată; APIs/limite inspectate în source-ul upstream fixat `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`. Python API3.13.15 și uv0.12.19 sunt disponibile. Node/npm ambientale nu sunt pinurile proiectului; se folosesc executabilele din toolchainul privat Node24.21.0. Nu s-au pornit DB/servicii/native/OAuth/model/target în discovery.

### Primul candidat și reviewurile — remedii înainte de native

[Autorul](p4a-first-author.json) fixează28fișiere; părintele a comparat toate hashurile și întreg inventarul schimbat.35SOURCE/83web și Ruff/mypy/build/contracte au output real, nu QA instalată. [Review normativ](p4a-first-review-norm.json) și [safety](p4a-first-review-safety.json) sunt CHANGES_REQUESTED pe același snapshot. [Reproducerea părintelui](p4a-first-parent-repro.json) confirmă constatările cu controalele originale, fără native/PG/provider; exit0 al reproducerelor înseamnă defect confirmat, nu PASS de produs.

| Finding | Decizie curentă |
|---|---|
| SAFETY-FIRST-F01/HIGH | OPEN: PUT poate începe după grant expirat. Refuz înainte de dispatchul efectiv, inclusiv după await-uri; un Save deja trimis rămâne in-flight/UNKNOWN până la readback/drain, nu atomicitate DB/filesystem inventată. Stop nu este confirmat înainte de drenarea writerului local. |
| P4A-NORM-F01 = SAFETY-FIRST-F02/HIGH | OPEN: configurația cu selecția corectă poate păstra fallback/aux/providers/delegation sau câmpuri agent/auth străine. Validare finit/exact înainte de readback/save; zero writer pe refuz. |
| SAFETY-FIRST-F03/MEDIUM | OPEN: anularea înainte de prima intrare în worker lasă receipt PENDING deși taskul s-a terminat. Finalizare în owner, fără resend. |
| SAFETY-FIRST-F04/LOW | OPEN, inclus în remediul mic: ACK numeric1 nu este boolean true; validare strictă și regresii. |

**Adjudecare arhitecturală a părintelui:** acceptăm numai ca direcție a acestui increment adaptorul management-only finit care folosește readerul strict și `save_config` native. Nu pretindem reutilizarea handlerelor HTTP `config_env`: GET stock elimină providerul, iar bootul stock lansează servicii auxiliare. Nu adăugăm alt motor de config, store sau supervisor; păstrăm pinul/entrypointul/ownerul și patchul minimal auditat. Această decizie nu aprobă codul cu findings și nu autorizează reimplementarea OAuth; următorul increment trebuie să refolosească fluxul nativ real. CLI/Compose normal încă nu montează/conectează RuntimeHost și `/state/provider`; această prerechizită trebuie implementată și verificată pentru livrarea utilizabilă, nu ocolită cu un demo.
