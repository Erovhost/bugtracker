"""Страницы ошибок 400/403/404/500 в оформлении сайта."""

from flask import render_template
from flask_wtf.csrf import CSRFError

from app import db


def csrf_error(error):
    # Устаревший или чужой CSRF-токен: форма долго была открыта, сессия сменилась
    return render_template("errors/400.html"), 400


def forbidden(error):
    return render_template("errors/403.html"), 403


def not_found(error):
    return render_template("errors/404.html"), 404


def internal_error(error):
    # Ошибка могла случиться посреди работы с базой: откатываем транзакцию,
    # иначе сессия останется «сломанной» и упадёт и эта страница
    db.session.rollback()
    return render_template("errors/500.html"), 500


def register_error_handlers(app):
    app.register_error_handler(CSRFError, csrf_error)
    app.register_error_handler(403, forbidden)
    app.register_error_handler(404, not_found)
    app.register_error_handler(500, internal_error)
