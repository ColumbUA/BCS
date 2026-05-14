"""Спільні залежності для всіх route-модулів.

Тут зосереджені:
  - db (motor client)
  - COMPANY (з structure.json)
  - DOCS_DIR
  - Константи (LOCATION_STATUSES, TRANSFER_TYPES, DOC_STATUSES, EQUIPMENT_*, ...)
  - Helpers (_quote, _company_node_paths, _delete_file)
"""
import os
import json
import datetime
from pathlib import Path
from urllib.parse import quote as _quote
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
REQUIRED_DOC_TYPES = ["passport", "ipn", "military_id"]
DRIVER_REQUIRED = ["passport", "ipn", "military_id", "driver_license"]

LOCATION_STATUSES = [
    "ППД", "РЗ", "РВ",
    "Відрядження", "Відпустка", "Лікарня",
    "СЗЧ", "ВЛК", "Інше",
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

WAREHOUSE_CATEGORIES = ["ОВТ", "БК", "Засіб зв'язку", "Транспорт", "ПММ", "Майно (речове)",
                       "Інженерне", "Медичне", "Продовольче", "Інше"]
WAREHOUSE_TXN_TYPES = ["IN", "OUT", "WRITEOFF"]
TXN_LABELS = {"IN": "Прихід", "OUT": "Видача", "WRITEOFF": "Списання"}


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


async def _delete_file(file_id: str):
    """Видалити файл документа з диску та БД."""
    p = DOCS_DIR / file_id
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass
    await db.doc_files.delete_one({"id": file_id})


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
