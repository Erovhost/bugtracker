# Сквозные HTTP-сценарии

Сценарии, по которым приложение проверено под ролью БД `bugtracker_app`
(минимальные права, см. `sql/roles.sql`). На этапе 11 они станут тестами
pytest (тестовый клиент Flask), часть — сквозными тестами Playwright.

Цель набора — показать, что **приложению хватает минимальных прав**: ни одно
действие не должно давать ответ 5xx (ошибка сервера, в том числе
«нет доступа» от PostgreSQL). Все запросы, меняющие данные, — POST с
CSRF-токеном той же сессии.

## Исходные данные

Создаются владельцем БД (`bugtracker`) перед сценариями и удаляются после:

| Логин | Роль | Состояние |
|---|---|---|
| adm | admin | активен |
| zoe | tester | активен, участник проекта P |
| bob | developer | активен, участник проекта P |
| dan | developer | активен, участник проекта P |
| req | tester | заявка (approved_at = NULL, неактивен) |

Проект **P** с участниками zoe, bob, dan. У всех пароль `secret123`.
Каждый пользователь входит через `POST /auth/login`.

## Сценарии

«Права БД» — какие операции PostgreSQL выполняет сценарий под `bugtracker_app`.

| № | Кто | Действие | Ожидаемый ответ | Проверить в БД | Права БД |
|---|---|---|---|---|---|
| 1 | adm | `GET /admin/` — список пользователей | 200 | — | SELECT users, roles |
| 2 | adm | `POST /admin/users/<req>/approve`, роль developer | 302 | req: approved_at заполнен, is_active = true, роль developer | UPDATE users |
| 3 | adm | `POST /admin/users/new` — логин made, роль tester | 302 | made: активен, одобрен, пароль — хэш | INSERT users, sequence |
| 4 | adm | `POST /project/new` — проект P_new | 302 | проект создан, created_by = adm | INSERT projects, sequence |
| 5 | adm | `POST /project/<P>/edit` — новое описание | 302 | описание изменилось | UPDATE projects |
| 6 | adm | `POST /project/<P>/members/add` — req | 302 | req в участниках P | INSERT project_members |
| 7 | zoe | `POST /bugs/project/<P>/new` — баг B1 (major, high) | 302 | B1: status new, reporter = updated_by = zoe | INSERT bugs, sequence |
| 8 | zoe | `POST /bugs/project/<P>/new` — баг B2 (minor, low) | 302 | B2 создан | INSERT bugs |
| 9 | zoe | `POST /bugs/<B1>/assign` — bob | 302 | B1: assignee = bob, updated_by = zoe | UPDATE bugs |
| 10 | zoe | `POST /bugs/<B1>/comments` — текст | 302 | комментарий от zoe | INSERT comments, sequence |
| 11 | bob | `POST /bugs/<B1>/status` — in_progress | 302 | B1 in_progress; история new → in_progress от bob | UPDATE bugs + триггер INSERT status_history |
| 12 | bob | `POST /bugs/<B1>/status` — fixed | 302 | B1 fixed; запись в истории | UPDATE bugs + триггер |
| 13 | zoe | `POST /bugs/<B1>/status` — closed | 302 | B1 closed; история new → in_progress → fixed → closed | UPDATE bugs + триггер |
| 14 | dan | `POST /bugs/<B2>/status` — in_progress | 302 | B2 in_progress, assignee = dan (взял свободный баг) | UPDATE bugs + триггер |
| 15 | bob | `POST /bugs/<B1>/edit` — не автор | **403** | B1 не изменился | SELECT |
| 16 | adm | `POST /project/<P>/members/<dan>/remove` | 302 | dan не участник P; B2: new, без исполнителя, в истории in_progress → new от adm | DELETE project_members, UPDATE bugs + триггер |
| 17 | adm | `POST /admin/users/<bob>/block` | 302 | bob заблокирован; с открытых багов снят; закрытый B1 сохранил исполнителя | UPDATE users, bugs |
| 18 | adm | `POST /admin/users/<bob>/unblock` | 302 | bob активен; назначения не вернулись | UPDATE users |
| 19 | adm | `POST /admin/users/<bob>/role` — tester | 302 | роль bob = tester | UPDATE users |
| 20 | bob | `POST /bugs/<B2>/status` — rejected с причиной (bob уже tester) | 302 + сообщение об ошибке | B2 не изменился, комментария нет | SELECT |
| 21 | zoe | `GET /bugs/<B1>` — карточка | 200 | видны история и комментарий | SELECT bugs, comments, status_history |
| 22 | zoe | `GET /bugs/?status=closed` — список с фильтром | 200 | в списке только B1 | SELECT bugs |
| 23 | zoe | `GET /bugs/stats` — статистика | 200 | только проект P | SELECT v_bug_stats, v_open_bugs_by_assignee |
| 24 | adm | `GET /project/<P>` — страница проекта | 200 | участники и баги P | SELECT projects, project_members, bugs |

## Итоговая проверка

- Ни одного ответа 5xx.
- История B1: `new → in_progress` (bob), `in_progress → fixed` (bob),
  `fixed → closed` (zoe) — записана триггером под правами приложения.
- История B2: `new → in_progress` (dan), `in_progress → new` (adm).
- Очистку тестовых данных выполняет владелец БД: у `bugtracker_app` нет прав
  на удаление пользователей, проектов и багов (это тоже часть проверки).
