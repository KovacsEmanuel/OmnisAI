# R1 independent — B04 English-copy caller correction

**Verdict: APPROVED_SOURCE_SCOPED. Findings blocante: niciuna.**

Admitere SOURCE pentru proba reală existentă B04, nu PASS de browser/API/PG și nu acceptare a canonicalului. Reviewer independent read-only, fără relație de autorat cu developerul precedent.

## Snapshot și limită

- Repository: `/home/kali/OmnisAI`.
- HEAD revizuit: `6dbaec54812c94b5d906d849145f9c42977788c5`.
- Părinte/bază corecție: `b116c1082f263eaad509207fa32bb1a6e72d40cb`.
- Bază originală complete34: `94f48fd7e7f0a418a876c6db69ad48b62971a2bd`.
- Delta comisă: numai `web/tests/e2e/b04.mjs`, 16 linii înlocuite, fără schimbare de număr de linii (190).
- B04 SHA256 înainte: `cc0b0133a5de2ff37f20b672eb0dd13bf460b0cdac10d6c29a7a32685ab281a9`.
- B04 SHA256 după: `36ee916a94915caa71c4464818f69b17c4fcf9f4b9b2c88ed92f702fc3d8daa8`.
- Git tracked worktree/index curate la început și la readback. Cele două căi untracked protejate au fost numai listate de Git; nu au fost deschise, modificate sau staged.

ORIENT minim: README/CURRENT, CONTRIBUTING, rândurile relevante din implementation-status și contractul team-slice. CURRENT T1 reprezintă acceptarea anterioară, nu înlocuiește mandatul activ PromptA Settings C. Fără PromptB ori audit recursiv al produsului/reviewurilor vechi.

## Cerință → consumer → control → decizie

Cerința este alinierea callerului B04 cu UI-ul englez deja aprobat. Consumerul este `runB04`, importat și apelat de `web/tests/e2e/run.mjs:12,179–180`, inclusiv etapele before/after. Riscul este selectorul vechi care oprea călătoria înainte de primul Save sau slăbirea incidentală a testului. Controalele sunt identitatea byte-exact și compararea literalelor cu produsul real; rezultatul permite părintelui proba B04 reală, nu o aprobă retroactiv.

| Criteriu | Constatare verificată |
|---|---|
| 15 selectori obiectiv | Exact `Objective / Brain instructions`, conform `Wizard.tsx:243` și `copy.ts:8`. |
| 3 așteptări default | Exact `Assess the authorized Web/API surface within the selected profile.`, conform `Wizard.tsx:16`; B04:65,89,103. |
| Radio focused | Exact `Focused test`, B04:101, conform radio `Wizard.tsx:238–241`. |
| Produsul englez deja aprobat | `Wizard.tsx` și `copy.ts` sunt byte-identice cu commitul PromptA `212a3acaea4e20b78059ec85e6fb38710c3999e4` și cu worktree/HEAD. Nu există editare de produs în corecție. |
| Numai cele trei înlocuiri | Transformarea înainte→după și inversa după→înainte sunt byte-exact. Multiplicități 15/3/1; suprapunerea explică 16 linii modificate. Inversa reproduce atât b116, cât și baseline94f. |
| Textul utilizatorului | Linia B04:7 este byte-identică: `const objective = '  Focus 🧪\nRespectă spațiul.  ';`. Sufixele `\nFirst editor` (4 utilizări) și `\nSecond editor` (3) sunt păstrate. Nu este tradus textul utilizatorului. |
| Forța testului | 40 apeluri `check`, 22 apeluri `assert.*`, 3 `secretChecks`, toate neschimbate. Inversa exactă dovedește lipsa altor modificări, nu numai egalitatea contoarelor. |
| Invariante | Payloaduri, validare whitespace, CAS409, 422, refuzuri Host/Origin/CSRF/ref, reload/restart, receipt/digest/revizii, focus/mobil, secrete și Start disabled rămân neschimbate. Fără timeout nou, aserțiune relaxată sau cale condițională nouă. |
| Caller trace | Toate cele 7 fișiere `.mjs` E2E verificate; zero literal UI vechi din cele trei înlocuiri sau `Evaluare generală`. Textul custom românesc rămâne intenționat date de utilizator. `run.mjs:16` păstrează timeoutul 15000ms. |

## Identitate complete34 — control bounded, nu reauditare

- Manifest: `/home/kali/.hermes/cache/scratch/uif10-fJpmj2/final34-freeze.json`.
- SHA256 măsurat: `d70dc32374718a770c794758e3be36faf488d5fefb50b095b570641c053e9f7f`.
- Candidate ID recalculat din JSON canonic `{base,files:[{path,sha256}]}` cu path/keys sortate și separatori compacți: `9f4fccff3f59ec5b41f43d938d3b710fbe26c57387f2689d9c3a84f26e84595f`.
- Exact 34 căi unice; setul este egal cu diff-ul baseline94f→HEAD. Pentru fiecare: bytes, SHA256 și git_blob din manifest corespund HEAD și worktree.
- Cele 33 intrări anterioare sunt identice cu b116 și cu manifestul final33; identitatea manifestului anterior verificată direct: `3d5f4af077f5f698b3f26c3b18bb323fda41cd041ccd05cc89a0a024cfdca79e`. Nu au fost recitite reviewurile anterioare.
- `web/dist/omnis-web.json`: SHA256 `e2d646e4bcd898ff8bb9621c23e3ce055bd83b8f7a4e507e4935d19c45641fe1`; manifestul de build și toate cele 4 fișiere enumerate corespund hashurilor actuale și manifestului precedent. Fără rebuild.
- Manifestul freeze păstrează eticheta pre-commit; aici verdictul este legat de HEAD-ul comis confirmat și de bytes identici, nu de acea etichetă istorică.

## Dovezi executate/citite

- `git status --short --branch`, `git rev-parse HEAD`, `git rev-parse HEAD^`, `git show --stat --oneline HEAD`, diff și `git diff-tree`: exit0; singura cale comisă este B04.
- `node --check web/tests/e2e/b04.mjs`: exit0, inclusiv readback final.
- `git diff --check b116c1082f263eaad509207fa32bb1a6e72d40cb..HEAD`: exit0.
- Control inline Python stdlib de identitate/hash/transformare/calleri: exit0; toate condițiile de mai sus evaluate pe bytes reali. Niciun script/verifier persistent nou.
- Reutilizate, nu rerulate: logurile SOURCE autorizate `uif10-fJpmj2/source-red.log` și `source-green.log`. RED: objective selectors/default/radio false, copy→Wizard true; GREEN: toate patru true, numere 15/3/1. Manifestul consemnează exit1→exit0. Acestea sunt SOURCE_ONLY, nu browser/API/PG.

## Dispoziție și pas următor

**Părintele poate admite consumerul existent `test-b04-e2e`**, cu build real și fixture PostgreSQL nouă proprie, aceleași aserțiuni/limite și cleanup/readback propriu; apoi canonicalul obligatoriu neschimbat la frontiera de integrare. `Makefile:261–263` leagă targetul de `build-web` și testul E2E real existent selectat `-k b04`. Gate-fit, preflights, bugetul și execuția aparțin părintelui. Nu este necesar un nou harness, rerun al SOURCE/unit196/SettingsUI4 ori redeschiderea aprobărilor core neschimbate. Corecția caller-only nu schimbă autoritate/auth; un review independent focalizat este proporțional, fără a înlocui cele două aprobări core precedente.

Contextul de execuție furnizat de părinte, fără citire de loguri private, rămâne: canonical1 `scn1-6pbg90` FAIL2/drained, E2E9PASS/1FAIL pe selectorul B04 vechi înainte de Save; CLI/release ulterioare NOT_RUN. UI1/2/3 FAIL și N01 LOW neblocant sunt păstrate, iar UI4 anterior nu este substitut pentru B04. Niciunul nu este promovat prin acest verdict.

## Fișiere și limite

Creat numai acest raport în scratch propriu; mod final 0444, SHA256 transmis separat. Fără repo edits, stage, commit, servicii, DB, browser real, rețea, provider/spend, credentiale, stare privată de browser sau fișiere protejate. Reticle NOT_APPLICABLE pentru review SOURCE; Chisel BLOCKED_NO_GO, fără probe.

Nu am rerulat scope-uri neatinse, B04 real ori canonicalul. Riscul rămas este comportamentul de integrare/runtime încă neprobat pe corecția curentă; SOURCE admission nu înseamnă B04/overall PASS.
