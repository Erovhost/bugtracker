"""Модульные тесты правил жизненного цикла бага (app/workflow.py).

Объекты создаются в памяти, база данных не нужна.
Правила — таблица переходов из ТЗ, раздел «Жизненный цикл бага».
"""

import pytest

from app.models import Bug, Project, Role, User
from app.workflow import (
    TRANSITIONS,
    apply_transition,
    available_transitions,
    check_transition,
)

STATUSES = ["new", "in_progress", "fixed", "rejected", "closed"]

ROLES = {name: Role(name=name) for name in ["admin", "tester", "developer"]}


# --- Помощники: объекты в памяти -------------------------------------------

def make_user(user_id, role):
    return User(id=user_id, username=f"{role}{user_id}", role=ROLES[role])


def make_project(*members):
    return Project(name="P", members=list(members))


def make_bug(project, status="new", assignee=None, reporter=None):
    bug = Bug(project=project, status=status, reporter=reporter)
    if assignee is not None:
        bug.assignee = assignee
        # В памяти (без базы) id внешнего ключа сам не заполняется
        bug.assignee_id = assignee.id
    return bug


@pytest.fixture
def people():
    """Типичный состав: админ, два тестировщика, два разработчика, посторонний."""
    team = {
        "admin": make_user(1, "admin"),
        "tester": make_user(2, "tester"),
        "tester2": make_user(3, "tester"),
        "dev": make_user(4, "developer"),
        "dev2": make_user(5, "developer"),
        "outsider": make_user(6, "developer"),
    }
    team["project"] = make_project(
        team["tester"], team["tester2"], team["dev"], team["dev2"]
    )
    return team


# --- Таблица переходов -------------------------------------------------------

# Все пары (из, в), которых нет в TRANSITIONS, запрещены для всех
FORBIDDEN_PAIRS = [
    (old, new)
    for old in STATUSES
    for new in STATUSES
    if old != new and (old, new) not in TRANSITIONS
]


def test_transitions_table_matches_spec():
    assert TRANSITIONS == {
        ("new", "in_progress"): "developer",
        ("in_progress", "fixed"): "developer",
        ("new", "rejected"): "developer",
        ("in_progress", "rejected"): "developer",
        ("fixed", "closed"): "tester",
        ("fixed", "in_progress"): "tester",
        ("rejected", "new"): "tester",
    }


@pytest.mark.parametrize("old, new", FORBIDDEN_PAIRS)
def test_forbidden_pairs_rejected_for_everyone(people, old, new):
    for who in ["tester", "dev"]:
        bug = make_bug(people["project"], old, assignee=people["dev"])
        error = check_transition(people[who], bug, new, comment="причина")
        assert error is not None
        assert "невозможен" in error


def test_closed_is_final(people):
    bug = make_bug(people["project"], "closed", assignee=people["dev"])
    for who in ["tester", "dev"]:
        assert available_transitions(people[who], bug) == []


@pytest.mark.parametrize("old, new", sorted(TRANSITIONS))
def test_wrong_role_rejected(people, old, new):
    right_role = TRANSITIONS[(old, new)]
    wrong_user = people["tester"] if right_role == "developer" else people["dev"]
    bug = make_bug(people["project"], old, assignee=people["dev"])
    error = check_transition(wrong_user, bug, new, comment="причина")
    assert error is not None
    assert "выполняет" in error


# --- Кто именно может выполнить переход -------------------------------------

def test_admin_cannot_change_status(people):
    bug = make_bug(people["project"], "new")
    assert check_transition(people["admin"], bug, "in_progress") == (
        "Администратор не меняет статусы багов."
    )


def test_outsider_cannot_change_status(people):
    bug = make_bug(people["project"], "new")
    error = check_transition(people["outsider"], bug, "in_progress")
    assert error == "Менять статус могут только участники проекта."


def test_take_free_bug(people):
    bug = make_bug(people["project"], "new")
    assert check_transition(people["dev"], bug, "in_progress") is None


def test_take_own_bug(people):
    bug = make_bug(people["project"], "new", assignee=people["dev"])
    assert check_transition(people["dev"], bug, "in_progress") is None


def test_cannot_take_bug_assigned_to_other(people):
    bug = make_bug(people["project"], "new", assignee=people["dev"])
    error = check_transition(people["dev2"], bug, "in_progress")
    assert error == "Баг назначен на другого разработчика."


@pytest.mark.parametrize("new", ["fixed", "rejected"])
def test_only_assignee_can_finish_in_progress(people, new):
    bug = make_bug(people["project"], "in_progress", assignee=people["dev"])
    assert check_transition(people["dev"], bug, new, comment="причина") is None
    error = check_transition(people["dev2"], bug, new, comment="причина")
    assert error == "Это может сделать только исполнитель бага."


def test_any_developer_can_reject_new_bug(people):
    bug = make_bug(people["project"], "new", assignee=people["dev"])
    assert check_transition(people["dev2"], bug, "rejected", comment="дубликат") is None


@pytest.mark.parametrize("comment", [None, "", "   ", "\n\t"])
def test_reject_requires_reason(people, comment):
    bug = make_bug(people["project"], "new")
    error = check_transition(people["dev"], bug, "rejected", comment=comment)
    assert error == "Укажите причину отклонения в комментарии."


@pytest.mark.parametrize(
    "old, new", [("fixed", "closed"), ("fixed", "in_progress"), ("rejected", "new")]
)
def test_any_tester_member_not_only_reporter(people, old, new):
    bug = make_bug(people["project"], old, assignee=people["dev"], reporter=people["tester"])
    # tester2 — не автор бага, но участник проекта
    assert check_transition(people["tester2"], bug, new) is None


# --- Последствия переходов (apply_transition) -------------------------------
# Комментарий добавляется в db.session, поэтому нужен контекст приложения
# (к базе при этом никто не подключается — изменения откатываем).

@pytest.fixture
def app_context():
    from app import create_app, db
    from config import Config

    class MemoryConfig(Config):
        TESTING = True
        # Подключения не будет: сессию откатываем, ничего не записывая
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://unused@localhost/unused"

    app = create_app(MemoryConfig)
    with app.app_context():
        yield
        db.session.rollback()


def test_taking_free_bug_assigns_developer(people):
    bug = make_bug(people["project"], "new")
    assert apply_transition(people["dev"], bug, "in_progress") == "in_progress"
    assert bug.status == "in_progress"
    assert bug.assignee is people["dev"]
    assert bug.updater is people["dev"]


def test_return_from_fixed_keeps_assignee(people):
    bug = make_bug(people["project"], "fixed", assignee=people["dev"])
    apply_transition(people["tester"], bug, "in_progress")
    assert bug.status == "in_progress"
    assert bug.assignee is people["dev"]
    assert bug.updater is people["tester"]


def test_return_from_fixed_without_assignee_goes_to_new(people):
    bug = make_bug(people["project"], "fixed")
    assert apply_transition(people["tester"], bug, "in_progress") == "new"
    assert bug.status == "new"
    assert bug.assignee is None


def test_rejected_to_new_clears_assignee(people):
    bug = make_bug(people["project"], "rejected", assignee=people["dev"])
    apply_transition(people["tester"], bug, "new")
    assert bug.status == "new"
    assert bug.assignee is None


def test_reject_saves_trimmed_reason(people, app_context):
    bug = make_bug(people["project"], "new")
    apply_transition(people["dev"], bug, "rejected", comment="  Не баг, так задумано  ")
    assert bug.status == "rejected"
    assert [(c.author, c.text) for c in bug.comments] == [
        (people["dev"], "Не баг, так задумано")
    ]


# --- Кнопки совпадают с проверкой -------------------------------------------

@pytest.mark.parametrize("status", STATUSES)
def test_buttons_match_check(people, status):
    for who in ["admin", "tester", "tester2", "dev", "dev2", "outsider"]:
        bug = make_bug(people["project"], status, assignee=people["dev"])
        shown = {new for new, _label in available_transitions(people[who], bug)}
        allowed = {
            new
            for new in STATUSES
            if check_transition(people[who], bug, new, comment="причина") is None
        }
        assert shown == allowed, f"{who} на статусе {status}"
