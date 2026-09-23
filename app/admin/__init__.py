from flask import Blueprint

bp = Blueprint("admin", __name__)

# Импорт внизу, потому что routes.py сам импортирует bp из этого файла
from app.admin import routes  # noqa: E402, F401
