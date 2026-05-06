# PRD — Управління ротою радіо та радіотехнічної розвідки

## Original problem statements (eng/ukr/rus mix)
1. Створити блок-схему управління ротою на базі БЧС, експорт у MS Project
2. Додати редактор з можливістю додавати засоби/транспорт + штатний/позаштатний
3. Виправити завантаження + повний пакет для розгортання
4. **Повний комплекс**: картки солдатів (мобілізація, БЗВП, КТЗ, освіта, документи), облік БК (АК-74, CZ BREN 2), JWT auth + ролі + Google Authenticator, сповіщення матеріалісту, перейменувати РРР → повна назва, перенести КОЛУМБ на КР

## Архітектура
- **Backend**: FastAPI + MongoDB (motor) + bcrypt + PyJWT + pyotp + qrcode
- **Frontend**: React 19, контекст AuthContext, 6 вкладок, модалки
- **Storage**: MongoDB (дані) + локальна ФС (`/app/storage/docs` для документів)

## Реалізовано (2026-05-02 ÷ 2026-05-06)

### Auth & Roles (iter 3)
- JWT (8 год), bcrypt, brute-force lock 5×15 хв
- 4 ролі: COMMANDER / PLATOON_LEADER / MATERIAL / VIEWER
- 2FA TOTP через Google Authenticator (pyotp + qrcode)
- 6 seed-користувачів (admin, kr, material, kv1, kv2, viewer)

### БЧС-структура
- Парсер з Excel у JSON (109 осіб, 7 підрозділів)
- КОЛУМБ перенесений з 1 Взводу на Командира роти (АМЕЛЬКІН Василь Сергійович)

### Особові картки (iter 3)
- 23 картки автоматично з БЧС
- Поля: ПІБ, позивний, звання, посада, мобілізація, БЗВП, КТЗ, освіта[], сертифікати[], група крові, ВП
- Завантаження документів: passport / ipn / diploma / driver_license / military_id / certificate / other
- File upload до 20 MB, локальне зберігання

### Засоби та БК (iter 1-3)
- 7 категорій (Засіб зв'язку, Транспорт, ОВТ, РТ засіб, БпЛА, РЕБ, Інше)
- Тип: штатний / позаштатний
- БК: 19 типів зброї (АК-74, CZ BREN 2, ПМ, СВД, ВОГ, гранати, ...)
- Типовий пресет: 17418 одиниць БК (14700 АК-74, 2310 CZ BREN 2)

### Матриця взаємодії (iter 1)
- 7 типів каналів (УКХ/КХ/ЗАЗ/цифровий/дротовий/SAT/посильний)
- Типовий пресет: 11 каналів між підрозділами

### Сповіщення (iter 3)
- Endpoint /api/notifications/material показує неповні картки
- Recipient: ОРЛОВ Борис Борисович «ВЕНОМ» (матеріаліст)
- Логіка: passport+ipn+military_id обов'язкові; driver_license якщо has_driver_license=true

### Експорт MS Project (iter 1-2)
- 3 XML: оргструктура (з засобами як Material), бойове управління, матриця
- ZIP-пакет з XML + 4 CSV (засоби, БК, матриця, ОС)
- Завантаження через fetch+blob (кириличні назви)

### Deploy
- Docker Compose + Nginx + JWT_SECRET у .env
- Volume для документів (`storage_data`)
- ZIP-пакет 300 KB / 84 файли (`/files/rota-rrr-deploy.zip`)

## Тестування
- Iter 1: 12/12 backend, frontend smoke OK
- Iter 2: 5/5 download buttons OK
- Iter 3: 23/23 backend (auth, 2FA, RBAC, soldiers, docs, ammo, notifications), 100% frontend

## Технічні зауваги
- Proton Drive — НЕ реалізовано (немає публічного API). Документи зберігаються локально, повний експорт у ZIP можна вручну закинути в Proton Drive
- 2FA failure counter відокремлений від password counter (виправлено після iter 3)

## Backlog (P2)
- Розширити RBAC: PLATOON_LEADER має бачити лише свій взвод (зараз бачить усе)
- Audit log дій (хто, що, коли)
- Експорт PDF особової картки
- Інтеграція з MinIO/S3 для масштабування файлів
- Пуш-сповіщення матеріалісту через Telegram Bot
