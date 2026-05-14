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
from templates_lib import list_templates, render_template
from backup_mod import make_backup, list_backups, delete_backup, BACKUP_DIR
from audit_mod import log_audit, should_log, ensure_indexes as ensure_audit_indexes
from deps import WAREHOUSE_CATEGORIES, WAREHOUSE_TXN_TYPES

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


# ============================ AUDIT MIDDLEWARE ============================

from starlette.middleware.base import BaseHTTPMiddleware


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        method = request.method
        path = request.url.path
        response = await call_next(request)
        if should_log(method, path):
            try:
                # Витягнути user з токена (без блокування ендпоінта при помилках)
                user_obj = None
                token = None
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                elif request.cookies.get("access_token"):
                    token = request.cookies.get("access_token")
                if token:
                    try:
                        from auth import decode_token
                        payload = decode_token(token)
                        u = await db.users.find_one({"id": payload["sub"]},
                                                    {"_id": 0, "password_hash": 0, "totp_secret": 0})
                        if u:
                            class _U:
                                pass
                            user_obj = _U()
                            user_obj.id = u.get("id", "")
                            user_obj.username = u.get("username", "")
                            user_obj.role = u.get("role", "")
                            user_obj.platoon = u.get("platoon", "")
                    except Exception:
                        pass
                client_ip = request.client.host if request.client else ""
                # Body не логуємо щоб не ламати Streaming/UploadFile.
                # Метаінформація (path/method/status) уже достатньо для аудиту.
                await log_audit(
                    user=user_obj, method=method, path=path,
                    status_code=response.status_code,
                    body_snippet="", ip=client_ip,
                )
            except Exception:
                logging.exception("AuditMiddleware: failed to log")
        return response


# Підключимо ДО CORS (FastAPI middlewares додаються в зворотньому порядку)
app.add_middleware(AuditMiddleware)


# ============================ AUDIT API ============================

@api_router.get("/audit-log")
async def get_audit_log(
    limit: int = 200,
    category: str = "",
    username: str = "",
    success: Optional[bool] = None,
    user=Depends(commander_only),
):
    """Журнал дій (тільки COMMANDER). Зберігається 90 днів автоматично."""
    q: dict = {}
    if category:
        q["category"] = category
    if username:
        q["username"] = username
    if success is not None:
        q["success"] = success
    limit = max(1, min(limit, 1000))
    items = await db.audit_log.find(q, {"_id": 0, "created_at_ts": 0}).sort("created_at", -1).to_list(limit)
    return {"items": items, "total": len(items), "filters": {"category": category, "username": username, "success": success}}


@api_router.get("/audit-log/categories")
async def get_audit_categories(user=Depends(commander_only)):
    """Список доступних категорій для UI-фільтрів."""
    cats = await db.audit_log.distinct("category")
    users = await db.audit_log.distinct("username")
    return {"categories": sorted([c for c in cats if c]), "usernames": sorted([u for u in users if u])}


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

LOCATION_STATUSES = [
    "ППД",          # пункт постійної дислокації
    "РЗ",           # район зосередження
    "РВ",           # район виконання (бойове завдання)
    "Відрядження",
    "Відпустка",
    "Лікарня",
    "СЗЧ",          # самовільне залишення частини
    "ВЛК",
    "Інше",
]
TRANSFER_TYPES = {
    "in-rota":     "Переміщення в межах роти",
    "in-bat":      "Переміщення в межах батальйону",
    "in-polk":     "Переміщення в межах полка",
    "in-brigade":  "Переміщення в межах бригади",
    "in-zsu":      "Переміщення між частинами ЗСУ",
    "discharge":   "Звільнення з військової служби",
    "deceased":    "Виключення зі списків (загибель)",
    "missing":     "Виключення зі списків (зник безвісти)",
}
TRANSFER_STATUSES = ["draft", "submitted", "approved", "executed", "rejected"]
TRANSFER_STATUS_LABELS = {
    "draft":     "Чернетка",
    "submitted": "Подано (на розгляді)",
    "approved":  "Затверджено",
    "executed":  "Виконано",
    "rejected":  "Відхилено",
}
DOC_STATUSES = ["draft", "signed", "executed"]
DOC_STATUS_LABELS = {"draft": "Чернетка", "signed": "Підписано", "executed": "Виконано"}


def _company_node_paths() -> set[str]:
    """Список усіх валідних node_path (взвод та взвод/відділення) у поточній структурі."""
    paths: set[str] = set()
    for su_key in COMPANY.get("order", []):
        su = COMPANY["subunits"].get(su_key, {})
        su_name = su.get("name", "")
        if not su_name:
            continue
        paths.add(su_name)
        sqs = su.get("squads", {})
        if isinstance(sqs, dict):
            for sq_data in sqs.values():
                if isinstance(sq_data, dict):
                    sq_name = sq_data.get("name", "")
                    if sq_name:
                        paths.add(f"{su_name}/{sq_name}")
    return paths


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


# ============================ USERS MANAGEMENT (admin) ============================

class UserRegister(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str
    password: str
    name: str = ""
    role: Literal["COMMANDER", "PLATOON_LEADER", "MATERIAL", "VIEWER"] = "VIEWER"
    platoon: str = ""
    # Дані картки (опціонально):
    create_soldier_card: bool = True
    fio: str = ""
    callsign: str = ""
    rank: str = ""
    position: str = ""
    node_path: str = ""
    birth_date: str = ""
    mobilized_at: str = ""
    bzvp_passed_at: str = ""
    ktz_passed_at: str = ""
    blood_group: str = ""
    has_driver_license: bool = False
    notes: str = ""


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    role: Optional[Literal["COMMANDER", "PLATOON_LEADER", "MATERIAL", "VIEWER"]] = None
    platoon: Optional[str] = None
    new_password: Optional[str] = None    # скидання пароля адміном


@api_router.get("/users")
async def list_users(user=Depends(commander_only)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0, "totp_secret": 0}).to_list(500)
    return users


@api_router.post("/users/register")
async def register_user(payload: UserRegister, user=Depends(commander_only)):
    uname = payload.username.strip().lower()
    if not uname:
        raise HTTPException(400, "Логін обов'язковий")
    if len(payload.password) < 6:
        raise HTTPException(400, "Пароль ≥6 символів")
    existing = await db.users.find_one({"username": uname})
    if existing:
        raise HTTPException(400, "Логін уже існує")

    user_id = str(uuid.uuid4())
    soldier_id = None
    if payload.create_soldier_card and (payload.fio or payload.position):
        # Створюємо картку
        soldier_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await db.soldiers.insert_one({
            "id": soldier_id,
            "fio": payload.fio or payload.name,
            "callsign": payload.callsign,
            "rank": payload.rank,
            "position": payload.position,
            "node_path": payload.node_path,
            "birth_date": payload.birth_date,
            "mobilized_at": payload.mobilized_at,
            "bzvp_passed_at": payload.bzvp_passed_at,
            "ktz_passed_at": payload.ktz_passed_at,
            "blood_group": payload.blood_group,
            "has_driver_license": payload.has_driver_license,
            "education": [],
            "certificates": [],
            "documents": {},
            "notes": payload.notes,
            "created_at": now, "updated_at": now,
            "created_by_user": user_id,
        })

    await db.users.insert_one({
        "id": user_id,
        "username": uname,
        "password_hash": hash_password(payload.password),
        "name": payload.name or payload.fio or uname,
        "role": payload.role,
        "platoon": payload.platoon,
        "totp_secret": "", "totp_enabled": False,
        "soldier_id": soldier_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "created_by": user.username,
    })
    return {"user_id": user_id, "soldier_id": soldier_id, "username": uname}


@api_router.put("/users/{uid}")
async def admin_update_user(uid: str, payload: UserUpdate, user=Depends(commander_only)):
    upd = {k: v for k, v in payload.model_dump().items() if v is not None and k != "new_password"}
    if payload.new_password:
        if len(payload.new_password) < 6:
            raise HTTPException(400, "Пароль ≥6 символів")
        upd["password_hash"] = hash_password(payload.new_password)
    if not upd:
        raise HTTPException(400, "Нічого оновлювати")
    res = await db.users.find_one_and_update(
        {"id": uid}, {"$set": upd},
        return_document=True, projection={"_id": 0, "password_hash": 0, "totp_secret": 0})
    if not res:
        raise HTTPException(404, "Не знайдено")
    return res


@api_router.delete("/users/{uid}")
async def admin_delete_user(uid: str, user=Depends(commander_only)):
    target = await db.users.find_one({"id": uid}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Не знайдено")
    if target["username"] == "admin":
        raise HTTPException(400, "Системного admin видалити не можна")
    if target["id"] == user.id:
        raise HTTPException(400, "Не можна видалити власний акаунт")
    # Видаляємо лінковану картку якщо є
    if target.get("soldier_id"):
        sold = await db.soldiers.find_one({"id": target["soldier_id"]}, {"_id": 0})
        if sold:
            for fid in (sold.get("documents") or {}).values():
                p = DOCS_DIR / fid
                if p.exists():
                    try: p.unlink()
                    except Exception: pass
            await db.doc_files.delete_many({"soldier_id": target["soldier_id"]})
            await db.soldiers.delete_one({"id": target["soldier_id"]})
    await db.users.delete_one({"id": uid})
    return {"deleted": uid}


# ============================ STRUCTURE ROUTES ============================

@api_router.get("/structure")
async def get_structure(user=Depends(get_current_user)):
    return COMPANY


class StructureSubunitCreate(BaseModel):
    """Створити підрозділ (взвод/рота тощо)."""
    model_config = ConfigDict(extra="ignore")
    key: str          # унікальний ключ ("vzvod_3", "med_punkt" — латиницею)
    name: str
    type: str = "platoon"   # hq | platoon | squad | other
    count: int = 0


class StructureSquadCreate(BaseModel):
    """Створити відділення в межах існуючого підрозділу."""
    model_config = ConfigDict(extra="ignore")
    parent_key: str
    key: str
    name: str
    count: int = 0


class StructureRename(BaseModel):
    """Перейменувати підрозділ або відділення."""
    model_config = ConfigDict(extra="ignore")
    new_name: str


def _save_structure():
    """Записати поточний COMPANY у structure.json (атомарно)."""
    import tempfile, shutil
    target = ROOT_DIR / 'structure.json'
    tmp = target.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(COMPANY, f, ensure_ascii=False, indent=2)
    shutil.move(str(tmp), str(target))


@api_router.post("/structure/subunits")
async def create_subunit(payload: StructureSubunitCreate, user=Depends(commander_only)):
    """Додати новий підрозділ (взвод/штаб/тощо)."""
    if not payload.key or not payload.name:
        raise HTTPException(400, "key і name обов'язкові")
    if payload.key in COMPANY["subunits"]:
        raise HTTPException(400, f"Підрозділ з ключем '{payload.key}' уже існує")
    COMPANY["subunits"][payload.key] = {
        "name": payload.name,
        "type": payload.type,
        "count": payload.count,
        "squads": {"__DIRECT__": {"name": "", "positions": []}},
    }
    if payload.key not in COMPANY["order"]:
        COMPANY["order"].append(payload.key)
    _save_structure()
    return {"key": payload.key, "subunits_total": len(COMPANY["subunits"])}


@api_router.put("/structure/subunits/{key}")
async def rename_subunit(key: str, payload: StructureRename, user=Depends(commander_only)):
    """Перейменувати підрозділ. Оновлює node_path у всіх пов'язаних колекціях."""
    if key not in COMPANY["subunits"]:
        raise HTTPException(404, "Підрозділ не знайдено")
    old_name = COMPANY["subunits"][key]["name"]
    new_name = payload.new_name.strip()
    if not new_name:
        raise HTTPException(400, "Нова назва не може бути порожньою")
    if old_name == new_name:
        return {"updated": False}
    COMPANY["subunits"][key]["name"] = new_name
    _save_structure()
    # Каскадне оновлення node_path
    import re
    updated_total = 0
    for coll in ("soldiers", "equipment", "ammo"):
        cur = db[coll]
        async for d in cur.find({"node_path": {"$regex": f"^{re.escape(old_name)}(/.*)?$"}}, {"_id": 0, "id": 1, "node_path": 1}):
            new_path = re.sub(f"^{re.escape(old_name)}", new_name, d["node_path"])
            await cur.update_one({"id": d["id"]}, {"$set": {"node_path": new_path}})
            updated_total += 1
    return {"updated": True, "old_name": old_name, "new_name": new_name, "cascade_count": updated_total}


@api_router.delete("/structure/subunits/{key}")
async def delete_subunit(key: str, force: int = 0, user=Depends(commander_only)):
    """Видалити підрозділ. force=1 — навіть якщо є картки/засоби (вони не видаляються,
    лише втрачають структурний зв'язок). Без force — 400 якщо є залежності."""
    if key not in COMPANY["subunits"]:
        raise HTTPException(404, "Підрозділ не знайдено")
    name = COMPANY["subunits"][key]["name"]
    if not force:
        import re
        rx = f"^{re.escape(name)}(/.*)?$"
        cnt = await db.soldiers.count_documents({"node_path": {"$regex": rx}})
        eq = await db.equipment.count_documents({"node_path": {"$regex": rx}})
        ammo = await db.ammo.count_documents({"node_path": {"$regex": rx}})
        if cnt + eq + ammo > 0:
            raise HTTPException(
                400,
                f"Не можна видалити: пов'язано {cnt} карток, {eq} засобів, {ammo} БК. "
                f"Спершу перенесіть або видаліть, або викличте з ?force=1"
            )
    del COMPANY["subunits"][key]
    if key in COMPANY["order"]:
        COMPANY["order"].remove(key)
    _save_structure()
    return {"deleted": key, "name": name}


@api_router.post("/structure/squads")
async def create_squad(payload: StructureSquadCreate, user=Depends(commander_only)):
    """Додати відділення до існуючого підрозділу."""
    if payload.parent_key not in COMPANY["subunits"]:
        raise HTTPException(404, "Батьківський підрозділ не знайдено")
    sub = COMPANY["subunits"][payload.parent_key]
    squads = sub.setdefault("squads", {})
    if payload.key in squads:
        raise HTTPException(400, "Відділення з таким ключем уже існує")
    squads[payload.key] = {"name": payload.name, "count": payload.count, "positions": []}
    _save_structure()
    return {"parent_key": payload.parent_key, "key": payload.key, "name": payload.name}


@api_router.put("/structure/squads/{parent_key}/{key}")
async def rename_squad(parent_key: str, key: str, payload: StructureRename, user=Depends(commander_only)):
    """Перейменувати відділення."""
    if parent_key not in COMPANY["subunits"]:
        raise HTTPException(404, "Батьківський підрозділ не знайдено")
    squads = COMPANY["subunits"][parent_key].get("squads", {})
    if key not in squads:
        raise HTTPException(404, "Відділення не знайдено")
    parent_name = COMPANY["subunits"][parent_key]["name"]
    old_name = squads[key].get("name", "")
    new_name = payload.new_name.strip()
    if not new_name:
        raise HTTPException(400, "Нова назва не може бути порожньою")
    squads[key]["name"] = new_name
    _save_structure()
    # Каскадне оновлення node_path
    if old_name and old_name != new_name:
        old_full = f"{parent_name}/{old_name}"
        new_full = f"{parent_name}/{new_name}"
        import re
        for coll in ("soldiers", "equipment", "ammo"):
            await db[coll].update_many(
                {"node_path": old_full},
                {"$set": {"node_path": new_full}}
            )
    return {"updated": True, "key": key, "new_name": new_name}


@api_router.delete("/structure/squads/{parent_key}/{key}")
async def delete_squad(parent_key: str, key: str, force: int = 0, user=Depends(commander_only)):
    """Видалити відділення."""
    if parent_key not in COMPANY["subunits"]:
        raise HTTPException(404, "Батьківський підрозділ не знайдено")
    squads = COMPANY["subunits"][parent_key].get("squads", {})
    if key not in squads:
        raise HTTPException(404, "Відділення не знайдено")
    parent_name = COMPANY["subunits"][parent_key]["name"]
    sq_name = squads[key].get("name", "")
    if not force and sq_name:
        full = f"{parent_name}/{sq_name}"
        cnt = await db.soldiers.count_documents({"node_path": full})
        eq = await db.equipment.count_documents({"node_path": full})
        ammo = await db.ammo.count_documents({"node_path": full})
        if cnt + eq + ammo > 0:
            raise HTTPException(
                400,
                f"Не можна видалити: пов'язано {cnt} карток, {eq} засобів, {ammo} БК. ?force=1 щоб все одно"
            )
    del squads[key]
    _save_structure()
    return {"deleted": key, "name": sq_name}


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


# ============================ SOLDIERS / TRANSFERS / BCHS EXPORT ============================
# Перенесено у /app/backend/routes/soldiers.py та /app/backend/routes/transfers.py


# ============================ DOCUMENTS UPLOAD ============================

class DocumentStatusUpdate(BaseModel):
    """Payload для оновлення статусу документа. Whitelist полів."""
    model_config = ConfigDict(extra="forbid")
    status: Literal["draft", "signed", "executed"]
    status_at: Optional[str] = None
    doc_notes: Optional[str] = None


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
        "source": "uploaded",
        "status": "executed",
        "status_at": "",
        "doc_notes": "",
    }
    await db.doc_files.insert_one(meta)
    docs[doc_type] = file_id
    await db.soldiers.update_one({"id": sid},
                                 {"$set": {"documents": docs,
                                           "updated_at": meta["uploaded_at"]}})
    return {"file_id": file_id, "filename": meta["filename"]}


@api_router.get("/documents/{file_id}")
async def download_document(file_id: str, inline: int = 0, user=Depends(get_current_user)):
    meta = await db.doc_files.find_one({"id": file_id}, {"_id": 0})
    if not meta:
        raise HTTPException(404, "Файл не знайдено")
    p = DOCS_DIR / file_id
    if not p.exists():
        raise HTTPException(404, "Файл втрачено")
    fn = meta["filename"]
    disp = "inline" if inline else "attachment"
    headers = {"Content-Disposition": f"{disp}; filename=\"file\"; filename*=UTF-8''{_quote(fn)}"}
    return FileResponse(p, media_type=meta.get("mime", "application/octet-stream"),
                        filename=fn, headers=headers)


@api_router.put("/documents/{file_id}/status")
async def update_document_status(file_id: str, payload: DocumentStatusUpdate, user=Depends(can_edit)):
    """Зміна статусу документа: draft | signed | executed (+ дата + примітка)."""
    upd = {"status": payload.status}
    if payload.status_at is not None:
        upd["status_at"] = payload.status_at
    if payload.doc_notes is not None:
        upd["doc_notes"] = payload.doc_notes
    res = await db.doc_files.find_one_and_update(
        {"id": file_id}, {"$set": upd}, return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Файл не знайдено")
    return res


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
        "warehouse_categories": WAREHOUSE_CATEGORIES,
        "warehouse_txn_types": WAREHOUSE_TXN_TYPES,
        "company_name": COMPANY["name"],
    }


# ============================ SETTINGS (реквізити частини) ============================

class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    unit_full: str = ""        # повна назва частини
    unit_short: str = ""       # в/ч А____
    unit_chief: str = ""       # ПІБ командира частини
    unit_chief_rank: str = ""  # звання командира частини
    city: str = ""             # місто/н.п.
    company_name: str = ""
    company_chief: str = ""    # "командиру роти"


@api_router.get("/settings", response_model=Settings)
async def get_settings(user=Depends(get_current_user)):
    s = await db.settings.find_one({"_id": "main"}, {"_id": 0}) or {}
    if not s.get("company_name"):
        s["company_name"] = COMPANY["name"]
    if not s.get("company_chief"):
        s["company_chief"] = "командиру роти"
    return Settings(**s)


@api_router.put("/settings", response_model=Settings)
async def update_settings(payload: Settings, user=Depends(commander_only)):
    upd = payload.model_dump()
    await db.settings.update_one({"_id": "main"}, {"$set": upd}, upsert=True)
    return payload


# ============================ TEMPLATES (документи) ============================

@api_router.get("/templates")
async def get_templates(user=Depends(get_current_user)):
    return {"templates": list_templates()}


@api_router.get("/templates/{tid}/render")
async def render_template_endpoint(tid: str, soldier_id: Optional[str] = None,
                                   save_to_card: int = 1,
                                   user=Depends(get_current_user)):
    soldier = None
    if soldier_id:
        soldier = await db.soldiers.find_one({"id": soldier_id}, {"_id": 0})
    settings = await db.settings.find_one({"_id": "main"}, {"_id": 0}) or {}
    if not settings.get("company_name"):
        settings["company_name"] = COMPANY["name"]
    buf, fname = render_template(tid, soldier=soldier, settings=settings)
    if not buf:
        raise HTTPException(404, "Шаблон не знайдено")
    content = buf.getvalue()
    # Якщо обрано солдата і save_to_card=1 — зберігаємо у картку як "generated" документ
    if soldier_id and soldier and save_to_card:
        today = datetime.date.today().isoformat()
        # Dedupe: якщо для (soldier_id, template_id, date=сьогодні) уже є draft —
        # перезаписуємо його файл замість створення нового
        existing = await db.doc_files.find_one(
            {"soldier_id": soldier_id, "template_id": tid,
             "source": "generated", "status": "draft",
             "uploaded_at": {"$regex": f"^{today}"}},
            {"_id": 0}
        )
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if existing:
            # Перезаписуємо файл і оновлюємо мета
            file_id = existing["id"]
            storage_path = DOCS_DIR / file_id
            with open(storage_path, "wb") as f:
                f.write(content)
            await db.doc_files.update_one(
                {"id": file_id},
                {"$set": {
                    "filename": fname,
                    "size": len(content),
                    "uploaded_at": now_iso,
                    "uploaded_by": user.username,
                }}
            )
        else:
            file_id = str(uuid.uuid4())
            storage_path = DOCS_DIR / file_id
            with open(storage_path, "wb") as f:
                f.write(content)
            meta = {
                "id": file_id,
                "soldier_id": soldier_id,
                "type": "generated",
                "filename": fname,
                "size": len(content),
                "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "uploaded_at": now_iso,
                "uploaded_by": user.username,
                "source": "generated",
                "template_id": tid,
                "template_name": fname.replace(".docx", ""),
                "status": "draft",      # тільки що згенеровано
                "status_at": "",
                "doc_notes": "",
            }
            await db.doc_files.insert_one(meta)
    headers = {"Content-Disposition": f"attachment; filename=\"document.docx\"; filename*=UTF-8''{_quote(fname)}"}
    return FastAPIResponse(content=content,
                           media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           headers=headers)


# ============================ WAREHOUSE / BACKUP ============================
# Перенесено у /app/backend/routes/warehouse.py та /app/backend/routes/backup.py


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
        await db.transfers.create_index("soldier_id")
        await db.backup_jobs.create_index("created_at")
        await db.doc_files.create_index([("soldier_id", 1), ("template_id", 1), ("status", 1)])
        await ensure_audit_indexes()
    except Exception:
        pass
    # Auto-backup щодня о 02:00 UTC
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        sched = AsyncIOScheduler()
        sched.add_job(make_backup, CronTrigger(hour=2, minute=0), id="daily_backup",
                      replace_existing=True, misfire_grace_time=3600)
        sched.start()
        app.state.scheduler = sched
        logging.info("Backup scheduler started: daily at 02:00 UTC")
    except Exception as e:
        logging.warning(f"Could not start backup scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ============================ FINAL ============================

# Підключаємо роутери з routes/ — кожен має префікс /api/...
from routes.soldiers import router as soldiers_router
from routes.transfers import router as transfers_router
from routes.backup import router as backup_router
from routes.warehouse import router as warehouse_router

api_router.include_router(soldiers_router)
api_router.include_router(transfers_router)
api_router.include_router(backup_router)
api_router.include_router(warehouse_router)

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
