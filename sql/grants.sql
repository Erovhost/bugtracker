-- =====================================================================
-- Баг-трекер: права ролей bugtracker_app и bugtracker_readonly
--
-- Роли создаёт sql/roles.sql (администратор PostgreSQL), он же вызывает
-- этот файл. Сам файл может запускать ВЛАДЕЛЕЦ базы — владелец вправе
-- раздавать права на свои объекты:
--   psql -U bugtracker -d bugtracker -f sql/grants.sql
--
-- Запускайте после каждой миграции, добавляющей таблицы: права выдаются
-- по списку таблиц, новые таблицы автоматически их не получают.
-- Файл можно запускать повторно: права сначала отбираются, потом выдаются.
-- Работает в любой базе с нашей схемой (имя берётся из current_database()),
-- поэтому тесты выдают им права в bugtracker_test.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 2. Доступ к базе и схеме
-- ---------------------------------------------------------------------
-- По умолчанию подключаться к базе может любая роль (PUBLIC). Убираем это
-- и разрешаем явно. Владелец и суперпользователь не затронуты.
-- Имя базы берём из current_database(): файл работает и в bugtracker,
-- и в тестовой bugtracker_test. format(... %I ...) — безопасно
-- подставить имя в текст команды, EXECUTE — выполнить её.
DO $$
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO bugtracker_app, bugtracker_readonly',
        current_database()
    );
END
$$;

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
