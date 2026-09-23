import sqlalchemy as sa
import sqlalchemy.orm as so

from app import create_app, db
from app.models import Project, Role, User

app = create_app()


# Что будет доступно в flask shell без импортов
@app.shell_context_processor
def make_shell_context():
    return {
        "sa": sa,
        "so": so,
        "db": db,
        "Role": Role,
        "User": User,
        "Project": Project,
    }
