# Управління ротою — інструкція з розгортання

Повноцінний веб-додаток для управління ротою радіо та радіотехнічної розвідки:
- Облік особового складу (картки солдатів з документами)
- Облік озброєння, техніки, зв'язку (штатний / позаштатний)
- Облік боєкомплекту (АК-74, CZ BREN 2, гранати, ВОГ)
- Матриця взаємодії підрозділів
- Експорт у Microsoft Project XML
- JWT-авторизація з ролями + 2FA Google Authenticator
- Сповіщення матеріалісту про неповні документи

## Що в пакеті

```
rota-rrr-deploy/
├── backend/                    FastAPI + MongoDB
│   ├── server.py               REST API (auth, soldiers, ammo, equipment, ...)
│   ├── auth.py                 JWT + bcrypt + TOTP + ролі
│   ├── xml_generators.py       MS Project XML
│   └── structure.json          БЧС роти (109 осіб, 7 підрозділів)
├── frontend/                   React 19 + Tailwind
├── deploy/                     Docker конфіги
├── docker-compose.yml          MongoDB + Backend + Nginx
├── .env.example                ШАБЛОН (PUBLIC_URL, JWT_SECRET, HTTP_PORT)
├── CREDENTIALS.md              Тестові облікові
└── DEPLOY.md                   Ця інструкція
```

---

## Швидкий старт (5 хвилин)

### Вимоги
- Linux/macOS/Windows-сервер
- Docker 24+ і Docker Compose v2

### Крок 1. Скопіюйте проєкт на сервер

```bash
# Через SCP/SFTP, Git або просто розпакуйте ZIP
scp -r rota-rrr-deploy/ user@your-server:/opt/
ssh user@your-server
cd /opt/rota-rrr-deploy
```

### Крок 2. Налаштуйте `.env`

```bash
cp .env.example .env
# Згенеруйте JWT_SECRET (важливо для безпеки!):
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s/ЗМІНИТИ_НА_ВЛАСНИЙ_64_СИМВОЛЬНИЙ_HEX_РЯДОК/$JWT_SECRET/" .env
nano .env  # відредагуйте PUBLIC_URL
```

```env
PUBLIC_URL=http://192.168.1.100:8080
HTTP_PORT=8080
JWT_SECRET=<згенерований 64-символьний hex>
```

### Крок 3. Запустіть

```bash
docker compose up -d --build
docker compose ps   # всі 3 сервіси Up
```

Відкрийте: **http://your-server-ip:8080**

### Крок 4. Перший вхід

Тестові облікові (див. `CREDENTIALS.md`):
- `admin` / `rota2026` — повний доступ
- `kr` / `kolumb2026` — командир роти КОЛУМБ
- `material` / `venom2026` — матеріаліст ВЕНОМ

⚠ **Обов'язково змініть паролі через "Профіль → Змінити пароль"** після першого входу!

### Крок 5. Наповніть базу

Ввійшовши як `admin`, натисніть кнопки **«Заповнити типове»** на вкладках:
- Структура та засоби (38 одиниць техніки)
- Боєкомплект (24 записи: ~17000 БК)
- Матриця взаємодії (11 каналів)
- Картки солдатів → «Створити картки з БЧС» (23 картки)

---

## Архітектура

```
┌─────────────────┐         ┌────────────────┐         ┌──────────────┐
│  Браузер        │ ──HTTP──►   Nginx (80)   │ ──/api──►  FastAPI     │
│  (React SPA)    │ ◄────────  + статика SPA │ ◄────────  (uvicorn)   │
└─────────────────┘         └────────────────┘         └──────┬───────┘
                                                              │
                                                              ▼
                                                       ┌──────────────┐
                                                       │   MongoDB 7  │
                                                       │ (volume mongo_data) │
                                                       └──────────────┘
```

- **MongoDB** — внутрішня (порт не публікується назовні)
- **Backend (FastAPI)** — внутрішній (порт 8001 в docker-мережі)
- **Frontend (Nginx)** — публічний (порт 8080), проксує `/api/*` → backend

---

## Розгортання за HTTPS-доменом

Якщо хочете доступ через домен з SSL:

### Варіант 1 — Caddy (найпростіший)

Встановіть Caddy на хості та додайте `Caddyfile`:

```caddy
rota.example.com {
    reverse_proxy localhost:8080
}
```

`docker compose up -d` → `caddy run`. SSL отримається автоматично через Let's Encrypt.

### Варіант 2 — Traefik

Додайте до `docker-compose.yml`:

```yaml
  traefik:
    image: traefik:v3.0
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.le.acme.tlschallenge=true"
      - "--certificatesresolvers.le.acme.email=admin@example.com"
      - "--certificatesresolvers.le.acme.storage=/letsencrypt/acme.json"
    ports: ["80:80", "443:443"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    networks: [rrr-net]
```

І міток до `frontend`:

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.rrr.rule=Host(`rota.example.com`)"
      - "traefik.http.routers.rrr.entrypoints=websecure"
      - "traefik.http.routers.rrr.tls.certresolver=le"
```

### Варіант 3 — Nginx на хості + Let's Encrypt

```nginx
server {
    server_name rota.example.com;
    listen 443 ssl http2;
    ssl_certificate     /etc/letsencrypt/live/rota.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rota.example.com/privkey.pem;

    client_max_body_size 20m;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## Резервне копіювання БД

```bash
# Бекап
docker exec rrr-mongo mongodump --archive --db rrr_company > backup-$(date +%F).archive

# Відновлення
cat backup-2026-05-02.archive | docker exec -i rrr-mongo mongorestore --archive --drop
```

---

## Оновлення

```bash
git pull   # або заново скачайте архів
docker compose up -d --build
```

Дані MongoDB зберігаються у Docker volume `mongo_data` і не видаляються при оновленні.

---

## Логи / діагностика

```bash
docker compose logs -f                # всі сервіси
docker compose logs -f backend        # тільки backend
docker compose logs -f frontend       # тільки nginx

# Перезапустити окремий сервіс
docker compose restart backend

# Зайти в контейнер
docker exec -it rrr-backend bash
docker exec -it rrr-mongo mongosh
```

### Типові проблеми

| Симптом | Рішення |
|---------|---------|
| 502 Bad Gateway на `/api/...` | `docker compose logs backend` — перевірте чи стартанув |
| CORS error у консолі | Перевірте `PUBLIC_URL` у `.env`, перебілдьте: `docker compose up -d --build` |
| Порт 8080 зайнятий | Змініть `HTTP_PORT` у `.env` |
| MongoDB не стартує | `docker volume rm rota-rrr-deploy_mongo_data` (УВАГА: видалить дані) |

---

## Безпека (production)

⚠ За замовчуванням додаток **без автентифікації**. Для prod-розгортання обов'язково:

1. **Базова HTTP-автентифікація через Nginx**:
   ```bash
   apt install apache2-utils
   htpasswd -c /etc/nginx/.htpasswd admin
   ```
   Додайте у `deploy/nginx.conf`:
   ```nginx
   location / {
       auth_basic "РРР - доступ обмежено";
       auth_basic_user_file /etc/nginx/.htpasswd;
       try_files $uri $uri/ /index.html;
   }
   ```

2. **Або** опублікуйте лише через VPN / закритий контур.

3. **MongoDB** — за замовчуванням без auth (бо не публічна), але якщо публікуєте порт назовні — обов'язково ввімкніть `--auth` і створіть користувача.

---

## API Endpoints

| Метод | Шлях | Опис |
|-------|------|------|
| GET | `/api/structure` | Повна структура роти |
| GET | `/api/config` | Категорії, типи, стани, канали |
| GET | `/api/equipment?node_path=...` | Список засобів |
| POST | `/api/equipment` | Додати засіб |
| PUT | `/api/equipment/{id}` | Оновити |
| DELETE | `/api/equipment/{id}` | Видалити |
| POST | `/api/equipment/preset/typical` | Заповнити типове |
| GET | `/api/equipment/summary` | Зведення |
| GET/POST/PUT/DELETE | `/api/interactions[/...]` | Матриця взаємодії |
| POST | `/api/interactions/preset/typical` | Типова матриця |
| GET | `/api/export/orgstructure.xml` | MS Project XML — оргструктура |
| GET | `/api/export/command.xml` | MS Project XML — бойове управління |
| GET | `/api/export/interactions.xml` | MS Project XML — матриця |
| GET | `/api/export/full-package.zip` | ZIP-пакет (3 XML + 2 CSV) |

---

## Контакти / підтримка

Усе працює на стандартних опенсорсних компонентах:
- FastAPI (Apache-2.0)
- React (MIT)
- MongoDB (SSPL для community edition)
- Nginx (BSD-2)

Не потребує жодного зовнішнього API чи ключів.
