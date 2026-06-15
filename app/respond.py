"""Анкета оценщика по токен-ссылке /r/<token>. Без логина — доступ по секрету.

Статусы назначения: pending → in_progress (первый ответ) → submitted (отправка).
Доступ только пока цикл active; токен — единственная авторизация.
"""
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .db import get_db

bp = Blueprint("respond", __name__)


def _load_assignment(token):
    """Назначение по токену + контекст цикла/оцениваемого. Без скоупа по компании — авторизует токен."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.cycle_id, a.relation, a.status,
                   c.status AS cycle_status, c.title AS cycle_title,
                   subj.full_name AS subject_name
            FROM assignments a
            JOIN cycles c ON c.id = a.cycle_id
            JOIN cycle_subjects cs ON cs.id = a.subject_id
            JOIN employees subj ON subj.id = cs.employee_id
            WHERE a.token = %s
            """,
            (token,),
        )
        a = cur.fetchone()
    if a is None:
        abort(404)
    return a


def _get_cycle_question(cycle_id, cq_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM cycle_questions WHERE id = %s AND cycle_id = %s",
            (cq_id, cycle_id),
        )
        cq = cur.fetchone()
    if cq is None:
        abort(404)
    return cq


@bp.route("/r/<token>")
def form(token):
    a = _load_assignment(token)
    if a["cycle_status"] == "draft":
        abort(404)  # черновик — ссылки ещё не активны

    db = get_db()
    with db.cursor() as cur:
        # Порядок снимка = порядок вставки (id), компетенции идут блоками.
        cur.execute(
            "SELECT * FROM cycle_questions WHERE cycle_id = %s ORDER BY id",
            (a["cycle_id"],),
        )
        questions = cur.fetchall()
        cur.execute(
            "SELECT cycle_question_id, rating, text_answer FROM responses WHERE assignment_id = %s",
            (a["id"],),
        )
        answers = {r["cycle_question_id"]: r for r in cur.fetchall()}

    groups = []
    for q in questions:
        if not groups or groups[-1]["name"] != q["competency_name"]:
            groups.append({"name": q["competency_name"], "questions": []})
        groups[-1]["questions"].append(q)

    locked = a["status"] == "submitted" or a["cycle_status"] != "active"
    return render_template(
        "respond/form.html", a=a, groups=groups, answers=answers, token=token, locked=locked
    )


@bp.route("/r/<token>/answer", methods=["POST"])
def answer(token):
    a = _load_assignment(token)
    if a["cycle_status"] != "active" or a["status"] == "submitted":
        abort(409)
    cq_id = request.form.get("cycle_question_id", type=int)
    if not cq_id:
        abort(400)
    cq = _get_cycle_question(a["cycle_id"], cq_id)

    if cq["qtype"] == "rating":
        rating = request.form.get("rating", type=int)
        if rating is None or not (1 <= rating <= 5):
            abort(400)
        text = None
    else:
        text = (request.form.get("text_answer") or "").strip() or None
        rating = None

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO responses (assignment_id, cycle_question_id, rating, text_answer)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (assignment_id, cycle_question_id)
            DO UPDATE SET rating = EXCLUDED.rating, text_answer = EXCLUDED.text_answer
            """,
            (a["id"], cq_id, rating, text),
        )
        # Первый ответ переводит назначение в in_progress.
        cur.execute(
            "UPDATE assignments SET status = 'in_progress' WHERE id = %s AND status = 'pending'",
            (a["id"],),
        )
    db.commit()
    return "✓ сохранено"


@bp.route("/r/<token>/submit", methods=["POST"])
def submit(token):
    a = _load_assignment(token)
    if a["cycle_status"] != "active" or a["status"] == "submitted":
        abort(409)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM cycle_questions WHERE cycle_id = %s AND qtype = 'rating'",
            (a["cycle_id"],),
        )
        total_rating = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT count(*) AS n FROM responses r
            JOIN cycle_questions cq ON cq.id = r.cycle_question_id
            WHERE r.assignment_id = %s AND cq.qtype = 'rating' AND r.rating IS NOT NULL
            """,
            (a["id"],),
        )
        done_rating = cur.fetchone()["n"]

    if done_rating < total_rating:
        flash("Ответьте на все вопросы с оценкой перед отправкой.")
        return redirect(url_for("respond.form", token=token))

    with db.cursor() as cur:
        cur.execute(
            "UPDATE assignments SET status = 'submitted', submitted_at = now() WHERE id = %s",
            (a["id"],),
        )
    db.commit()
    return redirect(url_for("respond.form", token=token))
