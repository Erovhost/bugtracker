-- =====================================================================
-- Баг-трекер: роли PostgreSQL с минимальными правами
--
--   bugtracker          — владелец базы (уже есть): миграции, полный доступ
--   bugtracker_app      — роль приложения: только нужные операции с данными,
--                         без CREATE / ALTER / DROP
--   bugtracker_readonly — только чтение для отчётов, без password_hash
--
-- Запускает администратор PostgreSQL (создавать роли может только он):
--   psql -U postgres -d bugtracker -f sql/roles.sql
-- Скрипт спросит пароли для новых ролей. Можно передать их сразу:
--   -v app_password=... -v readonly_password=...
-- (но тогда пароли останутся в истории команд).
--
-- Скрипт можно запускать повторно: роли создаются, если их нет, права
-- выдаются заново. Запускайте его после каждой миграции, добавляющей
-- таблицы, — новые таблицы права автоматически не получают.
-- =====================================================================

\set ON_ERROR_STOP on

-- Пароли: из параметров -v или спросить (ввод не сохраняется в истории)
\if :{?app_password}
\else
    \prompt 'Пароль для bugtracker_app: ' app_password
\endif
\if :{?readonly_password}
\else
    \prompt 'Пароль для bugtracker_readonly: ' readonly_password
\endif

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Создать роли, если их ещё нет, и задать пароли
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bugtracker_app') THEN
        CREATE ROLE bugtracker_app;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bugtracker_readonly') THEN
        CREATE ROLE bugtracker_readonly;
    END IF;
END
$$;

-- LOGIN — может подключаться; NOSUPERUSER/NOCREATEDB/NOCREATEROLE — никаких
-- административных прав. :'...' — psql подставляет пароль в кавычках.
ALTER ROLE bugtracker_app
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER ROLE bugtracker_readonly
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'readonly_password';

-- ---------------------------------------------------------------------
-- 2. Доступ к базе и схеме
-- ---------------------------------------------------------------------
-- По умолчанию подключаться к базе может любая роль (PUBLIC). Убираем это
-- и разрешаем явно. Владелец и суперпользователь не затронуты.
REVOKE ALL ON DATABASE bugtracker FROM PUBLIC;
GRANT CONNECT ON DATABASE bugtracker TO bugtracker_app, bugtracker_readonly;

-- Создавать объекты в схеме public может только владелец
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO bugtracker_app, bugtracker_readonly;

-- Сбрасываем прежние права, чтобы повторный запуск давал ровно то, что ниже
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM bugtracker_app, bugtracker_readonly;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM bugtracker_app, bugtracker_readonly;

-- ---------------------------------------------------------------------
-- 3. Права приложения: только то, что делает код
-- ---------------------------------------------------------------------
GRANT SELECT                 ON roles           TO bugtracker_app;
-- пользователей не удаляем, только блокируем
GRANT SELECT, INSERT, UPDATE ON users           TO bugtracker_app;
-- удаления проектов и багов в приложении нет
GRANT SELECT, INSERT, UPDATE ON projects        TO bugtracker_app;
GRANT SELECT, INSERT, UPDATE ON bugs            TO bugtracker_app;
-- «убрать участника из проекта» — это DELETE строки
GRANT SELECT, INSERT, DELETE ON project_members TO bugtracker_app;
-- журналы: только добавлять и читать, менять и удалять нельзя
-- (INSERT в status_history нужен триггеру: он работает с правами того,
-- кто изменил bugs)
GRANT SELECT, INSERT         ON comments        TO bugtracker_app;
GRANT SELECT, INSERT         ON status_history  TO bugtracker_app;
-- представления для страницы статистики
GRANT SELECT ON v_bug_stats, v_open_bugs_by_assignee TO bugtracker_app;
-- счётчики SERIAL: без USAGE не получить новый id при INSERT
GRANT USAGE ON SEQUENCE
    users_id_seq, projects_id_seq, bugs_id_seq, comments_id_seq, status_history_id_seq
    TO bugtracker_app;

-- ---------------------------------------------------------------------
-- 4. Роль только для чтения: все данные, кроме хэшей паролей
-- ---------------------------------------------------------------------
GRANT SELECT ON roles, projects, project_members, bugs, comments, status_history
    TO bugtracker_readonly;
GRANT SELECT ON v_bug_stats, v_open_bugs_by_assignee TO bugtracker_readonly;
-- Права на отдельные колонки: password_hash в список не входит
GRANT SELECT (id, username, email, role_id, is_active, approved_at, created_at)
    ON users TO bugtracker_readonly;

COMMIT;

\echo 'Роли bugtracker_app и bugtracker_readonly настроены.'
