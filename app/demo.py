"""Демо-данные: flask seed и flask seed --restore-demo (команда в app/cli.py).

Демо-аккаунт — это пользователь, у которого совпадают И логин, И почта на
домене demo.example. Так настоящий пользователь, зарегистрировавшийся,
например, как «bob», никогда не будет принят за демо-аккаунт: ему не
сбросят пароль и не сменят роль.

Статусы багов меняются через те же функции, что и кнопки на сайте
(app/workflow.py), поэтому историю в status_history пишет триггер.
"""

import sqlalchemy as sa

from app import db
from app.assignments import unassign_user_bugs
from app.models import Bug, Comment, Project, Role, User
from app.workflow import apply_transition, check_transition

# Пароли демо-аккаунтов известны всем — только для демонстрации!
DEMO_ACCOUNTS = [
    {"username": "pixel", "role": "admin", "password": "qwerty123"},
    {"username": "ana", "role": "tester", "password": "qwerty"},
    {"username": "bob", "role": "developer", "password": "qwerty"},
]
DEMO_PROJECT = "Демо: интернет-магазин"
# Участники демо-проекта (админу участие не нужно — он видит всё)
DEMO_MEMBERS = ["ana", "bob"]


class DemoError(Exception):
    """Демо-данные нельзя создать (например, логин занят настоящим пользователем)."""


def demo_email(username):
    return f"{username}@demo.example"


def find_user(username):
    return db.session.scalar(sa.select(User).where(User.username == username))


def is_demo_account(user):
    return user.email == demo_email(user.username)


def find_role(name):
    return db.session.scalar(sa.select(Role).where(Role.name == name))


def find_demo_project():
    return db.session.scalar(sa.select(Project).where(Project.name == DEMO_PROJECT))


# --- flask seed ------------------------------------------------------------------

def create_account(account):
    user = User(
        username=account["username"],
        email=demo_email(account["username"]),
        role=find_role(account["role"]),
        is_active=True,
        approved_at=sa.func.now(),
    )
    user.set_password(account["password"])
    db.session.add(user)
    return user


def move(bug, user, new_status, comment=None):
    """Сменить статус по правилам жизненного цикла, как кнопкой на сайте."""
    error = check_transition(user, bug, new_status, comment)
    if error is not None:
        raise DemoError(f"Демо-данные нарушают правила: {error}")
    apply_transition(user, bug, new_status, comment)
    # Отправляем изменение в базу сразу, по двум причинам:
    # 1) иначе bug.assignee_id останется пустым до сохранения, и следующая
    #    проверка «только исполнитель» откажет (связь assignee уже есть,
    #    а числовая колонка заполняется только при отправке в базу);
    # 2) иначе несколько переходов подряд склеятся в один UPDATE,
    #    и триггер запишет одну строку истории вместо нескольких
    db.session.flush()


def add_comment(bug, author, text):
    db.session.add(Comment(bug=bug, author=author, text=text))
    db.session.flush()


def new_bug(project, reporter, title, severity, priority, **fields):
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
    db.session.flush()
    return bug


def create_demo_bugs(project, ana, bob):
    """Пять багов — по одному на каждый статус, у каждого есть комментарии."""
    # new
    buy = new_bug(
        project, ana, "Кнопка «Купить» не реагирует на нажатие", "critical", "high",
        steps="1. Открыть карточку товара\n2. Нажать «Купить»",
        expected="Товар добавляется в корзину",
        actual="Ничего не происходит",
        environment="Chrome 128, Windows 11",
    )
    add_comment(buy, bob, "В каком браузере ещё проверяли? В Firefox у меня работает.")

    # in_progress
    cart = new_bug(
        project, ana, "Неверная сумма в корзине при скидке", "major", "high",
        steps="1. Добавить товар со скидкой\n2. Открыть корзину",
        expected="Сумма с учётом скидки",
        actual="Сумма без скидки",
    )
    move(cart, bob, "in_progress")
    add_comment(cart, bob, "Нашёл: скидка не применяется к товарам из акции. Исправляю.")

    # fixed
    typo = new_bug(
        project, ana, "Опечатка на странице доставки", "trivial", "low",
        actual="«Доставка осуществляеться»",
    )
    move(typo, bob, "in_progress")
    move(typo, bob, "fixed")
    add_comment(typo, bob, "Исправил текст, проверьте, пожалуйста.")

    # closed — с возвратом на доработку
    email = new_bug(
        project, ana, "Не приходит письмо о заказе", "critical", "high",
        steps="1. Оформить заказ\n2. Проверить почту",
        expected="Письмо с номером заказа",
        actual="Письма нет",
    )
    move(email, bob, "in_progress")
    move(email, bob, "fixed")
    add_comment(email, ana, "Письмо приходит, но без номера заказа. Возвращаю.")
    move(email, ana, "in_progress")
    move(email, bob, "fixed")
    add_comment(email, bob, "Добавил номер заказа в шаблон письма.")
    move(email, ana, "closed")

    # rejected — причина в комментарии
    price = new_bug(
        project, ana, "Фильтр по цене показывает товары дороже заданной", "minor", "medium",
        expected="Только товары до указанной цены",
        actual="Есть товары дороже на 1–2 рубля",
    )
    move(
        price, bob, "rejected",
        "Так задумано: фильтр сравнивает цену без копеек, это требование заказчика.",
    )


def seed():
    """Создать демо-аккаунты, демо-проект и баги. Повторно ничего не дублирует.

    Всё одной транзакцией: при ошибке в базе не останется «половины» демо-данных.
    Возвращает список строк для вывода.
    """
    # Сначала проверяем логины — до любых изменений
    for account in DEMO_ACCOUNTS:
        user = find_user(account["username"])
        if user is not None and not is_demo_account(user):
            raise DemoError(
                f"Логин «{account['username']}» занят пользователем, который не является "
                "демо-аккаунтом. Демо-данные не созданы."
            )

    report = []
    users = {}
    for account in DEMO_ACCOUNTS:
        user = find_user(account["username"])
        if user is None:
            user = create_account(account)
            report.append(f"Создан демо-аккаунт {account['username']} ({account['role']}).")
        else:
            report.append(f"Демо-аккаунт {account['username']} уже есть.")
        users[account["username"]] = user
    db.session.flush()

    if find_demo_project() is None:
        project = Project(
            name=DEMO_PROJECT,
            description="Демонстрационный проект: баги во всех статусах.",
            creator=users["pixel"],
        )
        db.session.add(project)
        for username in DEMO_MEMBERS:
            project.members.append(users[username])
        db.session.flush()
        create_demo_bugs(project, users["ana"], users["bob"])
        report.append(f"Создан проект «{DEMO_PROJECT}» с 5 багами.")
    else:
        report.append(f"Проект «{DEMO_PROJECT}» уже есть — баги не создаются.")

    db.session.commit()
    return report


# --- flask seed --restore-demo ----------------------------------------------------

def restore_demo_accounts():
    """Вернуть демо-аккаунтам рабочее состояние. Чужие данные не трогаем.

    Для каждого демо-аккаунта: разблокировать, вернуть роль и пароль;
    ana и bob — вернуть в демо-проект. Возвращает список строк для вывода.
    """
    report = []
    users = {}
    for account in DEMO_ACCOUNTS:
        username = account["username"]
        user = find_user(username)
        if user is None:
            user = create_account(account)
            report.append(f"{username}: аккаунта не было — создан.")
        elif not is_demo_account(user):
            report.append(
                f"{username}: ПРОПУЩЕН — это не демо-аккаунт (почта не {demo_email(username)})."
            )
            continue
        else:
            report.append(f"{username}: восстановлен.")
        users[username] = user
    db.session.flush()

    # Кто выполняет системные действия — демо-админ (updated_by обязателен)
    actor = users.get("pixel")
    for account in DEMO_ACCOUNTS:
        user = users.get(account["username"])
        if user is None:
            continue
        if user.role.name == "developer" and account["role"] != "developer" and actor:
            # Правило смены роли: исполнителем может быть только developer
            bugs = unassign_user_bugs(user, actor)
            if bugs:
                numbers = ", ".join(f"#{bug.id}" for bug in bugs)
                report.append(f"{user.username}: снято назначение с багов {numbers}.")
        user.role = find_role(account["role"])
        user.set_password(account["password"])
        user.is_active = True
        if user.approved_at is None:
            user.approved_at = sa.func.now()

    project = find_demo_project()
    if project is None:
        report.append(f"Проект «{DEMO_PROJECT}» не найден — участники не восстановлены.")
    else:
        for username in DEMO_MEMBERS:
            user = users.get(username)
            if user is not None and user not in project.members:
                project.members.append(user)
                report.append(f"{username}: возвращён в проект «{DEMO_PROJECT}».")

    db.session.commit()
    return report
