-- =====================================================================
-- Баг-трекер: проверка прав ролей bugtracker_app и bugtracker_readonly
--
-- Запускать под каждой ролью (скрипт сам определяет, под какой):
--   psql -U bugtracker_app      -d bugtracker -f sql/check_roles.sql
--   psql -U bugtracker_readonly -d bugtracker -f sql/check_roles.sql
--
-- Перед каждой пробой печатается ожидаемый результат:
--   УСПЕХ        — команда должна выполниться;
--   ОШИБКА 42501 — insufficient_privilege, «нет доступа» (permission denied).
-- Сравните с тем, что вывел psql сразу после строки с ожиданием.
--
-- Скрипт ничего не меняет: всё внутри BEGIN ... ROLLBACK, каждая проба —
-- внутри SAVEPOINT, поэтому ошибка одной пробы не мешает следующим.
-- Нужен хотя бы один пользователь в таблице users (подойдёт админ).
-- Роли создаются скриптом sql/roles.sql.
-- =====================================================================

\set ON_ERROR_STOP off
\set QUIET on

SELECT current_user = 'bugtracker_app'      AS is_app,
       current_user = 'bugtracker_readonly' AS is_readonly
\gset

BEGIN;

\if :is_app
\echo '=== bugtracker_app ==='

\echo '[app 1] ожидается УСПЕХ: SELECT из roles'
SAVEPOINT probe;
SELECT count(*) FROM roles;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 2] ожидается УСПЕХ: SELECT из users'
SAVEPOINT probe;
SELECT count(*) FROM users;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 3] ожидается УСПЕХ: UPDATE users'
SAVEPOINT probe;
UPDATE users SET email = email WHERE id = (SELECT min(id) FROM users);
ROLLBACK TO SAVEPOINT probe;

\echo '[app 4] ожидается УСПЕХ: INSERT в users (заявка — неактивный пользователь)'
SAVEPOINT probe;
INSERT INTO users (username, email, password_hash, role_id, is_active)
VALUES ('check_roles_user', 'check_roles@example.com', 'h',
        (SELECT id FROM roles WHERE name = 'tester'), false);
ROLLBACK TO SAVEPOINT probe;

\echo '[app 5] ожидается УСПЕХ: INSERT в projects'
SAVEPOINT probe;
INSERT INTO projects (name, created_by)
VALUES ('check_roles_project', (SELECT min(id) FROM users));
ROLLBACK TO SAVEPOINT probe;

\echo '[app 6] ожидается УСПЕХ: INSERT в project_members'
SAVEPOINT probe;
WITH p AS (
    INSERT INTO projects (name, created_by)
    VALUES ('check_roles_project', (SELECT min(id) FROM users)) RETURNING id
)
INSERT INTO project_members (project_id, user_id)
SELECT id, (SELECT min(id) FROM users) FROM p;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 7] ожидается УСПЕХ: INSERT в bugs'
SAVEPOINT probe;
WITH p AS (
    INSERT INTO projects (name, created_by)
    VALUES ('check_roles_project', (SELECT min(id) FROM users)) RETURNING id
)
INSERT INTO bugs (project_id, title, severity, reporter_id, updated_by)
SELECT id, 'check', 'minor', (SELECT min(id) FROM users), (SELECT min(id) FROM users) FROM p;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 8] ожидается УСПЕХ: SELECT из представления v_bug_stats'
SAVEPOINT probe;
SELECT count(*) FROM v_bug_stats;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 9] ожидается УСПЕХ: SELECT из представления v_open_bugs_by_assignee'
SAVEPOINT probe;
SELECT count(*) FROM v_open_bugs_by_assignee;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 10] ожидается УСПЕХ: DELETE из project_members'
SAVEPOINT probe;
DELETE FROM project_members WHERE false;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 11] ожидается ОШИБКА 42501: DELETE из status_history (журнал)'
SAVEPOINT probe;
DELETE FROM status_history;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 12] ожидается ОШИБКА 42501: UPDATE status_history (журнал)'
SAVEPOINT probe;
UPDATE status_history SET new_status = new_status;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 13] ожидается ОШИБКА 42501: DELETE из comments (журнал)'
SAVEPOINT probe;
DELETE FROM comments;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 14] ожидается ОШИБКА 42501: UPDATE comments (журнал)'
SAVEPOINT probe;
UPDATE comments SET text = text;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 15] ожидается ОШИБКА 42501: DELETE из bugs'
SAVEPOINT probe;
DELETE FROM bugs;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 16] ожидается ОШИБКА 42501: DELETE из users'
SAVEPOINT probe;
DELETE FROM users;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 17] ожидается ОШИБКА 42501: DELETE из projects'
SAVEPOINT probe;
DELETE FROM projects;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 18] ожидается ОШИБКА 42501: INSERT в roles'
SAVEPOINT probe;
INSERT INTO roles (name) VALUES ('superuser');
ROLLBACK TO SAVEPOINT probe;

\echo '[app 19] ожидается ОШИБКА 42501: TRUNCATE bugs'
SAVEPOINT probe;
TRUNCATE bugs;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 20] ожидается ОШИБКА 42501: DROP TABLE bugs (сообщение «must be owner»)'
SAVEPOINT probe;
DROP TABLE bugs;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 21] ожидается ОШИБКА 42501: ALTER TABLE bugs (сообщение «must be owner»)'
SAVEPOINT probe;
ALTER TABLE bugs ADD COLUMN check_roles_column int;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 22] ожидается ОШИБКА 42501: CREATE TABLE в схеме public'
SAVEPOINT probe;
CREATE TABLE check_roles_table (id int);
ROLLBACK TO SAVEPOINT probe;

\echo '[app 23] ожидается ОШИБКА 42501: SELECT из alembic_version'
SAVEPOINT probe;
SELECT * FROM alembic_version;
ROLLBACK TO SAVEPOINT probe;

\echo '[app 24] ожидается ОШИБКА 42501: DROP VIEW v_bug_stats (сообщение «must be owner»)'
SAVEPOINT probe;
DROP VIEW v_bug_stats;
ROLLBACK TO SAVEPOINT probe;

\elif :is_readonly
\echo '=== bugtracker_readonly ==='

\echo '[ro 1] ожидается УСПЕХ: SELECT из bugs'
SAVEPOINT probe;
SELECT count(*) FROM bugs;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 2] ожидается УСПЕХ: SELECT разрешённых колонок users (без password_hash)'
SAVEPOINT probe;
SELECT count(*) FROM (
    SELECT id, username, email, role_id, is_active, approved_at, created_at FROM users
) AS allowed_columns;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 3] ожидается УСПЕХ: SELECT из представления v_bug_stats'
SAVEPOINT probe;
SELECT count(*) FROM v_bug_stats;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 4] ожидается УСПЕХ: SELECT из status_history'
SAVEPOINT probe;
SELECT count(*) FROM status_history;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 5] ожидается ОШИБКА 42501: SELECT password_hash из users'
SAVEPOINT probe;
SELECT password_hash FROM users;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 6] ожидается ОШИБКА 42501: SELECT * из users (звёздочка включает password_hash)'
SAVEPOINT probe;
SELECT * FROM users;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 7] ожидается ОШИБКА 42501: INSERT в comments'
SAVEPOINT probe;
INSERT INTO comments (bug_id, author_id, text) VALUES (1, 1, 'x');
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 8] ожидается ОШИБКА 42501: UPDATE bugs'
SAVEPOINT probe;
UPDATE bugs SET title = title;
ROLLBACK TO SAVEPOINT probe;

\echo '[ro 9] ожидается ОШИБКА 42501: CREATE TABLE в схеме public'
SAVEPOINT probe;
CREATE TABLE check_roles_table (id int);
ROLLBACK TO SAVEPOINT probe;

\else
\echo 'Этот скрипт нужно запускать под bugtracker_app или bugtracker_readonly.'
\endif

ROLLBACK;
\echo 'Готово: все изменения откачены.'
