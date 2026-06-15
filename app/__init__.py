"""Фабрика приложения SG_360review."""
from flask import Flask, g, redirect, url_for

from . import auth, cli, competencies, cycles, db, employees, respond
from .config import Config


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    cli.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(competencies.bp)
    app.register_blueprint(cycles.bp)
    app.register_blueprint(respond.bp)

    @app.route("/")
    def home():
        if getattr(g, "admin", None) is not None:
            return redirect(url_for("employees.index"))
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
