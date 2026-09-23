from flask import Flask

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Подключаем модули (blueprints)
    from app.projects import bp as projects_bp
    app.register_blueprint(projects_bp)

    return app
