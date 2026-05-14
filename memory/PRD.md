# PRD — Управління ротою радіо та радіотехнічної розвідки

## Зведено за всі ітерації

**MVP**: Веб-комплекс для управління ротою РРР (109 осіб):
структура БЧС, засоби, БК, картки солдатів, склад, документообіг, MS Project експорт.

## Реалізовано
- **Auth**: JWT + bcrypt + brute-force lock + 2FA TOTP
- **Ролі**: COMMANDER / PLATOON_LEADER / MATERIAL / VIEWER + захист `admin` від пониження/видалення
- **11 seed-користувачів**: admin, KR, 5 КВ, 3 матеріальних, viewer, MALVINA
- **Структура роти**: 7 підрозділів, 109 посад, КОЛУМБ → командир роти
- **Засоби**: 7 категорій × штатний/позаштатний
- **БК**: 19 типів зброї, 17418 од.
- **Картки солдатів**: документи (паспорт/ІПН/диплом/ВП/ВК), БЗВП/КТЗ, мобілізація
- **Сповіщення матеріалісту** про неповні картки
- **Склад**: позиції з SN, прихід/видача/списання, мін.залишки
- **Документообіг**: 25 шаблонів .docx з авто-приєднанням до картки
- **MS Project XML + Deploy ZIP** (Docker)
- **Локації**: ППД/РЗ/РВ/Відрядження/Лікарня/СЗЧ/ВЛК + фільтр
- **Переміщення**: 8 типів з валідацією структури + авто-ППД
- **Inline PDF/image preview**, dedupe генерованих .docx
- **Backup async** (mongodump+tar.gz) з job tracking + UI poll
- **PLATOON_LEADER scope**: КВ бачить лише свій взвод
- **Audit log**: всі POST/PUT/DELETE з TTL 90 днів, UI вкладка
- **PDF особової картки** (reportlab + FreeSans для кирилиці)
- **CRUD редактор структури** з каскадним оновленням node_path

## Iteration 8 (2026-05-14) — Heat-map + admin защита
- **Risk Heat-map**: `/api/risk-heatmap` обчислює ризик для кожного солдата:
  - 🔴 Червоний: відсутні документи (passport/ipn/military_id), СЗЧ, прострочене переміщення >14 днів
  - 🟡 Жовтий: БЗВП/КТЗ не пройдено або >12 міс, Лікарня/ВЛК
  - 🟢 Зелений: усе в нормі
- **UI**: вкладка «🔥 Огляд» як стартова, hero-bar з пропорціями, картки по підрозділах, фільтр + список солдатів з причинами
- **PLATOON_LEADER scope** працює і в heatmap (бачить тільки свої взводи)
- **Admin protection**: PUT/DELETE /api/users захищає системного admin від пониження ролі та видалення

## Тестування
- Iter 1-5: Backend 100%, Frontend 100%
- Iter 6 (code-review): 19/19 ✅
- Iter 7 (refactor + 4 фічі): 32/32 backend + 100% frontend ✅
- **Iter 8 (Heat-map)**: self-tested через curl + screenshot (admin 24, kv1 12, viewer 24, admin protect ✅)

## Архітектура
- FastAPI + MongoDB + python-docx + bcrypt + PyJWT + pyotp + qrcode + APScheduler + reportlab
- React 19 + Tailwind + axios + AuthContext
- Backend: `auth.py`, `routes/{soldiers,transfers,backup,warehouse}.py`, `deps.py`, `audit_mod.py`, `pdf_card.py`, `backup_mod.py`, `templates_lib.py`, `xml_generators.py`
- Frontend: 12 вкладок (Огляд / Структура / БК / Склад / Картки / Документи / Матриця / Сповіщення / Користувачі / Бекап / Аудит / Структура ред. / Зведення)

## Backlog (P1)
- Інтеграція структури батальйону (користувач опише текстом)
- Refactor: винести structure CRUD + audit endpoints у окремі routers
- Кешування user у `request.state` (AuditMiddleware зараз робить find_one на кожний mutating)

## Backlog (P2)
- Async file write для `_save_structure()` (aiofiles + Lock)
- Telegram бот для пуш-сповіщень
- WhatsApp Bot для авто-завантаження документів (відкладено)
- MinIO/S3 для масштабованого зберігання документів
- Drag-and-drop upload
- Експорт всіх документів роти одним архівом
- CSV `\r\n` для Excel-Win
