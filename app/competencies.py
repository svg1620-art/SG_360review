"""CRUD компетенций и вопросов. Всё скоупится по company_id из сессии."""
from flask import Blueprint, abort, g, render_template, request

from .auth import login_required
from .db import get_db

bp = Blueprint("competencies", __name__, url_prefix="/competencies")


def _get_owned_competency(comp_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM competencies WHERE id = %s AND company_id = %s",
            (comp_id, g.company_id),
        )
        comp = cur.fetchone()
    if comp is None:
        abort(404)
    return comp


def _questions_for(comp_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM questions WHERE competency_id = %s ORDER BY sort_order, id",
            (comp_id,),
        )
        return cur.fetchall()


def _get_owned_question(q_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT q.* FROM questions q
            JOIN competencies c ON c.id = q.competency_id
            WHERE q.id = %s AND c.company_id = %s
            """,
            (q_id, g.company_id),
        )
        q = cur.fetchone()
    if q is None:
        abort(404)
    return q


# --- Компетенции ---------------------------------------------------------


@bp.route("/")
@login_required
def index():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM competencies WHERE company_id = %s ORDER BY sort_order, id",
            (g.company_id,),
        )
        comps = cur.fetchall()
        cur.execute(
            """
            SELECT q.* FROM questions q
            JOIN competencies c ON c.id = q.competency_id
            WHERE c.company_id = %s
            ORDER BY q.sort_order, q.id
            """,
            (g.company_id,),
        )
        questions = cur.fetchall()
    questions_by_comp = {}
    for q in questions:
        questions_by_comp.setdefault(q["competency_id"], []).append(q)
    return render_template(
        "competencies/index.html", comps=comps, questions_by_comp=questions_by_comp
    )


@bp.route("/<int:comp_id>")
@login_required
def show(comp_id):
    comp = _get_owned_competency(comp_id)
    return render_template(
        "competencies/_competency.html", c=comp, questions=_questions_for(comp_id)
    )


@bp.route("/<int:comp_id>/edit")
@login_required
def edit(comp_id):
    return render_template("competencies/_competency_form.html", c=_get_owned_competency(comp_id))


@bp.route("/", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not name:
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO competencies (company_id, name, description, sort_order)
            VALUES (%s, %s, %s,
                (SELECT COALESCE(MAX(sort_order) + 1, 0)
                 FROM competencies WHERE company_id = %s))
            RETURNING *
            """,
            (g.company_id, name, request.form.get("description") or None, g.company_id),
        )
        comp = cur.fetchone()
    db.commit()
    return render_template("competencies/_competency.html", c=comp, questions=[])


@bp.route("/<int:comp_id>", methods=["POST"])
@login_required
def update(comp_id):
    _get_owned_competency(comp_id)
    name = request.form.get("name", "").strip()
    if not name:
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE competencies SET name = %s, description = %s, active = %s
            WHERE id = %s AND company_id = %s RETURNING *
            """,
            (
                name,
                request.form.get("description") or None,
                request.form.get("active") == "on",
                comp_id,
                g.company_id,
            ),
        )
        comp = cur.fetchone()
    db.commit()
    return render_template(
        "competencies/_competency.html", c=comp, questions=_questions_for(comp_id)
    )


@bp.route("/<int:comp_id>", methods=["DELETE"])
@login_required
def delete(comp_id):
    _get_owned_competency(comp_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM competencies WHERE id = %s AND company_id = %s",
            (comp_id, g.company_id),
        )
    db.commit()
    return ""


# --- Вопросы -------------------------------------------------------------


@bp.route("/<int:comp_id>/questions", methods=["POST"])
@login_required
def create_question(comp_id):
    _get_owned_competency(comp_id)
    text = request.form.get("text", "").strip()
    qtype = request.form.get("qtype", "rating")
    if not text or qtype not in ("rating", "open"):
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO questions (competency_id, text, qtype, sort_order)
            VALUES (%s, %s, %s,
                (SELECT COALESCE(MAX(sort_order) + 1, 0)
                 FROM questions WHERE competency_id = %s))
            RETURNING *
            """,
            (comp_id, text, qtype, comp_id),
        )
        q = cur.fetchone()
    db.commit()
    return render_template("competencies/_question.html", q=q)


@bp.route("/questions/<int:q_id>")
@login_required
def show_question(q_id):
    return render_template("competencies/_question.html", q=_get_owned_question(q_id))


@bp.route("/questions/<int:q_id>/edit")
@login_required
def edit_question(q_id):
    return render_template("competencies/_question_form.html", q=_get_owned_question(q_id))


@bp.route("/questions/<int:q_id>", methods=["POST"])
@login_required
def update_question(q_id):
    _get_owned_question(q_id)
    text = request.form.get("text", "").strip()
    qtype = request.form.get("qtype", "rating")
    if not text or qtype not in ("rating", "open"):
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE questions SET text = %s, qtype = %s WHERE id = %s RETURNING *",
            (text, qtype, q_id),
        )
        q = cur.fetchone()
    db.commit()
    return render_template("competencies/_question.html", q=q)


@bp.route("/questions/<int:q_id>", methods=["DELETE"])
@login_required
def delete_question(q_id):
    _get_owned_question(q_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM questions WHERE id = %s", (q_id,))
    db.commit()
    return ""
