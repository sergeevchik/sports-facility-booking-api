# Отчёт по итоговому проекту DevOps

**Sports Facility Booking API**, индивидуальный проект, автор **sergeevchik**.
Репозиторий: https://github.com/sergeevchik/sports-facility-booking-api

Сервис реализует поиск свободных спортивных площадок, создание и отмену бронирований.
PostgreSQL запрещает пересечения даже при одновременных запросах и прямом INSERT.
Точный состав: [спецификация](docs/specification.md), [архитектура](docs/architecture.md).

## Обязательный порог и доказательства

| № | Требование | Прямое доказательство |
|---|---|---|
| 1 | Публичный Git-репозиторий | [Код и история](https://github.com/sergeevchik/sports-facility-booking-api), [PR #1](https://github.com/sergeevchik/sports-facility-booking-api/pull/1) |
| 2 | Нет секретов в репозитории | [.gitignore](.gitignore), [пустой шаблон](.env.example), [Settings → Secrets без значений](docs/evidence/github-secrets.jpg); [Gitleaks report](docs/evidence/gitleaks.json) и проверка всех Git blobs на фактические локальные credentials |
| 3 | Инструкция запуска | [README: быстрый запуск](README.md#быстрый-запуск), [runbook](docs/runbook.md) |
| 4 | HTTP и /health | [Примеры curl](README.md#примеры-http), [результат smoke](docs/evidence/smoke.json), [автоматизированный сценарий](scripts/smoke.py) |
| 5 | CI при push/PR в main | [Workflow](.github/workflows/ci.yml), [успешный запуск PR](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45521928124) |
| 6 | Статический анализ | [Ruff config](pyproject.toml), job Quality в указанном CI, артефакт quality-reports/ruff.json |
| 7 | Запуск Compose одной командой | [docker-compose.yml](docker-compose.yml), [README](README.md#быстрый-запуск); миграции и provisioning автоматические |
| 8 | Версионированный опубликованный образ | [GHCR package](https://github.com/sergeevchik/sports-facility-booking-api/pkgs/container/sports-facility-booking-api), [проверка релиза v1.0.0](docs/evidence/release-image.json), [HTTP smoke](docs/evidence/published-smoke.json), [публичный пакет](docs/evidence/ghcr-package.jpg) |
| 9 | Prometheus и Grafana | [Prometheus](monitoring/prometheus.yml), [дашборд](monitoring/grafana/dashboards/booking.json), [реальный скриншот](docs/evidence/grafana-dashboard.png), [проверка live samples](docs/evidence/monitoring.json) |
| 10 | Нагрузочный тест с отчётом | [Сценарий](load/locustfile.py), [отчёт с анализом и CSV](docs/evidence/load-report.md) |

## Автоматические проверки и наблюдаемое поведение

- **47 тестов** с реальным PostgreSQL, **98% coverage** приложения:
  [результат](docs/evidence/test-summary.txt), [тесты](tests/).
- Миграции проходят downgrade/upgrade на изолированной booking_test; другое имя БД отвергается.
- Проверяются пересечения, границы, часовые пояса, вместимость, отмена, повторная отмена,
  фильтры, пагинация, доступ по ключу, конкурентность и прямой обход сервисного слоя.
- Шесть одинаковых конкурентных запросов: ровно один успех и пять конфликтов.
- [Recovery evidence](docs/evidence/recovery.json): данные переживают restart API;
  при отказе БД readiness/business API дают 503, metrics — 200; БД восстанавливается без restart API.
- Нагрузка: 10 пользователей, лимит 300 с, итоговые 5801 запрос, 0 failures, p95 15 мс.
  Разница между периодическим CSV и финальной таблицей явно объяснена в отчёте.

В Actions сохраняются quality-reports (JUnit, coverage XML, Ruff) и deployment-reports
(smoke JSON, live monitoring JSON). Применимый исполняемый артефакт Python-проекта —
собранный Docker-образ с runtime-зависимостями; JAR не требуется.

## Полный цикл и публикация

Изменение кода → рабочая ветка → PR → Ruff/тесты → сборка/Compose smoke → merge →
версионированный GHCR image → pull/запуск → HTTP → Grafana.

На момент исходного PR положительный CI проверен на Linux amd64, локальный стенд —
на Apple Silicon arm64. Образ публикуется только после всех проверок main/релизного тега.
[Отрицательный CI-сценарий и исправление](docs/evidence/ci-failure.md): реальный business regression
отклонён pytest; зависимые этапы не запущены. Main защищён обязательными checks и PR.
Первая публикация успешно завершена: [CI публикации](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45522980266).
Образ скачан и запущен на Mac; OCI revision совпал с исходным SHA,
HTTP smoke и мониторинг прошли. [Результат](docs/evidence/published-image.json), [порядок проверки доставки](docs/evidence/delivery.md).

Исправление отрицательного сценария: [зелёный CI с 47 тестами и Gitleaks](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45523468579).
Релиз: [v1.0.0](https://github.com/sergeevchik/sports-facility-booking-api/releases/tag/v1.0.0),
[полностью успешный release CI](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45524063706).
[Release image evidence](docs/evidence/release-image.json): pull с пустым auth config,
нативный arm64 запуск, проверка SHA, успешный откат и возврат с сохранением 1017 броней.
[HTTP smoke релиза](docs/evidence/release-smoke.json). Релиз оставлен запущенным локально.
После тега main содержит дополнения evidence и ожидание первого scrape в проверочном
скрипте; runtime-код релиза не изменён.

## Конфигурация и отсутствие секретов

Реальные значения создаются bootstrap локально в .env с mode 600. В workflow используется
автоматический GITHUB_TOKEN; пользовательские repository/environment secrets не нужны.
Поэтому Settings → Secrets пуст, а не заполнен фиктивными переменными ради скриншота.
Снимок Settings не доказывает отсутствие утечек сам по себе: отдельно проверялась история Git.
Оригиналы учебного архива, записи, транскрипции и документы курса не публикуются.

## Документация и границы

- [Журнал команд и решений](DEVOPS_JOURNAL.md).
- [Запуск, остановка, ошибки, обновление и откат](docs/runbook.md).
- [Окружение фактической проверки](docs/evidence/environment.json).
- [Закреплённые digests базовых образов](docs/evidence/image-pins.json).

Один комплекс, операторский API с общим ключом, один Uvicorn worker; без платежей,
пользовательских ролей и регулярных занятий. HTTP-отказы 409 отделены от серверных 5xx.
Kubernetes, Terraform, Ansible и ELK не включены в обязательную часть.
Точный дедлайн, веса частей и единый процент покрытия в изученных требованиях не подтверждены.
Письменное задание предусматривает отправку ссылки на репозиторий; расхождение с ранним
устным упоминанием ZIP остаётся вопросом организационного регламента.

## Итоговый аудит

Все десять пороговых пунктов имеют прямые доказательства выше. Выполнены также
автоматические бизнес-тесты, отрицательный CI-сценарий, журнал команд, защищённый main,
проверка истории секретов, восстановление после отказа БД и совместимый откат образа.

Технических блокировок запуска/сборки/публикации не выявлено. Остаются организационные
вопросы курса: точный срок, расписание защиты и согласование способа сдачи при расхождении
устного и письменного объяснения. Дополнительные инфраструктурные расширения не заменяют
обязательные пункты и не объявлены выполненными без реализации.
