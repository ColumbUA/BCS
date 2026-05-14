"""Бекап БД та файлів.

Створює tar.gz з:
  - MongoDB dump (mongodump)
  - /app/storage/docs/ (документи)
  - /app/backend/structure.json (БЧС)
Зберігає у /app/backups/. Залишає лише N останніх бекапів.
"""
import os, subprocess, tarfile, shutil, tempfile, json
from datetime import datetime, timezone
from pathlib import Path

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/app/backups"))
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/app/storage"))
BACKEND_DIR = Path(__file__).parent
KEEP_LAST = int(os.environ.get("BACKUP_KEEP_LAST", "10"))
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def make_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    name = f"backup-{stamp}.tar.gz"
    out_path = BACKUP_DIR / name
    fallback = False
    fallback_error = ""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dump_dir = tmp_path / "mongo"
        dump_dir.mkdir()

        # 1) mongodump
        try:
            subprocess.run(
                ["mongodump", "--uri", MONGO_URL, "--db", DB_NAME,
                 "--out", str(dump_dir), "--quiet"],
                check=True, capture_output=True, timeout=120
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            # Fallback: ручний JSON dump через pymongo
            fallback = True
            fallback_error = str(e)
            _manual_json_dump(dump_dir / DB_NAME)

        # 2) Збираємо tar.gz
        with tarfile.open(out_path, "w:gz") as tar:
            tar.add(dump_dir, arcname="mongo")
            if STORAGE_DIR.exists():
                tar.add(STORAGE_DIR, arcname="storage")
            structure = BACKEND_DIR / "structure.json"
            if structure.exists():
                tar.add(structure, arcname="structure.json")
            # Записуємо meta
            meta = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "db_name": DB_NAME,
                "docs_dir": str(STORAGE_DIR),
                "fallback": fallback,
                "fallback_error": fallback_error if fallback else "",
            }
            meta_path = tmp_path / "meta.json"
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            tar.add(meta_path, arcname="meta.json")

    # Видаляємо старі бекапи
    backups = sorted(BACKUP_DIR.glob("backup-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for old in backups[KEEP_LAST:]:
        try:
            old.unlink()
            removed.append(old.name)
        except Exception:
            pass

    return {
        "name": name,
        "path": str(out_path),
        "size": out_path.stat().st_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "removed_old": removed,
        "fallback": fallback,
        "fallback_error": fallback_error if fallback else "",
    }


def _manual_json_dump(db_path: Path):
    """Fallback якщо mongodump недоступний — пишемо колекції як JSON."""
    from pymongo import MongoClient
    db_path.mkdir(parents=True, exist_ok=True)
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    for coll in db.list_collection_names():
        data = list(db[coll].find({}))
        for d in data:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        with open(db_path / f"{coll}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def list_backups() -> list:
    if not BACKUP_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUP_DIR.glob("backup-*.tar.gz"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "name": p.name,
            "size": st.st_size,
            "created_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        })
    return out


def delete_backup(name: str) -> bool:
    if "/" in name or "\\" in name or ".." in name:
        return False
    p = BACKUP_DIR / name
    if not p.exists() or not p.is_file():
        return False
    p.unlink()
    return True
