# SG_360review

SaaS-сервис оценки сотрудников по методу 360°. Мультитенантный, доменно-нейтральный.

Полное ТЗ — [`docs/SG_360review_TZ.md`](docs/SG_360review_TZ.md) (источник правды).

## Стек
Flask + Jinja2 + HTMX · PostgreSQL · Alembic · psycopg 3 · Chart.js · APScheduler · Railway (EU) · ЮKassa

## Локальный запуск

```bash
# 1. Зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Окружение
cp .env.example .env   # пропиши DATABASE_URL и SECRET_KEY

# 3. Миграции
alembic upgrade head

# 4. (опционально) демо-компания с дефолтным шаблоном компетенций
flask --app wsgi seed-demo-company --name "Acme"

# 5. Запуск
flask --app wsgi run --debug
```

Проверка: `GET /health` → `{"status": "ok"}`.

## Структура
```
app/
  __init__.py              фабрика create_app()
  config.py                конфиг из переменных окружения
  db.py                    подключение к PostgreSQL (psycopg 3)
  cli.py                   flask-команды (seed-demo-company)
  seeds/
    default_competencies.py  дефолтный шаблон компетенций + сид-функция
migrations/                Alembic (env.py читает DATABASE_URL из окружения)
  versions/0001_initial_schema.py   схема БД строго по разделу 6 ТЗ
wsgi.py                    точка входа (gunicorn wsgi:app)
Procfile                   запуск на Railway
```

## Миграции
Пишутся вручную через `op.execute(...)` (без ORM/автогенерации). URL для Alembic
берётся из `DATABASE_URL` и переводится на драйвер `postgresql+psycopg://` в
`migrations/env.py`.

## Тесты
```bash
pip install -r requirements-dev.txt
createdb sg_360review_test
DATABASE_URL=postgresql://localhost/sg_360review_test FLASK_ENV=testing \
  SECRET_KEY=test pytest -q
```
Схема накатывается автоматически (фикстура), данные чистятся перед каждым тестом.
CI (`.github/workflows/ci.yml`) гоняет pytest на сервисном PostgreSQL.

## Деплой на Railway (EU)
- Переменные окружения добавляются **по одной** через «New Variable» (не склеивать
  многострочные значения). Регион — EU.
- Обязательно задать: `DATABASE_URL`, `SECRET_KEY` (в `production` без него падаем),
  `APP_BASE_URL` (для ссылок в письмах). Опционально: `EMAIL_BACKEND`,
  `REMINDER_DAYS_BEFORE`, `ANON_THRESHOLD`, `SESSION_COOKIE_SECURE`.
- `Procfile`:
  - `web` — накатывает миграции (`alembic upgrade head`) и запускает gunicorn.
    Держите `WEB_CONCURRENCY=1`, иначе APScheduler стартует в каждом воркере.
  - `worker` — отдельный процесс планировщика. Если нужно масштабировать web
    (`WEB_CONCURRENCY>1`), включите `worker` и поставьте на web `SCHEDULER_ENABLED=0`.
- Фоновые задачи: напоминания и авто-закрытие циклов (APScheduler), идемпотентны.
