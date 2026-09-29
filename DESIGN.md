---
version: alpha
name: Omnis Operator Cockpit
description: Consolă locală de investigație, cu proveniență vizibilă și control explicit al efectelor.
colors:
  primary: "#C7BAA7"
  secondary: "#B8AEA1"
  neutral: "#0B0C0A"
  surface: "#131412"
  elevated: "#191B18"
  text: "#EEE9E1"
  border: "#726D62"
  divider: "#30312C"
  selected: "#2A2C27"
  focus: "#D6C9B6"
  danger: "#F28E7F"
  dangerBg: "#301E1B"
  warning: "#E7B56C"
  warningBg: "#30271B"
  success: "#C7BAA7"
  successBg: "#2A2C27"
  info: "#A2BAD0"
  infoBg: "#202930"
typography:
  h1:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 1.75rem
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 1.25rem
    fontWeight: 500
    lineHeight: 1.4
  body-md:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 14.5px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 0.8125rem
    fontWeight: 600
    lineHeight: 1.45
  code:
    fontFamily: "Geist Mono, Liberation Mono, Consolas, monospace"
    fontSize: 0.8125rem
    fontWeight: 400
    lineHeight: 1.6
  display:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 60px
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  engagement-title:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 40px
    fontWeight: 500
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  metric:
    fontFamily: "Geist, Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 36px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.035em"
rounded:
  sm: 8px
  md: 10px
  lg: 14px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  focus-ring:
    backgroundColor: "{colors.focus}"
    height: 2px
  input-border:
    backgroundColor: "{colors.border}"
    height: 1px
  separator:
    backgroundColor: "{colors.divider}"
    height: 1px
  app:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.text}"
    typography: "{typography.body-md}"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
  panel-elevated:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text}"
  button-primary:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    padding: 12px
    height: 44px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.pill}"
    height: 44px
  button-danger:
    backgroundColor: "{colors.dangerBg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.pill}"
    height: 44px
  nav-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.primary}"
    rounded: "{rounded.pill}"
  metadata:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: 44px
  status-warning:
    backgroundColor: "{colors.warningBg}"
    textColor: "{colors.warning}"
  status-success:
    backgroundColor: "{colors.successBg}"
    textColor: "{colors.success}"
  status-info:
    backgroundColor: "{colors.infoBg}"
    textColor: "{colors.info}"
---

## Overview

**Surface primar: Operate / Monitor; secundar: Inspect.** Omnis prioritizează stadiul engagementului, deciziile operatorului și lanțul observație → acțiune → dovadă → verdict. Antetul amplu și metricile cerute explicit urmează compoziția referinței; nu sunt înlocuite cu o consolă minimalistă generică.

**VISUAL_ACCEPTED — prototip `df17a29`:** utilizatorul a acceptat direcția vizuală după iterațiile respinse. Referința `omnis-cockpit-v5.html` și proveniența sunt în UI/UX §0. Negru cald, ivory/taupe, accent nisipiu, capsule și double-bezel; compoziția/densitatea se păstrează la portare, nu numai culorile. Fără brain graph/council sau tab Chains. Amendamentul G-PATH permite numai timeline bounded în finding inspector; extensia cere verificare/aprobare vizuală separată și nu schimbă acceptarea df17a29. Tema light a aplicației rămâne post-MVP; raportul imprimabil este light. Prototipul rămâne DEMO, nu aplicație, iar acordul de pornire este separat.

## Colors

`primary` marchează acțiunea principală și selecția, nu „securitate garantată”. Statusurile folosesc **text plus semn/etichetă**, niciodată numai culoare. UNKNOWN, unavailable și zero sunt stări diferite. `border` este pentru contururi interactive; `divider` numai pentru separatoare neesențiale. Focus vizibil de 2px, offset 3px, în `focus`. Preview-urile evidence nu moștenesc HTML/CSS de la țintă.

Nicio informație esențială nu folosește opacitate redusă în loc de contrast. Butonul Stop rămâne cu contrast verificat, nu dezactivat estetic în timpul reconectării. Expirarea conexiunii se explică prin text; încercarea Stop poate afișa „transmitere nereușită”, nu „oprit”.

## Typography

Geist și Geist Mono urmează tipografia referinței. Prototipul include local subseturile Latin/Latin-ext în `documents/assets/prototype-fonts.css`, cu SIL OFL 1.1 și proveniență/checksums alături; browserul nu cere fonturi unui CDN. Fonturile de sistem rămân fallback. Sans pentru operațiuni, mono pentru URL, ID, metodă HTTP, hash și evidence. Numere tabelare în coloanele cantitative. Licența aparține autorilor fontului, nu produsului Omnis.

Body desktop 14.5px, mobil/form input 16px; metadata minimum 12px. Dashboard display 40–60px, titlu engagement 40px (30 pe mobil), headinguri auxiliare 28/20px, metrici 36px (32 pe mobil). Această scară înlocuiește restricția anterioară prea severă asupra antetului/statisticilor. Print minimum 12pt. Zoom 200% nu ascunde Stop sau acțiunile formularului.

## Layout

- Container centrat de maximum 1180px, padding 32px desktop/16px mobil. Trei suprafețe: Home/Dashboard global, Engagement și Settings. Capsula globală de 60px este comună; taburile engagementului sau Settings apar numai în contextul lor. Fără sidebar permanent. Controale minimum 44px; capsulele vizuale mai mici nu reduc suprafața clicabilă.
- Dashboard: antet amplu + target/new-engagement; Needs your review; patru carduri statistice; pulse compact; bento Recent engagements cu card principal pe două coloane și card de creare pe una. Valorile sunt derivate, nu filler.
- Overview: now-bar/stadiu și checks; Needs you; cinci metrici Confirmed/Critical/High/Coverage/Endpoints; Top findings + Severity în raport 1.5:1; Budget & gates + Run snapshot dedesubt. Gap 16px și panouri aliniate pe rând. Brain stream rămâne în tab propriu. Endpoints și matricea sunt sub Coverage; Candidates și Setup sunt acțiuni secundare, nu alte taburi principale.
- <1024px: drawer cu grup contextual, dashboard într-o coloană, detaliu full-width; Stop în topbar persistent. În afara engagementului topbarul este o bandă compactă cu identitatea runului activ, fără taburi de țintă. Tabelele derulează local, niciodată întreaga pagină.
- 320–600px: acțiuni pe două rânduri dacă este nevoie; wizard într-o singură coloană; finding/evidence detail stack. Nu ascundem verdictul, identitatea, snapshotul sau motivul blocajului pentru a câștiga spațiu.

Spacing pe multipli de 4px. Metricile și donutul de 128px sunt componente cerute, cu count/numitor/snapshot explicite. Dashboard central selectează engagementul, nu se substituie lui. Skills/Runtime apar numai sub Settings. Nu adăugăm precision/confidence fără definiție, model tiers sau tab Chains. Setupul mode/obiectiv, rosterul, path timeline și editorii versionați refolosesc aceste componente; sunt contracte funcționale noi, nu aprobare vizuală automată. Copy-ul fixture-ului și controalele de simulare nu sunt cerințe de produs aprobate. Proveniența și legătura la backend sunt în `documents/Omnis_UI_UX_Spec.md`.

## Elevation & Depth

Double-bezel real: înveliș de 5px, raze 14px exterior / 10px interior, contur ivory subtil, core de 24px. Fără glow sau animații decorative. Separatoare și fundaluri delimitează streamul/evidence; nav are umbră ambientală discretă. Un singur overlay modal activ; revenire de focus la un control vizibil. Când topbarul devine inert, overlay-ul conține Stop echivalent și identitatea runului. Resize-ul închide modul modal și mută focusul în workspace; Esc nu anulează aprobări deja trimise.

## Shapes

Radii 8–10px pentru input/evidence/stream și 14px pentru panouri/dialoguri. Capsule pentru topnav, butoane și statusuri, conform referinței; nu pentru containerele de conținut. Un icon numai dacă ajută orientarea, cu accessible name; simbolul Omnis este decorativ. Fără emoji de status, grafuri sau animații decorative.

## Components

- Shell: landmark nav/main, skip link, engagement selector, breadcrumb, status sync și Stop/Pause/Start în poziție stabilă.
- Table: header semantic, sort button cu aria-sort, selecție explicită, paginare server-side; nu virtualizăm înainte de a demonstra nevoia și accesibilitatea.
- Form: label vizibil, hint, eroare legată prin aria-describedby, rezumat erori cu focus; save draft separat de Start. Dirty-state înaintea părăsirii formularului.
- Inspector: Summary / Evidence / Related / History; dovezi redactate implicit, download raw explicit cu avertisment, fără render HTML activ.
- Approval: țintă, metodă/operație, identitate/epoch, efecte, argumente redactate, scope revision, expirare; „Aprobă această acțiune” și „Refuză”, fără always approve.
- Run controls: Start deschide preflight+confirmare; Stop se trimite imediat, idempotent, apoi STOPPING; Pause arată PAUSING până la drenare. Resume arată noul preflight. Succesul nu este optimist.
- Toast doar pentru feedback neesențial; erorile, auth blocks și reconcilierea au panou persistent. Live region polite pentru stare, nu pentru fiecare request.
- Empty / not implemented / unavailable / loading / error / stale sunt componente distincte. N/A nu este 0 sau 100%.
- Settings Skills: listă/căutare în stânga, detaliu/fișiere în centru, release/readiness/review în dreapta; editor simplu cu diff, fără IDE complet. Publicarea arată „Applies to new runs”; taskurile din același run păstrează snapshotul catalogului.

## Do's and Don'ts

**Do:** arată întotdeauna sursa, identitatea și snapshotul rezultatului; conservă selecția/filtrele în URL; explică acțiunile blocate; verifică keyboard/focus/contrast/reduced motion și responsive. Animații de maximum 150ms pentru continuitate, eliminate când reduced-motion este activ.

**Don't:** zero metrici inventate în produs, zero procente fără numitor, zero confirmed dintr-un text LLM, zero titluri „AI Insights” fără date, zero graph canvas decorativ, zero secrete în URL/localStorage, zero HTML/JS/SVG de la țintă executat în Omnis. Nu dezactiva CSP a țintei pentru o demonstrație XSS.
