"""Хелперы для тестов: обёртки над HTTP-эндпоинтами и БД."""
import re


def register(client, name="Acme", email="a@a.io", pw="password1"):
    return client.post(
        "/register",
        data={"company_name": name, "email": email, "password": pw},
    )


def add_employee(client, name, email=""):
    r = client.post("/employees/", data={"full_name": name, "email": email})
    return re.search(r'id="emp-(\d+)"', r.get_data(as_text=True)).group(1)


def create_cycle(client, title="C", period="quarter", deadline=None):
    data = {"title": title, "period_type": period}
    if deadline:
        data["deadline"] = deadline
    r = client.post("/cycles/", data=data)
    return re.search(r"/cycles/(\d+)", r.headers["Location"]).group(1)


def add_subject(client, cyc, emp):
    r = client.post(f"/cycles/{cyc}/subjects", data={"employee_id": emp})
    m = re.search(r'id="subject-(\d+)"', r.get_data(as_text=True))
    return m.group(1) if m else None


def add_assignment(client, cyc, sb, emp, relation):
    return client.post(
        f"/cycles/{cyc}/subjects/{sb}/assignments",
        data={"evaluator_id": emp, "relation": relation},
    )


def set_plan(app, company_name, plan):
    from app.db import get_db

    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("UPDATE companies SET plan = %s WHERE name = %s", (plan, company_name))
        db.commit()


def fill_and_submit(app, cyc, value_for):
    """Заполняет все rating-вопросы и помечает назначения submitted.

    value_for(relation, comp_index) -> рейтинг 1..5.
    """
    from app.db import get_db

    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, competency_name, qtype FROM cycle_questions WHERE cycle_id=%s ORDER BY id",
                (cyc,),
            )
            cqs = cur.fetchall()
            ci, order = {}, []
            for q in cqs:
                if q["competency_name"] not in ci:
                    ci[q["competency_name"]] = len(order)
                    order.append(q["competency_name"])
            rating = [(q["id"], ci[q["competency_name"]]) for q in cqs if q["qtype"] == "rating"]
            cur.execute("SELECT id, relation FROM assignments WHERE cycle_id=%s", (cyc,))
            for a in cur.fetchall():
                for qid, cidx in rating:
                    cur.execute(
                        "INSERT INTO responses (assignment_id, cycle_question_id, rating) VALUES (%s,%s,%s)",
                        (a["id"], qid, value_for(a["relation"], cidx)),
                    )
                cur.execute(
                    "UPDATE assignments SET status='submitted', submitted_at=now() WHERE id=%s",
                    (a["id"],),
                )
        db.commit()
