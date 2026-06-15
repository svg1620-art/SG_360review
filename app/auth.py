"""Аутентификация админа: регистрация, вход, выход, сессии."""
import functools

import psycopg
from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .seeds.default_competencies import seed_default_competencies

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_logged_in_admin():
    """Подгружает текущего админа и его company_id из сессии в g."""
    g.admin = None
    g.company_id = None
    g.plan = None
    admin_id = session.get("admin_id")
    if admin_id is not None:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.company_id, a.email, a.full_name, c.plan
                FROM admins a JOIN companies c ON c.id = a.company_id
                WHERE a.id = %s
                """,
                (admin_id,),
            )
            g.admin = cur.fetchone()
        if g.admin is not None:
            g.company_id = g.admin["company_id"]
            g.plan = g.admin["plan"]


def login_required(view):
    """Пускает только аутентифицированного админа."""

    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.admin is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.admin is not None:
        return redirect(url_for("employees.index"))
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None
        if not company_name or not email or not password:
            error = "Заполните название компании, email и пароль."
        elif len(password) < 8:
            error = "Пароль должен быть не короче 8 символов."

        if error is None:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        "INSERT INTO companies (name) VALUES (%s) RETURNING id",
                        (company_name,),
                    )
                    company_id = cur.fetchone()["id"]
                    cur.execute(
                        """
                        INSERT INTO admins (company_id, email, password_hash, full_name)
                        VALUES (%s, %s, %s, %s) RETURNING id
                        """,
                        (
                            company_id,
                            email,
                            generate_password_hash(password),
                            full_name or None,
                        ),
                    )
                    admin_id = cur.fetchone()["id"]
                # Дефолтный шаблон компетенций для новой компании (раздел 10 ТЗ).
                seed_default_competencies(db, company_id)
            except psycopg.errors.UniqueViolation:
                db.rollback()
                error = "Админ с таким email уже зарегистрирован."
            else:
                session.clear()
                session["admin_id"] = admin_id
                return redirect(url_for("employees.index"))

        flash(error)

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.admin is not None:
        return redirect(url_for("employees.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash FROM admins WHERE email = %s", (email,)
            )
            admin = cur.fetchone()
        if admin is not None and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            return redirect(url_for("employees.index"))
        flash("Неверный email или пароль.")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
