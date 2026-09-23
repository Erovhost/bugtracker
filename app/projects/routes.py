import sqlalchemy as sa
from flask import render_template
from flask_login import current_user, login_required

from app import db
from app.models import Project
from app.projects import bp


@bp.route("/")
@login_required
def index():
    # Админ видит все проекты, остальные — только те, где они участники
    query = sa.select(Project).order_by(Project.name)
    if not current_user.has_role("admin"):
        query = query.where(Project.members.contains(current_user))
    projects = db.session.scalars(query).all()
    return render_template("projects/index.html", projects=projects)
