from app.db import get_db
from tests.helpers import add_assignment, add_employee, add_subject, create_cycle, register


def _launched(app, client):
    register(client)
    subj = add_employee(client, "Субъект")
    peer = add_employee(client, "Коллега")
    cyc = create_cycle(client, "Q1")
    sb = add_subject(client, cyc, subj)
    add_assignment(client, cyc, sb, peer, "peer")
    client.post(f"/cycles/{cyc}/launch")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT id, token FROM assignments WHERE cycle_id=%s AND relation='peer'", (cyc,))
            a = cur.fetchone()
            cur.execute("SELECT id, qtype FROM cycle_questions WHERE cycle_id=%s ORDER BY id", (cyc,))
            qs = cur.fetchall()
    rating = [q["id"] for q in qs if q["qtype"] == "rating"]
    return a["id"], a["token"], rating


def test_draft_token_404(app, client):
    register(client)
    subj = add_employee(client, "S")
    peer = add_employee(client, "P")
    cyc = create_cycle(client, "Q")
    sb = add_subject(client, cyc, subj)
    add_assignment(client, cyc, sb, peer, "peer")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT token FROM assignments WHERE cycle_id=%s AND relation='peer'", (cyc,))
            tok = cur.fetchone()["token"]
    assert app.test_client().get(f"/r/{tok}").status_code == 404  # черновик


def test_autosave_status_and_submit(app, client):
    aid, tok, rating = _launched(app, client)
    pub = app.test_client()
    assert pub.get(f"/r/{tok}").status_code == 200
    # некорректный рейтинг
    assert pub.post(f"/r/{tok}/answer", data={"cycle_question_id": rating[0], "rating": "6"}).status_code == 400
    # первый ответ -> in_progress
    pub.post(f"/r/{tok}/answer", data={"cycle_question_id": rating[0], "rating": "4"})
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status FROM assignments WHERE id=%s", (aid,))
            assert cur.fetchone()["status"] == "in_progress"
    # неполный submit не проходит
    pub.post(f"/r/{tok}/submit")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status FROM assignments WHERE id=%s", (aid,))
            assert cur.fetchone()["status"] == "in_progress"
    # заполняем все рейтинги и отправляем
    for qid in rating:
        pub.post(f"/r/{tok}/answer", data={"cycle_question_id": qid, "rating": "5"})
    pub.post(f"/r/{tok}/submit")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status, submitted_at FROM assignments WHERE id=%s", (aid,))
            row = cur.fetchone()
            assert row["status"] == "submitted" and row["submitted_at"] is not None
    # после submit ответы запрещены
    assert pub.post(f"/r/{tok}/answer", data={"cycle_question_id": rating[0], "rating": "1"}).status_code == 409
