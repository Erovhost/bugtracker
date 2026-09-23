import sqlalchemy as sa
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app import db
from app.auth import bp
from app.auth.forms import LoginForm
from app.models import User


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
            flash("Неверный логин или пароль.", "error")
            return render_template("auth/login.html", form=form)
        # О блокировке говорим только тому, кто знает пароль
        if not user.is_active:
            flash("Аккаунт заблокирован или ещё не одобрен администратором.", "error")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not is_safe_next(next_page):
            next_page = url_for("projects.index")
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


# Только POST: выход меняет состояние, а GET-ссылку может «нажать» чужой сайт.
# CSRF-токен проверяет CSRFProtect.
@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
