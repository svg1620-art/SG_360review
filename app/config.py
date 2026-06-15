"""Конфиг приложения. Все значения — из переменных окружения."""
import os

from dotenv import load_dotenv

# Локально подхватываем .env (на Railway переменные приходят из окружения).
load_dotenv()


class Config:
    APP_ENV = os.environ.get("FLASK_ENV", "production")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    # Порог анонимности по умолчанию для новых компаний (companies.anon_threshold).
    ANON_THRESHOLD = int(os.environ.get("ANON_THRESHOLD", "3"))
    DEBUG = APP_ENV == "development"

    # Куки сессии: защита от XSS и базовая защита от CSRF для форм.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # В проде куки только по HTTPS (по умолчанию вкл для production).
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "1" if APP_ENV == "production" else "0"
    ) not in ("0", "false", "False")

    # APScheduler: напоминания и авто-закрытие циклов по дедлайну.
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "1") not in ("0", "false", "False")
    SCHEDULER_INTERVAL_MIN = int(os.environ.get("SCHEDULER_INTERVAL_MIN", "5"))
    REMINDER_DAYS_BEFORE = int(os.environ.get("REMINDER_DAYS_BEFORE", "3"))

    # Email и базовый URL для ссылок в письмах.
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
