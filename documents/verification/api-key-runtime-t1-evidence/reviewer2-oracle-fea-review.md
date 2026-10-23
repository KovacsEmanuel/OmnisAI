# R2 — re-review focalizat fea

Snapshot: `fea84e2d987d56db3a3f701f0b3d396f7fe21a64`, tree `0c92f4852572673498a18ac60a92563c9dbe633c`, față de `37877c83ac2525f5480c5e5db091ea429eeec43b`.

Inspecție read-only: delta și funcțiile afectate; fără execuție teste, PostgreSQL, rețea sau efecte de produs.

## Delta exactă

- `api/tests/test_model_test_v2.py:761`: `assert datetime.now(UTC) < min(`
- `api/tests/test_model_test_v2.py:762`: `utc(connect_scope.deadline), utc(connect_deadline)`
- `api/tests/test_model_test_v2.py:763`: `)`
- `api/tests/test_model_test_v2.py:869`: `assert datetime.now(UTC) < late_deadline`

## Verdict și dispoziție F1

**APROBAT pentru delta temporală, prin inspecție statică focalizată; F1 temporal închis pe acest snapshot.** Cele două verificări adăugate reobservă timpul la consumul dovezii ACK raw și la ramura Cancel/connect, înaintea readback/release; nu modifică TTL-ul, predicatele de autoritate ori produsul. Validitatea istorică a dovezii nu este reutilizată ca validitate curentă.

## Binding runtime `connect_deadline`

Cele două ramuri `if` depind de `physical_phase`; un `await` între ele nu rebindează o variabilă locală în cadrul coroutinei. Dacă `physical_phase` nu este reasignat între ramuri și atribuirea termenului domină prima ramură, aceeași condiție garantează binding-ul la utilizare. Un diagnostic LSP `possibly unbound` nu este singur un contraexemplu runtime și nu justifică extinderea scope-ului.

## Dovezi și limite

- Identitate și diff: `git status --short --branch`, `git rev-parse HEAD HEAD^{tree}`, `git diff --stat` și `git diff --unified=16 37877c83ac2525f5480c5e5db091ea429eeec43b HEAD -- "*test_model_test_v2.py"`; citire manifest părinte și raport F1 anterior.
- Nu s-au reluat suitele 86/28, auditul celor nouă fișiere sau gates de calitate. Logurile raw și mypy rămân dovezi moștenite, nu execuții R2.
- Aprobările produsului 878 și predicatelor neschimbate 378 nu sunt redeschise de această deltă.
- Fără probă PostgreSQL live nouă: nu se revendică PG PASS, T1 sau acceptare runtime. Lipsa PG nu este o precondiție pentru a închide defectul temporal demonstrat la nivelul oracle-ului.
- Singurul fișier creat/modificat de R2: acest raport; fără editări cod/produs/Git/HTML.
