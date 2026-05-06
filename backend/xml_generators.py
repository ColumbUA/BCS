"""Генератори MS Project XML.

Експортуються три функції:
  - generate_org_structure_xml(company, equipment_list)
  - generate_command_cycle_xml(company)
  - generate_interaction_matrix_xml(company, interactions)
"""
import datetime
from xml.sax.saxutils import escape

NS = 'http://schemas.microsoft.com/project'
START = datetime.datetime(2026, 5, 2, 8, 0, 0)


def _x(s):
    return escape(s if s else "")


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _dur(hours):
    return f"PT{int(hours)}H0M0S"


def _calendar_24x7(uid=1, name="24/7"):
    parts = []
    parts.append('  <Calendars>')
    parts.append('    <Calendar>')
    parts.append(f'      <UID>{uid}</UID>')
    parts.append(f'      <Name>{_x(name)}</Name>')
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
    return parts


def _project_header(name, title, manager="Командир роти", finish_dt=None):
    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    parts.append(f'<Project xmlns="{NS}">')
    parts.append('  <SaveVersion>14</SaveVersion>')
    parts.append(f'  <Name>{_x(name)}</Name>')
    parts.append(f'  <Title>{_x(title)}</Title>')
    parts.append('  <Author>Згенеровано з БЧС</Author>')
    parts.append(f'  <Manager>{_x(manager)}</Manager>')
    parts.append('  <Company>Розвідувальний батальйон</Company>')
    parts.append(f'  <CreationDate>{_fmt_dt(START)}</CreationDate>')
    parts.append(f'  <StartDate>{_fmt_dt(START)}</StartDate>')
    parts.append(f'  <FinishDate>{_fmt_dt(finish_dt or (START + datetime.timedelta(days=30)))}</FinishDate>')
    parts.append('  <ScheduleFromStart>1</ScheduleFromStart>')
    parts.append('  <CalendarUID>1</CalendarUID>')
    parts.append('  <DefaultStartTime>08:00:00</DefaultStartTime>')
    parts.append('  <DefaultFinishTime>17:00:00</DefaultFinishTime>')
    parts.append('  <MinutesPerDay>1440</MinutesPerDay>')
    parts.append('  <MinutesPerWeek>10080</MinutesPerWeek>')
    parts.append('  <DaysPerMonth>30</DaysPerMonth>')
    parts.append('  <CurrencyDigits>2</CurrencyDigits>')
    parts.append('  <CurrencySymbol>грн</CurrencySymbol>')
    parts.append('  <CurrencySymbolPosition>3</CurrencySymbolPosition>')
    parts.append('  <DurationFormat>7</DurationFormat>')
    parts.append('  <WorkFormat>2</WorkFormat>')
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
    return parts


def _task(uid, tid, name, level, outline, summary, dur_h, preds=None, notes="", critical=0):
    p = []
    p.append('    <Task>')
    p.append(f'      <UID>{uid}</UID>')
    p.append(f'      <ID>{tid}</ID>')
    p.append(f'      <Name>{_x(name)}</Name>')
    p.append('      <Type>1</Type>')
    p.append('      <IsNull>0</IsNull>')
    p.append('      <CreateDate>2026-05-02T08:00:00</CreateDate>')
    p.append(f'      <WBS>{_x(outline)}</WBS>')
    p.append(f'      <OutlineNumber>{_x(outline)}</OutlineNumber>')
    p.append(f'      <OutlineLevel>{level}</OutlineLevel>')
    p.append('      <Priority>500</Priority>')
    p.append(f'      <Start>{_fmt_dt(START)}</Start>')
    p.append(f'      <Finish>{_fmt_dt(START + datetime.timedelta(hours=max(dur_h,1)))}</Finish>')
    p.append(f'      <Duration>{_dur(max(dur_h,1))}</Duration>')
    p.append('      <DurationFormat>7</DurationFormat>')
    p.append(f'      <Work>{_dur(max(dur_h,1))}</Work>')
    p.append(f'      <Summary>{1 if summary else 0}</Summary>')
    p.append(f'      <Critical>{critical}</Critical>')
    p.append('      <FixedCostAccrual>3</FixedCostAccrual>')
    p.append('      <ConstraintType>4</ConstraintType>')
    p.append('      <CalendarUID>-1</CalendarUID>')
    p.append(f'      <ConstraintDate>{_fmt_dt(START)}</ConstraintDate>')
    p.append('      <LevelAssignments>1</LevelAssignments>')
    p.append('      <LevelingCanSplit>1</LevelingCanSplit>')
    p.append('      <Manual>0</Manual>')
    p.append('      <EarnedValueMethod>0</EarnedValueMethod>')
    p.append('      <IgnoreResourceCalendar>0</IgnoreResourceCalendar>')
    p.append('      <Active>1</Active>')
    if preds:
        for pu in preds:
            p.append('      <PredecessorLink>')
            p.append(f'        <PredecessorUID>{pu}</PredecessorUID>')
            p.append('        <Type>1</Type>')
            p.append('        <CrossProject>0</CrossProject>')
            p.append('        <LinkLag>0</LinkLag>')
            p.append('        <LagFormat>7</LagFormat>')
            p.append('      </PredecessorLink>')
    if notes:
        p.append(f'      <Notes>{_x(notes)}</Notes>')
    p.append('    </Task>')
    return p


def _resource(uid, name, initials="", group="", code="", res_type=1):
    """res_type: 1=Work (особа), 0=Material (засіб)"""
    p = []
    p.append('    <Resource>')
    p.append(f'      <UID>{uid}</UID>')
    p.append(f'      <ID>{uid}</ID>')
    p.append(f'      <Name>{_x(name)}</Name>')
    p.append(f'      <Initials>{_x(initials)}</Initials>')
    p.append(f'      <Type>{res_type}</Type>')
    p.append('      <IsNull>0</IsNull>')
    p.append('      <ElementaryType>0</ElementaryType>')
    p.append(f'      <Group>{_x(group)}</Group>')
    p.append(f'      <Code>{_x(code)}</Code>')
    if res_type == 0:  # Material
        p.append('      <MaterialLabel>од.</MaterialLabel>')
    else:
        p.append('      <MaxUnits>1</MaxUnits>')
    p.append('      <PeakUnits>1</PeakUnits>')
    p.append('      <OverAllocated>0</OverAllocated>')
    p.append('      <CanLevel>1</CanLevel>')
    p.append('      <AccrueAt>3</AccrueAt>')
    p.append('      <CalendarUID>-1</CalendarUID>')
    p.append('      <StandardRate>0</StandardRate>')
    p.append('      <StandardRateFormat>2</StandardRateFormat>')
    p.append('      <Cost>0</Cost>')
    p.append('      <OvertimeRate>0</OvertimeRate>')
    p.append('      <OvertimeRateFormat>2</OvertimeRateFormat>')
    p.append('      <CostPerUse>0</CostPerUse>')
    p.append('      <Active>1</Active>')
    p.append('    </Resource>')
    return p


def _assignment(uid, task_uid, res_uid, units=1.0, work_h=8):
    p = []
    p.append('    <Assignment>')
    p.append(f'      <UID>{uid}</UID>')
    p.append(f'      <TaskUID>{task_uid}</TaskUID>')
    p.append(f'      <ResourceUID>{res_uid}</ResourceUID>')
    p.append(f'      <Units>{units}</Units>')
    p.append(f'      <Work>{_dur(work_h)}</Work>')
    p.append(f'      <RegularWork>{_dur(work_h)}</RegularWork>')
    p.append('      <ActualWork>PT0H0M0S</ActualWork>')
    p.append(f'      <RemainingWork>{_dur(work_h)}</RemainingWork>')
    p.append('      <OvertimeWork>PT0H0M0S</OvertimeWork>')
    p.append('      <ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>')
    p.append('      <RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>')
    p.append(f'      <Start>{_fmt_dt(START)}</Start>')
    p.append(f'      <Finish>{_fmt_dt(START + datetime.timedelta(hours=work_h))}</Finish>')
    p.append('      <DelayFormat>7</DelayFormat>')
    p.append('      <Cost>0</Cost>')
    p.append('      <RemainingCost>0</RemainingCost>')
    p.append('      <ActualCost>0</ActualCost>')
    p.append('      <ActualOvertimeCost>0</ActualOvertimeCost>')
    p.append('      <RemainingOvertimeCost>0</RemainingOvertimeCost>')
    p.append('      <PercentWorkComplete>0</PercentWorkComplete>')
    p.append('      <CostRateTable>0</CostRateTable>')
    p.append('      <ResumeType>0</ResumeType>')
    p.append('    </Assignment>')
    return p


# ============================== ORG STRUCTURE ==============================

def generate_org_structure_xml(company, equipment_list):
    """Генерує MS Project XML для оргструктури роти + засобів (штатні+позаштатні).

    Tasks: hierarchy unit→squad→position
    Resources:
      - особовий склад (Work)
      - засоби: штатні (Material, Group="штатний")
      - засоби: позаштатні (Material, Group="позаштатний")
    Assignments: position-task → person, та засіб → відповідний підрозділ-task.
    """
    HQ_KEY = "__HQ__"
    tasks = []
    resources = []
    assignments = []
    uid_seq = [1]

    def nu():
        v = uid_seq[0]; uid_seq[0] += 1; return v

    # path -> task_uid (для прив'язки засобів)
    path_to_uid = {}

    # Root
    root_uid = nu()
    tasks.append({"uid": root_uid, "name": company["name"], "level": 1,
                  "outline": "1", "summary": True, "dur_h": 8,
                  "notes": f"Батальйон: {company['battalion']}\nВсього за БЧС: {company['total_personnel']} осіб"})
    path_to_uid[company["name"]] = root_uid

    sub_idx = 0
    for sub_key in company["order"]:
        sub = company["subunits"][sub_key]
        sub_idx += 1
        sub_outline = f"1.{sub_idx}"
        sub_uid = nu()
        tasks.append({"uid": sub_uid, "name": sub["name"], "level": 2,
                      "outline": sub_outline, "summary": True, "dur_h": 8,
                      "notes": f"Тип: {sub['type']}; за БЧС: {sub['count']} осіб"})
        path_to_uid[sub["name"]] = sub_uid

        sq_idx = 0
        sq_keys = list(sub["squads"].keys())
        for sq_key in sq_keys:
            sq = sub["squads"][sq_key]
            if sq_key == "__DIRECT__":
                pi = 0
                for p in sq["positions"]:
                    pi += 1
                    pos_uid = nu()
                    pos_name = p["position"] + (f" ({p['rank_state']})" if p["rank_state"] else "")
                    notes_bits = []
                    if p["fio"]: notes_bits.append(f"ПІБ: {p['fio']}")
                    if p["callsign"]: notes_bits.append(f"Позивний: {p['callsign']}")
                    if p["rank_actual"]: notes_bits.append(f"Звання факт.: {p['rank_actual']}")
                    if p["location"]: notes_bits.append(f"Дислокація: {p['location']}")
                    tasks.append({"uid": pos_uid, "name": pos_name, "level": 3,
                                  "outline": f"{sub_outline}.{pi}", "summary": False,
                                  "dur_h": 8, "notes": "\n".join(notes_bits),
                                  "_position": p})
            else:
                sq_idx += 1
                sq_outline = f"{sub_outline}.{sq_idx}"
                sq_uid = nu()
                tasks.append({"uid": sq_uid, "name": sq["name"], "level": 3,
                              "outline": sq_outline, "summary": True, "dur_h": 8,
                              "notes": f"Особовий склад: {len(sq['positions'])} осіб"})
                path_to_uid[f"{sub['name']}/{sq['name']}"] = sq_uid

                pi = 0
                for p in sq["positions"]:
                    pi += 1
                    pos_uid = nu()
                    pos_name = p["position"] + (f" ({p['rank_state']})" if p["rank_state"] else "")
                    notes_bits = []
                    if p["fio"]: notes_bits.append(f"ПІБ: {p['fio']}")
                    if p["callsign"]: notes_bits.append(f"Позивний: {p['callsign']}")
                    if p["rank_actual"]: notes_bits.append(f"Звання факт.: {p['rank_actual']}")
                    if p["location"]: notes_bits.append(f"Дислокація: {p['location']}")
                    tasks.append({"uid": pos_uid, "name": pos_name, "level": 4,
                                  "outline": f"{sq_outline}.{pi}", "summary": False,
                                  "dur_h": 8, "notes": "\n".join(notes_bits),
                                  "_position": p})

    # ID sequential
    for i, t in enumerate(tasks, start=1):
        t["id"] = i

    # Resources: персонал
    res_uid_map = {}
    for sub in company["subunits"].values():
        for sq in sub["squads"].values():
            for p in sq["positions"]:
                if p["fio"] and p["fio"] not in res_uid_map:
                    ru = nu()
                    res_uid_map[p["fio"]] = ru
                    name = p["fio"] + (f' «{p["callsign"]}»' if p["callsign"] else "")
                    resources.append({"uid": ru, "name": name, "type": 1,
                                      "initials": (p["callsign"][:5] if p["callsign"] else p["fio"].split()[0][:5]),
                                      "group": p["rank_actual"] or p["rank_state"],
                                      "code": p["position"]})

    # Resources: засоби (Material) — окремі за категорією+назвою+типом
    eq_res_map = {}  # (cat, name, type) -> uid
    for e in equipment_list:
        key = (e.get("category",""), e.get("name",""), e.get("type","штатний"))
        if key not in eq_res_map:
            ru = nu()
            eq_res_map[key] = ru
            display_name = f'[{e["type"].upper()}] {e["category"]}: {e["name"]}'
            resources.append({"uid": ru, "name": display_name, "type": 0,
                              "initials": e["category"][:5],
                              "group": e["type"],   # штатний/позаштатний
                              "code": e["category"]})

    # Assignments: посади → особи
    auid = 1
    for t in tasks:
        p = t.get("_position")
        if p and p.get("fio") and p["fio"] in res_uid_map:
            assignments.append({"uid": auid, "task_uid": t["uid"],
                                "res_uid": res_uid_map[p["fio"]],
                                "units": 1.0, "work_h": 8})
            auid += 1

    # Assignments: засоби → відповідний task (підрозділ або відділення)
    for e in equipment_list:
        np_path = e.get("node_path", "")
        # Спершу шукаємо точний шлях, потім fallback
        target_uid = None
        if np_path in path_to_uid:
            target_uid = path_to_uid[np_path]
        else:
            # fallback: знайти за першим сегментом
            first = np_path.split("/")[0] if np_path else ""
            target_uid = path_to_uid.get(first)
        if not target_uid:
            target_uid = root_uid
        key = (e.get("category",""), e.get("name",""), e.get("type","штатний"))
        ru = eq_res_map.get(key)
        if ru:
            qty = max(int(e.get("qty", 1)), 1)
            assignments.append({"uid": auid, "task_uid": target_uid,
                                "res_uid": ru, "units": float(qty), "work_h": 8})
            auid += 1

    # ----- Build XML -----
    parts = _project_header(
        "Управління ротою РРР - Організаційна структура",
        f"Управління ротою РРР - Організаційна структура (БЧС {datetime.date(2026,5,2).strftime('%d.%m.%Y')})"
    )
    parts += _calendar_24x7(name="Стандартний (24/7)")

    parts.append('  <Tasks>')
    for t in tasks:
        parts += _task(t["uid"], t["id"], t["name"], t["level"], t["outline"],
                       t["summary"], t["dur_h"], notes=t.get("notes",""))
    parts.append('  </Tasks>')

    parts.append('  <Resources>')
    for r in resources:
        parts += _resource(r["uid"], r["name"], r.get("initials",""),
                           r.get("group",""), r.get("code",""), r.get("type",1))
    parts.append('  </Resources>')

    parts.append('  <Assignments>')
    for a in assignments:
        parts += _assignment(a["uid"], a["task_uid"], a["res_uid"],
                             a.get("units",1.0), a.get("work_h",8))
    parts.append('  </Assignments>')

    parts.append('</Project>')
    return "\n".join(parts)


# ============================== COMMAND CYCLE ==============================

def generate_command_cycle_xml(company):
    HQ = company["subunits"].get("__HQ__")
    plat_order = ["1 взвод радіорозвідки", "2 взвод радіорозвідки",
                  "взвод радіоелектронної розвідки", "взвод безпілотних"]

    def find_in_sub(sub_kw, pos_kw):
        for sub in company["subunits"].values():
            if any(kw in sub["name"].lower() for kw in sub_kw):
                for sq in sub["squads"].values():
                    for p in sq["positions"]:
                        if any(kw in p["position"].lower() for kw in pos_kw):
                            return p
        return None

    def find_in_hq(pos_kw):
        if not HQ: return None
        for sq in HQ["squads"].values():
            for p in sq["positions"]:
                if any(kw in p["position"].lower() for kw in pos_kw):
                    return p
        return None

    actors = []
    def add(role, person):
        if person:
            display = (person["fio"] or role) + (f' «{person["callsign"]}»' if person["callsign"] else "")
            rank = person["rank_actual"] or person["rank_state"] or ""
            actors.append({"role": role, "name": display, "rank": rank, "position": person["position"]})
        else:
            actors.append({"role": role, "name": role, "rank": "", "position": role})

    add("Командир роти", find_in_hq(["командир роти"]))
    add("ЗКР з ПП", find_in_hq(["заступник"]))
    add("Старший технік роти", find_in_hq(["старший технік"]))
    add("Головний сержант роти", find_in_hq(["головний сержант"]))
    add("Сержант із МЗ", find_in_hq(["матеріального забезпечення"]))
    add("Старший бойовий медик", find_in_hq(["медик"]))
    add("Начальник ГОІ", find_in_sub(["обробк"], ["начальник групи"]))
    for kw in plat_order:
        add(f"КВ — {kw.title()}", find_in_sub([kw], ["командир взводу"]))
    add("Начальник РМО", find_in_sub(["майстер"], ["начальник майстерні"]))

    phases = [
        ("I. Підготовка управління", [
            ("Отримання бойового завдання від КБ", 1, ["Командир роти"]),
            ("З'ясування завдання, виділення задач", 2, ["Командир роти", "ЗКР з ПП"]),
            ("Орієнтування заступників і командирів підрозділів", 1, ["Командир роти"]),
            ("Розрахунок часу", 1, ["Командир роти", "Головний сержант роти"]),
        ]),
        ("II. Оцінка обстановки", [
            ("Оцінка противника", 4, ["Начальник ГОІ"] + [f"КВ — {p.title()}" for p in plat_order]),
            ("Оцінка своїх сил, стану ОВТ", 2, ["Командир роти", "Старший технік роти", "Начальник РМО"]),
            ("Оцінка району дій, маршрутів, позицій", 3, ["Командир роти"] + [f"КВ — {p.title()}" for p in plat_order[:2]]),
            ("Оцінка часу, метеоумов, доріг", 1, ["Старший технік роти"]),
            ("Оцінка тилу, медицини, психології", 2, ["Сержант із МЗ", "Старший бойовий медик", "ЗКР з ПП"]),
        ]),
        ("III. Прийняття рішення", [
            ("Формування задуму бойових дій", 3, ["Командир роти"]),
            ("Визначення задач підрозділам та порядку взаємодії", 2, ["Командир роти"]),
            ("Доповідь рішення командиру батальйону", 1, ["Командир роти"]),
        ]),
        ("IV. Постановка задач підрозділам", [
            ("Бойовий наказ / розпорядження по роті", 2, ["Командир роти"]),
            ("Постановка задач Групі обробки інформації", 1, ["Начальник ГОІ"]),
            ("Постановка задач 1 Взводу РР", 1, [f"КВ — {plat_order[0].title()}"]),
            ("Постановка задач 2 Взводу РР", 1, [f"КВ — {plat_order[1].title()}"]),
            ("Постановка задач Взводу РЕР", 1, [f"КВ — {plat_order[2].title()}"]),
            ("Постановка задач Взводу БпАК", 1, [f"КВ — {plat_order[3].title()}"]),
            ("Постановка задач РМО", 1, ["Начальник РМО"]),
        ]),
        ("V. Забезпечення та взаємодія", [
            ("Розвідувально-інформаційний обмін", 2, ["Начальник ГОІ", "Командир роти"]),
            ("Зв'язок та управління", 2, ["Старший технік роти"]),
            ("Тил, ЗІП, ПММ, харчування", 2, ["Сержант із МЗ", "Начальник РМО"]),
            ("Медичне забезпечення", 2, ["Старший бойовий медик"]),
            ("Психологічна підтримка", 2, ["ЗКР з ПП"]),
        ]),
        ("VI. Контроль і виконання", [
            ("Контроль готовності підрозділів", 2, ["Командир роти", "Головний сержант роти"]),
            ("Виконання БЗ — ведення розвідки", 8, ["Начальник ГОІ"] + [f"КВ — {p.title()}" for p in plat_order]),
            ("Поточний контроль і коригування", 4, ["Командир роти"]),
        ]),
        ("VII. Доповіді та підсумки", [
            ("Поточні доповіді до КБ", 1, ["Командир роти", "Начальник ГОІ"]),
            ("Підсумкова доповідь за добу", 2, ["Командир роти", "Сержант із МЗ", "Старший бойовий медик"]),
            ("Постановка задач на наступну добу", 1, ["Командир роти"]),
        ]),
    ]

    # Resources
    resources = []
    res_uid_map = {}
    uid_seq = [1]
    def nu():
        v = uid_seq[0]; uid_seq[0] += 1; return v

    for a in actors:
        ru = nu()
        res_uid_map[a["role"]] = ru
        full = (a["rank"] + " " + a["name"]).strip()
        resources.append({"uid": ru, "name": full, "initials": a["role"][:8],
                          "group": a["role"], "code": a["position"], "type": 1})

    # Tasks
    tasks = []
    root_uid = nu()
    tasks.append({"uid": root_uid, "name": "Цикл управління ротою РРР (24 год)",
                  "level": 1, "outline": "1", "summary": True, "dur_h": 0, "preds": []})
    prev_phase_uid = None
    for ph_idx, (ph_name, items) in enumerate(phases, start=1):
        ph_uid = nu()
        tasks.append({"uid": ph_uid, "name": ph_name, "level": 2,
                      "outline": f"1.{ph_idx}", "summary": True, "dur_h": 0,
                      "preds": [prev_phase_uid] if prev_phase_uid else []})
        prev_sub_uid = None
        for it_idx, (tname, dur_h, assignees) in enumerate(items, start=1):
            t_uid = nu()
            tasks.append({"uid": t_uid, "name": tname, "level": 3,
                          "outline": f"1.{ph_idx}.{it_idx}", "summary": False,
                          "dur_h": dur_h, "preds": [prev_sub_uid] if prev_sub_uid else [],
                          "assignees": assignees, "critical": 1})
            prev_sub_uid = t_uid
        prev_phase_uid = ph_uid

    # IDs
    for i, t in enumerate(tasks, start=1):
        t["id"] = i

    # Phase totals
    for i, t in enumerate(tasks):
        if t["level"] == 2:
            children = []
            for j in range(i+1, len(tasks)):
                if tasks[j]["level"] <= 2: break
                if tasks[j]["level"] == 3: children.append(tasks[j])
            t["dur_h"] = sum(c["dur_h"] for c in children) or 1
    root_total = sum(t["dur_h"] for t in tasks if t["level"] == 2)
    tasks[0]["dur_h"] = root_total

    # Assignments
    assignments = []
    auid = 1
    for t in tasks:
        if t["level"] == 3:
            for role in t.get("assignees", []):
                if role in res_uid_map:
                    assignments.append({"uid": auid, "task_uid": t["uid"],
                                        "res_uid": res_uid_map[role],
                                        "units": 1.0, "work_h": t["dur_h"]})
                    auid += 1

    parts = _project_header("Управління ротою РРР - Бойове управління",
                            "Цикл управління ротою РРР (24 год)",
                            finish_dt=START + datetime.timedelta(hours=root_total))
    parts += _calendar_24x7(name="Бойовий цикл 24/7")

    parts.append('  <Tasks>')
    for t in tasks:
        parts += _task(t["uid"], t["id"], t["name"], t["level"], t["outline"],
                       t["summary"], t["dur_h"], preds=t.get("preds"),
                       notes=("Виконавці: " + ", ".join(t.get("assignees", [])) if t.get("assignees") else ""),
                       critical=t.get("critical", 0))
    parts.append('  </Tasks>')

    parts.append('  <Resources>')
    for r in resources:
        parts += _resource(r["uid"], r["name"], r["initials"], r["group"], r["code"], r["type"])
    parts.append('  </Resources>')

    parts.append('  <Assignments>')
    for a in assignments:
        parts += _assignment(a["uid"], a["task_uid"], a["res_uid"],
                             a["units"], a["work_h"])
    parts.append('  </Assignments>')

    parts.append('</Project>')
    return "\n".join(parts)


# ============================== INTERACTION MATRIX ==============================

def generate_interaction_matrix_xml(company, interactions):
    """Кожен зв'язок — окреме завдання з призначенням джерело+адресат."""
    parts = _project_header("Управління ротою РРР - Матриця взаємодії",
                            "Матриця взаємодії підрозділів роти РРР")
    parts += _calendar_24x7(name="Постійно")

    uid_seq = [1]
    def nu():
        v = uid_seq[0]; uid_seq[0] += 1; return v

    # Ресурси: усі підрозділи, що зустрічаються
    nodes = set()
    for i in interactions:
        nodes.add(i.get("source",""))
        nodes.add(i.get("target",""))
    # додаємо стандартні підрозділи з БЧС
    for sub_key in company["order"]:
        nodes.add(company["subunits"][sub_key]["name"])
    nodes.discard("")
    nodes = sorted(nodes)
    res_uid_map = {}
    resources_xml = []
    for n in nodes:
        ru = nu()
        res_uid_map[n] = ru
        resources_xml.append({"uid": ru, "name": n, "initials": n[:8],
                              "group": "Підрозділ", "code": "", "type": 1})

    # Tasks
    tasks = []
    root_uid = nu()
    tasks.append({"uid": root_uid, "name": "Матриця взаємодії підрозділів", "level": 1,
                  "outline": "1", "summary": True, "dur_h": 8})
    # Групуємо за каналами
    channels = {}
    for i in interactions:
        ch = i.get("channel", "інший")
        channels.setdefault(ch, []).append(i)

    ch_idx = 0
    for ch_name, links in sorted(channels.items()):
        ch_idx += 1
        ch_uid = nu()
        tasks.append({"uid": ch_uid, "name": f"Канал: {ch_name}", "level": 2,
                      "outline": f"1.{ch_idx}", "summary": True, "dur_h": 8})
        li = 0
        for link in links:
            li += 1
            t_uid = nu()
            tname = f'{link.get("source","")} → {link.get("target","")}'
            if link.get("freq"): tname += f' [{link["freq"]}]'
            if link.get("callsign"): tname += f' «{link["callsign"]}»'
            notes_bits = [
                f'Канал: {link.get("channel","")}',
                f'Частота/RC: {link.get("freq","")}',
                f'Позивний: {link.get("callsign","")}',
                f'Призначення: {link.get("purpose","")}',
            ]
            tasks.append({"uid": t_uid, "name": tname, "level": 3,
                          "outline": f"1.{ch_idx}.{li}", "summary": False,
                          "dur_h": 8, "notes": "\n".join(notes_bits),
                          "_link": link})

    # IDs
    for i, t in enumerate(tasks, start=1):
        t["id"] = i

    # Assignments: link → 2 ресурси (source + target)
    assignments = []
    auid = 1
    for t in tasks:
        link = t.get("_link")
        if link:
            for side in ("source", "target"):
                ru = res_uid_map.get(link.get(side,""))
                if ru:
                    assignments.append({"uid": auid, "task_uid": t["uid"],
                                        "res_uid": ru, "units": 1.0, "work_h": 8})
                    auid += 1

    parts.append('  <Tasks>')
    for t in tasks:
        parts += _task(t["uid"], t["id"], t["name"], t["level"], t["outline"],
                       t["summary"], t["dur_h"], notes=t.get("notes",""))
    parts.append('  </Tasks>')

    parts.append('  <Resources>')
    for r in resources_xml:
        parts += _resource(r["uid"], r["name"], r["initials"], r["group"], r["code"], r["type"])
    parts.append('  </Resources>')

    parts.append('  <Assignments>')
    for a in assignments:
        parts += _assignment(a["uid"], a["task_uid"], a["res_uid"], a["units"], a["work_h"])
    parts.append('  </Assignments>')

    parts.append('</Project>')
    return "\n".join(parts)
