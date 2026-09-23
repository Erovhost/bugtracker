"""Журнал приложения (app/logs.py и записи в маршрутах).

caplog — фикстура pytest, которая перехватывает записи журнала.
"""

import logging
from logging.handlers import RotatingFileHandler

import pytest

from app.logs import setup_file_logging
from tests.helpers import PASSWORD, login, post
from tests.test_errors import make_app_with_broken_route


@pytest.fixture
def log(caplog):
    # Журнал приложения называется по имени пакета — "app"
    caplog.set_level(logging.INFO, logger="app")
    return caplog


def records(log, level):
    return [r.getMessage() for r in log.records if r.levelname == level]


def test_failed_login_logged_without_password(client, factory, log):
    factory.user("zoe")
    login(client, "zoe", "wrong-password")
    warnings = records(log, "WARNING")
    assert any("Неудачный вход: логин «zoe»" in m and "IP" in m for m in warnings)
    # Ни введённый, ни настоящий пароль в журнал не попадают
    assert "wrong-password" not in log.text
    assert PASSWORD not in log.text


def test_successful_login_and_logout_logged(client, factory, log):
    factory.user("zoe", "tester")
    login(client, "zoe")
    post(client, "/auth/logout")
    infos = records(log, "INFO")
    assert any("Вход: «zoe» (tester)" in m for m in infos)
    assert any("Выход: «zoe»" in m for m in infos)
    assert PASSWORD not in log.text


@pytest.mark.parametrize("status", ["pending", "blocked"])
def test_inactive_login_attempt_logged(client, factory, log, status):
    factory.user("u", status=status)
    login(client, "u")
    assert any(f"неактивного пользователя «u» ({status})" in m for m in records(log, "WARNING"))


def test_registration_logged(client, log):
    data = {"username": "newbie", "email": "newbie@example.com",
            "password": PASSWORD, "password2": PASSWORD}
    post(client, "/auth/register", data, token_page="/auth/register")
    assert any("Новая заявка на регистрацию: «newbie»" in m for m in records(log, "INFO"))
    assert PASSWORD not in log.text


def test_forbidden_logged(client, factory, log):
    factory.user("zoe", "tester")
    login(client, "zoe")
    client.get("/admin/")
    assert any(
        "Отказ в доступе (403): GET /admin/" in m and "«zoe»" in m
        for m in records(log, "WARNING")
    )


def test_csrf_rejection_logged(client, factory, log):
    factory.user("zoe")
    login(client, "zoe")
    client.post("/auth/logout")
    assert any("без верного CSRF-токена: POST /auth/logout" in m for m in records(log, "WARNING"))


def test_admin_actions_logged(client, factory, log):
    factory.user("adm", "admin")
    bob = factory.user("bob", "developer")
    login(client, "adm")
    post(client, f"/admin/users/{bob}/block")
    post(client, f"/admin/users/{bob}/unblock")
    post(client, f"/admin/users/{bob}/role", {"role": "tester"})
    post(client, "/project/new", {"name": "P"})
    infos = records(log, "INFO")
    for expected in [
        "Админ «adm» заблокировал «bob»",
        "Админ «adm» разблокировал «bob»",
        "Админ «adm» сменил роль «bob»: developer → tester",
        "Админ «adm» создал проект «P»",
    ]:
        assert any(expected in m for m in infos), expected


def test_server_error_logged_with_traceback(factory, log):
    factory.user("zoe")
    app = make_app_with_broken_route()
    client = app.test_client()
    login(client, "zoe")
    client.get("/broken")
    errors = [r for r in log.records if r.levelname == "ERROR"]
    assert errors, "ошибка 500 не записана"
    assert errors[0].exc_info is not None  # с трассировкой
    assert "no_such_table" in log.text


def test_file_logging(app, tmp_path):
    # tmp_path — временная папка pytest; журнал пишется в файл в UTF-8
    handler = setup_file_logging(app, tmp_path)
    try:
        app.logger.info("Проверка журнала: кириллица")
        handler.flush()
        content = (tmp_path / "bugtracker.log").read_text(encoding="utf-8")
        assert "INFO: Проверка журнала: кириллица" in content
        assert "[in " in content  # файл и строка кода
        assert handler.maxBytes == 1_000_000 and handler.backupCount == 10
    finally:
        app.logger.removeHandler(handler)
        handler.close()


def test_no_log_file_in_tests(app):
    handlers = [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)]
    assert handlers == []
