# Reviewer 2 — Settings web / decoder / privacy / auth / a11y

**Verdict: CHANGES_REQUESTED**, limitat la noul consumer SOURCE Settings. Motiv blocant: decoderul refuză readback valid al producerului existent. Nu este gate closure, acceptare installed, browser sau T1.

## Identitate și scope

- HEAD `91bb74849eb1e628a264c3c0df18d652b9fabd6f`, tree `a39b1485a497c8c158122286110448d88a312cb3`, față de baza `c19440a357866c162672be5400e08df4636b585f`.
- Worktree curat la intrare și la final. Manifestul `settings-form-freeze.json` SHA256 `407f64b24d4903d145b8e41f8248e0dd91fbedd707eedcd6c874040dc1f2aa8a`, lista exactă de 17 căi și SHA256 pe bytes au fost verificate programatic. Manifestul bundle-final SHA256 `f1c5a58446db9e7d86d9904728e568a33f7f64f270022904f20dbe33de6338fe` verificat.
- Traseu citit: `Settings → ProviderSettings → client → providerKeys decoder → /api/v1/settings/providers`; `useBrowserSession/readPrivate` pentru auth/epoch. API/owner/DTO consultate numai pentru semantica datelor consumate, nu re-audit al seifului aprobat. Diff-ul API/src, API/tests și manifest/lock API față de bază este gol.
- CLI/bundle consultate numai pentru identitatea noului profil și separarea de consumerul legacy; lifecycle/mount/Stop aparțin reviewerului 1.

## Findings concrete

### Decoderul respinge prezența independentă de enabled/LOCKED — același finding al părintelui, consolidat, fără ID concurent

- **severity:** MEDIUM — blocant pentru acceptarea acestei felii.
- **file:line:** `web/src/shared/api/providerKeys.ts:26` (și fixture-ul negativ incompatibil cu producerul din `web/src/shared/api/providerKeys.test.ts:13`).
- **reproducer:** `logs/parent-revoked-producer.json`, produs de părinte prin `ProviderSettingsOwner.view`, conține conexiune revision2, `enabled=false`, `credential_present=true`, `vault_status=UNLOCKED`. DTO-ul public permite aceste axe independente; ownerul `provider_key_service.py:145–170` proiectează separat `row.enabled` și `vault.contains(...)`. Decoderul efectiv aruncă INVALID_RESPONSE. Reprodus suplimentar prin App/Settings: GET inițial valid cu conexiunea activă → click **Revoke locally** → PUT cu receipt autentic revoked+present și command_id exact → **Outcome unknown**, fără Saved; **Recover exact receipt** primește același receipt valid → **Receipt not confirmed**, mutațiile rămân disabled, PUT total exact1. După reload, și current GET cu aceeași stare persistentă este respins. Aceeași condiție inventată refuză și `LOCKED` global cu altă conexiune având încă `credential_present=true`: bucla producerului poate seta status global LOCKED când o referință lipsește, fără a rescrie bitul present al celorlalte conexiuni. Aceasta este aceeași rădăcină, nu un finding separat.
- **violated criterion:** readback/recovery al producerului real, contractul tipizat public și separarea enabled/revoked, prezență locală și verificare/reachability; frontendul nu poate inventa invariantă care face imposibil Revoke→readback.
- **minimal remedy:** păstrează validarea strictă de tipuri/chei/UUID/revisions/bounds, dar elimină implicațiile suplimentare `present ⇒ enabled && UNLOCKED`. Nu schimba semantica ownerului/seifului aprobat și nu acorda autoritate din presence. Ajustează fixture-ul negativ greșit și adaugă regresii cu DTO real pentru revoked+present, mixed LOCKED/present și formular Revoke→GET→receipt/reload fără PUT automat.

### Focusul se pierde prin remontarea formularului după Save selection

- **severity:** LOW — regresie a11y SOURCE, separată de blockerul decoderului.
- **file:line:** `web/src/features/engagement/ProviderSettings.tsx:106`.
- **reproducer:** formular cu selecție persistentă revision1; focalizează butonul **Save model selection**, salvează și livrează receipt+GET corecte cu revision2. `key={JSON.stringify(view)}` distruge formularul și butonul focalizat; proba componentei confirmă `oldButton.isConnected=false`, `document.activeElement === document.body` după readback. Nu există restaurare echivalentă. Nu afirm comportament de browser/screen reader real.
- **violated criterion:** păstrarea focusului și traseului de tastatură pentru UI afectată, fără redesign; actualizarea persisted truth nu trebuie să abandoneze focusul operatorului în body.
- **minimal remedy:** păstrează resetarea la sursa persistentă, dar conservă/restaurează controlul echivalent atunci când readbackul remontează controlul focalizat, fără a fura focusul dacă operatorul s-a mutat între timp. Regresie componentă pentru save cu schimbare reală de revision.

## Probe SOURCE executate

PATH fixat la `/home/kali/.local/share/omnis-toolchains/bin`; observat Node `v24.21.0`, npm `11.19.0`; TMPDIR owned `/home/kali/.hermes/cache/scratch/ot1-0zxf62th`.

1. Din `src`: `npm --prefix web test -- src/app/ProviderKeySettings.test.tsx src/shared/api/providerKeys.test.ts` — **15 PASS**, Vitest 2.20s, exit0. Original: `logs/reviewer2-settings-form-tests.log`. Aceste teste trec deși fixture-urile lor nu reprezintă corect starea revoked+present; nu sunt dovadă de Revoke real reușit.
2. Din `src`: `NODE_ENV=test node web/node_modules/vitest/vitest.mjs run --config /home/kali/.hermes/cache/scratch/ot1-0zxf62th/logs/reviewer2-vitest.config.mjs --reporter=verbose` — **6 PASS**, 1.99s, exit0. Original final: `logs/reviewer2-source-final.log`; sursa: `logs/reviewer2-source-probe.test.tsx`. PASS înseamnă aserțiuni executate, inclusiv reproducerea defectelor existente, NU remedii GREEN.
   - auth loss în timpul mutației: input detașat gol, răspuns tardiv nu repopulează cache și nu anunță Saved;
   - HTTP401 real simulat pe noul GET: expirare sesiune, pairing, input nesubmis gol la unmount, cache privat absent, zero PUT;
   - default exact + clear Brain: payload complet/null, GET truth și sursa persistentă actualizată, un singur PUT;
   - pierdere focus la revision nouă, confirmată SOURCE;
   - decoder/revoke/receipt invalid pe fixture-ul autentic al părintelui, un singur PUT;
   - observație nepromovată ca finding: un secret **nesubmis** rămâne în input la click Revoke, dar nu apare în acea cerere; nu am confundat asta cu echo/storage ori cu submitul formularului cheii.
3. Prima tentativă a probei proprii: **2 FAIL/2 PASS**, exclusiv matcher inexistent `toBeConnected`; original `logs/reviewer2-source-probe.log` păstrat. Corectat numai testul owned la `isConnected`, fără editare produs. Rularea intermediară 5 PASS este păstrată separat în `logs/reviewer2-source-probe-final.log`; finalul de mai sus are6teste.

Citire SOURCE suplimentară: ID pending este UUID-only în sessionStorage, fără payload/secret; load/recover folosesc numai GET, nu autoput; CAS409 intră în stale până la reload explicit; cheie1–512ASCII, model1–256ASCII exact, output1–65536; default obligatoriu și override-uri nullable; răspunsuri strict own-keys și command ID exact. Secretul nu intră în React Query/state payload cache/storage/log din noul traseu. Labels native, fieldset/legend și output live există; focusul de mai sus rămâne defect concret. Nu s-a identificat alt blocker în această limită, dar bugul de decoder invalidează aprobarea readbackului end-to-end.

## Fișiere și limite

Nicio modificare de produs, Git, canon sau skills; fără commit. Create numai raportul/proba/config/logurile R2 în rootul owned `logs/` și symlinkul `logs/node_modules → ../src/web/node_modules` pentru rezoluția dependențelor existente. Nicio instalare sau dependență nouă. Fixture-ul părintelui a fost numai citit.

Nu am executat DB, Docker/build, servicii, installed/browser/provider, canonical sau auditul vault anterior; nu am citit credentiale, .omnis/r1, profiluri globale ori HTML protejat. Reticle **NOT_INTEGRATED**; Chisel **BLOCKED_NO_GO**. Fără aprobare estetică/WCAG/runtime/T1; findings necesită adjudecarea părintelui și remediere de developer pe bytes noi.
