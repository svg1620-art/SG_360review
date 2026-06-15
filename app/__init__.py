"""Фабрика приложения SG_360review."""
from flask import Flask

from . import cli, db
from .config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    cli.init_app(app)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
