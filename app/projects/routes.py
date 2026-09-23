from app.projects import bp


@bp.route("/")
def index():
    return "Проекты: страница в разработке"
