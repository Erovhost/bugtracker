# Баг-трекер

Учебный веб-проект: учёт багов в проектах с ролями (администратор,
тестировщик, разработчик), жизненным циклом бага, историей статусов и
статистикой. Flask + PostgreSQL.

> README дополняется: описание, стек, запуск и деплой — на следующем этапе.

## Тесты

Тесты работают с **отдельной базой** — её имя должно заканчиваться на `_test`
(тесты стирают в ней данные). Строка подключения — `TEST_DATABASE_URL` в `.env`
(образец в `.env.example`). Базу создаёт администратор PostgreSQL:

```powershell
psql -U postgres -c "CREATE DATABASE bugtracker_test OWNER bugtracker ENCODING 'UTF8' TEMPLATE template0;"
```

Запуск (из папки проекта, виртуальное окружение активно):

```powershell
pytest                     # все тесты
pytest -m "not e2e"        # быстро, без браузера
pytest -m e2e              # только сквозные тесты в браузере
pytest -m e2e --headed --slowmo 500   # показать окно браузера и замедлить действия
```

### Сквозные тесты в браузере (Playwright)

e2e-тесты запускаются в **установленном браузере — Microsoft Edge или Google
Chrome**. Отдельно скачивать браузеры Playwright (`playwright install`) **не
нужно**.

По умолчанию используется Edge — он есть в Windows. Настройка — `addopts` в
`pytest.ini`: `--browser-channel msedge`. Чтобы запустить в Chrome, укажите
канал в командной строке (он главнее значения из `pytest.ini`):

```powershell
pytest -m e2e --browser-channel chrome
```

Если выбранного браузера нет на компьютере, Playwright сообщит `Chromium distribution 'chrome' is not found` — установите браузер
или используйте другой канал.

### Что проверяют тесты

| Файл | Что проверяет |
|---|---|
| `tests/test_workflow.py` | правила жизненного цикла бага (без базы) |
| `tests/test_access.py` | права доступа; все маршруты: вход обязателен, действия только POST, CSRF |
| `tests/test_auth.py` | вход, выход, регистрация, `flask create-admin` |
| `tests/test_scenarios.py` | 24 сквозных сценария под ролью БД `bugtracker_app` (`docs/test_scenarios.md`) |
| `tests/test_db_roles.py` | права ролей PostgreSQL (`sql/grants.sql`) |
| `tests/test_e2e.py` | вход, создание бага, смена статуса в браузере |
| `tests/test_infrastructure.py` | сама тестовая инфраструктура |

Тесты ролей и сценарии под `bugtracker_app` пропускаются, если в `.env` нет
`APP_DATABASE_URL` / `READONLY_DATABASE_URL` (роли создаёт `sql/roles.sql`).
