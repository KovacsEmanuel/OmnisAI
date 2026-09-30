# Predare în chat — matricea statusului global Omnis

## Obligatoriu la închiderea unei sarcini

Afișează matricea **direct în chat**, la finalul răspunsului în care termini o sarcină Omnis: implementare, review, documentare sau pregătire de handoff. Un link către documente **nu înlocuiește matricea**. Nu este necesară la fiecare apel de tool sau mesaj intermediar.

Înlocuiește placeholders cu fapte verificate. Folosește în mod normal 6–8 rânduri, nu toate cele 36 de subfelii; extinde numai la cererea utilizatorului sau când rândurile agregate ar ascunde un blocker. Arată explicit **AICI** la felia curentă. Datele DEMO, documentele și testele de structură nu devin produs implementat.

Scrie înaintea matricei rezultatul scurt al sarcinii, comenzile/probele relevante, commiturile și Cleanup-ul propriu sau N/A. Nu repeta apoi întregul raport sub tabel.

**Status global Omnis — HEAD `<sha>` / `<branch>`**

| Zonă / felie | Implementare | Probe | Review | Poziție / pas următor |
|---|---|---|---|---|
| Fundații livrate `<IDs>` | `<ce există efectiv>` | `<PASS scoped la revizie sau limite>` | `<Aprobat în scope / restanțe>` | `<ce reutilizăm>` |
| **AICI — `<felia curentă>`** | `<implementat/parțial/neimplementat>` | `<PASS / FAIL / BLOCKED / NOT-RUN; nu ascunde RED>` | `<Aprobat / În review / Neaprobat — motiv>` | `<corecție imediată sau condiție de închidere>` |
| Următoarea felie `<ID>` | `<stare reală>` | `<stare reală>` | `<nu este revizuită / verdict delimitat>` | `<prerechizit canonic>` |
| Gate/milestone `<ID>` | `<deschis/închis, fără echivalare cu cod>` | `<probe lipsă ori efective>` | `<acceptare sau blocker>` | `<condiție de trecere>` |
| Restul MVP `<interval/ramuri>` | `<stare agregată fără procente inventate>` | `<stare efectivă>` | `<review al implementării, nu al specificației>` | `<ordinea/dependența relevantă>` |
| post-MVP `<E waves/B21m/unscheduled>` | `<planificat/implementat, după dovezi>` | `<stare efectivă>` | `<stare efectivă>` | `<separat de MVP, fără programare inventată>` |

Dacă un subagent încă lucrează, folosește **În review**, nu aprobat. Lipsa review-ului este NOT_REVIEWED, distinctă de CHANGES_REQUESTED. Un review aprobat pe snapshot vechi nu aprobă automat HEAD. Include CI remote/assessment readiness când sunt relevante pentru felia/gate-ul curent, fără repetarea tuturor limitelor în fiecare celulă.

## Documentele sunt suport pentru agenți și implementare

`documents/verification/implementation-status.md` păstrează harta completă; registrele feliei păstrează detaliile probelor și deciziilor. Acestea sunt memoria de lucru **pentru agenți**, nu un substitut pentru statusul vizibil utilizatorului.

- **ORIENT:** citește Git/harta și publică matricea; **fără editări** sau commit gol numai pentru a putea răspunde în chat.
- **CLOSE:** actualizează în documente numai schimbările factuale autorizate, verifică/comite și apoi publică matricea în chat. Nu genera un raport documentar nou la fiecare prompt fără un motiv factual.
- Scope, revizie testată/revizuită, comenzi/exit, constatări/adjudecare și cleanup rămân în registrul existent sau mesajul commitului, nu în memoria globală.
- Reviewerul read-only transmite delta părintelui; nu își comite/aprobă propria integrare.
