from flask import render_template

from app.projects import bp


@bp.route("/")
def index():
    return render_template("projects/index.html")
