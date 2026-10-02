# M22 — config non-secret în worktree izolat

Bază: `ad3e1f28825ab6ff38361b940bbf3482493d03e4`, branch `p0-m22-config`.
Scope: U21–U23, parser strict și consumatorii P0 actuali; nu aprobă SL04/G00.

## Contract de implementare și probă

- Config numai `$XDG_CONFIG_HOME/omnis/config.toml`, implicit `~/.config/omnis/config.toml`; lipsa nu creează directoare/fișiere.
- Patru chei root: `port` (1024–65535; default 8765), `startup_timeout_seconds` (30–300; default 180), `shutdown_timeout_seconds` (15–180; default 180), `cleanup_timeout_seconds` (30–180; default 100). Numai integer exact; nicio cheie necunoscută sau secretă.
- CLI explicit > config > defaults numai la instanță nouă. Receiptul/instance origin existent rămâne autoritate inclusiv la restart. O selecție explicită divergentă refuză, fără rescrierea originului, journalului sau adoptarea datelor.
- Refuz sanitizat înainte de lock/Docker/UDS/browser pentru config invalid în default/start/status/pair/open/stop. Fișier privat 0600, director Omnis 0700, owner curent, fără hardlink/symlink ori ancestor replaceable; path absolut/canonic. Config absent nu autorizează ignorarea unei căi existente nesigure.
- Deadline startup/shutdown monotonic propagat în consumatorii existenți; cleanup are allowance nou separat numai după eșecul startupului. Așteptările forwarder consumă deadline-ul, nu un timeout fix mai mare.
- Căi permise: `cli/src/omnis_cli/config.py`, wiring în main/start/stop/status/verified, `cli/tests`, `cli/README.md`, acest document. Nicio modificare globală/HTML/Makefile/profil. Dacă un consumator real cere alt fișier, justificarea precede editarea aici.
- TDD vertical, output RED/GREEN real în scratchul privat al worktree-ului; source import verificat; build/wheel instalat și executat din cwd extern cu HOME/XDG private și hashuri comparate.
- Fără Docker/PG/OCI, servicii existente, network provider/ținte sau push. Boundary cu runtime substituit nu dovedește deadline fizic Docker. Gate-urile fizice și review independent sunt NOT_RUN/delegare părinte; reconcilierea cu noul Stop este obligatorie înainte de integrare.
- Rollback: revert commiturile M22 în ordine inversă; nu există migrare ori rescriere de date/config a operatorului.

## Proveniență inițială

`uv 0.12.19`; `uv sync --locked --no-config --offline --directory api` și `cli`: exit 0. Python 3.13.15. `cli/.venv/bin/python -I` importă `omnis_cli` din acest worktree (`cli/src/omnis_cli/__init__.py`), nu principalul.

## Rezultate

ÎN LUCRU. Probe source/wheel și SHA-uri se consemnează după execuție. G00 rămâne deschis, integrarea neaprobată.
