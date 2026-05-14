"""Audit log: запис усіх mutating дій (POST/PUT/DELETE).

Зберігаємо у db.audit_log з TTL 90 днів (через MongoDB TTL index на created_at_ts).
"""
import datetime
import json
import uuid
import logging
from typing import Optional

from deps import db, now_iso

# Шляхи, які НЕ логуємо (надто шумні / нечутливі)
SKIP_PATHS = {
    "/api/auth/login",       # окремий лог
    "/api/auth/2fa/verify",
}
SKIP_PATH_PREFIXES = (
    "/api/auth/me",
    "/api/admin/backup/job/",   # polling — шумно
)


def _categorize(path: str) -> str:
    """Категорія ресурсу за path-ом."""
    p = path.lower()
    if "/soldiers" in p: return "soldiers"
    if "/transfers" in p: return "transfers"
    if "/documents" in p or "/templates" in p: return "documents"
    if "/warehouse" in p: return "warehouse"
    if "/ammo" in p: return "ammo"
    if "/equipment" in p: return "equipment"
    if "/users" in p: return "users"
    if "/admin/backup" in p: return "backup"
    if "/settings" in p: return "settings"
    if "/interactions" in p: return "interactions"
    return "other"


def _summarize_target(method: str, path: str, status: int, body_repr: str) -> str:
    """Стисле повідомлення для відображення в UI."""
    action = {"POST": "створено", "PUT": "оновлено", "DELETE": "видалено", "PATCH": "оновлено"}.get(method, method)
    cat = _categorize(path)
    return f"{action} {cat} • {method} {path}"


async def log_audit(*,
                    user: Optional[object],
                    method: str,
                    path: str,
                    status_code: int,
                    body_snippet: str = "",
                    ip: str = "",
                    extra: Optional[dict] = None):
    """Записати подію в audit_log. Викликається з middleware."""
    try:
        entry = {
            "id": str(uuid.uuid4()),
            "created_at": now_iso(),
            "created_at_ts": datetime.datetime.now(datetime.timezone.utc),  # для TTL index
            "username": (getattr(user, "username", None) or "anon") if user else "anon",
            "user_id": getattr(user, "id", "") if user else "",
            "user_role": getattr(user, "role", "") if user else "",
            "user_platoon": getattr(user, "platoon", "") if user else "",
            "method": method,
            "path": path,
            "status_code": status_code,
            "category": _categorize(path),
            "summary": _summarize_target(method, path, status_code, body_snippet),
            "body_snippet": (body_snippet or "")[:500],
            "ip": ip,
            "success": 200 <= status_code < 400,
        }
        if extra:
            entry["extra"] = extra
        await db.audit_log.insert_one(entry)
    except Exception:
        logging.exception("Failed to write audit log")


def should_log(method: str, path: str) -> bool:
    """Чи логувати цей запит?"""
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return False
    if path in SKIP_PATHS:
        return False
    for pref in SKIP_PATH_PREFIXES:
        if path.startswith(pref):
            return False
    return True


async def ensure_indexes():
    """TTL index на created_at_ts: 90 днів зберігання."""
    try:
        await db.audit_log.create_index(
            "created_at_ts", expireAfterSeconds=90 * 24 * 3600
        )
        await db.audit_log.create_index([("category", 1), ("created_at", -1)])
        await db.audit_log.create_index([("username", 1), ("created_at", -1)])
    except Exception:
        logging.exception("audit_log: cannot create indexes")
