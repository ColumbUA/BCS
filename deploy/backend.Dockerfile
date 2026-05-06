# =====================================================================
# Управління ротою РРР — Backend (FastAPI + Python 3.11)
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системні залежності (для motor/pymongo)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Установлюємо залежності (мінімальний набір для production)
COPY deploy/backend.requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копіюємо код
COPY backend/server.py backend/auth.py backend/xml_generators.py backend/structure.json ./

# Створюємо директорію для зберігання документів
RUN mkdir -p /app/storage/docs
ENV STORAGE_DIR=/app/storage

EXPOSE 8001

# Запуск через uvicorn (production-ready з 2 worker'ами)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
