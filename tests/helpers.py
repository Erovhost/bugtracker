"""Помощники для тестов: вход и отправка форм с CSRF-токеном.

Использование в тестах:
    from tests.helpers import login, post
"""

import re

# Пароль всех пользователей, которых создаёт factory
PASSWORD = "secret123"


# --- Работа с формами --------------------------------------------------------

def csrf_token(client, url="/"):
    """CSRF-токен со страницы (из hidden-поля формы) — той же сессии клиента."""
    html = client.get(url).get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match, f"на странице {url} нет CSRF-токена"
    return match.group(1)


def login(client, username, password=PASSWORD):
    """Войти так же, как через браузер. Возвращает ответ на POST."""
    token = csrf_token(client, "/auth/login")
    return client.post(
        "/auth/login",
        data={"username": username, "password": password, "csrf_token": token},
    )


def post(client, url, data=None, token_page="/"):
    """Отправить форму с CSRF-токеном текущей сессии."""
    form = dict(data or {})
    form["csrf_token"] = csrf_token(client, token_page)
    return client.post(url, data=form)


def flash_messages(client, url="/"):
    """Тексты flash-сообщений на странице (показываются один раз)."""
    html = client.get(url).get_data(as_text=True)
    return re.findall(r'class="flash flash-\w+">([^<]+)<', html)
