"""Команда flask seed и flask seed --restore-demo (app/demo.py)."""

from collections import Counter

import pytest
import sqlalchemy as sa

from app import db
from app.cli import seed
from app.demo import DEMO_PROJECT
from app.models import Bug, Comment, Project, StatusHistory, User
from tests.helpers import login, post

PASSWORDS = {"pixel": "qwerty123", "ana": "qwerty", "bob": "qwerty"}


def run(app, *args):
    return app.test_cli_runner().invoke(seed, list(args))


def counts(app):
    with app.app_context():
        return {
            model.__name__: db.session.scalar(sa.select(sa.func.count(model.id)))
            for model in (User, Project, Bug, Comment, StatusHistory)
        }


def demo_bug(title_start):
    return db.session.scalar(sa.select(Bug).where(Bug.title.like(f"{title_start}%")))


@pytest.fixture
def seeded(app):
    result = run(app)
    assert result.exit_code == 0, result.output
    return result


# --- 1. Что создаёт flask seed ------------------------------------------------

def test_accounts(app, seeded):
    with app.app_context():
        users = {
            u.username: (u.role.name, u.status, u.email)
            for u in db.session.scalars(sa.select(User))
        }
    assert users == {
        "pixel": ("admin", "active", "pixel@demo.example"),
        "ana": ("tester", "active", "ana@demo.example"),
        "bob": ("developer", "active", "bob@demo.example"),
    }


@pytest.mark.parametrize("username", ["pixel", "ana", "bob"])
def test_accounts_log_in_with_given_passwords(app, seeded, username):
    client = app.test_client()
    assert login(client, username, PASSWORDS[username]).status_code == 302
    assert client.get("/").status_code == 200


def test_project_and_bugs_in_all_statuses(app, seeded):
    with app.app_context():
        project = db.session.scalar(sa.select(Project).where(Project.name == DEMO_PROJECT))
        assert sorted(u.username for u in project.members) == ["ana", "bob"]
        assert project.creator.username == "pixel"
        statuses = Counter(bug.status for bug in project.bugs)
        without_comments = [bug.title for bug in project.bugs if not bug.comments]
    assert statuses == {"new": 1, "in_progress": 1, "fixed": 1, "closed": 1, "rejected": 1}
    assert without_comments == []


# --- 2. История пишется триггером, пошагово -------------------------------------

def test_history_step_by_step(app, seeded):
    with app.app_context():
        email = demo_bug("Не приходит письмо")
        history = [(h.old_status, h.new_status, h.changer.username) for h in email.history]
        rejected = demo_bug("Фильтр по цене")
        reason = rejected.comments[0].text
        total = db.session.scalar(sa.select(sa.func.count(StatusHistory.id)))
    assert history == [
        ("new", "in_progress", "bob"),
        ("in_progress", "fixed", "bob"),
        ("fixed", "in_progress", "ana"),  # возврат на доработку
        ("in_progress", "fixed", "bob"),
        ("fixed", "closed", "ana"),
    ]
    assert reason.startswith("Так задумано")
    # in_progress: 1, fixed: 2, closed: 5, rejected: 1
    assert total == 9


def test_pages_render(app, seeded):
    client = app.test_client()
    login(client, "pixel", PASSWORDS["pixel"])
    for url in ["/", "/bugs/", "/bugs/stats", "/admin/"]:
        assert client.get(url).status_code == 200, url


# --- 3. Повторный запуск без дубликатов ------------------------------------------

def test_second_run_creates_nothing(app, seeded):
    before = counts(app)
    result = run(app)
    assert result.exit_code == 0
    assert counts(app) == before
    assert "уже есть" in result.output


def test_real_user_with_demo_login_blocks_seed(app, factory):
    factory.user("bob", "tester")  # настоящий пользователь с почтой bob@example.com
    result = run(app)
    assert result.exit_code == 1
    assert "Логин «bob» занят" in result.output
    with app.app_context():
        # ничего не создано, настоящий bob не тронут
        assert find_username_list() == ["bob"]
        bob = db.session.scalar(sa.select(User).where(User.username == "bob"))
        assert bob.email == "bob@example.com" and bob.role.name == "tester"


def find_username_list():
    return sorted(db.session.scalars(sa.select(User.username)))


# --- 4. --restore-demo ----------------------------------------------------------

def break_demo(app):
    """Посетитель демо «испортил» аккаунты."""
    with app.app_context():
        users = {u.username: u for u in db.session.scalars(sa.select(User))}
        users["ana"].is_active = False
        users["pixel"].set_password("changed-by-someone")
        project = db.session.scalar(sa.select(Project).where(Project.name == DEMO_PROJECT))
        project.members.remove(users["bob"])
        users["bob"].role = users["pixel"].role  # стал admin
        db.session.commit()


def test_restore_accounts(app, seeded, factory):
    other = factory.user("stranger", "tester", status="blocked")
    break_demo(app)
    before = counts(app)

    result = run(app, "--restore-demo")
    assert result.exit_code == 0, result.output
    with app.app_context():
        users = {u.username: u for u in db.session.scalars(sa.select(User))}
        assert users["ana"].status == "active"
        assert users["bob"].role.name == "developer"
        assert users["pixel"].check_password("qwerty123")
        project = db.session.scalar(sa.select(Project).where(Project.name == DEMO_PROJECT))
        assert users["bob"] in project.members
        # чужой пользователь не тронут
        assert db.session.get(User, other).status == "blocked"
    assert counts(app) == before  # ничего не создано и не удалено
    assert "bob: возвращён в проект" in result.output


def test_restore_does_not_touch_bugs(app, seeded):
    with app.app_context():
        before = [(b.id, b.status, b.assignee_id, b.title) for b in db.session.scalars(
            sa.select(Bug).order_by(Bug.id))]
    break_demo(app)
    run(app, "--restore-demo")
    with app.app_context():
        after = [(b.id, b.status, b.assignee_id, b.title) for b in db.session.scalars(
            sa.select(Bug).order_by(Bug.id))]
    assert after == before


def test_restore_skips_real_user_with_demo_login(app, factory):
    real_id = factory.user("bob", "tester")  # не демо: почта bob@example.com
    result = run(app, "--restore-demo")
    assert result.exit_code == 0
    assert "bob: ПРОПУЩЕН" in result.output
    with app.app_context():
        real = db.session.get(User, real_id)
        assert real.role.name == "tester"
        assert real.check_password("secret123")  # пароль не сброшен


def test_restore_unassigns_when_developer_role_is_taken_back(app, seeded):
    # Админ сделал ana разработчиком, она взяла баг в работу
    with app.app_context():
        ana = db.session.scalar(sa.select(User).where(User.username == "ana"))
        ana.role = db.session.scalar(sa.select(User).where(User.username == "bob")).role
        bug = demo_bug("Кнопка «Купить»")
        bug.assignee = ana
        bug.updater = ana
        db.session.commit()
        bug_id = bug.id
    result = run(app, "--restore-demo")
    assert f"снято назначение с багов #{bug_id}" in result.output
    with app.app_context():
        assert db.session.get(Bug, bug_id).assignee is None
        ana = db.session.scalar(sa.select(User).where(User.username == "ana"))
        assert ana.role.name == "tester"


def test_restore_when_project_renamed(app, seeded):
    client = app.test_client()
    login(client, "pixel", PASSWORDS["pixel"])
    with app.app_context():
        project_id = db.session.scalar(sa.select(Project.id).where(Project.name == DEMO_PROJECT))
    post(client, f"/project/{project_id}/edit", {"name": "Переименован"})
    result = run(app, "--restore-demo")
    assert result.exit_code == 0
    assert "не найден" in result.output
    assert "pixel: восстановлен." in result.output


def test_restore_creates_missing_accounts(app):
    result = run(app, "--restore-demo")
    assert result.exit_code == 0
    with app.app_context():
        assert find_username_list() == ["ana", "bob", "pixel"]
