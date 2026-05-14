"""Transfers (переміщення солдатів)."""
import uuid
from typing import List, Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict

from auth import get_current_user, commander_only, can_edit
from deps import db, TRANSFER_TYPES, _company_node_paths, now_iso
from routes.soldiers import _is_in_scope

router = APIRouter()


class TransferBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    soldier_id: str
    transfer_type: str = "in-rota"
    from_node_path: str = ""
    to_node_path: str = ""
    new_position: str = ""
    reason: str = ""
    effective_date: str = ""
    order_number: str = ""
    status: Literal["draft", "submitted", "approved", "executed", "rejected"] = "draft"
    notes: str = ""


class Transfer(TransferBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    soldier_fio: str = ""
    document_ids: List[str] = []
    created_at: str = Field(default_factory=now_iso)
    created_by: str = ""
    executed_at: str = ""


# ============================ ENDPOINTS ============================

@router.get("/soldiers/{sid}/transfers", response_model=List[Transfer])
async def list_soldier_transfers(sid: str, user=Depends(get_current_user)):
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0, "node_path": 1})
    if not s:
        raise HTTPException(404, "Картку не знайдено")
    if not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу")
    return await db.transfers.find({"soldier_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/transfers", response_model=List[Transfer])
async def list_all_transfers(user=Depends(get_current_user)):
    # PLATOON_LEADER бачить лише транзит-и зі свого взводу (з/до)
    role = getattr(user, "role", "")
    if role == "PLATOON_LEADER":
        platoon = (getattr(user, "platoon", "") or "").strip()
        if not platoon:
            return []
        import re
        rx = f"^{re.escape(platoon)}(/.*)?$"
        q = {"$or": [
            {"from_node_path": {"$regex": rx}},
            {"to_node_path": {"$regex": rx}},
        ]}
        return await db.transfers.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return await db.transfers.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("/transfers", response_model=Transfer)
async def create_transfer(payload: TransferBase, user=Depends(can_edit)):
    s = await db.soldiers.find_one({"id": payload.soldier_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Картку не знайдено")
    # Перевірка типу переміщення
    if payload.transfer_type not in TRANSFER_TYPES:
        raise HTTPException(400, f"Невідомий тип переміщення. Допустимі: {list(TRANSFER_TYPES.keys())}")
    # PLATOON_LEADER: солдат має бути з його взводу (вихідне переміщення)
    if not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу до картки солдата")
    # Для in-rota: to_node_path і from_node_path мають належати структурі роти
    if payload.transfer_type == "in-rota":
        valid_paths = _company_node_paths()
        if payload.to_node_path and payload.to_node_path not in valid_paths:
            raise HTTPException(
                400,
                f"Невірний підрозділ призначення '{payload.to_node_path}'. "
                f"Допустимі: {sorted(valid_paths)}"
            )
        if payload.from_node_path and payload.from_node_path not in valid_paths:
            raise HTTPException(
                400,
                f"Невірний підрозділ відправлення '{payload.from_node_path}'. "
                f"Допустимі: {sorted(valid_paths)}"
            )
    data = payload.model_dump()
    if not data.get("from_node_path"):
        data["from_node_path"] = s.get("node_path", "")
    t = Transfer(**data,
                 soldier_fio=s["fio"],
                 created_by=user.username)
    await db.transfers.insert_one(t.model_dump())
    return t


@router.put("/transfers/{tid}", response_model=Transfer)
async def update_transfer(tid: str, payload: TransferBase, user=Depends(can_edit)):
    existing = await db.transfers.find_one({"id": tid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Не знайдено")
    s = await db.soldiers.find_one({"id": existing["soldier_id"]}, {"_id": 0, "node_path": 1})
    if s and not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу")
    res = await db.transfers.find_one_and_update(
        {"id": tid}, {"$set": payload.model_dump()},
        return_document=True, projection={"_id": 0})
    return res


@router.post("/transfers/{tid}/execute")
async def execute_transfer(tid: str, user=Depends(can_edit)):
    t = await db.transfers.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Не знайдено")
    if t["status"] == "executed":
        raise HTTPException(400, "Вже виконано")
    s = await db.soldiers.find_one({"id": t["soldier_id"]}, {"_id": 0})
    if s and not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу до картки солдата")
    upd = {"updated_at": now_iso()}
    if t["transfer_type"] == "in-rota" and t.get("to_node_path"):
        valid_paths = _company_node_paths()
        if t["to_node_path"] not in valid_paths:
            raise HTTPException(
                400,
                f"Підрозділ призначення '{t['to_node_path']}' не існує у поточній структурі роти"
            )
        upd["node_path"] = t["to_node_path"]
        if t.get("new_position"):
            upd["position"] = t["new_position"]
        upd["location_status"] = "ППД"
        upd["location_place"] = ""
        upd["location_updated_at"] = upd["updated_at"]
    elif t["transfer_type"] in ("in-bat", "in-polk", "in-brigade", "in-zsu", "discharge", "deceased", "missing"):
        cur_notes = (s or {}).get("notes", "") or ""
        new_note = f"[{t.get('effective_date') or 'без дати'}] {TRANSFER_TYPES.get(t['transfer_type'], t['transfer_type'])}: {t.get('to_node_path','')}"
        upd["notes"] = (cur_notes + "\n" + new_note).strip()
        upd["location_status"] = "Інше"
        upd["location_place"] = t.get("to_node_path", "")
        upd["location_updated_at"] = upd["updated_at"]
    await db.soldiers.update_one({"id": t["soldier_id"]}, {"$set": upd})
    now = now_iso()
    await db.transfers.update_one({"id": tid}, {"$set": {"status": "executed", "executed_at": now}})
    return {"executed": tid}


@router.delete("/transfers/{tid}")
async def delete_transfer(tid: str, user=Depends(commander_only)):
    res = await db.transfers.delete_one({"id": tid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Не знайдено")
    return {"deleted": tid}
