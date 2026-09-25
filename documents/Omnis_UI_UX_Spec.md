# Omnis — specificație UI/UX v2 · propunere

**Revizie după referința utilizatorului · Surface: Operate, cu inspector contextual · Aprobarea vizuală este în așteptare**

[DESIGN.md](../DESIGN.md) este sursa tokenurilor; [prototipul offline](Omnis_UI_Prototype.html) este o demonstrație navigabilă, nu frontendul implementat. Conținutul sintetic este etichetat DEMO și nu poate executa requesturi, autentificări sau scanări. Limbajul UI MVP: engleză pentru etichete tehnice consecvente, documentație română; nu implementăm i18n complet, dar textele rămân centralizate.

## 0. Referința primită și felia de design

**Propunere în lucru, nu aprobare vizuală.** Referință furnizată de utilizator: `/home/kali/OTPen/omnis/brand/omnis-cockpit-v5.html`, SHA-256 `d0545bda58284f5eacd595de395e161efe0d5ba083ffa94dd2423d8a084ed2e7`. Fișierul extern rămâne nemodificat; nu importăm scripturile, conținutul de securitate sau configurațiile sale. Referința este un template vizual, nu contractul de domeniu Omnis.

**Surface primar: Operate; secundar: Inspect.** Păstrăm negrul cald, textul ivory/taupe, accentele nisipii, navigarea globală compactă deasupra contextului engagementului, subtabs și panouri cu contur dublu discret. Nu preluăm hero-ul, statistici fără sursă, procente de confidence/precision inventate, animațiile și fonturile remote. Contrastul informației esențiale și țintele de 44px au prioritate față de microtextul din template.

Adaptări obligatorii:

- Cockpit: context/run/Stop persistent, decizii pentru operator, findings accesibile direct, lucru activ și Brain stream într-o compoziție asimetrică. Fără sidebar permanent care consumă spațiul central; drawer pe mobil păstrează Stop echivalent.
- Fără brain graph, canvas de noduri sau panouri plutitoare draggable. Brain stream: evenimente și decizii scurte, actor/task, motiv rezumat, rezultat și link către obiect/dovadă. Nu expune chain-of-thought și nu deduce starea runului din conversație.
- Fără council, jurori, voturi sau buton de confirmare manuală a unui finding. Investigator → validator separat → verdict persistent admis de serviciul probatoriu, pe oracle/controale/evidence. Validatorul nu este un vot LLM suficient pentru CONFIRMED.
- Findings confirmate separate de candidates/inconclusive. Detaliu deschis din listă: impact, severitate motivată, precondiții, reproducere, evidence redactate, controale, decizia validatorului, limite, remediere și retest. Lipsa actuală a dovezilor nu rescrie verdictul istoric.

**Contractul feliei:** adaptăm prototipul existent, cu cockpit și finding detail reprezentative; celelalte ecrane rămân probe funcționale, nu redesign complet aprobat. Fișiere admise: prototip, testele sale, DESIGN/tokenuri, această specificație și indexurile/probele aferente. Fără frontend/backend de produs, noi dependențe UI, conturi, date reale sau trafic target. Nu creăm un baseline concurent.

**Acceptare tehnică:** navigare și detaliu utilizabile; DEMO permanent; stări fără succes optimist; regresiile Stop/modal/drawer/focus păstrate; fără overflow de pagină la 320/390/1024/1280/1440; screenshoturi inspectate, inclusiv detaliu; zero requesturi externe. Verificare: `python tests/documentation/browser_check.py --include-documents --output <scratch>/browser-check.json`, `python scripts/render_docs.py --check`, `python -m unittest discover -s tests/documentation -v`, plus lint/export tokenuri. Baseline înainte de schimbare: 95 checks browser, 16 teste documentare trecute, zero erori JS/requesturi externe.

Rollback: reverturile commiturilor acestei felii, fără schimbări de DB/runtime; referința externă nu este atinsă. Aprobarea vizuală și acordul de implementare rămân ale utilizatorului. După această iterație se stabilește în arhitectura/planul existente structura fișierelor și pornirea prin executabilul `omnis`, nu se începe scaffoldul.

## 1. Anatomia consolei

```text
                  ( Omnis | Engagements · Workspace · Settings )
┌ engagement / target / exact run ───────── run + sync ─ Pause · Stop ┐
│ Overview · Findings · Target map · Investigations · Reports · Setup │
├─────────────────────────────────────────────────────────────────────┤
│ heading / action + scope snapshot / identity / budget state         │
├───────────────────────────────────────┬─────────────────────────────┤
│ Needs your attention                  │ Brain stream                │
│ Confirmed findings → inspect          │ actor filter / event cursor │
│ Active / blocked tasks                │ short decision + result     │
│ Coverage & limitations → Map          │ link → task / finding       │
└───────────────────────────────────────┴─────────────────────────────┘
                centered workspace · maximum 1280px
```

Navigare în două niveluri: global sus (Engagements, Workspace, Settings), apoi contextul engagementului. Pe mobil, navigarea contextuală și Settings intră în drawer. Nu există agent, council sau graf ca obiect primar în nav; taskul/ipoteza și dovada sunt obiectele de lucru. Overview arată workerii în contextul taskurilor, nu o pagină de avataruri. În prototip, Skills/Runtime rămân scurtături tehnice; în produs sunt sub Settings.

Topbar menține numele engagementului, run state și sync state. Stop rămâne accesibil în toate paginile și pe mobil când un run este activ. Selecția contextului nu mută accidental controlul pe alt run: butonul indică exact runul activ dacă pagina consultă un snapshot vechi.

## 2. Route map și placement

| Rută planificată | Conținut primar | Inspector / acțiune |
|---|---|---|
| `/engagements` | Tabel: nume, țintă, status, ultima actualizare; search și filtru | New engagement sus-dreapta; empty cu un singur CTA |
| `/engagements/new` | Wizard cu pași verticali și form central | Rezumat sticky desktop; Save draft permanent, Next/Back; nimic nu pornește |
| `/engagements/:id/setup` | Revizie/draft, scope și context | Edit numai oprit; active → motiv + link Stop, fără editare mascată |
| `/engagements/:id/overview` | Context compact, blocaje/aprobări, findings și taskuri; Brain stream lateral | Preflight/Start sau Pause/Stop; stream cu actor/cursor/motiv/rezultat/link; fără KPI decorativi |
| `/engagements/:id/map?tab=surfaces` | Tree host/path, tabel metodă/path/auth/sursă/stare | Operație selectată: params, observations, request/response, related |
| `/engagements/:id/map?tab=coverage` | Matrice suprafață × identitate × familie, filtre | Click celulă → procedură, test, control și evidence; numitor/snapshot vizibile |
| `/engagements/:id/investigations` | Tabel/queue taskuri cu ipoteză, rol, skill, attempt, blocaj/verdict | Timeline investigator→validator; reason, budget, results și stop task dacă suportat |
| `/engagements/:id/findings` | Confirmate implicit, filtre clasă/severitate/status remediere | Dovadă, impact, limite, remediere, retest; candidates nu sunt amestecați |
| `/engagements/:id/reports` | Snapshoturi/version history și limite | Generate snapshot, HTML/JSON download, print; nu rescrie raport vechi |
| `/settings/providers` | OpenRouter și Codex: stări și model/config | Save/test/delete ori device OAuth; consum AI explicit |
| `/settings/skills` | Catalog, search, lifecycle și readiness independente | Files/diff/review/publish; pachet/revizie/digest/evaluare vizibile |
| `/settings/runtime` | Pin Hermes, tool inventory, executori, compatibilitate | Diagnostic sanitizat; fără shell, env reveal, auto-upgrade |
| `/settings/data` | Storage/retention, export/delete/backups, data policy | Operații distructive confirmate cu impact; restore nu autorulează |

URL păstrează filtre și ID de selecție, **niciodată secrete, request bodies sau tokenuri**. Datele reale vin prin API și Query cache; refresh reîncarcă snapshotul. Preference neconfidențiale de densitate pot fi locale; nu persistăm dovezi/credentiale în browser.

## 3. Setup în cinci pași

1. **Target & permission:** nume, obiectiv, owner/autorizație, fereastră; origins ATTACKABLE/VISIT_ONLY/BLOCKED, căi și excluderi. Preview al regulilor, fără requests pentru validarea de sintaxă.
2. **Application context:** seed URLs, workflowuri prioritare, obiecte test, reguli `(rol/tenant × obiect × operație → ALLOW/DENY/UNKNOWN)`, proveniență/revizie, import OpenAPI revizionat. Cerințele BOLA nu se ascund într-un free-text opțional.
3. **Identities (optional):** anonymous valid; persona/rol/tenant, tip auth și secret handle; Verify login cu efecte și scope explicite. Assisted browser deschis numai după aprobarea scopeului dependențelor, fără browser personal.
4. **Rules & budgets:** efecte, praguri, request/time/storage, rezervă validare, data policy/provider/model și catalog admis. „Cost necunoscut” separat de limita tehnică; nu afișăm quota Codex inventată.
5. **Review & preflight:** erori/blocaje grupate cu link înapoi la câmp; revizie/model/identități/riscuri/costul posibil rezumate. Save draft nu face inferență. Start cere preflight actual și confirmare explicită a rulării.

Backendul este autoritatea finală. Un wizard bifat nu garantează că între timp auth/lease/model/policy nu s-au schimbat. La 409 păstrăm editările locale și arătăm conflictul; nu suprascriem automat.

## 4. Fluxurile critice

### Start / approvals / Stop

- Start: buton disabled cu explicație dacă gate incomplet; la click se cere preflight real, apoi dialog de rezumat. Comanda primește ID; UI arată PENDING până la readback.
- Approval: panou persistent în Overview și badge număr real în nav; detaliu cu acțiune/efect/target/body redactat/persona/epoch/revizie/expirare. Confirmarea este exactă și o singură utilizare. Expirarea/invalidate se vede chiar dacă dialogul era deschis.
- Stop: click imediat, fără modală care întârzie oprirea; 202 afișează STOPPING, nu STOPPED. Orice dialog/drawer care face topbarul inert conține o acțiune Stop echivalentă pentru runul activ; aceasta închide overlay-ul și trimite aceeași comandă idempotentă. Dacă rețeaua cade, mesaj persistent „Stop not acknowledged” și calea locală de oprire din runbook; nu toast verde.
- Pause: PAUSING până la drenarea efectelor, apoi PAUSED; explică diferența față de Stop. Resume face preflight și poate intra în NEEDS_RECONCILIATION.
- Lucrul deja expediat nu este prezentat ca anulat. Efectele UNKNOWN au detaliu și acțiune de review; nu există retry automat dintr-un buton generic „repară”.

### Map → investigație → dovadă

Surfaces/coverage sunt taburi ale Map. Treeul selectează contextul, tabelul selectează operația, inspectorul nu pierde identity/snapshot. Parametri grupați query/path/header/cookie/body; valorile redactate. Sursa JS/OpenAPI este INFERRED până există observație. Un header/banner nu apare la Findings.

Click pe coverage cell arată: denominator key, procedură/revizie, precondiții, acțiunile executate, controlul și evidence. `tested_no_issue` este descris „No issue demonstrated by this procedure”, nu „Safe”. Un filtru nu schimbă numitorul global fără etichetă.

Investigația arată ipoteză, motiv de prioritizare, worker/attempt, skill digest și dependențe. Timeline separă investigator, validator și serviciul de verdict. Nu afișăm deliberări interne/chain-of-thought; afișăm decizii scurte și rezultate observabile.

### Findings → report → retest

Listă implicită numai CONFIRMED. Candidates/REJECTED/INCONCLUSIVE rămân în Investigations și pot fi deschise explicit. Finding detail: impact demonstrat, severitate motivată, precondiții, pași, evidence, limite, remediere. Confidence nu este severity.

**Compoziția de review:** rând expandabil cu severitate, titlu, metodă/rută, identificator, investigator → validator și verdict. Nu există Confirm/Dismiss/vot în listă. La expandare: context run/scope/identity/epoch/regulă, apoi impact + reproducere + baseline/replay/control în coloana principală, cu decizia validatorului și verificările oracle într-un panou distinct. Sub 1024px panourile se stivuiesc; verdictul rămâne disponibil înaintea detaliilor lungi. Linkul din Brain stream deschide findingul, nu o listă fără selecție.

Disponibilitatea **actuală** a evidence este separată de completitudinea **la momentul verdictului**. În prototip, selectorul DEMO AVAILABLE/MISSING/TRUNCATED/CORRUPT/DELETED ascunde transcripturile indisponibile și dezactivează preview-ul cerințelor de replay, dar nu rescrie verdictul istoric. Textele/transcripturile sunt sintetice, nu output al unui executor. Produsul nu va avea acest selector de scenarii: starea vine din API.

Retest cere run/autorizație/buget proaspăt și afișează FIXED doar după precondiții valide/control. Auth expirat produce RETEST_INCONCLUSIVE. Raportul nou citează probe noi; cel vechi rămâne neschimbat. Dedup conservator cu occurrences expandabile, nu dispariția „duplicatelor” fără audit.

### Providers și Skills

Settings minim poate fi catalog read-only. Settings complet adaugă editor/diff/review/publish fără a schimba layoutul. Readiness provider are patru axe: configured/authenticated/reachable/inference_ready. Test inference este separat și potențial facturabil. Cancel login și logout sunt operații distincte, cu readback.

Editorul de skill este form text/file tree controlat, nu filesystem browser. Publicarea arată exact digest/revizie și spune „Applies to new runs”; toate taskurile aceluiași run păstrează catalogul fixat. Disable blochează selecția în runuri noi; revocarea de urgență a unui release activ trece prin Stop/fencing. Erorile de path/reference/dependency sunt lângă fișierul relevant.

## 5. Stări și copy obligatorii

| Stare | UI corect | UI interzis |
|---|---|---|
| Nu există date | Empty + următoarea acțiune | Numere demo în baza reală |
| Încărcare | Skeleton bounded și aria-busy | „0 findings” înainte de răspuns |
| Readiness insuficient | Motiv și gate lipsă | Start funcțional cu backend absent |
| SSE deconectat | Stale, ultimul cursor/timp, reconnect | Indicator live verde |
| Model cost necunoscut | Unknown + motiv | 0.00 inventat |
| Scope/protocol nesuportat | Unsupported/not tested | No issue / passed |
| Auth expirat | AUTH_BLOCKED, identitatea afectată | Negative test / fixed |
| Evidence lipsă | MISSING/TRUNCATED și ce nu se poate verifica | Replay disponibil fictiv |
| Stop trimis | STOPPING + verificări | STOPPED pe răspuns 202 |
| Limită atinsă | LIMITED, teste rămase și motiv | „Assessment complete” fără limite |

## 6. Accesibilitate și responsive

Țintă WCAG 2.2 AA pentru fluxurile implementate: semantică, keyboard, focus vizibil/neobscurat, contrast, reflow și mesaje de status; verificarea automată nu certifică singură conformitatea.[9]

- Toate controalele au label/accessible name; tab order natural și skip link. Nu shortcut global cu o singură literă pentru Stop sau alte efecte.
- Dialoguri/drawers cu focus containment, Esc și restore; erori form cu summary focus. Live region polite agregat, nu spam la fiecare eveniment.
- Touch targets minimum 44px; niciun text esențial sub 14px desktop/16px form mobil; nu tabele gigantice înghesuite pe mobil.
- Container maximum 1280px fără sidebar permanent. Cockpit două coloane la ≥1024, stack sub 1024. Map: ≥1440 inspector lateral; 1024–1439 inspector sub tabel; <1024 nav drawer și detaliu full-width. La 320/390 controalele rămân accesibile, cu scroll local etichetat pentru tabele.
- Zoom 200%, prefers-reduced-motion și high contrast/forced colors verificate pe fluxurile de bază. Statusurile au text, nu doar nuanță.
- Raport print A4, text minimum 12pt, referințe la evidence lizibile, fără sidebar/acțiuni de aplicație.

## 7. Contract frontend și acceptance checklist

Componente comune: AppShell, RunControls, StatusLabel, EmptyState, ErrorPanel, DataTable, ScopeEditor, IdentitySelector, PreflightChecklist, ApprovalDetail, EvidenceViewer, CoverageMatrix și SkillReleasePanel. Radix acoperă dialog/tabs/menu; nu înlocuim elementele native utile. Nu adăugăm bibliotecă mare de charts sau IDE editor înaintea unei nevoi.

Frontendul nu cunoaște tokenul admin Hermes, secretul proxy, credentialul AI sau cheia seifului. Target evidence este text escapate, nu `dangerouslySetInnerHTML`. Schema API generată, erorile tipizate și entity revision alimentează UI; nu inferăm starea runului din streamul conversației.

**U01** Create/edit/reload/restart, field errors, dirty-state și conflict între două taburi.

**U02** Start blocked/preflight/pending/live; Stop pending/disconnected/stopped, fără succes optimist.

**U03** Approval expirat sau policy revizuit în timp ce panoul era deschis este refuzat și explicat.

**U04** Tree/tabel/coverage/inspector folosesc același snapshot/identity și permit trecerea la evidence.

**U05** Candidate nu apare ca finding; negative fără dovadă nu crește coverage; report+retest păstrează istoricul.

**U06** Provider/Skills readiness independent, cancel/logout/readback și release immutable.

**U07** Keyboard complet, focus/dialog, contrast, mobile 320/390 și desktop 1280/1440, zoom/reduced motion.

**U08** Payload HTML/JS/SVG ostil, linkuri externe și screenshot invalid nu execută/încarcă resurse în browserul operatorului.

**U09** SSE replay/resync/stale și refresh nu dublează counters; numerator/denominator și N/A se păstrează.

**U10** DEMO-ul este separat vizibil și tehnic: fără API real, secrets, fetch către țintă, metrici salvate în datele produsului sau confuzie cu teste de integrare.

## Sources

[9] https://www.w3.org/WAI/WCAG22/quickref — How to Meet WCAG (Quickref Reference)
