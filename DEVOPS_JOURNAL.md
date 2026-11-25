# Журнал DevOps-процесса

Проект: sports-facility-booking-api. Работа индивидуальная, автор sergeevchik.
Дата начальной реализации и проверки: 25.11.2026, Europe/Moscow.
Команды ниже относятся к отдельному каталогу проекта; учебные материалы не изменяются.
Значения секретов и содержимое .env в журнал не включаются.

| Этап | Команда / действие | Полученный результат |
|---|---|---|
| Окружение | docker version | Существующий Docker Desktop доступен, Engine linux/arm64 |
| Окружение | gh auth status | Существующая авторизация GitHub работает, повторный вход не нужен |
| Git | git clone указанного репозитория | Пустой публичный репозиторий, main |
| Python | uv venv --python 3.13 | Изолированное окружение, системный Python не заменён |
| Зависимости | uv pip compile ... --universal | requirements.txt и requirements-dev.txt с точными версиями |
| Зависимости | uv pip install ...; uv pip check | Зависимости совместимы |
| Правила | pytest tests/unit -q | Проверены интервалы, границы, часовые пояса, настройки |
| PostgreSQL | docker compose -f compose.test.yml up -d --wait | Изолированная тестовая БД готова |
| Тесты | pytest --cov=app ... | 47 тестов, включая реальные конкурентные запросы; 98% покрытия |
| Качество | ruff check .; ruff format --check . | Проверки проходят |
| Конфигурация | python scripts/bootstrap.py | Локальные случайные секреты, .env с правами 600 |
| Docker | docker compose up -d --build --wait | API, PostgreSQL, Prometheus и Grafana запущены; миграция применена |
| Данные | docker compose exec -T api python -m app.seed | Демонстрационные площадки; повтор не создаёт дубликатов |
| HTTP | python scripts/smoke.py | Бронь, конфликт, отмена, повторная отмена, повторное бронирование работают |
| Наблюдаемость | python scripts/check_monitoring.py | Реальные samples и provisioned dashboard подтверждены |
| Инцидент | python scripts/check_recovery.py | Перезапуск сохраняет данные; отказ БД даёт 503, восстановление без restart API |
| Нагрузка | python scripts/run_load.py --users 10 --seconds 300 | CSV/HTML и анализ в docs/evidence/load-report.md |
| Воспроизводимость | Docker manifest digest / Action commit SHA | Базы образов и Actions закреплены |
| Публикация кода | Рабочая ветка и PR #1 | Проверки на GitHub, исходники курса не включены |

## Найденные проблемы и исправления

- Окружение Mac имеет proxy-настройки: первые HTTPX-проверки localhost попадали в proxy.
  Smoke/monitoring и Locust используют прямое подключение; сам API был исправен.
- Первоначальная миграция зависела от ORM metadata: заменена самостоятельным DDL-снимком,
  чтобы будущие изменения моделей не меняли смысл старой миграции.
- Для воспроизводимой сборки на разных архитектурах lock-файлы сформированы в universal-режиме.
- Ожидаемые 409 учитываются отдельно от 5xx; эксперимент отказа БД отделён от нагрузки.

Подробные фактические результаты и ссылки на GitHub приведены в REPORT.md.
