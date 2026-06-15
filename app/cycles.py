"""Оценочные циклы: создание, оцениваемые, назначения, запуск.

Жизненный цикл (раздел 5 ТЗ): draft → active → closed.
Здесь покрыты draft и переход в active (запуск).
"""
import secrets

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .db import get_db

bp = Blueprint("cycles", __name__, url_prefix="/cycles")

PERIOD_TYPES = ("quarter", "half_year", "year", "custom")
MANUAL_RELATIONS = ("manager", "peer", "subordinate")
# Порядок и подписи relation для строки прогресса.
PROGRESS_RELATIONS = (
    ("self", "самооценка"),
    ("manager", "руководитель"),
    ("peer", "коллеги"),
    ("subordinate", "подчинённые"),
)


def _draft_token():
    """Плейсхолдер-токен на этапе draft (не раздаётся; перевыпускается при запуске)."""
    return "draft-" + secrets.token_urlsafe(16)


# --- helpers с проверкой принадлежности компании --------------------------


def _get_owned_cycle(cycle_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM cycles WHERE id = %s AND company_id = %s",
            (cycle_id, g.company_id),
        )
        cycle = cur.fetchone()
    if cycle is None:
        abort(404)
    return cycle


def _get_owned_employee(emp_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, full_name FROM employees WHERE id = %s AND company_id = %s",
            (emp_id, g.company_id),
        )
        emp = cur.fetchone()
    if emp is None:
        abort(404)
    return emp


def _get_owned_subject(cycle_id, subject_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT cs.id, cs.employee_id
            FROM cycle_subjects cs
            JOIN cycles c ON c.id = cs.cycle_id
            WHERE cs.id = %s AND cs.cycle_id = %s AND c.company_id = %s
            """,
            (subject_id, cycle_id, g.company_id),
        )
        subj = cur.fetchone()
    if subj is None:
        abort(404)
    return subj


def _assignments_for_subject(subject_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.subject_id, a.relation, a.status, a.token,
                   ev.full_name AS evaluator_name
            FROM assignments a
            JOIN employees ev ON ev.id = a.evaluator_id
            WHERE a.subject_id = %s
            ORDER BY a.relation, ev.full_name
            """,
            (subject_id,),
        )
        return cur.fetchall()


def _active_employees():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, full_name FROM employees WHERE company_id = %s AND active = true ORDER BY full_name",
            (g.company_id,),
        )
        return cur.fetchall()


# --- Циклы ----------------------------------------------------------------


@bp.route("/")
@login_required
def index():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT c.*,
                (SELECT count(*) FROM cycle_subjects cs WHERE cs.cycle_id = c.id) AS subj_count
            FROM cycles c
            WHERE c.company_id = %s
            ORDER BY c.created_at DESC
            """,
            (g.company_id,),
        )
        cycles = cur.fetchall()
    return render_template("cycles/index.html", cycles=cycles)


@bp.route("/", methods=["POST"])
@login_required
def create():
    title = request.form.get("title", "").strip()
    period_type = request.form.get("period_type", "custom")
    if not title or period_type not in PERIOD_TYPES:
        abort(400)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cycles (company_id, title, period_type, period_label, deadline)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (
                g.company_id,
                title,
                period_type,
                request.form.get("period_label") or None,
                request.form.get("deadline") or None,
            ),
        )
        cycle_id = cur.fetchone()["id"]
    db.commit()
    return redirect(url_for("cycles.detail", cycle_id=cycle_id))


@bp.route("/<int:cycle_id>")
@login_required
def detail(cycle_id):
    cycle = _get_owned_cycle(cycle_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT cs.id AS subject_id, cs.employee_id, e.full_name
            FROM cycle_subjects cs
            JOIN employees e ON e.id = cs.employee_id
            WHERE cs.cycle_id = %s
            ORDER BY e.full_name
            """,
            (cycle_id,),
        )
        subjects = cur.fetchall()
        cur.execute(
            """
            SELECT a.id, a.subject_id, a.relation, a.status, a.token,
                   ev.full_name AS evaluator_name
            FROM assignments a
            JOIN employees ev ON ev.id = a.evaluator_id
            WHERE a.cycle_id = %s
            ORDER BY a.relation, ev.full_name
            """,
            (cycle_id,),
        )
        assignments = cur.fetchall()
        # Кандидаты в оцениваемые — активные, ещё не добавленные.
        cur.execute(
            """
            SELECT id, full_name FROM employees
            WHERE company_id = %s AND active = true
              AND id NOT IN (SELECT employee_id FROM cycle_subjects WHERE cycle_id = %s)
            ORDER BY full_name
            """,
            (g.company_id, cycle_id),
        )
        candidate_subjects = cur.fetchall()
        # Прогресс: сдавшие по каждому relation у каждого оцениваемого.
        cur.execute(
            """
            SELECT subject_id, relation, count(*) AS total,
                   count(*) FILTER (WHERE status = 'submitted') AS submitted
            FROM assignments WHERE cycle_id = %s
            GROUP BY subject_id, relation
            """,
            (cycle_id,),
        )
        prog_rows = cur.fetchall()
    assignments_by_subject = {}
    for a in assignments:
        assignments_by_subject.setdefault(a["subject_id"], []).append(a)

    prog = {}
    for p in prog_rows:
        prog.setdefault(p["subject_id"], {})[p["relation"]] = (p["submitted"], p["total"])
    progress_line = {}
    for sid, rels in prog.items():
        progress_line[sid] = " · ".join(
            f"{label} {rels[key][0]}/{rels[key][1]}"
            for key, label in PROGRESS_RELATIONS
            if key in rels
        )

    return render_template(
        "cycles/detail.html",
        cycle=cycle,
        subjects=subjects,
        assignments_by_subject=assignments_by_subject,
        candidate_subjects=candidate_subjects,
        employees=_active_employees(),
        progress_line=progress_line,
    )


# --- Оцениваемые ----------------------------------------------------------


@bp.route("/<int:cycle_id>/subjects", methods=["POST"])
@login_required
def add_subject(cycle_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "draft":
        abort(409)
    employee_id = request.form.get("employee_id", type=int)
    if not employee_id:
        abort(400)
    emp = _get_owned_employee(employee_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM cycle_subjects WHERE cycle_id = %s AND employee_id = %s",
            (cycle_id, employee_id),
        )
        if cur.fetchone():
            abort(409)
        cur.execute(
            "INSERT INTO cycle_subjects (cycle_id, employee_id) VALUES (%s, %s) RETURNING id",
            (cycle_id, employee_id),
        )
        subject_id = cur.fetchone()["id"]
        # Самооценка добавляется автоматически (раздел 5 ТЗ).
        cur.execute(
            """
            INSERT INTO assignments (cycle_id, subject_id, evaluator_id, relation, token)
            VALUES (%s, %s, %s, 'self', %s)
            """,
            (cycle_id, subject_id, employee_id, _draft_token()),
        )
    db.commit()
    subject = {"subject_id": subject_id, "employee_id": employee_id, "full_name": emp["full_name"]}
    return render_template(
        "cycles/_subject.html",
        s=subject,
        assignments=_assignments_for_subject(subject_id),
        employees=_active_employees(),
        cycle=cycle,
        progress="",  # в draft строка прогресса не показывается
    )


@bp.route("/<int:cycle_id>/subjects/<int:subject_id>", methods=["DELETE"])
@login_required
def delete_subject(cycle_id, subject_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "draft":
        abort(409)
    _get_owned_subject(cycle_id, subject_id)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM cycle_subjects WHERE id = %s AND cycle_id = %s",
            (subject_id, cycle_id),
        )
    db.commit()
    return ""


# --- Назначения оценщиков -------------------------------------------------


@bp.route("/<int:cycle_id>/subjects/<int:subject_id>/assignments", methods=["POST"])
@login_required
def add_assignment(cycle_id, subject_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "draft":
        abort(409)
    subj = _get_owned_subject(cycle_id, subject_id)
    evaluator_id = request.form.get("evaluator_id", type=int)
    relation = request.form.get("relation", "")
    if not evaluator_id or relation not in MANUAL_RELATIONS:
        abort(400)
    evaluator = _get_owned_employee(evaluator_id)
    if evaluator_id == subj["employee_id"]:
        abort(400)  # сам себя оценивает только через self (авто)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM assignments WHERE cycle_id = %s AND subject_id = %s AND evaluator_id = %s",
            (cycle_id, subject_id, evaluator_id),
        )
        if cur.fetchone():
            abort(409)
        cur.execute(
            """
            INSERT INTO assignments (cycle_id, subject_id, evaluator_id, relation, token)
            VALUES (%s, %s, %s, %s, %s) RETURNING id, subject_id, relation, status, token
            """,
            (cycle_id, subject_id, evaluator_id, relation, _draft_token()),
        )
        a = cur.fetchone()
    db.commit()
    a["evaluator_name"] = evaluator["full_name"]
    return render_template("cycles/_assignment.html", a=a, cycle=cycle)


@bp.route("/<int:cycle_id>/assignments/<int:assignment_id>", methods=["DELETE"])
@login_required
def delete_assignment(cycle_id, assignment_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "draft":
        abort(409)
    db = get_db()
    with db.cursor() as cur:
        # Удаляем только не-self назначение и только в своей компании.
        cur.execute(
            """
            DELETE FROM assignments a
            USING cycles c
            WHERE a.id = %s AND a.cycle_id = %s
              AND c.id = a.cycle_id AND c.company_id = %s
              AND a.relation <> 'self'
            """,
            (assignment_id, cycle_id, g.company_id),
        )
        deleted = cur.rowcount
    db.commit()
    if deleted == 0:
        abort(404)
    return ""


# --- Запуск цикла ---------------------------------------------------------


@bp.route("/<int:cycle_id>/launch", methods=["POST"])
@login_required
def launch(cycle_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "draft":
        abort(409)
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM cycle_subjects WHERE cycle_id = %s", (cycle_id,))
        n_subjects = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT count(*) AS n
            FROM competencies c JOIN questions q ON q.competency_id = c.id
            WHERE c.company_id = %s AND c.active = true
            """,
            (g.company_id,),
        )
        n_questions = cur.fetchone()["n"]

    if n_subjects == 0:
        flash("Добавьте хотя бы одного оцениваемого перед запуском.")
        return redirect(url_for("cycles.detail", cycle_id=cycle_id))
    if n_questions == 0:
        flash("Нет активных вопросов для анкеты — добавьте компетенции и вопросы.")
        return redirect(url_for("cycles.detail", cycle_id=cycle_id))

    with db.cursor() as cur:
        # 1. Снимок активных компетенций/вопросов на момент запуска.
        cur.execute(
            """
            INSERT INTO cycle_questions
                (cycle_id, competency_name, question_text, qtype, comp_order, q_order)
            SELECT %s, c.name, q.text, q.qtype, c.sort_order, q.sort_order
            FROM competencies c
            JOIN questions q ON q.competency_id = c.id
            WHERE c.company_id = %s AND c.active = true
            ORDER BY c.sort_order, c.id, q.sort_order, q.id
            """,
            (cycle_id, g.company_id),
        )
        # 2. Боевые токены на каждое назначение.
        cur.execute("SELECT id FROM assignments WHERE cycle_id = %s", (cycle_id,))
        for r in cur.fetchall():
            cur.execute(
                "UPDATE assignments SET token = %s WHERE id = %s",
                (secrets.token_urlsafe(32), r["id"]),
            )
        # 3. Перевод в active.
        cur.execute(
            "UPDATE cycles SET status = 'active', starts_at = now() WHERE id = %s AND company_id = %s",
            (cycle_id, g.company_id),
        )
    db.commit()
    flash("Цикл запущен. Токен-ссылки доступны на странице цикла.")
    return redirect(url_for("cycles.detail", cycle_id=cycle_id))


@bp.route("/<int:cycle_id>/close", methods=["POST"])
@login_required
def close(cycle_id):
    cycle = _get_owned_cycle(cycle_id)
    if cycle["status"] != "active":
        abort(409)
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE cycles SET status = 'closed' WHERE id = %s AND company_id = %s",
            (cycle_id, g.company_id),
        )
    db.commit()
    flash("Цикл закрыт. Отчёты доступны.")
    return redirect(url_for("cycles.detail", cycle_id=cycle_id))
