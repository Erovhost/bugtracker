import os

from dotenv import load_dotenv

# Папка, в которой лежит этот файл (корень проекта)
basedir = os.path.abspath(os.path.dirname(__file__))

# Загружаем переменные из .env в переменные окружения
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


class TestConfig(Config):
    # Настройки для pytest: отдельная база, которую тесты очищают.
    # CSRF не отключаем — тесты проверяют и его.
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL")
