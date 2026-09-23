import click
import sqlalchemy as sa
from flask import current_app
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


@click.command("seed")
@click.option(
    "--restore-demo",
    is_flag=True,
    help="Только восстановить демо-аккаунты (роли, пароли, разблокировка, участие в проекте).",
)
@with_appcontext
def seed(restore_demo):
    """Создать демо-данные (повторный запуск ничего не дублирует)."""
    # Импорт здесь: демо-данные нужны только этой команде
    from app.demo import DEMO_ACCOUNTS, DemoError, restore_demo_accounts
    from app.demo import seed as create_demo_data

    try:
        if restore_demo:
            report = restore_demo_accounts()
        else:
            report = create_demo_data()
    except DemoError as error:
        raise click.ClickException(str(error)) from error

    for line in report:
        click.echo(line)
    current_app.logger.info(
        "Команда flask seed%s выполнена", " --restore-demo" if restore_demo else ""
    )
    click.echo("Демо-аккаунты (пароли известны всем — не храните на сайте настоящих данных):")
    for account in DEMO_ACCOUNTS:
        click.echo(f"  {account['username']:6} {account['role']:10} пароль {account['password']}")
