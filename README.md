# OmnisAI

Platformă web locală pentru evaluări Web/API autorizate, cu Brain/copii nativi Hermes și skills versionate.

**Stare:** baseline de implementare pregătit; aplicația nu este implementată. Au fost executate probe izolate de dependențe și verificări ale documentelor/prototipului, nu scanări sau integrarea live Hermes.

## Începe aici

- **[Plan de implementare v2 — HTML](documents/Omnis_Implementation_Plan.html)** · [Markdown](documents/Omnis_Implementation_Plan.md)
- **[Arhitectura MVP v1 — HTML](documents/Omnis_MVP_Architecture.html)** · [Markdown](documents/Omnis_MVP_Architecture.md)
- **[Stack și versiuni — HTML](documents/Omnis_Stack_Baseline.html)** · [Markdown](documents/Omnis_Stack_Baseline.md) · [Registru JSON](documents/Omnis_Stack_Baseline.versions.json)
- **[UI/UX — HTML](documents/Omnis_UI_UX_Spec.html)** · [Markdown](documents/Omnis_UI_UX_Spec.md) · [DESIGN.md](DESIGN.md)
- **[Prototip UI navigabil — DEMO offline](documents/Omnis_UI_Prototype.html)**
- **[Re-review și readiness — HTML](documents/Omnis_Implementation_Readiness_Review.html)** · [Markdown](documents/Omnis_Implementation_Readiness_Review.md)

### Decizia de pornire

**GO:** fundație, engagement persistent, web și probe Hermes inerte. **NO-GO pentru target effects:** până la rezolvarea gate-ului de dependențe proxy, bindingului task–copil și confinării. `mitmproxy 12.2.3` publicat este respins pentru trafic target din cauza dependențelor cu advisories; nu îl ascundem sub un dependency resolve reușit. Testele provider cer separat cont, model, acord și buget.

Planul include trasabilitatea tuturor celor 12 recomandări inițiale. Acest pachet este baza curentă; propunerile de mai jos sunt istoric și nu reintră implicit în scope.

## Dovezi și întreținerea documentelor

- [Probe de stack și instrucțiuni de reproducere](documents/verification/README.md)
- [Output real al probelor de dependențe](documents/verification/stack-probe.json)
- [Surse publice și extrasele baseline-ului](documents/Omnis_Baseline.sources.json)
- [Tokenuri DTCG exportate](documents/Omnis_Design.tokens.json)

Markdown este sursa editabilă a documentelor; `python scripts/render_docs.py` regenerează cititoarele HTML, iar `--check` detectează drift. Dependența de documentare este în `documents/requirements-docs.txt`. Rendererul primește doar Markdown trusted al proiectului, niciodată evidence/importuri ale țintei.

HTML-urile și prototipul se deschid local, fără server sau resurse de afișare externe. Prototipul nu are backend, nu acceptă credentiale și nu execută trafic de țintă. Probele din `documents/verification/stack-probe-inputs/` sunt teste de compatibilitate, nu aplicația Omnis.

## Istoric păstrat

- [Review critic inițial, înaintea planului v2](documents/Omnis_Implementation_Plan_Review.md) · [surse](documents/Omnis_Implementation_Plan_Review.sources.json)
- [Propunerea local MVP și auditul contractelor Hermes — HTML](documents/Omnis_Hermes_Local_MVP_Integration_Proposal.html) · [Markdown](documents/Omnis_Hermes_Local_MVP_Integration_Proposal.md)
- [Fezabilitate inițială — HTML](documents/Omnis_Hermes_Feasibility_Review.html)
- [Propunerea inițială — Markdown](documents/Omnis_Hermes_MVP_Architecture_Proposal.md)

Niciun document nu constituie autorizație de scanare, dovadă de eficacitate universală sau aprobare pentru folosirea credentialelor personale.
