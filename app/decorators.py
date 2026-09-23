from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*role_names):
    """Пускает на страницу только пользователей с одной из указанных ролей.

    Использование (ставится под @login_required):
        @bp.route("/")
        @login_required
        @role_required("admin")
        def index(): ...
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.has_role(*role_names):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
