"""Общие фикстуры для тестов с базой данных.

pytest сам находит этот файл; его фикстуры доступны во всех тестах.

Тесты работают с ОТДЕЛЬНОЙ базой из TEST_DATABASE_URL (имя на _test).
Перед запуском схема пересоздаётся миграциями, перед каждым тестом
данные очищаются (кроме справочника ролей). Данные последнего теста
остаются в базе — их можно посмотреть в psql для отладки.

Важно: запросы тестового клиента выполняются ВНЕ app.app_context() —
иначе Flask-Login закэширует пользователя между запросами (этап 3).
Поэтому factory возвращает id, а не объекты.
"""

from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade

from app import create_app, db
from app.models import Bug, Project, Role, User
from config import TestConfig
from tests.helpers import PASSWORD

# Все таблицы с данными, кроме roles (роли создаёт миграция)
DATA_TABLES = "users, projects, project_members, bugs, comments, status_history"


def check_test_database_url(url):
    """Не даём тестам работать с рабочей базой."""
    if not url:
        return "В .env нет TEST_DATABASE_URL — тесты с базой пропущены"
    db_name = urlsplit(url).path.lstrip("/")
    if not db_name.endswith("_test"):
        pytest.exit(
            f"TEST_DATABASE_URL указывает на базу «{db_name}». Тесты стирают данные, "
            "поэтому имя базы должно заканчиваться на _test.",
            returncode=1,
        )
    return None


@pytest.fixture(scope="session")
def app():
    """Приложение с тестовыми настройками и свежей схемой — один раз за запуск."""
    reason = check_test_database_url(TestConfig.SQLALCHEMY_DATABASE_URI)
    if reason:
        pytest.skip(reason)

    app = create_app(TestConfig)
    with app.app_context():
        # Пересоздаём схему с нуля и применяем все миграции:
        # таблицы, роли, триггер, представления — как в рабочей базе
        db.session.execute(sa.text("DROP SCHEMA public CASCADE"))
        db.session.execute(sa.text("CREATE SCHEMA public"))
        db.session.commit()
        upgrade(directory="migrations")
    return app


@pytest.fixture(autouse=True)
def clean_db(request):
    """Перед каждым тестом с базой — очистить данные (autouse: для всех тестов).

    Очистка ДО теста: каждый тест начинает с пустой базы, а данные
    последнего теста (в том числе упавшего) остаются в bugtracker_test
    для просмотра. Код после yield выполнялся бы при любом исходе теста.
    """
    if "app" in request.fixturenames:
        app = request.getfixturevalue("app")
        with app.app_context():
            db.session.execute(
                sa.text(f"TRUNCATE {DATA_TABLES} RESTART IDENTITY CASCADE")
            )
            db.session.commit()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


# --- Создание тестовых данных -----------------------------------------------

class Factory:
    """Создаёт записи в тестовой базе и возвращает их id.

    Пример: zoe = factory.user("zoe", "tester")
    """

    def __init__(self, app):
        self.app = app

    def user(self, username, role="tester", status="active"):
        """status: active / pending (заявка) / blocked."""
        with self.app.app_context():
            user = User(
                username=username,
                email=f"{username}@example.com",
                role=db.session.scalar(sa.select(Role).where(Role.name == role)),
                is_active=status == "active",
                approved_at=None if status == "pending" else sa.func.now(),
            )
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            return user.id

    def project(self, name, creator_id, member_ids=()):
        with self.app.app_context():
            project = Project(name=name, creator=db.session.get(User, creator_id))
            # Сначала в сессию, потом участники: иначе поиск участника
            # запустит автосохранение проекта, которого ещё нет в сессии
            db.session.add(project)
            for member_id in member_ids:
                project.members.append(db.session.get(User, member_id))
            db.session.commit()
            return project.id

    def bug(self, project_id, reporter_id, status="new", assignee_id=None,
            severity="major", title="Тестовый баг"):
        with self.app.app_context():
            reporter = db.session.get(User, reporter_id)
            bug = Bug(
                project=db.session.get(Project, project_id),
                title=title,
                severity=severity,
                status=status,
                reporter=reporter,
                updater=reporter,
                assignee=db.session.get(User, assignee_id) if assignee_id else None,
            )
            db.session.add(bug)
            db.session.commit()
            return bug.id


@pytest.fixture
def factory(app):
    return Factory(app)
