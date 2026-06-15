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
