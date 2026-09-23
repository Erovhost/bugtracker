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
-- Скрипт можно запускать повторно: роли создаются, если их нет.
-- Права выдаёт sql/grants.sql (подключается в конце). После миграции,
-- добавляющей таблицы, достаточно запустить только grants.sql — это
-- может сделать владелец базы bugtracker, пароль postgres не нужен.
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

COMMIT;

-- ---------------------------------------------------------------------
-- 2–4. Права на базу, схему, таблицы и представления — в отдельном файле,
-- который может запускать и владелец базы (без пароля postgres)
-- ---------------------------------------------------------------------
\ir grants.sql

\echo 'Роли bugtracker_app и bugtracker_readonly настроены.'
