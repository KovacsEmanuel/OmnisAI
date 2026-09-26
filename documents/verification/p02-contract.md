# P0.2 — contractul de implementare

Bază: `6baa57f25d91daf5a0fd88f28eb2837818f8d68a`, checkout curat. Utilizatorul a cerut explicit continuarea P0.2. Autoritate: plan §5/§19, arhitectură §4/§6/§12. Acest fișier detaliază felia, nu pornește un plan concurent.

## Rezultat și limite

- Pairing atomic one-use/expirabil, sesiune opacă persistentă, logout server-side, Host exact, Origin exact și CSRF legat de sesiune. Rate limit persistent, erori fără body/secrete reflectate. HTTP loopback asumat; fără garanție împotriva root/aceluiași UID.
- `control.sock` separat de HTTP, peer UID + capability per boot, director privat verificat; protocol tipizat și bounded pentru status, înregistrare digest pairing și lifecycle. Nicio comandă shell/Compose/admin generic.
- Supervisor separat din același wheel: un singur owner DB, lease/fencing, restart închis. Admitere și shutdown folosesc aceeași tranzacție/lock `InstanceControl`. Lucrul de probă este exclusiv inert în harness, nu endpoint de assessment.
- Migrare nouă pe DB goală și upgrade de la `0001_instance_control`, readback și controale negative; P0.1 rămâne acoperit.

Nu implementăm web/CLI, SSE, engagement/run, Settings provider, Hermes, proxy, executori sau trafic target. `dashboard_ready=false`, `assessment_ready=false`; G00, L05 complet instalat și L08 integrarea producătorilor viitori rămân deschise.

## Perimetru și livrare

`api/src/omnis/{security,transport,supervisor,modules/instance,core,migrations}`, teste API/migrare/proces, Makefile și documentația relevantă. Nicio dependență nouă implicită. RED→GREEN pe comportamente și commit mic imediat; review independent read-only înainte de acceptarea finală.

Verificări: teste reale PostgreSQL din proiectul Docker dedicat, HTTP ASGI și procese reale/socket Unix, concurență/crash/restart, migrare instalată din wheel, `make check`, renderer și teste documentare. Output temporar numai în scratch; rezumatul probelor și limitelor în Git.

## Detalierea barierei P0.2

`InstanceControl` rămâne singletonul de autoritate. Orice admitere și comandă de lifecycle blochează întâi acel rând, apoi `supervisor_lease`. Lease-ul durează 5 secunde, epochul crește la fiecare owner; un owner expirat nu poate reînnoi/admite/publica quiescență. Takeover/release închide orice admitere deschisă și creează intenție durabilă de shutdown; nu reia lucru.

Comenzile OPEN/SHUTDOWN/FINALIZE au UUID și generație așteptată, cu receipt durabil. Reutilizarea UUID-ului cu payload diferit dă conflict; replayul identic întoarce generația rezultatului original fără a modifica generația curentă. Transportul trebuie să prezinte separat readbackul curent.

FINALIZE atestă numai finalizarea **controlului inert**, după quiescența persistată. Nu afirmă că au fost oprite containere. OPEN după shutdown cere FINALIZE plus un epoch nou de supervisor și acțiune explicită. P0.4 trebuie să verifice separat receiptul/identitatea containerelor oprite înainte de această nouă pornire. Un crash cu shutdown nefinalizat rămâne închis chiar dacă supervisorul a demonstrat quiescența. Nu confundăm quiescența cu oprirea instalării.

Proba de admitere folosește un marker SQL sintetic, creat numai de harness, în aceeași tranzacție cu verificarea barierei. Commitul încheie întregul lucru inert; nu există task async/efect extern de simulat. P0 poate declara quiescență numai pentru acest set gol de executori și tranzacții drenate. P2/P3 trebuie să extindă explicit predicatul cu dovezile adaptoarelor înainte să introducă producători reali.

## Efecte externe / rollback

Înainte: niciun container de test pornit, nu există DSN de test moștenit. Se creează un proiect unic `omnis-p01-p02-*` folosind imaginea digest-pinned existentă și un volum propriu. Fără date reale, fără adoptare de DB/credentiale personale. Invers: `docker compose -f ops/compose.test.yaml down` în același mediu verificat; volumul se păstrează, fără `-v`. Fixture-urile creează/șterg numai DB UUID atestate. Revert Git pentru cod, nu pentru schema sau volumele deja create. Upgrade pe date reale cere backup/restore explicit și nu este executat aici.
