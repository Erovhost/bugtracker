"""seed roles

Revision ID: a99f6624cf09
Revises: 98be09f151cc
Create Date: 2026-09-23 14:50:01.576027

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a99f6624cf09'
down_revision = '98be09f151cc'
branch_labels = None
depends_on = None


# Описание таблицы прямо здесь, а не импорт модели Role:
# миграция должна работать одинаково, даже если модель потом изменится.
roles_table = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
)

ROLE_NAMES = ["admin", "tester", "developer"]


def upgrade():
    op.bulk_insert(roles_table, [{"name": name} for name in ROLE_NAMES])


def downgrade():
    op.execute(roles_table.delete().where(roles_table.c.name.in_(ROLE_NAMES)))
