import sqlalchemy as sa
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.admin import bp
from app.admin.forms import ApproveForm, CreateUserForm, RoleForm
from app.assignments import unassign_user_bugs
from app.decorators import role_required
from app.models import USER_STATUS_LABELS, Role, User


def back_to_list():
    return redirect(url_for("admin.index"))


@bp.route("/")
@login_required
@role_required("admin")
def index():
    # Порядок: заявки (approved_at IS NULL) -> заблокированные -> активные,
    # внутри — по логину. В PostgreSQL false < true.
    users = db.session.scalars(
        sa.select(User).order_by(
            User.approved_at.is_not(None), User.is_active, User.username
        )
    ).all()
    # У каждого пользователя своя форма смены роли с его текущей ролью.
    # formdata=None — не брать данные из запроса, только из data.
    role_forms = {}
    for user in users:
        role_forms[user.id] = RoleForm(formdata=None, data={"role": user.role.name})
    return render_template(
        "admin/index.html",
        users=users,
        USER_STATUS_LABELS=USER_STATUS_LABELS,
        approve_form=ApproveForm(),
        role_forms=role_forms,
    )


@bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve(user_id):
    user = db.get_or_404(User, user_id)
    if user.status != "pending":
        flash(f"{user.username} не ожидает одобрения.", "error")
        return back_to_list()
    form = ApproveForm()
    if not form.validate_on_submit():
        flash("Выберите роль из списка.", "error")
        return back_to_list()

    user.role = db.session.scalar(sa.select(Role).where(Role.name == form.role.data))
    # Время одобрения ставит сама база
    user.approved_at = sa.func.now()
    user.is_active = True
    db.session.commit()
    flash(f"{user.username} одобрен с ролью {user.role.name}.", "success")
    return back_to_list()


@bp.route("/users/<int:user_id>/block", methods=["POST"])
@login_required
@role_required("admin")
def block(user_id):
    # CSRF-токен проверяет CSRFProtect
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Нельзя заблокировать самого себя.", "error")
        return back_to_list()
    if user.status != "active":
        flash(f"{user.username} сейчас не активен.", "error")
        return back_to_list()

    user.is_active = False
    # Заблокированный не может быть исполнителем: снимаем с открытых багов
    # во всех проектах (closed и rejected не трогаем — правило из ТЗ)
    bugs = unassign_user_bugs(user, current_user)
    db.session.commit()
    message = f"{user.username} заблокирован."
    if bugs:
        numbers = ", ".join(f"#{bug.id}" for bug in bugs)
        message += f" Снято назначение с багов: {numbers}."
    flash(message, "info")
    return back_to_list()


@bp.route("/users/<int:user_id>/unblock", methods=["POST"])
@login_required
@role_required("admin")
def unblock(user_id):
    user = db.get_or_404(User, user_id)
    if user.status != "blocked":
        flash(f"{user.username} не заблокирован.", "error")
        return back_to_list()
    user.is_active = True
    db.session.commit()
    flash(f"{user.username} разблокирован.", "success")
    return back_to_list()


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@role_required("admin")
def change_role(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Нельзя сменить роль самому себе.", "error")
        return back_to_list()
    if user.status == "pending":
        flash(
            f"{user.username} ещё не одобрен — роль выбирается при одобрении.",
            "error",
        )
        return back_to_list()
    form = RoleForm()
    if not form.validate_on_submit():
        flash("Выберите роль из списка.", "error")
        return back_to_list()
    if form.role.data == user.role.name:
        flash(f"Роль {user.username} не изменилась.", "info")
        return back_to_list()

    old_role = user.role.name
    user.role = db.session.scalar(sa.select(Role).where(Role.name == form.role.data))
    message = f"{user.username}: роль {old_role} → {user.role.name}."
    # Исполнителем может быть только developer: при уходе с этой роли
    # снимаем назначения по тому же правилу, что при блокировке
    if old_role == "developer":
        bugs = unassign_user_bugs(user, current_user)
        if bugs:
            numbers = ", ".join(f"#{bug.id}" for bug in bugs)
            message += f" Снято назначение с багов: {numbers}."
    db.session.commit()
    flash(message, "success")
    return back_to_list()


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        role = db.session.scalar(sa.select(Role).where(Role.name == form.role.data))
        # Созданный админом пользователь сразу одобрен и активен
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=role,
            is_active=True,
            approved_at=sa.func.now(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"Пользователь {user.username} создан с ролью {role.name}.", "success")
        return back_to_list()

    return render_template("admin/create_user.html", form=form)
