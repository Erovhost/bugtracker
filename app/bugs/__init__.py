from flask import Blueprint

bp = Blueprint("bugs", __name__)

# Импорт внизу, потому что routes.py сам импортирует bp из этого файла
from app.bugs import routes  # noqa: E402, F401
