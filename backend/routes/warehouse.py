"""Warehouse (склад): items + transactions."""
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict

from auth import get_current_user, commander_only, can_edit
from deps import db, now_iso

router = APIRouter(prefix="/warehouse")


# ============================ MODELS ============================

class WarehouseItemBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    category: str = "Майно (речове)"
    unit: str = "шт"
    serial: str = ""
    notes: str = ""
    min_balance: int = 0


class WarehouseItem(WarehouseItemBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=now_iso)


class WarehouseTxnBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_id: str
    type: Literal["IN", "OUT", "WRITEOFF"]
    qty: int
    date: str = ""
    counterparty: str = ""
    doc_ref: str = ""
    reason: str = ""
    notes: str = ""


class WarehouseTxn(WarehouseTxnBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=now_iso)
    created_by: str = ""


# ============================ ITEMS ============================

@router.get("/items")
async def list_warehouse(user=Depends(get_current_user)):
    items = await db.warehouse_items.find({}, {"_id": 0}).to_list(2000)
    txns = await db.warehouse_txns.find({}, {"_id": 0}).to_list(50000)
    bal = {}
    for t in txns:
        delta = t["qty"] if t["type"] == "IN" else -t["qty"]
        bal[t["item_id"]] = bal.get(t["item_id"], 0) + delta
    for it in items:
        it["balance"] = bal.get(it["id"], 0)
        it["below_min"] = it["balance"] < (it.get("min_balance") or 0) if (it.get("min_balance") or 0) > 0 else False
    return items


@router.post("/items", response_model=WarehouseItem)
async def create_warehouse_item(payload: WarehouseItemBase, user=Depends(can_edit)):
    item = WarehouseItem(**payload.model_dump())
    await db.warehouse_items.insert_one(item.model_dump())
    return item


@router.put("/items/{iid}", response_model=WarehouseItem)
async def update_warehouse_item(iid: str, payload: WarehouseItemBase, user=Depends(can_edit)):
    res = await db.warehouse_items.find_one_and_update(
        {"id": iid}, {"$set": payload.model_dump()},
        return_document=True, projection={"_id": 0})
    if not res:
        raise HTTPException(404, "Не знайдено")
    return res


@router.delete("/items/{iid}")
async def delete_warehouse_item(iid: str, user=Depends(commander_only)):
    existing = await db.warehouse_items.find_one({"id": iid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Не знайдено")
    await db.warehouse_txns.delete_many({"item_id": iid})
    await db.warehouse_items.delete_one({"id": iid})
    return {"deleted": iid}


@router.get("/items/{iid}/txns")
async def get_item_txns(iid: str, user=Depends(get_current_user)):
    txns = await db.warehouse_txns.find({"item_id": iid}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return txns


# ============================ TXNS ============================

@router.post("/txns", response_model=WarehouseTxn)
async def create_txn(payload: WarehouseTxnBase, user=Depends(can_edit)):
    item = await db.warehouse_items.find_one({"id": payload.item_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Позицію не знайдено")
    if payload.qty <= 0:
        raise HTTPException(400, "Кількість має бути > 0")
    if payload.type in ("OUT", "WRITEOFF"):
        txns = await db.warehouse_txns.find({"item_id": payload.item_id}, {"_id": 0}).to_list(10000)
        bal = sum((t["qty"] if t["type"] == "IN" else -t["qty"]) for t in txns)
        if payload.qty > bal:
            raise HTTPException(400, f"Недостатньо на залишку. Залишок: {bal} {item['unit']}")
    txn = WarehouseTxn(**payload.model_dump(), created_by=user.username)
    await db.warehouse_txns.insert_one(txn.model_dump())
    return txn


@router.delete("/txns/{tid}")
async def delete_txn(tid: str, user=Depends(commander_only)):
    res = await db.warehouse_txns.delete_one({"id": tid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Не знайдено")
    return {"deleted": tid}


@router.get("/summary")
async def warehouse_summary(user=Depends(get_current_user)):
    items = await db.warehouse_items.find({}, {"_id": 0}).to_list(2000)
    txns = await db.warehouse_txns.find({}, {"_id": 0}).to_list(50000)
    bal = {}
    for t in txns:
        delta = t["qty"] if t["type"] == "IN" else -t["qty"]
        bal[t["item_id"]] = bal.get(t["item_id"], 0) + delta
    by_cat = {}
    total = 0
    for it in items:
        b = bal.get(it["id"], 0)
        c = it.get("category", "Інше")
        by_cat[c] = by_cat.get(c, 0) + b
        total += b
    return {"total_items": len(items), "total_qty": total, "by_category": by_cat,
            "txns_total": len(txns)}
