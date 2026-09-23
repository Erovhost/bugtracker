"""Проверка прав ролей PostgreSQL bugtracker_app и bugtracker_readonly.

Те же пробы, что в sql/check_roles.sql. Каждая выполняется в транзакции,
которая откатывается, — база не меняется.

Нужны строки подключения в .env (см. .env.example):
APP_DATABASE_URL и READONLY_DATABASE_URL. Если их нет, тесты пропускаются.
Роли создаёт скрипт sql/roles.sql.
"""

import os

import psycopg
import pytest
import sqlalchemy as sa

import config  # noqa: F401  (загружает .env в переменные окружения)

# Подзапросы вместо конкретных id: тесты не зависят от данных в базе
ANY_USER = "(SELECT min(id) FROM users)"
TESTER_ROLE = "(SELECT id FROM roles WHERE name = 'tester')"
NEW_PROJECT = (
    "INSERT INTO projects (name, created_by) "
    f"VALUES ('test_roles_project', {ANY_USER}) RETURNING id"
)

APP_ALLOWED = [
    "SELECT count(*) FROM roles",
    "SELECT count(*) FROM users",
    f"UPDATE users SET email = email WHERE id = {ANY_USER}",
    "INSERT INTO users (username, email, password_hash, role_id, is_active) "
    f"VALUES ('test_roles_user', 'test_roles@example.com', 'h', {TESTER_ROLE}, false)",
    NEW_PROJECT,
    f"WITH p AS ({NEW_PROJECT}) "
    f"INSERT INTO project_members (project_id, user_id) SELECT id, {ANY_USER} FROM p",
    f"WITH p AS ({NEW_PROJECT}) "
    "INSERT INTO bugs (project_id, title, severity, reporter_id, updated_by) "
    f"SELECT id, 'check', 'minor', {ANY_USER}, {ANY_USER} FROM p",
    "SELECT count(*) FROM v_bug_stats",
    "SELECT count(*) FROM v_open_bugs_by_assignee",
    "DELETE FROM project_members WHERE false",
]

APP_DENIED = [
    "DELETE FROM status_history",
    "UPDATE status_history SET new_status = new_status",
    "DELETE FROM comments",
    "UPDATE comments SET text = text",
    "DELETE FROM bugs",
    "DELETE FROM users",
    "DELETE FROM projects",
    "INSERT INTO roles (name) VALUES ('superuser')",
    "TRUNCATE bugs",
    "DROP TABLE bugs",
    "ALTER TABLE bugs ADD COLUMN test_roles_column int",
    "CREATE TABLE test_roles_table (id int)",
    "SELECT * FROM alembic_version",
    "DROP VIEW v_bug_stats",
]

READONLY_ALLOWED = [
    "SELECT count(*) FROM bugs",
    "SELECT count(*) FROM (SELECT id, username, email, role_id, is_active, "
    "approved_at, created_at FROM users) AS allowed_columns",
    "SELECT count(*) FROM v_bug_stats",
    "SELECT count(*) FROM status_history",
]

READONLY_DENIED = [
    "SELECT password_hash FROM users",
    "SELECT * FROM users",
    "INSERT INTO comments (bug_id, author_id, text) VALUES (1, 1, 'x')",
    "UPDATE bugs SET title = title",
    "CREATE TABLE test_roles_table (id int)",
]


def make_engine(env_key):
    url = os.environ.get(env_key)
    if not url:
        pytest.skip(f"В .env нет {env_key} — проверка ролей пропущена")
    return sa.create_engine(url)


# Фикстура — то, что pytest готовит для тестов. scope="module": одно
# подключение на весь файл, а не на каждый тест. Код после yield
# выполняется, когда тесты файла закончились (закрываем подключения).
@pytest.fixture(scope="module")
def app_engine():
    engine = make_engine("APP_DATABASE_URL")
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def readonly_engine():
    engine = make_engine("READONLY_DATABASE_URL")
    yield engine
    engine.dispose()


def run_and_rollback(engine, sql):
    """Выполнить команду в транзакции и откатить её."""
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(sa.text(sql))
        finally:
            transaction.rollback()


def assert_permission_denied(engine, sql):
    """Команда должна упасть именно с ошибкой прав (42501), а не с любой другой."""
    with pytest.raises(sa.exc.DBAPIError) as error:
        run_and_rollback(engine, sql)
    assert isinstance(error.value.orig, psycopg.errors.InsufficientPrivilege), (
        f"ожидалась ошибка прав, а получена {type(error.value.orig).__name__}"
    )


def test_app_connects_as_its_role(app_engine):
    with app_engine.connect() as conn:
        assert conn.execute(sa.text("SELECT current_user")).scalar() == "bugtracker_app"


def test_readonly_connects_as_its_role(readonly_engine):
    with readonly_engine.connect() as conn:
        role = conn.execute(sa.text("SELECT current_user")).scalar()
        assert role == "bugtracker_readonly"


@pytest.mark.parametrize("sql", APP_ALLOWED)
def test_app_allowed(app_engine, sql):
    run_and_rollback(app_engine, sql)


@pytest.mark.parametrize("sql", APP_DENIED)
def test_app_denied(app_engine, sql):
    assert_permission_denied(app_engine, sql)


@pytest.mark.parametrize("sql", READONLY_ALLOWED)
def test_readonly_allowed(readonly_engine, sql):
    run_and_rollback(readonly_engine, sql)


@pytest.mark.parametrize("sql", READONLY_DENIED)
def test_readonly_denied(readonly_engine, sql):
    assert_permission_denied(readonly_engine, sql)
