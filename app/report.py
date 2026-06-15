"""Движок отчёта по оцениваемому (разделы 7–8 ТЗ). Видит только админ.

Агрегат строится строго по правилам анонимности:
- self / manager — не анонимны, показываются всегда;
- peer / subordinate — отдельные столбцы только при достижении порога;
- «другие» = пул анонимных источников (peer + subordinate); показывается, только
  если суммарно ответивших >= порога И это не позволяет вычесть скрытую подгруппу.
"""
import random
from collections import defaultdict

from flask import Blueprint, abort, flash, g, redirect, render_template, url_for

from .auth import login_required
from .db import get_db
from .limits import is_pro

bp = Blueprint("report", __name__)

BLIND_DELTA = 1.0  # порог Δ для слепых/скрытых зон (шкала 1–5)
TOP_N = 3          # сколько компетенций в «сильные»/«рост»


def _others_visible(p, s, threshold):
    """Можно ли показать композит «другие» (peer+sub) без утечки скрытой подгруппы."""
    if p + s < threshold:
        return False
    # Утечка: одна анонимная группа показана (>=порога), другая непуста, но скрыта (<порога).
    if (p >= threshold and 0 < s < threshold) or (s >= threshold and 0 < p < threshold):
        return False
    return True


def _mean(pair):
    return pair[0] / pair[1] if pair[1] else None


def _rating_aggregate(conn, cycle_id, subject_id, threshold):
    """Средние по компетенциям и источникам + флаги видимости. Переиспользуется для динамики."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT competency_name FROM cycle_questions WHERE cycle_id = %s ORDER BY id",
            (cycle_id,),
        )
        comp_order, seen = [], set()
        for r in cur.fetchall():
            if r["competency_name"] not in seen:
                seen.add(r["competency_name"])
                comp_order.append(r["competency_name"])

        cur.execute(
            """
            SELECT relation, count(*) AS n FROM assignments
            WHERE cycle_id = %s AND subject_id = %s AND status = 'submitted'
            GROUP BY relation
            """,
            (cycle_id, subject_id),
        )
        counts = {row["relation"]: row["n"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT a.relation, cq.competency_name, r.rating
            FROM responses r
            JOIN assignments a ON a.id = r.assignment_id
            JOIN cycle_questions cq ON cq.id = r.cycle_question_id
            WHERE a.cycle_id = %s AND a.subject_id = %s AND a.status = 'submitted'
              AND cq.qtype = 'rating' AND r.rating IS NOT NULL
            """,
            (cycle_id, subject_id),
        )
        rating_rows = cur.fetchall()

    p, s = counts.get("peer", 0), counts.get("subordinate", 0)
    peer_visible, sub_visible = p >= threshold, s >= threshold
    others_visible = _others_visible(p, s, threshold)

    acc = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # comp -> relation -> [sum, n]
    others = defaultdict(lambda: [0, 0])                    # comp -> [sum, n] для peer+sub
    for row in rating_rows:
        comp, rel, val = row["competency_name"], row["relation"], row["rating"]
        acc[comp][rel][0] += val
        acc[comp][rel][1] += 1
        if rel in ("peer", "subordinate"):
            others[comp][0] += val
            others[comp][1] += 1

    means = {}
    for comp in comp_order:
        src = acc.get(comp, {})
        means[comp] = {
            "self": _mean(src["self"]) if "self" in src else None,
            "manager": _mean(src["manager"]) if "manager" in src else None,
            "peer": _mean(src["peer"]) if ("peer" in src and peer_visible) else None,
            "subordinate": _mean(src["subordinate"]) if ("subordinate" in src and sub_visible) else None,
            "others": _mean(others[comp]) if (comp in others and others_visible) else None,
        }
    return {
        "means": means,
        "counts": counts,
        "competencies": comp_order,
        "peer_visible": peer_visible,
        "sub_visible": sub_visible,
        "others_visible": others_visible,
    }


def _open_answers(conn, cycle_id, subject_id, peer_visible, sub_visible):
    """Открытые ответы, сгруппированные по вопросу; peer/sub — анонимно и в перемешку."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, competency_name, question_text FROM cycle_questions WHERE cycle_id = %s AND qtype = 'open' ORDER BY id",
            (cycle_id,),
        )
        questions = cur.fetchall()
        cur.execute(
            """
            SELECT a.relation, r.cycle_question_id AS qid, r.text_answer
            FROM responses r
            JOIN assignments a ON a.id = r.assignment_id
            JOIN cycle_questions cq ON cq.id = r.cycle_question_id
            WHERE a.cycle_id = %s AND a.subject_id = %s AND a.status = 'submitted'
              AND cq.qtype = 'open' AND r.text_answer IS NOT NULL
            """,
            (cycle_id, subject_id),
        )
        rows = cur.fetchall()

    by_q = defaultdict(lambda: {"self": [], "manager": [], "peers": [], "subs": []})
    for row in rows:
        bucket = by_q[row["qid"]]
        rel, text = row["relation"], row["text_answer"]
        if rel == "self":
            bucket["self"].append(text)
        elif rel == "manager":
            bucket["manager"].append(text)
        elif rel == "peer" and peer_visible:
            bucket["peers"].append(text)
        elif rel == "subordinate" and sub_visible:
            bucket["subs"].append(text)

    blocks = []
    for q in questions:
        b = by_q.get(q["id"], {"self": [], "manager": [], "peers": [], "subs": []})
        random.shuffle(b["peers"])  # без привязки к автору, в перемешанном порядке
        random.shuffle(b["subs"])
        if b["self"] or b["manager"] or b["peers"] or b["subs"]:
            blocks.append(
                {
                    "competency": q["competency_name"],
                    "question": q["question_text"],
                    "self": b["self"],
                    "manager": b["manager"],
                    "peers": b["peers"],
                    "subs": b["subs"],
                }
            )
    return blocks


def _dynamics(conn, company_id, employee_id, threshold, comp_order):
    """Средний балл «другие» по компетенциям от закрытого цикла к закрытому циклу."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.title, c.period_label, cs.id AS subject_id
            FROM cycles c
            JOIN cycle_subjects cs ON cs.cycle_id = c.id
            WHERE c.company_id = %s AND cs.employee_id = %s AND c.status = 'closed'
            ORDER BY c.starts_at NULLS LAST, c.id
            """,
            (company_id, employee_id),
        )
        cycles = cur.fetchall()
    if len(cycles) < 2:
        return None

    labels = [c["period_label"] or c["title"] for c in cycles]
    series = {comp: [] for comp in comp_order}
    for c in cycles:
        agg = _rating_aggregate(conn, c["id"], c["subject_id"], threshold)
        for comp in comp_order:
            val = agg["means"].get(comp, {}).get("others") if agg else None
            series[comp].append(round(val, 2) if val is not None else None)
    # Оставляем только компетенции, где есть хотя бы одна точка.
    series = {k: v for k, v in series.items() if any(x is not None for x in v)}
    return {"labels": labels, "series": series}


@bp.route("/cycles/<int:cycle_id>/subjects/<int:subject_id>/report")
@login_required
def report(cycle_id, subject_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM cycles WHERE id = %s AND company_id = %s",
            (cycle_id, g.company_id),
        )
        cycle = cur.fetchone()
        if cycle is None:
            abort(404)
        cur.execute(
            """
            SELECT cs.employee_id, e.full_name
            FROM cycle_subjects cs JOIN employees e ON e.id = cs.employee_id
            WHERE cs.id = %s AND cs.cycle_id = %s
            """,
            (subject_id, cycle_id),
        )
        subj = cur.fetchone()
        if subj is None:
            abort(404)
        cur.execute("SELECT anon_threshold FROM companies WHERE id = %s", (g.company_id,))
        threshold = cur.fetchone()["anon_threshold"]

    if cycle["status"] != "closed":
        flash("Отчёт доступен после закрытия цикла.")
        return redirect(url_for("cycles.detail", cycle_id=cycle_id))

    agg = _rating_aggregate(db, cycle_id, subject_id, threshold)
    means, comp_order = agg["means"], agg["competencies"]

    # Радар: компетенции, где есть и self, и «другие».
    radar_comps = [c for c in comp_order if means[c]["self"] is not None and means[c]["others"] is not None]
    radar = {
        "labels": radar_comps,
        "self": [round(means[c]["self"], 2) for c in radar_comps],
        "others": [round(means[c]["others"], 2) for c in radar_comps],
        "manager": [round(means[c]["manager"], 2) if means[c]["manager"] is not None else None for c in radar_comps],
    }
    has_manager_line = any(v is not None for v in radar["manager"])

    # Зоны — по баллу «другие».
    others_pairs = [(c, means[c]["others"]) for c in comp_order if means[c]["others"] is not None]
    strong = sorted(others_pairs, key=lambda x: -x[1])[:TOP_N]
    growth = sorted(others_pairs, key=lambda x: x[1])[:TOP_N]
    blind, hidden = [], []
    for c in comp_order:
        sv, ov = means[c]["self"], means[c]["others"]
        if sv is None or ov is None:
            continue
        if sv - ov > BLIND_DELTA:
            blind.append((c, sv, ov, sv - ov))
        elif ov - sv > BLIND_DELTA:
            hidden.append((c, sv, ov, ov - sv))
    blind.sort(key=lambda x: -x[3])
    hidden.sort(key=lambda x: -x[3])

    open_blocks = _open_answers(db, cycle_id, subject_id, agg["peer_visible"], agg["sub_visible"])
    # Сравнение динамики — только на Pro (раздел 9 ТЗ).
    dynamics = _dynamics(db, g.company_id, subj["employee_id"], threshold, comp_order) if is_pro() else None

    return render_template(
        "report/report.html",
        cycle=cycle,
        subject_name=subj["full_name"],
        threshold=threshold,
        counts=agg["counts"],
        competencies=comp_order,
        means=means,
        peer_visible=agg["peer_visible"],
        sub_visible=agg["sub_visible"],
        others_visible=agg["others_visible"],
        radar=radar,
        has_manager_line=has_manager_line,
        zones={"strong": strong, "growth": growth, "blind": blind, "hidden": hidden},
        open_blocks=open_blocks,
        dynamics=dynamics,
    )
