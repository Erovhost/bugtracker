import sqlalchemy as sa
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.access import can_edit_bug, get_bug_or_403, get_project_or_403
from app.assignments import assignee_candidates, can_be_assignee, unassign
from app.bugs import bp
from app.bugs.forms import AssignForm, BugForm
from app.decorators import role_required
from app.models import PRIORITY_LABELS, SEVERITY_LABELS, STATUS_LABELS, Bug, Project, User
from app.workflow import apply_transition, available_transitions, check_transition


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


def make_assign_form(bug):
    """Форма выбора исполнителя с вариантами для проекта этого бага."""
    form = AssignForm()
    form.assignee_id.choices = [("", "— не назначен —")] + [
        (str(user.id), user.username) for user in assignee_candidates(bug.project)
    ]
    return form


@bp.route("/<int:bug_id>")
@login_required
def detail(bug_id):
    bug = get_bug_or_403(bug_id)
    can_edit = can_edit_bug(current_user, bug)
    assign_form = None
    # Выбирать исполнителя могут те же, кто редактирует: автор и admin
    if can_edit:
        assign_form = make_assign_form(bug)
        assign_form.assignee_id.data = str(bug.assignee_id) if bug.assignee_id else ""
    return render_template(
        "bugs/detail.html",
        bug=bug,
        can_edit=can_edit,
        assign_form=assign_form,
        transitions=available_transitions(current_user, bug),
    )


@bp.route("/<int:bug_id>/status", methods=["POST"])
@login_required
def change_status(bug_id):
    # CSRF-токен проверяет CSRFProtect; правила перехода — app/workflow.py
    bug = get_bug_or_403(bug_id)
    new_status = request.form.get("new_status", "")
    comment = request.form.get("comment")

    error = check_transition(current_user, bug, new_status, comment)
    if error is not None:
        flash(error, "error")
        return redirect(url_for("bugs.detail", bug_id=bug.id))

    # Смена статуса, комментарий и запись триггера в историю — одна транзакция
    result = apply_transition(current_user, bug, new_status, comment)
    db.session.commit()
    flash(f"Статус изменён: «{STATUS_LABELS[result]}».", "success")
    return redirect(url_for("bugs.detail", bug_id=bug.id))


@bp.route("/<int:bug_id>/assign", methods=["POST"])
@login_required
def assign(bug_id):
    # admin и автор: назначить любого подходящего developer'а или снять назначение
    bug = get_bug_or_403(bug_id)
    if not can_edit_bug(current_user, bug):
        abort(403)
    form = make_assign_form(bug)
    if not form.validate_on_submit():
        flash("Выберите исполнителя из списка.", "error")
    elif form.assignee_id.data == "":
        if bug.assignee is not None:
            unassign(bug, current_user)
            db.session.commit()
            flash("Назначение снято.", "info")
    else:
        user = db.session.get(User, int(form.assignee_id.data))
        bug.assignee = user
        bug.updater = current_user
        db.session.commit()
        flash(f"Исполнитель: {user.username}.", "success")
    return redirect(url_for("bugs.detail", bug_id=bug.id))


@bp.route("/<int:bug_id>/take", methods=["POST"])
@login_required
@role_required("developer")
def take(bug_id):
    # developer назначает себя, только если баг свободен
    bug = get_bug_or_403(bug_id)
    if bug.assignee is not None:
        flash("У бага уже есть исполнитель.", "error")
    elif not can_be_assignee(current_user, bug.project):
        abort(403)
    else:
        bug.assignee = current_user
        bug.updater = current_user
        db.session.commit()
        flash("Баг назначен на вас.", "success")
    return redirect(url_for("bugs.detail", bug_id=bug.id))


@bp.route("/<int:bug_id>/release", methods=["POST"])
@login_required
@role_required("developer")
def release(bug_id):
    # developer снимает назначение только с себя
    bug = get_bug_or_403(bug_id)
    if bug.assignee_id != current_user.id:
        abort(403)
    unassign(bug, current_user)
    db.session.commit()
    flash("Вы отказались от бага.", "info")
    return redirect(url_for("bugs.detail", bug_id=bug.id))


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
