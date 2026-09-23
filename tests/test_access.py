"""Права доступа и общие свойства маршрутов.

Часть тестов обходит ВСЕ маршруты приложения (app.url_map): новый
маршрут без защиты будет пойман без правки тестов.
"""

import re

import pytest

from tests.helpers import csrf_token, login, post

# Страницы, открытые без входа
PUBLIC_ENDPOINTS = {"auth.login", "auth.register", "static"}


@pytest.fixture
def world(factory):
    """P1: zoe (tester), bob (developer), баг B1. P2: eve (developer), баг B2."""
    ids = {
        "adm": factory.user("adm", "admin"),
        "zoe": factory.user("zoe", "tester"),
        "bob": factory.user("bob", "developer"),
        "eve": factory.user("eve", "developer"),
    }
    ids["P1"] = factory.project("P1", ids["adm"], [ids["zoe"], ids["bob"]])
    ids["P2"] = factory.project("P2", ids["adm"], [ids["eve"]])
    ids["B1"] = factory.bug(ids["P1"], ids["zoe"], assignee_id=ids["bob"], title="bug one")
    ids["B2"] = factory.bug(ids["P2"], ids["adm"], assignee_id=ids["eve"], title="bug two")
    return ids


def client_for(app, username):
    client = app.test_client()
    login(client, username)
    return client


def build_url(app, rule):
    """Адрес по правилу маршрута: параметры <int:...> заменяем на 1."""
    return re.sub(r"<(?:int:)?[^>]+>", "1", rule.rule)


def rules_with(app, method):
    return [r for r in app.url_map.iter_rules() if method in r.methods]


# --- Свойства всех маршрутов -------------------------------------------------

def test_guest_is_redirected_from_every_private_page(app, client):
    pages = [r for r in rules_with(app, "GET") if r.endpoint not in PUBLIC_ENDPOINTS]
    assert pages, "маршруты не найдены"
    for rule in pages:
        response = client.get(build_url(app, rule))
        assert response.status_code == 302, rule.rule
        assert "/auth/login" in response.headers["Location"], rule.rule


# Страницы с формой: GET показывает форму, POST её отправляет.
# Все остальные маршруты с POST — действия, у них GET запрещён.
FORM_PAGES = {
    "auth.login",
    "auth.register",
    "projects.create",
    "projects.edit",
    "bugs.create",
    "bugs.edit",
    "admin.create_user",
}


def test_actions_do_not_accept_get(app):
    # Правило ТЗ: GET никогда ничего не меняет. Если к действию
    # случайно добавят GET, оно попадёт сюда.
    for rule in rules_with(app, "POST"):
        if "GET" in rule.methods:
            assert rule.endpoint in FORM_PAGES, f"{rule.rule} принимает GET"


def test_post_only_routes_reject_get(app, world):
    admin = client_for(app, "adm")
    post_only = [r for r in rules_with(app, "POST") if "GET" not in r.methods]
    assert len(post_only) >= 10
    for rule in post_only:
        assert admin.get(build_url(app, rule)).status_code == 405, rule.rule


def test_every_post_requires_csrf_token(app, world):
    admin = client_for(app, "adm")
    for rule in rules_with(app, "POST"):
        response = admin.post(build_url(app, rule), data={})
        assert response.status_code == 400, rule.rule


def test_admin_area_forbidden_for_other_roles(app, world):
    admin_rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith("admin.")]
    for username in ["zoe", "bob"]:
        client = client_for(app, username)
        for rule in admin_rules:
            url = build_url(app, rule)
            if "GET" in rule.methods:
                assert client.get(url).status_code == 403, (username, rule.rule)
            if "POST" in rule.methods:
                assert post(client, url).status_code == 403, (username, rule.rule)


# --- Проекты -----------------------------------------------------------------

def test_project_list_shows_only_own_projects(app, world):
    zoe_page = client_for(app, "zoe").get("/").get_data(as_text=True)
    assert ">P1<" in zoe_page and ">P2<" not in zoe_page
    admin_page = client_for(app, "adm").get("/").get_data(as_text=True)
    assert ">P1<" in admin_page and ">P2<" in admin_page


def test_project_page_access(app, world):
    zoe = client_for(app, "zoe")
    assert zoe.get(f"/project/{world['P1']}").status_code == 200
    assert zoe.get(f"/project/{world['P2']}").status_code == 403
    assert zoe.get("/project/9999").status_code == 404
    assert client_for(app, "adm").get(f"/project/{world['P2']}").status_code == 200


def test_only_admin_manages_projects(app, world):
    for username in ["zoe", "bob"]:
        client = client_for(app, username)
        assert client.get("/project/new").status_code == 403
        assert client.get(f"/project/{world['P1']}/edit").status_code == 403
        add = post(client, f"/project/{world['P1']}/members/add", {"user_id": world["eve"]})
        assert add.status_code == 403
        remove_url = f"/project/{world['P1']}/members/{world['bob']}/remove"
        assert post(client, remove_url).status_code == 403
    admin = client_for(app, "adm")
    assert admin.get("/project/new").status_code == 200
    assert admin.get(f"/project/{world['P1']}/edit").status_code == 200


# --- Баги ----------------------------------------------------------------------

def test_bug_page_access(app, world):
    zoe = client_for(app, "zoe")
    assert zoe.get(f"/bugs/{world['B1']}").status_code == 200
    assert zoe.get(f"/bugs/{world['B2']}").status_code == 403
    assert zoe.get("/bugs/9999").status_code == 404
    assert client_for(app, "adm").get(f"/bugs/{world['B2']}").status_code == 200


def test_bug_actions_on_foreign_bug_forbidden(app, world):
    zoe = client_for(app, "zoe")
    b2 = world["B2"]
    assert post(zoe, f"/bugs/{b2}/comments", {"text": "x"}).status_code == 403
    assert post(zoe, f"/bugs/{b2}/status", {"new_status": "fixed"}).status_code == 403
    assert zoe.get(f"/bugs/{b2}/edit").status_code == 403


def test_bug_list_shows_only_own_projects(app, world):
    page = client_for(app, "zoe").get("/bugs/").get_data(as_text=True)
    assert "bug one" in page and "bug two" not in page
    admin_page = client_for(app, "adm").get("/bugs/").get_data(as_text=True)
    assert "bug one" in admin_page and "bug two" in admin_page


def test_filter_cannot_reveal_foreign_bugs(app, world):
    zoe = client_for(app, "zoe")
    page = zoe.get(f"/bugs/?assignee={world['eve']}").get_data(as_text=True)
    assert "bug two" not in page
    # eve не назначена на видимые zoe баги — её нет и в списке фильтра
    assert ">eve" not in zoe.get("/bugs/").get_data(as_text=True)


def test_filter_ignores_garbage(app, world):
    zoe = client_for(app, "zoe")
    page = zoe.get("/bugs/?status=hack&severity=%27%20OR%201%3D1&assignee=abc")
    assert page.status_code == 200
    assert "bug one" in page.get_data(as_text=True)


def test_stats_only_own_projects(app, world):
    zoe_page = client_for(app, "zoe").get("/bugs/stats").get_data(as_text=True)
    assert ">P1<" in zoe_page and ">P2<" not in zoe_page
    admin_page = client_for(app, "adm").get("/bugs/stats").get_data(as_text=True)
    assert ">P1<" in admin_page and ">P2<" in admin_page


@pytest.mark.parametrize(
    "username, expected",
    [("zoe", 200), ("bob", 403), ("adm", 403), ("outsider", 403)],
)
def test_who_can_create_bug(app, factory, world, username, expected):
    if username == "outsider":
        factory.user("outsider", "tester")  # тестировщик, но не участник P1
    client = client_for(app, username)
    assert client.get(f"/bugs/project/{world['P1']}/new").status_code == expected


@pytest.mark.parametrize("username, expected", [("zoe", 200), ("adm", 200), ("bob", 403)])
def test_who_can_edit_bug(app, world, username, expected):
    # B1: автор zoe; admin может; bob — участник, но не автор
    client = client_for(app, username)
    assert client.get(f"/bugs/{world['B1']}/edit").status_code == expected


def test_edit_link_only_for_allowed(app, world):
    url = f"/bugs/{world['B1']}"
    assert "Редактировать" in client_for(app, "zoe").get(url).get_data(as_text=True)
    assert "Редактировать" not in client_for(app, "bob").get(url).get_data(as_text=True)


def test_csrf_token_from_other_session_rejected(app, world):
    zoe = client_for(app, "zoe")
    other = client_for(app, "bob")
    foreign_token = csrf_token(other)
    response = zoe.post(
        f"/bugs/{world['B1']}/comments", data={"text": "x", "csrf_token": foreign_token}
    )
    assert response.status_code == 400
