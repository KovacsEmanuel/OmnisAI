# Reviewer2 — rereview focalizat UI-READBACK-F01 / UI-FOCUS-N01

**Verdict: APPROVED_SCOPED — SOURCE/jsdom și identitatea artefactului construit**, exclusiv cele două findings și delta web `91bb748 → c9eba400`. Nicio regresie concretă nouă identificată în această limită. Nu este aprobare browser/installed, închidere T1 sau integrare; adjudecarea și QA consumerului real rămân la părinte.

## Snapshot și proveniență

- Checkout izolat: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/src`, curat la intrare și după probe.
- Bază: `91bb74849eb1e628a264c3c0df18d652b9fabd6f`; HEAD: `c9eba4009291dede9cb034f259bd8b4f35bf6a98`; tree: `4a21cd04bac75c6c16b6805fadd998780e14e6f1`.
- Remedii: `ff8b08ab9f8bfd687bd8e4a5f90695cdc907650d`, apoi `c9eba4009291dede9cb034f259bd8b4f35bf6a98`.
- Raportul original CHANGES_REQUESTED este păstrat nemodificat: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/logs/reviewer2-settings-form-review.md`; SHA256 `ace20a589d728b6b1ca00efa45b9bcafa70c92cda3bb1dec264e4a73672ec6eb`. Dispozițiile de mai jos închid explicit reproducerii lui, nu îi rescriu istoricul.
- Freeze: `logs/web-fixed-freeze.json`, SHA256 `2091692f13d41be00bb92b585a62bf750dcda470858db1d01df8b2feb65f1cb4`. Verificate programatic HEAD/tree, lista exactă de 5 căi, blob/size/SHA256 pentru fiecare și hashes ale dovezilor declarate.

## Dispoziția fiecărui finding

| Finding | Dispoziție | Cod, criteriu și probă |
|---|---|---|
| UI-READBACK-F01 | **RESOLVED_SCOPED** | `web/src/shared/api/providerKeys.ts:22–28` elimină numai implicația necontractuală `present ⇒ enabled && UNLOCKED`. Tipurile booleene, own-keys exacte, UUID/identitatea command_id, reviziile safe-integer, bounds, unicitatea provider/connection și selecțiile stricte rămân. `providerKeys.test.ts:11–18` acceptă fixture-ul producerului și mixed global LOCKED/present; testele negative continuă să refuze readback incompatibil. `web/tests/provider-key-revoked.json` este byte-identic cu `logs/parent-revoked-producer.json`, SHA256 `f7354bb55eb40667e9698bae26b041662c5c37a9ca4de4e3fd75d1f9b6f58476`. `ProviderKeySettings.test.tsx:156–212` verifică Revoke → receipt/current → reload/remount și recovery receive-only pentru lost reply/wrong receipt/invalid current, exact un PUT. Revoked+present nu devine conexiune eligibilă, iar reachable/inference rămân NOT_VERIFIED. |
| UI-FOCUS-N01 | **RESOLVED_SCOPED** | `web/src/features/engagement/ProviderSettings.tsx:106–109,131` păstrează butonul Save în afara subarborelui keyed, asociat nativ prin `form="provider-model-selection"` / `id`. Formularul keyed continuă resetarea autoritativă a câmpurilor și override-urilor; nu există restaurare imperativă care să fure focus. `ProviderKeySettings.test.tsx:121–154` verifică revision1→2, același nod Save și focus conservat; controlul negativ mută operatorul pe Providers înainte de răspuns și îl păstrează acolo. Reload revision3 elimină draftul/override-ul nesalvat fără furt de focus sau PUT suplimentar. |

Cele cinci fișiere efectiv inspectate sunt: `web/src/app/ProviderKeySettings.test.tsx`, `web/src/features/engagement/ProviderSettings.tsx`, `web/src/shared/api/providerKeys.test.ts`, `web/src/shared/api/providerKeys.ts`, `web/tests/provider-key-revoked.json`. Nicio altă cale nu diferă față de baza originală. Nu cer refactor, feature nou sau schimbarea producerului aprobat.

## Probe independente pe bytes curenți

PATH fixat la `/home/kali/.local/share/omnis-toolchains/bin`; TMPDIR privat `/home/kali/.hermes/cache/scratch/ot1-0zxf62th`; numai dependențele Node existente.

1. Din `src`: `npm --prefix web test -- src/app/ProviderKeySettings.test.tsx src/shared/api/providerKeys.test.ts --reporter=verbose` — **23 PASS / 2 fișiere, exit0**, 3.11s. Log original: `logs/reviewer2-web-fixed-tests.log`. Fetch-ul este simulat; proba este SOURCE/jsdom, nu API/PG/browser real.
2. Verificare directă read-only a bindings — **exit0**; rezultat original `logs/reviewer2-web-fixed-bindings.json`. Verificate toate cele 10 payloaduri ale noului bundle și manifestul web; web-ul bundle-ului este byte-identic cu `src/web/dist`. Manifestul `bundle-web-fixed/release.json` are SHA256 `9ef854c6d2cca95a81bae032b9e7667e5c067517a40ed73f2b40da5173b63616`, format3/profile `t1-provider-settings`/schema `0014_provider_settings`. Toate payloadurile nonweb sunt byte-identice cu bundle-final; manifestul și payloadurile originale sunt intacte. Diff API/CLI/ops este gol.
3. Rebuild independent numai Vite, din `src/web`: `NODE_ENV=production node node_modules/vite/bin/vite.js build --outDir /home/kali/.hermes/cache/scratch/ot1-0zxf62th/reviewer2-web-fixed-rebuild` — **exit0**, 476ms. Toate cele 4 fișiere generate (HTML/JS/CSS/notice font) sunt byte-identice cu noul bundle. Manifestul web separat a fost verificat la punctul 2; nu pretind că această comandă execută întregul script npm build. Log original: `logs/reviewer2-web-fixed-rebuild.log`. Warning informativ: outDir extern nu este golit; directorul a fost verificat absent înaintea buildului. Nu am modificat `src/web/dist` sau bundle-ul.
4. `git diff --check 91bb748 c9eba400` — **exit0**. HEAD și worktree curat reverificate după teste și rebuild.

Dovezi anterioare numai citite: RED F01 include eșecul fixture-ului autentic și traseelor Revoke; RED N01 reproduce pierderea focusului în pozitiv, cu negativul operator-moved trecut. Logul final al developerului înregistrează 141 teste web trecute și buildul. Acestea nu sunt prezentate drept rerulări proprii ale întregului gate.

## Scope neschimbat, fișiere create și limite

- Reviewer1 lifecycle/profile **APPROVED_SCOPED se reutilizează numai pe bytes/scope neschimbate**. Originalul `logs/reviewer1-settings-form-profile-review.md`, SHA256 `e06d132140f355961bcab9a9f6d17fe1faa724c5d683156a8aa8b8280fc43552`, este intact. Nu l-am reauditat și nu îi extind aprobarea asupra noului web.
- Create numai acest raport, `logs/reviewer2-web-fixed-tests.log`, `logs/reviewer2-web-fixed-bindings.json`, `logs/reviewer2-web-fixed-rebuild.log` și directorul privat `reviewer2-web-fixed-rebuild/` cu cele 4 rezultate Vite. Nicio editare de produs/canon/skills, niciun commit, nicio modificare a rapoartelor/bundle-urilor originale.
- Fără PG, broad CLI, servicii, installed, browser, provider, rețea de produs sau canonical rerun; fără credentiale, `.omnis/r1`, profiluri globale, HTML protejat ori push. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Nu certific browser real, screen reader, estetică sau T1 complet.
- AICI: cele două remedii sunt implementate / SOURCE PASS_LOCAL_RECORDED / review **APPROVED_SCOPED**; acceptarea/integrările ulterioare și QA reală admisă aparțin părintelui. Lipsa unei închideri T1 globale nu este finding împotriva acestui increment.
