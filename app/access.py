from flask import abort
from flask_login import current_user

from app import db
from app.models import Project


def can_view_project(user, project):
    # Проект (и его баги) видят только участники и админ
    return user.has_role("admin") or user in project.members


def get_project_or_403(project_id):
    """Загрузить проект для текущего пользователя.

    Нет проекта — 404, нет доступа — 403.
    """
    project = db.get_or_404(Project, project_id)
    if not can_view_project(current_user, project):
        abort(403)
    return project
