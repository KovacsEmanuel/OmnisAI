---
version: alpha
name: Omnis Operator Cockpit
description: Consolă locală de investigație, cu proveniență vizibilă și control explicit al efectelor.
colors:
  primary: "#C7BAA7"
  primaryInk: "#111210"
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
    fontFamily: "Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 1.75rem
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.4
  body-md:
    fontFamily: "Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Segoe UI, Liberation Sans, Arial, sans-serif"
    fontSize: 0.8125rem
    fontWeight: 600
    lineHeight: 1.45
  code:
    fontFamily: "Liberation Mono, Consolas, monospace"
    fontSize: 0.8125rem
    fontWeight: 400
    lineHeight: 1.6
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
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primaryInk}"
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

**Surface primar: Operate; secundar: Command / Inspect.** Omnis este un instrument de lucru, nu o pagină de marketing și nu un chat cu o hartă atașată. Interfața prioritizează starea verificată, următoarea decizie a operatorului și lanțul observație → acțiune → dovadă → verdict.

**Propunere vizuală, încă neaprobată:** interpretare a referinței furnizate `omnis-cockpit-v5.html`, identificată în §0 din specificația UI. Negru cald, ivory/taupe, accent nisipiu, topnav compact și panouri cu contur discret. Înlocuiește direcția verde/albastră respinsă, nu creează un baseline concurent. Fără brain graph/council; Brain stream și finding detail sunt suprafețele reprezentative. Tema light a aplicației rămâne post-MVP; raportul imprimabil este light. DEMO etichetat, nu aplicație.

## Colors

`primary` marchează acțiunea principală și selecția, nu „securitate garantată”. Statusurile folosesc **text plus semn/etichetă**, niciodată numai culoare. UNKNOWN, unavailable și zero sunt stări diferite. `border` este pentru contururi interactive; `divider` numai pentru separatoare neesențiale. Focus vizibil de 2px, offset 3px, în `focus`. Preview-urile evidence nu moștenesc HTML/CSS de la țintă.

Nicio informație esențială nu folosește opacitate redusă în loc de contrast. Butonul Stop rămâne cu contrast verificat, nu dezactivat estetic în timpul reconectării. Expirarea conexiunii se explică prin text; încercarea Stop poate afișa „transmitere nereușită”, nu „oprit”.

## Typography

Fonturile de sistem sunt o alegere deliberată: citire offline, compatibilitate cu Linux/Windows și fără requesturi externe din consola de securitate. Nu adăugăm o dependență CDN pentru identitate vizuală. Sans pentru operațiuni, mono numai pentru URL, ID, metodă HTTP, hash și fragmente de evidence. Numerele tabelare sunt activate în coloanele cantitative.

Body desktop 14px, mobil/form input 16px; metadata minimum 12px, dar nu pentru erori sau instrucțiuni esențiale. Titlurile produsului sunt 28/20px, fără hero de 64px. Print minimum 12pt. Zoom 200% nu ascunde Stop sau acțiunile formularului.

## Layout

- Container centrat de maximum 1280px, padding 24px desktop/16–18px mobil. Navigare globală într-o capsulă deasupra engagementului; apoi topbar sticky cu identitatea runului și Stop, apoi navigare orizontală contextuală. Fără sidebar permanent. Controale minimum 44px.
- ≥1024px: cockpit asimetric (lucru/findings aproximativ 1.45fr, stream 1fr), gap 24px. Map păstrează inspectorul lateral la ≥1440, sub tabel în două coloane la 1024–1439. Nicio coloană nu depășește viewportul.
- <1024px: navigarea contextuală în drawer, cockpit într-o coloană, detaliu full-width; Stop în topbar persistent. Tabelele derulează în propriul container etichetat, niciodată întreaga pagină.
- 320–600px: acțiuni pe două rânduri dacă este nevoie; wizard într-o singură coloană; finding/evidence detail stack. Nu ascundem verdictul, identitatea, snapshotul sau motivul blocajului pentru a câștiga spațiu.

Spacing pe multipli de 4px. Overview: context compact → atenție operator + findings + taskuri, cu Brain stream alături. Fără monumente KPI sau procente fără numitor. Map are tree + tabel + inspector, Coverage rămâne tab al Map. Ecranele auxiliare păstrează contractele funcționale; redesignul lor complet așteaptă feedback pe această felie. Detaliile sunt în `documents/Omnis_UI_UX_Spec.md`.

## Elevation & Depth

Suprafețe solide, nu blur/glass. Contur dublu foarte discret pe panourile principale (outer 4px, ivory la aproximativ 2%), fără glow sau animații. Separatoare și fundaluri delimitează streamul/evidence. Umbre ample numai pe drawer/dialog. Un singur overlay modal activ; revenire de focus la un control vizibil. Când topbarul devine inert, overlay-ul conține Stop echivalent, fără confirmare. Resize-ul închide modul modal și mută focusul în workspace, deoarece drawerul dispare pe desktop; Esc nu anulează aprobări deja trimise.

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
