"""Сквозные тесты в настоящем браузере (Playwright).

Приложение запускается «живым» сервером на тестовой базе, браузер
открывает страницы, заполняет поля и нажимает кнопки, как человек.

Запуск:
    pytest -m e2e                     # браузер без окна
    pytest -m e2e --headed --slowmo 500   # смотреть, как браузер работает
Первый раз нужно скачать браузер: python -m playwright install chromium
"""

import threading

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from tests.helpers import PASSWORD

# Все тесты файла помечены как e2e
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def live_server(app):
    """Приложение на настоящем адресе http://127.0.0.1:<порт>.

    Сервер работает в отдельном потоке: он отвечает браузеру, пока тест
    командует браузером. Порт 0 — «выбери любой свободный».
    """
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def browser_login(page, live_server, username):
    page.goto(f"{live_server}/auth/login")
    page.get_by_label("Логин").fill(username)
    page.get_by_label("Пароль").fill(PASSWORD)
    page.get_by_role("button", name="Войти").click()


def test_login(page, live_server, factory):
    factory.user("zoe", "tester")

    # Гость открывает главную — его отправляют на вход с подсказкой
    page.goto(live_server + "/")
    expect(page).to_have_url(f"{live_server}/auth/login?next=%2F")
    expect(page.locator(".flash-info")).to_have_text("Войдите, чтобы открыть эту страницу.")

    # Неверный пароль
    page.get_by_label("Логин").fill("zoe")
    page.get_by_label("Пароль").fill("wrong-password")
    page.get_by_role("button", name="Войти").click()
    expect(page.locator(".flash-error")).to_have_text("Неверный логин или пароль.")

    # Верный пароль — главная, имя и роль в шапке, меню
    browser_login(page, live_server, "zoe")
    expect(page).to_have_url(f"{live_server}/")
    expect(page.locator(".topbar .user")).to_have_text("zoe (tester)")
    expect(page.get_by_role("link", name="Баги")).to_be_visible()
    # Пункта админки у тестировщика нет
    expect(page.get_by_role("link", name="Пользователи")).to_have_count(0)


def test_create_bug(page, live_server, factory):
    admin = factory.user("adm", "admin")
    zoe = factory.user("zoe", "tester")
    factory.project("Сайт магазина", admin, [zoe])

    browser_login(page, live_server, "zoe")
    page.get_by_role("link", name="Сайт магазина").click()
    page.get_by_role("link", name="Сообщить о баге").click()

    # Отправка без серьёзности — ошибка под полем, баг не создан
    page.get_by_label("Заголовок").fill("Не работает кнопка «Купить»")
    page.get_by_role("button", name="Создать").click()
    expect(page.locator(".field-error")).to_have_text("Выберите серьёзность.")

    page.get_by_label("Шаги воспроизведения").fill("1. Открыть товар\n2. Нажать «Купить»")
    page.get_by_label("Фактический результат").fill("Ничего не происходит")
    page.get_by_label("Серьёзность").select_option("critical")
    page.get_by_role("button", name="Создать").click()

    # Карточка созданного бага
    expect(page.locator(".flash-success")).to_have_text("Баг #1 создан.")
    expect(page.locator("h1")).to_have_text("#1 Не работает кнопка «Купить»")
    expect(page.locator(".status-bar .status")).to_have_text("Новый")
    expect(page.get_by_text("Критическая")).to_be_visible()
    expect(page.get_by_text("Ничего не происходит")).to_be_visible()

    # Баг виден в общем списке
    page.get_by_role("link", name="Баги").click()
    expect(page.get_by_role("link", name="Не работает кнопка «Купить»")).to_be_visible()


def test_status_change(page, live_server, factory):
    admin = factory.user("adm", "admin")
    zoe = factory.user("zoe", "tester")
    bob = factory.user("bob", "developer")
    project = factory.project("P", admin, [zoe, bob])
    bug = factory.bug(project, zoe, title="Падает вход")
    bug_url = f"{live_server}/bugs/{bug}"
    status = page.locator(".status-bar .status")

    # Разработчик берёт баг в работу и помечает исправленным
    browser_login(page, live_server, "bob")
    page.goto(bug_url)
    page.get_by_role("button", name="Взять в работу").click()
    expect(status).to_have_text("В работе")
    expect(page.locator(".props")).to_contain_text("bob")  # стал исполнителем
    page.get_by_role("button", name="Исправлено").click()
    expect(status).to_have_text("Исправлен")
    # Закрыть может только тестировщик — у разработчика кнопки нет
    expect(page.get_by_role("button", name="Закрыть")).to_have_count(0)

    page.get_by_role("button", name="Выйти").click()
    expect(page).to_have_url(f"{live_server}/auth/login")

    # Тестировщик проверяет и закрывает
    browser_login(page, live_server, "zoe")
    page.goto(bug_url)
    page.get_by_role("button", name="Закрыть").click()
    expect(status).to_have_text("Закрыт")
    expect(page.locator(".flash-success")).to_have_text("Статус изменён: «Закрыт».")

    # История: создание + три перехода, записанных триггером
    history = page.locator("#history-table tbody tr")
    expect(history).to_have_count(4)
    expect(history.nth(1)).to_contain_text("bob")
    expect(history.nth(3)).to_contain_text("zoe")
    expect(history.nth(3)).to_contain_text("Закрыт")
