# Reviewer1 — recuperare explicită T1

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete: niciunul blocant identificat în charterul R1.** Nu este acceptare QA fizică, rollout sau închidere T1.

## Snapshot și acoperire

- Base: `dd4f8747287496d1bb589de277455354d122892a`.
- Candidat: `df8bd693a7d2f64811c8a1cd1231e91d93b20c43`.
- Tree: `9d0a3a1e9e5a45ffcf31cf76eea879d68b52063c`.
- Manifest: `evidence/freeze.json`; diff SHA256 `ecb67ce406ced25792c367637cd1d8660cdb77f26ba1a1103bbd0da215e6fbd6`.
- Verificare proprie: exact cele **10/10 changed paths**, fiecare blob Git și SHA256, HEAD/tree/diff identice manifestului; checkout inițial clean. Citite delta celor 10 fișiere și definițiile/callerii relevanți, nu doar rezumatul developerului. Wheelurile și hashurile probelor au verificarea părintelui; nu revendic reverificarea lor independentă.

## Dispoziția cerințelor R1

1. **CLI → takeover → SHUTDOWN autentic → Stop-owner → STOPPED:** `main.py:135–136` intră în `stop_instance(recover=True)`, cu aceleași locks/OFD aliases. `recover.py:155–238` validează READY5/T1, generation/epoch, inventarul original și lease expirată; persistă/readback intentul original-bound și RECOVERING înaintea unicului `start` pe CID-ul original. Revalidează înainte de efect și cere owner nou, epoch/generation exact incrementate și barieră quiescentă CLOSED înainte de STOPPING. `stop.py:732–820` reutilizează SHUTDOWN, quiescență, FINALIZE, readback DB, ARM_STOP și ownerul existent. `_publish_stopped`/`readback_stopped` și `stop_owner.verify_stop_completion` verifică receiptul complet și absența resurselor; STOPPED nu rezultă din simplul ACK al restartului.

2. **Owner-loss implicit ≠ shutdown comandat:** `service.py:334–356` închide admission și schimbă lease/epoch în aceeași tranzacție, apoi reține identitatea barierei numai după commit. `service.py:478–517` permite înlocuirea numai pentru opt-in și tuple-ul exact al takeoverului curent, fără fence/receipt implicit, cu quiescență verificată. UPDATE-ul generației și INSERT-ul receiptului SHUTDOWN sunt în aceeași tranzacție, cu revalidarea lease-ului înainte de commit. Barierele moștenite de la alt proces sau un SHUTDOWN deja comandat nu primesc această excepție.

3. **Replay/readback și limite:** receiptul exact revine fără alt increment; comanda cu payload schimbat este refuzată. Callerul real `LocalControl:249–272` face `command_readback`, care leagă receipt/generație/epoch în altă tranzacție; ARM_STOP verifică ambele receipturi autentice. Limita READY de `9223372036854775804` rezervă inclusiv limita wire FINALIZE, nu doar incrementul SHUTDOWN. Intentul rămas blochează continuarea Start/Stop/recover; nicio ramură recovery nu autorizează emergency teardown sau replay al efectului incert.

4. **Istoric, UNKNOWN și fără re-SEND/OPEN:** supervisorul face `ApiKeyModelTest.reconcile()` înainte de quiescență și expunerea LocalControl (`__main__.py:158–179`). Traseul existent reconstruiește scope-urile pentru FENCE/DRAIN, apoi settle tranzacțional; nu programează operațiile moștenite. SENT fără rezultat devine UNKNOWN/OWNER_LOST; pre-send devine NOT_SENT, iar FINISHED nu este rescris (`model_test_runtime.py:74–143,774–855`). Noile cereri rămân sub admission CLOSED. Recuperarea nu apelează OPEN, Pair, metadata/Test ori sender.send și nu schimbă selecția/seiful; readbackul Stop păstrează verificările datelor.

## Probă proprie

În worktree-ul frozen, cu HOME/XDG_CONFIG_HOME/TMPDIR proprii sub `evidence/reviewer1-temp` și autoload pytest dezactivat:

```text
api/.venv/bin/python -I -B -m pytest -p no:cacheprovider -p pytest_asyncio.plugin -c api/pyproject.toml api/tests/test_instance.py::test_owner_loss_new_shutdown_source api/tests/test_instance.py::test_shutdown_wire_maximum_and_rejected_inputs_source -q --tb=short
```

**14 PASS, exit 0, 0.27s.** Output original: `evidence/reviewer1-source.txt`. Sunt teste SOURCE cu double SQL și validatori/wire reali, nu probă de commit PostgreSQL. Au fost inspectate testele CLI și proba PG adăugate; rezultatele developerului rămân distincte de execuția proprie.

**Neexecutat:** Docker/DB nouă, QA installed/fault, provider/browser, canonical8 și regresiile neschimbate; logurile PG raw sensibile nu au fost citite. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
**Risc rămas:** integrarea fizică a întregului traseu rămâne NOT_RUN și trebuie probată pe artefactul admis după reviewurile obligatorii; nu este un prerequisite circular pentru acest verdict SOURCE. Fără modificări de produs, date operator sau fișier protejat.
