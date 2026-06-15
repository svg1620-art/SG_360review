"""Общие фикстуры pytest. Требуется доступная PostgreSQL через DATABASE_URL."""
import os

# Планировщик в тестах не нужен — выключаем до импорта приложения (конфиг читает env при импорте).
os.environ.setdefault("SCHEDULER_ENABLED", "0")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    """Накатывает схему на тестовую БД один раз за сессию."""
    command.upgrade(AlembicConfig("alembic.ini"), "head")


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def _clean_db(app):
    """Чистим данные перед каждым тестом."""
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("TRUNCATE companies CASCADE")
        db.commit()
    yield


@pytest.fixture
def client(app):
    return app.test_client()
