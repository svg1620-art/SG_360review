from app.db import get_db
from tests.helpers import add_assignment, add_employee, add_subject, create_cycle, register, set_plan


def _setup(client):
    register(client)
    subj = add_employee(client, "Субъект")
    peer = add_employee(client, "Коллега")
    cyc = create_cycle(client, "Q1")
    sb = add_subject(client, cyc, subj)
    return subj, peer, cyc, sb


def test_add_subject_auto_self(client):
    subj, peer, cyc, sb = _setup(client)
    r = client.post(f"/cycles/{cyc}/subjects/{sb}/assignments", data={"evaluator_id": peer, "relation": "peer"})
    assert "[коллега]" in r.get_data(as_text=True)


def test_self_as_evaluator_and_dup_blocked(client):
    subj, peer, cyc, sb = _setup(client)
    add_assignment(client, cyc, sb, peer, "peer")
    assert add_assignment(client, cyc, sb, peer, "peer").status_code == 409  # дубль
    assert add_assignment(client, cyc, sb, subj, "peer").status_code == 400  # сам себя


def test_launch_snapshot_tokens_and_active(app, client):
    subj, peer, cyc, sb = _setup(client)
    add_assignment(client, cyc, sb, peer, "peer")
    client.post(f"/cycles/{cyc}/launch")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status, starts_at FROM cycles WHERE id=%s", (cyc,))
            row = cur.fetchone()
            assert row["status"] == "active" and row["starts_at"] is not None
            cur.execute("SELECT count(*) AS n FROM cycle_questions WHERE cycle_id=%s", (cyc,))
            assert cur.fetchone()["n"] == 24  # 6 компетенций * 4 вопроса
            cur.execute(
                "SELECT count(*) AS n, count(*) FILTER (WHERE token LIKE 'draft-%%') AS d, "
                "count(DISTINCT token) AS u FROM assignments WHERE cycle_id=%s",
                (cyc,),
            )
            a = cur.fetchone()
            assert a["d"] == 0 and a["u"] == a["n"]  # боевые уникальные токены


def test_mutations_blocked_after_launch(client):
    subj, peer, cyc, sb = _setup(client)
    client.post(f"/cycles/{cyc}/launch")
    assert client.post(f"/cycles/{cyc}/subjects", data={"employee_id": peer}).status_code == 409
    assert client.post(f"/cycles/{cyc}/launch").status_code == 409


def test_manual_close(app, client):
    subj, peer, cyc, sb = _setup(client)
    client.post(f"/cycles/{cyc}/launch")
    client.post(f"/cycles/{cyc}/close")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status FROM cycles WHERE id=%s", (cyc,))
            assert cur.fetchone()["status"] == "closed"
