from tests.helpers import add_employee, register


def test_register_login_logout(client):
    assert register(client).headers["Location"] == "/employees/"
    assert client.get("/employees/").status_code == 200
    assert client.post("/logout").headers["Location"] == "/login"
    # после выхода защищённые страницы редиректят на логин
    assert client.get("/employees/").status_code == 302


def test_duplicate_email_rejected(client):
    register(client)
    client.post("/logout")
    r = register(client, name="Beta", email="a@a.io")  # тот же email
    assert "уже зарегистрирован" in r.get_data(as_text=True)


def test_tenant_isolation(app, client):
    register(client, name="Acme", email="a@a.io")
    eid = add_employee(client, "Секрет A")
    other = app.test_client()
    register(other, name="Beta", email="b@b.io")
    # чужой сотрудник недоступен
    assert other.get(f"/employees/{eid}/edit").status_code == 404
    assert other.delete(f"/employees/{eid}").status_code == 404
    assert "Секрет A" not in other.get("/employees/").get_data(as_text=True)


def test_login_required_redirects(client):
    assert client.get("/employees/").status_code == 302
    assert client.get("/cycles/").status_code == 302
