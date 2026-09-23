"""Настройки для сервера: адрес базы, SECRET_KEY, журнал в консоль."""

import logging
from logging.handlers import RotatingFileHandler

import pytest

from app import create_app
from config import Config, TestConfig, database_url


@pytest.mark.parametrize(
    "given, expected",
    [
        # Так выдаёт адрес Render
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        # Уже с драйвером — не трогаем
        ("postgresql+psycopg://u:p@localhost/db", "postgresql+psycopg://u:p@localhost/db"),
        # Параметры после ? сохраняются
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        (None, None),
        ("", ""),
    ],
)
def test_database_url(given, expected):
    assert database_url(given) == expected


def make_config(**settings):
    """Класс настроек «как на сервере»: не тестовый, база не нужна."""
    return type("ServerConfig", (Config,), dict(
        TESTING=False,
        SQLALCHEMY_DATABASE_URI="postgresql+psycopg://unused@localhost/unused",
        **settings,
    ))


@pytest.mark.parametrize("key", [None, ""])
def test_app_refuses_to_start_without_secret_key(key):
    with pytest.raises(RuntimeError, match="Не задан SECRET_KEY"):
        create_app(make_config(SECRET_KEY=key))


def test_test_config_always_has_secret_key():
    assert TestConfig.SECRET_KEY


def file_handlers(app):
    return [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)]


def test_log_to_stdout(capsys):
    app = create_app(make_config(SECRET_KEY="k", LOG_TO_STDOUT=True))
    assert file_handlers(app) == []
    app.logger.info("Проверка журнала в консоль")
    output = capsys.readouterr().out
    # Ровно одна строка: встроенный обработчик Flask убран, дублей нет
    assert output.count("Проверка журнала в консоль") == 1
    assert "INFO: Проверка журнала в консоль [in " in output


def test_log_to_file_by_default(tmp_path):
    app = create_app(make_config(SECRET_KEY="k", LOG_TO_STDOUT=False, LOG_DIR=str(tmp_path)))
    handlers = file_handlers(app)
    try:
        assert len(handlers) == 1
        assert app.logger.level == logging.INFO
    finally:
        for handler in handlers:
            app.logger.removeHandler(handler)
            handler.close()


@pytest.mark.parametrize("secure", [True, False])
def test_session_cookie_secure_flag(secure):
    # Журнал в консоль: файловый журнал в тестах не создаём
    app = create_app(make_config(
        SECRET_KEY="k", LOG_TO_STDOUT=True, SESSION_COOKIE_SECURE=secure
    ))
    # Форма входа кладёт CSRF-токен в сессию — сервер присылает cookie
    response = app.test_client().get("/auth/login")
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("session=")
    assert ("Secure" in cookie) == secure
