from app.db import get_db
from app.report import _others_visible, _rating_aggregate
from tests.helpers import (
    add_assignment,
    add_employee,
    add_subject,
    create_cycle,
    fill_and_submit,
    register,
    set_plan,
)


def test_others_visibility_rules():
    t = 3
    assert _others_visible(3, 3, t) is True       # обе группы видны
    assert _others_visible(2, 2, t) is True        # обе скрыты, пул >= порога
    assert _others_visible(3, 2, t) is False       # одна видна, другая скрыта -> утечка
    assert _others_visible(3, 0, t) is True         # вторая пуста
    assert _others_visible(1, 1, t) is False        # пул < порога


def _build(client, peers, subs):
    register(client)
    subj = add_employee(client, "Субъект")
    ps = [add_employee(client, f"P{i}") for i in range(peers)]
    us = [add_employee(client, f"U{i}") for i in range(subs)]
    cyc = create_cycle(client, "Q1")
    sb = add_subject(client, cyc, subj)
    for e in ps:
        add_assignment(client, cyc, sb, e, "peer")
    for e in us:
        add_assignment(client, cyc, sb, e, "subordinate")
    client.post(f"/cycles/{cyc}/launch")
    return cyc, sb


def test_leak_case_hides_others(app, client):
    # 3 коллеги (видны) + 2 подчинённых (скрыты) -> «другие» прячем (утечка)
    cyc, sb = _build(client, peers=3, subs=2)
    fill_and_submit(app, cyc, lambda rel, ci: 4 if rel == "self" else 3)
    client.post(f"/cycles/{cyc}/close")
    with app.app_context():
        db = get_db()
        agg = _rating_aggregate(db, int(cyc), int(sb), 3)
    assert agg["peer_visible"] is True
    assert agg["sub_visible"] is False
    assert agg["others_visible"] is False
    assert all(v["others"] is None for v in agg["means"].values())


def test_pooled_others_visible(app, client):
    # 2 коллеги + 2 подчинённых: обе группы скрыты, но «другие» виден пулом
    cyc, sb = _build(client, peers=2, subs=2)
    fill_and_submit(app, cyc, lambda rel, ci: 4 if rel == "self" else 3)
    client.post(f"/cycles/{cyc}/close")
    with app.app_context():
        db = get_db()
        agg = _rating_aggregate(db, int(cyc), int(sb), 3)
    assert agg["peer_visible"] is False and agg["sub_visible"] is False
    assert agg["others_visible"] is True
    assert round(agg["means"]["Коммуникация"]["others"], 2) == 3.0


def test_report_route_closed_only(app, client):
    cyc, sb = _build(client, peers=3, subs=3)
    # active -> редирект
    assert client.get(f"/cycles/{cyc}/subjects/{sb}/report").status_code == 302
    fill_and_submit(app, cyc, lambda rel, ci: 4 if rel == "self" else 2)
    client.post(f"/cycles/{cyc}/close")
    body = client.get(f"/cycles/{cyc}/subjects/{sb}/report").get_data(as_text=True)
    assert "id=\"radar\"" in body
