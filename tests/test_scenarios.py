"""24 сквозных HTTP-сценария из docs/test_scenarios.md.

Приложение работает под ролью PostgreSQL bugtracker_app (минимальные права,
sql/grants.sql) в тестовой базе. Данные готовит и проверяет владелец базы.
Цель — ни одного ответа 5xx: приложению хватает минимальных прав.

Шаги зависят друг от друга, поэтому это один тест; номер упавшего шага
виден в сообщении об ошибке.
"""

import os

import pytest
import sqlalchemy as sa

from app import create_app, db
from app.models import Bug, Comment, Project, StatusHistory, User
from config import TestConfig
from tests.helpers import login, post


class AppRoleTestConfig(TestConfig):
    """Тестовая база, но подключение под ролью bugtracker_app."""


@pytest.fixture
def role_app(app):
    app_url = os.environ.get("APP_DATABASE_URL")
    if not app_url:
        pytest.skip("В .env нет APP_DATABASE_URL — сценарии под ролью приложения пропущены")
    # Логин и пароль роли — из APP_DATABASE_URL, имя базы — тестовое
    test_db = sa.engine.make_url(TestConfig.SQLALCHEMY_DATABASE_URI).database
    url = sa.engine.make_url(app_url).set(database=test_db)
    AppRoleTestConfig.SQLALCHEMY_DATABASE_URI = url.render_as_string(hide_password=False)
    role_app = create_app(AppRoleTestConfig)
    with role_app.app_context():
        who = db.session.execute(sa.text("SELECT current_user")).scalar()
        if who != "bugtracker_app":
            pytest.skip("роль bugtracker_app недоступна")
    return role_app


def test_scenarios_as_app_role(app, role_app, factory):
    # --- Исходные данные (владелец базы) ---
    ids = {
        "adm": factory.user("adm", "admin"),
        "zoe": factory.user("zoe", "tester"),
        "bob": factory.user("bob", "developer"),
        "dan": factory.user("dan", "developer"),
        "req": factory.user("req", "tester", status="pending"),
    }
    ids["P"] = factory.project("P", ids["adm"], [ids["zoe"], ids["bob"], ids["dan"]])

    clients = {}
    for name in ["adm", "zoe", "bob", "dan"]:
        clients[name] = role_app.test_client()
        assert login(clients[name], name).status_code == 302, f"вход {name}"
    adm, zoe, bob, dan = clients["adm"], clients["zoe"], clients["bob"], clients["dan"]
    P = ids["P"]
    codes = []

    def step(number, response, expected):
        codes.append(response.status_code)
        assert response.status_code == expected, f"шаг {number}: {response.status_code}"

    def owner_check(func):
        """Проверка в базе от имени владельца (вне запросов тестового клиента)."""
        with app.app_context():
            return func()

    def user(name):
        return db.session.scalar(sa.select(User).where(User.username == name))

    def last_bug_id():
        return owner_check(lambda: db.session.scalar(sa.select(sa.func.max(Bug.id))))

    def history(bug_id):
        return owner_check(lambda: [
            (h.old_status, h.new_status, h.changer.username)
            for h in db.session.get(Bug, bug_id).history
        ])

    # --- Админ ---
    step(1, adm.get("/admin/"), 200)

    step(2, post(adm, f"/admin/users/{ids['req']}/approve", {"role": "developer"}), 302)
    assert owner_check(lambda: (user("req").status, user("req").role.name)) == ("active", "developer")

    step(3, post(adm, "/admin/users/new", {
        "username": "made", "email": "made@example.com",
        "password": "secret123", "password2": "secret123", "role": "tester",
    }), 302)
    assert owner_check(lambda: user("made").status) == "active"

    step(4, post(adm, "/project/new", {"name": "P_new", "description": "d"}), 302)
    assert owner_check(lambda: db.session.scalar(
        sa.select(Project.created_by).where(Project.name == "P_new"))) == ids["adm"]

    step(5, post(adm, f"/project/{P}/edit", {"name": "P", "description": "edited"}), 302)
    assert owner_check(lambda: db.session.get(Project, P).description) == "edited"

    step(6, post(adm, f"/project/{P}/members/add", {"user_id": ids["req"]}), 302)
    assert owner_check(lambda: user("req") in db.session.get(Project, P).members)

    # --- Тестировщик и разработчики ---
    step(7, post(zoe, f"/bugs/project/{P}/new",
                 {"title": "B1", "severity": "major", "priority": "high"}), 302)
    b1 = last_bug_id()
    assert owner_check(lambda: (db.session.get(Bug, b1).status, db.session.get(Bug, b1).updater.username)) == ("new", "zoe")

    step(8, post(zoe, f"/bugs/project/{P}/new",
                 {"title": "B2", "severity": "minor", "priority": "low"}), 302)
    b2 = last_bug_id()

    step(9, post(zoe, f"/bugs/{b1}/assign", {"assignee_id": ids["bob"]}), 302)
    assert owner_check(lambda: db.session.get(Bug, b1).assignee.username) == "bob"

    step(10, post(zoe, f"/bugs/{b1}/comments", {"text": "Проверьте, пожалуйста"}), 302)
    assert owner_check(lambda: db.session.scalar(
        sa.select(sa.func.count(Comment.id)).where(Comment.bug_id == b1))) == 1

    step(11, post(bob, f"/bugs/{b1}/status", {"new_status": "in_progress"}), 302)
    assert history(b1) == [("new", "in_progress", "bob")]

    step(12, post(bob, f"/bugs/{b1}/status", {"new_status": "fixed"}), 302)
    step(13, post(zoe, f"/bugs/{b1}/status", {"new_status": "closed"}), 302)
    assert history(b1) == [
        ("new", "in_progress", "bob"),
        ("in_progress", "fixed", "bob"),
        ("fixed", "closed", "zoe"),
    ]

    step(14, post(dan, f"/bugs/{b2}/status", {"new_status": "in_progress"}), 302)
    assert owner_check(lambda: db.session.get(Bug, b2).assignee.username) == "dan"

    step(15, post(bob, f"/bugs/{b1}/edit",
                  {"title": "x", "severity": "minor", "priority": "low"}), 403)
    assert owner_check(lambda: db.session.get(Bug, b1).title) == "B1"

    # --- Админ: участники, блокировка, роли ---
    step(16, post(adm, f"/project/{P}/members/{ids['dan']}/remove"), 302)
    assert owner_check(lambda: (db.session.get(Bug, b2).status, db.session.get(Bug, b2).assignee)) == ("new", None)
    assert history(b2) == [("new", "in_progress", "dan"), ("in_progress", "new", "adm")]

    step(17, post(adm, f"/admin/users/{ids['bob']}/block"), 302)
    assert owner_check(lambda: user("bob").status) == "blocked"
    # закрытый B1 сохранил исполнителя — память о том, кто исправил
    assert owner_check(lambda: db.session.get(Bug, b1).assignee.username) == "bob"

    step(18, post(adm, f"/admin/users/{ids['bob']}/unblock"), 302)
    assert owner_check(lambda: user("bob").status) == "active"

    step(19, post(adm, f"/admin/users/{ids['bob']}/role", {"role": "tester"}), 302)
    assert owner_check(lambda: user("bob").role.name) == "tester"

    step(20, post(bob, f"/bugs/{b2}/status", {"new_status": "rejected", "comment": "x"}), 302)
    assert owner_check(lambda: db.session.get(Bug, b2).status) == "new"
    assert owner_check(lambda: db.session.scalar(
        sa.select(sa.func.count(Comment.id)).where(Comment.bug_id == b2))) == 0

    # --- Чтение ---
    card = zoe.get(f"/bugs/{b1}")
    step(21, card, 200)
    assert "Проверьте, пожалуйста" in card.get_data(as_text=True)

    listing = zoe.get("/bugs/?status=closed")
    step(22, listing, 200)
    assert ">B1</a>" in listing.get_data(as_text=True)
    assert ">B2</a>" not in listing.get_data(as_text=True)

    stats = zoe.get("/bugs/stats")
    step(23, stats, 200)
    assert ">P<" in stats.get_data(as_text=True)
    assert ">P_new<" not in stats.get_data(as_text=True)

    step(24, adm.get(f"/project/{P}"), 200)

    # --- Итог ---
    assert len(codes) == 24
    assert all(code < 500 for code in codes), codes
    # История записана триггером под правами приложения
    assert owner_check(lambda: db.session.scalar(sa.select(sa.func.count(StatusHistory.id)))) == 5
