# C03 records — arhivă de probe, nu runtime

Produsul probat este `20611d11b26b0334123b87f3ef5926e63e867e55`; corecția test-only și canonicalul final sunt la `c0261a7ae2319b57a0a3154d3e79b2ed908418f8`. Verdictul părintelui este în [CLOSE](../p2-b06b-c03-records-close.json), cu [installed composite](../p2-b06b-c03-records-installed.json), [canonical](../p2-b06b-c03-records-canonical.json) și [cleanup](../p2-b06b-c03-records-cleanup.json).

`manifest.json` mapează fiecare copie exactă la locatorul scratch original și SHA256. Acele locatoare sunt istorice și pot expira; copiile locale sunt dovezile păstrate. Nu există loguri private, DSN, coduri de pairing, cookies, capabilities sau runtime.boot în arhivă. Originalul HTML protejat nu este material al arhivei.

- `review-*.json`: două reviewuri complementare de produs și două reviewuri focalizate ale testului v3/v4.
- `installed-*.json`: rapoartele originale, inclusiv FAIL-uri; nu sunt rescrise ca suite reușite. `installed/` păstrează calificarea, publicarea și recordurile publice ORDERED/EMPTY înainte și după binding/release. `parent-native-readback.json` consemnează citirea independentă a acestor valori/barieră.
- `history/`: forme produse realmente de wheel-ul baseline și readbackurile noi. `installed-history-qa.json` păstrează comparațiile/restartul și limitele observatorului.
- `browser-*.json`: originalele și adjudecarea pe 59 IDs stabile: 47 PASS, 8 excluderi NOT_RUN, 4 NOT_IMPLEMENTED. `images/` conține toate cele 63 capturi inspectate, inclusiv capturile problematice. Perechile viewport/full-page delimitează artefactul capturii; imaginea ilustrativă nepereche rămâne inconclusive, nu aprobare vizuală/WCAG.
- `qa-*/`: surse istorice ale probelor capturate după execuție, nu module ale produsului, comenzi publice sau un framework nou. Nu le executa direct din acest director: folosesc locatoare/pinuri/acceptări/rooturi istorice și nu autorizează adopția ori reutilizarea resurselor. Reproducerul viitor cere root nou, verificarea tuturor pinurilor și autorizarea efectelor conform runnerului existent. Nu afirmăm automat că fiecare helper are hash de execuție măsurat; rapoartele precizează bindings efectiv observate.
- `canonical-before.json`: cele 727 fișiere tracked verificate identice înainte/după canonical, cu originalul protejat exclus înainte de enumerare. Nu este certificare pentru bytes noi adăugați ulterior în documentație.

Pentru folosirea noului consumer, urmează comenzile private din `api/README.md`, nu scripturile de probă. Template-ul publicat păstrează slotul; inputurile PACKAGE_EVAL și RUN sunt separate. Copilul RUN rămâne NO_MODEL/BLOCKED/INCOMPLETE, fără receipts de metodă și fără consumed_input_refs atribuite bindingului.
