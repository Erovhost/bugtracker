from app.admin import bp


@bp.route("/")
def index():
    return "Администрирование: страница в разработке"
