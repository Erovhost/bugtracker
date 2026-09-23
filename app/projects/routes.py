import sqlalchemy as sa
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.access import get_project_or_403
from app.decorators import role_required
from app.models import Project
from app.projects import bp
from app.projects.forms import ProjectForm


@bp.route("/")
@login_required
def index():
    # Админ видит все проекты, остальные — только те, где они участники
    query = sa.select(Project).order_by(Project.name)
    if not current_user.has_role("admin"):
        query = query.where(Project.members.contains(current_user))
    projects = db.session.scalars(query).all()
    return render_template("projects/index.html", projects=projects)


@bp.route("/project/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            # Пустое описание храним как NULL, а не как пустую строку
            description=form.description.data or None,
            creator=current_user,
        )
        db.session.add(project)
        db.session.commit()
        flash(f"Проект «{project.name}» создан.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/create.html", form=form)


@bp.route("/project/<int:project_id>")
@login_required
def detail(project_id):
    project = get_project_or_403(project_id)
    return render_template("projects/detail.html", project=project)
