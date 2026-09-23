import os

from dotenv import load_dotenv

# Папка, в которой лежит этот файл (корень проекта)
basedir = os.path.abspath(os.path.dirname(__file__))

# Загружаем переменные из .env в переменные окружения.
# Уже заданные переменные окружения главнее .env (так работает хостинг).
load_dotenv(os.path.join(basedir, ".env"))


def database_url(url):
    """Строка подключения с драйвером psycopg.

    Хостинги (Render и др.) выдают адрес вида postgresql://... или postgres://...,
    а SQLAlchemy без явного драйвера искал бы psycopg2. Меняем начало адреса
    на postgresql+psycopg://, остальное не трогаем.
    """
    if not url:
        return url
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = database_url(os.environ.get("DATABASE_URL"))
    # Папка журнала (logs/ в .gitignore)
    LOG_DIR = os.path.join(basedir, "logs")
    # На хостинге (Render) файлы стираются при перезапуске — журнал в консоль
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT") == "1"


class TestConfig(Config):
    # Настройки для pytest: отдельная база, которую тесты очищают.
    # CSRF не отключаем — тесты проверяют и его.
    TESTING = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "test-secret-key"
    SQLALCHEMY_DATABASE_URI = database_url(os.environ.get("TEST_DATABASE_URL"))
