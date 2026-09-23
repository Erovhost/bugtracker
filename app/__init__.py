from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

# Объекты создаются здесь, а к приложению привязываются в create_app()
db = SQLAlchemy()
migrate = Migrate()
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

    return app


# Импорт внизу: models.py сам импортирует db из этого файла
from app import models  # noqa: E402, F401
