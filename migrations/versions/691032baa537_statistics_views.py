"""statistics views

Revision ID: 691032baa537
Revises: 39b3923200b9
Create Date: 2026-09-23 16:35:30.136803

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '691032baa537'
down_revision = '39b3923200b9'
branch_labels = None
depends_on = None


# Статистика багов по проектам и статусам: одна строка на проект.
# LEFT JOIN — проекты без багов тоже попадают в отчёт (с нулями).
# count(b.id) не считает NULL, поэтому у проекта без багов total = 0.
# count(*) FILTER (WHERE ...) — считать только подходящие строки.
CREATE_BUG_STATS = """
CREATE VIEW v_bug_stats AS
SELECT
    p.id   AS project_id,
    p.name AS project_name,
    count(b.id) AS total,
    count(*) FILTER (WHERE b.status = 'new')         AS status_new,
    count(*) FILTER (WHERE b.status = 'in_progress') AS status_in_progress,
    count(*) FILTER (WHERE b.status = 'fixed')       AS status_fixed,
    count(*) FILTER (WHERE b.status = 'rejected')    AS status_rejected,
    count(*) FILTER (WHERE b.status = 'closed')      AS status_closed
FROM projects p
LEFT JOIN bugs b ON b.project_id = p.id
GROUP BY p.id, p.name;
"""

# Открытые баги (new, in_progress, fixed) по исполнителям в каждом проекте.
# LEFT JOIN users — баги без исполнителя дают строку с assignee_id = NULL.
CREATE_OPEN_BY_ASSIGNEE = """
CREATE VIEW v_open_bugs_by_assignee AS
SELECT
    b.project_id,
    u.id        AS assignee_id,
    u.username  AS assignee_username,
    u.is_active AS assignee_is_active,
    count(*) AS open_total,
    count(*) FILTER (WHERE b.status = 'new')         AS status_new,
    count(*) FILTER (WHERE b.status = 'in_progress') AS status_in_progress,
    count(*) FILTER (WHERE b.status = 'fixed')       AS status_fixed
FROM bugs b
LEFT JOIN users u ON u.id = b.assignee_id
WHERE b.status IN ('new', 'in_progress', 'fixed')
GROUP BY b.project_id, u.id, u.username, u.is_active;
"""


def upgrade():
    op.execute(CREATE_BUG_STATS)
    op.execute(CREATE_OPEN_BY_ASSIGNEE)


def downgrade():
    op.execute("DROP VIEW v_open_bugs_by_assignee;")
    op.execute("DROP VIEW v_bug_stats;")
