# Reviewer 2 — re-review Settings prerequisite

## Snapshot / verdict

**CHANGES_REQUESTED**, numai prerequisite-ul Settings; nu full T1, installed ori acceptare de integrare.

Base `686d342a1e5887e5b40ae97bc122f162a2faaa0d` → HEAD `3f7b4d3944869246bc70ab0d38495f4f1ea7146b`, tree `00e68c602c6fa384394aa4f4252bbd71645b4028`. Manifest `logs/settings-repair-freeze.json` SHA256 `023545c659f87a4400ed2fb3c304c7c53b857fca6f3fbc9093e5e2932a1f42dc`; toate cele7 delta paths identice ca size/SHA/blob; checkout curat. Probe originale neatinse. Review read-only; fără modificări de produs/commit/servicii/DB/provider.

## R2-F01 — CLOSED_SCOPED

Rezervarea SH este dobândită sincron înainte de create_task/to_thread (`provider_key_service.py:70–83`); workerul o închide după acțiunea filesystem. Drain verifică EX nonblocking pe același `vault.pending` (`provider_vault.py:121–132`), nu doar taskurile locale. Lockul RMW rămâne separat. Ambele reproduceri SOURCE existente cu spawn — scriere activă înainte de replace și executor ocupat/scriere încă în coadă — trec după anularea callerului; successor refuză drain până la finalizarea FS, apoi bytes rămân stabile.

Ordinea pe callerul real este admission DB (`instance_control` apoi `supervisor_lease`) → rezervare → RMW. Quiesce deține aceleași row locks și verifică drain înainte de UPDATE, cu reverificarea lease-ului; workerul FS nu așteaptă finalizer DB. Nu am identificat stale-quiescence/deadlock nou în această ordine. Dovezile PG existente pe exact HEAD sunt citite, nu rerulate: 33 PASS/24.33s, inclusiv takeover1→2, SHUTDOWN_INCOMPLETE fără receipt cât predecessorul este activ/pre-lock, apoi quiescență și LEASE_LOST pentru ownerul vechi.

## Finding nou R2-F02

- **Severitate:** MEDIUM (availability / cleanup; fail-closed, nu secret disclosure și nu false-positive drain).
- **Loc:** `api/src/omnis/modules/settings/provider_key_service.py:71–79`.
- **Scenariu:** rezervarea este deschisă înaintea programării, însă singurul close este în `write()`. Dacă executorul refuză jobul înainte ca `write()` să ruleze, taskul eșuează și dispare din `writes`, dar FD-ul SH rămâne deschis până la exitul procesului. Niciun writer nu mai există, totuși ownerul/succesorul nu pot confirma quiescența; chiar și o scriere ulterioară reușită nu eliberează rezervarea pierdută.
- **Reproducer SOURCE executat**, fără DB/servicii: vault sintetic bootstrapped și owner; `pool = ThreadPoolExecutor(max_workers=1); pool.shutdown(); asyncio.get_running_loop().set_default_executor(pool)`; `await owner._vault_write(lambda: vault.put(ref, "synthetic-failure-key"))` ridică `RuntimeError: cannot schedule new futures after shutdown`. După callback: `owner.writes` gol, vault bytes neatinși, `await owner.drain()` este **False**. Se setează un executor nou funcțional, următoarea `_vault_write` reușește, credentialul există, iar drain rămâne **False**. Output original: `failure-source.log` lângă acest raport, exit0. Declanșarea este explicită, cu executor oprit de probă; nu afirm că am observat exhaustion real ori această condiție într-un serviciu live.
- **Criteriu:** calea de eșec a programării nu trebuie să lase o rezervare fără writer care blochează permanent settlementul Settings/Stop în procesul încă viu.
- **Remediu minim:** ownership-ul rezervării trebuie eliberat și când jobul nu este admis/niciodată executabil, păstrat când jobul poate încă rula; un test restrâns pe submit refuzat. Nu închide necondiționat FD-ul la anularea callerului sau la orice eroare de scheduling: ar putea reintroduce R2-F01 dacă jobul există deja în coada executorului. Părintele adjudecă relevanța operațională a acestui failure path; nu este prezentat drept eșec live.

## Alte controale / dovezi

- Rerulare proprie: `api/.venv/bin/python -I -B -m pytest -c api/pyproject.toml -p no:cacheprovider --basetemp <owned>/pytest api/tests/test_provider_key_settings.py api/tests/test_provider_vault.py -k 'successor_drain_accounts or untrusted_uuid' -q`: **6 PASS/26 deselected/2.40s, exit0**; `focused-source.log` lângă raport. Mediu fără config PG/OMNIS/pytest ambientă, TMPDIR propriu.
- Failure SOURCE mic: `os.replace` ridică OSError în acțiunea reală vault.put; rezultă VaultLocked, bytes vechi păstrați și drain **True**. Deci failure-ul după intrarea în worker este curățat corect; findingul nou privește numai etapa anterioară.
- CredentialRef verifică tipurile înainte de UUID, fără relaxarea identității/AAD/secret validation. Bootstrap numai când istoricul DB este gol; heads revoked păstrează istoricul. Nu am găsit regresie concretă nouă secret/authority în aceste delta; dispozițiile R1 rămân ale reviewerului R1.
- `git diff --check 686d342 3f7b4d3`: exit0. Identitatea finală recitită, fără editări de repo.

Nu am rerulat PG/CLI/canonical, installed/browser/provider ori full T1; dovezile PG sunt reutilizate scoped. Reticle NOT_APPLICABLE, Chisel BLOCKED_NO_GO. Au fost create numai raportul/logurile și fixture-uri SOURCE sintetice în directorul scratch propriu; procesele SOURCE au ieșit, descriptorii sunt închiși la exit. Riscul nou este indisponibilitatea quiesce până la exit/restart după submit refuzat, nu permiterea unei scrieri stale după drain=True.
