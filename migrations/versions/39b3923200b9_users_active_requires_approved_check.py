"""users active requires approved check

Revision ID: 39b3923200b9
Revises: 781aa055c902
Create Date: 2026-09-23 16:23:00.271662

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39b3923200b9'
down_revision = '781aa055c902'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Сначала чиним данные: активный пользователь без approved_at нарушил бы
    #    новое ограничение, и PostgreSQL отказался бы его создавать.
    #    Точного времени одобрения нет — берём время регистрации.
    op.execute(
        "UPDATE users SET approved_at = created_at "
        "WHERE is_active AND approved_at IS NULL"
    )
    # 2. Добавляем ограничение: «одобрен ИЛИ неактивен».
    #    PostgreSQL при создании проверит все существующие строки.
    op.create_check_constraint(
        "ck_users_active_approved",
        "users",
        "approved_at IS NOT NULL OR NOT is_active",
    )


def downgrade():
    op.drop_constraint("ck_users_active_approved", "users", type_="check")
