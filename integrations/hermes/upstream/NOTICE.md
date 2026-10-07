# Hermes 0.21.5 — proveniență și limite B05

Cod original: Nous Research, MIT; textul integral este în `LICENSE`. Pinul și hashurile sunt în `../pin.json`; `uv.lock` și `pyproject.toml` sunt bytes originali ai commitului `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9`.

## Modificare locală declarată

`omnis-inert.patch` schimbă numai cinci fișiere, cu SHA256 before/after în `patch-manifest.json`. `inert-source/` conține exact versiunile rezultate, pentru overlay verificabil și testul no-IO. Flagul explicit `HERMES_OMNIS_INERT=1`:

- suprimă sidecarul, MCP startup, heartbeat/orphan startup, skin watcher și provider-model prewarm;
- suprimă update-prefetch și idle-reaperul de import;
- returnează din loaderul dotenv înaintea citirii home/project/managed/external secret sources;
- refuză handlerii RPC cu excepția `client.capabilities`, păstrând framingul, dispatcherul și contractele native;
- refuză lazy-install chiar dacă există un target writable.

Upstream nu oferă un singur flag production pentru aceste efecte. `HERMES_DISABLE_LAZY_INSTALLS=1` singur NU este deny-all când există un target durable; `security.allow_lazy_installs:false` există nativ. Guardurile pytest NU sunt folosite pentru a falsifica un startup inert. Flagul Omnis este exclusiv B05, fără sesiune Brain. Nu certifică politica de tooluri a unui run viitor și nu poate fi dezactivat implicit pentru inference.

## Build suportat, separat

`setup.py` al pinului refuză wheels native în afara Nix; această probă a eșuat real și nu este ocolită prin `HERMES_NIX_BUILD`. Artefactul Hermes păstrează layoutul sursă suportat în `/opt/hermes/source`, cu `.pth` în venv. Numai adaptorul Omnis este wheel separat. Payloadul exclude tests/docs/frontend source și datele operatorului; include modulele native și asseturile runtime upstream existente. Lista exactă/hashurile sunt în manifestul generat.

Pregătire reproductibilă (output nou obligatoriu):

```
git -C <repo-Hermes-readonly> archive --format=tar ee5ee84a345204a3b1d6ef6ba1ab747e602867b9 > <source.tar>
<python-3.13.15> ops/prepare_hermes_runtime.py --source-archive <source.tar> --output <nou-output> --build --python <python-3.13.15> --uv <uv-0.12.19-verificat> --adapter-wheel <omnis_hermes-wheel> --adapter-sha256 <hash-explicit>
docker build --network=none --build-arg RUNTIME_UID=<uid-host-nonzero> --build-arg RUNTIME_GID=<gid-host-nonzero> -f ops/Dockerfile.hermes <nou-output>
```

În build, numai URLurile wheels din lock, pe `https://files.pythonhosted.org`, sunt descărcate. Instalarea este binary-only/hash-locked/no-deps; instalarea finală OCI este offline. Helperul NSS de dezvoltare a fost verificat împreună cu uv real și fișierul NSS față de receiptul aprobat; nu este parte din runtime și nu schimbă NSS global. Comenzile și rezultatele reale sunt în `local-build/*/commands.jsonl`.

`--adapter-wheel` este un input, nu o implementare stub. Fără inputul Developer A, buildul OCI refuză lipsa `omnis_hermes.runtime_host`. Imaginea, readiness nativ și drainul instalat sunt responsabilitatea părintelui/QA și sunt NOT_RUN aici.

## Config, management și date

`inert-config.yaml` este input de fixture dedicat, nu configurare a profilului personal. Părintele trebuie să monteze acest config în home-ul fixture și să păstreze flagul inert în mediul allowlisted al copilului, inclusiv HOME/HERMES_HOME/CODEX_HOME/XDG/TMPDIR și `HERMES_MANAGED_DIR` gol dedicat. Mounturile host/root/private grants/checkoutul de dezvoltare sunt interzise. Source/system read-only, network_mode none, fără capabilități/privileged/Docker socket; IPC este separat.

Managementul sigur B05 este statusul intern tipizat al runtime-hostului/exclusivitatea writerului + handshake capabilities. Nu porni `hermes serve`, `/api/model/options`, setup/runtime-check, validate, OAuth, discovery sau rute Settings în B05. P4a este separat. Un status al providerului poate citi/adopta/refresh grants; nu este un healthcheck inert.

`state-tool-inventory.json` este audit STATIC: 725 ancore de path, 61 toolsets stock și 59 core-tools stock. Nu este inventar efectiv/live Brain și nu demonstrează H08. Empty/null toolsets pot moșteni defaults; refuzul `session.create` este controlul B05, nu o afirmație că `toolsets:[]` singur sandboxează un agent.

Decizia A→B→A: după drain verificat, arhivează întreg state-rootul de caz, inclusiv HERMES_HOME state.db/WAL/SHM, sessions/logs/cache/memorii/cron/proiecte/derivate și HOME/CODEX/XDG/TMPDIR. Nu muta SQLite cu writer activ. Store-urile provider (`auth.json`, `.anthropic_oauth.json`, `.env`, `.op.env`) și configul aprobat au un singur owner și nu se clonează în arhive; în fixture B05 sunt absente. Fallbackul root/profile (`hermes_constants.py:217–234`, `auth.py:495–536`), CODEX_HOME (`auth_codex.py:529–532`) și managed `/etc/hermes` trebuie excluse fizic. Unknown shared path => H02 BLOCKED, nu whitelist ghicit. A→B→A cu markeri, restaurare și permisiuni reale rămâne NOT_RUN pentru părinte.

## Dovezi și blocker

`test-receipts.json`: exact același sink no-IO pe original are 5 FAIL; overlayul are 5 PASS. Trei controale preparation/OCI au RED→GREEN. Nu a fost importat/porniit gatewayul real, nu s-au folosit grants personale sau provider/target calls.

Două builds separate au câte 62 wheels dependency verificate și 3184 fișiere native runtime cu manifest/hashuri identice; Python 3.13.15, pip-check exit0. Exportul curent `uv export --locked` reproduce byte-exact requirementsul core. `--no-config` fusese respins corect de `--locked` deoarece elimină exclude-newer din configurația pinului; nu a fost actualizat lockul. Un audit preliminar a selectat upstream `.python-version` 3.11 și a descărcat interpreterul de tool în cache uv; buildul nativ nu l-a folosit. Auditul final folosește proiect dependency-identic cu selector explicit 3.13.15.

**BLOCKER de dependențe:** auditul core `uv audit --locked`, toate extras excluse explicit, exit1: 37 intrări advisories pentru anyio 4.12.1, PyJWT 2.13.0 și urllib3 2.7.0; 68 pachete auditate, zero adverse statuses. Receiptul integral este `dependency-audit.json`. Pinul NU a fost upgradeat și advisories NU sunt ignorate. Build/install reușit nu este PASS de siguranță sau aprobare pentru inference/target/deployment.
