# TZ-App-Backend

REST API на Django REST Framework с JWT-аутентификацией и системой разграничения прав доступа
(RBAC) на основе ролей.

Учётная запись администратора — создаётся командой `python manage.py seed_data` (см. ниже):

```
Email:    admin@gmail.com
Пароль:   admin123
```

---

## 1. Установка и запуск

Требуется **PostgreSQL**. Резервного варианта на SQLite нет: при неверной настройке проект
намеренно не запустится, а не начнёт молча работать с другой базой.

### Что нужно заранее

| | Версия |
| --- | --- |
| Python | 3.12 |
| PostgreSQL | 16 (проверено на 16.14) |

### Шаг 1. Виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### Шаг 2. Настройки окружения

Файл `.env` в репозитории отсутствует (он в `.gitignore`), поэтому его нужно создать из шаблона:

```bash
cd src
cp .env.example .env
```

Затем откройте `.env` и заполните два значения:

```bash
# 1. Сгенерируйте SECRET_KEY и вставьте его в .env:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 2. Укажите DB_NAME и DB_USER вашей PostgreSQL.
```

Полный список переменных `.env` — их всего 11, и все они действительно читаются настройками:

| Переменная | Назначение |
| --- | --- |
| `DEBUG` | `1` — режим разработки, `0` — production. Других значений быть не должно |
| `SECRET_KEY` | Подписывает JWT. Должен быть длинным и случайным |
| `ALLOWED_HOSTS` | Читается только при `DEBUG=0` |
| `CORS_ALLOWED_ORIGINS` | Читается только при `DEBUG=0` |
| `CSRF_TRUSTED_ORIGINS` | Читается только при `DEBUG=0` |
| `DB_TYPE` | Должен быть `psql`, иначе `ImproperlyConfigured` при старте |
| `DB_NAME` | Имя базы, например `tz_app` |
| `DB_USER` | Пользователь PostgreSQL |
| `DB_PASSWORD` | Пусто при подключении через Unix-сокет |
| `DB_HOST` | **Оставьте пустым** — тогда используется локальный Unix-сокет (peer-аутентификация, без пароля). Если указать хост, потребуется `DB_PASSWORD` |
| `DB_PORT` | `5432` |

### Шаг 3. Зависимости

```bash
pip install -r requirements/dev.txt
```

`requirements/` устроены цепочкой: `dev.txt` и `production.txt` подключают `common.txt` через `-r`.
Библиотека времени выполнения → `common.txt`; инструменты разработки (pytest, ruff) → `dev.txt`.

### Шаг 4. База данных

```bash
createdb tz_app
python manage.py migrate
```

### Шаг 5. Тестовые данные

```bash
python manage.py seed_data
```

Создаёт роли, права, связи между ними и администратора. Команда **идемпотентна** — её можно
запускать сколько угодно раз (подробности в разделе «Команда seed_data»).

### Шаг 6. Запуск

```bash
python manage.py runserver
```

API доступен по адресу `http://127.0.0.1:8000/api/v1/`.

> Все команды выполняются из каталога `src/` — там лежит `manage.py`. Флаг настроек указывать не
> нужно: `manage.py` сам выставляет `DJANGO_SETTINGS_MODULE=config.settings`, а значение `DEBUG`
> в `.env` выбирает ветку development/production.

---

## 2. Список URL-адресов

### Документация

| URL | Что это |
| --- | --- |
| `/api/v1/docs/` | **Swagger UI** — интерактивная документация, можно выполнять запросы прямо из браузера |
| `/api/v1/redoc/` | ReDoc — та же схема, другой вид |
| `/api/v1/schema/` | Схема OpenAPI в исходном виде (YAML) |
| `/admin/` | Стандартная админка Django (роли, права, пользователи) |

### Аутентификация и профиль

| Метод | URL | Доступ | Результат |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register/` | — | 201, создаёт активного пользователя |
| POST | `/api/v1/auth/login/` | — | 200, `data` = `{refresh, access}` |
| POST | `/api/v1/auth/logout/` | ✅ токен | 200, refresh-токен в чёрном списке |
| GET | `/api/v1/auth/profile/` | ✅ токен | 200, текущий пользователь |
| PATCH | `/api/v1/auth/profile/` | ✅ токен | 200, обновление профиля |
| DELETE | `/api/v1/auth/profile/` | ✅ токен | 200, мягкое удаление |

### Роли

| Метод | URL | Требуемое право |
| --- | --- | --- |
| GET | `/api/v1/roles/` | `role.view` |
| GET | `/api/v1/roles/{id}/` | `role.view` |
| POST | `/api/v1/roles/` | `role.manage` |
| PUT | `/api/v1/roles/{id}/` | `role.manage` |
| PATCH | `/api/v1/roles/{id}/` | `role.manage` |
| DELETE | `/api/v1/roles/{id}/` | `role.manage` |

### Права

| Метод | URL | Требуемое право |
| --- | --- | --- |
| GET | `/api/v1/permissions/` | `permission.view` |
| GET | `/api/v1/permissions/{id}/` | `permission.view` |
| POST | `/api/v1/permissions/` | `permission.manage` |
| PUT | `/api/v1/permissions/{id}/` | `permission.manage` |
| PATCH | `/api/v1/permissions/{id}/` | `permission.manage` |
| DELETE | `/api/v1/permissions/{id}/` | `permission.manage` |

### Назначение прав

| Метод | URL | Требуемое право | Действие |
| --- | --- | --- | --- |
| POST | `/api/v1/assign-role/` | `role.manage` | **Добавить** роли пользователю |
| PUT | `/api/v1/assign-role/` | `role.manage` | **Заменить** роли пользователя |
| DELETE | `/api/v1/assign-role/` | `role.manage` | **Убрать** роли у пользователя |
| POST | `/api/v1/assign-permission/` | `permission.manage` | **Добавить** права роли |
| PUT | `/api/v1/assign-permission/` | `permission.manage` | **Заменить** права роли |
| DELETE | `/api/v1/assign-permission/` | `permission.manage` | **Убрать** права у роли |

### Mock-объекты бизнес-приложения

| Метод | URL | Требуемое право |
| --- | --- | --- |
| GET | `/api/v1/mock/projects/` | `mock.view` |
| GET | `/api/v1/mock/orders/` | `mock.view` |
| GET | `/api/v1/mock/employees/` | `mock.view` |
| GET | `/api/v1/mock/documents/` | `mock.view` |

---

## 3. Схема разграничения прав доступа (RBAC)

Доступ определяется **правами, которые пользователь получает через свои роли**:

```
User ──< UserRole >── Role ──< RolePermission >── Permission
```

Пользователь может иметь **несколько ролей**, и его действующие права — это **объединение**
всех прав всех его ролей. Право обозначается точечным кодом (`code`), например `mock.view`;
именно этот код проверяет эндпоинт.

| Таблица | Ключевые поля |
| --- | --- |
| `Role` | `name` (уникально), `description` |
| `Permission` | `code` (уникально), `name`, `description` |
| `UserRole` | `user`, `role` — пара уникальна |
| `RolePermission` | `role`, `permission` — пара уникальна |

Это собственные таблицы проекта, к системе прав `django.contrib.auth` они отношения не имеют.

### Как проверяются права

1. Запрос приходит с заголовком `Authorization: Bearer <access>`.
2. SimpleJWT проверяет подпись и срок действия токена и отклоняет его, если пользователь
   неактивен. Токена нет или он неверный → **401 Unauthorized**.
3. Эндпоинт вычисляет коды прав пользователя, проходя цепочку
   `User → UserRole → Role → RolePermission → Permission.code`.
4. Если нужного кода в этом наборе нет → **403 Forbidden**.
5. Иначе выдаётся запрошенный ресурс.

Разделение 401/403 сделано намеренно: **401** значит «мы не знаем, кто вы», **403** — «мы знаем,
кто вы, и вам этого нельзя».

В коде — хелперы в `apps/rbac/services.py`, классы прав в `apps/rbac/permissions.py`:

```python
from apps.rbac.permissions import HasPermission, require_permissions

class MockProjectsView(APIView):
    permission_classes = [require_permissions('mock.view')]

class RoleListView(APIView):                  # то же самое, но объявлено на view
    permission_classes = [HasPermission]
    required_permissions = 'role.view'

require_permissions('role.view', 'role.manage')                     # нужны оба
require_permissions('role.view', 'role.manage', require_all=False)  # достаточно любого
```

```python
from apps.rbac.services import get_user_permission_codes, user_has_permission

user_has_permission(request.user, 'mock.view')   # -> bool
get_user_permission_codes(request.user)          # -> frozenset кодов
```

Вычисление прав пользователя стоит **один запрос к БД** независимо от количества ролей, а
результат кешируется на время текущего запроса. `is_superuser` **не даёт обхода**: права берутся
только из базы, поэтому суперпользователь без ролей не получит доступ никуда — это осознанное
решение, чтобы `User → Roles → Permissions` был единственным путём авторизации.

---

## 4. Аутентификация

JWT через `djangorestframework-simplejwt`. Сначала регистрация, затем login — он возвращает пару
токенов. Access-токен отправляется в каждом последующем запросе:

```
Authorization: Bearer <access token>
```

**Регистрация** принимает имя, фамилию, отчество, email, пароль и повтор пароля:

```json
{
  "first_name": "Иван",
  "last_name": "Петров",
  "middle_name": "Сергеевич",
  "email": "ivan@example.com",
  "password": "Password123!",
  "confirm_password": "Password123!"
}
```

Email проверяется на уникальность **без учёта регистра**, пароли должны совпадать, пароль
проверяется валидаторами Django и хранится в виде хеша (pbkdf2).

**Logout** заносит refresh-токен в чёрный список, и обменять его на новый access-токен больше
нельзя. Сам access-токен продолжает действовать до истечения срока — это неотъемлемое свойство
stateless JWT.

**Удаление профиля (мягкое):** `is_active` становится `False`, но строка в базе остаётся. Все
refresh-токены учётной записи заносятся в чёрный список, а текущий access-токен перестаёт
работать немедленно, потому что SimpleJWT отклоняет токены неактивных пользователей. Войти
повторно такая учётная запись уже не может.

---

## 5. Роли

Только у роли **Admin** есть коды `role.view`/`role.manage`, поэтому на практике эти эндпоинты
доступны лишь администратору. Но это следствие данных в таблицах, а не жёстко зашитая проверка:
достаточно выдать `role.view` другой роли, и чтение откроется без изменения кода.

```bash
GET /api/v1/roles/?page=2&page_size=5          # пагинация
GET /api/v1/roles/?search=manager              # поиск по name и description
GET /api/v1/roles/?ordering=-created_at        # name | created_at | updated_at, «-» — по убыванию
```

Поле `name` обязательное, обрезается по краям, максимум 100 символов и уникально **без учёта
регистра** — `admin` будет отклонён, если уже есть `Admin`. Права роли (`permissions`) выдаются
только на чтение; изменяются они через `assign-permission`.

Удаление роли удаляет и её связи с правами, и её назначения пользователям (сами пользователи и
права остаются). Удаление роли **Admin** лишит администратора всех прав и заблокирует API —
восстановить можно командой `python manage.py seed_data`.

---

## 6. Права

**Фильтрация** — точная, в отличие от `?search=`, который ищет нестрого по коду, названию и
описанию:

```bash
GET /api/v1/permissions/?code=mock.view          # точное совпадение, без учёта регистра
GET /api/v1/permissions/?code_contains=manage    # подстрока кода
GET /api/v1/permissions/?namespace=user          # всё из пространства user.*
GET /api/v1/permissions/?name=mock               # подстрока названия
GET /api/v1/permissions/?role_name=Manager       # что есть у роли
GET /api/v1/permissions/?role=<role-uuid>
GET /api/v1/permissions/?unassigned=true         # права, не выданные ни одной роли
GET /api/v1/permissions/?created_after=2026-01-01T00:00:00Z
GET /api/v1/permissions/?search=deactivate       # нестрогий поиск по трём полям
GET /api/v1/permissions/?ordering=-code          # code | name | created_at | updated_at
```

`code` **приводится к нижнему регистру при записи** и должен состоять из слов в нижнем регистре,
разделённых `.`, `_` или `-`: отправите `Report.Export` — сохранится `report.export`. Это не
косметика: проверка прав сравнивает коды строго по строке, поэтому запись `Report.Export` никогда
не совпала бы с проверкой `report.export` и молча не работала бы.

Удаление права отзывает его у всех ролей (сами роли остаются). Любой эндпоинт, защищённый
удалённым кодом, после этого закроется для всех — каталог восстанавливается через `seed_data`.

---

## 7. Назначение ролей пользователям

Один URL, три операции, разделённые HTTP-методом. Всем нужен `role.manage`.

```json
{ "user": "<user-uuid>", "roles": ["<role-uuid>", "<role-uuid>"] }
```

Ответ содержит итоговое состояние и то, что изменилось:

```json
{
  "success": true,
  "message": "Roles assigned successfully.",
  "data": {
    "user": { "id": "…", "email": "john@x.com", "full_name": "John Doe", "is_active": true },
    "roles": ["Employee", "Manager"],
    "added": ["Employee"],
    "already_assigned": ["Manager"]
  }
}
```

PUT сообщает `added` / `removed` / `unchanged`; DELETE — `removed` / `not_assigned`.

**Идемпотентность.** Назначение роли, которая уже есть, или снятие роли, которой нет, — не ошибка,
а сообщение в ответе. Повторять запросы безопасно.

**Валидация.** Пользователь и все роли должны существовать, идентификаторы не должны повторяться
внутри одного запроса, список `roles` не может быть пустым (кроме PUT — там пустой список снимает
все роли). Один неизвестный id отклоняет весь запрос: запись идёт в транзакции, поэтому частично
верные данные не сохранятся.

---

## 8. Назначение прав ролям

Та же схема на уровень выше. Всем операциям нужен `permission.manage`.

```json
{ "role": "<role-uuid>", "permissions": ["<permission-uuid>"] }
```

### Изменения применяются немедленно

Каждый пользователь с этой ролью увидит изменение на **следующем же запросе** — без повторного
входа, без обновления токена:

```
GET /api/v1/roles/   с токеном Guest'а        -> 403
POST /api/v1/assign-permission/  выдаём Guest роли право role.view
GET /api/v1/roles/   тот же самый токен       -> 200
DELETE /api/v1/assign-permission/  забираем право
GET /api/v1/roles/   тот же самый токен       -> 403
```

Это свойство архитектуры, а не отдельный механизм: коды прав читаются из базы на каждом запросе и
кешируются только на время этого запроса, поэтому устаревшему состоянию между запросами взяться
неоткуда. **JWT несёт идентификацию, а не права** — именно поэтому токен, выданный до выдачи
права, его подхватывает.

---

## 9. Mock-объекты бизнес-приложения

Вымышленные объекты, на которых показана работа системы разграничения доступа. **Таблиц в БД
нет** — данные статические, ответ представляет собой обычный массив.

```bash
GET /api/v1/mock/projects/
{"success": true, "message": "Projects retrieved successfully.",
 "data": [{"id": 1, "name": "CRM"}, {"id": 2, "name": "ERP"}]}

GET /api/v1/mock/orders/
{"success": true, "message": "Orders retrieved successfully.",
 "data": [{"id": 100, "price": 500}]}
```

Это те эндпоинты, до которых может дотянуться **не администратор**, поэтому на них правила RBAC
видны нагляднее всего. С данными из `seed_data`:

| Кто обращается | Результат |
| --- | --- |
| Аноним (без токена) | **401** |
| Guest (роль без прав) | **403** |
| Employee (`mock.view`) | **200** |
| Manager (`mock.view`, `user.view`) | **200** |
| Admin (все 8 прав) | **200** |

---

## 10. Формат ответа

**Любой** ответ любого эндпоинта — это один из двух конвертов, третьего не бывает.

Успех:

```json
{ "success": true, "message": "Roles retrieved successfully.", "data": { } }
```

Ошибка:

```json
{ "success": false, "message": "Validation failed.", "errors": { "name": ["This field may not be blank."] } }
```

`success` позволяет клиенту понять форму ответа, не разбирая код статуса. `data` — полезная
нагрузка: объект, массив или `{}`, если возвращать нечего. `errors` — детализация по полям, `{}`
для ошибок без разбивки по полям. Конверты не смешиваются: в успешном ответе нет ключа `errors`,
в ошибочном — нет `data`.

У списочных эндпоинтов пагинация лежит **внутри** `data`:

```json
{
  "success": true,
  "message": "Roles retrieved successfully.",
  "data": { "count": 4, "pages": 1, "results": [ {"id": "…", "name": "Admin"} ] }
}
```

Конверт накладывается в `api/renderers.py` (успех) и `api/exceptions.py` (ошибки), а не в самих
view — поэтому под то же правило попадают и generic-классы DRF, и новый эндпоинт не сможет о нём
забыть.

### Удаление и logout отвечают 200, а не 204

HTTP запрещает тело у ответов `204`/`205`, поэтому такие эндпоинты стали бы единственным
исключением из формата. Вместо этого они возвращают **200** с конвертом:

```json
{ "success": true, "message": "Role deleted successfully.", "data": {} }
```

Касается `DELETE /auth/profile/`, `POST /auth/logout/`, `DELETE /roles/{id}/`,
`DELETE /permissions/{id}/`. Больше в них ничего не изменилось.

### Таблица ошибок

| Ситуация | Код | `message` | `errors` |
| --- | --- | --- | --- |
| Нет токена или он неверный | 401 | `Authentication credentials were not provided.` | `{}` |
| Есть токен, но нет права | 403 | `This action requires the role.view permission.` | `{}` |
| Ошибка валидации | 400 | `Validation failed.` | `{"name": ["This field may not be blank."]}` |
| Неизвестный id | 404 | `No Role matches the given query.` | `{}` |
| Неверный метод | 405 | `Method "POST" not allowed.` | `{}` |
| Необработанное исключение | 500 | `Internal server error.` | `{}` |

**Ответ 500 никогда не раскрывает внутренности.** Тип исключения, сообщение и traceback уходят в
лог `api.exceptions`, клиент видит только общую фразу. Поэтому лог — единственная запись о сбое:
в production логирование должно быть настроено.

---

## 11. Команда seed_data

```bash
cd src
python manage.py seed_data
```

Создаёт четыре роли, восемь прав, связи между ними и администратора. **Идемпотентна**: сколько
бы раз её ни запускали, существующие записи переиспользуются, дубликаты не создаются.

Роли и их права после заполнения:

| Роль | Права |
| --- | --- |
| **Admin** | все восемь |
| **Manager** | `mock.view`, `user.view` |
| **Employee** | `mock.view` |
| **Guest** | нет |

Восемь кодов прав: `user.view`, `user.update`, `user.delete`, `role.view`, `role.manage`,
`permission.view`, `permission.manage`, `mock.view`.

Команда также создаёт `admin@gmail.com` / `admin123` как суперпользователя **и выдаёт ему роль
Admin**. Именно эта роль и даёт ему полномочия: авторизация решается только таблицами RBAC, а
`is_superuser` сам по себе прав в API не даёт — суперпользователь без ролей не пройдёт ни на один
защищённый эндпоинт. Если учётная запись уже существует, команда не трогает её пароль, а лишь
проверяет флаги и роль.

Каталог в `apps/rbac/management/commands/seed_data.py` — источник истины: повторный запуск
восстановит изменённое описание роли или права и заново создаст удалённую связь.

По умолчанию команда только **добавляет** связи, поэтому выданное вручную право не будет молча
отозвано. Чтобы привести состояние ровно к описанному в каталоге и убрать лишнее:

```bash
python manage.py seed_data --prune
```

---

## 12. Postman

В репозитории две коллекции: `postman-workflows.json` (запросы) и `postman-variables.json`
(окружение).

### Как пользоваться

1. Откройте Postman.
2. **Import** → выберите `src/postman-variables.json`. Это **окружение** — выберите его в
   выпадающем списке справа сверху.
3. **Import** → выберите `src/postman-workflows.json`. Это **коллекция**.
4. Убедитесь, что сервер запущен (`python manage.py runserver`) и данные заполнены
   (`python manage.py seed_data`).
5. Выполните запрос **1. Auth → Login (admin)**.

Больше ничего вручную вводить не нужно: скрипт этого запроса сам сохраняет пару токенов в
переменные окружения, а авторизация уровня коллекции подставляет access-токен во все запросы
администратора. Идентификаторы ролей и прав тоже подхватываются автоматически — папки
рассчитаны на выполнение **сверху вниз**, каждая сохраняет то, что понадобится следующей.

### Что внутри

| Папка | Запросов | Что показывает |
| --- | --- | --- |
| **1. Auth** | 11 | Регистрация → login → профиль → обновление → logout → мягкое удаление → доказательство, что войти больше нельзя |
| **2. Roles (admin)** | 9 | CRUD ролей, поиск, сортировка, пагинация, ошибка на дубликат имени |
| **3. Permissions (admin)** | 11 | CRUD прав, все шесть фильтров, ошибка на неверный код |
| **4. Assignment (admin)** | 8 | Назначение/замена/снятие ролей и прав, идемпотентность |
| **5. Mock business objects** | 4 | Четыре mock-эндпоинта |
| **6. 401 / 403 / 404 / 405** | 7 | Правила доступа из ТЗ в явном виде |

Всего **50 запросов и 107 проверок**. Проверяется не только код ответа, но и конверт
(`success`/`message`/`data`), поэтому коллекция заодно работает как smoke-тест контракта.

### Запуск целиком из консоли

```bash
npx newman run src/postman-workflows.json -e src/postman-variables.json
```

Коллекцию можно запускать **повторно**: регистрация каждый раз генерирует уникальный email, а
созданные роли и права удаляются в конце своих папок, так что заполненные данные остаются в
исходном состоянии.

---

## 13. Разработка

Тесты и линтер запускаются **из корня репозитория**, а не из `src/`:

```bash
pytest                 # 455 тестов; нужен доступный PostgreSQL
ruff check .           # должен вывести "All checks passed!"
ruff check . --fix     # безопасные автоисправления
```

Для тестов нужна роль PostgreSQL с правом `CREATEDB` — pytest-django создаёт базу
`test_<DB_NAME>`.

---

## 14. Структура проекта

```
src/
  api/                  HTTP-слой: маршруты, view, сериализаторы. Django-приложениями не является.
    auth/               регистрация, login, logout, профиль
    user/               роли, права, назначения, mock
    exceptions.py       конверт ошибок  -> REST_FRAMEWORK['EXCEPTION_HANDLER']
    renderers.py        конверт успеха  -> DEFAULT_RENDERER_CLASSES
    schema.py           конверт в Swagger -> SPECTACULAR POSTPROCESSING_HOOKS
    pagination.py       CustomPagination -> DEFAULT_PAGINATION_CLASS
  apps/                 Django-приложения: модели и миграции
    users/              модель User
    rbac/               Role/Permission/UserRole/RolePermission, services,
                        классы прав, команда seed_data
  config/               настройки (base/development/production), urls, wsgi/asgi
  requirements/         common.txt <- dev.txt / production.txt
```

Правило: модель или миграция → `src/apps/<домен>/`; URL, view или сериализатор →
`src/api/<аудитория>/`. Зависимость односторонняя: `api/` импортирует из `apps/`, но никогда
наоборот.

Production разворачивается через gunicorn: `deployment/gunicorn.service` + `gunicorn.socket` за
`deployment/nginx.conf`.
