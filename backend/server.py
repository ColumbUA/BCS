"""Backend для редактора управління ротою радіо та радіотехнічної розвідки.

Функції:
  - Структура роти з БЧС (читається з structure.json)
  - CRUD засобів (озброєння/техніка/транспорт/зв'язок)
  - CRUD матриці взаємодії
  - CRUD особових карток солдатів + завантаження документів
  - CRUD обліку боєкомплекту (БК)
  - JWT-авторизація + ролі + 2FA TOTP
  - Сповіщення матеріалісту про неповні документи
  - Експорт у MS Project XML
"""
from fastapi import (
    FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
)
from fastapi.responses import StreamingResponse, FileResponse, Response as FastAPIResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, json, io, zipfile, logging, uuid, datetime, mimetypes
from urllib.parse import quote as _quote
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Auth & XML modules
from auth import (
    UserCreate, UserPublic, LoginRequest, TokenResponse,
    hash_password, verify_password, create_access_token,
    gen_totp_secret, gen_totp_qr, verify_totp,
    get_current_user, commander_only, can_edit, require_role,
    is_locked, record_failed, clear_attempts, seed_users,
)
from xml_generators import (
    generate_org_structure_xml,
    generate_command_cycle_xml,
    generate_interaction_matrix_xml,
)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Storage для документів
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/app/storage"))
DOCS_DIR = STORAGE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Завантажуємо структуру роти з JSON
with open(ROOT_DIR / 'structure.json', encoding='utf-8') as f:
    COMPANY = json.load(f)


app = FastAPI(title="Управління ротою РРР")
app.state.db = db
api_router = APIRouter(prefix="/api")


# ============================ ENUMS / CONSTS =====================================
EQUIPMENT_CATEGORIES = ["Засіб зв'язку", "Транспорт", "ОВТ", "РТ засіб", "БпЛА", "Засіб РЕБ", "Інше"]
EQUIPMENT_TYPES = ["штатний", "позаштатний"]
EQUIPMENT_STATES = ["справний", "несправний", "потребує ремонту", "у польоті/виконанні", "втрачений"]
INTERACTION_CHANNELS = ["радіо УКХ", "радіо КХ", "ЗАЗ (захищений)", "цифровий канал", "дротовий", "посильний", "L-band/SAT"]

WEAPON_TYPES = [
    "АК-74", "АКС-74", "АК-74М", "АКС-74У",
    "CZ BREN 2 (5.56 мм)",
    "ПМ", "Форт-12", "Глок-19",
    "ПКМ", "РПК-74",
    "СВД", "ВСС «ВИНТОРЕЗ»",
    "РПГ-7В", "РПГ-22",
    "РГД-5", "Ф-1", "РГ-42", "РГО",
    "ВОГ-25", "ВОГ-25П",
    "ВОГ-17", "АГС-17",
    "Інше",
]
AMMO_TYPES = ["патрон", "граната", "ВОГ", "сигнальний", "трасер", "запал", "інше"]
DOCUMENT_TYPES = {
    "passport": "Паспорт",
    "ipn": "ІПН (РНОКПП)",
    "diploma": "Диплом / атестат",
    "driver_license": "Водійське посвідчення",
    "military_id": "Військовий квиток / офіцерське посвідчення",
    "certificate": "Сертифікат / посвідчення",
    "other": "Інше",
}
REQUIRED_DOC_TYPES = ["passport", "ipn", "military_id"]   # обов'язкові для всіх
DRIVER_REQUIRED = ["passport", "ipn", "military_id", "driver_license"]


# ============================ AUTH ROUTES ============================

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    ident = req.username.strip().lower()
    if await is_locked(db, ident):
        raise HTTPException(status_code=423, detail="Акаунт тимчасово заблоковано (>5 невдалих спроб). Зачекайте 15 хв.")
    user = await db.users.find_one({"username": ident}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        await record_failed(db, ident)
        raise HTTPException(status_code=401, detail="Невірний логін або пароль")
    # 2FA — окремий лічильник, щоб помилка коду не блокувала legit-користувача
    if user.get("totp_enabled"):
        if not req.totp_code:
            raise HTTPException(status_code=401, detail="Потрібен код 2FA з Google Authenticator")
        if not verify_totp(user.get("totp_secret", ""), req.totp_code):
            # Не використовуємо record_failed (це для пароля) — просто 401
            raise HTTPException(status_code=401, detail="Невірний код 2FA")
    await clear_attempts(db, ident)
    token = create_access_token(user["id"], user["username"], user["role"])
    public = {k: user.get(k) for k in ["id", "username", "name", "role", "platoon", "totp_enabled"]}
    public["created_at"] = user.get("created_at", "")
    return TokenResponse(access_token=token, user=UserPublic(**public))


@api_router.get("/auth/me", response_model=UserPublic)
async def auth_me(user=Depends(get_current_user)):
    full = await db.users.find_one({"id": user.id}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
    return UserPublic(**full)


@api_router.post("/auth/2fa/setup")
async def setup_2fa(user=Depends(get_current_user)):
    """Генерує новий TOTP secret + QR-код. Поки не активний, доки не verify."""
    secret = gen_totp_secret()
    await db.users.update_one({"id": user.id}, {"$set": {"totp_secret": secret, "totp_enabled": False}})
    qr = gen_totp_qr(user.username, secret)
    return {"secret": secret, "qr_data_uri": qr}


@api_router.post("/auth/2fa/verify")
async def verify_2fa(payload: dict, user=Depends(get_current_user)):
    code = payload.get("code", "")
    full = await db.users.find_one({"id": user.id}, {"_id": 0})
    if not verify_totp(full.get("totp_secret", ""), code):
        raise HTTPException(status_code=400, detail="Невірний код. Спробуйте ще раз.")
    await db.users.update_one({"id": user.id}, {"$set": {"totp_enabled": True}})
    return {"enabled": True}


@api_router.post("/auth/2fa/disable")
async def disable_2fa(user=Depends(get_current_user)):
    await db.users.update_one({"id": user.id}, {"$set": {"totp_enabled": False, "totp_secret": ""}})
    return {"enabled": False}


@api_router.post("/auth/change-password")
async def change_password(payload: dict, user=Depends(get_current_user)):
    old_pwd = payload.get("old_password", "")
    new_pwd = payload.get("new_password", "")
    if len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="Пароль має бути ≥6 символів")
    full = await db.users.find_one({"id": user.id}, {"_id": 0})
    if not verify_password(old_pwd, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Невірний старий пароль")
    await db.users.update_one({"id": user.id}, {"$set": {"password_hash": hash_password(new_pwd)}})
    return {"ok": True}


# ============================ STRUCTURE ROUTES ============================

@api_router.get("/structure")
async def get_structure(user=Depends(get_current_user)):
    return COMPANY


@api_router.get("/")
async def root():
    counts = {k: COMPANY["subunits"][k]["count"] for k in COMPANY["order"]}
    return {
        "app": "Управління ротою РРР",
        "company": COMPANY["name"],
        "total_personnel": COMPANY["total_personnel"],
        "subunits": counts
    }


# ============================ EQUIPMENT CRUD ============================

class EquipmentBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_path: str
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


@api_router.get("/equipment", response_model=List[Equipment])
async def list_equipment(node_path: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if node_path:
        q["node_path"] = node_path
    return await db.equipment.find(q, {"_id": 0}).to_list(5000)


@api_router.post("/equipment", response_model=Equipment)
async def create_equipment(payload: EquipmentBase, user=Depends(can_edit)):
    item = Equipment(**payload.model_dump())
    await db.equipment.insert_one(item.model_dump())
    return item


@api_router.put("/equipment/{eid}", response_model=Equipment)
async def update_equipment(eid: str, payload: EquipmentUpdate, user=Depends(can_edit)):
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(400, "Немає полів")
    res = await db.equipment.find_one_and_update({"id": eid}, {"$set": upd},
                                                 return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Не знайдено")
    return res


@api_router.delete("/equipment/{eid}")
async def delete_equipment(eid: str, user=Depends(can_edit)):
    res = await db.equipment.delete_one({"id": eid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Не знайдено")
    return {"deleted": eid}


@api_router.get("/equipment/summary")
async def equipment_summary(user=Depends(get_current_user)):
    items = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    by_cat, by_type = {}, {"штатний": 0, "позаштатний": 0}
    for it in items:
        c = it.get("category", "Інше")
        by_cat[c] = by_cat.get(c, 0) + it.get("qty", 1)
        by_type[it.get("type", "штатний")] = by_type.get(it.get("type", "штатний"), 0) + it.get("qty", 1)
    return {"total_items": sum(by_cat.values()), "by_category": by_cat, "by_type": by_type}


@api_router.post("/equipment/preset/typical")
async def preset_typical(user=Depends(commander_only)):
    await db.equipment.delete_many({"type": "штатний"})
    presets = [
        ("Управління роти", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 2),
        ("Управління роти", "Засіб зв'язку", "Motorola DP4400e", 4),
        ("Управління роти", "Транспорт", "УРАЛ-4320 (КУНГ)", 1),
        ("Управління роти", "Транспорт", "MITSUBISHI L200", 1),
        ("Управління роти", "ОВТ", "АК-74", 5),
        ("Управління роти", "ОВТ", "CZ BREN 2 (5.56 мм)", 2),
        ("Управління роти", "ОВТ", "ПМ", 2),
        ("Група обробки інформації", "РТ засіб", "АРК «КОЛЧАН»", 1),
        ("Група обробки інформації", "Засіб зв'язку", "Starlink (термінал)", 2),
        ("Група обробки інформації", "Транспорт", "ГАЗ-66 (КШМ)", 1),
        ("Група обробки інформації", "ОВТ", "АК-74", 8),
        ("1 Взвод радіорозвідки", "РТ засіб", "Станція «КВАРТА»", 2),
        ("1 Взвод радіорозвідки", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 4),
        ("1 Взвод радіорозвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 2),
        ("1 Взвод радіорозвідки", "ОВТ", "АК-74", 18),
        ("1 Взвод радіорозвідки", "ОВТ", "CZ BREN 2 (5.56 мм)", 2),
        ("2 Взвод радіорозвідки", "РТ засіб", "Станція «КВАРТА»", 3),
        ("2 Взвод радіорозвідки", "Засіб зв'язку", "Р-187П1 АКВЕДУК", 6),
        ("2 Взвод радіорозвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 3),
        ("2 Взвод радіорозвідки", "ОВТ", "АК-74", 26),
        ("2 Взвод радіорозвідки", "ОВТ", "CZ BREN 2 (5.56 мм)", 3),
        ("Взвод радіоелектронної розвідки", "РТ засіб", "Станція «БУКОВЕЛЬ-AD»", 3),
        ("Взвод радіоелектронної розвідки", "РТ засіб", "Пост РЕР «ХОРТИЦЯ»", 1),
        ("Взвод радіоелектронної розвідки", "Транспорт", "УРАЛ-4320 (КУНГ)", 3),
        ("Взвод радіоелектронної розвідки", "ОВТ", "АК-74", 24),
        ("Взвод радіоелектронної розвідки", "ОВТ", "CZ BREN 2 (5.56 мм)", 2),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "MAVIC 3T", 6),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "AUTEL EVO MAX 4T", 3),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "FPV 7\" (ударні)", 30),
        ("Взвод безпілотних авіаційних комплексів", "БпЛА", "POSEIDON H10", 2),
        ("Взвод безпілотних авіаційних комплексів", "Засіб РЕБ", "Антена-репітер «КВЕРТУС»", 2),
        ("Взвод безпілотних авіаційних комплексів", "Транспорт", "TOYOTA HILUX", 2),
        ("Взвод безпілотних авіаційних комплексів", "Транспорт", "MITSUBISHI L200", 1),
        ("Взвод безпілотних авіаційних комплексів", "ОВТ", "АК-74", 14),
        ("Взвод безпілотних авіаційних комплексів", "ОВТ", "CZ BREN 2 (5.56 мм)", 2),
        ("Ремонтна майстерня озброєння", "ОВТ", "Набір зброяра ТАК-3", 1),
        ("Ремонтна майстерня озброєння", "Транспорт", "ГАЗ-66 (рем.)", 1),
        ("Ремонтна майстерня озброєння", "ОВТ", "АК-74", 3),
    ]
    docs = [Equipment(node_path=n, category=c, name=na, type="штатний", qty=q, state="справний").model_dump()
            for n, c, na, q in presets]
    if docs:
        await db.equipment.insert_many(docs)
    return {"inserted": len(docs)}


# ============================ INTERACTIONS CRUD ============================

class InteractionBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str
    target: str
    channel: str = "радіо УКХ"
    freq: str = ""
    callsign: str = ""
    purpose: str = ""


class Interaction(InteractionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


@api_router.get("/interactions", response_model=List[Interaction])
async def list_interactions(user=Depends(get_current_user)):
    return await db.interactions.find({}, {"_id": 0}).to_list(2000)


@api_router.post("/interactions", response_model=Interaction)
async def create_interaction(payload: InteractionBase, user=Depends(can_edit)):
    item = Interaction(**payload.model_dump())
    await db.interactions.insert_one(item.model_dump())
    return item


@api_router.put("/interactions/{iid}", response_model=Interaction)
async def update_interaction(iid: str, payload: InteractionBase, user=Depends(can_edit)):
    res = await db.interactions.find_one_and_update({"id": iid}, {"$set": payload.model_dump()},
                                                    return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Не знайдено")
    return res


@api_router.delete("/interactions/{iid}")
async def delete_interaction(iid: str, user=Depends(can_edit)):
    res = await db.interactions.delete_one({"id": iid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Не знайдено")
    return {"deleted": iid}


@api_router.post("/interactions/preset/typical")
async def preset_typical_interactions(user=Depends(commander_only)):
    await db.interactions.delete_many({})
    presets = [
        ("Командир батальйону", "Управління роти", "ЗАЗ (захищений)", "RC-1", "КОЛУМБ", "Накази, доповіді"),
        ("Управління роти", "1 Взвод радіорозвідки", "радіо УКХ", "RC-12", "КВ-1", "Постановка задач"),
        ("Управління роти", "2 Взвод радіорозвідки", "радіо УКХ", "RC-13", "КВ-2", "Постановка задач"),
        ("Управління роти", "Взвод радіоелектронної розвідки", "радіо УКХ", "RC-14", "КВ-РЕР", "Постановка задач"),
        ("Управління роти", "Взвод безпілотних авіаційних комплексів", "цифровий канал", "RC-15", "КВ-БпАК", "Постановка задач"),
        ("Управління роти", "Група обробки інформації", "цифровий канал", "Starlink+VPN", "САЙРЄКС", "Інформаційний обмін"),
        ("1 Взвод радіорозвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Дані радіоперехоплення"),
        ("2 Взвод радіорозвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Дані радіоперехоплення"),
        ("Взвод радіоелектронної розвідки", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Спектрограми, координати"),
        ("Взвод безпілотних авіаційних комплексів", "Група обробки інформації", "цифровий канал", "VPN/файл", "—", "Відео/координати цілей"),
        ("Управління роти", "Ремонтна майстерня озброєння", "радіо УКХ", "RC-19", "—", "Заявки на ремонт"),
    ]
    docs = [Interaction(source=s, target=t, channel=c, freq=f, callsign=cs, purpose=p).model_dump()
            for s, t, c, f, cs, p in presets]
    if docs:
        await db.interactions.insert_many(docs)
    return {"inserted": len(docs)}


# ============================ SOLDIERS CRUD ============================

class EducationItem(BaseModel):
    degree: str = ""        # ступінь
    institution: str = ""
    year: str = ""
    specialty: str = ""


class Certificate(BaseModel):
    name: str = ""
    issued_at: str = ""
    issuer: str = ""


class SoldierBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fio: str
    callsign: str = ""
    node_path: str = ""           # підрозділ/відділення
    position: str = ""            # посада з БЧС
    rank: str = ""
    birth_date: str = ""
    mobilized_at: str = ""        # дата мобілізації (YYYY-MM-DD)
    bzvp_passed_at: str = ""      # дата проходження БЗВП
    ktz_passed_at: str = ""       # дата проходження КТЗ
    education: List[EducationItem] = []
    certificates: List[Certificate] = []
    blood_group: str = ""
    has_driver_license: bool = False
    notes: str = ""


class Soldier(SoldierBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    documents: dict = {}    # {type: file_id}
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = ""


@api_router.get("/soldiers", response_model=List[Soldier])
async def list_soldiers(user=Depends(get_current_user)):
    return await db.soldiers.find({}, {"_id": 0}).to_list(500)


@api_router.get("/soldiers/{sid}", response_model=Soldier)
async def get_soldier(sid: str, user=Depends(get_current_user)):
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Картку не знайдено")
    return s


@api_router.post("/soldiers", response_model=Soldier)
async def create_soldier(payload: SoldierBase, user=Depends(can_edit)):
    item = Soldier(**payload.model_dump())
    item.updated_at = item.created_at
    await db.soldiers.insert_one(item.model_dump())
    return item


@api_router.put("/soldiers/{sid}", response_model=Soldier)
async def update_soldier(sid: str, payload: SoldierBase, user=Depends(can_edit)):
    upd = payload.model_dump()
    upd["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    res = await db.soldiers.find_one_and_update({"id": sid}, {"$set": upd},
                                                return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Картку не знайдено")
    return res


@api_router.delete("/soldiers/{sid}")
async def delete_soldier(sid: str, user=Depends(commander_only)):
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if s:
        # видалити документи
        for fid in (s.get("documents") or {}).values():
            await _delete_file(fid)
    await db.soldiers.delete_one({"id": sid})
    return {"deleted": sid}


@api_router.post("/soldiers/seed-from-bchs")
async def seed_soldiers_from_bchs(user=Depends(commander_only)):
    """Створює картки для всіх посад з БЧС, у яких є ПІБ."""
    inserted = 0
    for sub_key, sub in COMPANY["subunits"].items():
        sub_name = sub["name"]
        for sq_key, sq in sub["squads"].items():
            sq_path = sub_name if sq_key == "__DIRECT__" else f"{sub_name}/{sq['name']}"
            for p in sq["positions"]:
                if not p.get("fio"):
                    continue
                # Перевіримо чи вже є картка
                ex = await db.soldiers.find_one({"fio": p["fio"]}, {"_id": 0})
                if ex:
                    continue
                s = Soldier(
                    fio=p["fio"], callsign=p.get("callsign", ""),
                    node_path=sq_path, position=p["position"],
                    rank=p.get("rank_actual") or p.get("rank_state", ""),
                )
                s.updated_at = s.created_at
                await db.soldiers.insert_one(s.model_dump())
                inserted += 1
    return {"inserted": inserted}


# ============================ DOCUMENTS UPLOAD ============================

async def _delete_file(file_id: str):
    p = DOCS_DIR / file_id
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass
    await db.doc_files.delete_one({"id": file_id})


@api_router.post("/soldiers/{sid}/documents")
async def upload_document(
    sid: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(can_edit),
):
    if doc_type not in DOCUMENT_TYPES:
        raise HTTPException(400, "Невідомий тип документа")
    soldier = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if not soldier:
        raise HTTPException(404, "Картку не знайдено")
    # Заміняємо існуючий документ цього типу
    docs = soldier.get("documents") or {}
    if doc_type in docs:
        await _delete_file(docs[doc_type])
    file_id = str(uuid.uuid4())
    storage_path = DOCS_DIR / file_id
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Файл більше 20MB")
    with open(storage_path, "wb") as f:
        f.write(content)
    meta = {
        "id": file_id,
        "soldier_id": sid,
        "type": doc_type,
        "filename": file.filename or "document",
        "size": len(content),
        "mime": file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream",
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "uploaded_by": user.username,
    }
    await db.doc_files.insert_one(meta)
    docs[doc_type] = file_id
    await db.soldiers.update_one({"id": sid},
                                 {"$set": {"documents": docs,
                                           "updated_at": meta["uploaded_at"]}})
    return {"file_id": file_id, "filename": meta["filename"]}


@api_router.get("/documents/{file_id}")
async def download_document(file_id: str, user=Depends(get_current_user)):
    meta = await db.doc_files.find_one({"id": file_id}, {"_id": 0})
    if not meta:
        raise HTTPException(404, "Файл не знайдено")
    p = DOCS_DIR / file_id
    if not p.exists():
        raise HTTPException(404, "Файл втрачено")
    fn = meta["filename"]
    headers = {"Content-Disposition": f"attachment; filename=\"file\"; filename*=UTF-8''{_quote(fn)}"}
    return FileResponse(p, media_type=meta.get("mime", "application/octet-stream"),
                        filename=fn, headers=headers)


@api_router.delete("/documents/{file_id}")
async def delete_document(file_id: str, user=Depends(can_edit)):
    meta = await db.doc_files.find_one({"id": file_id}, {"_id": 0})
    if not meta:
        raise HTTPException(404, "Файл не знайдено")
    await db.soldiers.update_one(
        {"id": meta["soldier_id"]},
        {"$unset": {f"documents.{meta['type']}": ""}}
    )
    await _delete_file(file_id)
    return {"deleted": file_id}


@api_router.get("/soldiers/{sid}/documents")
async def list_soldier_documents(sid: str, user=Depends(get_current_user)):
    metas = await db.doc_files.find({"soldier_id": sid}, {"_id": 0}).to_list(100)
    return metas


# ============================ AMMUNITION (БК) ============================

class AmmoBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_path: str                       # підрозділ
    weapon: str                          # АК-74, CZ BREN 2 (5.56 мм), РГД-5 тощо
    ammo_type: str = "патрон"            # патрон / граната / ВОГ
    caliber: str = ""                    # 5.45×39, 5.56×45 тощо
    qty: int = 0
    unit: str = "шт"
    notes: str = ""


class Ammo(AmmoBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


@api_router.get("/ammo", response_model=List[Ammo])
async def list_ammo(user=Depends(get_current_user)):
    return await db.ammo.find({}, {"_id": 0}).to_list(2000)


@api_router.post("/ammo", response_model=Ammo)
async def create_ammo(payload: AmmoBase, user=Depends(can_edit)):
    item = Ammo(**payload.model_dump())
    await db.ammo.insert_one(item.model_dump())
    return item


@api_router.put("/ammo/{aid}", response_model=Ammo)
async def update_ammo(aid: str, payload: AmmoBase, user=Depends(can_edit)):
    upd = payload.model_dump()
    upd["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    res = await db.ammo.find_one_and_update({"id": aid}, {"$set": upd},
                                            return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Не знайдено")
    return res


@api_router.delete("/ammo/{aid}")
async def delete_ammo(aid: str, user=Depends(can_edit)):
    res = await db.ammo.delete_one({"id": aid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Не знайдено")
    return {"deleted": aid}


@api_router.post("/ammo/preset/typical")
async def preset_ammo(user=Depends(commander_only)):
    """Типовий БК на роту (норма по 1 БК)."""
    await db.ammo.delete_many({})
    presets = [
        # (підрозділ, зброя, тип, калібр, к-сть)
        ("Управління роти", "АК-74", "патрон", "5.45×39", 5*150),
        ("Управління роти", "CZ BREN 2 (5.56 мм)", "патрон", "5.56×45", 2*210),
        ("Управління роти", "ПМ", "патрон", "9×18", 2*32),
        ("Управління роти", "РГД-5", "граната", "", 7*2),
        ("Управління роти", "Ф-1", "граната", "", 7*1),
        ("Група обробки інформації", "АК-74", "патрон", "5.45×39", 8*150),
        ("Група обробки інформації", "РГД-5", "граната", "", 8*2),
        ("1 Взвод радіорозвідки", "АК-74", "патрон", "5.45×39", 18*150),
        ("1 Взвод радіорозвідки", "CZ BREN 2 (5.56 мм)", "патрон", "5.56×45", 2*210),
        ("1 Взвод радіорозвідки", "РГД-5", "граната", "", 20*2),
        ("1 Взвод радіорозвідки", "Ф-1", "граната", "", 20*1),
        ("2 Взвод радіорозвідки", "АК-74", "патрон", "5.45×39", 26*150),
        ("2 Взвод радіорозвідки", "CZ BREN 2 (5.56 мм)", "патрон", "5.56×45", 3*210),
        ("2 Взвод радіорозвідки", "РГД-5", "граната", "", 29*2),
        ("2 Взвод радіорозвідки", "Ф-1", "граната", "", 29*1),
        ("Взвод радіоелектронної розвідки", "АК-74", "патрон", "5.45×39", 24*150),
        ("Взвод радіоелектронної розвідки", "CZ BREN 2 (5.56 мм)", "патрон", "5.56×45", 2*210),
        ("Взвод радіоелектронної розвідки", "РГД-5", "граната", "", 26*2),
        ("Взвод радіоелектронної розвідки", "Ф-1", "граната", "", 26*1),
        ("Взвод безпілотних авіаційних комплексів", "АК-74", "патрон", "5.45×39", 14*150),
        ("Взвод безпілотних авіаційних комплексів", "CZ BREN 2 (5.56 мм)", "патрон", "5.56×45", 2*210),
        ("Взвод безпілотних авіаційних комплексів", "ВОГ-25", "ВОГ", "40 мм", 50),
        ("Взвод безпілотних авіаційних комплексів", "РГД-5", "граната", "", 16*2),
        ("Ремонтна майстерня озброєння", "АК-74", "патрон", "5.45×39", 3*150),
    ]
    docs = [Ammo(node_path=n, weapon=w, ammo_type=t, caliber=c, qty=q).model_dump()
            for n, w, t, c, q in presets]
    if docs:
        await db.ammo.insert_many(docs)
    return {"inserted": len(docs)}


@api_router.get("/ammo/summary")
async def ammo_summary(user=Depends(get_current_user)):
    items = await db.ammo.find({}, {"_id": 0}).to_list(2000)
    by_weapon, by_type = {}, {}
    for it in items:
        by_weapon[it["weapon"]] = by_weapon.get(it["weapon"], 0) + it.get("qty", 0)
        by_type[it["ammo_type"]] = by_type.get(it["ammo_type"], 0) + it.get("qty", 0)
    return {"total": sum(by_weapon.values()), "by_weapon": by_weapon, "by_type": by_type}


# ============================ NOTIFICATIONS (для матеріаліста) ============================

@api_router.get("/notifications/material")
async def material_notifications(user=Depends(get_current_user)):
    """Повертає список солдатів з неповним пакетом документів."""
    soldiers = await db.soldiers.find({}, {"_id": 0}).to_list(500)
    issues = []
    for s in soldiers:
        docs = s.get("documents") or {}
        required = list(REQUIRED_DOC_TYPES)
        if s.get("has_driver_license"):
            required.append("driver_license")
        missing = [DOCUMENT_TYPES[d] for d in required if d not in docs]
        if missing:
            issues.append({
                "soldier_id": s["id"],
                "fio": s["fio"],
                "callsign": s.get("callsign", ""),
                "position": s.get("position", ""),
                "node_path": s.get("node_path", ""),
                "missing": missing,
                "missing_codes": [d for d in required if d not in docs],
            })
    return {
        "recipient": "ОРЛОВ Борис Борисович «ВЕНОМ» (матеріаліст)",
        "total_soldiers": len(soldiers),
        "with_issues": len(issues),
        "issues": issues,
    }


# ============================ CONFIG ============================

@api_router.get("/config")
async def get_config():
    return {
        "equipment_categories": EQUIPMENT_CATEGORIES,
        "equipment_types": EQUIPMENT_TYPES,
        "equipment_states": EQUIPMENT_STATES,
        "interaction_channels": INTERACTION_CHANNELS,
        "weapon_types": WEAPON_TYPES,
        "ammo_types": AMMO_TYPES,
        "document_types": DOCUMENT_TYPES,
        "required_doc_types": REQUIRED_DOC_TYPES,
        "company_name": COMPANY["name"],
    }


# ============================ EXPORT ============================

@api_router.get("/export/orgstructure.xml")
async def export_orgstructure(user=Depends(get_current_user)):
    equipment = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    xml = generate_org_structure_xml(COMPANY, equipment)
    fn = f"{COMPANY['name']} - Організаційна структура.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"orgstructure.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return FastAPIResponse(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/command.xml")
async def export_command(user=Depends(get_current_user)):
    xml = generate_command_cycle_xml(COMPANY)
    fn = f"{COMPANY['name']} - Бойове управління.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"command.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return FastAPIResponse(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/interactions.xml")
async def export_interactions(user=Depends(get_current_user)):
    interactions = await db.interactions.find({}, {"_id": 0}).to_list(2000)
    xml = generate_interaction_matrix_xml(COMPANY, interactions)
    fn = f"{COMPANY['name']} - Матриця взаємодії.xml"
    headers = {"Content-Disposition": f"attachment; filename=\"interactions.xml\"; filename*=UTF-8''{_quote(fn)}"}
    return FastAPIResponse(content=xml, media_type="application/xml", headers=headers)


@api_router.get("/export/full-package.zip")
async def export_full_package(user=Depends(get_current_user)):
    equipment = await db.equipment.find({}, {"_id": 0}).to_list(10000)
    interactions = await db.interactions.find({}, {"_id": 0}).to_list(2000)
    ammo = await db.ammo.find({}, {"_id": 0}).to_list(2000)
    soldiers = await db.soldiers.find({}, {"_id": 0}).to_list(500)
    org_xml = generate_org_structure_xml(COMPANY, equipment)
    cmd_xml = generate_command_cycle_xml(COMPANY)
    int_xml = generate_interaction_matrix_xml(COMPANY, interactions)

    csv_eq = ["Підрозділ;Категорія;Назва;Тип;К-сть;Стан;Серійний;Примітки"]
    for e in equipment:
        csv_eq.append(";".join([str(e.get(k, "")).replace(";", ",").replace("\n", " ")
                                for k in ("node_path", "category", "name", "type", "qty", "state", "serial", "notes")]))

    csv_int = ["Джерело;Адресат;Канал;Частота/RC;Позивний;Призначення"]
    for i in interactions:
        csv_int.append(";".join([str(i.get(k, "")).replace(";", ",").replace("\n", " ")
                                 for k in ("source", "target", "channel", "freq", "callsign", "purpose")]))

    csv_ammo = ["Підрозділ;Зброя;Тип;Калібр;К-сть;Од.;Примітки"]
    for a in ammo:
        csv_ammo.append(";".join([str(a.get(k, "")).replace(";", ",").replace("\n", " ")
                                  for k in ("node_path", "weapon", "ammo_type", "caliber", "qty", "unit", "notes")]))

    csv_sol = ["ПІБ;Позивний;Звання;Посада;Підрозділ;Дата мобілізації;БЗВП;КТЗ;Документів"]
    for s in soldiers:
        docs = s.get("documents") or {}
        csv_sol.append(";".join([str(s.get(k, "")) for k in ("fio", "callsign", "rank", "position", "node_path",
                                                              "mobilized_at", "bzvp_passed_at", "ktz_passed_at")]
                                + [str(len(docs))]))

    company_name = COMPANY["name"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{company_name} - Організаційна структура.xml", org_xml)
        zf.writestr(f"{company_name} - Бойове управління.xml", cmd_xml)
        zf.writestr(f"{company_name} - Матриця взаємодії.xml", int_xml)
        zf.writestr("Засоби.csv", "\ufeff" + "\n".join(csv_eq))
        zf.writestr("Матриця взаємодії.csv", "\ufeff" + "\n".join(csv_int))
        zf.writestr("Боєкомплект.csv", "\ufeff" + "\n".join(csv_ammo))
        zf.writestr("Особовий склад.csv", "\ufeff" + "\n".join(csv_sol))
    buf.seek(0)
    fn = f"{company_name} - пакет.zip"
    headers = {"Content-Disposition": f"attachment; filename=\"package.zip\"; filename*=UTF-8''{_quote(fn)}"}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


# ============================ STARTUP ============================

@app.on_event("startup")
async def startup():
    await seed_users(db)
    try:
        await db.users.create_index("username", unique=True)
        await db.equipment.create_index("node_path")
        await db.soldiers.create_index("fio", unique=False)
        await db.doc_files.create_index("soldier_id")
        await db.ammo.create_index("node_path")
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ============================ FINAL ============================

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
