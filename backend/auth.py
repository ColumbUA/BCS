"""Аутентифікація: JWT + bcrypt + TOTP (Google Authenticator).

Ролі:
  - COMMANDER       — командир роти, повний доступ
  - PLATOON_LEADER  — командир взводу, обмежений (свій взвод)
  - MATERIAL        — матеріаліст, документи + сповіщення
  - VIEWER          — перегляд (read-only)
"""
import os, io, base64, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Literal

import bcrypt
import jwt as pyjwt
import pyotp
import qrcode
from fastapi import HTTPException, Request, Depends
from pydantic import BaseModel, ConfigDict, Field

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production-" + secrets.token_hex(16))
JWT_EXP_HOURS = 8

ROLES = ("COMMANDER", "PLATOON_LEADER", "MATERIAL", "VIEWER")


class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    username: str
    name: str = ""
    role: Literal["COMMANDER", "PLATOON_LEADER", "MATERIAL", "VIEWER"] = "VIEWER"
    platoon: str = ""        # для PLATOON_LEADER — назва взводу
    totp_enabled: bool = False


class UserCreate(UserBase):
    password: str


class UserPublic(UserBase):
    id: str
    created_at: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
        "type": "access",
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise pyjwt.InvalidTokenError("not access token")
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Сесія прострочена. Увійдіть знову.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Невалідний токен")


def gen_totp_secret() -> str:
    return pyotp.random_base32()


def gen_totp_qr(username: str, secret: str, issuer: str = "Рота РРР") -> str:
    """Повертає data URI PNG QR-коду для Google Authenticator."""
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ============================ FastAPI dependencies ============================

class CurrentUser(BaseModel):
    id: str
    username: str
    name: str = ""
    role: str
    platoon: str = ""


async def get_current_user(request: Request) -> CurrentUser:
    """Витягує токен з Authorization Bearer header або cookie."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif request.cookies.get("access_token"):
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизовано")
    payload = decode_token(token)
    # Підтягуємо актуальні дані з БД
    db = request.app.state.db
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0, "totp_secret": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Користувача не знайдено")
    return CurrentUser(**user)


def require_role(*allowed_roles: str):
    """Залежність, що пропускає тільки користувачів з визначеними ролями."""
    async def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403,
                                detail=f"Доступ заборонено. Потрібна роль: {' / '.join(allowed_roles)}")
        return user
    return dep


# Зручні залежності
async def commander_only(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "COMMANDER":
        raise HTTPException(status_code=403, detail="Лише командир роти")
    return user


async def can_edit(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("COMMANDER", "PLATOON_LEADER", "MATERIAL"):
        raise HTTPException(status_code=403, detail="Перегляд тільки. Звернітіться до командира.")
    return user


# ============================ Brute-force protection ============================

LOCK_THRESHOLD = 5
LOCK_MINUTES = 15


async def is_locked(db, identifier: str) -> bool:
    rec = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if not rec:
        return False
    if rec.get("count", 0) >= LOCK_THRESHOLD:
        last = rec.get("last_at")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.now(timezone.utc) - last_dt < timedelta(minutes=LOCK_MINUTES):
                    return True
                else:
                    # розблокувати
                    await db.login_attempts.delete_one({"identifier": identifier})
            except Exception:
                pass
    return False


async def record_failed(db, identifier: str):
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1},
         "$set": {"last_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )


async def clear_attempts(db, identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})


# ============================ Seed default admin ============================

DEFAULT_USERS = [
    # username, password, name, role, platoon
    ("admin",      "rota2026",   "Адміністратор",       "COMMANDER",      ""),
    ("kr",         "kolumb2026", "Командир роти КОЛУМБ", "COMMANDER",      ""),
    ("material",   "venom2026",  "ОРЛОВ Борис Борисович «ВЕНОМ» (матеріаліст)", "MATERIAL", ""),
    ("kv1",        "platoon1",   "КВ 1 Взводу РР",       "PLATOON_LEADER", "1 Взвод радіорозвідки"),
    ("kv2",        "platoon2",   "КВ 2 Взводу РР",       "PLATOON_LEADER", "2 Взвод радіорозвідки"),
    ("viewer",     "view2026",   "Перегляд",             "VIEWER",         ""),
]


async def seed_users(db):
    """Створює користувачів за замовчуванням, якщо їх немає."""
    import uuid
    for username, password, name, role, platoon in DEFAULT_USERS:
        existing = await db.users.find_one({"username": username})
        if not existing:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "username": username,
                "password_hash": hash_password(password),
                "name": name,
                "role": role,
                "platoon": platoon,
                "totp_secret": "",
                "totp_enabled": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    # Гарантуємо унікальність
    try:
        await db.users.create_index("username", unique=True)
    except Exception:
        pass
