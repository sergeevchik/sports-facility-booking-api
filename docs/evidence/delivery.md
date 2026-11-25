# Проверка доставки и происхождения образа

## Первая публикация

Исходный коммит: `fec0c2d77c61486d556bc7d27adad3f33bb9cf2a`.
[Успешный CI с публикацией](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45522980266).

Публичный пакет: [GHCR](https://github.com/sergeevchik/sports-facility-booking-api/pkgs/container/sports-facility-booking-api),
[скриншот интерфейса](ghcr-package.jpg). Manifest содержит linux/amd64 и linux/arm64;
дополнительные unknown/unknown entries являются attestation manifests.

Первый проверенный manifest digest:
`sha256:129f70b184a748a831a461842cad97c77cc266e1f1c5f7a1f2b0e8e43f3eada6`.

В постоянной рабочей копии выполнены pull и
`APP_IMAGE=ghcr.io/sergeevchik/sports-facility-booking-api@sha256:129f70b184a748a831a461842cad97c77cc266e1f1c5f7a1f2b0e8e43f3eada6 docker compose up -d --no-build --wait`.

Затем успешно выполнены deployed HTTP smoke и проверка Prometheus/Grafana.
Получен native arm64 образ размером 321427819 байт, OCI revision совпал с исходным SHA.
[Данные проверки](published-image.json), [HTTP-проверки](published-smoke.json).

## Связь с релизом

Тег [v1.0.0](https://github.com/sergeevchik/sports-facility-booking-api/releases/tag/v1.0.0)
указывает на `efe87c2a3731c83e2f0da0aa8259999db1d06c09`: включает исправление
демонстрационной регрессии, 47 тестов и проверку истории Gitleaks.
Тег не передвигается; финальные дополнительные evidence-документы могут находиться
в следующих коммитах документации и проверочных инструментов main. Код runtime от этого не меняется.

Точные результаты проверки релизного образа сохраняются отдельно в release-image.json.
Digest, исходный SHA и HTTP-проверка связываются явно; наличие одного тега не считается
доказательством работоспособности приложения.

## Проверенный релиз v1.0.0

[Успешный релизный CI](https://github.com/sergeevchik/sports-facility-booking-api/actions/runs/45524063706).
Manifest digest: `sha256:c4670faa75a62b826b82f5f6cbd24bbd214e6c8d6eaf4b3d7d52313de27d0c0b`.

Релиз скачан с пустым Docker auth config, без registry-credentials, и запущен на arm64.
Проверено совпадение OCI revision с тегом Git. Размер native image — 321427564 байт.
Выполнены переход на релиз, откат к предыдущему digest и возврат к релизу.
На каждом переходе /health давал 200, сохранялись все 1017 имевшихся броней и доступ
к выбранной записи. После этого отдельно прошли HTTP smoke и live monitoring.

[Машиночитаемый результат](release-image.json), [HTTP smoke](release-smoke.json).
Стенд оставлен на v1.0.0; локальный .env выбирает этот образ. Для возврата к локальной
разработке используйте `APP_IMAGE=sports-facility-booking-api:local docker compose up -d --build --wait`.
Откат схемы БД не выполнялся; обе проверенные версии совместимы с миграцией 0001.
