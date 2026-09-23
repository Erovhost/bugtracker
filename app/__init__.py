from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config

# Объекты создаются здесь, а к приложению привязываются в create_app()
db = SQLAlchemy()
migrate = Migrate()
# CSRF-защита для всех POST-запросов приложения, даже без класса формы
csrf = CSRFProtect()
login = LoginManager()
# Куда отправлять гостя, который открыл закрытую страницу
login.login_view = "auth.login"
login.login_message = "Войдите, чтобы открыть эту страницу."
login.login_message_category = "info"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Без ключа сессии и CSRF-защита небезопасны — не запускаемся
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "Не задан SECRET_KEY. Локально — в файле .env, на сервере — "
            "в переменных окружения хостинга."
        )

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login.init_app(app)

    # Подключаем модули (blueprints)
    from app.projects import bp as projects_bp
    app.register_blueprint(projects_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.bugs import bp as bugs_bp
    app.register_blueprint(bugs_bp, url_prefix="/bugs")

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Консольные команды: flask create-admin, flask seed
    from app.cli import create_admin, seed
    app.cli.add_command(create_admin)
    app.cli.add_command(seed)

    # Страницы ошибок 400/403/404/500
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # Журнал: в файл logs/bugtracker.log или (на хостинге) в консоль.
    # В тестах не пишем.
    if not app.testing:
        from app.logs import is_server_start, setup_file_logging, setup_stdout_logging
        if app.config["LOG_TO_STDOUT"]:
            setup_stdout_logging(app)
        else:
            setup_file_logging(app, app.config["LOG_DIR"])
        if is_server_start(app):
            app.logger.info("Баг-трекер запущен")

    return app


# Импорт внизу: models.py сам импортирует db из этого файла
from app import models  # noqa: E402, F401
