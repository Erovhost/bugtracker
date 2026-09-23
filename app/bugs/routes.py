from app.bugs import bp


@bp.route("/")
def index():
    return "Баги: страница в разработке"
