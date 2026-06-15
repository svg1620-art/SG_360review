"""Подключение к PostgreSQL через psycopg 3. Соединение живёт в рамках запроса."""
import psycopg
from psycopg.rows import dict_row
from flask import current_app, g


def get_db():
    """Возвращает psycopg-подключение, привязанное к текущему запросу."""
    if "db" not in g:
        g.db = psycopg.connect(
            current_app.config["DATABASE_URL"], row_factory=dict_row
        )
    return g.db


def close_db(e=None):
    """Закрывает подключение в конце запроса."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
