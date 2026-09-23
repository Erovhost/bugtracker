"""Журнал приложения в файл logs/bugtracker.log с ротацией."""

import logging
import os
from logging.handlers import RotatingFileHandler

import click
from werkzeug.serving import is_running_from_reloader

LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"


def setup_file_logging(app, log_dir):
    """Писать журнал app.logger в файл log_dir/bugtracker.log.

    Ротация: файл до 1 МБ, потом он становится bugtracker.log.1 и т.д.,
    хранится 10 старых файлов — журнал не займёт весь диск.
    """
    os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(log_dir, "bugtracker.log"),
        maxBytes=1_000_000,
        backupCount=10,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    return handler


def is_server_start(app):
    """Запускается ли веб-сервер (а не другая команда flask).

    flask run — команда click с именем "run". Другие команды (flask routes,
    flask db upgrade, flask seed-demo) — не запуск сервера. Если команды
    click нет вовсе, приложение запустил веб-сервер вроде gunicorn.

    С перезагрузчиком (режим отладки) flask run создаёт два процесса:
    наблюдатель и сам сервер. Сервер — дочерний процесс, его Werkzeug
    помечает (is_running_from_reloader); пишем только из него.
    """
    context = click.get_current_context(silent=True)
    if context is None:
        return True
    if context.info_name != "run":
        return False
    reload = context.params.get("reload")
    if reload is None:
        # Как во Flask: без явного --reload/--no-reload решает режим отладки
        reload = app.debug
    if reload:
        return is_running_from_reloader()
    return True
