from flask import render_template
from flask_login import login_required

from app.admin import bp
from app.decorators import role_required


@bp.route("/")
@login_required
@role_required("admin")
def index():
    return render_template("admin/index.html")
