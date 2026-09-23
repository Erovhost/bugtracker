import sqlalchemy as sa
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.access import get_project_or_403
from app.decorators import role_required
from app.models import Bug, Project, Role, User
from app.projects import bp
from app.projects.forms import AddMemberForm, ProjectForm


def member_choices(project):
    """Кого можно добавить в проект: активные tester и developer, ещё не участники."""
    query = (
        sa.select(User)
        .join(User.role)
        .where(User.is_active, Role.name.in_(["tester", "developer"]))
        .order_by(User.username)
    )
    choices = []
    for user in db.session.scalars(query):
        if user not in project.members:
            choices.append((user.id, f"{user.username} ({user.role.name})"))
    return choices


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
    bugs = db.session.scalars(
        sa.select(Bug).where(Bug.project_id == project.id).order_by(Bug.id.desc())
    ).all()
    add_form = None
    if current_user.has_role("admin"):
        add_form = AddMemberForm()
        add_form.user_id.choices = member_choices(project)
    return render_template(
        "projects/detail.html", project=project, bugs=bugs, add_form=add_form
    )


@bp.route("/project/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit(project_id):
    project = db.get_or_404(Project, project_id)
    # obj=project: при открытии страницы поля заполняются текущими значениями
    form = ProjectForm(original_name=project.name, obj=project)
    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data or None
        db.session.commit()
        flash("Изменения сохранены.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/edit.html", form=form, project=project)


@bp.route("/project/<int:project_id>/members/add", methods=["POST"])
@login_required
@role_required("admin")
def add_member(project_id):
    project = db.get_or_404(Project, project_id)
    form = AddMemberForm()
    form.user_id.choices = member_choices(project)
    if form.validate_on_submit():
        user = db.session.get(User, form.user_id.data)
        project.members.append(user)
        db.session.commit()
        flash(f"{user.username} добавлен в проект.", "success")
    else:
        flash("Не удалось добавить: выберите пользователя из списка.", "error")
    return redirect(url_for("projects.detail", project_id=project.id))


@bp.route("/project/<int:project_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
@role_required("admin")
def remove_member(project_id, user_id):
    # CSRF-токен проверяет CSRFProtect
    project = db.get_or_404(Project, project_id)
    user = db.get_or_404(User, user_id)
    if user in project.members:
        project.members.remove(user)
        db.session.commit()
        flash(f"{user.username} убран из проекта.", "info")
    return redirect(url_for("projects.detail", project_id=project.id))
