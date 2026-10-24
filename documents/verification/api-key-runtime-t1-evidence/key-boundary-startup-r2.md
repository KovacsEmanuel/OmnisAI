# R2 independent — startup `92e36082`, effects/secret/Stop/cleanup

**Verdict: APPROVED_SOURCE_SCOPED. Findings concrete noi: niciunul în delta și callerii afectați examinați.** Nu este acceptare T1, integrare sau QA a artefactului normal instalat.

Ce schimbă: importurile Settings/model și construcția inertă `ModelSender` sunt mutate înainte de `acquire`; wiring-ul cu identitatea ownerului, reconcile, quiesce, controlul și finalizatorii rămân după acquire și neschimbate. Remediul elimină consumarea lease-ului prin pregătirea rece, fără retry, prewarm, lease ori timeout extins.

## Identitate și mandat

- Checkout read-only: `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`, clean la început și sfârșit; branch `impl/t1-sent-recovery`.
- Bază `be72942d82dfa6caf0c1c42c095306a5e33eaa81`; HEAD `92e36082d64b8ae49437df1976876b0d66ba089f`; tree `f82811691df67b073e0bc28b16332651c26dd638`.
- `freeze.json` verificat direct: trei bloburi/SHA256 identice; diff SHA256 `1123cbf7ef6b5990ed31616706c21456176d58a86d13829b7540be75333c19e2`; `git diff --check be72942..HEAD` exit 0.
- Scope: cele trei fișiere frozen (`api/src/omnis/supervisor/__main__.py`, `api/tests/test_supervisor.py`, `api/tests/test_runtime_supervisor.py`) și numai definițiile/callerii relevanți pentru construcție, authority, drain, secret și oracle. Cerință → `supervisor.run/main` → pregătire rece fără efecte pre-authority și cleanup corect → verdict asupra remedierii, nu asupra întregului T1.
- CURRENT/CONTRIBUTING/team-slice și procedurile review/status citite. Nicio modificare produs, PG, servicii, provider, chei, profiluri, HTML protejat, integration-src sau canonical5; fără push.

## Matrice cerință → cod → dovadă/dispoziție

| Cerință | Cod verificat | Concluzie scoped |
|---|---|---|
| Pregătire fără provider I/O înainte de autoritate | `__main__.py:81–98`; `model_sender.py:100–104,151–163,246–255`; `model_relay.py:33–39` | Constructorii configurează TLS/pool/HTTPX și obiectul Relay, fără `send`, `metadata`, `rpc`, task ori conectare. Pool-ul nu are conexiuni. `trust_env=False`, redirects false și retries 0 rămân. TLS poate citi certificate CA locale; „inert” nu înseamnă zero citiri de filesystem. |
| Seif și identitate nu sunt devansate înainte de owner | `__main__.py:98–107`; `provider_vault.py:90–101`; `provider_key_service.py:58–65`; `model_relay.py:55–78` | `owned_status` revalidează owner/epoch înainte de construirea ownerilor. `ProviderVault.__init__` însuși doar validează/reține argumente. Importul nu citește master key, iar capability-ul relay se citește doar la RPC, nu la constructor. I/O de seif nu a fost mutat în pregătirea pre-acquire. Nu este un re-audit al tuturor handlerelor seifului. |
| Failed acquire nu lasă sender deschis și nu eliberează owner străin | `__main__.py:68–72,97–100,259–288`; test nou `test_runtime_supervisor.py:16–75` | După refuz, `epoch` rămâne None; senderul deja asignat este închis, engine-ul disposed, semnalele eliminate; `owned_status` și `release` nu se apelează. Nu se creează fișiere vault/keys/control. Constructorul nu deține socket/task care să necesite drain pre-authority. |
| Guarduri de configurație rămân fail-closed | `__main__.py:83–94`; același test parametrizat | Missing keys, runtime incompatibil și egress diferit de `/vault` refuză înainte de constructor/acquire. Cele patru cazuri au fost rerulate independent, vezi mai jos. |
| Owner loss/Stop/finalizare nu sunt slăbite | `__main__.py:151–156,200–218,259–288`; `instance/service.py:303–307,329–363,489–517,975–979` | Același lease PG de 5 secunde, același control de owner/epoch și stop fence; reconcile → quiesce → expunere control; aceeași ordine drain → sender close → release. Expirarea după acquire continuă să refuze READY. Cazul owner_loss păstrează lease-ul expirat, nu fabrică release reușit. |
| Oracle separă pregătirea rece de lease expirat | `test_supervisor.py:17–159` | Proces fresh `-I -B`, source exact, OpenAI/sender neimportate la checkpoint; delay real 5.25s o singură dată la import/construcție, control identic înainte de acquire, negativ la quiesce. Clockurile/lease-ul nu sunt mockuite. Guardurile refuză provider/process egress; readback cere admission false, generation 0, operations/dispatches 0, cleanup sender/socket și rezultat exact al lease-ului. |

## Dovezi examinate / execuție proprie

1. **RED autor** — `red2/db-4389d2f2e3f247d5/gate.log`: 3 FAIL / 3 PASS, 49.92s. Import și constructor dau exit 3, `LEASE_LOST`, fără READY; controlul before-acquire trece, owner_loss refuză conform așteptării. Al treilea FAIL este așteptarea nouă de pregătire/închidere la acquire refuzat: înainte de fix senderul nu era construit. Acest al treilea caz este protecție a noului lifecycle, nu încă un defect istoric de startup. Prima tentativă RED cu stderr de teardown rămâne necurată/reținută, nu este înlocuită de o istorie idealizată.
2. **GREEN autor** — `green/db-f0120e045fb148bd/gate.log`: 111 PASS, 115.54s. Numărul rândurilor PASSED verificat programatic. `green/owner.log:7–10` leagă selecția efectivă, exit 0 și cleanupul raportat container/network/socket absent, uncertain false; datele sunt păstrate. `run_scoped.py` folosește ownerul PG existent cu selecție explicită; nu este canonical și nici întregul target `test-sl04-pg`. Include cele cinci cazuri cold, unicitate/restart, failure sanitizat, source lifecycle/settings, sender/guarduri și blocarea autorității DB. Cleanupul PG este readback al dovezii autorului, nu o nouă verificare externă R2.
3. **SOURCE/quality autor** — `source.log`: 50 PASS, 4.36s; `freeze.json`/mesajul candidatului declară exit 0. Quality declarat exit 0 pentru Ruff/format/mypy afectate; `quality.log` conține doar `[][]`, deci nu îl prezint drept transcript independent detaliat. Nu am rerulat quality ori suitele PG.
4. **R2 proaspăt, SOURCE-only, DB mockuită, fără QA instalată** — din checkoutul frozen:

```sh
env -i PATH=/usr/bin:/bin HOME=/home/kali/.hermes/cache/scratch/t1-33ee99/fix TMPDIR=/home/kali/.hermes/cache/scratch/t1-33ee99/fix PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml 'api/tests/test_runtime_supervisor.py::test_model_sender_preparation_preserves_guards_and_closes_on_acquire_refusal' --basetemp=/home/kali/.hermes/cache/scratch/t1-33ee99/fix/r2-source-tmp -q --tb=short
```

Rezultat real: **4 passed in 1.06s, exit 0**. Constructorul ModelSender/închiderea HTTPX sunt reale; authority/DB sunt doubles. Directorul scratch al testelor are numai directoare, fără fișiere la readback. Cele trei SHA frozen și checkoutul clean au fost reverificate după execuție.

## Limite și predare

- Niciun blocker nou demonstrat pentru această reordonare. Findingul reproductibil import/construcție după acquire are remediu și RED→GREEN relevante; aprobarea nu atribuie cauza eșecului istoric instalat acestui mecanism.
- Rootul istoric `/home/kali/.local/share/omnis-t1-33ee99` rămâne **UNKNOWN / retired / UNCERTAIN**, neatins. Ciclul harness-only anterior și FAIL-urile se păstrează.
- Testul cold ajunge la primul heartbeat și închidere nominală; nu probează funcționare îndelungată, toate combinațiile de cleanup eșuat, inferență, crash/SENT recovery sau distribuția normală. Nu redeschid sursa neschimbată pentru a pretinde completitudine universală.
- Artefactul normal actual: QA **NOT_RUN**. Urmează decizia părintelui după reviewurile necesare și verificarea/QA pe bytes distribuiți exacți; această lipsă nu este un prerequisite circular pentru admiterea acelei QA. Canonical5 separat nu este evaluat sau atins de R2.
- Reticle **NOT_APPLICABLE**; Chisel **BLOCKED_NO_GO**.
- Singurul fișier creat de R2: acest raport original `fix/review-r2.md`; pytest a creat directoare scratch goale. Nicio editare de produs și niciun commit în checkoutul read-only.

**Neexecutat:** PG/provider/servicii/QA normală instalată și canonical5. **Risc rămas:** aprobarea SOURCE scoped nu certifică startupul artefactului instalat și nu rezolvă retrospectiv cauza UNKNOWN.
