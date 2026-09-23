import sqlalchemy as sa
from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.access import can_edit_bug, get_bug_or_403, get_project_or_403
from app.bugs import bp
from app.bugs.forms import BugForm
from app.decorators import role_required
from app.models import PRIORITY_LABELS, SEVERITY_LABELS, STATUS_LABELS, Bug, Project


# Словари подписей доступны во всех шаблонах приложения
@bp.app_context_processor
def inject_labels():
    return {
        "SEVERITY_LABELS": SEVERITY_LABELS,
        "PRIORITY_LABELS": PRIORITY_LABELS,
        "STATUS_LABELS": STATUS_LABELS,
    }


@bp.route("/")
@login_required
def index():
    # Админ видит все баги, остальные — баги своих проектов. Новые сверху.
    query = sa.select(Bug).order_by(Bug.id.desc())
    if not current_user.has_role("admin"):
        query = query.join(Bug.project).where(Project.members.contains(current_user))
    bugs = db.session.scalars(query).all()
    return render_template("bugs/index.html", bugs=bugs)


@bp.route("/project/<int:project_id>/new", methods=["GET", "POST"])
@login_required
@role_required("tester")
def create(project_id):
    # Баг заводит только тестировщик — участник проекта
    project = get_project_or_403(project_id)
    form = BugForm()
    if form.validate_on_submit():
        bug = Bug(
            project=project,
            title=form.title.data,
            # Пустые необязательные поля храним как NULL
            steps=form.steps.data or None,
            expected=form.expected.data or None,
            actual=form.actual.data or None,
            environment=form.environment.data or None,
            severity=form.severity.data,
            priority=form.priority.data,
            reporter=current_user,
            # По правилу схемы: при создании updated_by = автор
            updater=current_user,
        )
        db.session.add(bug)
        db.session.commit()
        flash(f"Баг #{bug.id} создан.", "success")
        return redirect(url_for("bugs.detail", bug_id=bug.id))

    return render_template("bugs/create.html", form=form, project=project)


@bp.route("/<int:bug_id>")
@login_required
def detail(bug_id):
    bug = get_bug_or_403(bug_id)
    return render_template(
        "bugs/detail.html", bug=bug, can_edit=can_edit_bug(current_user, bug)
    )


@bp.route("/<int:bug_id>/edit", methods=["GET", "POST"])
@login_required
def edit(bug_id):
    bug = get_bug_or_403(bug_id)
    if not can_edit_bug(current_user, bug):
        abort(403)

    form = BugForm(obj=bug)
    if form.validate_on_submit():
        # Переписываем только поля формы. Статуса в форме нет:
        # он меняется только кнопками переходов жизненного цикла.
        bug.title = form.title.data
        bug.steps = form.steps.data or None
        bug.expected = form.expected.data or None
        bug.actual = form.actual.data or None
        bug.environment = form.environment.data or None
        bug.severity = form.severity.data
        bug.priority = form.priority.data
        bug.updater = current_user
        db.session.commit()
        flash("Изменения сохранены.", "success")
        return redirect(url_for("bugs.detail", bug_id=bug.id))

    return render_template("bugs/edit.html", form=form, bug=bug)
