# Settings — opțiuni vizuale, fără implementare de produs

Deschide `settings-options.html` direct în browser. Nu cere server, pairing sau chei.
Artefactul nu este inclus în buildul/releaseul web. Eticheta **MOCKUP** rămâne vizibilă;
stările, modelele și notificările sunt demonstrative, fără salvare persistentă ori IO provider.
Câmpul de cheie este intenționat readonly. Reîncărcarea resetează demonstrația.

## Alegerea de design

- **A — Formular compact (recomandată):** provider/cheie/model într-un singur panou,
  apoi rezumat salvat. Cea mai mică schimbare prin callerii T1 existenți.
- **B — Conexiuni + editor:** două conexiuni în stânga, configurarea celei selectate în
  dreapta; pe mobil se așază vertical. Util dacă operatorul folosește ambii routeri.
- **C — Configurare ghidată:** Conexiune → Model → Confirmare, cu rezumat direct la
  revenire. Mai mult ghidaj la prima utilizare, dar mai multe clickuri.

Aceeași simulare deservește toate variantele. Butoanele de deasupra aplicației aleg
layoutul, starea și răspunsul simulat. Încearcă și Salvare fără verificare, eroare,
rezultat neconfirmat, seif blocat și conexiune dezactivată. Avansat păstrează rolurile.
Paletă, Geist, capsule, focus și double-bezel: `../../DESIGN.md` și asseturile existente;
fără fonturi remote, dependențe noi, animații decorative sau direcție vizuală nouă.
Copy-ul românesc și redenumirea vizuală Providers → Modele sunt propuneri, nu modificări
ale rutelor sau traducerea întregii aplicații. Scena nu are run activ; în produs, Stop
și identitatea runului activ rămân în shell pe Settings.

## Verificarea planului și limita recomandată

Bază inspectată: `7214bad9cbd5891012c321bfad2639cb62d3af36`; T1 CLOSED_SCOPED local,
fără mandat T2. Sursele normative decid comportamentul, acest fișier nu este plan concurent.

| Cerință | Canon și stare | Recomandare pentru implementarea ulterioară |
|---|---|---|
| Cheie/config păstrate după browser/restart | Arhitectură §8.1; plan §8/T1. Seif privat AEAD/autounlock și metadata DB există. Proba T1 final-live consemnează Stop→Start fără Save/rebind. | Refolosim mecanismul; UI arată „Cheie salvată”, nu reumple secretul. Nu refacem seiful și nu presupunem o instalare nouă identică instanței existente. |
| Mai multe modele pe aceeași cheie, alese pe rol | Plan §8/SL12 și arhitectură §5.3: default + BRAIN/INVESTIGATOR/VALIDATOR, fiecare referind conexiunea/revizia. Reprezentabile în DTO/DB actuale. Test model verifică numai defaultul, nu override-urile. | Simplificăm prezentarea peste conexiunile/selecțiile existente. Nu salvăm iar cheia și nu duplicăm un credential per model. Execuția agentică reală pe roluri rămâne T2, nu promisiune a machetei. |
| Ambii routeri și run mixt | Plan §4.1 tabel P4b și §12/B14a–G04b, SL33; P4b depinde de T1. Codul are enum/endpointuri pentru doi routeri și maximum o conexiune curentă/provider. OrcaRouter live și mixul nu sunt probate de T1. | Nu e funcție uitată. UI poate reprezenta ce există; proba runului mixt vine cu un consumer RUN real, nu este necesară pentru polish Settings. Nu declarăm P4b închis dintr-un dropdown. |
| Colecție arbitrară de modele favorite | Nu există colecție dedicată în contractele T1/default/override verificate; P4b acoperă configurația/editorul, fără un ticket explicit „favorite”. | În afara primei implementări. Dacă se cere lista independentă de roluri, stabilim intrările/limita/persistența și migrarea minimă; nu o simulăm prin date în browser. |
| Provider suplimentar față de OpenRouter/OrcaRouter | Direcția curentă permite cei doi routeri, nu endpoint arbitrar. | Nu adăugăm o opțiune neverificată în select. Necesită adaptor/policy/probă și decizie de scope. |
| CLI → browser → Dashboard | Arhitectură §4.1–4.2, plan SL03, UI §1–2: cu sesiune validă intrarea directă există; fără sesiune validă se cere pairing manual. Nu este definită o etapă ulterioară de autopair în secțiunile verificate. | Schimbare distinctă a bootstrapului, nu CSS și nu componentă ascunsă din T2. Ticketul one-use prin fragment ar încălca interdicția actuală URL/argv și cere acord asupra amendamentului și riscului rezidual. Fără excepție, trebuie alt canal browser/CLI, cu scope mai mare. |
| Un buton Salvează și verifică | Plan §8 și UI §3/§6: Save zero provider IO, metadata explicită, test finit cu input/cost/acord explicit. | Buton compus cu intenție clară: save/readback → metadata/readback → cel mult un test/readback. Save-only rămâne local. Nu facem probe la boot/reload, retry automat, hot-swap sau succes din simplul HTTP200/catalog. |

Surse: `../../documents/Omnis_Implementation_Plan.md` §4.1/§4.2/§8/§12,
`../../documents/Omnis_MVP_Architecture.md` §4/§5.3/§8.1,
`../../documents/Omnis_UI_UX_Spec.md` §1–3/§6 și
`../../documents/verification/api-key-runtime-t1-evidence/final-live/result.md`.

## Cel mai mic scope după alegere

Prima felie: ProviderSettings/ModelTest și state/copy/CSS prin API-ul existent, cu
regresiile client/DTO/UI afectate. Persistența, ownerul, idempotency, revocarea, Stop,
Cancel și recovery receive-only nu sunt înlocuite. Secvența compusă nu este atomică:
configurația deja salvată rămâne salvată dacă verificarea eșuează; un răspuns pierdut se
reconciliază după ID fără resend. Rezultatul se leagă de model/conexiune/revizie, nu de
un badge permanent „online”. Override explicit vechi nu este șters la editarea defaultului.

Autopair este felie separată numai după decizia de securitate, cu CLI/control/sessions,
bootstrap, contracte generate dacă se schimbă API-ul și testele lor reale. Nu se include
implicit în alegerea layoutului. Biblioteca de favorite și run mix nu sunt prerequisite
ale formularului simplu. Nu promitem zero regresii sau succes dintr-o singură încercare;
reducem riscul prin refolosire, schimbări mici și verificări pe consumerii afectați.

## Self-check fără produs

Cu dependențele Playwright 1.63.0 / Chromium fixate deja instalate în `web/node_modules`:

```sh
node web/design/settings-options.test.mjs
# Opțional, capturi în scratch, niciodată date de produs:
OMNIS_DESIGN_OUTPUT="$TMPDIR/omnis-settings-options" node web/design/settings-options.test.mjs
```

Se verifică trei variante, save-only versus verificare, stări/eroare/UNKNOWN, roluri,
cheie demonstrativă, text inert, tastatură/focus, 320/390/1280/1440, zoom CSS200%,
reset la reload/schimbare variantă și lipsa cererilor externe/erorilor browser.
Testul nu pornește server, Omnis, DB sau provider și nu certifică persistența produsului,
screen-readerele, toate browserele ori estetica aleasă de operator.

RED inițial: self-check exit1/ENOENT înainte de existența HTML. Verificările finale,
reviewul și eventualele remedii sunt în mesajele commiturilor artefactului. Nu actualizăm
CURRENT sau harta globală: niciun status de implementare al produsului nu s-a schimbat.
