# R2 — review independent focalizat: cleanup fixtures

**Verdict: APPROVED_TEST_SCOPED. Findings concrete: niciunul.**

## Identitate și limită

- Checkout read-only: `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`.
- Bază: `4eb0bfc149c099380af653740329726a5a9bf38f`.
- HEAD verificat înainte/după: `1ef4df28bbb0b19e3d08e7d90426dbbd4d7573e8`; worktree/index curate.
- Singura deltă: `cli/integration/test_release.py`, +9/−3, numai cele două teste timeout.
- Blob: `e9b37980e236e775b10ad0811b703e207de4bea5`.
- SHA-256 fișier: `cabab5d4908b3c0f9eba5e7af9b8f56fc0f241d60e98647816ae0fc20fa9e32c`.
- SHA-256 diff: `0127f9596194116f30c0020aca304a8df9e2dd37646638aa79f29d367b5e96bb`; egal cu `candidate.diff` și FREEZE.

Cerință → consumer → risc → decizie: fixture-urile timeout trebuie să traverseze `_docker_id`/`compose._run` reale până la verificările cleanup, fără bypass al izolării, acceptarea altui daemon ori promovarea incertitudinii în succes. Aprobarea privește numai acest remediu de test, nu produsul/distribuția sau gate-ul global.

## Constatări pe bytes curenți

1. **Izolare, fără relaxare:** `test_release.py:239,318` creează explicit `data` cu `0700`, în fixture temporar propriu. Nu schimbă umask global, owner, validarea `private_dir`, codul de produs ori helperul cleanup. `compose.py:40–67` continuă să verifice parent-ul, să creeze client config temporar privat și să dea subprocessului numai PATH/HOME/DOCKER_CONFIG izolate; `config.json` rămâne `0600`, fără credentiale.
2. **Mock conform argv real, nu succes generic:** `test_release.py:269–272,350–353` acceptă noua formă `docker --config <path> --host <host> info --format {{.ID}}` numai cu parent-ul configului egal cu `data` și sufixul integral exact. `_docker_id` și `_run` nu sunt patchuite în cele două teste. Ramurile de operații neașteptate rămân refuzuri; nu apare un fallback de succes pentru orice comandă. Prefixele preexistente pentru image inspect/rm nu sunt extinse de această deltă.
3. **Bariere destructive păstrate:** helperul neschimbat `test_release.py:458–539` validează receipt/manifest/socket/daemon, apoi proiectul și digestul etichetelor, image ID când există și din nou daemonul înainte de `image rm`; verifică absența ulterior. Deltă zero în aceste predicate: un owner străin nu devine autorizat prin noua ramură info.
4. **Incertitudine și control negativ păstrate:** timeoutul rămâne `uncertain=True` (`657–664`); cleanupul nu îl transformă în succes (`538–539`). Asserțiile `removed`, late inspect ≥3 și intent existent rămân (`310,390–394`). Controlul daemon-switch (`396–456`) refuză ștergerea după schimbarea identității și păstrează intentul; acesta folosește în continuare propriul double `_docker_id`, separat de cele două teste reparate.

## Verificare independentă executată

Comandă, cwd checkoutul de mai sus:

```text
cli/.venv/bin/python -I -B -m unittest discover -s cli/integration -p test_release.py -k test_image_install_timeout_cleans_recorded_tag -k test_timeout_with_late_image_keeps_uncertainty_after_cleanup -k test_cleanup_rejects_daemon_switch_before_deletion -v
```

**3 teste PASS, 0.113s, exit 0.** Mediu explicit minimal: PATH `/usr/bin:/bin`; HOME/TMPDIR/XDG_CONFIG_HOME/XDG_CACHE_HOME într-un root `r2cleanup-*` nou sub scratch; fără opt-in-uri runtime sau variabile provider. Limită proces 60s. Subprocess/Docker și lansarea CLI sunt doubles conform testelor; numai fișierele temporare și socketurile Unix sintetice sunt reale. Importurile `compose.py` și `instance.py` au fost confirmate din `dev/cli/src/omnis_cli`, nu din alt snapshot.

Cleanup propriu: `remaining_owned_entries: []`, apoi `owned_temporary_root_removed: True`. Niciun cod, gate, asset ori fișier de status modificat. `git diff --check 4eb0bfc..HEAD`: exit 0.

Am citit dovezile originale, fără rerulare: `evidence/red.log` (2 ERROR/private_dir), `private-parent-only.log` (2 FAIL/mock argv), `green.log` (2 PASS), `release-full.log` (73 teste, 18.940s, OK; exit 0 în FREEZE). Acestea rămân dovezile autorului; proba mea este exclusiv selecția de trei teste de mai sus.

## Predare și limite

Creat numai prezentul raport original. Nicio remediere cerută în scope; integrarea și adjudecarea aparțin părintelui. Acceptările anterioare neschimbate, counter2/PENDING/connect-write și Stop4 nu sunt resetate sau promovate. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Nu am rerulat suita completă/canonical, nu am testat live Docker/OCI, PG, servicii, provider sau installed-root și nu am accesat rootul operatorului. Riscul rezidual: verdictul certifică remediul SOURCE cu doubles, nu o ștergere reală sigură ori închiderea T1.
