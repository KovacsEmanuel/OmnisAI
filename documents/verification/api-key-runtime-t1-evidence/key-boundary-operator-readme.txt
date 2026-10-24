OMNIS T1 — instalare durabilă separată, oprită

Root: /home/kali/.local/share/omnis-t1-ready-33ee99
Origin după Start: http://127.0.0.1:8772/
Artefact normal: 4ae4e51d41af781b4edfd9aeb5b1443a45e9c5dd5b6a62dcee4ae56404fc3cc1
Profil: t1-provider-settings; schema: 0015_model_test_v2.
Stare la predare: STOPPED, generation 4; datele păstrate. Nu există autostart.
CLI/Python/bundle/release sunt durabile, în afara scratch-ului. Nu reconstruiți
sau reinstalați pentru utilizarea normală. Nu modificați receipturile lifecycle.

1. Deschideți un terminal propriu, izolat de configurația ambientală:

env -i \
 HOME=/home/kali/.local/share/omnis-t1-ready-33ee99/home \
 XDG_CONFIG_HOME=/home/kali/.local/share/omnis-t1-ready-33ee99/c \
 XDG_DATA_HOME=/home/kali/.local/share/omnis-t1-ready-33ee99/d \
 XDG_STATE_HOME=/home/kali/.local/share/omnis-t1-ready-33ee99/s \
 XDG_RUNTIME_DIR=/home/kali/.local/share/omnis-t1-ready-33ee99/r \
 PATH=/home/kali/.local/share/omnis-t1-ready-33ee99/cli/bin:/usr/bin:/bin \
 TMPDIR=/home/kali/.hermes/cache/scratch \
 PYTHONDONTWRITEBYTECODE=1 \
 /bin/bash --noprofile --norc

2. În acel terminal (aceleași roots pentru TOATE comenzile):

omnis status --json
omnis start --no-open --json
omnis status --json
omnis pair
omnis open

Start nou este explicit. Continuați Pair numai dacă status este READY.
Pair cere TTY și emite un cod de unică folosință, cu expirare în 5 minute.
Nu îl salvați în fișiere, loguri sau chat. Introduceți-l în formularul local.
În această sesiune headless, `omnis open` a dat BROWSER_LAUNCH_FAILED/exit3;
serviciile au rămas READY. Alternativa: deschideți manual originul de mai sus.
Deschiderea manuală și interfața reală au fost verificate într-un browser propriu.

3. Settings → Providers

Cheia este goală/write-only, Vault UNCONFIGURED, nicio conexiune sau selecție
salvată. Save API key și Save model selection sunt dezactivate în starea goală.
Test model are Metadata NOT_REQUESTED, test dezactivat și hintul de configurare.
Reload a păstrat aceste stări. Nu a fost introdusă nicio cheie, nici sintetică.
O viitoare cheie se introduce numai în interfața web; nu în CLI sau config.toml.
Salvarea/metadata/testul/inferența nu au fost exercitate ori autorizate de QA.

4. Oprire cu păstrarea datelor

În Settings → Runtime & data: Log out, apoi în terminal:

omnis stop --json
omnis status --json
exit

Stop și Status au returnat STOPPED/exit0; cele trei containere, rețeaua proprie,
forwarderul, listenerul8772 și socketurile sunt absente. Directoarele DB/vault
și toate roots rămân păstrate. La UNCERTAIN/RECOVERY_REQUIRED nu relansați orb,
nu ștergeți date sau jurnale și nu adoptați altă instanță.

Config: c/omnis/config.toml (0600), port8772, bugete nemodificate180/180/100.
Date: s/omnis; release instalat: d/omnis/releases/0.1.0; CLI: cli/bin/omnis.
Raport QA și capturi: /home/kali/.hermes/cache/scratch/t1-33ee99/evidence/ready-install-result.json
și ready-install-result.md. QA scoped nu este canonical/T1 global PASS,
certificare provider ori aprobare estetică. Părintele a verificat separat
Restart → READY generation3 → Stop/status STOPPED generation4, exit0;
cele trei containere noi, rețeaua, forwarderul și socketurile sunt absente,
iar identitățile directoarelor DB/vault/vault-key sunt neschimbate.

Frontiera operatorului — NU a fost executată și NU este acord implicit:

Configurație propusă pentru prima probă, de confirmat explicit: OpenRouter,
model exact openai/gpt-4.1-mini, Default output tokens 128, fără override-uri.
ID-ul apare în documentația publică oficială:
https://openrouter.ai/openai/gpt-4.1-mini
Aceasta nu verifică accesul cheii sau compatibilitatea metadata live.

După acordul de folosire a conexiunii, cheia se introduce exclusiv în UI.
Save API key este local. Apoi Save model selection explicit pe conexiunea
și revizia actuale. Nu trimiteți cheia prin chat, argv sau environment.

Acordul provider-live trebuie să numească separat:
  1. Un Refresh model metadata: GET https://openrouter.ai/api/v1/models,
     maximum15s, răspuns bounded2MiB, fără retry/redirect.
  2. Numai după READY autentic: un Test model, maximum1apel/300s,
     maximum128output tokens, fără tools/ținte/retry/fallback automat.

Inputul fix transmis, afișat și în UI:
  System: Respond only with OMNIS_MODEL_TEST_OK. Use no tools.
  User: This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.

Model input serializat≤32768bytes; text reținut≤8192bytes, trunchiere explicită.
Costul poate fi taxat de provider; un cost neobservat rămâne UNKNOWN, nu zero.
Un timeout/UNKNOWN nu se retrimite automat. Readback/Cancel/Stop nu sunt refund.
Metadata/Test/usage și frontierele finale live rămân NOT_RUN; T1 PARTIAL,
nu T2 automat. Nicio combinație de routeri sau tool loop nu este certificată.
