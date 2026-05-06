"""Backend для редактора управління ротою РРР.

Функції:
  - Структура роти з БЧС (читається з structure.json)
  - CRUD засобів (озброєння/техніка/транспорт/зв'язок) з типом штатний/позаштатний
  - CRUD матриці взаємодії підрозділів
  - Генерація MS Project XML (org structure, бойове управління, матриця взаємодії)
  - ZIP-пакет
"""
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, json, io, zipfile, logging, uuid, datetime
from urllib.parse import quote as _quote
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal

from xml_generators import (
    generate_org_structure_xml,
    generate_command_cycle_xml,
    generate_interaction_matrix_xml,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Завантажуємо структуру роти з JSON (статичні дані БЧС)
with open(ROOT_DIR / 'structure.json', encoding='utf-8') as f:
    COMPANY = json.load(f)


app = FastAPI(title="Управління ротою РРР")
api_router = APIRouter(prefix="/api")


# ============================ MODELS =====================================
EQUIPMENT_CATEGORIES = ["Засіб зв'язку", "Транспорт", "ОВТ", "РТ засіб", "БпЛА", "Засіб РЕБ", "Інше"]
EQUIPMENT_TYPES = ["штатний", "позаштатний"]
EQUIPMENT_STATES = ["справний", "несправний", "потребує ремонту", "у польоті/виконанні", "втрачений"]


class EquipmentBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_path: str = Field(..., description="Шлях до вузла, напр. 'Управління роти' або '1 Взвод радіорозвідки/1 Відділення радіорозвідки'")
    category: str
    name: str
    type: Literal["штатний", "позаштатний"] = "штатний"
    qty: int = 1
    state: str = "справний"
    serial: str = ""
    notes: str = ""


class Equipment(EquipmentBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_path: Optional[str] = None
    category: Optional[str] = None
    name: Optional[str] = None
    type: Optional[Literal["штатний", "позаштатний"]] = None
    qty: Optional[int] = None
    state: Optional[str] = None
    serial: Optional[str] = None
    notes: Optional[str] = None


INTERACTION_CHANNELS = ["радіо УКХ", "радіо КХ", "ЗАЗ (захищений)", "цифровий канал", "дротовий", "посильний", "L-band/SAT"]


class InteractionBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str = Field(..., description="Підрозділ-джерело")
    target: str = Field(..., description="Підрозділ-отримувач")
    channel: str = "радіо УКХ"
    freq: str = ""           # частота / RC
    callsign: str = ""       # позивний станції
    purpose: str = ""        # призначення (доповіді, накази, дані розвідки тощо)


class Interaction(InteractionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class InteractionCreate(InteractionBase):
    pass


# ============================ STRUCTURE ROUTES ============================

@api_router.get("/structure")
async def get_structure():
    """Повертає повну структуру роти з БЧС + лічильники."""
    return COMPANY


@api_router.get("/nodes")
async def get_nodes():
    """Повертає плоский перелік усіх вузлів (підрозділ/відділення/посада) для UI."""
    nodes = []
    nodes.append({"path": COMPANY["name"], "type": "company", "label": COMPANY["name"]})
    for sub_key in COMPANY["order"]:
        sub = COMPANY["subunits"][sub_key]
        sub_path = sub["name"]
        nodes.append({"path": sub_path, "type": sub["type"], "label": sub["name"]})
        for sq_key, sq in sub["squads"].items():
            if sq_key == "__DIRECT__":
                # Додамо посади напряму під підрозділом
                for i, p in enumerate(sq["positions"]):
                    label = p["position"]
                    if p["fio"]:
                        label += f" — {p['fio']}"
                        if p["callsign"]:
                            label += f" «{p['callsign']}»"
                    nodes.append({
                        "path": f"{sub_path}/{p['position']}#{i}",
                        "type": "position",
                        "label": label,
                        "parent": sub_path,
                        "position_meta": p
                    })
            else:
                sq_path = f"{sub_path}/{sq['name']}"
                nodes.append({"path": sq_path, "type": "squad", "label": sq["name"], "parent": sub_path})
                for i, p in enumerate(sq["positions"]):
                    label = p["position"]
                    if p["fio"]:
                        label += f" — {p['fio']}"
                        if p["callsign"]:
                            label += f" «{p['callsign']}»"
                    nodes.append({
                        "path": f"{sq_path}/{p['position']}#{i}",
                        "type": "position",
                        "label": label,
                        "parent": sq_path,
                        "position_meta": p
                    })
    return {"nodes": nodes, "total_personnel": COMPANY["total_personnel"]}


# ============================ EQUIPMENT CRUD ============================

@api_router.get("/equipment", response_model=List[Equipment])
async def list_equipment(node_path: Optional[str] = None):
    q = {}
    if node_path:
        q["node_path"] = node_path
    items = await db.equipment.find(q, {"_id": 0}).to_list(5000)
    return items


@api_router.post("/equipment", response_model=Equipment)
async def create_equipment(payload: EquipmentCreate):
    item = Equipment(**payload.model_dump())
    await db.equipment.insert_one(item.model_dump())
    return item


@api_router.put("/equipment/{eid}", response_model=Equipment)
async def update_equipment(eid: str, payload: EquipmentUpdate):
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Немає полів для оновлення")
    res = await db.equipment.find_one_and_update(
        {"id": eid}, {"$set": upd},
        return_document=True, projection={"_id": 0}
    )
    if not res:
        raise HTTPException(404, "Засіб не знайдено")
    return res


@api_router.delete("/equipment/{eid}")
async def delete_equipment(eid: str):
    res = await db.equipment.delete_one({"id": eid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Засіб не знайдено")
    return {"deleted": eid}


@api_router.get("/equipment/summary")
async def equipment_summary():
    """Зведена статистика по засобах: за категоріями та типами."""
    items = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    by_cat = {}
    by_type = {"штатний": 0, "позаштатний": 0}
    for it in items:
        c = it.get("category", "Інше")
        by_cat[c] = by_cat.get(c, 0) + it.get("qty", 1)
        by_type[it.get("type", "штатний")] = by_type.get(it.get("type", "штатний"), 0) + it.get("qty", 1)
    return {"total_items": sum(by_cat.values()), "by_category": by_cat, "by_type": by_type}


# ============================ INTERACTION CRUD ============================

@api_router.get("/interactions", response_model=List[Interaction])
async def list_interactions():
    items = await db.interactions.find({}, {"_id": 0}).to_list(2000)
    return items


@api_router.post("/interactions", response_model=Interaction)
async def create_interaction(payload: InteractionCreate):
    item = Interaction(**payload.model_dump())
    await db.interactions.insert_one(item.model_dump())
    return item


@api_router.delete("/interactions/{iid}")
async def delete_interaction(iid: str):
    res = await db.interactions.delete_one({"id": iid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Зв'язок не знайдено")
    return {"deleted": iid}


@api_router.put("/interactions/{iid}", response_model=Interaction)
async def update_interaction(iid: str, payload: InteractionCreate):
    upd = payload.model_dump()
    res = await db.interactions.find_one_and_update(
        {"id": iid}, {"$set": upd},
        return_document=True, projection={"_id": 0}
    )
    if not res:
        raise HTTPException(404, "Зв'язок не знайдено")
    return res


# ============================ CONFIG / ENUMS =============================

@api_router.get("/config")
async def get_config():
    return {
        "equipment_categories": EQUIPMENT_CATEGORIES,
        "equipment_types": EQUIPMENT_TYPES,
        "equipment_states": EQUIPMENT_STATES,
        "interaction_channels": INTERACTION_CHANNELS,
    }


# ============================ PRESET (TYPICAL) ============================

@api_router.post("/equipment/preset/typical")
async def preset_typical():
    """Заповнює базу типовими засобами для роти РРР (стирає попередні засоби типу "штатний")."""
    await db.equipment.delete_many({"type": "штатний"})
    # Шаблон засобів за підрозділами
    presets = [
        # Управління роти
        ("Управління роти", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 2),
        ("Управління роти", "Засіб зв'язку", "Motorola DP4400e", 4),
        ("Управління роти", "Транспорт", "УРАЛ-4320 (КУНГ)", 1),
        ("Управління роти", "Транспорт", "MITSUBISHI L200", 1),
        ("Управління роти", "ОВТ", "АК-74", 7),
        ("Управління роти", "ОВТ", "ПМ", 2),
        # Група обробки інформації
        ("Група обробки інформації", "РТ засіб", "АРК «КОЛЧАН»", 1),
        ("Група обробки інформації", "Засіб зв'язку", "Starlink (термінал)", 2),
        ("Група обробки інформації", "Транспорт", "ГАЗ-66 (КШМ)", 1),
        ("Група обробки інформації", "ОВТ", "АК-74", 8),
        # 1 Взвод радіорозвідки
        ("1 Взвод радіорозвідки", "РТ засіб", "Станція «КВАРТА»", 2),
        ("1 Взвод радіорозвідки", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 4),
        ("1 Взвод радіорозвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 2),
        ("1 Взвод радіорозвідки", "ОВТ", "АК-74", 20),
        # 2 Взвод радіорозвідки
        ("2 Взвод радіорозвідки", "РТ засіб", "Станція «КВАРТА»", 3),
        ("2 Взвод радіорозвідки", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 6),
        ("2 Взвод радіорозвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 3),
        ("2 Взвод радіорозвідки", "ОВТ", "АК-74", 29),
        # Взвод РЕР
        ("Взвод радіоелектронної розвідки", "РТ засіб", "Станція «БУКОВЕЛЬ-AD»", 3),
        ("Взвод радіоелектронної розвідки", "РТ засіб", "Пост РЕР «ХОРТИЦЯ»", 1),
        ("Взвод радіоелектронної розвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 3),
        ("Взвод радіоелектронної розвідки", "ОВТ", "АК-74", 26),
        # Взвод БпАК
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "MAVIC 3T", 6),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "AUTEL EVO MAX 4T", 3),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "FPV 7\" (ударні)", 30),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "POSEIDON H10 (розвідник)", 2),
        ("Взвод безпілотних авіаційних комплексів", "Засіб РЕБ", "Антена-репітер «КВЕРТУС»", 2),
        ("Взвод безпілотних авіаційних комплексів", "Транспорт", "TOYOTA HILUX", 2),
        ("Взвод безпілотних авіаційних комплексів", "Транспорт", "MITSUBISHI L200", 1),
        ("Взвод безпілотних авіаційних комплексів", "ОВТ", "АК-74", 16),
        # Ремонтна майстерня
        ("Ремонтна майстерня озброєння", "ОВТ", "Набір зброяра ТАК-3", 1),
        ("Ремонтна майстерня озброєння", "Транспорт", "ГАЗ-66 (рем.)", 1),
        ("Ремонтна майстерня озброєння", "ОВТ", "АК-74", 3),
    ]
    docs = []
    for node_path, cat, name, qty in presets:
        item = Equipment(
            node_path=node_path, category=cat, name=name,
            type="штатний", qty=qty, state="справний"
        )
        docs.append(item.model_dump())
    if docs:
        await db.equipment.insert_many(docs)
    return {"inserted": len(docs)}


@api_router.post("/interactions/preset/typical")
async def preset_typical_interactions():
    """Типова матриця взаємодії роти РРР."""
    await db.interactions.delete_many({})
    presets = [
        ("Командир батальйону", "Управління роти", "ЗАЗ (захищений)", "RC-1", "ШЕВА", "Накази, доповіді"),
        ("Управління роти", "1 Взвод радіорозвідки", "радіо УКХ", "RC-12", "КОЛУМБ", "Постановка задач, доповіді"),
        ("Управління роти", "2 Взвод радіорозвідки", "радіо УКХ", "RC-13", "КВ-2", "Постановка задач, доповіді"),
        ("Управління роти", "Взвод радіоелектронної розвідки", "радіо УКХ", "RC-14", "КВ-РЕР", "Постановка задач, доповіді"),
        ("Управління роти", "Взвод безпілотних авіаційних комплексів", "цифровий канал", "RC-15", "КВ-БпАК", "Постановка задач, керування"),
        ("Управління роти", "Група обробки інформації", "цифровий канал", "Starlink+VPN", "САЙРЄКС", "Інформаційний обмін"),
        ("1 Взвод радіорозвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Передача даних радіоперехоплення"),
        ("2 Взвод радіорозвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Передача даних радіоперехоплення"),
        ("Взвод радіоелектронної розвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Передача спектрограм та координат"),
        ("Взвод безпілотних авіаційних комплексів", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Передача відео/координат цілей"),
        ("Управління роти", "Ремонтна майстерня озброєння", "радіо УКХ", "RC-19", "—", "Заявки на ремонт ОВТ"),
    ]
    docs = []
    for src, tgt, ch, freq, cs, purpose in presets:
        it = Interaction(source=src, target=tgt, channel=ch, freq=freq, callsign=cs, purpose=purpose)
        docs.append(it.model_dump())
    if docs:
        await db.interactions.insert_many(docs)
    return {"inserted": len(docs)}


# ============================ EXPORT ROUTES ============================

@api_router.get("/export/orgstructure.xml")
async def export_orgstructure():
    equipment = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    xml = generate_org_structure_xml(COMPANY, equipment)
    fn = "Управління ротою РРР - Організаційна структура.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"orgstructure.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return Response(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/command.xml")
async def export_command():
    xml = generate_command_cycle_xml(COMPANY)
    fn = "Управління ротою РРР - Бойове управління.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"command.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return Response(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/interactions.xml")
async def export_interactions():
    interactions = await db.interactions.find({}, {"_id": 0}).to_list(2000)
    xml = generate_interaction_matrix_xml(COMPANY, interactions)
    fn = "Управління ротою РРР - Матриця взаємодії.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"interactions.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return Response(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/full-package.zip")
async def export_full_package():
    equipment = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    interactions = await db.interactions.find({}, {"_id": 0}).to_list(2000)
    org_xml = generate_org_structure_xml(COMPANY, equipment)
    cmd_xml = generate_command_cycle_xml(COMPANY)
    int_xml = generate_interaction_matrix_xml(COMPANY, interactions)
    # Equipment list as CSV
    csv_lines = ["Підрозділ;Категорія;Назва;Тип;К-сть;Стан;Серійний;Примітки"]
    for e in equipment:
        csv_lines.append(";".join([
            e.get("node_path",""), e.get("category",""), e.get("name",""),
            e.get("type",""), str(e.get("qty",1)),
            e.get("state",""), e.get("serial",""), e.get("notes","").replace(";",",").replace("\n"," ")
        ]))
    csv_text = "\n".join(csv_lines)

    # Interactions CSV
    icsv = ["Джерело;Адресат;Канал;Частота/RC;Позивний;Призначення"]
    for i in interactions:
        icsv.append(";".join([
            i.get("source",""), i.get("target",""), i.get("channel",""),
            i.get("freq",""), i.get("callsign",""), i.get("purpose","")
        ]))
    icsv_text = "\n".join(icsv)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Управління ротою РРР - Організаційна структура.xml", org_xml)
        zf.writestr("Управління ротою РРР - Бойове управління.xml", cmd_xml)
        zf.writestr("Управління ротою РРР - Матриця взаємодії.xml", int_xml)
        zf.writestr("Засоби (озброєння-техніка-зв'язок).csv", "\ufeff" + csv_text)
        zf.writestr("Матриця взаємодії.csv", "\ufeff" + icsv_text)
    buf.seek(0)
    fn = "Управління ротою РРР - пакет.zip"
    headers = {"Content-Disposition": f"attachment; filename=\"package.zip\"; filename*=UTF-8''{_quote(fn)}"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


# ============================ ROOT ============================

@api_router.get("/")
async def root():
    counts = {k: COMPANY["subunits"][k]["count"] for k in COMPANY["order"]}
    return {
        "app": "Управління ротою РРР",
        "company": COMPANY["name"],
        "total_personnel": COMPANY["total_personnel"],
        "subunits": counts
    }


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
