---
version: alpha
name: Omnis Operator Console
description: Consolă locală de investigație, cu proveniență vizibilă și control explicit al efectelor.
colors:
  primary: "#93E3BD"
  primaryInk: "#10231A"
  secondary: "#AFBCCA"
  neutral: "#0E1318"
  surface: "#151B22"
  elevated: "#1D2630"
  text: "#EDF2F7"
  border: "#596B7D"
  divider: "#2B3743"
  selected: "#233D32"
  focus: "#B0EACD"
  danger: "#FFB4AB"
  dangerBg: "#4B2226"
  warning: "#F3CB82"
  warningBg: "#3D321F"
  success: "#A4E8C8"
  successBg: "#18382D"
  info: "#B1D5FF"
  infoBg: "#23364A"
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
  sm: 4px
  md: 6px
  lg: 10px
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
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  panel-elevated:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primaryInk}"
    rounded: "{rounded.md}"
    padding: 12px
    height: 40px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    height: 40px
  button-danger:
    backgroundColor: "{colors.dangerBg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.md}"
    height: 40px
  nav-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
  metadata:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: 40px
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

Direcție unică pentru MVP: dark console cu accente verzi discrete, densitate moderată și tabele lizibile. Nu clonăm identitatea unui produs existent. Tema light a aplicației este post-MVP; raportul imprimabil este light de la început. Prototipul este DEMO etichetat și nu constituie aplicația.

## Colors

`primary` marchează acțiunea principală și selecția, nu „securitate garantată”. Statusurile folosesc **text plus semn/etichetă**, niciodată numai culoare. UNKNOWN, unavailable și zero sunt stări diferite. `border` este pentru contururi interactive; `divider` numai pentru separatoare neesențiale. Focus vizibil de 2px, offset 3px, în `focus`. Preview-urile evidence nu moștenesc HTML/CSS de la țintă.

Nicio informație esențială nu folosește opacitate redusă în loc de contrast. Butonul Stop rămâne cu contrast verificat, nu dezactivat estetic în timpul reconectării. Expirarea conexiunii se explică prin text; încercarea Stop poate afișa „transmitere nereușită”, nu „oprit”.

## Typography

Fonturile de sistem sunt o alegere deliberată: citire offline, compatibilitate cu Linux/Windows și fără requesturi externe din consola de securitate. Nu adăugăm o dependență CDN pentru identitate vizuală. Sans pentru operațiuni, mono numai pentru URL, ID, metodă HTTP, hash și fragmente de evidence. Numerele tabelare sunt activate în coloanele cantitative.

Body desktop 14px, mobil/form input 16px; metadata minimum 12px, dar nu pentru erori sau instrucțiuni esențiale. Titlurile produsului sunt 28/20px, fără hero de 64px. Print minimum 12pt. Zoom 200% nu ascunde Stop sau acțiunile formularului.

## Layout

- Sidebar desktop 232px; topbar minimum 64px; padding content 24px; rând tabel minimum 44px; controale touch minimum 44px.
- ≥1440px: nav 232px + workspace fluid + inspector 360px când este selectat un obiect. Nicio coloană nu trebuie să depășească viewportul.
- 1024–1439px: nav 208px, inspector sub tabel în două coloane; tabelul primește prioritate. Selecția rămâne vizibilă și detaliul nu acoperă controalele runului.
- <1024px: nav în drawer, inspector ca pagină/panou de detaliu; filtre pliabile, Stop în topbar persistent. Tabelele pot derula în propriul container etichetat, niciodată întreaga pagină.
- 320–600px: acțiuni pe două rânduri dacă este nevoie; wizard într-o singură coloană; finding/evidence detail stack. Nu ascundem verdictul, identitatea, snapshotul sau motivul blocajului pentru a câștiga spațiu.

Spacing pe multipli de 4px. Overview are taskuri/blocaje/evenimente, nu trei carduri egale cu numere decorative. Map are tree + tabel + inspector, iar Coverage este un tab al Map. Planul ecran-cu-ecran este în `documents/Omnis_UI_UX_Spec.md`.

## Elevation & Depth

Suprafețe solide, nu blur/glass. Separatoare și nivel de fundal delimitează panourile. Shadow numai pe drawer/dialog/popover; fără umbre pe fiecare rând. Un singur overlay modal activ; revenire de focus la un control vizibil. Când topbarul devine inert, overlay-ul conține o acțiune Stop echivalentă, fără confirmare suplimentară. Resize-ul închide modul modal înainte să ascundă triggerul de închidere; Esc poate închide drawerul, nu poate anula retroactiv aprobări deja trimise.

## Shapes

Radii 4–6px pentru controale și rânduri selectate; 10px maximum pentru dialog. Badge-uri compacte cu text clar, nu capsule peste tot. Un icon numai dacă ajută orientarea, întotdeauna cu accessible name. Fără emoji de status sau animații decorative.

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
