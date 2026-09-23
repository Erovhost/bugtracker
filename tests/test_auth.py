"""Вход, выход, регистрация, команда flask create-admin."""

from urllib.parse import quote

import pytest
import sqlalchemy as sa

from app import db
from app.cli import create_admin
from app.models import User
from tests.helpers import PASSWORD, csrf_token, flash_messages, login, post

WRONG = "Неверный логин или пароль."
PENDING = "Аккаунт ещё не одобрен администратором."
BLOCKED = "Аккаунт заблокирован. Обратитесь к администратору."


def get_user(app, username):
    with app.app_context():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            return None
        return {
            "status": user.status,
            "role": user.role.name,
            "hash_ok": user.check_password(PASSWORD),
            "hash": user.password_hash,
        }


def page_text(response):
    return response.get_data(as_text=True)


# --- Вход ----------------------------------------------------------------------

def test_login_success_redirects_home(client, factory):
    factory.user("zoe")
    response = login(client, "zoe")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert "zoe (tester)" in page_text(client.get("/"))


def test_wrong_password_and_unknown_user_same_message(client, factory):
    factory.user("zoe")
    assert WRONG in page_text(login(client, "zoe", "wrong-password"))
    assert WRONG in page_text(login(client, "nobody"))


@pytest.mark.parametrize("status, message", [("pending", PENDING), ("blocked", BLOCKED)])
def test_inactive_status_revealed_only_after_right_password(client, factory, status, message):
    factory.user("u", status=status)
    wrong = page_text(login(client, "u", "wrong-password"))
    assert WRONG in wrong and message not in wrong
    right = login(client, "u")
    assert message in page_text(right)
    assert client.get("/").status_code == 302  # вход не выполнен


def test_login_without_csrf_rejected(client, factory):
    factory.user("zoe")
    response = client.post("/auth/login", data={"username": "zoe", "password": PASSWORD})
    assert response.status_code == 400
    assert client.get("/").status_code == 302


def test_blocked_user_is_logged_out_immediately(app, client, factory):
    user_id = factory.user("zoe")
    login(client, "zoe")
    assert client.get("/").status_code == 200
    with app.app_context():
        db.session.get(User, user_id).is_active = False
        db.session.commit()
    assert client.get("/").status_code == 302


@pytest.mark.parametrize("status, loaded", [("active", True), ("blocked", False), ("pending", False)])
def test_user_loader_rejects_inactive(app, factory, status, loaded):
    # Второй уровень защиты: Flask-Login и так считает неактивного «не вошедшим»
    # (UserMixin.is_authenticated = is_active), но и загрузчик его не отдаёт.
    from app.models import load_user

    user_id = factory.user("u", status=status)
    with app.app_context():
        assert (load_user(str(user_id)) is not None) == loaded


def test_logged_in_user_skips_login_and_register(client, factory):
    factory.user("zoe")
    login(client, "zoe")
    assert client.get("/auth/login").headers["Location"] == "/"
    assert client.get("/auth/register").headers["Location"] == "/"


# --- Переход на next после входа -------------------------------------------------

def test_next_inside_site(client, factory):
    factory.user("zoe")
    token = csrf_token(client, "/auth/login")
    response = client.post(
        "/auth/login?next=%2Fbugs%2F",
        data={"username": "zoe", "password": PASSWORD, "csrf_token": token},
    )
    assert response.headers["Location"] == "/bugs/"


@pytest.mark.parametrize("evil", ["https://evil.com", "//evil.com", "/\\evil.com"])
def test_next_to_other_site_ignored(client, factory, evil):
    factory.user("zoe")
    token = csrf_token(client, "/auth/login")
    response = client.post(
        "/auth/login?next=" + quote(evil, safe=""),
        data={"username": "zoe", "password": PASSWORD, "csrf_token": token},
    )
    assert response.headers["Location"] == "/"


# --- Выход ---------------------------------------------------------------------

def test_logout_only_post_with_csrf(client, factory):
    factory.user("zoe")
    login(client, "zoe")
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 400
    assert client.get("/").status_code == 200  # всё ещё в системе
    response = post(client, "/auth/logout")
    assert response.headers["Location"] == "/auth/login"
    assert client.get("/").status_code == 302


# --- Регистрация ---------------------------------------------------------------

REGISTRATION = {
    "username": "newbie",
    "email": "newbie@example.com",
    "password": PASSWORD,
    "password2": PASSWORD,
}


def test_registration_creates_pending_tester(app, client):
    response = post(client, "/auth/register", REGISTRATION, token_page="/auth/register")
    assert response.headers["Location"] == "/auth/login"
    user = get_user(app, "newbie")
    assert user["status"] == "pending"
    assert user["role"] == "tester"
    assert user["hash_ok"] and user["hash"] != PASSWORD
    assert PENDING in page_text(login(client, "newbie"))


def test_registration_cannot_choose_role(app, client):
    data = dict(REGISTRATION, role="admin", is_active="y", approved_at="2026-01-01")
    post(client, "/auth/register", data, token_page="/auth/register")
    user = get_user(app, "newbie")
    assert user["role"] == "tester" and user["status"] == "pending"


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"email": "not-an-email"}, "Введите корректный адрес почты."),
        ({"password": "123", "password2": "123"}, "Пароль должен быть не короче 8 символов."),
        ({"password2": "other-password"}, "Пароли не совпадают."),
        ({"username": ""}, "Заполните это поле."),
    ],
)
def test_registration_validation(app, client, changes, error):
    data = dict(REGISTRATION, **changes)
    response = post(client, "/auth/register", data, token_page="/auth/register")
    assert response.status_code == 200
    assert error in page_text(response)
    assert get_user(app, "newbie") is None


def test_registration_duplicates_rejected(client, factory):
    factory.user("newbie")
    response = post(client, "/auth/register", REGISTRATION, token_page="/auth/register")
    text = page_text(response)
    assert "Этот логин уже занят." in text
    assert "Эта почта уже зарегистрирована." in text


def test_success_message_after_registration(client):
    post(client, "/auth/register", REGISTRATION, token_page="/auth/register")
    messages = flash_messages(client, "/auth/login")
    assert any("Заявка на регистрацию отправлена" in m for m in messages)


# --- Команда flask create-admin -----------------------------------------------

def run_create_admin(app, answers):
    return app.test_cli_runner().invoke(create_admin, input="\n".join(answers) + "\n")


def test_create_admin_command(app, client):
    result = run_create_admin(app, ["boss", "boss@example.com", PASSWORD, PASSWORD])
    assert result.exit_code == 0
    assert PASSWORD not in result.output  # пароль не печатается
    user = get_user(app, "boss")
    assert user["role"] == "admin" and user["status"] == "active"
    login(client, "boss")
    assert client.get("/admin/").status_code == 200


@pytest.mark.parametrize(
    "answers, error",
    [
        (["boss", "boss@example.com", "123", "123"], "не короче 8 символов"),
        (["zoe", "boss@example.com", PASSWORD, PASSWORD], "уже занят"),
        (["boss", "zoe@example.com", PASSWORD, PASSWORD], "уже зарегистрирована"),
    ],
)
def test_create_admin_command_errors(app, factory, answers, error):
    factory.user("zoe")
    result = run_create_admin(app, answers)
    assert result.exit_code == 1
    assert error in result.output
    assert get_user(app, "boss") is None
