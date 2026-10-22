# QA independentă — focus Settings pe consumer instalat real

**Verdict: PASS_INSTALLED_FOCUS_SCOPED pentru cele 3 cazuri cerute; nu închidere T1 sau tracking.** Părintele adjudecă QA-SETTINGS-FOCUS-01. O observație exclusiv de captură full-page la 320px rămâne neadjudecată, separat de rezultatul funcțional.

## Identitate și limite

- Produs frozen: `4a18f443bd9d21e0c606459d42d67204b1dda6d7`; Main metadata-only: `a20cc59faccea51fe8ea440325a7223bdd8852d2`.
- Bundle original: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1-settings-artifacts/bundle-web-focus-secure`.
- SHA-256 release.json: `d01bd9eb17e16e6d26b6efb418b9f402008c73812b4f5da68ed5cdbfcf7ad924`; format3 / `t1-provider-settings` / schema `0014_provider_settings`; toate cele 10 payloaduri verificate. Originalele 0555/0444 și hashurile lor sunt neschimbate la final. Main web/dist este byte-equal pe toate cele 5 fișiere web.
- API wheel: `ca2096d466c0b8ec4a31ccb26cf31b43458c77ee08f626384824a4fda271dcae`; CLI wheel: `3cf775e962b85716542207af48f05be38396ef7e4aba078ffa339d2e2f7e0f9e`.
- Singurul root cu efecte: acest director `t1q-focus`; copie bundle privată 0700/0600, CLI wheel într-un venv separat. PATH fixat la toolchain + binarele sistemului. uv0.12.19, CPython3.13.15; browserul executat: Playwright1.63.0 / Chromium153.0.8010.12, cache existent, fără download.
- Origine instalată: `http://127.0.0.1:48766`; instanță `a6271523-19e3-4b9d-b650-5efc43013d76`; proiect OCI unic `omnis-local-72e69b3309e64b599f009ec165efd856`.
- Fără Vite, backend fals, owner alternativ, restart, adopție vechiQ/r1/operator, provider/model/target traffic, chei personale, global install, push sau T2. Aprobările API/CLI neschimbate nu sunt reauditate/extinse.

## Preflight și primul eșec păstrat

Root ABSENT și bind real48766 verificate înainte de creare. CLI help general/start/install/install-image/stop/pair, modulele din venv și egalitatea surselor CLI din wheel cu Main au fost verificate. Parserul real a validat cele10 payloaduri; controlul negativ a folosit lipsa manifestului. Producer/oracle: răspuns real `route.fetch` → hold finit12s → `route.fulfill({response})`, fără JSON sau status inventat; CAS din două taburi reale. Fiecare fază relevantă este observată după două requestAnimationFrame.

**Primul preflight a eșuat exclusiv în oracle-ul negativ al harnessului:** `_manifest` intern ridică `FileNotFoundError` pentru manifest lipsă, nu `ReleaseError` al boundary-ului public de install. Originalele `evidence/library-preflight.{command.json,stdout,stderr}` sunt păstrate. Corecție restrânsă: verificare explicită `FileNotFoundError`, tentativă distinctă `library-preflight-corrected.*`, exit0; niciun install/start/PG efect înainte de corecție. Un ciclu harness-only, apoi progres real pe produs; fără retry orb sau deadline mărit. Nu s-a repetat proba browser.

## Rezultate reale

Comenzi și ieșiri originale private în `evidence/*.command.json`, `.stdout`, `.stderr`:

- `install --bundle <newQ>/bundle`: exit0.
- `install-image`: exit0; tag unic, nu tag comun0.1.0.
- `start --no-open --port 48766 --json --startup-timeout 120 --cleanup-timeout 90`: exit0 / READY, generația1; `status --json`: exit0 / READY.
- `pair`: exit0 prin helperul existent PTY; cod numai în memorie → stdin browser, fără raw stdout salvat, argv sau chat.
- Browser `node <newQ>/journey.mjs focus`: exit0,8.902s, browser/context closed; **65 verificări PASS,0 FAIL**.

O singură cheie sintetică nefuncțională introdusă prin formular, apoi selecție default validă prin formular. GET canonic real: UNLOCKED, exact o conexiune revizia1, secret write-only/input gol. Nicio rotire sau revocare.

| Caz | Dovadă instalată | Rezultat |
|---|---|---|
| Retained | Tab nativ de la Validator override → Save → Enter; răspuns PUT real200 ținut după commit; GET readback real200 și refetch real200 ținute separat, fiecare peste două cadre; activeElement rămâne Save, nativeDisabled=false/aria-disabled=true; Enter repetat, click repetat și requestSubmit în fiecare fază nu admit al doilea PUT; focus păstrat după readback/refetch | PASS; exact1PUT,2GET held; selecție revizia2 |
| Moved | După submit, operatorul mută focus la linkul Providers; focus rămâne acolo în PUT/readback/refetch și final, fără furt de focus | PASS; exact1PUT,2GET held; revizia3 |
| Stale | Al doilea tab citește revizia3; primul tab avansează legitim la4; al doilea face PUT cu expected_revision3 și primește real409/REVISION_CONFLICT; Reload GET real200 este forwarded apoi ținut; Save.nativeDisabled=true în stale+pending reload; click/requestSubmit nu admit PUT nou; GET canonic ridică stale și păstrează selecția legitimă | PASS; staleTabPUT1 separat de mainAdvancePUT1; fără409 fabricat |

Reload final: zero PUT nou, niciun mesaj Saved transferat din cache. Total6 PUT HTTP:1cheie +1selecție inițială +1retained +1moved +1avans legitim +1stale refuzat.

**PG real, tranzacție READ ONLY / exit0:** schema0014,1rând connection_revision,4rânduri selection_revision,5receipturi command; payloadul ultimei selecții coincide exact cu default din GET canonic; selecția stale refuzată nu există. Original: `pg-readback.*`; verdict: `pg-verdict.json`. Datele finale sunt sintetice și păstrate, nu provider validat/inferență.

## DOM, focus, capturi și erori

- Focus nativ și `:focus-visible` adevărate în toate cele3 faze retained; outline solid2px; cursor not-allowed; culorile/background busy aria corespund unui control native-disabled, inclusiv hover.
- Capturi originale: `screens/busy-desktop.png`, `busy-320.png`, `final-desktop.png`, `final-320.png`; inspecție tehnică vizuală efectuată pe toate4. Secret gol verificat înainte de fiecare captură. DOM-uri nesensibile în `evidence/dom-*.txt`.
- Desktop: pending lizibil, focus ring vizibil, fără overlap/clipping de formular evident; final NOT_VERIFIED, input gol și fără Saved după reload. La320, pending/Save lizibile și DOM scrollWidth≤innerWidth+1 în busy/final; numele lung al modelului depășește lățimea vizibilă internă a inputului, nu lățimea paginii.
- **OBS-FULLPAGE-SKIP-LINK-01 — UNCERTAIN_SCREENSHOT_ONLY:** în captura busy320 apare «Skip to content» peste o parte din textul Inference; în final320 nu apare. Capturile sunt fullPage după scroll/focus/resize; fără geometrie live a skip-linkului păstrată, nu se poate separa defect runtime de compoziția full-page cu un element fixed poziționat offscreen. Nu este declarat defect de focus confirmat și nu este ascuns printr-un PASS vizual global. Părintele adjudecă dacă necesită un reproducer separat; nu s-a relansat/restartat instanța pentru a produce o captură verde.
- `pageErrors=[]`, externalRequests=[] și zero hold expirat. Console2 erori HTTP așteptate:401 înainte de pairing și409 din controlul CAS; nu excepții JS. Nu se revendică «console zero».
- GET/public DOM/localStorage/sessionStorage și numai logurile noii instanțe fără canary. Raw secret/session/cookie/CSRF/pairing nu sunt păstrate în evidence. Literalul sintetic există numai în harness, necesar introducerii și scanării, nu în logurile produsului.
- Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Nu certificare estetică, WCAG, screen-reader sau toate browserele.

## Stop și cleanup fizic

`stop --json --shutdown-timeout 120`: exit0,8.795s; `status --json`: exit0 / STOPPED, generația2. Dovadă fizică separată în `evidence/cleanup-readback.json` și răspunsurile originale:

- Exact cele3 CID-uri din jurnalul acestei tentative: docker inspect exit1/No such object.
- Exact network ID înregistrat live: network inspect exit1/not found.
- Forwarder PID760595/start_ticks14818237: /proc absent.
- Listener48766 absent prin ss; connect_ex111; IPC sockets absente în ambele directoare proprii.
- PGDATA, vault/vault.pending, master.key, receipts, logs, imagini și date păstrate; inode/mode/size/mtime vault+master identice înainte/după Stop. Nicio citire a valorii master/key, prune, down-v sau kill de proces necunoscut.

**Noile resurse sunt fizic absente; nu STOPPED dedus doar din port sau exit0.** VechiulQ nu a fost pornit/oprit/adoptat; o execuție read-only `--help` a binarului său CLI a fost folosită la orientarea inițială, fără helper cu defaults vechi sau efecte lifecycle.

## Fișiere și predare

Au fost create numai în newQ: copia bundle, venv, XDG roots/data produse de lifecycle, `qa_local.py`/`run_browser.py` reutilizate local, `journey.mjs`, evidence private,4capturi, raportul prezent și `independent-focus-installed-evidence.json`. Main și bundle original nemodificate; untracked HTML preexistent neatins. Fără commit în checkoutul comun; părintele integrează numai concluzia adjudecată.

Nu s-au repetat vechea matrice85, recovery, breadth CAS, revoke, autounlock/LOCKED, restart sau suitele sursă deja trecute. Consumer Test model/refresh absent pe acest artefact; NOT_RUN și niciun efect provider/model/target. **T1 rămâne ÎN LUCRU; închiderea focusului și observația capturii aparțin părintelui.**
