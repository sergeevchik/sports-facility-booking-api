# Sports Facility Booking API

[![CI](https://github.com/sergeevchik/sports-facility-booking-api/actions/workflows/ci.yml/badge.svg)](https://github.com/sergeevchik/sports-facility-booking-api/actions/workflows/ci.yml)

REST-сервис одного спортивного комплекса: поиск свободных площадок, бронирование,
отмена и защита от двойного бронирования, включая конкурентные запросы.
Проект выполняется индивидуально: **sergeevchik**. Приложение и инфраструктура созданы
для этого проекта; за основу не копировался готовый учебный сервис.

**[Отчёт и доказательства выполнения → REPORT.md](REPORT.md)**

## Быстрый запуск

Нужны Git, Python 3.13+ для локальных инструментов и работающий Docker с Compose v2.
Само приложение запускается в контейнере Python 3.13.
Apple Silicon поддерживается; опубликованные образы предназначены для arm64 и amd64.

```bash
git clone https://github.com/sergeevchik/sports-facility-booking-api.git
cd sports-facility-booking-api
python3 scripts/bootstrap.py
docker compose up -d --build --wait
docker compose exec -T api python -m app.seed
curl --noproxy '*' http://localhost:8000/health
```

Ожидаемый ответ: `{"status":"ok","version":"1.0.0","database":"ready"}`.
`bootstrap.py` создаёт локальный `.env` со случайными значениями и правами 600,
не печатает секреты и не перезаписывает существующий файл.
После настройки окружения обычный запуск всего стенда — **`docker compose up -d`**.
В установках с отдельной совместимой командой допустима форма **`docker-compose up -d`**.
Создание схемы БД и её обновление происходят автоматически перед стартом API.
Заполнение демонстрационных площадок выполняется явно и повторно безопасно.

Адреса на локальной машине:

| Назначение | Адрес |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| OpenAPI | http://localhost:8000/openapi.json |
| Health | http://localhost:8000/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000/d/sports-booking |

Для API нажмите **Authorize** в Swagger и укажите значение `API_KEY` из своего `.env`.
Для Grafana используйте логин `admin` и свой `GRAFANA_ADMIN_PASSWORD` из `.env`.
Не публикуйте этот файл и не включайте его значения в скриншоты.
Порты привязаны к loopback; PostgreSQL основного стенда наружу не публикуется.

## Примеры HTTP

В своём терминале можно загрузить локальные переменные без вывода их значений:

```bash
set -a
source .env
set +a
curl --noproxy '*' -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/facilities
```

Ответ `200`: объект с `items`, `total`, `limit`, `offset`.
Без корректного ключа бизнес-эндпоинты возвращают `401`.

```bash
curl --noproxy '*' -X POST http://localhost:8000/api/v1/bookings \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"facility_id":"<UUID из каталога>","customer_ref":"demo-customer","participants":2,"starts_at":"2030-06-02T10:00:00+03:00","ends_at":"2030-06-02T11:00:00+03:00"}'
```

Замените UUID и используйте актуальную будущую дату. Успех — `201` с UUID брони.
Повтор той же брони — `409`, `code=booking_conflict`.
`POST /api/v1/bookings/{id}/cancel` — `200`, `status=cancelled`.
Повторная отмена возвращает прежний результат, отмена после начала — `409`.
Для полностью автоматической проверки без ручной подстановки UUID используйте smoke-скрипт ниже.

## Правила и API

- Вся площадка бронируется целиком; число участников ограничено вместимостью.
- Часовой пояс комплекса — Europe/Moscow; хранение и ответы — UTC.
- Входные даты требуют UTC-смещения; интервал начинается в будущем.
- Время кратно 30 минутам, длительность 30–180 минут, часы работы 08:00–22:00.
- Соседние интервалы допустимы: `[10:00, 11:00)` и `[11:00, 12:00)`.
- Отмена возможна до начала; отменённые записи сохраняются в истории.
- Площадку нельзя отключить при будущих или текущих подтверждённых бронях.
- Поиск доступности не резервирует место; окончательное решение принимает транзакция создания.

Полные контракт, правила и ограничения: [спецификация](docs/specification.md).
Архитектура: [описание и схема](docs/architecture.md).

## Разработка и тесты

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
docker compose -f compose.test.yml up -d --wait
ruff check .
ruff format --check .
pytest --cov=app --cov-report=term-missing --cov-report=xml:artifacts/coverage.xml \
  --junitxml=artifacts/junit.xml
python scripts/smoke.py --output artifacts/smoke.json
python scripts/check_monitoring.py
```

Тестовая БД отдельная: `booking_test` на `127.0.0.1:55432` с одноразовым хранилищем.
Тесты **очищают только её**; другое имя БД отвергается. Временная тестовая БД использует
trust-аутентификацию и доступна только через loopback; основной стенд использует случайный пароль.
Каждый запуск тестов проверяет downgrade/upgrade миграций, затем выполняет unit,
интеграционные и конкурентные сценарии. Проверки времени используют управляемые часы.

Для изменения зависимостей используйте `uv pip compile pyproject.toml --universal -o requirements.txt`
и `uv pip compile pyproject.toml --extra dev --universal -o requirements-dev.txt`.
Оба файла с точными версиями сохраняются в Git.

Локальный запуск приложения без контейнера возможен с `DATABASE_URL`, `API_KEY` и
доступным PostgreSQL: `alembic upgrade head`, затем `uvicorn app.asgi:app --no-access-log`.
В основном Compose PostgreSQL намеренно не публикует порт: для такого режима нужна
отдельная локальная БД. Не направляйте тесты на рабочую БД.

## CI и версии

[GitHub Actions](.github/workflows/ci.yml) выполняет Ruff, проверку зависимостей,
все тесты с PostgreSQL, сборку и запуск полного Compose-стенда, smoke и проверку мониторинга.
Отчёты JUnit, coverage, Ruff и smoke сохраняются как Actions artifacts.
При push в `main` или тега после успешных проверок публикуется multi-platform образ в GHCR:

- `ghcr.io/sergeevchik/sports-facility-booking-api:sha-<полный commit SHA>`;
- `:main` — текущая проверенная основная ветка;
- `:v1.0.0` — релиз.

OCI labels содержат ссылку на репозиторий, исходный SHA и версию.
Для публикации используется встроенный `GITHUB_TOKEN` с `packages: write`, без личного PAT в проекте.
PR выполняет проверки без публикации образа.

Запуск выбранного опубликованного образа вместо локальной сборки:

```bash
docker pull ghcr.io/sergeevchik/sports-facility-booking-api:v1.0.0
APP_IMAGE=ghcr.io/sergeevchik/sports-facility-booking-api:v1.0.0 \
  docker compose up -d --no-build --wait
```

Точный digest и результаты фактической проверки перечислены в отчёте.
Для воспроизводимой проверки предпочтителен digest либо тег с SHA.

## Мониторинг, нагрузка, восстановление

Grafana автоматически получает datasource и [дашборд](monitoring/grafana/dashboards/booking.json).
Панели показывают запросы, p95, 4xx/5xx отдельно, `up`, готовность БД, создания,
отмены и конфликты бронирования. Бизнес-конфликт `409` не является внутренней ошибкой.
`/metrics` не включает себя в HTTP-статистику; метки используют шаблоны маршрутов.

```bash
python scripts/run_load.py --users 10 --seconds 300
python scripts/check_recovery.py
```

Нагрузка направляется только на этот локальный стенд. Результаты находятся в `artifacts/load/`.
Скрипт восстановления создаёт собственную тестовую бронь, перезапускает API,
временно останавливает **БД этого Compose-проекта**, проверяет `503`, восстанавливает БД
и проверяет сохранность записи. Выполняйте его отдельно от измерения нормальной нагрузки.

Эксплуатация, типовые проблемы и откат: [runbook](docs/runbook.md).
Команды и результаты: [DEVOPS_JOURNAL.md](DEVOPS_JOURNAL.md).

## Остановка

```bash
docker compose down
docker compose -f compose.test.yml down
```

Обычный `down` сохраняет данные основного стенда. `down -v` удаляет его тома;
эта команда нужна только при намеренном сбросе собственных данных.

Проект демонстрирует операторский REST API. Платежи, пользовательские аккаунты,
повторяющиеся занятия и публичный интернет-деплой не входят в текущий объём.
Учебные записи, транскрипции и другие материалы курса в репозиторий не включаются.
