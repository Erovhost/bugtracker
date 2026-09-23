from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.access import get_project_or_403
from app.bugs import bp
from app.bugs.forms import BugForm
from app.decorators import role_required
from app.models import PRIORITY_LABELS, SEVERITY_LABELS, STATUS_LABELS, Bug


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
    return render_template("bugs/index.html")


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
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("bugs/create.html", form=form, project=project)
