# Управління ротою РРР — інструкція з розгортання

Повноцінний веб-додаток для редагування БЧС роти радіо та радіотехнічної розвідки з експортом у Microsoft Project XML.

## Що в пакеті

```
rota-rrr-deploy/
├── backend/                    FastAPI + Python
│   ├── server.py               REST API (CRUD засобів, взаємодій, експорт)
│   ├── xml_generators.py       генератори MS Project XML
│   └── structure.json          БЧС роти (109 осіб, 7 підрозділів)
├── frontend/                   React 19 + Tailwind
│   └── src/                    редактор з 3 вкладками
├── deploy/                     конфіги для Docker
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile     (multi-stage → Nginx)
│   ├── nginx.conf              SPA + проксі /api
│   └── backend.requirements.txt
├── docker-compose.yml          оркестрація 3 контейнерів
├── .env.example                шаблон налаштувань
└── DEPLOY.md                   ця інструкція
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
nano .env
```

```env
# Зовнішня адреса сервера (для CORS)
PUBLIC_URL=http://192.168.1.100:8080
# або якщо за домен через reverse-proxy:
# PUBLIC_URL=https://rota.example.com

HTTP_PORT=8080      # порт для зовнішнього доступу
```

### Крок 3. Запустіть

```bash
docker compose up -d --build
```

Перший білд триває 3–5 хв. Після завершення:

```bash
docker compose ps
# rrr-mongo, rrr-backend, rrr-frontend — всі Up
```

Відкрийте у браузері: **http://your-server-ip:8080**

### Крок 4. Наповніть базу типовими даними

Натисніть кнопки **«Заповнити типове»** на вкладках:
- *Структура та засоби* → 33 записи (~198 одиниць техніки)
- *Матриця взаємодії* → 11 типових каналів зв'язку

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
