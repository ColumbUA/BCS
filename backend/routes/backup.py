"""Backup (admin-only, фонові задачі)."""
import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from auth import commander_only
from deps import db, now_iso
from backup_mod import make_backup, list_backups, delete_backup, BACKUP_DIR

router = APIRouter(prefix="/admin/backup")


async def _run_backup_job(job_id: str):
    """Виконується у фоні. Записує статус у db.backup_jobs."""
    started = now_iso()
    await db.backup_jobs.update_one(
        {"id": job_id},
        {"$set": {"status": "running", "started_at": started}}
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, make_backup)
        finished = now_iso()
        await db.backup_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "done",
                "finished_at": finished,
                "result": result,
                "fallback": result.get("fallback", False),
                "error": "",
            }}
        )
    except Exception as e:
        finished = now_iso()
        logging.exception("Backup job failed")
        await db.backup_jobs.update_one(
            {"id": job_id},
            {"$set": {"status": "error", "finished_at": finished, "error": str(e)}}
        )


@router.get("/list")
async def admin_backup_list(user=Depends(commander_only)):
    return {"backups": list_backups(), "backup_dir": str(BACKUP_DIR)}


@router.post("/run", status_code=202)
async def admin_backup_run(user=Depends(commander_only)):
    """Запуск бекапу у фоновому режимі. Повертає job_id для poll-а."""
    active = await db.backup_jobs.find_one(
        {"status": {"$in": ["queued", "running"]}}, {"_id": 0}
    )
    if active:
        return {
            "job_id": active["id"],
            "status": active["status"],
            "started_at": active.get("started_at", ""),
            "message": "Бекап вже виконується",
        }
    job_id = str(uuid.uuid4())
    now = now_iso()
    await db.backup_jobs.insert_one({
        "id": job_id,
        "status": "queued",
        "created_at": now,
        "created_by": user.username,
        "started_at": "",
        "finished_at": "",
        "result": None,
        "fallback": False,
        "error": "",
    })
    asyncio.create_task(_run_backup_job(job_id))
    return {"job_id": job_id, "status": "queued", "created_at": now}


@router.get("/job/{job_id}")
async def admin_backup_job_status(job_id: str, user=Depends(commander_only)):
    """Стан фонової задачі бекапу для UI polling."""
    job = await db.backup_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Задачу не знайдено")
    return job


@router.get("/jobs")
async def admin_backup_jobs(user=Depends(commander_only)):
    """Останні 20 задач бекапу для журналу/моніторингу."""
    jobs = await db.backup_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"jobs": jobs}


@router.get("/download/{name}")
async def admin_backup_download(name: str, user=Depends(commander_only)):
    if "/" in name or ".." in name:
        raise HTTPException(400, "Невірне ім'я")
    p = BACKUP_DIR / name
    if not p.exists():
        raise HTTPException(404, "Бекап не знайдено")
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    return FileResponse(p, media_type="application/gzip", filename=name, headers=headers)


@router.delete("/{name}")
async def admin_backup_delete(name: str, user=Depends(commander_only)):
    ok = delete_backup(name)
    if not ok:
        raise HTTPException(404, "Бекап не знайдено")
    return {"deleted": name}
