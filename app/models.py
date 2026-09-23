from datetime import datetime

import sqlalchemy as sa
import sqlalchemy.orm as so

from app import db


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

    def __repr__(self):
        return f"<User {self.username}>"
