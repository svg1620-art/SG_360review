from app.db import get_db
from tests.helpers import add_employee, add_subject, create_cycle, register, set_plan


def test_free_employee_limit(app, client):
    register(client)
    set_plan(app, "Acme", "free")
    for i in range(15):
        r = client.post("/employees/", data={"full_name": f"E{i}"})
    assert r.status_code == 200
    assert client.post("/employees/", data={"full_name": "16th"}).status_code == 403


def test_free_competency_readonly(app, client):
    register(client)
    set_plan(app, "Acme", "free")
    assert client.post("/competencies/", data={"name": "X"}).status_code == 403


def test_free_subjects_and_active_cycle_limits(app, client):
    register(client)
    set_plan(app, "Acme", "free")
    emps = [add_employee(client, f"E{i}") for i in range(6)]
    cyc = create_cycle(client, "C1")
    for e in emps[:5]:
        r = add_subject(client, cyc, e)
    assert r is not None  # 5-й ок
    assert client.post(f"/cycles/{cyc}/subjects", data={"employee_id": emps[5]}).status_code == 403
    # один активный цикл
    client.post(f"/cycles/{cyc}/launch")
    cyc2 = create_cycle(client, "C2")
    add_subject(client, cyc2, emps[0])
    client.post(f"/cycles/{cyc2}/launch")
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT status FROM cycles WHERE id=%s", (cyc2,))
            assert cur.fetchone()["status"] == "draft"  # запуск заблокирован


def test_pro_lifts_limits(app, client):
    register(client)
    set_plan(app, "Acme", "pro")
    for i in range(16):
        r = client.post("/employees/", data={"full_name": f"E{i}"})
    assert r.status_code == 200
    assert client.post("/competencies/", data={"name": "Новая"}).status_code == 200
