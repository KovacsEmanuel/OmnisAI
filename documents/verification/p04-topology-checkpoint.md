# P0.4 — checkpoint de întrerupere: topologia control instalată

**WIP, NU livrat / G00 deschis.** Ramură izolată `p04-control-topology-wip`, pornită din `c4cb784` de pe `main`. Utilizatorul a cerut oprirea laptopului; acest checkpoint păstrează doar experimentul RED/implementarea parțială, nu promite startup. Nu face merge/push și nu interpreta ramura drept produs gata.

## Ce este sigur pe `main`

Commituri locale verificate: `822c24f` (fsync release), `a9b14e4` (install-image), `6091038` (README/plan/HTML), `c4cb784` (skill ops). Pe HEAD curat `make check-installed-image UV=/home/kali/.hermes/cache/scratch/omnis-final-readiness/dependency-probe/tools/uv` a trecut exit 0 (32 CLI unit, 9 integrări; ID-ul imaginii instalate probat). `make check UV=...` a trecut direct exit 0 pe PostgreSQL disposable `omnis-p01-p04-9ae6cd9e066c`; numai containerul/rețeaua proiectului atestat au fost oprite prin `down` fără `-v`, volumul `_pgdata` reținut. Nu s-a făcut push. Aceste rezultate **nu** certifică serviciile Compose de produs.

## Ce este WIP în ramură

- `cli/integration/test_control_topology.py`: 3 controale pentru override Docker/Compose/libpq și port loopback străin; au trecut înainte de ultima editare.
- `cli/integration/control_topology.py`: guardurile de mediu/port și helperi de inspect/Compose adăugați parțial; **lipsește `run_probe`**, iar ultimii helperi nu au fost rulați/lintați după editare. Nu presupuneți că fișierul este green.
- `cli/integration/test_release.py`: callback exclusiv pentru `OMNIS_INSTALLED_CONTROL_PROBE=1`, care importă `run_probe` doar după instalarea imaginii și smoke-ul ei. RED real din alt cwd cu bundle/wheel/imagen instalate a eșuat așteptat la `ImportError: cannot import name 'run_probe'`. Proba nu a pornit DB/API/supervisor. Bundleul scratch al acestui RED (`omnis-bundle-kofsfc5m`) a fost eliminat numai după readback: tagul și containerele proprii erau absente, iar `state/postgres` era un director gol de config; nicio DB de produs nu a fost creată.

Nu s-au conectat conturi, consumat LLM sau generat trafic de țintă. Docker este local pe Unix; nicio imagine/tag `omnis-control-*` sau container al probei nu era activ la ultimul readback. Nu sunt parole personale în repo. Fișierele de parolă din testele anterioare erau sintetice și disposable.

## Reluare precisă

1. `git switch p04-control-topology-wip`; `git status --short --branch`; `git show --stat --oneline HEAD`; recitiți plan §19, arhitectura §4/§12 și `p04-image-install.md`. Nu folosiți origin/main ca bază; nu refaceți web/designul.
2. Implementați numai proba opt-in a **DB/API/supervisor reale din release+image ID instalate**, cu preflight fail-closed și cleanup atestat. Ordine obligatorie: DB health → migrare numai pe DB goală disposable → schemă compatibilă → supervisor/API → IPC + HTTP/assets/Host real. `compose.control.yaml` pornește supervisorul înaintea migrării dacă se face `up` pentru toate serviciile; nu pretindeți readiness atunci.
3. Fișierul de parolă DB este sintetic, privat; DB bind nou sub scratch privat, fără date existente. Niciun `down -v`, prune, pull/build la startup, socket Docker în containere, fallback la port străin ori output de DSN/capability. Dacă topologia reală eșuează (UID, rețea internă sau permisiuni), păstrați probele și volumele/identitățile, raportați blockerul. Nu executați assessment.
4. Cicluri RED→GREEN, review independent, `make check-installed-control` explicit doar după ce targetul există, apoi `make check` pe PostgreSQL disposable și artifactul instalat din afara checkoutului. Documentați rezultate pozitive/negative și limita dovezii. Commituri mici pe ramură; integrați în `main` numai după code review/gate green, fără amend/squash/rebase implicit. G00 rămâne deschis până la `omnis start/pair/open/stop`, L01–L05-control/L08-core și topologia completă.

**Rollback extern:** niciun serviciu Compose de produs nu a fost pornit de experimentul WIP; nu există DB nouă de produs de restaurat. Git revert/switch nu șterge volumele disposable reținute pe `main`. Verificați întotdeauna proiectul, etichetele, mountul și imaginea înainte de o operație Docker ulterioară.
