from flask import Blueprint

bp = Blueprint("auth", __name__)

# Импорт внизу, потому что routes.py сам импортирует bp из этого файла
from app.auth import routes  # noqa: E402, F401
