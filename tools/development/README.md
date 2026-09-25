# Unelte pentru dezvoltarea Omnis

Aceste unelte sunt separate de aplicație și de catalogul runtime de pentest. Nu înlocuiesc planul din `documents/` și nu sunt MCP-uri globale pornite automat.

| Sursă cerută | Integrare și stare | Dovadă / procedură |
|---|---|---|
| [Reticle](https://github.com/reticlehq/reticle) | Helper local izolat, pin `@reticlehq/server@3.2.0`; MCP direct verificat pe fixture. Nu este încă instrumentarea aplicației. | [Setup, licență și limite](reticle/README.md); [rezultat MCP](reticle/verification/mcp-smoke.json); [CLI reload nereușit](reticle/verification/cli-reload-failure.json) |
| [Chisel](https://github.com/ckanthony/Chisel/tree/main) | **NO-GO**, skill de evaluare prezent, server dezactivat/neînregistrat. Folosim uneltele native de fișiere. | [Motive și criterii de reevaluare](chisel/README.md); [probe reale individuale](chisel/audit.json) |
| [ui-skills](https://github.com/ibelick/ui-skills) | Trei skill-uri adaptate pentru frontend, accesibilitate și performanță; surse/MIT fixate, fără CLI/registry live. | `.hermes/skills/omnis-frontend`, `omnis-accessibility`, `omnis-frontend-performance`, fiecare cu `references/upstream.json` |
| [anti-slop](https://github.com/dmmulroy/anti-slop) | Trei reguli Oxlint selectate și executabile; fără politici care interzic validarea la boundary. | [Setup, policy și regresii](anti-slop/README.md); [proveniență](anti-slop/upstream.json) |

## Intrarea standard

[Inventarul verificat al celor 12 skill-uri](skills-manifest.json) include versiuni, digesturi și rezultatul încărcării prin loaderul Hermes real. Acesta este un snapshot de verificare, nu un auto-installer sau catalog de pentest; după modificarea unui skill, rerulează verificarea înainte să actualizezi snapshotul.

După instalarea dependențelor documentare și a pachetului anti-slop din lock:

```sh
# Într-un checkout nou; environment dedicat documentelor/uneltelor.
uv venv .venv
uv pip install --python .venv/bin/python -r documents/requirements-docs.txt
npm --prefix tools/development/anti-slop ci --include=dev --ignore-scripts --no-fund
PATH="$PWD/.venv/bin:$PATH" make check
```

Folosește un mediu Python izolat pentru instalare; comanda de mai sus nu cere modificarea environmentului Hermes. `make check` verifică documentele, launcher-ele și controalele anti-slop, nu pretinde că testează aplicația încă neimplementată. Proba completă Reticle este separată/opt-in, conform README-ului ei; Chisel nu are un gate „verde” ascuns în check.

Regresia browser a documentelor/prototipului rămâne separată și se rulează la schimbări de UI. Aspectul prototipului `df17a29` a fost acceptat explicit; pornirea implementării este separată și se cere în sesiunea nouă. Nu confundăm smoke-uri de unelte cu testele viitoare React/FastAPI/PostgreSQL/Hermes ale produsului.

## Actualizare și rollback

- Nu instala întregul catalog, nu rula scripturi remote și nu înlocui stackul după preferințele unui skill importat.
- Păstrează SHA-uri, lockfiles, licențe și override-uri; testează controlul pozitiv și negativ înainte de a avansa o versiune.
- Corectează procedura pe baza eșecurilor reale și păstrează remedierea în commit separat când modifică independent comportamentul.
- [Setările Hermes și inversele lor](hermes-settings.json) sunt distincte de revert Git. Modelul/providerul și SOUL nu au fost schimbate. Skill-urile de dezvoltare sunt încărcate la cerere în checkoutul trusted.
