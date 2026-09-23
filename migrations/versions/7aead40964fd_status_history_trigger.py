"""status history trigger

Revision ID: 7aead40964fd
Revises: a99f6624cf09
Create Date: 2026-09-23 15:53:47.297220

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7aead40964fd'
down_revision = 'a99f6624cf09'
branch_labels = None
depends_on = None


# Функция триггера: пишет строку в status_history.
# OLD — строка бага до изменения, NEW — после. Автор смены — bugs.updated_by.
CREATE_FUNCTION = """
CREATE FUNCTION log_bug_status_change() RETURNS trigger AS $$
BEGIN
    INSERT INTO status_history (bug_id, old_status, new_status, changed_by)
    VALUES (NEW.id, OLD.status, NEW.status, NEW.updated_by);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

# Триггер срабатывает после UPDATE колонки status и только если статус
# действительно изменился (UPDATE со старым значением историю не пишет).
CREATE_TRIGGER = """
CREATE TRIGGER trg_bugs_status_history
    AFTER UPDATE OF status ON bugs
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_bug_status_change();
"""


def upgrade():
    op.execute(CREATE_FUNCTION)
    op.execute(CREATE_TRIGGER)


def downgrade():
    op.execute("DROP TRIGGER trg_bugs_status_history ON bugs;")
    op.execute("DROP FUNCTION log_bug_status_change();")
