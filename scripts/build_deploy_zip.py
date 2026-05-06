"""Створює ZIP-пакет для розгортання на віддаленому сервері."""
import zipfile, os
from pathlib import Path

OUT = Path("/tmp/rota-rrr-deploy.zip")
ROOT = Path("/app")

# Файли, які входять до пакета (з шляхами всередині zip)
files = [
    # Backend
    ("backend/server.py",            "rota-rrr-deploy/backend/server.py"),
    ("backend/xml_generators.py",    "rota-rrr-deploy/backend/xml_generators.py"),
    ("backend/structure.json",       "rota-rrr-deploy/backend/structure.json"),
    # Deploy
    ("deploy/backend.Dockerfile",    "rota-rrr-deploy/deploy/backend.Dockerfile"),
    ("deploy/frontend.Dockerfile",   "rota-rrr-deploy/deploy/frontend.Dockerfile"),
    ("deploy/nginx.conf",            "rota-rrr-deploy/deploy/nginx.conf"),
    ("deploy/backend.requirements.txt", "rota-rrr-deploy/deploy/backend.requirements.txt"),
    ("deploy/.env.example",          "rota-rrr-deploy/deploy/.env.example"),
    ("docker-compose.yml",           "rota-rrr-deploy/docker-compose.yml"),
    (".env.example",                 "rota-rrr-deploy/.env.example"),
    ("DEPLOY.md",                    "rota-rrr-deploy/DEPLOY.md"),
]

# Frontend — копіюємо всі src + конфіги, без node_modules та build
frontend_root = ROOT / "frontend"
include_dirs = ["src", "public"]
include_files = ["package.json", "yarn.lock", "tailwind.config.js",
                 "postcss.config.js", "craco.config.js", "components.json",
                 "jsconfig.json", ".env"]

# Frontend .env для production — ставимо порожнє, бо буде override через build-arg
frontend_env_prod = "REACT_APP_BACKEND_URL=\nWDS_SOCKET_PORT=443\n"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    # Backend + deploy + root files
    for src, dst in files:
        p = ROOT / src
        if p.exists():
            z.write(p, dst)
            print(f"+ {dst}")
        else:
            print(f"! MISSING: {src}")

    # Frontend
    for d in include_dirs:
        for path in (frontend_root / d).rglob("*"):
            if path.is_file():
                # пропускаємо папку /files (статичні файли preview-середовища)
                rel = path.relative_to(frontend_root)
                if str(rel).startswith("public/files"):
                    continue
                arc = f"rota-rrr-deploy/frontend/{rel}"
                z.write(path, arc)

    # Frontend root files
    for fname in include_files:
        p = frontend_root / fname
        if p.exists():
            if fname == ".env":
                # production .env (порожній REACT_APP_BACKEND_URL → /api проксується)
                z.writestr("rota-rrr-deploy/frontend/.env", frontend_env_prod)
            else:
                z.write(p, f"rota-rrr-deploy/frontend/{fname}")

    # README на корені
    z.writestr("rota-rrr-deploy/README.md",
               "Дивіться DEPLOY.md для повної інструкції.\n\n"
               "Швидкий старт:\n"
               "  cp .env.example .env\n"
               "  # відредагуйте PUBLIC_URL\n"
               "  docker compose up -d --build\n"
               "  # відкрийте http://your-server:8080\n")

print(f"\nГотово: {OUT}")
print(f"Розмір: {OUT.stat().st_size//1024} KB")
