"""Команда flask seed-demo (app/demo.py, app/cli.py)."""

from collections import Counter

import pytest
import sqlalchemy as sa

from app import db
from app.cli import seed_demo
from app.demo import DEMO_PASSWORD
from app.models import Bug, Comment, Project, StatusHistory, User
from tests.helpers import login


def run_seed(app, args=("--yes",), answer=""):
    return app.test_cli_runner().invoke(seed_demo, list(args), input=answer)


@pytest.fixture
def seeded(app):
    result = run_seed(app)
    assert result.exit_code == 0, result.output
    return result


def test_output_lists_accounts(seeded):
    assert "Создано: пользователей 7, проектов 3, багов 8." in seeded.output
    for username in ["demo_admin", "anna", "igor", "petr", "olga", "new_user", "blocked_dev"]:
        assert username in seeded.output


def test_users_and_statuses(app, seeded):
    with app.app_context():
        users = {u.username: (u.role.name, u.status) for u in db.session.scalars(sa.select(User))}
    assert users == {
        "demo_admin": ("admin", "active"),
        "anna": ("tester", "active"),
        "igor": ("tester", "active"),
        "petr": ("developer", "active"),
        "olga": ("developer", "active"),
        "blocked_dev": ("developer", "blocked"),
        "new_user": ("tester", "pending"),
    }


def test_bugs_in_all_statuses(app, seeded):
    with app.app_context():
        statuses = Counter(db.session.scalars(sa.select(Bug.status)))
        empty = db.session.scalar(sa.select(Project).where(Project.name == "Внутренний портал"))
        assert empty.bugs == [] and empty.members == []
    assert statuses == {"new": 2, "in_progress": 2, "fixed": 1, "closed": 2, "rejected": 1}


def test_history_written_by_trigger(app, seeded):
    with app.app_context():
        bug = db.session.scalar(sa.select(Bug).where(Bug.title == "Не приходит письмо о заказе"))
        history = [(h.old_status, h.new_status, h.changer.username) for h in bug.history]
        rejected = db.session.scalar(sa.select(Bug).where(Bug.status == "rejected"))
        reason = [c.text for c in rejected.comments]
        total = db.session.scalar(sa.select(sa.func.count(StatusHistory.id)))
        comments = db.session.scalar(sa.select(sa.func.count(Comment.id)))
    assert history == [
        ("new", "in_progress", "petr"),
        ("in_progress", "fixed", "petr"),
        ("fixed", "in_progress", "igor"),  # возврат на доработку
        ("in_progress", "fixed", "petr"),
        ("fixed", "closed", "anna"),
    ]
    assert reason and reason[0].startswith("Так задумано")
    assert total == 13
    assert comments == 4  # 3 в обсуждении + причина отклонения


def test_blocked_developer_kept_on_closed_bug(app, client, seeded):
    with app.app_context():
        crash = db.session.scalar(sa.select(Bug).where(Bug.title.like("Приложение закрывается%")))
        crash_id = crash.id
        assert crash.status == "closed" and crash.assignee.username == "blocked_dev"
    login(client, "demo_admin", DEMO_PASSWORD)
    page = client.get(f"/bugs/{crash_id}").get_data(as_text=True)
    assert 'class="blocked">заблокирован' in page


@pytest.mark.parametrize("username", ["demo_admin", "anna", "petr"])
def test_demo_accounts_can_log_in(app, seeded, username):
    client = app.test_client()
    response = login(client, username, DEMO_PASSWORD)
    assert response.status_code == 302
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("username", ["new_user", "blocked_dev"])
def test_inactive_demo_accounts_cannot_log_in(app, seeded, username):
    client = app.test_client()
    login(client, username, DEMO_PASSWORD)
    assert client.get("/").status_code == 302


def test_pages_render_with_demo_data(app, seeded):
    client = app.test_client()
    login(client, "demo_admin", DEMO_PASSWORD)
    for url in ["/", "/bugs/", "/bugs/stats", "/admin/"]:
        assert client.get(url).status_code == 200, url


def test_second_run_refused(app, seeded):
    result = run_seed(app)
    assert result.exit_code == 1
    assert "Демо-данные уже есть" in result.output
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count(User.id))) == 7


def test_asks_confirmation(app):
    result = run_seed(app, args=(), answer="n\n")
    assert result.exit_code == 1  # отказ — ничего не создано
    assert "Не запускайте эту команду на сервере" in result.output
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count(User.id))) == 0
