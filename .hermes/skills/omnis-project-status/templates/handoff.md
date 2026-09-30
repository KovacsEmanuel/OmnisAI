# Predare compactă — status global Omnis

Înlocuiește câmpurile cu fapte verificate; nu păstra placeholders în raportul final.
Folosește cel mult câteva rânduri plus linkul hărții, nu întreaga matrice la fiecare tură.

**Status global Omnis — HEAD `<sha>` / `<branch>`**
- **Unde suntem / delta:** `<fază și SL/B; rezultat al acestei sesiuni sau ÎN LUCRU; schimbare de produs vs numai dezvoltare/documentare>`.
- **Review:** **Aprobat** `<scope + revizie + adjudecare>`; **În review** `<ce așteaptă verdict>`; **Neaprobat** `<CHANGES_REQUESTED și blocante sau NOT_REVIEWED, nu le confunda>`.
- **Probe:** `<PASS / FAIL / BLOCKED / NOT-RUN, comanda și limita esențială; rezultate istorice etichetate>`.
- **Porți / perspectivă:** `<gate deschis; milestone MVP curent; post-MVP E1–E4 și capabilități neprogramate — neschimbate dacă nu există delta>`.
- **Următoarea felie:** `<ID exact și prerechizit din plan, nu un plan alternativ>`.
- **Git / Cleanup:** `<commituri, modificări intenționate rămase, fără push/push verificat; resurse/date proprii păstrate și incertitudini sau N/A>`.

Hartă completă: `documents/verification/implementation-status.md`.

## În registrul feliei sau mesajul commitului, nu în memoria globală

- Scope și bază: ID SL/B ori schimbare de dezvoltare distinctă, HEAD și căile afectate.
- Implementare: observabilul livrat și ce NU este livrat.
- Probe: revizie efectiv testată, comandă, exit code, sursă de dovadă și limite.
- Review: raport/snapshot/fișiere, constatări, reproducer/remediu și decizia părintelui.
- Map delta: rândurile schimbate, motiv, dependența/gate-ul următor; restul neschimbat.
- Cleanup: readback pentru efectele externe proprii sau N/A; fără secrete sau loguri brute private.

Un review read-only transmite aceste date părintelui; nu își comite/aprobă propria integrare.
