from flask import render_template

from app.bugs import bp


@bp.route("/")
def index():
    return render_template("bugs/index.html")
