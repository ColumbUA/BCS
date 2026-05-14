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
- **БК (боєкомплект)**: 19 типів зброї, типовий пресет 17418 од.
- **Картки солдатів**: ПІБ, мобілізація, БЗВП, КТЗ, освіта, сертифікати, документи
- **Документи (5 типів)**: паспорт, ІПН, диплом, ВП, ВК — upload до 20 MB
- **Сповіщення матеріалісту** про неповні картки
- **Склад**: позиції з SN, прихід/видача/списання, мін.залишки
- **Документообіг**: 25 шаблонів .docx
- **MS Project XML**: оргструктура, бойове управління, матриця взаємодії
- **Експорт ZIP**: 3 XML + 4 CSV
- **Deploy ZIP**: Docker Compose + Dockerfile + Nginx
- **Локації солдата**: ППД/РЗ/РВ/Відрядження/Лікарня/СЗЧ/ВЛК + місце + фільтр
- **Переміщення (transfers)**: 8 типів з виконанням і авто-оновленням локацій
- **Inline PDF/image preview** документів
- **Авто-приєднання згенерованих .docx** з статусами + dedupe
- **Backup БД+файлів** через mongodump+tar.gz, async з job tracking

## Iteration 7 (2026-05-14) — Великий пакет
- **Refactor**: `server.py` 1591 → 1329 рядків. Винесено у `routes/soldiers.py, transfers.py, backup.py, warehouse.py` + `deps.py` (shared constants/db/helpers).
- **PLATOON_LEADER scope**: КВ бачить лише свій взвод (фільтр soldiers/transfers через `_is_in_scope` / `_scope_filter` з префікс-перевіркою по `user.platoon`). Може створювати transfer-и до будь-якого підрозділу роти. Заборонено: GET/PUT/DELETE чужих солдатів (403), зміна node_path через PUT (треба `/transfers`).
- **Audit log**: `AuditMiddleware` логує всі POST/PUT/DELETE у `db.audit_log` з **TTL 90 днів** (MongoDB index). Ендпоінти `GET /api/audit-log` (фільтри: category/username/success/limit), `/audit-log/categories`. Тільки COMMANDER. UI: вкладка 📋 Аудит.
- **PDF експорт картки**: `GET /api/soldiers/{sid}/export.pdf` через `reportlab + FreeSans` (кирилиця). 1-2 сторінки A4: загальні дані, підготовка, локація, освіта, сертифікати, документи, переміщення, примітки. UI: кнопка 📄 PDF у картці.
- **CRUD редактор структури**: POST/PUT/DELETE `/api/structure/subunits` та `/structure/squads/{parent_key}/{key}`. Каскадне оновлення `node_path` у soldiers/equipment/ammo при перейменуванні. DELETE з ?force=1 при залежностях. Тільки COMMANDER. UI: вкладка 🏗 Структура (ред.).

## Тестування
- Iter 1-5: Backend 100%, Frontend 100%
- Iter 6 (code-review fixes): 19/19 ✅
- **Iter 7 (актуальна)**: 32/32 backend + 100% frontend ✅, 0 блокерів

## Архітектура
- FastAPI + MongoDB + python-docx + bcrypt + PyJWT + pyotp + qrcode + APScheduler + reportlab
- React 19 + Tailwind + axios + AuthContext
- Backend routers: `auth.py` (модуль), `routes/{soldiers,transfers,backup,warehouse}.py`, `deps.py`, `audit_mod.py`, `pdf_card.py`, `backup_mod.py`, `templates_lib.py`, `xml_generators.py`
- Сервер.py — auth/users/structure CRUD/equipment/interactions/documents/ammo/notifications/config/settings/templates/audit/export

## Backlog (P1)
- Додатковий рефактор: винести structure CRUD у `routes/structure.py`, audit endpoints у `routes/audit.py`
- Кешувати user у `request.state` (зараз AuditMiddleware робить db.users.find_one() на кожному mutating-запиті)
- Інтеграція "Штатка схема розвідувальний батальйон" — користувач опише структуру батальйону текстом (3 РРР + штаб + забезпечення тощо)

## Backlog (P2)
- Async file write для `_save_structure()` (aiofiles + Lock)
- Логування body_snippet у audit для критичних DELETE/PUT
- Enum для DOC_STATUSES + DOC_STATUS_LABELS
- Telegram Bot для пуш-сповіщень матеріалісту
- WhatsApp Bot для авто-завантаження документів (відкладено користувачем)
- MinIO/S3 для масштабованого зберігання документів
- Drag-and-drop для upload документів
- Двійковий експорт усіх документів роти одним архівом
- CSV `\r\n` для Excel-Win
