"""Конфиг приложения. Все значения — из переменных окружения."""
import os

from dotenv import load_dotenv

# Локально подхватываем .env (на Railway переменные приходят из окружения).
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    # Порог анонимности по умолчанию для новых компаний (companies.anon_threshold).
    ANON_THRESHOLD = int(os.environ.get("ANON_THRESHOLD", "3"))
    DEBUG = os.environ.get("FLASK_ENV", "production") == "development"

    # Куки сессии: защита от XSS и базовая защита от CSRF для форм.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # APScheduler: авто-закрытие циклов по дедлайну.
    SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "1") not in ("0", "false", "False")
    SCHEDULER_INTERVAL_MIN = int(os.environ.get("SCHEDULER_INTERVAL_MIN", "5"))
