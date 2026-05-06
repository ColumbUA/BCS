"""Генератор MS Project XML — Бойове управління ротою РРР.

Завдання — типові етапи управління ротою (24-год цикл):
  1. Отримання бойового завдання (від КБ)
  2. З'ясування завдання + орієнтування підлеглих
  3. Розрахунок часу
  4. Оцінка обстановки (противник, свої, район, час, тил)
  5. Прийняття рішення
  6. Постановка задач підрозділам (бойовий наказ/розпорядження)
  7. Організація взаємодії, забезпечення, управління
  8. Контроль готовності, виконання
  9. Доповіді (поточні + підсумкова)
Виконавці — посадові особи, які реально присутні у БЧС (із позивними/ПІБ).
"""
import json, datetime
from xml.sax.saxutils import escape

with open('/app/output/structure.json', encoding='utf-8') as f:
    data = json.load(f)


def x(s): return escape(s if s else "")


# ---------- Підбираємо ключових виконавців з БЧС ----------
def find_position(sub_name_kw, pos_kw):
    for sub in data["subunits"].values():
        if any(kw in sub["name"].lower() for kw in sub_name_kw) or sub_name_kw == [""]:
            for sq in sub["squads"].values():
                for p in sq["positions"]:
                    if any(kw in p["position"].lower() for kw in pos_kw):
                        return p
    return None


def find_in_hq(pos_kw):
    for sub_key, sub in data["subunits"].items():
        if sub["name"] == "Управління роти":
            for sq in sub["squads"].values():
                for p in sq["positions"]:
                    if any(kw in p["position"].lower() for kw in pos_kw):
                        return p
    return None


actors = []  # list of dicts {role, fio, callsign, rank}

def add_actor(role_label, person, fallback_pos=""):
    if person:
        fio = person["fio"] or ""
        callsign = person["callsign"] or ""
        rank = person["rank_actual"] or person["rank_state"] or ""
        if fio:
            display = fio + (f' «{callsign}»' if callsign else "")
        else:
            display = role_label
        actors.append({
            "role": role_label,
            "name": display,
            "rank": rank,
            "position": person["position"]
        })
    else:
        actors.append({"role": role_label, "name": role_label, "rank": "", "position": fallback_pos})


# Командир роти
add_actor("Командир роти", find_in_hq(["командир роти"]) and {**find_in_hq(["командир роти"])} or None, "Командир роти")
# ЗКР з ПС
add_actor("ЗКР з психологічної підтримки", find_in_hq(["заступник"]), "ЗКР з ПП")
# Старший технік
add_actor("Старший технік роти", find_in_hq(["старший технік"]), "Старший технік")
# Головний сержант роти
add_actor("Головний сержант роти", find_in_hq(["головний сержант"]), "Головний сержант")
# Сержант із МЗ
add_actor("Сержант із МЗ", find_in_hq(["матеріального забезпечення"]), "Сержант із МЗ")
# Старший бойовий медик
add_actor("Старший бойовий медик", find_in_hq(["медик"]), "Бойовий медик")

# Начальник групи обробки інформації
def find_in_sub(sub_kw, pos_kw):
    for sub in data["subunits"].values():
        if any(kw in sub["name"].lower() for kw in sub_kw):
            for sq in sub["squads"].values():
                for p in sq["positions"]:
                    if any(kw in p["position"].lower() for kw in pos_kw):
                        return p
    return None

add_actor("Начальник ГОІ", find_in_sub(["обробк"], ["начальник групи"]), "Начальник ГОІ")

# Командири взводів — у порядку
plat_order = ["1 взвод радіорозвідки", "2 взвод радіорозвідки",
              "взвод радіоелектронної розвідки", "взвод безпілотних"]
for i, pkw in enumerate(plat_order, start=1):
    person = find_in_sub([pkw], ["командир взводу"])
    label = f"КВ — {pkw.title()}"
    add_actor(label, person, label)

# Начальник майстерні
add_actor("Начальник РМО", find_in_sub(["майстер"], ["начальник майстерні"]), "Начальник РМО")


# ---------- Завдання — цикл управління ----------
# Структура: phases з підзавданнями
phases = [
    {
        "name": "I. Підготовка управління",
        "tasks": [
            ("Отримання бойового завдання від командира батальйону", 1, ["Командир роти"]),
            ("З'ясування завдання, виділення основних задач", 2, ["Командир роти", "ЗКР з психологічної підтримки"]),
            ("Орієнтування заступників і командирів підрозділів", 1, ["Командир роти"]),
            ("Розрахунок часу на підготовку бойових дій", 1, ["Командир роти", "Головний сержант роти"]),
        ]
    },
    {
        "name": "II. Оцінка обстановки",
        "tasks": [
            ("Оцінка противника (склад, можливості, вірогідні дії)", 4, [
                "Начальник ГОІ", f"КВ — {plat_order[0].title()}",
                f"КВ — {plat_order[1].title()}", f"КВ — {plat_order[2].title()}",
                f"КВ — {plat_order[3].title()}"]),
            ("Оцінка своїх сил, стану підрозділів та озброєння", 2, [
                "Командир роти", "Старший технік роти", "Начальник РМО"]),
            ("Оцінка району дій (місцевість, маршрути, позиції)", 3, [
                "Командир роти", f"КВ — {plat_order[0].title()}",
                f"КВ — {plat_order[1].title()}"]),
            ("Оцінка часу, метеоумов, стану доріг", 1, ["Старший технік роти"]),
            ("Оцінка тилового, медичного та психологічного забезпечення", 2, [
                "Сержант із МЗ", "Старший бойовий медик", "ЗКР з психологічної підтримки"]),
        ]
    },
    {
        "name": "III. Прийняття рішення",
        "tasks": [
            ("Формування задуму бойових дій роти", 3, ["Командир роти"]),
            ("Визначення задач підрозділам та порядку взаємодії", 2, ["Командир роти"]),
            ("Доповідь рішення командиру батальйону, отримання схвалення", 1, ["Командир роти"]),
        ]
    },
    {
        "name": "IV. Постановка задач підрозділам",
        "tasks": [
            ("Бойовий наказ / бойове розпорядження по роті", 2, ["Командир роти"]),
            ("Постановка задач Групі обробки інформації", 1, ["Начальник ГОІ"]),
            ("Постановка задач 1 взводу радіорозвідки", 1, [f"КВ — {plat_order[0].title()}"]),
            ("Постановка задач 2 взводу радіорозвідки", 1, [f"КВ — {plat_order[1].title()}"]),
            ("Постановка задач взводу радіоелектронної розвідки", 1, [f"КВ — {plat_order[2].title()}"]),
            ("Постановка задач взводу БпАК", 1, [f"КВ — {plat_order[3].title()}"]),
            ("Постановка задач РМО (підготовка ОВТ)", 1, ["Начальник РМО"]),
        ]
    },
    {
        "name": "V. Організація забезпечення та взаємодії",
        "tasks": [
            ("Організація розвідувально-інформаційного обміну", 2, ["Начальник ГОІ", "Командир роти"]),
            ("Організація зв'язку та управління (радіо, шифрозв'язок)", 2, ["Старший технік роти"]),
            ("Тилове та технічне забезпечення (ПММ, ЗІП, харчування)", 2, ["Сержант із МЗ", "Начальник РМО"]),
            ("Медичне забезпечення та евакуація", 2, ["Старший бойовий медик"]),
            ("Психологічна підтримка особового складу", 2, ["ЗКР з психологічної підтримки"]),
        ]
    },
    {
        "name": "VI. Контроль і виконання",
        "tasks": [
            ("Контроль готовності підрозділів до виконання задач", 2, [
                "Командир роти", "Головний сержант роти"]),
            ("Виконання бойового завдання — ведення розвідки", 8, [
                "Начальник ГОІ", f"КВ — {plat_order[0].title()}",
                f"КВ — {plat_order[1].title()}", f"КВ — {plat_order[2].title()}",
                f"КВ — {plat_order[3].title()}"]),
            ("Поточний контроль і коригування дій", 4, ["Командир роти"]),
        ]
    },
    {
        "name": "VII. Доповіді та підсумки",
        "tasks": [
            ("Поточні доповіді про обстановку до КБ", 1, ["Командир роти", "Начальник ГОІ"]),
            ("Підсумкова доповідь за добу, аналіз втрат і витрат", 2, [
                "Командир роти", "Сержант із МЗ", "Старший бойовий медик"]),
            ("Постановка задач на наступну добу", 1, ["Командир роти"]),
        ]
    },
]


# ---------- Будуємо XML ----------
NS = 'http://schemas.microsoft.com/project'
START = datetime.datetime(2026, 5, 2, 8, 0, 0)


def fmt_dt(dt): return dt.strftime("%Y-%m-%dT%H:%M:%S")
def dur_pt(hours): return f"PT{int(hours)}H0M0S"


# Resources — actors
res_uid_map = {}
resources_xml = []
ru = 1
for a in actors:
    res_uid_map[a["role"]] = ru
    resources_xml.append((ru, a))
    ru += 1


# Tasks — flat list with outline levels
tasks_data = []  # (uid, id, name, outline_level, outline_number, summary, dur_h, predecessors_uid, assignees)
uid = 1
def new_uid():
    global uid; v = uid; uid += 1; return v


# Корінь
root_uid = new_uid()
tasks_data.append({
    "uid": root_uid, "name": "Цикл управління ротою РРР (24 год)",
    "outline_level": 1, "outline_number": "1", "summary": True,
    "dur_h": 0, "preds": [], "assignees": []
})

phase_uids = []
prev_phase_uid = None
phase_idx = 0
for ph in phases:
    phase_idx += 1
    ph_uid = new_uid()
    tasks_data.append({
        "uid": ph_uid, "name": ph["name"],
        "outline_level": 2, "outline_number": f"1.{phase_idx}", "summary": True,
        "dur_h": 0, "preds": [prev_phase_uid] if prev_phase_uid else [], "assignees": []
    })
    phase_uids.append(ph_uid)
    sub_idx = 0
    prev_sub_uid = None
    for (tname, dur_h, assignees) in ph["tasks"]:
        sub_idx += 1
        t_uid = new_uid()
        tasks_data.append({
            "uid": t_uid, "name": tname,
            "outline_level": 3, "outline_number": f"1.{phase_idx}.{sub_idx}",
            "summary": False, "dur_h": dur_h,
            "preds": [prev_sub_uid] if prev_sub_uid else [],
            "assignees": assignees
        })
        prev_sub_uid = t_uid
    prev_phase_uid = ph_uid


# Призначаємо ID послідовно
for i, t in enumerate(tasks_data, start=1):
    t["id"] = i


# Розрахунок дат: послідовний таймлайн із залежностями FS
# Для summary — починається з мін(start дочірніх) до макс(finish дочірніх)
def compute_dates():
    # Спочатку — listy завдання (level 3)
    cur = START
    for t in tasks_data:
        if t["outline_level"] == 3:
            t["start"] = cur
            t["finish"] = cur + datetime.timedelta(hours=t["dur_h"])
            cur = t["finish"]
    # Phase summary — від першого до останнього sub
    for ph_uid in phase_uids:
        children = [t for t in tasks_data if t["outline_level"] == 3 and
                    any(p == ph_uid for p in [])]
    # Простіше: проходимо tasks_data по групах
    # Розрахуємо phase start/finish
    # Знайдемо для кожного phase його під-задачі
    # Спочатку — phase summary (level 2)
    for i, t in enumerate(tasks_data):
        if t["outline_level"] == 2:
            children = []
            for j in range(i+1, len(tasks_data)):
                if tasks_data[j]["outline_level"] <= 2:
                    break
                if tasks_data[j]["outline_level"] == 3:
                    children.append(tasks_data[j])
            if children:
                t["start"] = children[0]["start"]
                t["finish"] = children[-1]["finish"]
                t["dur_h"] = sum(c["dur_h"] for c in children)
            else:
                t["start"] = START
                t["finish"] = START
    # Потім — root (level 1)
    for t in tasks_data:
        if t["outline_level"] == 1:
            children = [c for c in tasks_data if c["outline_level"] == 2]
            if children:
                t["start"] = children[0]["start"]
                t["finish"] = children[-1]["finish"]
                t["dur_h"] = sum(c["dur_h"] for c in children)
            else:
                t["start"] = START; t["finish"] = START

compute_dates()


# Assignments
assignments = []
auid = 1
for t in tasks_data:
    if t["outline_level"] == 3:
        for role in t["assignees"]:
            if role in res_uid_map:
                assignments.append({
                    "uid": auid, "task_uid": t["uid"],
                    "resource_uid": res_uid_map[role],
                    "start": t["start"], "finish": t["finish"],
                    "work_h": t["dur_h"]
                })
                auid += 1


# ---------- XML ----------
parts = []
parts.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
parts.append(f'<Project xmlns="{NS}">')
parts.append('  <SaveVersion>14</SaveVersion>')
parts.append('  <Name>Управління ротою РРР - Бойове управління</Name>')
parts.append('  <Title>Управління ротою РРР - Бойове управління (цикл 24 год)</Title>')
parts.append('  <Subject>Блок-схема бойового управління роти</Subject>')
parts.append('  <Author>Згенеровано з БЧС</Author>')
parts.append('  <Manager>Командир роти</Manager>')
parts.append(f'  <Company>{x(data["battalion"])}</Company>')
parts.append(f'  <CreationDate>{fmt_dt(START)}</CreationDate>')
parts.append(f'  <StartDate>{fmt_dt(START)}</StartDate>')
parts.append(f'  <FinishDate>{fmt_dt(tasks_data[0]["finish"])}</FinishDate>')
parts.append('  <ScheduleFromStart>1</ScheduleFromStart>')
parts.append('  <CalendarUID>1</CalendarUID>')
parts.append('  <DefaultStartTime>08:00:00</DefaultStartTime>')
parts.append('  <DefaultFinishTime>17:00:00</DefaultFinishTime>')
parts.append('  <MinutesPerDay>1440</MinutesPerDay>')
parts.append('  <MinutesPerWeek>10080</MinutesPerWeek>')
parts.append('  <DaysPerMonth>30</DaysPerMonth>')
parts.append('  <DurationFormat>7</DurationFormat>')
parts.append('  <WorkFormat>2</WorkFormat>')
parts.append('  <CurrencyDigits>2</CurrencyDigits>')
parts.append('  <CurrencySymbol>грн</CurrencySymbol>')
parts.append('  <CurrencySymbolPosition>3</CurrencySymbolPosition>')
parts.append('  <DefaultTaskType>0</DefaultTaskType>')
parts.append('  <DefaultFixedCostAccrual>3</DefaultFixedCostAccrual>')
parts.append('  <DefaultStandardRate>0</DefaultStandardRate>')
parts.append('  <DefaultOvertimeRate>0</DefaultOvertimeRate>')
parts.append('  <HonorConstraints>1</HonorConstraints>')
parts.append('  <NewTasksEffortDriven>0</NewTasksEffortDriven>')
parts.append('  <SplitsInProgressTasks>1</SplitsInProgressTasks>')
parts.append('  <TaskUpdatesResource>1</TaskUpdatesResource>')
parts.append('  <FiscalYearStart>0</FiscalYearStart>')
parts.append('  <WeekStartDay>1</WeekStartDay>')
parts.append('  <ExtendedCreationDate>2026-05-02T00:00:00</ExtendedCreationDate>')
parts.append('  <NewTaskStartDate>0</NewTaskStartDate>')
parts.append('  <ProjectExternallyEdited>0</ProjectExternallyEdited>')
parts.append('  <ActualsInSync>0</ActualsInSync>')
parts.append('  <RemoveFileProperties>0</RemoveFileProperties>')
parts.append('  <AdminProject>0</AdminProject>')

# Calendar — 24/7 (бойові дії)
parts.append('  <Calendars>')
parts.append('    <Calendar>')
parts.append('      <UID>1</UID>')
parts.append('      <Name>Бойовий цикл 24/7</Name>')
parts.append('      <IsBaseCalendar>1</IsBaseCalendar>')
parts.append('      <BaseCalendarUID>-1</BaseCalendarUID>')
parts.append('      <WeekDays>')
for dow in range(1, 8):
    parts.append('        <WeekDay>')
    parts.append(f'          <DayType>{dow}</DayType>')
    parts.append('          <DayWorking>1</DayWorking>')
    parts.append('          <WorkingTimes>')
    parts.append('            <WorkingTime><FromTime>00:00:00</FromTime><ToTime>23:59:00</ToTime></WorkingTime>')
    parts.append('          </WorkingTimes>')
    parts.append('        </WeekDay>')
parts.append('      </WeekDays>')
parts.append('    </Calendar>')
parts.append('  </Calendars>')

# Tasks
parts.append('  <Tasks>')
for t in tasks_data:
    parts.append('    <Task>')
    parts.append(f'      <UID>{t["uid"]}</UID>')
    parts.append(f'      <ID>{t["id"]}</ID>')
    parts.append(f'      <Name>{x(t["name"])}</Name>')
    parts.append('      <Type>1</Type>')
    parts.append('      <IsNull>0</IsNull>')
    parts.append('      <CreateDate>2026-05-02T08:00:00</CreateDate>')
    parts.append(f'      <WBS>{x(t["outline_number"])}</WBS>')
    parts.append(f'      <OutlineNumber>{x(t["outline_number"])}</OutlineNumber>')
    parts.append(f'      <OutlineLevel>{t["outline_level"]}</OutlineLevel>')
    parts.append('      <Priority>500</Priority>')
    parts.append(f'      <Start>{fmt_dt(t["start"])}</Start>')
    parts.append(f'      <Finish>{fmt_dt(t["finish"])}</Finish>')
    parts.append(f'      <Duration>{dur_pt(t["dur_h"])}</Duration>')
    parts.append('      <DurationFormat>7</DurationFormat>')
    parts.append(f'      <Work>{dur_pt(t["dur_h"])}</Work>')
    parts.append(f'      <Summary>{1 if t["summary"] else 0}</Summary>')
    parts.append('      <Critical>1</Critical>')
    parts.append('      <FixedCostAccrual>3</FixedCostAccrual>')
    parts.append('      <ConstraintType>0</ConstraintType>')
    parts.append('      <CalendarUID>-1</CalendarUID>')
    parts.append('      <ConstraintDate>2026-05-02T08:00:00</ConstraintDate>')
    parts.append('      <LevelAssignments>1</LevelAssignments>')
    parts.append('      <LevelingCanSplit>1</LevelingCanSplit>')
    parts.append('      <Manual>0</Manual>')
    parts.append('      <EarnedValueMethod>0</EarnedValueMethod>')
    parts.append('      <IgnoreResourceCalendar>0</IgnoreResourceCalendar>')
    parts.append('      <Active>1</Active>')
    # Predecessor links
    for pred_uid in t["preds"]:
        parts.append('      <PredecessorLink>')
        parts.append(f'        <PredecessorUID>{pred_uid}</PredecessorUID>')
        parts.append('        <Type>1</Type>')
        parts.append('        <CrossProject>0</CrossProject>')
        parts.append('        <LinkLag>0</LinkLag>')
        parts.append('        <LagFormat>7</LagFormat>')
        parts.append('      </PredecessorLink>')
    if t.get("assignees"):
        notes = "Виконавці: " + ", ".join(t["assignees"])
        parts.append(f'      <Notes>{x(notes)}</Notes>')
    parts.append('    </Task>')
parts.append('  </Tasks>')

# Resources
parts.append('  <Resources>')
for ru, a in resources_xml:
    parts.append('    <Resource>')
    parts.append(f'      <UID>{ru}</UID>')
    parts.append(f'      <ID>{ru}</ID>')
    full_name = a["name"]
    if a["rank"]:
        full_name = f'{a["rank"]} {a["name"]}'
    parts.append(f'      <Name>{x(full_name)}</Name>')
    parts.append(f'      <Initials>{x(a["role"][:8])}</Initials>')
    parts.append('      <Type>1</Type>')
    parts.append('      <IsNull>0</IsNull>')
    parts.append('      <ElementaryType>0</ElementaryType>')
    parts.append(f'      <Group>{x(a["role"])}</Group>')
    parts.append(f'      <Code>{x(a["position"])}</Code>')
    parts.append('      <MaxUnits>1</MaxUnits>')
    parts.append('      <PeakUnits>1</PeakUnits>')
    parts.append('      <OverAllocated>0</OverAllocated>')
    parts.append('      <CanLevel>1</CanLevel>')
    parts.append('      <AccrueAt>3</AccrueAt>')
    parts.append('      <CalendarUID>-1</CalendarUID>')
    parts.append('      <StandardRate>0</StandardRate>')
    parts.append('      <StandardRateFormat>2</StandardRateFormat>')
    parts.append('      <Cost>0</Cost>')
    parts.append('      <OvertimeRate>0</OvertimeRate>')
    parts.append('      <OvertimeRateFormat>2</OvertimeRateFormat>')
    parts.append('      <CostPerUse>0</CostPerUse>')
    parts.append('      <Active>1</Active>')
    parts.append('    </Resource>')
parts.append('  </Resources>')

# Assignments
parts.append('  <Assignments>')
for a in assignments:
    parts.append('    <Assignment>')
    parts.append(f'      <UID>{a["uid"]}</UID>')
    parts.append(f'      <TaskUID>{a["task_uid"]}</TaskUID>')
    parts.append(f'      <ResourceUID>{a["resource_uid"]}</ResourceUID>')
    parts.append('      <Units>1.0</Units>')
    parts.append(f'      <Work>{dur_pt(a["work_h"])}</Work>')
    parts.append(f'      <RegularWork>{dur_pt(a["work_h"])}</RegularWork>')
    parts.append('      <ActualWork>PT0H0M0S</ActualWork>')
    parts.append(f'      <RemainingWork>{dur_pt(a["work_h"])}</RemainingWork>')
    parts.append('      <OvertimeWork>PT0H0M0S</OvertimeWork>')
    parts.append('      <ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>')
    parts.append('      <RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>')
    parts.append(f'      <Start>{fmt_dt(a["start"])}</Start>')
    parts.append(f'      <Finish>{fmt_dt(a["finish"])}</Finish>')
    parts.append('      <DelayFormat>7</DelayFormat>')
    parts.append('      <Cost>0</Cost>')
    parts.append('      <RemainingCost>0</RemainingCost>')
    parts.append('      <ActualCost>0</ActualCost>')
    parts.append('      <ActualOvertimeCost>0</ActualOvertimeCost>')
    parts.append('      <RemainingOvertimeCost>0</RemainingOvertimeCost>')
    parts.append('      <PercentWorkComplete>0</PercentWorkComplete>')
    parts.append('      <CostRateTable>0</CostRateTable>')
    parts.append('      <ResumeType>0</ResumeType>')
    parts.append('    </Assignment>')
parts.append('  </Assignments>')

parts.append('</Project>')

xml = "\n".join(parts)
out = '/app/output/Управління ротою РРР - Бойове управління.xml'
with open(out, 'w', encoding='utf-8') as f:
    f.write(xml)

print(f"OK: {out}")
print(f"  завдань: {len(tasks_data)}, ресурсів: {len(resources_xml)}, призначень: {len(assignments)}")
print(f"  тривалість циклу: {tasks_data[0]['dur_h']} год")
