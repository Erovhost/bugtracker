"""Страницы ошибок 400/403/404/500 (app/errors.py)."""

import sqlalchemy as sa

from app import create_app, db
from config import TestConfig
from tests.helpers import login


def text(response):
    return response.get_data(as_text=True)


def test_404_page(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Страница не найдена" in text(response)
    assert "Вход</a>" in text(response)  # общее оформление с меню


def test_404_for_missing_bug(client, factory):
    factory.user("zoe")
    login(client, "zoe")
    response = client.get("/bugs/9999")
    assert response.status_code == 404
    assert "Страница не найдена" in text(response)


def test_403_page(client, factory):
    factory.user("zoe", "tester")
    login(client, "zoe")
    response = client.get("/admin/")
    assert response.status_code == 403
    assert "Недостаточно прав" in text(response)
    assert "zoe (tester)" in text(response)


def test_400_page_for_missing_csrf(client, factory):
    factory.user("zoe")
    login(client, "zoe")
    response = client.post("/auth/logout")
    assert response.status_code == 400
    assert "Страница устарела" in text(response)


def make_app_with_broken_route():
    """Отдельное приложение с маршрутом, который падает на ошибке базы."""
    app = create_app(TestConfig)
    # В тестах Flask по умолчанию пробрасывает исключения наружу;
    # здесь нужно, чтобы сработал наш обработчик 500
    app.config["PROPAGATE_EXCEPTIONS"] = False

    def broken():
        db.session.execute(sa.text("SELECT * FROM no_such_table"))
        return "не дойдёт"

    app.add_url_rule("/broken", view_func=broken)
    return app


def test_500_page_after_database_error(factory):
    factory.user("zoe", "tester")
    app = make_app_with_broken_route()
    client = app.test_client()
    login(client, "zoe")

    response = client.get("/broken")
    assert response.status_code == 500
    page = text(response)
    assert "Внутренняя ошибка сервера" in page
    # Шапка страницы ошибки читает роль пользователя из базы — это работает
    # только потому, что обработчик откатил «сломанную» транзакцию
    assert "zoe (tester)" in page

    # Следующий запрос работает как обычно
    assert client.get("/").status_code == 200
