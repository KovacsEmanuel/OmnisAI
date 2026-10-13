# B06b — identitatea M1/M2 și prerechizitul de stocare

Aceasta este decizia locală pentru următoarea felie din plan §7.1, nu un plan concurent și nu acceptare B06b/P2. Baza de produs: `f6b6c93b97eb36dafb546d869999871d17779b29`; PARTIAL este acceptat scoped în `7615a33`. Nu se reiau probele acceptate sau auditul launch.

## Blocaj reprodus, fără implementare pretinsă

[Autorul](p2-bound-predicates-evidence/result-qualification-blocked-author.json) a oprit înaintea editării produsului: validatorul `managed_contract.record` și CHECK-ul `managed_record` acceptă numai revision=1; PK-ul id nu poate păstra două revizii ale aceluiași UUID. Părintele a reprodus pe aceeași SOURCE boundary cu SQL double declarat:

```text
env -u PYTHONPATH -u PYTHONHOME -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 api/.venv/bin/python -I -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -c api/pyproject.toml --basetemp=/home/kali/.hermes/cache/scratch/p2-rq-parent-schema-red /home/kali/.hermes/cache/scratch/p2-result-qualification-schema-red.py -q --tb=line
```

**1 FAIL / 1 PASS, 0.85s, exit1**: M1 atinge boundary-ul, M2 este MANAGED_REJECTED înainte SQL. Nu este probă PostgreSQL; GREEN de produs/migrare/native NOT_RUN. Rapoartele și SHA source au fost verificate; nu există diff de produs.

## Adjudecarea părintelui

Acceptăm recomandarea [arhitectului read-only](p2-bound-predicates-evidence/result-qualification-schema-decision-review.json) ca **decizie de implementare**, nu verdict de cod sau runtime. Canonul §6.3/§9.3 cere adresabilitate exactă și identitate logică stabilă pentru buget; nu prescrie textual PK-ul sau UUID-ul fiecărei revizii. Alegerea locală este explicită:

- M1/M2 au **același MissionSpec.id**, revision integer1/integer2 și digesturi canonice independente. Cheia logică `(run_id, mission_id, FOCUS_BOOTSTRAP)` nu se schimbă. Felia curentă FULL_ASSESSMENT nu implementează/fabrică buget focused.
- Păstrăm `managed_record` și toate FK-urile sale existente/revision1/immutability. Extindere **un singur tabel `managed_mission_revision`**, numai pentru mission/revision2, PK `(mission_id, revision)` și ownership/run ancorate în misiunea originală. Nu un ledger general, owner, scheduler sau tabel per agent.
- M2 citează exact M1 ca unic predecessor mission în `basis_refs`; acest rol restrâns se definește aici, nu se deduce dintr-un basis arbitrar. Constructorul backend verifică payloadul strict și extensia aditivă, nu primește freshness/ELIGIBLE de la client. Datele/goalul/modul material schimbate nu devin M2 compatibil.
- În SQL, guardul root-kind/ownership/lineage și immutability sunt enforce/attest exact; NULL/missing/coercions nu pot trece CHECK. CanonicalJSON/digest se calculează și reverifică în backend, nu din serializarea JSONB.
- Rezolvarea mission se face prin Ref complet, nu latest/ID-only. Graph poate conține M1 și M2 fără last-row-wins; reconstruirea TaskResult/MethodCheck/CriterionOutcome citează **mission din headerul istoric** și păstrează bytes/refs. Nonmission și generic catalog rămân revision1.
- Nicio admitere de lucru nou sub contextul revizuit: refuz explicit înainte assignment/native/tools/model. Replay/readback M1 nu este grant. Nu rescriem context/run/focus/cursor/headerurile ca să indice M2.

Refuzăm UUID nou/revision1 pseudo-M2; UUID nou/revision2 cu numai basis arbitrar ar necesita încă un contract de logical-root/buget. Rekey-ul global surrogate/composite ar modifica FK-uri necerute de consumerul curent; extensia mission-only este aleasă pentru frontiera mai mică, **nu dovedită prin test că ar fi minimul absolut**.

## Felii coerente și limita de fișiere

1. **Prerechizit DB**: migrare nouă `0013_mission_revisions` după0012; DDL attestation și pinuri current API/CLI/bundle/fixture sincronizate, plus teste reale empty/populated0012→0013, ownership/root-kind/lineage/immutability/NULL/denials. Migrațiile istorice și probele explicite0011→0012 rămân originale. Fără consumer Python M2 sau ResultQualification pretins încă.
2. **Consumerul M2**, după acceptarea prerechizitului: validator/constructor mission-only, store/ref/graph/readback și command idempotent existente, refuz new-admission, compatibilitate receive-only pentru checker/rule exact pre-edit, probe pe rezultat M1 autentic.
3. **ResultQualification**, separat: compatibilitate/current-state finită pe records, istoric versus curent și lipsa freshness/auth proof fără ELIGIBLE fabricat. Nu verdict funcțional, wake sau replan general.

Ordinea detaliază dependența deja obligatorie B06b, nu mută gate-ul sau planul. Limita inițială8paths fără migrare/tabel este explicit depășită **numai pentru prerechizitul schema/pins coerent**: un autor poate atinge noua migrare, core schema/db attestors, pinuri API/CLI/bundle și testele/fixture-urile lor reale. Sunt modificări inseparabile ale unui singur head, nu permisiune pentru refactor sau schimbări de lifecycle. Consumers/qualification se autorizează ulterior separat.

## Probe, resurse și rollback

Două reviewuri complementare pe snapshot exact înainte de PG; părintele reproduce findings și adjudecă. Apoi runnerul existent, **fixture nouă proprie PG18 UDS/no-network**, empty și populated0012→0013; conexiuni close/reopen și history/FK/constraints/digests readback. SOURCE/driver doubles și collection nu sunt PG PASS. Canonicalul complet rămâne pentru frontiera finală de integrare; pinul vechi nu devine READY doar prin stamp.

Nu migrăm sau pornim r1/DB-ul operatorului, nu adoptăm fixture-uri vechi. DDL before/after:0012→0013 numai disposable. Datele/logurile rămân păstrate și resursele proprii se verifică exact. Git revert inversează source, **nu DDL/history**. Downgrade refuză; orice migrare ulterioară de date ale operatorului cere instanță oprită/fenced, backup complet compatibil și restaurare verificată explicit autorizate. Nu drop M2, disable triggers sau simplu restamp ca rollback.

**Stare: M1/M2 BLOCKED_SCHEMA până la prerechizit; ResultQualification NOT_IMPLEMENTED; B06b/G02/P2 PARTIAL/NOT_CLOSED; P4a-minim NOT_IMPLEMENTED; canonical final NOT_RUN.** Fără cont/provider/inferență/target/P3/r1/global/push. Reviewul acestei decizii nu este acceptare PostgreSQL sau cod implementat.
