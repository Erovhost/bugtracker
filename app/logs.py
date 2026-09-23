"""Журнал приложения в файл logs/bugtracker.log с ротацией."""

import logging
import os
from logging.handlers import RotatingFileHandler

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
