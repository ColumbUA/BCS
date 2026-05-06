"""Генератор MS Project XML для організаційної структури роти РРР (WBS).

Створює файл, який імпортується в MS Project (File → Open → .xml) та містить:
  - Завдання-WBS: Рота → Підрозділи → Відділення → Посади
  - Ресурси: особовий склад (ПІБ, позивний, звання)
  - Призначення: кожна посада → відповідна особа
"""
import json, datetime, html
from xml.sax.saxutils import escape

with open('/app/output/structure.json', encoding='utf-8') as f:
    data = json.load(f)

NS = 'http://schemas.microsoft.com/project'
TODAY = datetime.date(2026, 5, 2)
START = datetime.datetime.combine(TODAY, datetime.time(8, 0))


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def x(s):
    return escape(s if s else "")


# ----------------------- Збираємо завдання та ресурси ----------------------
tasks = []      # list of dict: uid, id, name, outline_level, outline_number, summary, wbs, position_meta
resources = []  # list of dict: uid, id, name, initials, group, code
assignments = []

uid_counter = [1]
def next_uid():
    u = uid_counter[0]; uid_counter[0] += 1; return u

# UID 0 = project summary (зарезервовано MS Project)
PROJECT_SUMMARY_UID = 0

# Корінь — Рота
root_uid = next_uid()
tasks.append({
    "uid": root_uid, "name": data["name"], "outline_level": 1,
    "outline_number": "1", "wbs": "1", "summary": True,
    "notes": f"Батальйон: {data['battalion']}\nВсього за БЧС: {data['total_personnel']} осіб"
})

sub_idx = 0
for sub_key in data["order"]:
    sub = data["subunits"][sub_key]
    sub_idx += 1
    sub_outline_num = f"1.{sub_idx}"
    sub_uid = next_uid()
    tasks.append({
        "uid": sub_uid, "name": sub["name"], "outline_level": 2,
        "outline_number": sub_outline_num, "wbs": sub_outline_num, "summary": True,
        "notes": f"Тип: {sub['type']}; за БЧС: {sub['count']} осіб"
    })

    # Squads
    sq_idx = 0
    sq_keys = list(sub["squads"].keys())
    # Якщо у підрозділі є тільки __DIRECT__ — посади йдуть напряму (без рівня відділення)
    has_squads = any(k != "__DIRECT__" for k in sq_keys)

    for sq_key in sq_keys:
        sq = sub["squads"][sq_key]
        if sq_key == "__DIRECT__":
            # Посади напряму під підрозділом
            for pos in sq["positions"]:
                pos_uid = next_uid()
                pos_name = pos["position"]
                if pos["rank_state"]:
                    pos_name += f" ({pos['rank_state']})"
                tasks.append({
                    "uid": pos_uid, "name": pos_name, "outline_level": 3,
                    "outline_number": f"{sub_outline_num}.{len([t for t in tasks if t['outline_level']==3 and t['outline_number'].startswith(sub_outline_num+'.')])+1}",
                    "wbs": "", "summary": False, "position_meta": pos
                })
        else:
            sq_idx += 1
            sq_outline = f"{sub_outline_num}.{sq_idx}"
            sq_uid = next_uid()
            tasks.append({
                "uid": sq_uid, "name": sq["name"], "outline_level": 3,
                "outline_number": sq_outline, "wbs": sq_outline, "summary": True,
                "notes": f"Особовий склад: {len(sq['positions'])} осіб"
            })
            pi = 0
            for pos in sq["positions"]:
                pi += 1
                pos_uid = next_uid()
                pos_name = pos["position"]
                if pos["rank_state"]:
                    pos_name += f" ({pos['rank_state']})"
                tasks.append({
                    "uid": pos_uid, "name": pos_name, "outline_level": 4,
                    "outline_number": f"{sq_outline}.{pi}", "wbs": "",
                    "summary": False, "position_meta": pos
                })

# --- Ресурси: усі особи з ПІБ ---
people = {}  # fio -> resource info
for sub in data["subunits"].values():
    for sq in sub["squads"].values():
        for p in sq["positions"]:
            if p["fio"]:
                key = p["fio"]
                if key not in people:
                    people[key] = {
                        "fio": p["fio"],
                        "callsign": p["callsign"],
                        "rank": p["rank_actual"] or p["rank_state"],
                        "position": p["position"]
                    }

res_uid_map = {}  # fio -> uid
for fio, info in people.items():
    ru = next_uid()
    res_uid_map[fio] = ru
    name = fio
    if info["callsign"]:
        name = f'{fio} «{info["callsign"]}»'
    initials = info["callsign"][:5] if info["callsign"] else (fio.split()[0][:5] if fio else "")
    resources.append({
        "uid": ru, "name": name, "initials": initials,
        "group": info["rank"] or "", "code": info["position"]
    })

# --- Призначення: посада-таска → ресурс (якщо є ПІБ) ---
assn_uid = 1
for t in tasks:
    pm = t.get("position_meta")
    if pm and pm["fio"] and pm["fio"] in res_uid_map:
        assignments.append({
            "uid": assn_uid, "task_uid": t["uid"],
            "resource_uid": res_uid_map[pm["fio"]],
            "units": 1.0
        })
        assn_uid += 1

# Прорахунок ID (порядкові номери для відображення в Gantt) і Start/Finish/Duration
# Для кожного завдання-посади тривалість = 1 день (умовно — періодичний цикл управління)
# Сумарні (summary) завдання виводять зведено.
# Усі завдання починаються з START, тривалість 1 робочий день.
TASK_DUR = "PT8H0M0S"   # 8 годин = 1 робочий день
TASK_DUR_SUMMARY = "PT8H0M0S"

# ID послідовний за UID-порядком (як вони додані)
for i, t in enumerate(tasks, start=1):
    t["id"] = i


# ----------------------- Формуємо XML --------------------------------------
parts = []
parts.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
parts.append(f'<Project xmlns="{NS}">')
parts.append('  <SaveVersion>14</SaveVersion>')
parts.append(f'  <Name>Управління ротою РРР - Організаційна структура (БЧС)</Name>')
parts.append(f'  <Title>Управління ротою РРР - Організаційна структура (БЧС {TODAY.strftime("%d.%m.%Y")})</Title>')
parts.append(f'  <Subject>Блок-схема управління ротою радіо та радіотехнічної розвідки</Subject>')
parts.append(f'  <Author>Згенеровано з БЧС</Author>')
parts.append(f'  <Manager>Командир роти</Manager>')
parts.append(f'  <Company>{x(data["battalion"])}</Company>')
parts.append(f'  <CreationDate>{fmt_dt(START)}</CreationDate>')
parts.append(f'  <StartDate>{fmt_dt(START)}</StartDate>')
parts.append(f'  <FinishDate>{fmt_dt(START + datetime.timedelta(days=30))}</FinishDate>')
parts.append('  <ScheduleFromStart>1</ScheduleFromStart>')
parts.append('  <FYStartDate>1</FYStartDate>')
parts.append('  <CriticalSlackLimit>0</CriticalSlackLimit>')
parts.append('  <CurrencyDigits>2</CurrencyDigits>')
parts.append('  <CurrencySymbol>грн</CurrencySymbol>')
parts.append('  <CurrencySymbolPosition>3</CurrencySymbolPosition>')
parts.append('  <CalendarUID>1</CalendarUID>')
parts.append('  <DefaultStartTime>08:00:00</DefaultStartTime>')
parts.append('  <DefaultFinishTime>17:00:00</DefaultFinishTime>')
parts.append('  <MinutesPerDay>480</MinutesPerDay>')
parts.append('  <MinutesPerWeek>2400</MinutesPerWeek>')
parts.append('  <DaysPerMonth>20</DaysPerMonth>')
parts.append('  <DefaultTaskType>0</DefaultTaskType>')
parts.append('  <DefaultFixedCostAccrual>3</DefaultFixedCostAccrual>')
parts.append('  <DefaultStandardRate>0</DefaultStandardRate>')
parts.append('  <DefaultOvertimeRate>0</DefaultOvertimeRate>')
parts.append('  <DurationFormat>7</DurationFormat>')
parts.append('  <WorkFormat>2</WorkFormat>')
parts.append('  <EditableActualCosts>0</EditableActualCosts>')
parts.append('  <HonorConstraints>1</HonorConstraints>')
parts.append('  <InsertedProjectsLikeSummary>1</InsertedProjectsLikeSummary>')
parts.append('  <MultipleCriticalPaths>0</MultipleCriticalPaths>')
parts.append('  <NewTasksEffortDriven>0</NewTasksEffortDriven>')
parts.append('  <NewTasksEstimated>0</NewTasksEstimated>')
parts.append('  <SplitsInProgressTasks>1</SplitsInProgressTasks>')
parts.append('  <SpreadActualCost>0</SpreadActualCost>')
parts.append('  <SpreadPercentComplete>0</SpreadPercentComplete>')
parts.append('  <TaskUpdatesResource>1</TaskUpdatesResource>')
parts.append('  <FiscalYearStart>0</FiscalYearStart>')
parts.append('  <WeekStartDay>1</WeekStartDay>')
parts.append('  <NewTaskStartDate>0</NewTaskStartDate>')
parts.append('  <DefaultTaskEVMethod>0</DefaultTaskEVMethod>')
parts.append('  <ProjectExternallyEdited>0</ProjectExternallyEdited>')
parts.append('  <ExtendedCreationDate>2026-05-02T00:00:00</ExtendedCreationDate>')
parts.append('  <ActualsInSync>0</ActualsInSync>')
parts.append('  <RemoveFileProperties>0</RemoveFileProperties>')
parts.append('  <AdminProject>0</AdminProject>')

# --- Calendars ---
parts.append('  <Calendars>')
parts.append('    <Calendar>')
parts.append('      <UID>1</UID>')
parts.append('      <Name>Стандартний</Name>')
parts.append('      <IsBaseCalendar>1</IsBaseCalendar>')
parts.append('      <BaseCalendarUID>-1</BaseCalendarUID>')
parts.append('      <WeekDays>')
for dow in range(1, 8):
    working = "0" if dow in (1, 7) else "1"   # Sun=1, Sat=7 — вихідні
    parts.append('        <WeekDay>')
    parts.append(f'          <DayType>{dow}</DayType>')
    parts.append(f'          <DayWorking>{working}</DayWorking>')
    if working == "1":
        parts.append('          <WorkingTimes>')
        parts.append('            <WorkingTime><FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime></WorkingTime>')
        parts.append('            <WorkingTime><FromTime>13:00:00</FromTime><ToTime>17:00:00</ToTime></WorkingTime>')
        parts.append('          </WorkingTimes>')
    parts.append('        </WeekDay>')
parts.append('      </WeekDays>')
parts.append('    </Calendar>')
parts.append('  </Calendars>')

# --- Tasks ---
parts.append('  <Tasks>')
for t in tasks:
    parts.append('    <Task>')
    parts.append(f'      <UID>{t["uid"]}</UID>')
    parts.append(f'      <ID>{t["id"]}</ID>')
    parts.append(f'      <Name>{x(t["name"])}</Name>')
    parts.append('      <Type>1</Type>')
    parts.append('      <IsNull>0</IsNull>')
    parts.append('      <CreateDate>2026-05-02T08:00:00</CreateDate>')
    parts.append(f'      <WBS>{x(t.get("wbs",""))}</WBS>')
    parts.append(f'      <OutlineNumber>{x(t["outline_number"])}</OutlineNumber>')
    parts.append(f'      <OutlineLevel>{t["outline_level"]}</OutlineLevel>')
    parts.append('      <Priority>500</Priority>')
    parts.append(f'      <Start>{fmt_dt(START)}</Start>')
    parts.append(f'      <Finish>{fmt_dt(START + datetime.timedelta(hours=8))}</Finish>')
    parts.append(f'      <Duration>{TASK_DUR}</Duration>')
    parts.append('      <DurationFormat>7</DurationFormat>')
    parts.append('      <Work>PT8H0M0S</Work>')
    parts.append(f'      <Summary>{1 if t.get("summary") else 0}</Summary>')
    parts.append('      <Critical>0</Critical>')
    parts.append('      <FixedCostAccrual>3</FixedCostAccrual>')
    parts.append('      <ConstraintType>4</ConstraintType>')
    parts.append('      <CalendarUID>-1</CalendarUID>')
    parts.append(f'      <ConstraintDate>{fmt_dt(START)}</ConstraintDate>')
    parts.append('      <LevelAssignments>1</LevelAssignments>')
    parts.append('      <LevelingCanSplit>1</LevelingCanSplit>')
    parts.append('      <Manual>0</Manual>')
    parts.append('      <EarnedValueMethod>0</EarnedValueMethod>')
    parts.append('      <IgnoreResourceCalendar>0</IgnoreResourceCalendar>')
    parts.append('      <Active>1</Active>')

    # Notes для посад: ПІБ, позивний, звання, дислокація, стан
    notes = t.get("notes", "")
    pm = t.get("position_meta")
    if pm:
        bits = []
        if pm["fio"]: bits.append(f"ПІБ: {pm['fio']}")
        if pm["callsign"]: bits.append(f"Позивний: {pm['callsign']}")
        if pm["rank_actual"]: bits.append(f"Звання факт.: {pm['rank_actual']}")
        if pm["rank_state"]: bits.append(f"Звання за штатом: {pm['rank_state']}")
        if pm["location"]: bits.append(f"Дислокація: {pm['location']}")
        if pm["status"]: bits.append(f"Стан: {pm['status']}")
        notes = "\n".join(bits) if bits else ""
    if notes:
        parts.append(f'      <Notes>{x(notes)}</Notes>')
    parts.append('    </Task>')
parts.append('  </Tasks>')

# --- Resources ---
parts.append('  <Resources>')
# Resource UID 0 — пустий ресурс (resort to default)
for r in resources:
    parts.append('    <Resource>')
    parts.append(f'      <UID>{r["uid"]}</UID>')
    parts.append(f'      <ID>{r["uid"]}</ID>')
    parts.append(f'      <Name>{x(r["name"])}</Name>')
    parts.append(f'      <Initials>{x(r["initials"])}</Initials>')
    parts.append('      <Type>1</Type>')
    parts.append('      <IsNull>0</IsNull>')
    parts.append('      <ElementaryType>0</ElementaryType>')
    parts.append(f'      <Group>{x(r["group"])}</Group>')
    parts.append(f'      <Code>{x(r["code"])}</Code>')
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
    parts.append('      <CostVariance>0</CostVariance>')
    parts.append('      <Work>PT0H0M0S</Work>')
    parts.append('      <RegularWork>PT0H0M0S</RegularWork>')
    parts.append('      <OvertimeWork>PT0H0M0S</OvertimeWork>')
    parts.append('      <ActualWork>PT0H0M0S</ActualWork>')
    parts.append('      <RemainingWork>PT0H0M0S</RemainingWork>')
    parts.append('      <ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>')
    parts.append('      <RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>')
    parts.append('      <PercentWorkComplete>0</PercentWorkComplete>')
    parts.append('      <ActualCost>0</ActualCost>')
    parts.append('      <ActualOvertimeCost>0</ActualOvertimeCost>')
    parts.append('      <RemainingCost>0</RemainingCost>')
    parts.append('      <RemainingOvertimeCost>0</RemainingOvertimeCost>')
    parts.append('      <WorkVariance>0</WorkVariance>')
    parts.append('      <StartVariance>0</StartVariance>')
    parts.append('      <FinishVariance>0</FinishVariance>')
    parts.append('      <Active>1</Active>')
    parts.append('    </Resource>')
parts.append('  </Resources>')

# --- Assignments ---
parts.append('  <Assignments>')
for a in assignments:
    parts.append('    <Assignment>')
    parts.append(f'      <UID>{a["uid"]}</UID>')
    parts.append(f'      <TaskUID>{a["task_uid"]}</TaskUID>')
    parts.append(f'      <ResourceUID>{a["resource_uid"]}</ResourceUID>')
    parts.append(f'      <Units>{a["units"]}</Units>')
    parts.append('      <Work>PT8H0M0S</Work>')
    parts.append('      <RegularWork>PT8H0M0S</RegularWork>')
    parts.append('      <ActualWork>PT0H0M0S</ActualWork>')
    parts.append('      <RemainingWork>PT8H0M0S</RemainingWork>')
    parts.append('      <OvertimeWork>PT0H0M0S</OvertimeWork>')
    parts.append('      <ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>')
    parts.append('      <RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>')
    parts.append(f'      <Start>{fmt_dt(START)}</Start>')
    parts.append(f'      <Finish>{fmt_dt(START + datetime.timedelta(hours=8))}</Finish>')
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
out = '/app/output/Управління ротою РРР - Організаційна структура.xml'
with open(out, 'w', encoding='utf-8') as f:
    f.write(xml)

print(f"OK: {out}")
print(f"  завдань: {len(tasks)}, ресурсів: {len(resources)}, призначень: {len(assignments)}")
