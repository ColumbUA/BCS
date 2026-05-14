"""Soldiers CRUD + BCHS export + seed-from-bchs."""
import io
import uuid
import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response as FastAPIResponse
from pydantic import BaseModel, Field, ConfigDict

from auth import get_current_user, commander_only, can_edit
from deps import db, COMPANY, _quote, _delete_file, now_iso
from pdf_card import render_soldier_pdf

router = APIRouter()


# ============================ MODELS ============================

class EducationItem(BaseModel):
    degree: str = ""
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
    node_path: str = ""
    position: str = ""
    rank: str = ""
    birth_date: str = ""
    mobilized_at: str = ""
    bzvp_passed_at: str = ""
    ktz_passed_at: str = ""
    education: List[EducationItem] = []
    certificates: List[Certificate] = []
    blood_group: str = ""
    has_driver_license: bool = False
    location_status: str = "ППД"
    location_place: str = ""
    location_updated_at: str = ""
    notes: str = ""


class Soldier(SoldierBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    documents: dict = {}
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = ""


# ============================ HELPERS ============================

def _is_in_scope(user, node_path: str) -> bool:
    """Чи бачить користувач картку з даним node_path?

    COMMANDER / MATERIAL — бачать усе.
    PLATOON_LEADER — лише свій взвод (user.platoon префіксом).
    VIEWER — бачить усе (read-only).
    """
    role = getattr(user, "role", "")
    if role in ("COMMANDER", "MATERIAL", "VIEWER"):
        return True
    if role == "PLATOON_LEADER":
        platoon = (getattr(user, "platoon", "") or "").strip()
        if not platoon:
            return False
        # Префіксна перевірка: "1 Взвод радіорозвідки/1 Відділення" ⊂ "1 Взвод радіорозвідки"
        return (node_path or "").startswith(platoon)
    return False


def _scope_filter(user) -> dict:
    """MongoDB-фільтр на основі ролі для запитів soldiers/equipment/ammo."""
    role = getattr(user, "role", "")
    if role in ("COMMANDER", "MATERIAL", "VIEWER"):
        return {}
    if role == "PLATOON_LEADER":
        platoon = (getattr(user, "platoon", "") or "").strip()
        if not platoon:
            return {"id": "__none__"}   # нічого не повертати
        # Regex-anchor: починається з взводу
        import re
        return {"node_path": {"$regex": f"^{re.escape(platoon)}(/.*)?$"}}
    return {"id": "__none__"}


# ============================ SOLDIERS CRUD ============================

@router.get("/soldiers", response_model=List[Soldier])
async def list_soldiers(user=Depends(get_current_user)):
    q = _scope_filter(user)
    return await db.soldiers.find(q, {"_id": 0}).to_list(500)


@router.get("/soldiers/{sid}", response_model=Soldier)
async def get_soldier(sid: str, user=Depends(get_current_user)):
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Картку не знайдено")
    if not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу до цієї картки")
    return s


@router.post("/soldiers", response_model=Soldier)
async def create_soldier(payload: SoldierBase, user=Depends(can_edit)):
    if not _is_in_scope(user, payload.node_path):
        raise HTTPException(403, "Створення картки в чужому підрозділі заборонено")
    item = Soldier(**payload.model_dump())
    item.updated_at = item.created_at
    await db.soldiers.insert_one(item.model_dump())
    return item


@router.put("/soldiers/{sid}", response_model=Soldier)
async def update_soldier(sid: str, payload: SoldierBase, user=Depends(can_edit)):
    existing = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Картку не знайдено")
    if not _is_in_scope(user, existing.get("node_path", "")):
        raise HTTPException(403, "Немає доступу до цієї картки")
    # Заборонити PLATOON_LEADER зміну node_path на чужий взвод напряму (для переміщень існує /transfers)
    if not _is_in_scope(user, payload.node_path):
        raise HTTPException(403, "Зміна підрозділу через PUT заборонена; використайте /transfers")
    upd = payload.model_dump()
    upd["updated_at"] = now_iso()
    res = await db.soldiers.find_one_and_update({"id": sid}, {"$set": upd},
                                                return_document=True, projection={"_id": 0})
    return res


@router.delete("/soldiers/{sid}")
async def delete_soldier(sid: str, user=Depends(commander_only)):
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if s:
        for fid in (s.get("documents") or {}).values():
            await _delete_file(fid)
    await db.soldiers.delete_one({"id": sid})
    return {"deleted": sid}


@router.post("/soldiers/seed-from-bchs")
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


# ============================ RISK HEAT-MAP ============================

REQUIRED_DOC_TYPES_LOCAL = ("passport", "ipn", "military_id")
TRAINING_WARN_DAYS = 365   # БЗВП/КТЗ протерміновано якщо > 1 рік
TRANSFER_OVERDUE_DAYS = 14   # переміщення submitted/approved > 14 днів


def _risk_for_soldier(s: dict, active_transfers: dict) -> dict:
    """Обчислити рівень ризику для одного солдата.

    Args:
      s: документ солдата
      active_transfers: {soldier_id: oldest_active_transfer_dict}

    Returns:
      {risk: 'red'|'yellow'|'green', reasons: [code, ...], labels: [{code, label, severity}]}
    """
    today = datetime.date.today()
    reasons = []
    labels = []

    # 🔴 Червоні: відсутні критичні документи
    docs = s.get("documents") or {}
    missing_docs = [d for d in REQUIRED_DOC_TYPES_LOCAL if d not in docs]
    if missing_docs:
        reasons.append("docs_missing")
        labels.append({"code": "docs_missing", "severity": "red",
                       "label": f"Відсутні документи: {', '.join(missing_docs)}"})

    # 🔴 Червоний: СЗЧ
    if s.get("location_status") == "СЗЧ":
        reasons.append("szch")
        labels.append({"code": "szch", "severity": "red", "label": "Самовільне залишення частини"})

    # 🔴 Червоний: активне переміщення прострочене >14 днів
    t = active_transfers.get(s["id"])
    if t:
        try:
            created = datetime.datetime.fromisoformat(t.get("created_at", "").replace("Z", "+00:00"))
            age_days = (datetime.datetime.now(datetime.timezone.utc) - created).days
            if age_days > TRANSFER_OVERDUE_DAYS:
                reasons.append("transfer_overdue")
                labels.append({"code": "transfer_overdue", "severity": "red",
                               "label": f"Переміщення прострочено: {age_days} дн."})
        except Exception:
            pass

    # 🟡 Жовтий: БЗВП не пройдено або прострочено
    bzvp = s.get("bzvp_passed_at", "")
    if not bzvp:
        reasons.append("bzvp_missing")
        labels.append({"code": "bzvp_missing", "severity": "yellow", "label": "БЗВП не пройдено"})
    else:
        try:
            d = datetime.date.fromisoformat(bzvp)
            if (today - d).days > TRAINING_WARN_DAYS:
                reasons.append("bzvp_expired")
                labels.append({"code": "bzvp_expired", "severity": "yellow",
                               "label": f"БЗВП >12 міс ({(today - d).days // 30} міс)"})
        except Exception:
            pass

    # 🟡 Жовтий: КТЗ не пройдено / прострочено
    ktz = s.get("ktz_passed_at", "")
    if not ktz:
        reasons.append("ktz_missing")
        labels.append({"code": "ktz_missing", "severity": "yellow", "label": "КТЗ не пройдено"})
    else:
        try:
            d = datetime.date.fromisoformat(ktz)
            if (today - d).days > TRAINING_WARN_DAYS:
                reasons.append("ktz_expired")
                labels.append({"code": "ktz_expired", "severity": "yellow",
                               "label": f"КТЗ >12 міс ({(today - d).days // 30} міс)"})
        except Exception:
            pass

    # 🟡 Жовтий: лікарня / ВЛК
    if s.get("location_status") in ("Лікарня", "ВЛК"):
        reasons.append("medical")
        labels.append({"code": "medical", "severity": "yellow",
                       "label": f"Поза ППД: {s.get('location_status')}"})

    # Підсумок рівня ризику
    if any(l["severity"] == "red" for l in labels):
        risk = "red"
    elif any(l["severity"] == "yellow" for l in labels):
        risk = "yellow"
    else:
        risk = "green"

    return {"risk": risk, "reasons": reasons, "labels": labels}


@router.get("/risk-heatmap")
async def get_risk_heatmap(user=Depends(get_current_user)):
    """Heat-map ризиків особового складу.

    Повертає:
      {
        totals: {red, yellow, green, total, ratio_red, ratio_yellow},
        by_subunit: { node_path: {red, yellow, green, total} },
        soldiers: [{id, fio, callsign, node_path, position, risk, labels}],
        generated_at: ISO,
      }
    """
    q = _scope_filter(user)
    soldiers_list = await db.soldiers.find(q, {"_id": 0}).to_list(1000)
    sid_set = {s["id"] for s in soldiers_list}

    # Активні переміщення (submitted/approved) — по oldest на солдата
    active = {}
    if sid_set:
        async for t in db.transfers.find(
            {"soldier_id": {"$in": list(sid_set)}, "status": {"$in": ["submitted", "approved"]}},
            {"_id": 0}
        ).sort("created_at", 1):
            if t["soldier_id"] not in active:
                active[t["soldier_id"]] = t

    by_subunit = {}
    out = []
    totals = {"red": 0, "yellow": 0, "green": 0, "total": 0}

    for s in soldiers_list:
        r = _risk_for_soldier(s, active)
        totals[r["risk"]] += 1
        totals["total"] += 1
        np = s.get("node_path", "—")
        if np not in by_subunit:
            by_subunit[np] = {"red": 0, "yellow": 0, "green": 0, "total": 0}
        by_subunit[np][r["risk"]] += 1
        by_subunit[np]["total"] += 1
        out.append({
            "id": s["id"], "fio": s.get("fio", ""),
            "callsign": s.get("callsign", ""),
            "rank": s.get("rank", ""),
            "position": s.get("position", ""),
            "node_path": np,
            "location_status": s.get("location_status", ""),
            "risk": r["risk"],
            "labels": r["labels"],
        })

    totals["ratio_red"] = (totals["red"] / totals["total"] * 100) if totals["total"] else 0
    totals["ratio_yellow"] = (totals["yellow"] / totals["total"] * 100) if totals["total"] else 0
    totals["ratio_green"] = (totals["green"] / totals["total"] * 100) if totals["total"] else 0

    # Сортуємо солдатів: спочатку червоні, потім жовті
    out.sort(key=lambda x: (0 if x["risk"] == "red" else 1 if x["risk"] == "yellow" else 2, x["node_path"], x["fio"]))

    return {
        "totals": totals,
        "by_subunit": by_subunit,
        "soldiers": out,
        "generated_at": now_iso(),
    }


# ============================ BCHS EXPORT ============================

@router.get("/export/bchs.csv")
async def export_soldiers_csv(user=Depends(get_current_user)):
    import csv as _csv
    soldiers = await db.soldiers.find(_scope_filter(user), {"_id": 0}).to_list(500)
    buf = io.StringIO()
    writer = _csv.writer(buf, delimiter=";", quoting=_csv.QUOTE_MINIMAL,
                         lineterminator="\n")
    writer.writerow(["ПІБ", "Позивний", "Звання", "Посада", "Підрозділ",
                     "Дата народж.", "Дата моб.", "БЗВП", "КТЗ", "Гр.крові",
                     "ВП", "Стан", "Місце", "Документів", "Примітки"])
    for s in soldiers:
        docs = s.get("documents") or {}
        writer.writerow([
            s.get("fio", ""), s.get("callsign", ""), s.get("rank", ""),
            s.get("position", ""), s.get("node_path", ""),
            s.get("birth_date", ""), s.get("mobilized_at", ""),
            s.get("bzvp_passed_at", ""), s.get("ktz_passed_at", ""),
            s.get("blood_group", ""),
            "так" if s.get("has_driver_license") else "ні",
            s.get("location_status", ""), s.get("location_place", ""),
            str(len(docs)), s.get("notes", ""),
        ])
    csv_text = buf.getvalue()
    fn = f"БЧС - {COMPANY['name']} - {datetime.date.today().strftime('%Y-%m-%d')}.csv"
    headers = {"Content-Disposition": f"attachment; filename=\"bchs.csv\"; filename*=UTF-8''{_quote(fn)}"}
    return FastAPIResponse(content="\ufeff" + csv_text, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/export/bchs.xlsx")
async def export_soldiers_xlsx(user=Depends(get_current_user)):
    import openpyxl
    soldiers = await db.soldiers.find(_scope_filter(user), {"_id": 0}).to_list(500)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "БЧС"
    ws.append(["№", "ПІБ", "Позивний", "Звання", "Посада", "Підрозділ",
               "Дата народж.", "Дата моб.", "БЗВП", "КТЗ", "Гр.крові", "ВП",
               "Стан", "Місце", "Документів", "Примітки"])
    for i, s in enumerate(soldiers, 1):
        docs = s.get("documents") or {}
        ws.append([
            i, s.get("fio", ""), s.get("callsign", ""), s.get("rank", ""),
            s.get("position", ""), s.get("node_path", ""),
            s.get("birth_date", ""), s.get("mobilized_at", ""),
            s.get("bzvp_passed_at", ""), s.get("ktz_passed_at", ""),
            s.get("blood_group", ""),
            "так" if s.get("has_driver_license") else "ні",
            s.get("location_status", ""), s.get("location_place", ""),
            len(docs), s.get("notes", "")
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fn = f"БЧС - {COMPANY['name']} - {datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename=\"bchs.xlsx\"; filename*=UTF-8''{_quote(fn)}"}
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers=headers)


# ============================ PDF EXPORT (особова картка) ============================

@router.get("/soldiers/{sid}/export.pdf")
async def export_soldier_pdf(sid: str, user=Depends(get_current_user)):
    """Експорт особової картки солдата у PDF (1-2 сторінкова)."""
    s = await db.soldiers.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Картку не знайдено")
    if not _is_in_scope(user, s.get("node_path", "")):
        raise HTTPException(403, "Немає доступу до цієї картки")
    transfers = await db.transfers.find({"soldier_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(50)
    documents = await db.doc_files.find({"soldier_id": sid}, {"_id": 0}).to_list(100)
    settings = await db.settings.find_one({"_id": "main"}, {"_id": 0}) or {}
    buf, fname = render_soldier_pdf(
        soldier=s, settings=settings, company_name=COMPANY.get("name", ""),
        transfers=transfers, documents=documents,
    )
    headers = {
        "Content-Disposition": f"attachment; filename=\"soldier-card.pdf\"; filename*=UTF-8''{_quote(fname)}"
    }
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)
