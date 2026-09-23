import sqlalchemy as sa
from flask import render_template
from flask_login import login_required

from app import db
from app.admin import bp
from app.decorators import role_required
from app.models import USER_STATUS_LABELS, User


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
    return render_template(
        "admin/index.html", users=users, USER_STATUS_LABELS=USER_STATUS_LABELS
    )
