# Reviewer 2 — re-review focalizat R2-F02

## Dispoziție

**R2-F02: CLOSED_SCOPED. Verdict: APPROVED_SCOPED**, exclusiv remediul submit-refusal/reservation ownership și regresiile directe. Nicio regresie concretă nouă identificată. Nu este acceptare de integrare, full T1 ori installed.

Snapshot verificat: `3f7b4d3944869246bc70ab0d38495f4f1ea7146b` → `c19440a357866c162672be5400e08df4636b585f`, tree `71ca72ca0da70844f0d690096322352b8f54aaaa`. Checkoutul izolat este curat. Manifestul și patchul din `logs/r2f02-freeze.json` / `logs/r2f02-delta.patch` corespund exact HEAD/tree, celor două căi și bloburilor/SHA256; patchul corespunde byte-exact diff-ului Git full-index.

- `api/src/omnis/modules/settings/provider_key_service.py`: blob `f48ea67fb568dac2ed5af7988a2206ae2cdb4915`.
- `api/tests/test_provider_key_settings.py`: blob `8a7612171c34981d148b2cb3727508ca33eef386`.
- Patch blob declarat și conținut verificat: `ce9a5314709ce030a0d2fd216dc512989783b16d`; SHA256 `d018b5159e1f79bc954bf84dfffd5b9adf71292613d134e2ad5229fe8e255615`.

## Ownership și criteriul remedierii

`provider_key_service.py:71–95`: rezervarea SH se deschide sincron înainte de scheduling. `concurrent.futures.Future` este numai claim de ownership, nu rezultatul workerului. Tranzițiile concurente `cancel()` și `set_running_or_notify_cancel()` decid exclusiv cine poate închide FD-ul:

- La submit refuzat înainte ca workerul să revendice rezervarea, `schedule()` intră în `finally`; numai dacă `ownership.cancel()` reușește închide FD-ul (`:83–89`). Dispare astfel rezervarea fără writer care bloca permanent drain.
- Dacă `ThreadPoolExecutor.submit()` a pus deja callbackul în coadă și pornirea threadului eșuează, revocarea claimului face callbackul ulterior inert (`:75–77`): fără acțiune FS și fără al doilea close pe un descriptor eventual reutilizat.
- Dacă un worker existent revendică jobul înaintea erorii de pornire a altui thread, claimul este RUNNING, `cancel()` e False, iar numai workerul închide rezervarea în `finally` (`:78–81`). Faptul că taskul schedulerului a eșuat și a ieșit din `writes` nu permite drain fals: `vault.pending` rămâne ocupat până la finalizarea workerului.
- Anularea callerului rămâne separată prin `await asyncio.shield(task)` (`:95`); nu revocă o scriere activă sau încă programată normal. R2-F01 rămâne **CLOSED_SCOPED**, nu redeschis.

## Dovezi executate independent

Consumer SOURCE: owner/vault reale și executor standard, fixture-uri sintetice private, fără conexiune DB/provider. Mediu allowlist fără variabile ambientale PG/OMNIS/pytest, HOME/TMPDIR proprii, `-I -B`, plugin asyncio explicit și cacheprovider dezactivat.

Cwd: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/src`.

```text
api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml -p pytest_asyncio.plugin -p no:cacheprovider --basetemp /home/kali/.hermes/cache/scratch/ot1-0zxf62th/logs/reviewer2-r2f02-v4dzgsxf/pytest api/tests/test_provider_key_settings.py -k 'failed_submit_settles_reservation or successor_drain_accounts_for_cross_process_writers' -vv
```

**5 PASS / 15 deselected / 2.40s, exit0**, originalul comenzii și stdout în `focused-source.log` lângă raport:

1. Executor standard shutdown: submit refuzat, acțiune neexecutată/bytes neatinși, successor drain True; executor nou permite scriere și drain ulterior.
2. Thread.start refuzat după enqueue: drain True înainte de executarea ulterioară a cozii; callbackul vechi este consumat fără intrarea în acțiune și fără modificarea vaultului; recovery reușește.
3. Control activ: workerul real a intrat înaintea refuzului de thread-start; successor drain False până la release/finally, apoi credentialul este prezent și drain True; recovery reușește.
4–5. R2-F01: anulare caller cu scriere activă și queued, în procese distincte; successor refuză drain până la settlement și bytes rămân stabile după.

`git diff --check 3f7b4d3944869246bc70ab0d38495f4f1ea7146b c19440a357866c162672be5400e08df4636b585f`: **exit0**. HEAD/tree/fișierele citite și status curat verificate înainte și după rularea testelor.

Am citit dovezile existente, fără a le prezenta drept execuții proprii: RED autor 2 FAILED (shutdown/queued), 1 PASS (active), exit1; GREEN autor 5 PASS, exit0; API quality `make --no-print-directory lint-api typecheck-api`, exit0. Reproducerea părintelui păstrează originalul fail-closed fără taskuri active și drain False chiar după executor nou, în `logs/parent-r2f02-source.log`.

## Limite și ownership

Am verificat byte-exact că sursa de la `drain()` până la finalul ownerului este neschimbată. Dispozițiile R1 pe logica neschimbată și aprobările scoped anterioare se reutilizează, nu se redeschid. Dovezile PG istorice rămân numai pentru contractul DB neschimbat; nu reprezintă execuția noului scheduler.

Nu am modificat cod, teste, index, commituri, documente canonice ori checkoutul comun. Au fost create numai acest raport, `focused-source.log` și fixture-urile SOURCE în directorul scratch propriu; testele finalizează poolurile și reunesc procesele proprii. Nu am pornit verificatori suplimentari, servicii, instalări ori trafic de rețea. Integrarea/adjudecarea finală aparține părintelui.

Neexecutat: PG fresh, canonical, installed, browser/provider/full T1; fără efecte asupra profilurilor, `.omnis`, r1 sau HTML-ului protejat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO. Riscul rămas este limita SOURCE: nu certifică exhaustion real de threaduri ori Stop end-to-end instalat.
