"""Назначение исполнителей багов: общие правила в одном месте."""

import sqlalchemy as sa

from app import db
from app.models import Bug, Role, User, project_members

# У закрытых и отклонённых багов исполнителя не меняют:
# для closed это память о том, кто исправил.
LOCKED_STATUSES = ("closed", "rejected")


def assignee_locked(bug):
    return bug.status in LOCKED_STATUSES


def assignee_candidates(project):
    """Кого можно назначить исполнителем: активные developer — участники проекта."""
    query = (
        sa.select(User)
        .join(User.role)
        .join(project_members, project_members.c.user_id == User.id)
        .where(
            project_members.c.project_id == project.id,
            User.is_active,
            Role.name == "developer",
        )
        .order_by(User.username)
    )
    return db.session.scalars(query).all()


def can_be_assignee(user, project):
    return user in assignee_candidates(project)


def unassign(bug, actor):
    """Снять исполнителя с бага.

    Общее правило: баг в работе без исполнителя возвращается в new.
    actor — кто выполнил действие; от его имени будет запись в истории.
    """
    bug.assignee = None
    if bug.status == "in_progress":
        bug.status = "new"
    bug.updater = actor


def unassign_user_bugs(user, actor, project=None):
    """Снять пользователя с его открытых багов (в одном проекте или во всех).

    Вызывается при удалении участника из проекта и при блокировке.
    Закрытые и отклонённые баги не трогаем — исполнитель на них остаётся.
    Возвращает список багов, с которых снято назначение. Коммит — за вызывающим.
    """
    query = (
        sa.select(Bug)
        .where(Bug.assignee_id == user.id, Bug.status.not_in(LOCKED_STATUSES))
        .order_by(Bug.id)
    )
    if project is not None:
        query = query.where(Bug.project_id == project.id)
    bugs = db.session.scalars(query).all()
    for bug in bugs:
        unassign(bug, actor)
    return bugs
