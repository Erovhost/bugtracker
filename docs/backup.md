# Резервное копирование и восстановление базы данных

Инструмент — `pg_dump` / `pg_restore` из комплекта PostgreSQL. `pg_dump` снимает
согласованную копию одной базы, не останавливая её работу. Команды — для
PowerShell, из папки проекта. Копии кладём в `backups/` (папка в `.gitignore`).

> ⚠️ **Копия содержит все данные, включая хэши паролей пользователей.**
> Никогда не коммитьте её в Git и не отправляйте по открытым каналам. Храните
> копии отдельно от сервера базы (другой диск, облачное хранилище с доступом
> только для администратора), иначе при поломке диска пропадут и база, и копии.

## Что попадает в копию

Таблицы и данные (включая `alembic_version` — восстановленная база знает свою
версию миграций), представления, функция и триггер истории статусов,
ограничения (PK, FK, UNIQUE, CHECK), индексы, права на объекты (GRANT).

**Не попадают роли** (`bugtracker`, `bugtracker_app`, `bugtracker_readonly`):
роли — объекты всего сервера PostgreSQL, а не одной базы. На новом сервере их
нужно создать заново: владельца — как на этапе 0, остальные — `sql/roles.sql`.
Полную копию ролей может сделать администратор: `pg_dumpall -U postgres --roles-only`.

## 1. Сделать копию

Основной формат — **custom** (`-F c`): сжатый архив, восстанавливается через
`pg_restore`, можно посмотреть содержимое и восстановить выборочно.

```powershell
New-Item -ItemType Directory -Force backups
$date = Get-Date -Format "yyyy-MM-dd_HH-mm"
pg_dump -U bugtracker -d bugtracker -F c -f "backups\bugtracker_$date.dump"
```

Дополнительно можно сделать копию в виде **обычного SQL** — её можно открыть в
редакторе и прочитать:

```powershell
pg_dump -U bugtracker -d bugtracker -f "backups\bugtracker_$date.sql"
```

Копию делает владелец базы `bugtracker` (ему доступны все объекты).
`pg_dump` спросит пароль.

## 2. Проверить копию

Копию, которую ни разу не пробовали восстановить, нельзя считать надёжной.
Быстрая проверка — посмотреть оглавление архива:

```powershell
pg_restore --list "backups\bugtracker_ДАТА.dump"
```

Должны быть строки `TABLE`, `TABLE DATA`, `VIEW`, `FUNCTION`, `TRIGGER`.

Полная проверка — восстановить в отдельную базу (раздел 3) и сравнить с рабочей.

## 3. Восстановить в новую (пустую) базу

Так проверяют копию и так переносят базу на другой сервер. Рабочая база при
этом не затрагивается.

**3.1.** Создать пустую базу. Создавать базы может только администратор:

```powershell
psql -U postgres -c "CREATE DATABASE bugtracker_restore OWNER bugtracker ENCODING 'UTF8' TEMPLATE template0;"
```

**3.2.** Восстановить.

Из custom-архива:

```powershell
pg_restore -U bugtracker -d bugtracker_restore --no-owner "backups\bugtracker_ДАТА.dump"
```

Из SQL-файла:

```powershell
psql -U bugtracker -d bugtracker_restore -f "backups\bugtracker_ДАТА.sql"
```

`--no-owner` — объекты станут принадлежать тому, кто восстанавливает
(`bugtracker`). Это нужно при переносе на сервер, где владелец называется
иначе. Если роли `bugtracker_app` / `bugtracker_readonly` на сервере ещё нет,
`pg_restore` выдаст предупреждения на команды GRANT — это не мешает
восстановлению данных; после создания ролей запустите `sql/roles.sql`.

**3.3.** Сравнить с рабочей базой, например количество строк:

```powershell
$q = "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM bugs) AS bugs, (SELECT count(*) FROM status_history) AS history;"
psql -U bugtracker -d bugtracker -c $q
psql -U bugtracker -d bugtracker_restore -c $q
```

**3.4.** Удалить проверочную базу (может владелец):

```powershell
psql -U bugtracker -d postgres -c "DROP DATABASE bugtracker_restore;"
```

## 4. Восстановить рабочую базу из копии

Нужно, когда данные в рабочей базе испорчены. **Всё, что изменилось после
создания копии, будет потеряно.**

1. Остановить приложение (`Ctrl+C` в окне `flask run`), чтобы никто не менял
   данные во время восстановления.
2. На всякий случай сделать копию текущего (испорченного) состояния — раздел 1.
3. Восстановить с удалением существующих объектов:

   ```powershell
   pg_restore -U bugtracker -d bugtracker --clean --if-exists --no-owner "backups\bugtracker_ДАТА.dump"
   ```

   `--clean` удаляет объекты перед созданием, `--if-exists` не даёт ошибок,
   если какого-то объекта уже нет.
4. Выдать права ролям заново: `psql -U postgres -d bugtracker -f sql/roles.sql`.
5. Проверить версию миграций и запустить приложение:

   ```powershell
   flask db current
   flask run
   ```

## 5. Как часто делать копии

Для учебного проекта — перед каждой миграцией (`flask db upgrade`) и перед
ручными изменениями данных в psql. Для рабочего сервера — автоматически, по
расписанию (например, раз в сутки через Планировщик заданий Windows или cron),
храня несколько последних копий.

Чтобы `pg_dump` не спрашивал пароль при запуске по расписанию, пароль кладут
в файл `%APPDATA%\postgresql\pgpass.conf` (строка
`localhost:5432:bugtracker:bugtracker:ПАРОЛЬ`), доступный только этому
пользователю Windows, а не в сам скрипт.
