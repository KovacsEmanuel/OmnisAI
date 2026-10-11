# Continuare autorizată — SDK executat, oracol NO-IO încă FAIL

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

Bindingul wire final rămâne nedecis până la proba strictă NO-IO. Următoarea dependență este reconcilierea explicită a metadata SDK sub aceeași confinare, fără relaxarea zero-IO al serializării, fără fake response și fără al treilea audit generic. Nu se prezintă consumerul DTO produs complet. G-DATA-EARLY/SL10, G-MODEL/SL11 și faza2 rămân PARTIAL/NOT_CLOSED.

Toate datele/logurile/receipturile/markerii sunt păstrate; nicio ștergere sau adopție/replay de cleanup. DB/OCI/native/browser/canonical nu au rulat în această felie SDK. Revertul acestui checkpoint este Git-only, nu șterge resursele/eșecurile păstrate. Faza3/B07/targets/account/r1/global/push sunt excluse.
