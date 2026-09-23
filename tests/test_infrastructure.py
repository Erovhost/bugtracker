"""Проверка самой тестовой инфраструктуры (conftest.py).

Если эти тесты падают, остальным тестам с базой доверять нельзя.
"""

import pytest
import sqlalchemy as sa

from app import db
from app.models import Role, User
from tests.conftest import check_test_database_url
from tests.helpers import login


def scalar(app, sql):
    with app.app_context():
        return db.session.execute(sa.text(sql)).scalar()


def test_uses_test_database(app):
    assert scalar(app, "SELECT current_database()").endswith("_test")


def test_migrations_created_everything(app):
    assert scalar(app, "SELECT count(*) FROM alembic_version") == 1
    trigger = "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_bugs_status_history'"
    assert scalar(app, trigger) == 1
    views = "SELECT count(*) FROM pg_views WHERE viewname LIKE 'v\\_%'"
    assert scalar(app, views) == 2
    with app.app_context():
        names = set(db.session.scalars(sa.select(Role.name)))
    assert names == {"admin", "tester", "developer"}


def test_factory_creates_user(app, factory):
    user_id = factory.user("zoe", "tester")
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.role.name == "tester"
        assert user.status == "active"


# Два теста подряд: второй должен видеть пустую базу после первого
def test_isolation_first(factory):
    factory.user("only_in_first_test")


def test_isolation_second(app):
    assert scalar(app, "SELECT count(*) FROM users") == 0


def test_login_helper(client, factory):
    factory.user("zoe", "tester")
    response = login(client, "zoe")
    assert response.status_code == 302
    assert client.get("/").status_code == 200


def test_guard_rejects_non_test_database():
    # pytest.exit внутри проверки превращается в исключение pytest.exit.Exception
    with pytest.raises(pytest.exit.Exception):
        check_test_database_url("postgresql+psycopg://u:p@localhost/bugtracker")


def test_guard_skips_without_url():
    assert "TEST_DATABASE_URL" in check_test_database_url(None)
