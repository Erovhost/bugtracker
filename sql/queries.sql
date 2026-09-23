-- =====================================================================
-- Баг-трекер: показательные SQL-запросы (PostgreSQL)
--
-- Запуск целиком:  psql -U bugtracker -d bugtracker -f sql/queries.sql
-- Файл ничего не меняет в базе: все изменения данных (раздел 6)
-- выполняются внутри BEGIN ... ROLLBACK и откатываются.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Выборки с JOIN
-- ---------------------------------------------------------------------

-- 1.1. Список багов с названием проекта, автором и исполнителем.
-- INNER JOIN с projects и users (автор есть всегда),
-- LEFT JOIN с users для исполнителя: он может быть не назначен (NULL).
SELECT
    b.id,
    b.title,
    p.name                              AS project,
    b.status,
    b.severity,
    reporter.username                   AS reporter,
    COALESCE(assignee.username, '—')    AS assignee
FROM bugs b
JOIN projects p          ON p.id = b.project_id
JOIN users reporter      ON reporter.id = b.reporter_id
LEFT JOIN users assignee ON assignee.id = b.assignee_id
ORDER BY b.id DESC
LIMIT 20;

-- 1.2. Участники каждого проекта с их ролями.
-- Связь «многие ко многим» через таблицу project_members.
SELECT
    p.name     AS project,
    u.username,
    r.name     AS role
FROM project_members pm
JOIN projects p ON p.id = pm.project_id
JOIN users u    ON u.id = pm.user_id
JOIN roles r    ON r.id = u.role_id
ORDER BY p.name, u.username;

-- 1.3. Комментарии с автором и заголовком бага, новые сверху.
SELECT
    c.created_at,
    u.username AS author,
    b.id       AS bug_id,
    b.title,
    c.text
FROM comments c
JOIN users u ON u.id = c.author_id
JOIN bugs b  ON b.id = c.bug_id
ORDER BY c.created_at DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- 2. Агрегаты: COUNT, GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------

-- 2.1. Сколько багов каждой серьёзности.
SELECT severity, count(*) AS bugs
FROM bugs
GROUP BY severity
ORDER BY bugs DESC;

-- 2.2. Проекты, где больше одного открытого бага.
-- WHERE фильтрует строки ДО группировки, HAVING — группы ПОСЛЕ.
SELECT
    p.name,
    count(*) AS open_bugs
FROM bugs b
JOIN projects p ON p.id = b.project_id
WHERE b.status IN ('new', 'in_progress', 'fixed')
GROUP BY p.name
HAVING count(*) > 1
ORDER BY open_bugs DESC;

-- 2.3. Сколько участников в каждом проекте (включая проекты без участников).
-- LEFT JOIN сохраняет проекты без строк в project_members;
-- count(pm.user_id) не считает NULL, поэтому у таких проектов будет 0.
SELECT
    p.name,
    count(pm.user_id) AS members
FROM projects p
LEFT JOIN project_members pm ON pm.project_id = p.id
GROUP BY p.name
ORDER BY p.name;

-- 2.4. Среднее время от создания бага до закрытия, по проектам.
-- Время закрытия берём из истории статусов (её пишет триггер).
-- Разность двух TIMESTAMP в PostgreSQL — это INTERVAL.
SELECT
    p.name AS project,
    count(*) AS closed_bugs,
    avg(h.changed_at - b.created_at) AS avg_time_to_close
FROM status_history h
JOIN bugs b     ON b.id = h.bug_id
JOIN projects p ON p.id = b.project_id
WHERE h.new_status = 'closed'
GROUP BY p.name
ORDER BY p.name;


-- ---------------------------------------------------------------------
-- 3. Подзапросы: EXISTS / NOT EXISTS / IN
-- ---------------------------------------------------------------------

-- 3.1. Активные разработчики и тестировщики, которые не состоят ни в одном
-- проекте (кандидаты на добавление в проекты).
SELECT u.username, r.name AS role
FROM users u
JOIN roles r ON r.id = u.role_id
WHERE u.is_active
  AND r.name IN ('tester', 'developer')
  AND NOT EXISTS (
      SELECT 1 FROM project_members pm WHERE pm.user_id = u.id
  )
ORDER BY u.username;

-- 3.2. Баги, у которых есть хотя бы один комментарий.
SELECT b.id, b.title
FROM bugs b
WHERE EXISTS (SELECT 1 FROM comments c WHERE c.bug_id = b.id)
ORDER BY b.id;

-- 3.3. Заявки на регистрацию, ожидающие одобрения администратора.
SELECT username, email, created_at
FROM users
WHERE approved_at IS NULL
ORDER BY created_at;


-- ---------------------------------------------------------------------
-- 4. История статусов (данные пишет триггер trg_bugs_status_history)
-- ---------------------------------------------------------------------

-- 4.1. Кто сколько багов перевёл в «fixed» (исправил).
SELECT
    u.username,
    count(*) AS fixed_count
FROM status_history h
JOIN users u ON u.id = h.changed_by
WHERE h.new_status = 'fixed'
GROUP BY u.username
ORDER BY fixed_count DESC;

-- 4.2. Полная история одного бага (самого нового) по порядку.
SELECT
    h.changed_at,
    u.username AS changed_by,
    h.old_status,
    h.new_status
FROM status_history h
JOIN users u ON u.id = h.changed_by
WHERE h.bug_id = (SELECT max(id) FROM bugs)
ORDER BY h.id;

-- 4.3. Баги, которые возвращали из «fixed» обратно (проверка не прошла):
-- сколько раз для каждого.
SELECT
    b.id,
    b.title,
    count(*) AS returns
FROM status_history h
JOIN bugs b ON b.id = h.bug_id
WHERE h.old_status = 'fixed' AND h.new_status IN ('in_progress', 'new')
GROUP BY b.id, b.title
ORDER BY returns DESC;


-- ---------------------------------------------------------------------
-- 5. Представления (VIEW)
-- ---------------------------------------------------------------------

-- 5.1. Статистика по проектам: к представлению обращаемся как к таблице.
SELECT * FROM v_bug_stats ORDER BY project_name;

-- 5.2. Самые загруженные исполнители (по открытым багам во всех проектах).
-- К представлению можно применять группировку, как к обычной таблице.
SELECT
    assignee_username,
    sum(open_total) AS open_bugs
FROM v_open_bugs_by_assignee
WHERE assignee_id IS NOT NULL
GROUP BY assignee_username
ORDER BY open_bugs DESC;


-- ---------------------------------------------------------------------
-- 6. Изменение данных: INSERT, UPDATE, DELETE
-- Всё внутри транзакции, которая в конце откатывается (ROLLBACK).
-- ---------------------------------------------------------------------

BEGIN;

-- 6.1. INSERT ... SELECT: добавить комментарий к самому новому багу
-- от имени его автора. RETURNING возвращает вставленную строку.
INSERT INTO comments (bug_id, author_id, text)
SELECT id, reporter_id, 'Проверочный комментарий из queries.sql'
FROM bugs
ORDER BY id DESC
LIMIT 1
RETURNING id, bug_id, text;

-- 6.2. UPDATE: повысить приоритет всех открытых критических багов.
UPDATE bugs
SET priority = 'high'
WHERE severity = 'critical'
  AND status IN ('new', 'in_progress')
RETURNING id, title, priority;

-- 6.3. UPDATE статуса запускает триггер: он сам добавит строку
-- в status_history (автор — bugs.updated_by).
UPDATE bugs
SET status = 'in_progress'
WHERE id = (SELECT max(id) FROM bugs WHERE status = 'new');

SELECT bug_id, old_status, new_status, changed_by
FROM status_history
ORDER BY id DESC
LIMIT 1;

-- 6.4. Нарушение ограничения: недопустимый статус отклоняется CHECK.
-- SAVEPOINT позволяет «пережить» ошибку внутри транзакции.
SAVEPOINT before_bad_update;
UPDATE bugs SET status = 'done' WHERE id = (SELECT max(id) FROM bugs);
ROLLBACK TO SAVEPOINT before_bad_update;

-- 6.5. DELETE: удалить комментарий, добавленный в 6.1.
DELETE FROM comments
WHERE text = 'Проверочный комментарий из queries.sql'
RETURNING id;

-- Откатываем всё, что сделали в разделе 6: база остаётся как была.
ROLLBACK;
