# TASK1 — этап 3: два экземпляра, Prometheus, Grafana

Проект включает работоспособные этапы 1–2 без изменения Java-кода.
Этап 3 добавляет инфраструктуру мониторинга. **Дашборды пока не создаются**:
их автоматический CLI-генератор — следующий этап.

## Запуск из корня проекта

```bash
cp -n .env.example .env
docker compose down
docker compose config --quiet
docker compose up --build -d
docker compose ps
bash check-stage3.sh
```

В файле `.env` задаётся локальный пароль администратора Grafana. Файл не добавлять
в Git: `.gitignore` уже настроен. Если `.env` создан раньше, `cp -n` его не перезапишет.

Впервые Docker может скачивать образы Prometheus и Grafana и зависимости Maven.
Если `check-stage3.sh` сообщает об ошибке, посмотреть логи:

```bash
docker compose logs --tail=100 app-1 app-2 prometheus grafana
```

## Адреса на Mac

| Сервис | Адрес | Описание |
|---|---|---|
| Java #1 | http://127.0.0.1:8080/health | `pod-1`, `dc-a` |
| Java #2 | http://127.0.0.1:8081/health | `pod-2`, `dc-b` |
| Метрики #1 | http://127.0.0.1:8080/metrics | Экспорт метрик первого экземпляра |
| Метрики #2 | http://127.0.0.1:8081/metrics | Экспорт метрик второго экземпляра |
| Prometheus | http://127.0.0.1:9090/targets | Оба target должны иметь статус UP |
| Grafana | http://127.0.0.1:3000 | Пользователь и пароль из `.env` |

Подключение Grafana к Prometheus создаётся автоматически с **UID `itmo-prometheus`**.
Открой Grafana → Explore → Prometheus, введи запрос:

```promql
sum by (pod, dc) (rate(app_http_requests_total[1m]))
```

Отдельно для p95 по всем экземплярам:

```promql
histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[1m])))
```

Чтобы появились данные по RPS, сгенерируй запросы через `bash check-stage3.sh`.
Для стабильной ненулевой линии RPS понадобится генератор нагрузки (последний этап).

## Куда приходят запросы

`curl http://127.0.0.1:8080/health` → `app-1` (контейнерный порт 8080).
`curl http://127.0.0.1:8081/health` → `app-2` (контейнерный порт 8080).

Prometheus обращается к `http://app-1:8080/metrics` и
`http://app-2:8080/metrics` по внутреннему DNS Docker Compose.
Здесь **не нужен** сетевой порт macOS, так как контейнеры в одной сети.

Экземпляры Java-сервиса хранят данные **независимо** в `ConcurrentHashMap`.
Поэтому созданная в `app-1` запись не появится в `app-2` — это намеренное
упрощение задания.

## Проверки

`bash check-stage3.sh` проверяет обе копии API, ошибки 400/404/500, нормализацию
маршрутов, наличие buckets и счётчика, доступность двух целей Prometheus,
разные метки pod/dc и datasource Grafana с фиксированным UID.

После успешных проверок:

```bash
git status
git add -A -- . ':!app-backup'
git commit -m "feat: add two app instances with Prometheus and Grafana"
git push -u origin develop
```

Данные Prometheus и Grafana сохраняются в Docker volumes.
`docker compose down` не удаляет тома; `docker compose down -v` удаляет.
