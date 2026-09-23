import sqlalchemy as sa
from flask import render_template
from flask_login import login_required

from app import db
from app.admin import bp
from app.decorators import role_required
from app.models import User


@bp.route("/")
@login_required
@role_required("admin")
def index():
    # Сначала неактивные (новые заявки видны сразу), затем по логину.
    # В PostgreSQL false < true, поэтому is_active по возрастанию.
    users = db.session.scalars(
        sa.select(User).order_by(User.is_active, User.username)
    ).all()
    return render_template("admin/index.html", users=users)
