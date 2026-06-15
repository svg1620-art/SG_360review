"""Фабрика приложения SG_360review."""
from flask import Flask, g, redirect, url_for

from . import auth, billing, cli, competencies, cycles, db, employees, report, respond, scheduler
from .config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # В проде секрет обязателен — не пускаем дефолтный/пустой.
    if app.config["APP_ENV"] == "production" and app.config["SECRET_KEY"] in (
        None,
        "",
        "dev-secret-change-me",
    ):
        raise RuntimeError("В production обязательна переменная окружения SECRET_KEY.")

    db.init_app(app)
    cli.init_app(app)
    scheduler.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(competencies.bp)
    app.register_blueprint(cycles.bp)
    app.register_blueprint(respond.bp)
    app.register_blueprint(report.bp)
    app.register_blueprint(billing.bp)

    @app.route("/")
    def home():
        if getattr(g, "admin", None) is not None:
            return redirect(url_for("employees.index"))
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
