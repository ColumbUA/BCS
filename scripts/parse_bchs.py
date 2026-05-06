"""Парсер БЧС роти РРР з Excel у структурований JSON."""
import openpyxl, json, re

SRC = '/app/output/BCHS.xlsx'
OUT = '/app/output/structure.json'

wb = openpyxl.load_workbook(SRC, data_only=True)
ws = wb.active

# Колонки: A=ID, B=Батальйон, C=Рота, D=Взвод/Група, E=Відділення, F=Посада,
# G=Звання за штатом, H=Звання фактичне, I=Позивний, J=ПІБ, K=місце дислокації, L=стан

def s(v):
    if v is None: return ""
    if isinstance(v, (int, float)): return str(v)
    return str(v).strip().replace('…', '').strip()

# Збираємо вузли
company = {
    "name": "Рота радіо та радіотехнічної розвідки",
    "battalion": "Розвідувальний батальйон",
    "subunits": {}   # ключ = назва підрозділу рівня "Взвод/Група"  ("__HQ__" для управління роти)
}

HQ_KEY = "__HQ__"
company["subunits"][HQ_KEY] = {
    "name": "Управління роти",
    "type": "hq",
    "squads": {"__DIRECT__": {"name": "", "positions": []}}
}

for row in ws.iter_rows(min_row=4, values_only=True):
    # row index by col: 0=A,1=B,...
    if not row or all(v is None or s(v) == "" for v in row):
        continue
    bat, comp, plat, sq, pos = s(row[1]), s(row[2]), s(row[3]), s(row[4]), s(row[5])
    rank_st, rank_act = s(row[6]), s(row[7])
    callsign, fio = s(row[8]), s(row[9])
    ppd_now, status = s(row[10]), s(row[11])

    # Пропускаємо рядки-заголовки секцій (тільки A заповнено) та порожні
    if not pos:
        continue
    if not comp:
        continue

    # Визначаємо ключ підрозділу
    if not plat:
        # Управління роти
        sub_key = HQ_KEY
        sq_key = "__DIRECT__"
    else:
        sub_key = plat
        if sub_key not in company["subunits"]:
            t = "platoon" if "взвод" in plat.lower() else ("group" if "груп" in plat.lower() else
                 ("workshop" if "майстер" in plat.lower() else "unit"))
            company["subunits"][sub_key] = {"name": plat, "type": t, "squads": {}}
        if sq:
            sq_key = sq
            if sq_key not in company["subunits"][sub_key]["squads"]:
                company["subunits"][sub_key]["squads"][sq_key] = {"name": sq, "positions": []}
        else:
            sq_key = "__DIRECT__"
            if sq_key not in company["subunits"][sub_key]["squads"]:
                company["subunits"][sub_key]["squads"][sq_key] = {"name": "", "positions": []}

    company["subunits"][sub_key]["squads"][sq_key]["positions"].append({
        "position": pos,
        "rank_state": rank_st,
        "rank_actual": rank_act,
        "callsign": callsign,
        "fio": fio,
        "location": ppd_now,
        "status": status
    })

# Сортуємо взводи в логічному порядку
order_keys = []
# Спочатку HQ
if HQ_KEY in company["subunits"]:
    order_keys.append(HQ_KEY)
# Далі — Група обробки інформації
for k in company["subunits"]:
    if k != HQ_KEY and "груп" in k.lower():
        order_keys.append(k)
# Взводи
for k in company["subunits"]:
    if k != HQ_KEY and k not in order_keys and "взвод" in k.lower():
        order_keys.append(k)
# Решта
for k in company["subunits"]:
    if k not in order_keys:
        order_keys.append(k)

company["order"] = order_keys

# Підрахунок штату
total = 0
for k, sub in company["subunits"].items():
    cnt = sum(len(sq["positions"]) for sq in sub["squads"].values())
    sub["count"] = cnt
    total += cnt
company["total_personnel"] = total

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(company, f, ensure_ascii=False, indent=2)

# Звіт
print(f"Рота: {company['name']}, всього посад: {total}")
for k in order_keys:
    sub = company["subunits"][k]
    print(f"  • {sub['name']}  ({sub['count']} осіб) [{sub['type']}]")
    for sk, sq in sub["squads"].items():
        if sq["name"]:
            print(f"      └─ {sq['name']} ({len(sq['positions'])} осіб)")
        else:
            print(f"      └─ (прямого підпорядкування) ({len(sq['positions'])} осіб)")
