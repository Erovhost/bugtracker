"""Демо-данные: пользователи всех ролей, проекты, баги во всех статусах.

Статусы проставляются через правила жизненного цикла (app/workflow.py),
поэтому историю в status_history пишет триггер — как при работе через сайт.
Запуск: flask seed-demo (команда в app/cli.py).
"""

import sqlalchemy as sa

from app import db
from app.models import Bug, Comment, Project, Role, User
from app.workflow import apply_transition, check_transition

# Пароль всех демо-аккаунтов. Он известен всем — только для демонстрации!
DEMO_PASSWORD = "demo12345"

# (логин, роль, статус учётной записи)
DEMO_USERS = [
    ("demo_admin", "admin", "active"),
    ("anna", "tester", "active"),
    ("igor", "tester", "active"),
    ("petr", "developer", "active"),
    ("olga", "developer", "active"),
    ("blocked_dev", "developer", "active"),  # заблокируем в конце
    ("new_user", "tester", "pending"),       # заявка на регистрацию
]


def demo_data_exists():
    query = sa.select(User).where(User.username == "demo_admin")
    return db.session.scalar(query) is not None


def create_user(username, role_name, status):
    role = db.session.scalar(sa.select(Role).where(Role.name == role_name))
    user = User(
        username=username,
        email=f"{username}@demo.example",
        role=role,
        is_active=status == "active",
        approved_at=sa.func.now() if status == "active" else None,
    )
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    return user


def create_bug(project, reporter, title, severity, priority, **fields):
    bug = Bug(
        project=project,
        title=title,
        severity=severity,
        priority=priority,
        reporter=reporter,
        updater=reporter,
        **fields,
    )
    db.session.add(bug)
    db.session.commit()
    return bug


def move(bug, user, new_status, comment=None):
    """Сменить статус по правилам жизненного цикла, как кнопкой на сайте."""
    error = check_transition(user, bug, new_status, comment)
    if error is not None:
        raise RuntimeError(f"Демо-данные нарушают правила: {error}")
    apply_transition(user, bug, new_status, comment)
    # Коммит после каждого перехода — триггер пишет строку истории
    db.session.commit()


def comment(bug, author, text):
    db.session.add(Comment(bug=bug, author=author, text=text))
    db.session.commit()


def create_demo_data():
    """Создать демо-данные. Возвращает словарь с количеством созданных записей."""
    users = {}
    for username, role_name, status in DEMO_USERS:
        users[username] = create_user(username, role_name, status)
    db.session.commit()
    admin, anna, igor = users["demo_admin"], users["anna"], users["igor"]
    petr, olga, blocked_dev = users["petr"], users["olga"], users["blocked_dev"]

    shop = Project(
        name="Интернет-магазин",
        description="Сайт магазина: каталог, корзина, оформление заказа.",
        creator=admin,
    )
    mobile = Project(
        name="Мобильное приложение",
        description="Приложение магазина для Android и iOS.",
        creator=admin,
    )
    portal = Project(
        name="Внутренний портал",
        description="Портал для сотрудников. Работы ещё не начаты.",
        creator=admin,
    )
    db.session.add_all([shop, mobile, portal])
    shop.members.extend([anna, igor, petr, olga])
    mobile.members.extend([igor, petr, blocked_dev])
    db.session.commit()

    # --- Интернет-магазин ---
    create_bug(
        shop, anna, "Кнопка «Купить» не реагирует на нажатие", "critical", "high",
        steps="1. Открыть карточку товара\n2. Нажать «Купить»",
        expected="Товар добавляется в корзину",
        actual="Ничего не происходит",
        environment="Chrome 128, Windows 11",
    )  # new, свободен

    cart = create_bug(
        shop, anna, "Неверная сумма в корзине при скидке", "major", "high",
        steps="1. Добавить товар со скидкой\n2. Открыть корзину",
        expected="Сумма с учётом скидки",
        actual="Сумма без скидки",
    )
    move(cart, petr, "in_progress")  # petr взял в работу

    typo = create_bug(
        shop, igor, "Опечатка на странице доставки", "trivial", "low",
        actual="«Доставка осуществляеться»",
    )
    move(typo, olga, "in_progress")
    move(typo, olga, "fixed")  # ждёт проверки тестировщиком

    email = create_bug(
        shop, anna, "Не приходит письмо о заказе", "critical", "high",
        steps="1. Оформить заказ\n2. Проверить почту",
        expected="Письмо с номером заказа",
        actual="Письма нет",
        environment="Сервер тестовый",
    )
    move(email, petr, "in_progress")
    move(email, petr, "fixed")
    comment(email, igor, "Письмо приходит, но без номера заказа. Возвращаю.")
    move(email, igor, "in_progress")  # проверка не прошла
    comment(email, petr, "Добавил номер заказа в шаблон письма.")
    move(email, petr, "fixed")
    move(email, anna, "closed")

    price_filter = create_bug(
        shop, igor, "Фильтр по цене показывает товары дороже заданной", "minor", "medium",
        expected="Только товары до указанной цены",
        actual="Есть товары дороже на 1–2 рубля",
    )
    move(
        price_filter, olga, "rejected",
        "Так задумано: фильтр сравнивает цену без учёта копеек, это требование заказчика.",
    )

    catalog = create_bug(
        shop, anna, "Каталог загружается больше 5 секунд", "major", "medium",
        environment="Мобильный интернет 3G",
    )
    catalog.assignee = olga  # автор назначил исполнителя, работа ещё не начата
    catalog.updater = anna
    db.session.commit()

    # --- Мобильное приложение ---
    crash = create_bug(
        mobile, igor, "Приложение закрывается при повороте экрана", "critical", "high",
        steps="1. Открыть корзину\n2. Повернуть телефон",
        actual="Приложение закрывается",
        environment="Android 14",
    )
    move(crash, blocked_dev, "in_progress")
    move(crash, blocked_dev, "fixed")
    move(crash, igor, "closed")

    theme = create_bug(
        mobile, igor, "Не сохраняется тёмная тема после перезапуска", "minor", "low",
    )
    move(theme, petr, "in_progress")
    comment(theme, igor, "Воспроизводится и на iOS 18.")

    # Разработчик заблокирован после работы: закрытый баг сохраняет его
    # как исполнителя (в карточке — пометка «заблокирован»)
    blocked_dev.is_active = False
    db.session.commit()

    demo_projects = [shop.id, mobile.id, portal.id]
    return {
        "users": len(DEMO_USERS),
        "projects": len(demo_projects),
        "bugs": db.session.scalar(
            sa.select(sa.func.count(Bug.id)).where(Bug.project_id.in_(demo_projects))
        ),
    }
