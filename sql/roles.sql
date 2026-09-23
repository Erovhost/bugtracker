-- =====================================================================
-- Баг-трекер: роли PostgreSQL с минимальными правами
--
--   bugtracker          — владелец базы (уже есть): миграции, полный доступ
--   bugtracker_app      — роль приложения: только нужные операции с данными,
--                         без CREATE / ALTER / DROP
--   bugtracker_readonly — только чтение для отчётов, без password_hash
--
-- Запускает пользователь с правом CREATEROLE: локально — администратор
-- PostgreSQL, на Render — владелец базы (у него это право есть):
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

-- Пароли храним хэшем SCRAM-SHA-256. На некоторых серверах (например, Render)
-- по умолчанию стоит устаревший MD5; настройка действует только в этом сеансе.
SET password_encryption = 'scram-sha-256';

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

-- LOGIN — может подключаться; NOCREATEDB/NOCREATEROLE — никаких административных
-- прав. Суперпользователями новые роли не бывают и так (это значение по
-- умолчанию); явно писать NOSUPERUSER нельзя: в PostgreSQL 16+ это разрешено
-- только суперпользователю, а на хостинге (Render) у владельца базы есть
-- CREATEROLE, но нет SUPERUSER. :'...' — psql подставляет пароль в кавычках.
ALTER ROLE bugtracker_app
    LOGIN NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER ROLE bugtracker_readonly
    LOGIN NOCREATEDB NOCREATEROLE PASSWORD :'readonly_password';

COMMIT;

-- ---------------------------------------------------------------------
-- 2–4. Права на базу, схему, таблицы и представления — в отдельном файле,
-- который может запускать и владелец базы (без пароля postgres)
-- ---------------------------------------------------------------------
\ir grants.sql

\echo 'Роли bugtracker_app и bugtracker_readonly настроены.'
