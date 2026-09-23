-- Баг-трекер: SQL-версия схемы БД (PostgreSQL 13+).
-- Справочный файл для отчёта по ПМ11. В приложении таблицы создаются
-- миграциями Flask-Migrate (этап 2), эталон схемы описан в ТЗ.

BEGIN;

-- Роли пользователей: admin / tester / developer
CREATE TABLE roles (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Пользователи. Не удаляются, а блокируются (is_active = false).
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role_id       INTEGER      NOT NULL REFERENCES roles (id),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    approved_at   TIMESTAMP,              -- NULL: заявка ещё не одобрена
    created_at    TIMESTAMP    NOT NULL DEFAULT now(),
    -- Нельзя быть активным, не будучи одобренным: «одобрен ИЛИ неактивен»
    CONSTRAINT ck_users_active_approved
        CHECK (approved_at IS NOT NULL OR NOT is_active)
);

-- Проекты
CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    created_by  INTEGER      NOT NULL REFERENCES users (id),
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);

-- Участники проектов (связь «многие ко многим» между users и projects)
CREATE TABLE project_members (
    project_id INTEGER NOT NULL REFERENCES projects (id),
    user_id    INTEGER NOT NULL REFERENCES users (id),
    PRIMARY KEY (project_id, user_id)
);

-- Баги
CREATE TABLE bugs (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER      NOT NULL REFERENCES projects (id),
    title       VARCHAR(200) NOT NULL,
    steps       TEXT,
    expected    TEXT,
    actual      TEXT,
    environment VARCHAR(200),
    severity    VARCHAR(20)  NOT NULL
                CONSTRAINT ck_bugs_severity
                CHECK (severity IN ('critical', 'major', 'minor', 'trivial')),
    priority    VARCHAR(20)  NOT NULL DEFAULT 'medium'
                CONSTRAINT ck_bugs_priority
                CHECK (priority IN ('high', 'medium', 'low')),
    status      VARCHAR(20)  NOT NULL DEFAULT 'new'
                CONSTRAINT ck_bugs_status
                CHECK (status IN ('new', 'in_progress', 'fixed', 'rejected', 'closed')),
    reporter_id INTEGER      NOT NULL REFERENCES users (id),
    assignee_id INTEGER      REFERENCES users (id),  -- NULL: баг ещё не назначен
    updated_by  INTEGER      NOT NULL REFERENCES users (id),  -- при создании = reporter_id
    created_at  TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT now()
);

-- Комментарии. Удаляются вместе с багом.
CREATE TABLE comments (
    id         SERIAL PRIMARY KEY,
    bug_id     INTEGER   NOT NULL REFERENCES bugs (id) ON DELETE CASCADE,
    author_id  INTEGER   NOT NULL REFERENCES users (id),
    text       TEXT      NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- История смены статусов. Пишется только триггером при UPDATE статуса.
-- Удаляется вместе с багом.
CREATE TABLE status_history (
    id         SERIAL PRIMARY KEY,
    bug_id     INTEGER     NOT NULL REFERENCES bugs (id) ON DELETE CASCADE,
    old_status VARCHAR(20) NOT NULL,
    new_status VARCHAR(20) NOT NULL,
    changed_by INTEGER     NOT NULL REFERENCES users (id),
    changed_at TIMESTAMP   NOT NULL DEFAULT now()
);

-- Индексы для частых выборок: баги проекта, фильтр по статусу и исполнителю
CREATE INDEX ix_bugs_project_id   ON bugs (project_id);
CREATE INDEX ix_bugs_status       ON bugs (status);
CREATE INDEX ix_bugs_assignee_id  ON bugs (assignee_id);

-- Триггер: при смене статуса бага пишет запись в status_history.
-- Кто сменил статус, берётся из bugs.updated_by.
CREATE FUNCTION log_bug_status_change() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO status_history (bug_id, old_status, new_status, changed_by)
    VALUES (NEW.id, OLD.status, NEW.status, NEW.updated_by);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bugs_status_history
    AFTER UPDATE OF status ON bugs
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_bug_status_change();

-- Справочные данные
INSERT INTO roles (name) VALUES ('admin'), ('tester'), ('developer');

COMMIT;
