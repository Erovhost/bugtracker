from flask import Blueprint

bp = Blueprint("projects", __name__)

# Импорт внизу, потому что routes.py сам импортирует bp из этого файла
from app.projects import routes  # noqa: E402, F401
