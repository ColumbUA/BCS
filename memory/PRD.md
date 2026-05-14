# PRD — Управління ротою радіо та радіотехнічної розвідки

## Зведено за всі ітерації

**MVP**: Веб-комплекс для управління ротою РРР (109 осіб):
структура БЧС, засоби, БК, картки солдатів, склад, документообіг, MS Project експорт.

## Реалізовано
- **Auth**: JWT + bcrypt + brute-force lock + 2FA TOTP (Google Authenticator)
- **Ролі**: COMMANDER / PLATOON_LEADER / MATERIAL / VIEWER
- **11 seed-користувачів**: KR, 5 КВ, 3 матеріальних, viewer, admin, MALVINA
- **Структура роти**: 7 підрозділів, 109 посад, КОЛУМБ → командир роти
- **Засоби**: 7 категорій × штатний/позаштатний, типовий пресет
- **БК (боєкомплект)**: 19 типів зброї (АК-74, CZ BREN 2, гранати, ВОГ), типовий пресет 17418 од.
- **Картки солдатів**: ПІБ, мобілізація, БЗВП, КТЗ, освіта, сертифікати, документи
- **Документи (5 типів)**: паспорт, ІПН, диплом, ВП, ВК — upload до 20 MB
- **Сповіщення матеріалісту**: ОРЛОВ Борис «ВЕНОМ» — список неповних карток
- **Склад**: позиції з SN, прихід/видача/списання, мін.залишки, журнал операцій
- **Документообіг**: 25 шаблонів .docx (рапорти 8, накази 3, акти 5, журнали 6, донесення 3)
- **Реквізити частини**: повна назва, в/ч, командир, місто — підставляються у документи
- **MS Project XML**: оргструктура, бойове управління, матриця взаємодії
- **Експорт ZIP**: 3 XML + 4 CSV
- **Deploy ZIP**: Docker Compose + Dockerfile-и + Nginx + повна frontend/backend (320 KB / 87 файлів)
- **Локації солдата**: ППД / РЗ / РВ / Відрядження / Лікарня / СЗЧ / ВЛК / Інше + місце + фільтр у БЧС
- **Переміщення (transfers)**: in-rota / in-bat / in-polk / in-brigade / in-zsu / discharge / deceased / missing
- **Inline PDF/image preview**: документи відкриваються прямо у картці без скачування
- **Авто-приєднання згенерованих .docx**: з статусами draft → signed → executed
- **Backup БД+файлів**: tar.gz через mongodump + storage/ + structure.json, авто щодня 02:00 UTC, COMMANDER-only

## Iteration 6 (2026-05-14) — Code-Review Fixes
- **Async Backup**: POST /admin/backup/run повертає 202 з job_id (фонова asyncio.create_task), polling через GET /admin/backup/job/{id} (status: queued→running→done), GET /admin/backup/jobs — журнал. UI більше не блокується.
- **Validation in-rota transfers**: `_company_node_paths()` — обчислює валідні підрозділи зі structure.json; create/execute транзит-ендпоінти повертають 400 при невалідному `to_node_path`/`from_node_path`.
- **Auto location_status='ППД'** при внутрішньому виконанні переміщення (in-rota). Для in-bat/in-zsu/discharge/deceased/missing → location_status='Інше'.
- **Dedupe rendered docs**: GET /templates/{tid}/render?save_to_card=1 — за `(soldier_id, template_id, today)` оновлює існуючий draft замість створення нового.
- **DocumentStatusUpdate Pydantic** (extra='forbid', Literal['draft','signed','executed']) — заміна raw dict у PUT /documents/{fid}/status. 422 на invalid value/extra field.
- **backup_mod.py**: meta.json та результат містять поле `fallback` (True якщо mongodump впав і використано _manual_json_dump).
- **CSV export**: переписаний на `csv.writer` (QUOTE_MINIMAL) для коректних значень з ';' та '\n'.
- **Frontend BackupTab**: data-testid='backup-job-progress' (під час running) і 'backup-job-result' (після done з ✓ ім'я + розмір + позначка fallback).

## Тестування
- Iter 1-5: Backend 100%, Frontend 100%, документи валідні
- **Iter 6 (актуальна)**: 19/19 pytest проходять, Frontend smoke OK

## Архітектура
- FastAPI + MongoDB + python-docx + bcrypt + PyJWT + pyotp + qrcode + APScheduler
- React 19 + Tailwind + axios + AuthContext + Polling для async jobs

## Backlog (P1)
- Розбити server.py (1591 рядки) на routers: `routes/soldiers.py`, `routes/warehouse.py`, `routes/transfers.py`, `routes/backup.py`
- PLATOON_LEADER має бачити лише свій взвод (зараз бачить усе)
- Audit log дій (хто/що/коли)
- Експорт PDF особової картки
- Інтеграція "Штатка схема розвідувальний батальйон.xlsx" (множинні роти/підрозділи батальйону)

## Backlog (P2)
- Telegram Bot для пуш-сповіщень матеріалісту
- WhatsApp Bot для авто-завантаження документів з групи (відкладено користувачем)
- Інтеграція MinIO/S3 для масштабованого зберігання документів
- Drag-and-drop замість upload buttons
- Двійковий експорт усіх документів роти одним архівом
- Кешування `_company_node_paths()` з TTL ~60s
- Enum для DOC_STATUSES + DOC_STATUS_LABELS (синхронізація з DocumentStatusUpdate)
- CSV `\r\n` для кращої сумісності з Excel на Windows
