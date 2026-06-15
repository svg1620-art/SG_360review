"""CRUD сотрудников. Всё скоупится по company_id из сессии."""
from flask import Blueprint, abort, g, render_template, request

from .auth import login_required
from .db import get_db

bp = Blueprint("employees", __name__, url_prefix="/employees")


def _get_owned(emp_id):
    """Возвращает сотрудника, только если он принадлежит компании админа."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM employees WHERE id = %s AND company_id = %s",
            (emp_id, g.company_id),
        )
        emp = cur.fetchone()
    if emp is None:
        abort(404)
    return emp


@bp.route("/")
@login_required
def index():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM employees WHERE company_id = %s ORDER BY full_name",
            (g.company_id,),
        )
        employees = cur.fetchall()
    return render_template("employees/index.html", employees=employees)


@bp.route("/", methods=["POST"])
@login_required
def create():
    f = request.form
    full_name = f.get("full_name", "").strip()
    if not full_name:
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employees (company_id, full_name, email, position, department)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
            """,
            (
                g.company_id,
                full_name,
                f.get("email") or None,
                f.get("position") or None,
                f.get("department") or None,
            ),
        )
        emp = cur.fetchone()
    db.commit()
    return render_template("employees/_row.html", e=emp)


@bp.route("/<int:emp_id>/row")
@login_required
def row(emp_id):
    """Один ряд таблицы (для отмены редактирования)."""
    return render_template("employees/_row.html", e=_get_owned(emp_id))


@bp.route("/<int:emp_id>/edit")
@login_required
def edit(emp_id):
    return render_template("employees/_form_row.html", e=_get_owned(emp_id))


@bp.route("/<int:emp_id>", methods=["POST"])
@login_required
def update(emp_id):
    _get_owned(emp_id)
    f = request.form
    full_name = f.get("full_name", "").strip()
    if not full_name:
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE employees
            SET full_name = %s, email = %s, position = %s, department = %s, active = %s
            WHERE id = %s AND company_id = %s RETURNING *
            """,
            (
                full_name,
                f.get("email") or None,
                f.get("position") or None,
                f.get("department") or None,
                f.get("active") == "on",
                emp_id,
                g.company_id,
            ),
        )
        emp = cur.fetchone()
    db.commit()
    return render_template("employees/_row.html", e=emp)


@bp.route("/<int:emp_id>", methods=["DELETE"])
@login_required
def delete(emp_id):
    _get_owned(emp_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM employees WHERE id = %s AND company_id = %s",
            (emp_id, g.company_id),
        )
    db.commit()
    return ""  # пустой ответ — HTMX удаляет ряд
