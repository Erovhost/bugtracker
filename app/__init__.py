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

    # Консольные команды: flask create-admin, flask seed-demo
    from app.cli import create_admin, seed_demo
    app.cli.add_command(create_admin)
    app.cli.add_command(seed_demo)

    # Страницы ошибок 400/403/404/500
    from app.errors import register_error_handlers
    register_error_handlers(app)

    # Журнал в файл logs/bugtracker.log (в тестах не пишем)
    if not app.testing:
        from app.logs import setup_file_logging
        setup_file_logging(app, app.config["LOG_DIR"])
        app.logger.info("Баг-трекер запущен")

    return app


# Импорт внизу: models.py сам импортирует db из этого файла
from app import models  # noqa: E402, F401
