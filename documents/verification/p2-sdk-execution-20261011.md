# Continuare autorizată — SDK executat; FAIL păstrat și PASS serializer scoped

Owner `20261011_094100_1f2139`, sursă `36e0252`, branch `p04-control-topology-wip`. Mandatul actual permite faza2 și fixture-uri noi inerte; publicarea promptului este verificată și nu a fost repetată. Originalul protejat nu a fost citit/copat/hashuit/staged. Mission și cron sunt nemodificate; inferența produsului rămâne HOLD.

## Incrementul framing și execuția reală

[Receiptul](p2-sdk-execution-20261011.json) păstrează full body UTF-8, kwargs/extensions, namespace și audit traces **din SDK2.24.0 real**, nu din sursă ori provider fabricat. RED parser-only exact: standalone `--` refuzat exit2; driverul identity are unittest exit1. GREEN exec-only Python `-c` cu `os.execv`/repr: trei controale exit0, inclusiv quotes/Unicode/metacaractere. Runnerul `ops/run_test_db_gate.py` și produsul sunt byte-unchanged. Numai noul driver împachetează argv; bwrap/seccomp/oracolele nu sunt slăbite.

Scope-urile și roots noi sdk01/sdk02 au fost înregistrate înaintea efectelor în controlul `implementation`.16 wheeluri/4.742.943bytes și1500 fișiere venv au fost copiate/verificate în fiecare root privat, fără redownload/reinstall sau utilizarea mediului activ Hermes. Vechiul root este numai input read-only, fără adopție de familie/autoritate. Reviewurile dezvoltării au Sol6.1 900k/openai-codex/xhigh/priority/YOLO citite pe obiectul real înaintea primei cereri. SDKQA-01 (pinul probei observation-only nereconciliat) este reprodus exit1, remediat înainte de mkdir și re-revizuit APPROVED_SCOPED; driverul diagnostic ulterior este APPROVED_SCOPED pe hashes exacte. Nu sunt reviews de produs.

SDK01 a pornit real și a eșuat la assertion finală IO, outer/gate1/family_drained=true, fără body retenționat. Eșecul rămâne. SDK02 este **încercare distinctă după un eșec settled**, nu replay incert: root nou, retenție full înaintea aceleiași assertion, outer/gate1/family_drained=true. În niciuna nu există răspuns provider.

## Măsurători și blocker concret

- Baseline și bypass standalone fixat au bytes identice:259 bytes, SHA256 `98aae6d952597424ac4691bc80c8d83c348a518ca42bef20292f8c1675ff4f97`.
- `extra_body` suprascrie messages și model; un câmp nou ajunge în body. Caracterizare SDK, **nu** refuz Omnis trecut sau bypass al veto-ului managed.
- Fiecare caz păstrează model/messages/tools/stream/n/output cap, HTTP bytes și timeout separat în extensions; zero defensive transport calls. Namespace user/pid/mnt/net diferă efectiv de parent; NoNewPrivs1/Seccomp2/filter1 sunt readback real.
- Oracolul final NO-IO este **FAIL**, nu SDK PASS: prima construire a headerelor SDK cere metadata platform; Python3.13 `platform.processor` încearcă `subprocess.check_output(['uname','-p'])`. Auditul înregistrează și refuză înaintea efectului; SDK prinde această excepție metadata și continuă serializarea. Stiva reală fixează mecanismul; nu este DNS/provider/network send.

La checkpointul SDK02, bindingul wire final rămânea nedecis până la proba strictă NO-IO. Dependența concretă era reconcilierea metadata SDK sub aceeași confinare, fără relaxarea zero-IO al serializării, fără fake response și fără al treilea audit generic. Nu se prezintă consumerul DTO produs complet. G-DATA-EARLY/SL10, G-MODEL/SL11 și faza2 rămân PARTIAL/NOT_CLOSED.

## SDK03 — reconciliere executată, numai serializer scoped

[Receiptul SDK03](p2-sdk-execution-pass-20261011.json): **outer/gate0, family_drained=true**, patru full bodies/kwargs/extensions, aceleași digests și equality baseline/bypass măsurate, socket denials3, zero defensive transport și zero evenimente IO neașteptate în serializare. Namespace user/pid/mnt/net distincte de parent și seccomp sunt readback din proces. Root nou sdk03 și pin exact înregistrate înainte de efect; copiere verificată, fără reinstall/redownload sau adopție.

Fixul QA este un control negativ **explicit înaintea oricărui create**, nu o modificare SDK/platform: sub seccomp/audit active, metoda stock `client.platform_headers()` produce un singur Popen refuzat, atribuit prin stiva `get_platform/from_subprocess`. SDK-ul prinde denialul și cache-uiește valoarea sa reală `X-Stainless-OS=Unknown`. Lista independentă păstrează ambele negative (DNS și metadata); oracolul final refuză orice eveniment suplimentar în serializer. Review independent `20261011_100612_f4b20d`, Sol6.1/900k/openai-codex/xhigh/priority/YOLO verificat înainte de cerere, APPROVED_SCOPED pe hashes exacte; limita SDK03-LIMIT-COLD-START este acceptată explicit: **nu zero tentative IO la cold-start, nu SDK reparat, nu warm/turn ori inferență**. SDK01/02 rămân FAIL, vechiul prelaunch rămâne UNCERTAIN.

Reprezentarea post-bypass este acum măsurată și permite contractul primei felii DTO la sinkul comun direct/worker. Acest PASS nu este enforcement DTO, proveniență turn/config, reserve/SENT/Stop/caps sau INSTALLED_NATIVE. Veto-ul produsului și HOLD-ul live sunt neschimbate; consumerul produs complet și faza2 nu sunt declarate livrate.

Toate datele/logurile/receipturile/markerii sunt păstrate; nicio ștergere sau adopție/replay de cleanup. DB/OCI/native/browser/canonical nu au rulat în această felie SDK. Revertul acestui checkpoint este Git-only, nu șterge resursele/eșecurile păstrate. Faza3/B07/targets/account/r1/global/push sunt excluse.
