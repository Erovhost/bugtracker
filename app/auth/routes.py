import sqlalchemy as sa
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm
from app.models import Role, User


def is_safe_next(url):
    # Разрешаем переход только на страницы нашего сайта: адрес вида "/bugs/".
    # "//evil.com" и "/\evil.com" браузер понимает как чужой сайт — запрещаем.
    if not url:
        return False
    return url.startswith("/") and not url.startswith("//") and "\\" not in url


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("projects.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )
        if user is None or not user.check_password(form.password.data):
            # Пароль в журнал не пишем никогда — только введённый логин
            current_app.logger.warning(
                "Неудачный вход: логин «%s», IP %s",
                form.username.data, request.remote_addr,
            )
            flash("Неверный логин или пароль.", "error")
            return render_template("auth/login.html", form=form)
        # О статусе аккаунта говорим только тому, кто знает пароль
        if user.status != "active":
            current_app.logger.warning(
                "Попытка входа неактивного пользователя «%s» (%s), IP %s",
                user.username, user.status, request.remote_addr,
            )
        if user.status == "pending":
            flash("Аккаунт ещё не одобрен администратором.", "error")
            return render_template("auth/login.html", form=form)
        if user.status == "blocked":
            flash("Аккаунт заблокирован. Обратитесь к администратору.", "error")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        current_app.logger.info(
            "Вход: «%s» (%s), IP %s", user.username, user.role.name, request.remote_addr
        )
        next_page = request.args.get("next")
        if not is_safe_next(next_page):
            next_page = url_for("projects.index")
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("projects.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Заявка: approved_at = NULL и is_active = false, пока админ её не одобрит
        # и не назначит роль. role_id обязателен, поэтому временная роль tester.
        tester = db.session.scalar(sa.select(Role).where(Role.name == "tester"))
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=tester,
            is_active=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(
            "Новая заявка на регистрацию: «%s», IP %s", user.username, request.remote_addr
        )
        flash(
            "Заявка на регистрацию отправлена. Войти можно будет "
            "после одобрения администратором.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


# Только POST: выход меняет состояние, а GET-ссылку может «нажать» чужой сайт.
# CSRF-токен проверяет CSRFProtect.
@bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        current_app.logger.info("Выход: «%s»", current_user.username)
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
