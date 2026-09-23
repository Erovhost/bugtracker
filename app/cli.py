import click
import sqlalchemy as sa
from flask.cli import with_appcontext

from app import db
from app.models import Role, User


@click.command("create-admin")
@click.option("--username", prompt="Логин")
@click.option("--email", prompt="Почта")
# Пароль только через скрытый ввод: в истории команд PowerShell его не будет
@click.password_option("--password", prompt="Пароль", confirmation_prompt="Повторите пароль")
@with_appcontext
def create_admin(username, email, password):
    """Создать активного пользователя с ролью admin."""
    if len(password) < 8:
        raise click.ClickException("Пароль должен быть не короче 8 символов.")
    if db.session.scalar(sa.select(User).where(User.username == username)):
        raise click.ClickException(f"Логин {username} уже занят.")
    if db.session.scalar(sa.select(User).where(User.email == email)):
        raise click.ClickException(f"Почта {email} уже зарегистрирована.")

    admin_role = db.session.scalar(sa.select(Role).where(Role.name == "admin"))
    if admin_role is None:
        raise click.ClickException("Роли admin нет в базе. Выполните: flask db upgrade")

    # Созданный командой админ сразу одобрен (время ставит сама база)
    user = User(
        username=username,
        email=email,
        role=admin_role,
        is_active=True,
        approved_at=sa.func.now(),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Администратор {username} создан.")


@click.command("seed-demo")
@click.option("--yes", is_flag=True, help="Не спрашивать подтверждение.")
@with_appcontext
def seed_demo(yes):
    """Заполнить базу демо-данными (аккаунты под каждую роль)."""
    # Импорт здесь: демо-данные нужны только этой команде
    from app.demo import DEMO_PASSWORD, DEMO_USERS, create_demo_data, demo_data_exists

    if demo_data_exists():
        raise click.ClickException("Демо-данные уже есть (пользователь demo_admin).")
    if not yes:
        click.echo(
            f"У всех демо-аккаунтов общий известный пароль «{DEMO_PASSWORD}». "
            "Не запускайте эту команду на сервере с настоящими пользователями."
        )
        click.confirm("Создать демо-данные?", abort=True)

    counts = create_demo_data()
    click.echo(
        f"Создано: пользователей {counts['users']}, проектов {counts['projects']}, "
        f"багов {counts['bugs']}."
    )
    click.echo(f"Демо-аккаунты (пароль {DEMO_PASSWORD}):")
    for username, role_name, status in DEMO_USERS:
        note = ""
        if status == "pending":
            note = " — заявка, войти нельзя до одобрения"
        if username == "blocked_dev":
            note = " — заблокирован"
        click.echo(f"  {username:12} {role_name}{note}")
