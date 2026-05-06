# =====================================================================
# Управління ротою РРР — Frontend (multi-stage React build → Nginx)
# =====================================================================

# ---------- Stage 1: build ----------
FROM node:20-alpine AS build

WORKDIR /build

# Копіюємо мета-файли і встановлюємо залежності
COPY frontend/package.json frontend/yarn.lock* ./
RUN corepack enable && yarn install --frozen-lockfile || yarn install

# Копіюємо решту коду та збираємо
COPY frontend/. .

# REACT_APP_BACKEND_URL передається при білді (build-arg)
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}

RUN yarn build


# ---------- Stage 2: serve via Nginx ----------
FROM nginx:1.27-alpine

# Копіюємо білд
COPY --from=build /build/build /usr/share/nginx/html

# Власний nginx.conf — підтримка SPA + проксі /api на backend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
