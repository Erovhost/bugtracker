from datetime import datetime
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so

from app import db

# Связующая таблица «многие ко многим»: какой пользователь в каком проекте.
# Своих данных у неё нет, поэтому это простая таблица, а не класс-модель.
project_members = sa.Table(
    "project_members",
    db.metadata,
    sa.Column("project_id", sa.ForeignKey("projects.id"), primary_key=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(50), unique=True)

    # Все пользователи с этой ролью: role.users
    users: so.Mapped[list["User"]] = so.relationship(back_populates="role")

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model):
    __tablename__ = "users"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), unique=True)
    password_hash: so.Mapped[str] = so.mapped_column(sa.String(256))
    role_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("roles.id"))
    # default — подставляет SQLAlchemy при INSERT,
    # server_default — DEFAULT в самой таблице (на случай вставки через SQL)
    is_active: so.Mapped[bool] = so.mapped_column(
        default=True, server_default=sa.true()
    )
    created_at: so.Mapped[datetime] = so.mapped_column(server_default=sa.func.now())

    # Роль пользователя: user.role
    role: so.Mapped["Role"] = so.relationship(back_populates="users")
    # Проекты, в которых пользователь участник: user.projects
    projects: so.Mapped[list["Project"]] = so.relationship(
        secondary=project_members, back_populates="members"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class Project(db.Model):
    __tablename__ = "projects"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(120), unique=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    created_by: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey("users.id"))
    created_at: so.Mapped[datetime] = so.mapped_column(server_default=sa.func.now())

    # Кто создал проект: project.creator
    creator: so.Mapped[Optional["User"]] = so.relationship()
    # Участники проекта: project.members
    members: so.Mapped[list["User"]] = so.relationship(
        secondary=project_members, back_populates="projects"
    )
    # Баги проекта: project.bugs
    bugs: so.Mapped[list["Bug"]] = so.relationship(back_populates="project")

    def __repr__(self):
        return f"<Project {self.name}>"


class Bug(db.Model):
    __tablename__ = "bugs"
    # Допустимые значения проверяет сама база (CHECK)
    __table_args__ = (
        sa.CheckConstraint(
            "severity IN ('critical', 'major', 'minor', 'trivial')",
            name="ck_bugs_severity",
        ),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_bugs_priority",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'in_progress', 'fixed', 'rejected', 'closed')",
            name="ck_bugs_status",
        ),
    )

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    project_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("projects.id"), index=True
    )
    title: so.Mapped[str] = so.mapped_column(sa.String(200))
    steps: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    expected: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    actual: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)
    environment: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    severity: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    priority: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    status: so.Mapped[str] = so.mapped_column(
        sa.String(20), index=True, default="new", server_default="new"
    )
    reporter_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"))
    assignee_id: so.Mapped[Optional[int]] = so.mapped_column(
        sa.ForeignKey("users.id"), index=True
    )
    updated_by: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey("users.id"))
    created_at: so.Mapped[datetime] = so.mapped_column(server_default=sa.func.now())
    # onupdate — SQLAlchemy обновляет время при каждом UPDATE бага
    updated_at: so.Mapped[datetime] = so.mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )

    project: so.Mapped["Project"] = so.relationship(back_populates="bugs")
    # Три связи с users, поэтому для каждой указываем, через какую колонку
    reporter: so.Mapped["User"] = so.relationship(foreign_keys=[reporter_id])
    assignee: so.Mapped[Optional["User"]] = so.relationship(foreign_keys=[assignee_id])
    updater: so.Mapped[Optional["User"]] = so.relationship(foreign_keys=[updated_by])
    # Комментарии и история удаляются вместе с багом
    comments: so.Mapped[list["Comment"]] = so.relationship(
        back_populates="bug", cascade="all, delete-orphan"
    )
    history: so.Mapped[list["StatusHistory"]] = so.relationship(
        back_populates="bug", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Bug {self.id} {self.status}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    bug_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("bugs.id", ondelete="CASCADE")
    )
    author_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"))
    text: so.Mapped[str] = so.mapped_column(sa.Text)
    created_at: so.Mapped[datetime] = so.mapped_column(server_default=sa.func.now())

    bug: so.Mapped["Bug"] = so.relationship(back_populates="comments")
    author: so.Mapped["User"] = so.relationship()

    def __repr__(self):
        return f"<Comment {self.id} on bug {self.bug_id}>"


class StatusHistory(db.Model):
    __tablename__ = "status_history"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    bug_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("bugs.id", ondelete="CASCADE")
    )
    old_status: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    new_status: so.Mapped[str] = so.mapped_column(sa.String(20))
    changed_by: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey("users.id"))
    changed_at: so.Mapped[datetime] = so.mapped_column(server_default=sa.func.now())

    bug: so.Mapped["Bug"] = so.relationship(back_populates="history")
    changer: so.Mapped[Optional["User"]] = so.relationship()

    def __repr__(self):
        return f"<StatusHistory bug {self.bug_id}: {self.old_status} -> {self.new_status}>"
