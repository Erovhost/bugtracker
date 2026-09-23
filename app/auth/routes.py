from app.auth import bp


@bp.route("/login")
def login():
    return "Вход: страница в разработке"
