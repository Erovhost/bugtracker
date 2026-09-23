from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

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
