# PRD — Управління ротою РРР (БЧС → Editor → MS Project)

## Original problem statement
1. "сделай мне блок схему управленее ротой на базе БЧС и выведи ее в Microsoft Project"
2. "ТАК зроби та додай редактируюмую версию чтоб можно було дабавить засоби транспорт и все остальное добавь функцию штатный и позаштатныи засіб"

## User choices
- Інтерактивний веб-редактор + експорт у MS Project XML
- Org chart + бойове управління + матриця взаємодії
- Розрізнення штатний/позаштатний для кожного засобу
- Українська мова

## Архітектура
- **Backend**: FastAPI + MongoDB (motor); structure.json як статичні дані БЧС
- **Frontend**: React 19, TailwindCSS, axios, мілітарі-стиль (тема BG#0E1A14, accent#A4C26A)
- **Експорт**: 3 MS Project XML файли + ZIP з 2 CSV

## Реалізовано (2026-05-02)
- `/app/backend/server.py` — FastAPI з ~20 endpoints (CRUD засобів, взаємодій, presets, експорт)
- `/app/backend/xml_generators.py` — генератори MS Project XML
  - `generate_org_structure_xml(company, equipment)` — WBS + персонал (Work) + засоби (Material з Group=штатний/позаштатний)
  - `generate_command_cycle_xml(company)` — 38 завдань / 7 фаз циклу управління
  - `generate_interaction_matrix_xml(company, interactions)` — групи каналів зв'язку
- `/app/frontend/src/App.js` — редактор з 3 вкладками:
  - Структура та засоби (дерево + редагування)
  - Матриця взаємодії (CRUD каналів зв'язку)
  - Зведення (статистика, графіки)

## Ключові API
- `GET /api/structure` — БЧС структура (109 осіб, 7 підрозділів)
- `POST /api/equipment` — додати засіб (тип=штатний|позаштатний)
- `POST /api/equipment/preset/typical` — наповнити типове (33 записи, 198 одиниць)
- `POST /api/interactions/preset/typical` — наповнити типову матрицю (11 каналів)
- `GET /api/export/orgstructure.xml | command.xml | interactions.xml | full-package.zip`

## Тестування (iter 1)
- Backend: 12/12 pytest pass (100%)
- Frontend: smoke test — всі сценарії працюють (100%)

## Backlog
- P2: drag-and-drop переміщення засобу між вузлами
- P2: фільтр за станом (несправні / потребують ремонту)
- P2: експорт SVG блок-схем напряму з UI
- P2: групове редагування (мульти-вибір)
