"""Чтение статистики из представлений (VIEW) PostgreSQL.

Представления создаёт миграция «statistics views». Здесь они описаны
через sa.table — только для чтения, моделей-классов для них нет.
"""

import sqlalchemy as sa

from app import db
from app.models import Project

bug_stats = sa.table(
    "v_bug_stats",
    sa.column("project_id"),
    sa.column("project_name"),
    sa.column("total"),
    sa.column("status_new"),
    sa.column("status_in_progress"),
    sa.column("status_fixed"),
    sa.column("status_rejected"),
    sa.column("status_closed"),
)

open_by_assignee = sa.table(
    "v_open_bugs_by_assignee",
    sa.column("project_id"),
    sa.column("assignee_id"),
    sa.column("assignee_username"),
    sa.column("assignee_is_active"),
    sa.column("open_total"),
    sa.column("status_new"),
    sa.column("status_in_progress"),
    sa.column("status_fixed"),
)


def visible_project_ids(user):
    """Подзапрос: id проектов, которые видит пользователь (None — все)."""
    if user.has_role("admin"):
        return None
    return sa.select(Project.id).where(Project.members.contains(user))


def project_stats(user):
    """Строки v_bug_stats по видимым проектам, по названию проекта."""
    query = sa.select(bug_stats).order_by(bug_stats.c.project_name)
    project_ids = visible_project_ids(user)
    if project_ids is not None:
        query = query.where(bug_stats.c.project_id.in_(project_ids))
    return db.session.execute(query).mappings().all()


def open_bugs_by_assignee(user):
    """Строки v_open_bugs_by_assignee по видимым проектам.

    Внутри проекта: сначала «не назначен», потом по логину.
    """
    query = sa.select(open_by_assignee).order_by(
        open_by_assignee.c.project_id,
        open_by_assignee.c.assignee_username.nulls_first(),
    )
    project_ids = visible_project_ids(user)
    if project_ids is not None:
        query = query.where(open_by_assignee.c.project_id.in_(project_ids))
    return db.session.execute(query).mappings().all()
